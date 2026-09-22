"""DecisionProvider abstraction: one state + many questions = one JEV call.

The rest of the application never imports the TypeSafe SDK directly;
concrete providers live in ``sdk_provider`` (official SDK) and
``http_provider`` (documented HTTP fallback). Tests use FakeDecisionProvider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class Decision:
    """One validated Noul judgment in [0,1] (probability the answer is yes)."""

    question_id: str
    candidate_id: str
    property: str  # e.g. "relevant", "useful", "authoritative", "actionable"
    value: float


@dataclass
class DecisionResult:
    decisions: list[Decision] = field(default_factory=list)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    def by_candidate(self, candidate_id: str) -> dict[str, float]:
        return {d.property: d.value for d in self.decisions if d.candidate_id == candidate_id}


class DecisionProvider(Protocol):
    async def decide_questions(
        self,
        *,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]],
        meta: dict[str, str] | None = None,
    ) -> DecisionResult:
        """Evaluate many Noul questions against one shared state in one call.

        ``questions`` maps question ID -> raw question payload
        (``{"type": "noul", "instructions": ...}`` or an SDK question object).
        ``meta`` optionally maps question ID -> ``"<property>__<candidate>"``
        so answers can be mapped back without relying on ordering.
        """
        ...


class FakeDecisionProvider:
    """Offline test double. ``scores`` maps (candidate_id, property) -> value.

    ``drop`` simulates missing answers, ``extra`` unexpected IDs,
    ``malformed_values`` non-numeric answers, ``fail_with`` provider failure.
    """

    def __init__(
        self,
        scores: dict[tuple[str, str], float] | None = None,
        *,
        default: float = 0.9,
        fail_with: Exception | None = None,
        drop: set[tuple[str, str]] | None = None,
        extra: list[Decision] | None = None,
        malformed_values: dict[tuple[str, str], Any] | None = None,
    ) -> None:
        self._scores = dict(scores or {})
        self._default = default
        self._fail_with = fail_with
        self._drop = set(drop or set())
        self._extra = list(extra or [])
        self._malformed = dict(malformed_values or {})
        self.calls: list[dict[str, Any]] = []

    async def decide_questions(
        self,
        *,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]],
        meta: dict[str, str] | None = None,
    ) -> DecisionResult:
        if self._fail_with is not None:
            raise self._fail_with
        self.calls.append({"state": state, "questions": dict(questions)})
        decisions: list[Decision] = []
        qmeta = meta or {}
        for qid in questions:
            key = qmeta.get(qid, qid)
            # qid format: "<property>__<candidate_id>"
            if "__" in key:
                prop, cid = key.split("__", 1)
            else:
                prop, cid = key, ""
            if (cid, prop) in self._drop:
                continue
            if (cid, prop) in self._malformed:
                bad = self._malformed[(cid, prop)]
                decisions.append(
                    Decision(question_id=qid, candidate_id=cid, property=prop, value=bad)
                )
                continue
            value = self._scores.get((cid, prop), self._default)
            decisions.append(
                Decision(question_id=qid, candidate_id=cid, property=prop, value=float(value))
            )
        decisions.extend(self._extra)
        return DecisionResult(decisions=decisions, model="fake", input_tokens=0, output_tokens=0)
