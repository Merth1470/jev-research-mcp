"""DecisionProvider abstraction: one state + many questions = one JEV call.

The rest of the application never imports the TypeSafe SDK directly;
concrete providers live in ``sdk_provider`` (official SDK) and
``http_provider`` (documented HTTP fallback). Test doubles live in
``tests/helpers.py`` and are never used by production code.
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
    """Live JEV decision provider (TypeSafe SDK or documented HTTP fallback)."""

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
