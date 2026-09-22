"""Parser: noise removed, docs/code/hierarchy preserved, malformed safe."""

from __future__ import annotations

from jev_evidence_mcp.models import BlockType
from jev_evidence_mcp.parse.parser import parse_html_to_document


def test_noise_removed_content_kept(doc_html: str) -> None:
    doc = parse_html_to_document(doc_html, url="https://example.com/guide")
    assert doc.title == "Async Fetch Guide"
    assert doc.source_domain == "example.com"
    texts = " ".join(b.text for b in doc.blocks)
    assert "Enable streaming" in texts
    assert "Set this option to true" in texts
    # Noise must be gone.
    assert "Pricing" not in texts
    assert "track" not in texts
    assert "cookies" not in texts.lower()
    assert "Copyright" not in texts
    assert "Share on X" not in texts


def test_code_formatting_preserved(doc_html: str) -> None:
    doc = parse_html_to_document(doc_html, url="https://example.com/guide")
    code_blocks = [b for b in doc.blocks if b.type == BlockType.CODE]
    assert code_blocks, "expected at least one code block"
    code = code_blocks[0].text
    assert "async def fetch(url):" in code
    assert "\n" in code  # line breaks preserved
    assert code_blocks[0].language == "python"


def test_hierarchy_parent_heading(doc_html: str) -> None:
    doc = parse_html_to_document(doc_html, url="https://example.com/guide")
    target = next(b for b in doc.blocks if "Set this option to true" in b.text)
    assert target.parent_heading == "Enable streaming"


def test_lists_tables_quotes(doc_html: str) -> None:
    doc = parse_html_to_document(doc_html, url="https://example.com/guide")
    by_type = {b.type for b in doc.blocks}
    assert BlockType.LIST in by_type
    assert BlockType.TABLE in by_type
    assert BlockType.QUOTE in by_type
    table = next(b for b in doc.blocks if b.type == BlockType.TABLE)
    assert "timeout" in table.text and "15" in table.text


def test_malformed_html_never_raises() -> None:
    doc = parse_html_to_document("<p>unclosed <b>bold <div>div soup", url="https://x.com/")
    assert isinstance(doc.blocks, list)


def test_empty_html_yields_no_blocks() -> None:
    doc = parse_html_to_document("", url="https://x.com/")
    assert doc.blocks == []


def test_block_ids_sequential_and_capped(doc_html: str) -> None:
    doc = parse_html_to_document(doc_html, url="https://x.com/", max_blocks=3)
    assert len(doc.blocks) == 3
    assert [b.position for b in doc.blocks] == [0, 1, 2]


def test_oversized_block_split_keeps_context() -> None:
    html = "<html><body><h1>Big section</h1><p>" + ("word " * 5000) + "</p></body></html>"
    doc = parse_html_to_document(html, url="https://x.com/", max_block_chars=1000)
    assert len(doc.blocks) >= 2
    assert all(
        b.parent_heading == "Big section" for b in doc.blocks if b.type == BlockType.PARAGRAPH
    )
