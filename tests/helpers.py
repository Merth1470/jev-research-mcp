"""Test-only doubles. Never imported by production code.

These fakes let the unit/integration suite run offline without API keys or
network access. Nothing here is served to users: the server, dashboard, and
benchmark only ever use live providers and return structured errors when
keys are missing.
"""

from __future__ import annotations

from typing import Any

from jev_evidence_mcp.errors import ErrorCode, EvidenceError
from jev_evidence_mcp.fetch.fetcher import FetchedPage
from jev_evidence_mcp.jev.interface import Decision, DecisionResult
from jev_evidence_mcp.models import SearchResult
from jev_evidence_mcp.search.base import normalize_search_result


class FakeDecisionProvider:
    """Offline test double. ``scores`` maps (candidate_id, property) -> value.

    ``drop`` simulates missing answers, ``extra`` unexpected IDs,
    ``malformed_values`` non-numeric answers, ``fail_with`` provider failure.
    """

    def __init__(
        self,
        scores: dict[tuple[str, str], float] | None = None,
        *,
        default: float = 0.9,
        fail_with: Exception | None = None,
        drop: set[tuple[str, str]] | None = None,
        extra: list[Decision] | None = None,
        malformed_values: dict[tuple[str, str], Any] | None = None,
    ) -> None:
        self._scores = dict(scores or {})
        self._default = default
        self._fail_with = fail_with
        self._drop = set(drop or set())
        self._extra = list(extra or [])
        self._malformed = dict(malformed_values or {})
        self.calls: list[dict[str, Any]] = []

    async def decide_questions(
        self,
        *,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]],
        meta: dict[str, str] | None = None,
    ) -> DecisionResult:
        if self._fail_with is not None:
            raise self._fail_with
        self.calls.append({"state": state, "questions": dict(questions)})
        decisions: list[Decision] = []
        qmeta = meta or {}
        for qid in questions:
            key = qmeta.get(qid, qid)
            # qid format: "<property>__<candidate_id>"
            if "__" in key:
                prop, cid = key.split("__", 1)
            else:
                prop, cid = key, ""
            if (cid, prop) in self._drop:
                continue
            if (cid, prop) in self._malformed:
                bad = self._malformed[(cid, prop)]
                decisions.append(
                    Decision(question_id=qid, candidate_id=cid, property=prop, value=bad)
                )
                continue
            value = self._scores.get((cid, prop), self._default)
            decisions.append(
                Decision(question_id=qid, candidate_id=cid, property=prop, value=float(value))
            )
        decisions.extend(self._extra)
        return DecisionResult(decisions=decisions, model="fake", input_tokens=0, output_tokens=0)


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
    """Build ``count`` documentation-style fixtures for tests."""
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


class DictFetch:
    """In-memory fetch double serving canned HTML per URL; counts calls."""

    def __init__(self, pages: dict[str, str], *, fail: set[str] | None = None) -> None:
        self._pages = pages
        self.fail = fail or set()
        self.calls: list[str] = []

    async def fetch(self, url: str) -> FetchedPage:
        self.calls.append(url)
        if url in self.fail:
            raise EvidenceError(ErrorCode.FETCH_ERROR, "fixture failure")
        return FetchedPage(
            url=url, original_url=url, content=self._pages[url], content_type="text/html"
        )
