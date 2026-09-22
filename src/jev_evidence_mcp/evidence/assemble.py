"""Evidence assembly: context restoration, source preference, dedup, budget.

- Context: a selected block is returned with its nearest parent heading so
  ("Set this option to true." under "Enable streaming") stays intelligible.
- Source preference on duplicates: official docs > primary source >
  repo > reputable docs > secondary. Implemented as a small deterministic
  scorer (domain hints + JEV authority), not a taxonomy.
- Budget: whole blocks only; code never sliced; round-robin across sources
  preserves diversity; token counts are the documented chars/4 estimate.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Block, ParsedDocument, SourceEvidence
from .dedup import content_hash
from .tokens import estimate_tokens

_OFFICIAL_DOMAINS = ("docs.", "developer.", "developers.", "support.", "help.")
_REPO_DOMAINS = ("github.com", "gitlab.com", "bitbucket.org", "sourceforge.net")


def source_authority_score(domain: str, jev_authority: float | None) -> float:
    """Small deterministic preference scorer (higher = prefer)."""
    score = 0.0
    lowered = (domain or "").lower()
    if lowered.startswith(_OFFICIAL_DOMAINS) or "docs" in lowered.split("."):
        score += 0.30
    if lowered in _REPO_DOMAINS or lowered.endswith(".github.io"):
        score += 0.20
    if "wikipedia.org" in lowered or "stackoverflow.com" in lowered:
        score += 0.10
    if jev_authority is not None:
        score += 0.40 * jev_authority
    return score


def format_block(block: Block) -> str:
    """Render one block with minimal structural context (heading + content)."""
    text = block.text.strip()
    if block.type.value == "code":
        fence = f"```{block.language}" if block.language else "```"
        body = f"{fence}\n{text}\n```"
    else:
        body = text
    heading = (block.parent_heading or "").strip()
    # Headings carry their own context; don't duplicate it.
    if heading and block.type.value != "heading" and heading not in body[: len(heading) + 20]:
        return f"### {heading}\n\n{body}"
    return body


@dataclass
class _Candidate:
    doc: ParsedDocument
    block: Block
    text: str
    rank: float
    authority: float


def assemble_evidence(
    *,
    docs: list[ParsedDocument],
    kept_by_url: dict[str, list[Block]],
    block_rank: dict[str, float] | None = None,
    authority_by_url: dict[str, float] | None = None,
    max_tokens: int = 8_000,
) -> list[SourceEvidence]:
    rank_of = block_rank or {}
    authority_of = authority_by_url or {}

    # 1. Candidates with restored context + per-source authority.
    candidates: list[_Candidate] = []
    for doc in docs:
        kept = kept_by_url.get(doc.url, [])
        # Fall back to doc.url matching original_url is handled by caller keys.
        auth = source_authority_score(doc.source_domain, authority_of.get(doc.url))
        for block in kept:
            candidates.append(
                _Candidate(
                    doc=doc,
                    block=block,
                    text=format_block(block),
                    rank=rank_of.get(f"{doc.url}::{block.id}", rank_of.get(block.id, 0.5)),
                    authority=auth,
                )
            )

    # 2. Exact dedup with source preference: winner = highest
    #    (authority, rank); losers recorded as provenance.
    by_hash: dict[str, list[_Candidate]] = {}
    for cand in candidates:
        by_hash.setdefault(content_hash(cand.text), []).append(cand)
    winners: list[_Candidate] = []
    provenance: dict[int, list[str]] = {}
    for group in by_hash.values():
        group_sorted = sorted(group, key=lambda c: (c.authority, c.rank), reverse=True)
        winner = group_sorted[0]
        winners.append(winner)
        others = [c.doc.url for c in group_sorted[1:] if c.doc.url != winner.doc.url]
        if others:
            provenance[id(winner)] = sorted(set(others))

    # 3. Budget: round-robin across sources (diversity) ordered by each
    #    source's best rank; whole blocks only.
    per_source: dict[str, list[_Candidate]] = {}
    for winner in winners:
        per_source.setdefault(winner.doc.url, []).append(winner)
    for items in per_source.values():
        items.sort(key=lambda c: c.rank, reverse=True)
    source_order = sorted(
        per_source.keys(),
        key=lambda u: (
            max(c.authority for c in per_source[u]),
            max(c.rank for c in per_source[u]),
        ),
        reverse=True,
    )

    used = 0
    selected: list[_Candidate] = []
    progress = True
    first_overall = True
    while progress:
        progress = False
        for url in source_order:
            items = per_source.get(url, [])
            if not items:
                continue
            cand = items[0]
            cost = estimate_tokens(cand.text)
            if used + cost > max_tokens:
                if first_overall:
                    # Single over-budget block: kept whole, budget consumed.
                    selected.append(cand)
                    items.pop(0)
                    first_overall = False
                    progress = True
                continue
            selected.append(cand)
            items.pop(0)
            used += cost
            first_overall = False
            progress = True

    # 4. Group back into sources in rank order for stable output.
    selected_by_url: dict[str, list[_Candidate]] = {}
    for cand in selected:
        selected_by_url.setdefault(cand.doc.url, []).append(cand)

    doc_by_url = {d.url: d for d in docs}
    sources: list[SourceEvidence] = []
    for url in source_order:
        items = selected_by_url.get(url, [])
        if not items:
            continue
        doc = doc_by_url[url]
        sources.append(
            SourceEvidence(
                title=doc.title,
                url=doc.url,  # original URL preserved verbatim
                domain=doc.source_domain,
                evidence=[
                    {
                        "text": c.text,
                        "type": c.block.type.value,
                        "language": c.block.language,
                        "parent_heading": c.block.parent_heading,
                        "block_id": c.block.id,
                        "url": doc.url,
                        "score": round(c.rank, 4),
                        "also_seen_at": provenance.get(id(c), []),
                    }
                    for c in sorted(items, key=lambda c: c.block.position)
                ],
            )
        )
    return sources
