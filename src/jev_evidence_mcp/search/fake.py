"""In-memory fake search provider for tests, benchmarks, and offline use."""

from __future__ import annotations

from ..errors import ErrorCode, EvidenceError
from ..models import SearchResult
from .base import normalize_search_result


class FakeSearchProvider:
    """Returns preconfigured fixtures; records queries for invariant tests."""

    def __init__(self, fixtures: list[dict[str, str]] | None = None) -> None:
        self._fixtures = list(fixtures or [])
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        cleaned = query.strip()
        if not cleaned:
            raise EvidenceError(ErrorCode.VALIDATION_ERROR, "Search query must not be empty.")
        self.queries.append(cleaned)
        results: list[SearchResult] = []
        for index, item in enumerate(self._fixtures[:max_results]):
            normalized = normalize_search_result(
                result_id=f"r{index}",
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("snippet", ""),
                published_at=item.get("published_at"),
                metadata={"provider": "fake"},
            )
            if normalized is not None:
                normalized.id = f"r{len(results)}"
                results.append(normalized)
        return results


def make_fixture_results(count: int = 20) -> list[dict[str, str]]:
    """Build ``count`` realistic documentation-style fixtures."""
    topics = [
        (
            "Official docs: configuring async retries in httpx",
            "https://docs.python-httpx.org/en/stable/quickstart/",
            "Configure timeouts and retries with httpx.AsyncClient and exponential backoff.",
        ),
        (
            "GitHub issue: connection pooling under asyncio",
            "https://github.com/encode/httpx/discussions/1234",
            "Discussion of connection limits, pool timeouts, and semaphore-bounded concurrency.",
        ),
        (
            "Stack Overflow: how to bound concurrent fetches",
            "https://stackoverflow.com/questions/12345678/bound-concurrent-fetches",
            "Use asyncio.Semaphore to cap concurrent requests and respect upstream servers.",
        ),
    ]
    fixtures: list[dict[str, str]] = []
    for i in range(count):
        title, url, snippet = topics[i % len(topics)]
        fixtures.append({"title": f"{title} (part {i})", "url": f"{url}#p{i}", "snippet": snippet})
    return fixtures
