"""Validation of JEV decisions: treat every external answer as untrusted.

Checks: expected question IDs, no duplicates, no unexpected IDs, numeric
Noul values in [0,1], missing answers reported. Never silently accept
malformed decisions; never include secrets in errors.
"""

from __future__ import annotations

from typing import Any

from ..errors import ErrorCode, EvidenceError
from .interface import Decision, DecisionResult


def validate_decisions(
    *,
    expected_question_ids: set[str],
    meta: dict[str, str],
    raw_answers: dict[str, Any] | list[tuple[str, Any]],
) -> DecisionResult:
    """Validate raw ``answers`` into typed Decisions.

    ``raw_answers`` maps question ID -> numeric Noul value (or answer object
    with a numeric ``noul`` field, accepted for HTTP/SDK shape tolerance).
    A list of pairs is also accepted so duplicate IDs can be detected.
    """
    seen: set[str] = set()
    decisions: list[Decision] = []
    items = raw_answers.items() if isinstance(raw_answers, dict) else raw_answers
    for qid, raw in items:
        if qid not in expected_question_ids:
            raise EvidenceError(
                ErrorCode.VALIDATION_ERROR, f"JEV returned unexpected question id {qid!r}."
            )
        if qid in seen:
            raise EvidenceError(
                ErrorCode.VALIDATION_ERROR, f"JEV returned duplicate question id {qid!r}."
            )
        seen.add(qid)
        value = _coerce_noul(qid, raw)
        key = meta.get(qid, qid)
        if "__" in key:
            prop, cid = key.split("__", 1)
        else:
            prop, cid = key, ""
        decisions.append(Decision(question_id=qid, candidate_id=cid, property=prop, value=value))
    missing = expected_question_ids - seen
    if missing:
        sample = sorted(missing)[:5]
        raise EvidenceError(
            ErrorCode.VALIDATION_ERROR,
            f"JEV response missing {len(missing)} answer(s), e.g. {sample!r}.",
        )
    return DecisionResult(decisions=decisions)


def validate_decision_result(
    result: DecisionResult, *, expected_question_ids: set[str], meta: dict[str, str]
) -> DecisionResult:
    """Validate an already-typed DecisionResult (SDK path)."""
    raw: dict[str, Any] = {d.question_id: d.value for d in result.decisions}
    validated = validate_decisions(
        expected_question_ids=expected_question_ids, meta=meta, raw_answers=raw
    )
    validated.model = result.model
    validated.input_tokens = result.input_tokens
    validated.output_tokens = result.output_tokens
    return validated


def _coerce_noul(qid: str, raw: Any) -> float:
    if isinstance(raw, dict):
        raw = raw.get("noul", raw.get("value"))
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise EvidenceError(
            ErrorCode.VALIDATION_ERROR,
            f"JEV answer {qid!r} has non-numeric value; expected Noul probability.",
        )
    value = float(raw)
    if not (0.0 <= value <= 1.0):
        raise EvidenceError(
            ErrorCode.VALIDATION_ERROR,
            f"JEV answer {qid!r} out of range [0,1]: {value!r}.",
        )
    return value
