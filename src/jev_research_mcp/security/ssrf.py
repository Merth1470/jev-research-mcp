"""SSRF protection for fetching search-supplied URLs.

Threat model: search results are untrusted third-party input. Fetching must
never reach non-public destinations (loopback, RFC-1918, link-local,
cloud metadata endpoints) — including via redirects or DNS rebinding tricks.

Strategy (defense in depth, stdlib only):
1. Allow only http/https schemes; reject file/data/javascript/etc.
2. Reject obviously unsafe hostnames textually (localhost, metadata hosts).
3. Resolve the hostname with getaddrinfo and require *every* resolved
   address to be globally routable (``ip.is_global``), which excludes
   private/loopback/link-local/reserved/multicast/unspecified ranges
   for both IPv4 and IPv6.
4. Revalidate every redirect target the same way, with a bounded count.

DNS resolution uses a thread to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from ..errors import ErrorCode, EvidenceError

_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata.google.com",
}

# Well-known cloud metadata IP literals blocked even before DNS.
_BLOCKED_IP_LITERALS = {
    "169.254.169.254",  # AWS/GCP/Azure link-local metadata
    "100.100.100.200",  # Alibaba metadata
    "fd00:ec2::254",
}


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _check_ip_global(ip_text: str, *, url_for_error: str) -> None:
    if ip_text in _BLOCKED_IP_LITERALS:
        raise EvidenceError(
            ErrorCode.SECURITY_REJECTION, f"Blocked metadata-service address for {url_for_error!r}."
        )
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError as exc:
        raise EvidenceError(
            ErrorCode.SECURITY_REJECTION, f"Unresolvable IP literal for {url_for_error!r}."
        ) from exc
    # ``is_global`` is False for private, loopback, link-local, reserved,
    # multicast, and unspecified addresses (both v4 and v6).
    if not ip.is_global:
        raise EvidenceError(
            ErrorCode.SECURITY_REJECTION,
            f"Blocked non-public destination {ip_text!r} for {url_for_error!r}.",
        )


def validate_url_syntax(url: str) -> str:
    """Reject non-http(s) schemes, credentials, and malformed hosts."""
    cleaned = url.strip()
    if not cleaned:
        raise EvidenceError(ErrorCode.SECURITY_REJECTION, "Empty URL blocked.")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise EvidenceError(
            ErrorCode.SECURITY_REJECTION, f"Blocked non-HTTP(S) URL scheme for {cleaned!r}."
        )
    if not parsed.hostname:
        raise EvidenceError(ErrorCode.SECURITY_REJECTION, f"URL has no host: {cleaned!r}.")
    if parsed.username or parsed.password:
        raise EvidenceError(ErrorCode.SECURITY_REJECTION, "URLs with credentials are blocked.")
    host = parsed.hostname.lower()
    if host in _BLOCKED_HOSTNAMES or host.endswith(".internal"):
        raise EvidenceError(ErrorCode.SECURITY_REJECTION, f"Blocked unsafe hostname {host!r}.")
    if _is_ip_literal(host):
        _check_ip_global(host, url_for_error=cleaned)
    if len(cleaned) > 2048:
        raise EvidenceError(ErrorCode.SECURITY_REJECTION, "Overlong URL blocked.")
    return cleaned


async def assert_url_public(url: str) -> str:
    """Full check: syntax + DNS resolution requiring all A/AAAA to be global."""
    cleaned = validate_url_syntax(url)
    host = urlparse(cleaned).hostname or ""
    if _is_ip_literal(host):
        return cleaned  # already checked above
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None, socket.AF_UNSPEC)
    except socket.gaierror as exc:
        raise EvidenceError(
            ErrorCode.SECURITY_REJECTION, f"DNS resolution failed for {host!r}; refusing to fetch."
        ) from exc
    if not infos:
        raise EvidenceError(
            ErrorCode.SECURITY_REJECTION, f"No DNS records for {host!r}; refusing to fetch."
        )
    for info in infos:
        sockaddr = info[4]
        if sockaddr and sockaddr[0]:
            _check_ip_global(str(sockaddr[0]), url_for_error=cleaned)
    return cleaned


def is_redirect_allowed(status_code: int) -> bool:
    return status_code in {301, 302, 303, 307, 308}
