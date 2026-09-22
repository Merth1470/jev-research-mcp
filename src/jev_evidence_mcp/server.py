"""MCP server: exposes the single ``research`` tool.

Compatible with both MCP Python SDK v1 (``FastMCP``) and v2 (``MCPServer``);
the shim below picks whichever import path exists. Tool input is minimal
(query + optional caps); JEV thresholds stay server-side per V1 scope.
Failures are returned as structured ``{"error": {...}}`` payloads — one bad
webpage never crashes the tool.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .cache import MemoryCache
from .config import Settings, load_settings
from .errors import ErrorCode, EvidenceError
from .fetch.fetcher import FetchedPage, HttpxFetchProvider
from .jev.interface import DecisionProvider
from .jev.sdk_provider import SdkDecisionProvider
from .pipeline import ResearchPipeline
from .search.brave import BraveSearchProvider
from .search.fake import FakeSearchProvider, make_fixture_results

logger = logging.getLogger("jev_evidence_mcp")


def _load_mcp_class() -> Any:
    try:  # MCP SDK v1
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found, attr-defined]

        return FastMCP
    except ImportError:
        pass
    try:  # MCP SDK v2 (FastMCP renamed to MCPServer)
        from mcp.server.mcpserver import MCPServer  # type: ignore[import-not-found]

        return MCPServer
    except ImportError as exc:
        raise EvidenceError(
            ErrorCode.CONFIGURATION_ERROR,
            "MCP SDK not installed. Install it with: pip install mcp",
        ) from exc


def build_pipeline(
    settings: Settings,
    *,
    search: Any | None = None,
    fetch: Any | None = None,
    jev: DecisionProvider | None = None,
    jev_override: bool = False,
) -> ResearchPipeline:
    """Wire concrete providers from settings; explicit args win (tests)."""
    search_provider = search
    if search_provider is None:
        if settings.search_provider == "fake":
            search_provider = FakeSearchProvider(make_fixture_results(settings.max_search_results))
        else:
            search_provider = BraveSearchProvider(
                settings.require_search_key(),
                timeout_seconds=settings.fetch_timeout_seconds,
            )
    fetch_provider = fetch or HttpxFetchProvider(
        timeout_seconds=settings.fetch_timeout_seconds,
        max_response_bytes=settings.max_response_bytes,
        max_redirects=settings.max_redirects,
        max_document_chars=settings.max_document_chars,
    )
    jev_provider: DecisionProvider | None = jev
    if jev_provider is None and not jev_override:
        if settings.typesafe_api_key:
            jev_provider = SdkDecisionProvider(
                api_key=settings.typesafe_api_key,
                model=settings.typesafe_model,
                base_url=settings.typesafe_base_url,
            )
    cache = MemoryCache[FetchedPage](
        ttl_seconds=settings.cache_ttl_seconds if settings.enable_cache else 0.0
    )
    return ResearchPipeline(
        settings, search=search_provider, fetch=fetch_provider, jev=jev_provider, page_cache=cache
    )


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Never leak secrets: SDK redacts auth headers itself; our logs carry
    # only counts, timings, and truncated queries.


def create_mcp_server(
    settings: Settings | None = None,
    *,
    pipeline: ResearchPipeline | None = None,
) -> Any:
    settings = settings or load_settings()
    configure_logging(settings.log_level)
    pipe = pipeline or build_pipeline(settings)
    server_cls = _load_mcp_class()
    mcp = server_cls("jev-evidence")

    @mcp.tool()
    async def research(
        query: str,
        max_sources: int | None = None,
        max_evidence_tokens: int | None = None,
        mode: str = "jev",
    ) -> dict[str, Any]:
        """Research a coding question and return compact evidence with provenance.

        Args:
            query: The coding/research question (non-empty, max 2000 chars).
            max_sources: Max sources to fetch (1..server cap, default server-side).
            max_evidence_tokens: Evidence budget cap (approx tokens, whole blocks only).
            mode: 'jev' (semantic filtering) or 'baseline' (no JEV, for comparison).
        """
        if mode not in ("jev", "baseline"):
            return {
                "query": query,
                "sources": [],
                "metadata": {},
                "error": {
                    "code": ErrorCode.VALIDATION_ERROR.value,
                    "message": f"Invalid mode {mode!r}; expected 'jev' or 'baseline'.",
                },
            }
        try:
            result = await pipe.run(
                query,
                max_sources=max_sources,
                max_evidence_tokens=max_evidence_tokens,
                mode=mode,  # type: ignore[arg-type]
            )
        except EvidenceError as exc:
            logger.warning("research failed: %s", exc)
            return {
                "query": query,
                "sources": [],
                "metadata": {},
                "error": {"code": exc.code.value, "message": exc.message},
            }
        except Exception as exc:  # never crash the server on unexpected errors
            logger.exception("research internal error")
            return {
                "query": query,
                "sources": [],
                "metadata": {},
                "error": {
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": f"Internal error: {exc}",
                },
            }
        return result.model_dump()

    return mcp


def _run_stdio(mcp: Any) -> None:
    # v2 async entry points first, then v1 sync run().
    if hasattr(mcp, "run_stdio_async"):
        asyncio.run(mcp.run_stdio_async())
    elif hasattr(mcp, "run"):
        result = mcp.run()
        if asyncio.iscoroutine(result):
            asyncio.run(result)
    else:  # pragma: no cover - defensive
        raise EvidenceError(ErrorCode.CONFIGURATION_ERROR, "MCP server has no known run method.")
