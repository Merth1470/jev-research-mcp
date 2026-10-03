"""SearchProvider abstraction. The rest of the pipeline never cares which
search backend produced the candidates."""

from __future__ import annotations

from typing import Protocol
from urllib.parse import urlparse

from ..models import SearchResult


class SearchProvider(Protocol):
    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        """Return up to ``max_results`` normalized candidates for ``query``."""
        ...


def normalize_domain(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
        return host.removeprefix("www.")
    except Exception:
        return ""


def normalize_search_result(
    *,
    result_id: str,
    title: str | None,
    url: str | None,
    snippet: str | None,
    published_at: str | None = None,
    metadata: dict[str, object] | None = None,
) -> SearchResult | None:
    """Normalize one raw result; returns None for obviously malformed rows.

    No semantic processing here — only structural cleanup.
    """
    raw_url = (url or "").strip()
    if not raw_url:
        return None
    lowered = raw_url.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        return None
    # Reject overlong / control-char URLs that indicate garbage input.
    if len(raw_url) > 2048 or any(ord(c) < 32 for c in raw_url):
        return None
    title_clean = " ".join((title or "").split())
    snippet_clean = " ".join((snippet or "").split())
    if not title_clean and not snippet_clean:
        return None
    return SearchResult(
        id=result_id,
        title=title_clean[:500],
        url=raw_url,
        snippet=snippet_clean[:2000],
        domain=normalize_domain(raw_url),
        published_at=published_at,
        metadata=dict(metadata or {}),
    )
