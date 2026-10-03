"""Search normalization + live Brave provider mapping (mocked HTTP, no network).

Provider doubles for pipeline tests live in ``tests/helpers.py``.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from jev_research_mcp.errors import ErrorCode, EvidenceError
from jev_research_mcp.search.base import normalize_domain, normalize_search_result
from jev_research_mcp.search.brave import BraveSearchProvider
from tests.helpers import FakeSearchProvider, make_fixture_results


def test_normalize_trims_and_extracts_domain() -> None:
    result = normalize_search_result(
        result_id="r0",
        title="  Hello   World  ",
        url="https://WWW.Example.com/docs?a=1",
        snippet="line1\nline2",
    )
    assert result is not None
    assert result.title == "Hello World"
    assert result.domain == "example.com"
    assert result.snippet == "line1 line2"


def test_normalize_rejects_missing_url() -> None:
    assert normalize_search_result(result_id="r0", title="t", url="", snippet="s") is None


def test_normalize_rejects_non_http_scheme() -> None:
    assert (
        normalize_search_result(result_id="r0", title="t", url="file:///etc/passwd", snippet="s")
        is None
    )
    assert (
        normalize_search_result(result_id="r0", title="t", url="javascript:alert(1)", snippet="s")
        is None
    )


def test_normalize_rejects_empty_title_and_snippet() -> None:
    assert (
        normalize_search_result(result_id="r0", title="", url="https://x.com/", snippet="") is None
    )


def test_normalize_domain_edge_cases() -> None:
    assert normalize_domain("not a url") == ""
    assert normalize_domain("https://sub.docs.python.org/") == "sub.docs.python.org"


async def test_fake_provider_returns_bounded_results() -> None:
    provider = FakeSearchProvider(make_fixture_results(20))
    results = await provider.search("async retries", 20)
    assert len(results) == 20
    assert [r.id for r in results] == [f"r{i}" for i in range(20)]


async def test_fake_provider_rejects_empty_query() -> None:
    with pytest.raises(EvidenceError) as exc_info:
        await FakeSearchProvider().search("   ", 5)
    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


def _brave_client(payload: dict[str, Any], status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Subscription-Token"] == "k"
        return httpx.Response(status, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_brave_provider_parses_web_results() -> None:
    payload = {
        "web": {
            "results": [
                {
                    "title": "Docs",
                    "url": "https://docs.example.com/a",
                    "description": "How to configure retries.",
                    "age": "2026-01-01",
                },
                {"title": "", "url": "", "description": ""},  # malformed -> skipped
                {"title": "Bad", "url": "ftp://x/y", "description": "nope"},  # skipped
            ]
        }
    }
    provider = BraveSearchProvider("k", client=_brave_client(payload))
    results = await provider.search("retries", 10)
    assert len(results) == 1
    assert results[0].url == "https://docs.example.com/a"
    assert results[0].domain == "docs.example.com"


async def test_brave_provider_auth_error_mapped() -> None:
    provider = BraveSearchProvider("k", client=_brave_client({}, status=401))
    with pytest.raises(EvidenceError) as exc_info:
        await provider.search("q", 5)
    assert exc_info.value.code == ErrorCode.AUTHENTICATION_ERROR


async def test_brave_provider_timeout_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(EvidenceError) as exc_info:
        await BraveSearchProvider("k", client=client).search("q", 5)
    assert exc_info.value.code == ErrorCode.TIMEOUT
