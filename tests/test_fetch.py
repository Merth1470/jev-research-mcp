"""Fetcher: bounded, redirect-safe, content-gated (mocked HTTP, no internet)."""

from __future__ import annotations

import httpx
import pytest

from jev_evidence_mcp.errors import ErrorCode, EvidenceError
from jev_evidence_mcp.fetch.fetcher import HttpxFetchProvider

HTML = b"<html><head><title>T</title></head><body><p>Hello</p></body></html>"


def make_provider(
    handler: object, **kwargs: object
) -> tuple[HttpxFetchProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]
    provider = HttpxFetchProvider(client=client, verify_dns=False, **kwargs)  # type: ignore[arg-type]
    return provider, client


async def test_normal_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, content=HTML)

    provider, _ = make_provider(handler)
    page = await provider.fetch("https://example.com/a")
    assert page.status_code == 200
    assert "Hello" in page.content
    assert page.url == "https://example.com/a"


async def test_missing_content_type_allowed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=HTML)

    provider, _ = make_provider(handler)
    page = await provider.fetch("https://example.com/a")
    assert "Hello" in page.content


async def test_huge_response_rejected_by_length_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "content-length": "99999999"},
            content=b"x",
        )

    provider, _ = make_provider(handler)
    with pytest.raises(EvidenceError) as exc_info:
        await provider.fetch("https://example.com/big")
    assert exc_info.value.code == ErrorCode.FETCH_ERROR


async def test_huge_body_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"y" * 5000)

    provider, _ = make_provider(handler, max_response_bytes=1000)
    with pytest.raises(EvidenceError) as exc_info:
        await provider.fetch("https://example.com/big")
    assert exc_info.value.code == ErrorCode.FETCH_ERROR


async def test_timeout_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow server")

    provider, _ = make_provider(handler)
    with pytest.raises(EvidenceError) as exc_info:
        await provider.fetch("https://example.com/slow")
    assert exc_info.value.code == ErrorCode.TIMEOUT


async def test_redirect_followed_and_revalidated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "https://example.com/final"})
        return httpx.Response(200, headers={"content-type": "text/html"}, content=HTML)

    provider, _ = make_provider(handler)
    page = await provider.fetch("https://example.com/start")
    assert page.url == "https://example.com/final"


async def test_redirect_to_private_blocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/x"})

    provider, _ = make_provider(handler)
    with pytest.raises(EvidenceError) as exc_info:
        await provider.fetch("https://example.com/start")
    assert exc_info.value.code == ErrorCode.SECURITY_REJECTION


async def test_redirect_loop_bounded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://example.com/loop"})

    provider, _ = make_provider(handler, max_redirects=2)
    with pytest.raises(EvidenceError) as exc_info:
        await provider.fetch("https://example.com/loop")
    assert exc_info.value.code == ErrorCode.FETCH_ERROR


async def test_private_destination_blocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(200, content=b"x")

    provider, _ = make_provider(handler)
    with pytest.raises(EvidenceError) as exc_info:
        await provider.fetch("http://127.0.0.1/admin")
    assert exc_info.value.code == ErrorCode.SECURITY_REJECTION


async def test_unsupported_content_type_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=b"\x89PNG")

    provider, _ = make_provider(handler)
    with pytest.raises(EvidenceError) as exc_info:
        await provider.fetch("https://example.com/img.png")
    assert exc_info.value.code == ErrorCode.FETCH_ERROR


async def test_server_error_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"boom")

    provider, _ = make_provider(handler)
    with pytest.raises(EvidenceError) as exc_info:
        await provider.fetch("https://example.com/err")
    assert exc_info.value.code == ErrorCode.FETCH_ERROR


async def test_document_chars_truncated_not_rejected() -> None:
    body = b"<html><body><p>" + b"z" * 5000 + b"</p></body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, content=body)

    provider, _ = make_provider(handler, max_document_chars=1000)
    page = await provider.fetch("https://example.com/long")
    assert page.truncated is True
    assert len(page.content) == 1000


async def test_file_url_blocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(200, content=b"x")

    provider, _ = make_provider(handler)
    with pytest.raises(EvidenceError) as exc_info:
        await provider.fetch("file:///etc/passwd")
    assert exc_info.value.code == ErrorCode.SECURITY_REJECTION
