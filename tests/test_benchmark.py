"""Benchmark framework runs offline and reports honest measurements."""

from __future__ import annotations

from jev_evidence_mcp.benchmark.bench import compare
from jev_evidence_mcp.config import Settings


async def test_compare_baseline_vs_jev() -> None:
    settings = Settings(search_provider="fake")
    report = await compare("How do I bound concurrent fetches?", settings)
    assert set(report) >= {"date", "model", "query", "config", "baseline", "jev"}
    baseline = report["baseline"]
    jev = report["jev"]
    assert isinstance(baseline, dict) and isinstance(jev, dict)
    # JEV filtered out the marketing pages: fewer fetches, fewer tokens.
    assert jev["fetched"] < baseline["fetched"]
    assert jev["estimated_input_tokens"] <= baseline["estimated_input_tokens"]
    assert jev["jev_requests"] >= 1
    assert baseline["jev_requests"] == 0
    assert 0.0 <= report["context_reduction"] <= 1.0  # type: ignore[operator]
    assert 0.0 <= report["fetch_reduction"] <= 1.0  # type: ignore[operator]
    assert "approximation" in str(report["note"])
