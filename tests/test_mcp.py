"""MCP protocol correctness: server starts, tool advertised, schema valid,
invalid args rejected, valid args execute, errors structured."""

from __future__ import annotations

import json
from typing import Any

import pytest

from jev_evidence_mcp.config import Settings
from jev_evidence_mcp.errors import ErrorCode, EvidenceError
from jev_evidence_mcp.pipeline import ResearchPipeline
from jev_evidence_mcp.server import build_pipeline, create_mcp_server
from tests.conftest import DOC_HTML
from tests.helpers import DictFetch, FakeDecisionProvider, FakeSearchProvider


def _offline_pipeline() -> ResearchPipeline:
    fixtures = [
        {
            "title": f"Guide {i}",
            "url": f"https://example.com/docs/{i}",
            "snippet": "async fetch guide",
        }
        for i in range(4)
    ]
    scores = {(f"r{i}", p): 0.9 for i in range(4) for p in ("relevant", "useful", "authoritative")}
    settings = Settings()
    return ResearchPipeline(
        settings,
        search=FakeSearchProvider(fixtures),
        fetch=DictFetch({f"https://example.com/docs/{i}": DOC_HTML for i in range(4)}),
        jev=FakeDecisionProvider(scores=scores),
    )


async def _list_tools(mcp: Any) -> list[Any]:
    if hasattr(mcp, "list_tools"):
        result = mcp.list_tools()
        if hasattr(result, "__await__"):
            result = await result
        return list(result)
    # v1 fallback via tool manager internals
    manager = getattr(mcp, "_tool_manager", None)
    assert manager is not None, "no tool listing API found"
    listing = manager.list_tools()
    if hasattr(listing, "__await__"):
        listing = await listing
    return list(listing)


async def _call_tool(mcp: Any, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if hasattr(mcp, "call_tool"):
        result = await mcp.call_tool(name, args)
        content = getattr(result, "content", [])
        assert content, "empty tool result content"
        text = getattr(content[0], "text", None)
        assert isinstance(text, str)
        parsed = json.loads(text)
        assert isinstance(parsed, dict)
        return parsed
    # v1 fallback: invoke the registered function directly
    tool = await mcp._tool_manager.get_tool(name)
    func = getattr(tool, "fn", None)
    assert func is not None
    out = func(**args)
    if hasattr(out, "__await__"):
        out = await out
    return out if isinstance(out, dict) else json.loads(out)


def test_server_starts_and_advertises_research_tool() -> None:
    mcp = create_mcp_server(Settings(), pipeline=_offline_pipeline())
    assert mcp is not None
    assert mcp.name == "jev-evidence"


async def test_tool_schema_valid() -> None:
    mcp = create_mcp_server(Settings(), pipeline=_offline_pipeline())
    tools = await _list_tools(mcp)
    names = [
        getattr(t, "name", None) or (t["name"] if isinstance(t, dict) else None) for t in tools
    ]
    assert "research" in names
    research = next(t for t in tools if (getattr(t, "name", None) or t["name"]) == "research")
    schema = getattr(research, "input_schema", None) or research.get("inputSchema", {})
    assert schema.get("type") == "object"
    assert "query" in schema.get("properties", {})
    assert "query" in schema.get("required", [])


async def test_valid_call_executes_pipeline() -> None:
    mcp = create_mcp_server(Settings(), pipeline=_offline_pipeline())
    out = await _call_tool(mcp, "research", {"query": "how to fetch async?"})
    assert "error" not in out
    assert out["query"] == "how to fetch async?"
    assert len(out["sources"]) > 0
    assert out["metadata"]["search_results"] == 4
    for source in out["sources"]:
        assert source["url"]
        assert len(source["evidence"]) > 0


async def test_empty_query_rejected_structured() -> None:
    mcp = create_mcp_server(Settings(), pipeline=_offline_pipeline())
    out = await _call_tool(mcp, "research", {"query": "   "})
    assert out["error"]["code"] == ErrorCode.VALIDATION_ERROR.value


async def test_invalid_mode_rejected_structured() -> None:
    mcp = create_mcp_server(Settings(), pipeline=_offline_pipeline())
    out = await _call_tool(mcp, "research", {"query": "q", "mode": "telepathy"})
    assert out["error"]["code"] == ErrorCode.VALIDATION_ERROR.value


async def test_baseline_mode_executes() -> None:
    mcp = create_mcp_server(Settings(), pipeline=_offline_pipeline())
    out = await _call_tool(mcp, "research", {"query": "q", "mode": "baseline"})
    assert "error" not in out
    assert out["metadata"]["mode"] == "baseline"


async def test_missing_jev_key_returns_configuration_error() -> None:
    settings = Settings()
    pipeline = ResearchPipeline(
        settings,
        search=FakeSearchProvider([{"title": "t", "url": "https://example.com/a", "snippet": "s"}]),
        fetch=DictFetch({"https://example.com/a": DOC_HTML}),
        jev=None,
    )
    mcp = create_mcp_server(settings, pipeline=pipeline)
    out = await _call_tool(mcp, "research", {"query": "q"})
    assert out["error"]["code"] == ErrorCode.CONFIGURATION_ERROR.value


def test_build_pipeline_accepts_injected_providers() -> None:
    settings = Settings()
    pipe = build_pipeline(
        settings,
        search=FakeSearchProvider([{"title": "t", "url": "https://example.com/a", "snippet": "s"}]),
        fetch=DictFetch({"https://example.com/a": DOC_HTML}),
        jev=FakeDecisionProvider(),
    )
    assert isinstance(pipe, ResearchPipeline)


def test_build_pipeline_rejects_unknown_provider() -> None:
    settings = Settings()
    settings.search_provider = "bogus"  # type: ignore[assignment]
    with pytest.raises(EvidenceError) as exc_info:
        build_pipeline(settings)
    assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR


def test_server_starts_without_keys() -> None:
    mcp = create_mcp_server(Settings())
    assert mcp is not None
    assert mcp.name == "jev-evidence"


async def test_missing_keys_return_structured_error_not_crash() -> None:
    mcp = create_mcp_server(Settings())
    out = await _call_tool(mcp, "research", {"query": "q", "mode": "baseline"})
    assert out["error"]["code"] == ErrorCode.CONFIGURATION_ERROR.value
