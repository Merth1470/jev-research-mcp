"""JEV provider built on the official ``typesafe-sdk`` (source of truth).

Uses Noul questions (yes/no as calibrated probability in [0,1]) batched as
one state + many questions = one ``system_one`` call. Prefers the async
client; falls back to running the sync client in a worker thread.

Retry discipline: the SDK keeps its default RetryPolicy (it already handles
transient transport retries). This module adds an outer retry ONLY for
rate-limit/overload errors (bounded, exponential backoff) so there is no
nested retry storm for other error classes.
"""

from __future__ import annotations

from typing import Any

from ..errors import ErrorCode, EvidenceError
from .interface import DecisionResult
from .retry import MAX_TRANSIENT_RETRIES, sleep_backoff
from .validation import validate_decisions

_MISSING_SDK = (
    "typesafe-sdk is not installed. Install it with: pip install typesafe-sdk "
    "(or use the HTTP provider fallback)."
)


def _import_sdk() -> Any:
    try:
        import typesafe_sdk  # type: ignore[import-not-found]
    except ImportError as exc:
        raise EvidenceError(ErrorCode.CONFIGURATION_ERROR, _MISSING_SDK) from exc
    return typesafe_sdk


def _map_sdk_error(exc: BaseException) -> EvidenceError:
    # Never echo SDK exception text: it may contain request details.
    # Report only the error class and HTTP status.
    name = type(exc).__name__
    status = getattr(exc, "status", None)
    if "Authentication" in name or "PermissionDenied" in name or status in {401, 403}:
        return EvidenceError(
            ErrorCode.AUTHENTICATION_ERROR,
            "JEV rejected the API key (401/403). Check TYPESAFE_API_KEY.",
        )
    if "RateLimit" in name or status == 429:
        return EvidenceError(ErrorCode.JEV_ERROR, "JEV rate limit exceeded; retry with backoff.")
    if "Unprocessable" in name or "BadRequest" in name or status in {400, 422}:
        return EvidenceError(ErrorCode.VALIDATION_ERROR, f"JEV rejected the request ({name}).")
    if "Timeout" in name:
        return EvidenceError(ErrorCode.TIMEOUT, "JEV request timed out.")
    if "Connection" in name:
        return EvidenceError(ErrorCode.JEV_ERROR, "JEV connection failed.")
    suffix = f" (HTTP {status})" if isinstance(status, int) else ""
    return EvidenceError(ErrorCode.JEV_ERROR, f"JEV request failed ({name}{suffix}).")


def _is_transient_sdk_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if "RateLimit" in name or "InternalServer" in name:
        return True
    status = getattr(exc, "status", None)
    return status in {429, 529, 502, 503, 504}


class SdkDecisionProvider:
    """DecisionProvider implemented with the official TypeSafe SDK."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "jev-latest",
        base_url: str = "https://api.typesafe.ai",
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise EvidenceError(
                ErrorCode.CONFIGURATION_ERROR,
                "Missing TYPESAFE_API_KEY. Set it in your environment (see .env.example).",
            )
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout_seconds

    def _build_questions(self, sdk: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        built: dict[str, Any] = {}
        noul_cls = sdk.Noul
        for qid, payload in questions.items():
            instructions = payload.get("instructions", "")
            criteria = payload.get("criteria")
            if criteria is not None:
                built[qid] = noul_cls(instructions=instructions, criteria=criteria)
            else:
                built[qid] = noul_cls(instructions=instructions)
        return built

    async def decide_questions(
        self,
        *,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]],
        meta: dict[str, str] | None = None,
    ) -> DecisionResult:
        if not questions:
            return DecisionResult(decisions=[])
        sdk = _import_sdk()
        sdk_questions = self._build_questions(sdk, questions)
        last_error: BaseException | None = None
        for attempt in range(MAX_TRANSIENT_RETRIES + 1):
            try:
                return await self._call_once(sdk, state, sdk_questions, meta or {})
            except EvidenceError:
                raise
            except Exception as exc:  # SDK raises typed TypeSafe* errors
                if _is_transient_sdk_error(exc) and attempt < MAX_TRANSIENT_RETRIES:
                    last_error = exc
                    await sleep_backoff(attempt + 1)
                    continue
                raise _map_sdk_error(exc) from exc
        assert last_error is not None
        raise _map_sdk_error(last_error)

    async def _call_once(
        self, sdk: Any, state: dict[str, Any], questions: dict[str, Any], meta: dict[str, str]
    ) -> DecisionResult:
        expected = set(questions.keys())
        # Prefer the async client so many JEV calls don't block the loop.
        if hasattr(sdk, "AsyncTypeSafeClient"):
            async with sdk.AsyncTypeSafeClient(
                api_key=self._api_key, model=self._model, base_url=self._base_url
            ) as client:
                response = await client.system_one(state, questions, timeout=self._timeout)
                return self._convert_response(response, expected, meta)
        # Fallback: sync client in a worker thread.
        import asyncio as _asyncio

        def _call_sync() -> Any:
            with sdk.TypeSafeClient(
                api_key=self._api_key, model=self._model, base_url=self._base_url
            ) as client:
                return client.system_one(state, questions, timeout=self._timeout)

        response = await _asyncio.to_thread(_call_sync)
        return self._convert_response(response, expected, meta)

    def _convert_response(
        self, response: Any, expected: set[str], meta: dict[str, str]
    ) -> DecisionResult:
        # Extract raw Noul values, then run full validation (unexpected IDs,
        # duplicates, missing answers, range checks) in one place.
        try:
            answers = response.answers or {}
            model_name = str(getattr(response, "model", "") or "")
            usage = getattr(response, "usage", None)
            input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        except Exception as exc:
            raise EvidenceError(
                ErrorCode.VALIDATION_ERROR, "JEV SDK response had unexpected structure."
            ) from exc
        raw: dict[str, Any] = {}
        for qid, answer in answers.items():
            answer_type = getattr(answer, "type", None)
            if answer_type != "noul":
                raise EvidenceError(
                    ErrorCode.VALIDATION_ERROR,
                    f"JEV answer {qid!r} has unexpected type {answer_type!r}; expected 'noul'.",
                )
            try:
                raw[qid] = float(answer.noul)
            except (TypeError, ValueError) as exc:
                raise EvidenceError(
                    ErrorCode.VALIDATION_ERROR,
                    f"JEV answer {qid!r} has non-numeric value; expected Noul probability.",
                ) from exc
        validated = validate_decisions(expected_question_ids=expected, meta=meta, raw_answers=raw)
        validated.model = model_name
        validated.input_tokens = input_tokens
        validated.output_tokens = output_tokens
        return validated
