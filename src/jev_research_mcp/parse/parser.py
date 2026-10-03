"""Deterministic HTML → structured blocks.

Cleaning here is structural only (script/style/nav/banners/footers), never
semantic. Code formatting (indentation, line breaks, language) is preserved
verbatim. Output prefers semantic HTML structure over fixed-size chunks;
only very large blocks are split, keeping original IDs and parent context.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from ..models import Block, BlockType, ParsedDocument

_NOISE_TAGS = {"script", "style", "noscript", "template", "svg", "canvas"}

# Reliably-identifiable noise: matched structurally, not semantically.
_NOISE_SELECTORS = [
    "nav",
    "footer",
    "header nav",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    ".cookie-banner",
    ".cookie-consent",
    ".cookie-notice",
    "#cookie-banner",
    ".social-share",
    ".share-buttons",
    ".advertisement",
    ".ad-container",
    ".tracking-pixel",
]

_WS_RE = re.compile(r"[ \t\xa0]+")
_BLANK_RE = re.compile(r"\n\s*\n\s*\n+")


def _domain_of(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
        return host.removeprefix("www.")
    except Exception:
        return ""


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_WS_RE.sub(" ", line).strip() for line in text.split("\n")]
    cleaned = "\n".join(line for line in lines)
    # Collapse runs of blank lines to at most one.
    cleaned = _BLANK_RE.sub("\n\n", cleaned)
    return cleaned.strip()


def _class_list(tag: Tag) -> list[str]:
    value = tag.get("class")
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _code_language(tag: Tag) -> str | None:
    for name in _class_list(tag):
        if name.startswith("language-"):
            return name[len("language-") :]
        if name.startswith("lang-"):
            return name[len("lang-") :]
    data_lang = tag.get("data-language") or tag.get("data-lang")
    if data_lang:
        return str(data_lang)
    parent = tag.parent
    if isinstance(parent, Tag):
        for name in _class_list(parent):
            if name.startswith("language-"):
                return name[len("language-") :]
    code_child = tag.find("code") if tag.name == "pre" else None
    if isinstance(code_child, Tag):
        nested = _code_language(code_child)
        if nested:
            return nested
    return None


def _strip_noise(soup: BeautifulSoup) -> None:
    for tag_name in _NOISE_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()
    for selector in _NOISE_SELECTORS:
        try:
            for element in soup.select(selector):
                element.decompose()
        except (AttributeError, ValueError):
            # Unknown pseudo-classes on some bs4 versions; selector list is
            # best-effort structural noise removal, so skip failures.
            continue
    # Comments
    from bs4 import Comment

    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()


def _block_from_heading(tag: Tag, position: int, parent_heading: str | None) -> Block | None:
    text = _clean_text(tag.get_text(separator=" ", strip=True))
    if not text:
        return None
    try:
        level = int(tag.name[1]) if tag.name and tag.name.startswith("h") else None
    except (ValueError, IndexError):
        level = None
    return Block(
        id=f"b{position}",
        type=BlockType.HEADING,
        text=text[:4000],
        heading_level=level if level in (1, 2, 3, 4, 5, 6) else None,
        parent_heading=parent_heading,
        position=position,
    )


def parse_html_to_document(
    html: str,
    *,
    url: str,
    max_blocks: int = 300,
    max_block_chars: int = 8000,
) -> ParsedDocument:
    """Parse HTML into a structured document. Never raises on malformed HTML."""
    soup = BeautifulSoup(html or "", "html.parser")
    _strip_noise(soup)
    title = ""
    if soup.title and soup.title.string:
        title = _clean_text(soup.title.string)[:500]
    body = soup.body or soup

    blocks: list[Block] = []
    current_heading: str | None = None
    position = 0

    def push(block: Block | None) -> None:
        nonlocal position
        if block is None:
            return
        if len(block.text.strip()) == 0:
            return
        block.position = position
        block.id = f"b{position}"
        blocks.append(block)
        position += 1

    # Walk structure in document order for determinism.
    for tag in body.find_all(
        [
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
            "pre",
            "code",
            "ul",
            "ol",
            "blockquote",
            "table",
            "li",
            "div",
            "section",
            "article",
        ],
        recursive=True,
    ):
        # Skip nested duplicates: only handle a tag if none of its handled
        # ancestors of the same kind already consumed it. Simplest robust rule:
        # skip `li` when parent list already emitted, skip bare `code` inside `pre`.
        if not isinstance(tag, Tag):
            continue
        name = (tag.name or "").lower()
        if name == "code" and isinstance(tag.parent, Tag) and tag.parent.name == "pre":
            continue
        if name == "li" and isinstance(tag.parent, Tag) and tag.parent.get("data-jev-consumed"):
            continue
        if tag.get("data-jev-consumed"):
            continue

        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            block = _block_from_heading(tag, position, current_heading)
            if block is not None:
                current_heading = block.text[:300]
                push(block)
        elif name == "pre":
            code_text = tag.get_text(separator="\n", strip=False)
            # Preserve indentation/line breaks verbatim; only strip trailing blank lines.
            code_text = code_text.strip("\n")
            if code_text.strip():
                push(
                    Block(
                        id=f"b{position}",
                        type=BlockType.CODE,
                        text=code_text[:max_block_chars],
                        parent_heading=current_heading,
                        language=_code_language(tag),
                        position=position,
                    )
                )
        elif name == "code":
            # Inline code outside <pre>: keep as short code block.
            code_text = tag.get_text(separator=" ", strip=True)
            if code_text.strip() and len(code_text.strip()) >= 8:
                push(
                    Block(
                        id=f"b{position}",
                        type=BlockType.CODE,
                        text=code_text.strip()[:max_block_chars],
                        parent_heading=current_heading,
                        language=_code_language(tag),
                        position=position,
                    )
                )
        elif name in {"ul", "ol"}:
            items = [
                _clean_text(li.get_text(separator=" ", strip=True))
                for li in tag.find_all("li", recursive=False)
            ]
            items = [item for item in items if item]
            if items:
                for li in tag.find_all("li", recursive=False):
                    if isinstance(li, Tag):
                        li["data-jev-consumed"] = "1"
                push(
                    Block(
                        id=f"b{position}",
                        type=BlockType.LIST,
                        text="\n".join(f"- {item}" for item in items)[:max_block_chars],
                        parent_heading=current_heading,
                        position=position,
                    )
                )
        elif name == "blockquote":
            text = _clean_text(tag.get_text(separator=" ", strip=True))
            if text:
                push(
                    Block(
                        id=f"b{position}",
                        type=BlockType.QUOTE,
                        text=text[:max_block_chars],
                        parent_heading=current_heading,
                        position=position,
                    )
                )
        elif name == "table":
            rows: list[str] = []
            for tr in tag.find_all("tr"):
                if not isinstance(tr, Tag):
                    continue
                cells = [
                    _clean_text(c.get_text(separator=" ", strip=True))
                    for c in tr.find_all(["th", "td"])
                    if isinstance(c, Tag)
                ]
                cells = [c for c in cells if c]
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                push(
                    Block(
                        id=f"b{position}",
                        type=BlockType.TABLE,
                        text="\n".join(rows)[:max_block_chars],
                        parent_heading=current_heading,
                        position=position,
                    )
                )
        elif name == "p":
            text = _clean_text(tag.get_text(separator=" ", strip=True))
            if text:
                push(
                    Block(
                        id=f"b{position}",
                        type=BlockType.PARAGRAPH,
                        text=text[:max_block_chars],
                        parent_heading=current_heading,
                        position=position,
                    )
                )
        # div/section/article/li fall through: paragraphs inside them are
        # already visited via recursive find_all("p"), so ignore containers.

        if len(blocks) >= max_blocks:
            break

    # Fallback: if structure extraction found nothing, use body text.
    if not blocks:
        fallback = _clean_text(body.get_text(separator=" ", strip=True))
        if fallback:
            push(
                Block(
                    id="b0",
                    type=BlockType.PARAGRAPH,
                    text=fallback[:max_block_chars],
                    parent_heading=None,
                    position=0,
                )
            )

    split = _split_oversized(blocks, max_block_chars=max_block_chars)
    return ParsedDocument(
        url=url, title=title, source_domain=_domain_of(url), blocks=split[:max_blocks]
    )


def _split_oversized(blocks: list[Block], *, max_block_chars: int) -> list[Block]:
    """Split only very large blocks, preserving original ID + parent context."""
    out: list[Block] = []
    for block in blocks:
        if (
            len(block.text) <= max_block_chars
            or block.type == BlockType.CODE
            and len(block.text) <= max_block_chars
        ):
            out.append(block)
            continue
        # Code blocks are never cut in half silently: if a code block exceeds
        # the cap it is kept whole here (budget layer handles it) rather than
        # split mid-statement. Other types split on paragraph boundaries.
        if block.type == BlockType.CODE:
            out.append(block)
            continue
        pieces = re.split(r"\n\n+", block.text)
        chunk = ""
        index = 0
        for piece in pieces:
            candidate = (chunk + "\n\n" + piece).strip() if chunk else piece
            if len(candidate) > max_block_chars and chunk:
                out.append(
                    Block(
                        id=f"{block.id}c{index}",
                        type=block.type,
                        text=chunk,
                        heading_level=block.heading_level,
                        parent_heading=block.parent_heading,
                        language=block.language,
                        position=block.position,
                        chunk_index=index,
                        source_block_id=block.id,
                    )
                )
                index += 1
                chunk = piece
            else:
                chunk = candidate
        if chunk.strip():
            out.append(
                Block(
                    id=f"{block.id}c{index}" if index else block.id,
                    type=block.type,
                    text=chunk,
                    heading_level=block.heading_level,
                    parent_heading=block.parent_heading,
                    language=block.language,
                    position=block.position,
                    chunk_index=index if index else None,
                    source_block_id=block.id if index else None,
                )
            )
    # Reassign deterministic sequential ids? No — keep original ids stable for
    # JEV mapping; positions stay as parsed.
    return out
