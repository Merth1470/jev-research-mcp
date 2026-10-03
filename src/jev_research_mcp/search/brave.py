"""Brave Search provider (V1 concrete provider).

Docs: https://brave.com/search/api/ — simple GET with an API key header.
The key belongs entirely to the user and is sent only to Brave.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..errors import ErrorCode, EvidenceError
from ..models import SearchResult
from .base import normalize_search_result


class BraveSearchProvider:
    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 15.0,
        base_url: str = "https://api.search.brave.com",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise EvidenceError(ErrorCode.CONFIGURATION_ERROR, "Brave search requires an API key.")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._base_url = base_url.rstrip("/")
        self._client = client

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        cleaned = query.strip()
        if not cleaned:
            raise EvidenceError(ErrorCode.VALIDATION_ERROR, "Search query must not be empty.")
        count = max(1, min(int(max_results), 20))  # Brave `count` max is 20 per request.
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self._api_key,
        }
        params = {"q": cleaned, "count": str(count)}
        try:
            if self._client is not None:
                response = await self._client.get(
                    f"{self._base_url}/res/v1/web/search",
                    headers=headers,
                    params=params,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(
                        f"{self._base_url}/res/v1/web/search",
                        headers=headers,
                        params=params,
                    )
        except httpx.TimeoutException as exc:
            raise EvidenceError(ErrorCode.TIMEOUT, f"Brave search timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise EvidenceError(
                ErrorCode.SEARCH_ERROR, f"Brave search transport failed: {exc}"
            ) from exc

        if response.status_code == 401 or response.status_code == 403:
            raise EvidenceError(
                ErrorCode.AUTHENTICATION_ERROR,
                "Brave search rejected the API key (401/403). Check BRAVE_API_KEY.",
            )
        if response.status_code == 429:
            raise EvidenceError(ErrorCode.SEARCH_ERROR, "Brave search rate limit (429).")
        if response.status_code >= 400:
            raise EvidenceError(
                ErrorCode.SEARCH_ERROR, f"Brave search failed with HTTP {response.status_code}."
            )
        try:
            payload: Any = response.json()
        except Exception as exc:
            raise EvidenceError(
                ErrorCode.SEARCH_ERROR, "Brave search returned invalid JSON."
            ) from exc

        web = payload.get("web", {}) if isinstance(payload, dict) else {}
        raw_items = web.get("results", []) if isinstance(web, dict) else []
        results: list[SearchResult] = []
        for index, item in enumerate(raw_items):
            if not isinstance(item, dict):
                continue
            normalized = normalize_search_result(
                result_id=f"r{len(results)}",
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                snippet=str(item.get("description") or ""),
                published_at=str(item.get("age") or item.get("page_age") or "")
                if (item.get("age") or item.get("page_age"))
                else None,
                metadata={"provider": "brave", "position": index},
            )
            if normalized is not None:
                results.append(normalized)
            if len(results) >= max_results:
                break
        return results
