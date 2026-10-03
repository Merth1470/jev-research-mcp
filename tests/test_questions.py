"""JEV question builders: one state + many questions, explicit contracts."""

from __future__ import annotations

from jev_research_mcp.jev.questions import (
    BLOCK_PROPERTIES,
    RESULT_PROPERTIES,
    build_block_questions,
    build_block_state,
    build_result_questions,
    build_result_state,
)
from jev_research_mcp.models import Block, BlockType, SearchResult


def _results(n: int = 3) -> list[SearchResult]:
    return [
        SearchResult(
            id=f"r{i}",
            title=f"Title {i}",
            url=f"https://example.com/{i}",
            snippet=f"snippet {i}",
            domain="example.com",
        )
        for i in range(n)
    ]


def test_result_state_holds_task_and_candidates() -> None:
    state = build_result_state("how to retry?", _results(2))
    assert state["task"] == "how to retry?"
    assert [c["id"] for c in state["candidates"]] == ["r0", "r1"]
    assert state["candidates"][0]["domain"] == "example.com"


def test_result_questions_one_per_property_per_candidate() -> None:
    questions, meta = build_result_questions(_results(2))
    assert len(questions) == 2 * len(RESULT_PROPERTIES)
    # IDs are explicit, never positional.
    assert "relevant__r0" in questions
    assert meta["relevant__r0"] == "relevant__r0"
    for qid, payload in questions.items():
        assert meta[qid] == qid
        assert payload["type"] == "noul"
        assert isinstance(payload["instructions"], str)
        assert len(payload["instructions"]) > 20


def test_result_contracts_are_explicit_not_vague() -> None:
    from jev_research_mcp.jev.questions import RESULT_QUESTIONS

    for prop, text in RESULT_QUESTIONS.items():
        assert len(text) > 40, prop
        assert text.strip().endswith("?") or "Answer yes only" in text


def test_block_questions_cover_relevant_actionable() -> None:
    blocks = [Block(id="b0", type=BlockType.PARAGRAPH, text="Use a semaphore.", parent_heading="H")]
    questions, meta = build_block_questions(blocks)
    assert set(questions) == {"relevant__b0", "actionable__b0"}
    assert meta["relevant__b0"] == "relevant__b0"
    assert set(BLOCK_PROPERTIES) == {"relevant", "actionable"}


def test_block_state_truncates_long_blocks() -> None:
    blocks = [Block(id="b0", type=BlockType.PARAGRAPH, text="x" * 5000)]
    state = build_block_state("q", blocks, max_block_chars=100)
    assert len(state["blocks"][0]["text"]) <= 101
