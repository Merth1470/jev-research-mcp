"""Deterministic block-selection policy.

``keep = relevant AND actionable`` with the same conservative uncertain-band
rule as result selection. JEV output never mutates state directly: missing
properties default to 0.5 (uncertain -> retain) so a single missing answer
cannot silently wipe out all evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..jev.interface import DecisionResult
from ..models import Block


@dataclass(frozen=True)
class BlockVerdict:
    block: Block
    keep: bool
    relevant: float
    actionable: float
    rank_score: float


def _passes(value: float, threshold: float, margin: float) -> bool:
    return value >= threshold or value >= (threshold - margin)


def select_blocks(
    blocks: list[Block],
    decisions: DecisionResult,
    *,
    relevant_threshold: float = 0.5,
    actionable_threshold: float = 0.5,
    uncertain_margin: float = 0.15,
) -> list[BlockVerdict]:
    scores: dict[str, dict[str, float]] = {}
    for decision in decisions.decisions:
        scores.setdefault(decision.candidate_id, {})[decision.property] = decision.value

    verdicts: list[BlockVerdict] = []
    for block in blocks:
        props = scores.get(block.id, {})
        relevant = props.get("relevant", 0.5)
        actionable = props.get("actionable", 0.5)
        keep = _passes(relevant, relevant_threshold, uncertain_margin) and _passes(
            actionable, actionable_threshold, uncertain_margin
        )
        # Code blocks get a small rank bonus: they carry the highest
        # information density for coding agents.
        rank = (relevant + actionable) / 2.0 + (0.05 if block.type.value == "code" else 0.0)
        verdicts.append(
            BlockVerdict(
                block=block, keep=keep, relevant=relevant, actionable=actionable, rank_score=rank
            )
        )
    kept = sorted((v for v in verdicts if v.keep), key=lambda v: v.rank_score, reverse=True)
    dropped = [v for v in verdicts if not v.keep]
    return kept + dropped


def kept_blocks(verdicts: list[BlockVerdict]) -> list[Block]:
    # Preserve document order for evidence assembly (not rank order).
    kept = [v.block for v in verdicts if v.keep]
    return sorted(kept, key=lambda b: b.position)
