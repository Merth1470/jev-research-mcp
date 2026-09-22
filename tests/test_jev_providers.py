"""JEV providers: HTTP fallback contract + SDK adapter mapping (all offline)."""

from __future__ import annotations

import sys
import types
from typing import Any

import httpx
import pytest

from jev_evidence_mcp.errors import ErrorCode, EvidenceError
from jev_evidence_mcp.jev.http_provider import HttpDecisionProvider
from jev_evidence_mcp.jev.interface import DecisionResult
from jev_evidence_mcp.jev.sdk_provider import SdkDecisionProvider, _map_sdk_error

QUESTIONS = {
    "relevant__r0": {"type": "noul", "instructions": "Relevant?"},
    "useful__r0": {"type": "noul", "instructions": "Useful?"},
}
META = {"relevant__r0": "relevant__r0", "useful__r0": "useful__r0"}
STATE = {"task": "q", "candidates": [{"id": "r0"}]}


def _ok_payload() -> dict[str, object]:
    return {
        "model": "jev-1.13.0",
        "answers": {
            "relevant__r0": {"type": "noul", "noul": 0.95},
            "useful__r0": {"type": "noul", "noul": 0.2},
        },
        "usage": {"input_tokens": 100, "output_tokens": 5},
    }


async def test_http_success_single_call_for_many_questions_async() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["authorization"].startswith("Bearer ")
        body = httpx.Response(200, json=_ok_payload())
        return body

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = HttpDecisionProvider(api_key="secret", client=client)
    result = await provider.decide_questions(state=STATE, questions=QUESTIONS, meta=META)
    assert len(calls) == 1  # one state + many questions = one HTTP call
    assert result.by_candidate("r0") == {"relevant": 0.95, "useful": 0.2}
    assert result.model == "jev-1.13.0"
    assert result.input_tokens == 100


async def test_http_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "bad key"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(EvidenceError) as exc_info:
        await HttpDecisionProvider(api_key="bad", client=client).decide_questions(
            state=STATE, questions=QUESTIONS, meta=META
        )
    assert exc_info.value.code == ErrorCode.AUTHENTICATION_ERROR


async def test_http_validation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "bad question"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(EvidenceError) as exc_info:
        await HttpDecisionProvider(api_key="k", client=client).decide_questions(
            state=STATE, questions=QUESTIONS, meta=META
        )
    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


async def test_http_rate_limit_retries_then_succeeds() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, json={"detail": "slow down"})
        return httpx.Response(200, json=_ok_payload())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = HttpDecisionProvider(api_key="k", client=client)
    result = await provider.decide_questions(state=STATE, questions=QUESTIONS, meta=META)
    assert attempts["n"] == 2  # bounded retry, then success
    assert result.by_candidate("r0")["relevant"] == 0.95


async def test_http_malformed_answer_rejected() -> None:
    payload = {
        "model": "jev-x",
        "answers": {
            "relevant__r0": {"type": "noul", "noul": "high"},
            "useful__r0": {"type": "noul", "noul": 0.5},
        },
        "usage": {},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(EvidenceError) as exc_info:
        await HttpDecisionProvider(api_key="k", client=client).decide_questions(
            state=STATE, questions=QUESTIONS, meta=META
        )
    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


async def test_http_unexpected_id_rejected() -> None:
    payload = {
        "model": "jev-x",
        "answers": {**_ok_payload()["answers"], "evil__r9": {"type": "noul", "noul": 1.0}},  # type: ignore[dict-item]
        "usage": {},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(EvidenceError) as exc_info:
        await HttpDecisionProvider(api_key="k", client=client).decide_questions(
            state=STATE, questions=QUESTIONS, meta=META
        )
    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


async def test_http_empty_questions_no_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("must not be called")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await HttpDecisionProvider(api_key="k", client=client).decide_questions(
        state=STATE, questions={}, meta={}
    )
    assert result.decisions == []


def test_sdk_provider_requires_key() -> None:
    with pytest.raises(EvidenceError) as exc_info:
        SdkDecisionProvider(api_key="")
    assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR


def test_sdk_error_mapping() -> None:
    class AuthErr(Exception):
        status = 401

    class RateErr(Exception):
        status = 429

    class TypeSafeAPITimeoutError(Exception):
        pass

    assert _map_sdk_error(AuthErr("nope")).code == ErrorCode.AUTHENTICATION_ERROR
    assert _map_sdk_error(RateErr("slow")).code == ErrorCode.JEV_ERROR
    assert _map_sdk_error(TypeSafeAPITimeoutError("t")).code == ErrorCode.TIMEOUT
    assert "sk-secret" not in _map_sdk_error(RateErr("sk-secret")).message


# --- SDK adapter against a stub SDK module (no network, no key) ---


def _install_stub_sdk(answer_value: float = 0.8, answer_type: str = "noul") -> dict[str, Any]:
    recorded: dict[str, Any] = {}

    class Noul:
        def __init__(self, instructions: object = None, criteria: object = None) -> None:
            self.instructions = instructions
            self.criteria = criteria

    class Answer:
        def __init__(self) -> None:
            self.type = answer_type
            self.noul = answer_value

    class Usage:
        input_tokens = 12
        output_tokens = 3

    class Response:
        model = "jev-stub"
        usage = Usage()

        def __init__(self, questions: dict[str, object]) -> None:
            self.answers = {qid: Answer() for qid in questions}

    class AsyncClient:
        def __init__(self, **kwargs: object) -> None:
            recorded["init"] = kwargs

        async def __aenter__(self) -> AsyncClient:
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        async def system_one(
            self, state: object, questions: dict[str, object], timeout: object = None
        ) -> Response:
            recorded["state"] = state
            recorded["questions"] = questions
            return Response(questions)

    stub = types.ModuleType("typesafe_sdk")
    stub.Noul = Noul  # type: ignore[attr-defined]
    stub.AsyncTypeSafeClient = AsyncClient  # type: ignore[attr-defined]
    return {"stub": stub, "recorded": recorded}


async def test_sdk_adapter_single_batched_call(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _install_stub_sdk(answer_value=0.77)
    monkeypatch.setitem(sys.modules, "typesafe_sdk", env["stub"])
    provider = SdkDecisionProvider(api_key="k", model="jev-latest")
    result = await provider.decide_questions(state=STATE, questions=QUESTIONS, meta=META)
    recorded = env["recorded"]
    assert set(recorded["questions"]) == set(QUESTIONS)  # type: ignore[arg-type]
    assert recorded["state"] == STATE
    assert result.by_candidate("r0") == {"relevant": 0.77, "useful": 0.77}
    assert result.model == "jev-stub"
    assert result.input_tokens == 12


async def test_sdk_adapter_rejects_wrong_answer_type(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _install_stub_sdk(answer_type="choice")
    monkeypatch.setitem(sys.modules, "typesafe_sdk", env["stub"])
    provider = SdkDecisionProvider(api_key="k")
    with pytest.raises(EvidenceError) as exc_info:
        await provider.decide_questions(state=STATE, questions=QUESTIONS, meta=META)
    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


async def test_sdk_rate_limit_retries_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _install_stub_sdk()
    stub = env["stub"]

    class RateErr(Exception):
        status = 429

    attempts = {"n": 0}
    orig_client = stub.AsyncTypeSafeClient  # type: ignore[attr-defined]

    class FlakyClient(orig_client):  # type: ignore[valid-type, misc]
        async def system_one(
            self, state: object, questions: dict[str, object], timeout: object = None
        ) -> object:
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RateErr("slow down")
            return await super().system_one(state, questions, timeout)

    stub.AsyncTypeSafeClient = FlakyClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "typesafe_sdk", stub)
    provider = SdkDecisionProvider(api_key="k")
    result = await provider.decide_questions(state=STATE, questions=QUESTIONS, meta=META)
    assert attempts["n"] == 2
    assert isinstance(result, DecisionResult)
