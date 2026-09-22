"""Deterministic result-selection policy (JEV decides, code disposes).

``keep = relevant AND useful`` evaluated against configurable thresholds.
Conservative by design: false negatives (dropping the only relevant source)
hurt more than false positives, so values inside the *uncertain band*
``[threshold - margin, threshold)`` are retained rather than dropped.
Authority never drops a candidate; it only reorders survivors (official
docs and primary sources first when scores tie).

Noul values near 0.5 indicate model uncertainty — they are a decision
signal, not an accuracy guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..jev.interface import DecisionResult
from ..models import SearchResult

_OFFICIAL_HINTS = (
    "docs.",
    "documentation",
    "developer.",
    "developers.",
    "github.com",
    "gitlab.com",
)


def _authority_bonus(domain: str, authoritative_score: float | None) -> float:
    bonus = 0.0
    lowered = (domain or "").lower()
    if any(hint in lowered for hint in _OFFICIAL_HINTS):
        bonus += 0.05
    if authoritative_score is not None:
        bonus += 0.10 * authoritative_score
    return bonus


@dataclass(frozen=True)
class ResultVerdict:
    result: SearchResult
    keep: bool
    relevant: float
    useful: float
    authoritative: float | None
    rank_score: float


def _passes(value: float, threshold: float, margin: float) -> bool:
    # Conservative: keep when confidently above threshold OR inside the
    # uncertain band just below it; drop only when clearly below.
    return value >= threshold or value >= (threshold - margin)


def select_results(
    results: list[SearchResult],
    decisions: DecisionResult,
    *,
    relevant_threshold: float = 0.5,
    useful_threshold: float = 0.5,
    uncertain_margin: float = 0.15,
    require_useful: bool = True,
) -> list[ResultVerdict]:
    """Apply the deterministic keep/drop policy to JEV-scored results."""
    scores: dict[str, dict[str, float]] = {}
    for decision in decisions.decisions:
        scores.setdefault(decision.candidate_id, {})[decision.property] = decision.value

    verdicts: list[ResultVerdict] = []
    for result in results:
        props = scores.get(result.id, {})
        relevant = props.get("relevant", 0.5)  # missing -> uncertain -> retain
        useful = props.get("useful", 0.5)
        authoritative = props.get("authoritative")
        keep_relevant = _passes(relevant, relevant_threshold, uncertain_margin)
        keep_useful = (
            _passes(useful, useful_threshold, uncertain_margin) if require_useful else True
        )
        keep = keep_relevant and keep_useful
        rank = (relevant + useful) / 2.0 + _authority_bonus(result.domain, authoritative)
        verdicts.append(
            ResultVerdict(
                result=result,
                keep=keep,
                relevant=relevant,
                useful=useful,
                authoritative=authoritative,
                rank_score=rank,
            )
        )
    # Survivors ordered by rank; drops keep original order at the end.
    # (Score lookup above is keyed by candidate ID, never by position.)
    kept = sorted((v for v in verdicts if v.keep), key=lambda v: v.rank_score, reverse=True)
    dropped = [v for v in verdicts if not v.keep]
    return kept + dropped


def kept_results(verdicts: list[ResultVerdict]) -> list[SearchResult]:
    return [v.result for v in verdicts if v.keep]
