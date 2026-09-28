"""Benchmark harness: live-only, honest measurements, no fixture data.

The full comparison needs real API keys and network, so it is skipped
without them. The missing-keys path is tested: it must fail fast with a
configuration error, never with fabricated numbers.
"""

from __future__ import annotations

import os

import pytest

from jev_evidence_mcp.benchmark.bench import _report_with_cases, compare
from jev_evidence_mcp.config import Settings
from jev_evidence_mcp.errors import ErrorCode, EvidenceError

_LIVE = bool(os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY")) and bool(
    os.environ.get("BRAVE_API_KEY") or os.environ.get("SEARCH_API_KEY")
)


def test_compare_requires_live_keys(clean_env: None) -> None:
    settings = Settings()
    with pytest.raises(EvidenceError) as exc_info:
        import asyncio

        asyncio.run(compare("How do I bound concurrent fetches?", settings))
    assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR


def test_report_math_is_honest() -> None:
    from jev_evidence_mcp.benchmark.bench import BenchmarkCase

    base = BenchmarkCase(
        name="baseline",
        search_results=10,
        fetched=10,
        blocks_seen=80,
        blocks_selected=80,
        evidence_items=40,
        estimated_input_tokens=400,
        latency_ms=100,
        jev_requests=0,
        jev_input_tokens=0,
    )
    jev = BenchmarkCase(
        name="jev",
        search_results=10,
        fetched=8,
        blocks_seen=64,
        blocks_selected=50,
        evidence_items=20,
        estimated_input_tokens=300,
        latency_ms=200,
        jev_requests=9,
        jev_input_tokens=100,
    )
    report = _report_with_cases("q", Settings(), base, jev)
    assert report["context_reduction"] == 0.25
    assert report["fetch_reduction"] == 0.2
    assert isinstance(report["baseline"], dict) and isinstance(report["jev"], dict)
    assert "approximation" in str(report["note"])


@pytest.mark.skipif(not _LIVE, reason="needs TYPESAFE_API_KEY and BRAVE_API_KEY")
async def test_compare_baseline_vs_jev_live() -> None:
    from jev_evidence_mcp.config import load_settings

    settings = load_settings()
    report = await compare("How do I bound concurrent fetches?", settings)
    assert set(report) >= {"date", "model", "query", "config", "baseline", "jev"}
    baseline = report["baseline"]
    jev = report["jev"]
    assert isinstance(baseline, dict) and isinstance(jev, dict)
    assert jev["jev_requests"] >= 1
    assert baseline["jev_requests"] == 0
    assert 0.0 <= report["context_reduction"] <= 1.0  # type: ignore[operator]
    assert 0.0 <= report["fetch_reduction"] <= 1.0  # type: ignore[operator]
    assert "approximation" in str(report["note"])
