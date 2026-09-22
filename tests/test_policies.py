"""Deterministic policies: fixtures from the spec (section 62)."""

from __future__ import annotations

from jev_evidence_mcp.jev.interface import Decision, DecisionResult
from jev_evidence_mcp.models import Block, BlockType, SearchResult
from jev_evidence_mcp.policy.blocks import kept_blocks, select_blocks
from jev_evidence_mcp.policy.results import kept_results, select_results


def _result(id_: str) -> SearchResult:
    return SearchResult(
        id=id_,
        title=f"T {id_}",
        url=f"https://example.com/{id_}",
        snippet="s",
        domain="example.com",
    )


def _decisions(scores: dict[tuple[str, str], float]) -> DecisionResult:
    return DecisionResult(
        decisions=[
            Decision(question_id=f"{prop}__{cid}", candidate_id=cid, property=prop, value=value)
            for (cid, prop), value in scores.items()
        ]
    )


# --- Result policy (spec section 62) ---


def test_relevant_useful_authoritative_keep() -> None:
    verdicts = select_results(
        [_result("r0")],
        _decisions(
            {("r0", "relevant"): 0.95, ("r0", "useful"): 0.9, ("r0", "authoritative"): 0.95}
        ),
    )
    assert [v.keep for v in verdicts] == [True]


def test_irrelevant_drops() -> None:
    verdicts = select_results(
        [_result("r0")],
        _decisions({("r0", "relevant"): 0.05, ("r0", "useful"): 0.9, ("r0", "authoritative"): 0.9}),
    )
    assert [v.keep for v in verdicts] == [False]


def test_relevant_but_useless_drops() -> None:
    verdicts = select_results(
        [_result("r0")],
        _decisions({("r0", "relevant"): 0.9, ("r0", "useful"): 0.05, ("r0", "authoritative"): 0.9}),
    )
    assert [v.keep for v in verdicts] == [False]


def test_uncertain_retained_conservative() -> None:
    verdicts = select_results(
        [_result("r0")],
        _decisions({("r0", "relevant"): 0.5, ("r0", "useful"): 0.5, ("r0", "authoritative"): 0.5}),
    )
    assert [v.keep for v in verdicts] == [True]


def test_borderline_below_threshold_within_margin_retained() -> None:
    verdicts = select_results(
        [_result("r0")],
        _decisions({("r0", "relevant"): 0.42, ("r0", "useful"): 0.9, ("r0", "authoritative"): 0.5}),
        relevant_threshold=0.5,
        useful_threshold=0.5,
        uncertain_margin=0.15,
    )
    assert [v.keep for v in verdicts] == [True]


def test_clearly_below_margin_drops() -> None:
    verdicts = select_results(
        [_result("r0")],
        _decisions({("r0", "relevant"): 0.2, ("r0", "useful"): 0.9, ("r0", "authoritative"): 0.5}),
        relevant_threshold=0.5,
        useful_threshold=0.5,
        uncertain_margin=0.15,
    )
    assert [v.keep for v in verdicts] == [False]


def test_authority_reorders_but_never_drops() -> None:
    results = [_result("r0"), _result("r1")]
    verdicts = select_results(
        results,
        _decisions(
            {
                ("r0", "relevant"): 0.9,
                ("r0", "useful"): 0.9,
                ("r0", "authoritative"): 0.1,
                ("r1", "relevant"): 0.9,
                ("r1", "useful"): 0.9,
                ("r1", "authoritative"): 0.95,
            }
        ),
    )
    kept = kept_results(verdicts)
    assert len(kept) == 2
    assert kept[0].id == "r1"  # more authoritative first


def test_missing_scores_default_to_uncertain_retain() -> None:
    verdicts = select_results([_result("r0")], DecisionResult(decisions=[]))
    assert [v.keep for v in verdicts] == [True]


# --- Block policy ---


def _block(id_: str) -> Block:
    return Block(id=id_, type=BlockType.PARAGRAPH, text=f"text {id_}", position=int(id_[1:]))


def test_block_relevant_and_actionable_keep() -> None:
    verdicts = select_blocks(
        [_block("b0")], _decisions({("b0", "relevant"): 0.9, ("b0", "actionable"): 0.85})
    )
    assert [v.keep for v in verdicts] == [True]


def test_block_irrelevant_drops() -> None:
    verdicts = select_blocks(
        [_block("b0")], _decisions({("b0", "relevant"): 0.1, ("b0", "actionable"): 0.9})
    )
    assert [v.keep for v in verdicts] == [False]


def test_block_not_actionable_drops() -> None:
    verdicts = select_blocks(
        [_block("b0")], _decisions({("b0", "relevant"): 0.9, ("b0", "actionable"): 0.1})
    )
    assert [v.keep for v in verdicts] == [False]


def test_block_uncertain_retained() -> None:
    verdicts = select_blocks(
        [_block("b0")], _decisions({("b0", "relevant"): 0.5, ("b0", "actionable"): 0.5})
    )
    assert [v.keep for v in verdicts] == [True]


def test_kept_blocks_return_document_order() -> None:
    blocks = [_block("b2"), _block("b0"), _block("b1")]
    verdicts = select_blocks(
        blocks,
        _decisions(
            {
                ("b0", "relevant"): 0.9,
                ("b0", "actionable"): 0.9,
                ("b1", "relevant"): 0.9,
                ("b1", "actionable"): 0.9,
                ("b2", "relevant"): 0.9,
                ("b2", "actionable"): 0.9,
            }
        ),
    )
    assert [b.id for b in kept_blocks(verdicts)] == ["b0", "b1", "b2"]
