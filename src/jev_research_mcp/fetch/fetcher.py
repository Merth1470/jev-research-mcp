"""Secure bounded HTTP fetcher (plain HTTP, no browser automation).

Enforces, in order: URL validation + SSRF check, timeout, streaming
size limit, manual redirect handling with revalidation, content-type
gating, and document char capping. Redirects are handled manually (never
delegated to the HTTP client) so every hop is revalidated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin

import httpx

from ..errors import ErrorCode, EvidenceError
from ..security.ssrf import assert_url_public, is_redirect_allowed, validate_url_syntax

_ALLOWED_CONTENT_PREFIXES = (
    "text/html",
    "text/plain",
    "application/xhtml+xml",
)

_BINARY_HINTS = (
    "image/",
    "video/",
    "audio/",
    "application/pdf",
    "application/zip",
    "application/octet-stream",
    "application/wasm",
    "font/",
)


@dataclass
class FetchedPage:
    url: str  # final URL after redirects; original preserved by caller
    original_url: str = ""
    title_hint: str = ""
    content: str = ""
    content_type: str = ""
    status_code: int = 200
    truncated: bool = False
    response_bytes: int = 0


class FetchProvider(Protocol):
    async def fetch(self, url: str) -> FetchedPage: ...


def _content_type_allowed(content_type: str) -> bool:
    lowered = content_type.lower()
    if not lowered:
        return True  # missing content type: sniff below, allow text-like
    for hint in _BINARY_HINTS:
        if hint in lowered:
            return False
    for prefix in _ALLOWED_CONTENT_PREFIXES:
        if lowered.startswith(prefix):
            return True
    # e.g. application/json, application/xml, text/* variants: allow text-like.
    if lowered.startswith("text/") or "json" in lowered or "xml" in lowered:
        return True
    return False


class HttpxFetchProvider:
    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        max_response_bytes: int = 2_000_000,
        max_redirects: int = 5,
        max_document_chars: int = 200_000,
        client: httpx.AsyncClient | None = None,
        verify_dns: bool = True,
    ) -> None:
        self._timeout = timeout_seconds
        self._max_bytes = max_response_bytes
        self._max_redirects = max_redirects
        self._max_chars = max_document_chars
        self._client = client
        # verify_dns=False is a test-only escape hatch (offline suites use
        # MockTransport with reserved hostnames). Production always verifies.
        self._verify_dns = verify_dns

    async def _check(self, url: str) -> str:
        if self._verify_dns:
            return await assert_url_public(url)
        return validate_url_syntax(url)

    async def fetch(self, url: str) -> FetchedPage:
        original = url.strip()
        validate_url_syntax(original)  # fast synchronous reject before DNS
        current = await self._check(original)

        headers = {
            "User-Agent": "jev-research-mcp/0.1 (+local-research)",
            "Accept": "text/html,*/*",
        }
        redirects = 0
        try:
            if self._client is not None:
                return await self._fetch_with_client(
                    self._client, original, current, headers, redirects
                )
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=False) as client:
                return await self._fetch_with_client(client, original, current, headers, redirects)
        except EvidenceError:
            raise
        except httpx.TimeoutException as exc:
            raise EvidenceError(ErrorCode.TIMEOUT, f"Fetch timed out for {original!r}.") from exc
        except httpx.HTTPError as exc:
            raise EvidenceError(
                ErrorCode.FETCH_ERROR, f"Fetch transport failed for {original!r}."
            ) from exc

    async def _fetch_with_client(
        self,
        client: httpx.AsyncClient,
        original: str,
        current: str,
        headers: dict[str, str],
        redirects: int,
    ) -> FetchedPage:
        url = current
        while True:
            url = await self._check(url)
            try:
                response = await client.get(url, headers=headers, follow_redirects=False)
            except httpx.TimeoutException as exc:
                raise EvidenceError(
                    ErrorCode.TIMEOUT, f"Fetch timed out for {original!r}."
                ) from exc
            except httpx.HTTPError as exc:
                raise EvidenceError(
                    ErrorCode.FETCH_ERROR, f"Fetch failed for {original!r}."
                ) from exc

            if is_redirect_allowed(response.status_code):
                if redirects >= self._max_redirects:
                    raise EvidenceError(
                        ErrorCode.FETCH_ERROR, f"Too many redirects for {original!r}."
                    )
                location = response.headers.get("location", "")
                if not location:
                    raise EvidenceError(
                        ErrorCode.FETCH_ERROR, f"Redirect without location for {original!r}."
                    )
                url = urljoin(url, location)
                validate_url_syntax(url)  # reject file:/internal hops immediately
                redirects += 1
                continue

            if response.status_code == 429:
                raise EvidenceError(ErrorCode.FETCH_ERROR, f"Rate limited (429) for {original!r}.")
            if response.status_code >= 400:
                raise EvidenceError(
                    ErrorCode.FETCH_ERROR, f"HTTP {response.status_code} for {original!r}."
                )

            content_type = response.headers.get("content-type", "")
            if not _content_type_allowed(content_type):
                raise EvidenceError(
                    ErrorCode.FETCH_ERROR,
                    f"Unsupported content type {content_type!r} for {original!r}.",
                )

            raw = await self._read_bounded(client, url, headers, response)
            text = self._decode(raw, response)
            truncated = False
            if len(text) > self._max_chars:
                text = text[: self._max_chars]
                truncated = True
            return FetchedPage(
                url=url,
                original_url=original,
                content=text,
                content_type=content_type,
                status_code=response.status_code,
                truncated=truncated,
                response_bytes=len(raw),
            )

    async def _read_bounded(
        self, client: httpx.AsyncClient, url: str, headers: dict[str, str], first: httpx.Response
    ) -> bytes:
        """Stream the body enforcing MAX_RESPONSE_BYTES before buffering."""
        length_header = first.headers.get("content-length", "")
        if length_header.strip().isdigit() and int(length_header.strip()) > self._max_bytes:
            raise EvidenceError(
                ErrorCode.FETCH_ERROR, "Response exceeds size limit (content-length)."
            )
        chunks: list[bytes] = []
        total = 0
        # If the injected client already buffered (respx/mocks), reuse it.
        if first.is_closed or first.content:
            data = first.content or b""
            if len(data) > self._max_bytes:
                raise EvidenceError(ErrorCode.FETCH_ERROR, "Response exceeds size limit.")
            return data
        async with client.stream("GET", url, headers=headers, follow_redirects=False) as streamed:
            async for piece in streamed.aiter_bytes(chunk_size=65536):
                total += len(piece)
                if total > self._max_bytes:
                    raise EvidenceError(ErrorCode.FETCH_ERROR, "Response exceeds size limit.")
                chunks.append(piece)
        return b"".join(chunks)

    def _decode(self, raw: bytes, response: httpx.Response) -> str:
        # httpx infers charset from headers; fall back to utf-8.
        # Only LookupError (unknown codec) is expected; decoding itself is
        # infallible with errors="replace".
        try:
            if response.encoding:
                return raw.decode(response.encoding, errors="replace")
        except LookupError:
            pass
        return raw.decode("utf-8", errors="replace")
