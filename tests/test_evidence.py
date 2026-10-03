"""Dedup, token budget, assembly (context, preference, budget, provenance)."""

from __future__ import annotations

from jev_research_mcp.evidence.assemble import (
    assemble_evidence,
    format_block,
    source_authority_score,
)
from jev_research_mcp.evidence.dedup import content_hash, deduplicate, normalize_for_hash
from jev_research_mcp.evidence.tokens import estimate_tokens, fits_in_budget
from jev_research_mcp.jev.retry import backoff_delay_seconds
from jev_research_mcp.models import Block, BlockType, ParsedDocument


def test_normalize_for_hash_ignores_whitespace_case() -> None:
    assert normalize_for_hash("  Hello   World\n") == normalize_for_hash("hello world")


def test_deduplicate_removes_exact_duplicates() -> None:
    result = deduplicate(["same text", "same  text", "different", "", "same text"])
    assert result.items == [0, 2]
    assert result.dropped[3] == "empty"
    assert result.duplicate_of[1] == 0
    assert result.duplicate_of[4] == 0


def test_content_hash_stable() -> None:
    assert content_hash("abc") == content_hash("  ABC\n")


def test_estimate_tokens_is_chars_over_four() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_fits_in_budget_keeps_whole_first_block() -> None:
    texts = ["x" * 400, "y" * 400]
    assert fits_in_budget(texts, 1000) == [0, 1]
    assert fits_in_budget(texts, 50) == [0]  # over-budget single block kept whole
    assert fits_in_budget(texts, 150) == [0]
    assert fits_in_budget(texts, 200) == [0, 1]


def _doc(url: str, blocks: list[Block]) -> ParsedDocument:
    host = url.split("//", 1)[1].split("/", 1)[0].lower()
    domain = host.removeprefix("www.")
    return ParsedDocument(url=url, title=f"Title {url}", source_domain=domain, blocks=blocks)


def test_format_block_restores_heading_context() -> None:
    block = Block(
        id="b1",
        type=BlockType.PARAGRAPH,
        text="Set this option to true.",
        parent_heading="Enable streaming",
        position=1,
    )
    assert format_block(block) == "### Enable streaming\n\nSet this option to true."


def test_format_block_code_fenced_with_language() -> None:
    block = Block(
        id="b2",
        type=BlockType.CODE,
        text="x = 1",
        language="python",
        parent_heading="Setup",
        position=2,
    )
    assert format_block(block) == "### Setup\n\n```python\nx = 1\n```"


def test_format_block_heading_not_duplicated() -> None:
    block = Block(id="b0", type=BlockType.HEADING, text="Enable streaming", position=0)
    assert format_block(block) == "Enable streaming"


def test_assemble_prefers_official_source_on_duplicates() -> None:
    shared = Block(id="b1", type=BlockType.PARAGRAPH, text="Shared fact.", position=1)
    official = _doc("https://docs.example.com/a", [shared])
    blog = _doc(
        "https://blog.example.com/a",
        [Block(id="b1", type=BlockType.PARAGRAPH, text="Shared  fact.", position=1)],
    )
    sources = assemble_evidence(
        docs=[blog, official],
        kept_by_url={blog.url: blog.blocks, official.url: official.blocks},
        max_tokens=8000,
    )
    assert len(sources) == 1
    assert sources[0].domain == "docs.example.com"
    assert sources[0].evidence[0].also_seen_at == ["https://blog.example.com/a"]


def test_assemble_budget_never_slices_code() -> None:
    big_code = Block(
        id="b0", type=BlockType.CODE, text="x = 1\n" * 500, language="python", position=0
    )
    doc = _doc("https://example.com/a", [big_code])
    sources = assemble_evidence(docs=[doc], kept_by_url={doc.url: doc.blocks}, max_tokens=10)
    assert len(sources) == 1
    assert "x = 1" in sources[0].evidence[0].text  # kept whole despite budget


def test_assemble_provenance_urls_preserved() -> None:
    block = Block(id="b0", type=BlockType.PARAGRAPH, text="Fact.", position=0)
    doc = _doc("https://example.com/original/path?q=1", [block])
    sources = assemble_evidence(docs=[doc], kept_by_url={doc.url: doc.blocks}, max_tokens=8000)
    assert sources[0].url == "https://example.com/original/path?q=1"
    assert sources[0].evidence[0].url == "https://example.com/original/path?q=1"


def test_source_authority_score_orders_official_first() -> None:
    assert source_authority_score("docs.python.org", 0.5) > source_authority_score(
        "blog.example.com", 0.5
    )
    assert source_authority_score("github.com", None) > source_authority_score(
        "blog.example.com", None
    )


def test_backoff_is_bounded_and_growing() -> None:
    assert backoff_delay_seconds(1) == 0.5
    assert backoff_delay_seconds(2) == 1.0
    assert backoff_delay_seconds(100) == 5.0
