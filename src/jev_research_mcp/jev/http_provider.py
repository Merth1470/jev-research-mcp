"""Minimal HTTP fallback for the documented TypeSafe API.

Used only when the official SDK cannot perform the required operation
(or is unavailable). Speaks exactly the documented contract:
POST {base_url}/v1/systemone with Bearer auth, ``{state, model, questions}``
and Noul questions; validates the ``{answers, usage}`` response shape.
Kept tiny and isolated so the SDK remains the primary path.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..errors import ErrorCode, EvidenceError
from .interface import DecisionResult
from .retry import (
    MAX_TRANSIENT_RETRIES,
    RETRYABLE_STATUS_CODES,
    RetryableJevError,
    sleep_backoff,
)
from .validation import validate_decisions


class HttpDecisionProvider:
    """DecisionProvider over raw HTTPS (documented API, no SDK)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "jev-latest",
        base_url: str = "https://api.typesafe.ai",
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise EvidenceError(
                ErrorCode.CONFIGURATION_ERROR,
                "Missing TYPESAFE_API_KEY. Set it in your environment (see .env.example).",
            )
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = client

    async def decide_questions(
        self,
        *,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]],
        meta: dict[str, str] | None = None,
    ) -> DecisionResult:
        if not questions:
            return DecisionResult(decisions=[])
        meta = meta or {}
        expected = set(questions.keys())
        payload = {"state": state, "model": self._model, "questions": questions}
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        url = f"{self._base_url}/v1/systemone"

        last_error: RetryableJevError | None = None
        for attempt in range(MAX_TRANSIENT_RETRIES + 1):
            try:
                data = await self._post(url, headers, payload)
                return self._convert(data, expected, meta)
            except RetryableJevError as exc:
                last_error = exc
                if attempt < MAX_TRANSIENT_RETRIES:
                    await sleep_backoff(attempt + 1)
                    continue
                raise
        assert last_error is not None  # pragma: no cover - loop always returns/raises
        raise last_error

    async def _post(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            if self._client is not None:
                response = await self._client.post(url, headers=headers, json=payload)
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise RetryableJevError(
                f"JEV request timed out: {exc}", code=ErrorCode.TIMEOUT
            ) from exc
        except httpx.HTTPError as exc:
            raise RetryableJevError(f"JEV connection failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise EvidenceError(
                ErrorCode.AUTHENTICATION_ERROR,
                "JEV rejected the API key (401/403). Check TYPESAFE_API_KEY.",
            )
        if response.status_code in (400, 422):
            detail = response.text[:300]
            raise EvidenceError(ErrorCode.VALIDATION_ERROR, f"JEV rejected the request: {detail}")
        if response.status_code in RETRYABLE_STATUS_CODES:
            raise RetryableJevError(f"JEV overloaded/rate-limited ({response.status_code}).")
        if response.status_code >= 400:
            raise EvidenceError(
                ErrorCode.JEV_ERROR, f"JEV request failed with HTTP {response.status_code}."
            )
        try:
            data = response.json()
        except Exception as exc:
            raise EvidenceError(ErrorCode.VALIDATION_ERROR, "JEV returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise EvidenceError(ErrorCode.VALIDATION_ERROR, "JEV response was not a JSON object.")
        return data

    def _convert(
        self, data: dict[str, Any], expected: set[str], meta: dict[str, str]
    ) -> DecisionResult:
        answers = data.get("answers")
        if not isinstance(answers, dict):
            raise EvidenceError(
                ErrorCode.VALIDATION_ERROR, "JEV response missing 'answers' object."
            )
        raw: dict[str, Any] = {}
        for qid, answer in answers.items():
            if not isinstance(answer, dict):
                raise EvidenceError(
                    ErrorCode.VALIDATION_ERROR, f"JEV answer {qid!r} is not an object."
                )
            if answer.get("type") != "noul":
                got = answer.get("type")
                raise EvidenceError(
                    ErrorCode.VALIDATION_ERROR,
                    f"JEV answer {qid!r} has type {got!r}; expected 'noul'.",
                )
            raw[qid] = answer.get("noul")
        validated = validate_decisions(expected_question_ids=expected, meta=meta, raw_answers=raw)
        validated.model = str(data.get("model", "") or "")
        usage = data.get("usage", {})
        if isinstance(usage, dict):
            try:
                validated.input_tokens = int(usage.get("input_tokens", 0) or 0)
                validated.output_tokens = int(usage.get("output_tokens", 0) or 0)
            except (TypeError, ValueError):
                pass
        return validated
