"""Pipeline integration: test doubles in, real pipeline stages under test.

Doubles live in ``tests/helpers.py`` and never touch production code.
"""

from __future__ import annotations

import pytest

from jev_research_mcp.config import Settings
from jev_research_mcp.errors import ErrorCode, EvidenceError
from jev_research_mcp.pipeline import ResearchPipeline
from tests.conftest import DOC_HTML
from tests.helpers import DictFetch, FakeDecisionProvider, FakeSearchProvider


def _stack(
    n_results: int = 20,
    *,
    jev: FakeDecisionProvider | None = None,
    fail: set[str] | None = None,
    **settings_kwargs: object,
) -> tuple[ResearchPipeline, FakeSearchProvider, DictFetch, FakeDecisionProvider]:
    fixtures = [
        {"title": f"Guide {i}", "url": f"https://example.com/docs/{i}", "snippet": f"snippet {i}"}
        for i in range(n_results)
    ]
    search = FakeSearchProvider(fixtures)
    # Distinct body per page (unique marker paragraph) so exact-dedup does
    # not collapse fixtures; identical-content collapsing is covered
    # separately in test_identical_pages_dedup_to_one_source.
    pages = {
        f"https://example.com/docs/{i}": DOC_HTML.replace(
            "</body>", f"<p>Unique marker paragraph {i}.</p></body>"
        )
        for i in range(n_results)
    }
    fetch = DictFetch(pages, fail=fail)
    provider = jev or FakeDecisionProvider()
    settings = Settings(**settings_kwargs)
    pipe = ResearchPipeline(settings, search=search, fetch=fetch, jev=provider)
    return pipe, search, fetch, provider


async def test_end_to_end_filters_then_fetches_only_selected() -> None:
    scores = {
        (f"r{i}", prop): (0.92 if i < 5 else 0.08)
        for i in range(20)
        for prop in ("relevant", "useful", "authoritative")
    }
    pipe, _search, fetch, jev = _stack(jev=FakeDecisionProvider(scores=scores))
    result = await pipe.run("how to stream?", max_sources=6)
    # Discarded results are never fetched: architectural invariant.
    assert len(fetch.calls) == 5
    assert set(fetch.calls) == {f"https://example.com/docs/{i}" for i in range(5)}
    assert result.metadata.search_results == 20
    assert result.metadata.selected_results == 5
    assert result.metadata.documents_fetched == 5
    assert result.metadata.blocks_seen > 0
    assert result.metadata.blocks_selected > 0
    assert result.metadata.jev_requests >= 1
    # Batched: one state + many questions per batch, not one call per question.
    assert len(jev.calls) < 5 + result.metadata.blocks_selected
    # Provenance on every item.
    for source in result.sources:
        assert source.url.startswith("https://example.com/docs/")
        for item in source.evidence:
            assert item.url == source.url
    # Context restoration: explanatory text carries its heading.
    all_text = "\n".join(item.text for s in result.sources for item in s.evidence)
    assert "Enable streaming" in all_text


async def test_one_failed_page_does_not_fail_request() -> None:
    scores = {
        (f"r{i}", prop): 0.92 for i in range(5) for prop in ("relevant", "useful", "authoritative")
    }
    pipe, _s, fetch, _j = _stack(
        5, jev=FakeDecisionProvider(scores=scores), fail={"https://example.com/docs/2"}
    )
    result = await pipe.run("q", max_sources=5)
    assert result.metadata.documents_fetched == 4
    assert result.metadata.documents_failed == 1
    assert len(result.sources) == 4


async def test_all_pages_failed_is_structured_failure() -> None:
    urls = {f"https://example.com/docs/{i}" for i in range(3)}
    pipe, _s, _f, _j = _stack(3, fail=urls)
    with pytest.raises(EvidenceError) as exc_info:
        await pipe.run("q", max_sources=3)
    assert exc_info.value.code == ErrorCode.FETCH_ERROR


async def test_empty_query_rejected() -> None:
    pipe, _s, _f, _j = _stack()
    with pytest.raises(EvidenceError) as exc_info:
        await pipe.run("   ")
    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


async def test_excessive_limits_bounded() -> None:
    scores = {
        (f"r{i}", prop): 0.92 for i in range(20) for prop in ("relevant", "useful", "authoritative")
    }
    pipe, _s, fetch, _j = _stack(jev=FakeDecisionProvider(scores=scores))
    result = await pipe.run("q", max_sources=1_000_000, max_evidence_tokens=10**12)
    assert len(fetch.calls) <= 10  # server cap, not 1M
    assert result.metadata.estimated_input_tokens <= 100_000 + 10_000


async def test_jev_mode_without_provider_nonempty() -> None:
    settings = Settings()
    fixtures = [{"title": "t", "url": "https://example.com/a", "snippet": "s"}]
    pipe = ResearchPipeline(
        settings, search=FakeSearchProvider(fixtures), fetch=DictFetch({}), jev=None
    )
    with pytest.raises(EvidenceError) as exc_info:
        await pipe.run("q")
    assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR


async def test_jev_failure_propagates_not_bypassed() -> None:
    jev = FakeDecisionProvider(fail_with=EvidenceError(ErrorCode.JEV_ERROR, "boom"))
    pipe, _s, _f, _j = _stack(3, jev=jev)
    with pytest.raises(EvidenceError) as exc_info:
        await pipe.run("q")
    assert exc_info.value.code == ErrorCode.JEV_ERROR


async def test_baseline_mode_needs_no_jev() -> None:
    pipe, _s, fetch, _j = _stack(4, jev=FakeDecisionProvider())
    result = await pipe.run("q", max_sources=4, mode="baseline")
    assert result.metadata.mode == "baseline"
    assert result.metadata.jev_requests == 0
    assert result.metadata.blocks_selected == result.metadata.blocks_seen
    assert len(fetch.calls) == 4


async def test_identical_pages_dedup_to_one_source() -> None:
    # Same HTML under different URLs: exact dedup keeps one winner and
    # records the other URLs as provenance.
    fixtures = [
        {"title": f"Guide {i}", "url": f"https://example.com/docs/{i}", "snippet": "s"}
        for i in range(3)
    ]
    settings = Settings()
    scores = {(f"r{i}", p): 0.92 for i in range(3) for p in ("relevant", "useful", "authoritative")}
    pipe = ResearchPipeline(
        settings,
        search=FakeSearchProvider(fixtures),
        fetch=DictFetch({f"https://example.com/docs/{i}": DOC_HTML for i in range(3)}),
        jev=FakeDecisionProvider(scores=scores),
    )
    result = await pipe.run("q", max_sources=3)
    assert len(result.sources) == 1
    assert sorted(result.sources[0].evidence[0].also_seen_at) == [
        "https://example.com/docs/1",
        "https://example.com/docs/2",
    ]


async def test_no_search_results_returns_empty() -> None:
    settings = Settings()
    pipe = ResearchPipeline(
        settings, search=FakeSearchProvider([]), fetch=DictFetch({}), jev=FakeDecisionProvider()
    )
    result = await pipe.run("q")
    assert result.sources == []
    assert result.metadata.search_results == 0
