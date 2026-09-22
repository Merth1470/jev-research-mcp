"""SSRF protection: syntax rejects + DNS-gated resolution (offline)."""

from __future__ import annotations

import socket

import pytest

from jev_evidence_mcp.errors import ErrorCode, EvidenceError
from jev_evidence_mcp.security.ssrf import assert_url_public, validate_url_syntax


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost:8000/x",
        "http://[::1]/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.0.9/",
        "http://169.254.169.254/latest/meta-data/",
        "http://100.100.100.200/",
        "http://metadata.google.internal/",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "javascript:alert(1)",
        "data:text/html,hi",
        "https://user:pass@example.com/",
        "",
    ],
)
def test_syntax_blocks_unsafe_urls(url: str) -> None:
    with pytest.raises(EvidenceError) as exc_info:
        validate_url_syntax(url)
    assert exc_info.value.code == ErrorCode.SECURITY_REJECTION


def test_syntax_allows_public_https() -> None:
    assert validate_url_syntax("https://docs.python.org/3/library/") == (
        "https://docs.python.org/3/library/"
    )


async def test_dns_public_addresses_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(host: str, *args: object, **kwargs: object) -> list[object]:
        assert host == "docs.example.com"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    assert await assert_url_public("https://docs.example.com/x") == "https://docs.example.com/x"


async def test_dns_private_result_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(host: str, *args: object, **kwargs: object) -> list[object]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.9.9", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(EvidenceError) as exc_info:
        await assert_url_public("https://evil.example.com/")
    assert exc_info.value.code == ErrorCode.SECURITY_REJECTION


async def test_dns_failure_refuses_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(host: str, *args: object, **kwargs: object) -> list[object]:
        raise socket.gaierror("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(EvidenceError) as exc_info:
        await assert_url_public("https://nonexistent.invalid/")
    assert exc_info.value.code == ErrorCode.SECURITY_REJECTION


async def test_dns_mixed_public_and_private_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """DNS rebinding guard: ALL resolved addresses must be public."""

    def fake_getaddrinfo(host: str, *args: object, **kwargs: object) -> list[object]:
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(EvidenceError) as exc_info:
        await assert_url_public("https://rebind.example.com/")
    assert exc_info.value.code == ErrorCode.SECURITY_REJECTION
