"""Benchmark: baseline vs JEV-filtered on live providers.

Measures per mode: search results, fetches, blocks before/after filtering,
estimated input tokens, latency, JEV requests + token usage. Requires live
API keys (``TYPESAFE_API_KEY`` and ``BRAVE_API_KEY``); there is deliberately
no offline/fixture mode — the numbers must reflect real evidence selection.
Results are written to ``benchmark_outputs/`` (gitignored) with date, model,
config, and thresholds.

No claims are made here — the output is raw measurements for the README to
quote with provenance. Re-run for your own workload and quote your numbers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from ..config import Settings, load_settings
from ..errors import EvidenceError
from ..pipeline import ResearchPipeline
from ..server import build_pipeline


@dataclass
class BenchmarkCase:
    name: str
    search_results: int
    fetched: int
    blocks_seen: int
    blocks_selected: int
    evidence_items: int
    estimated_input_tokens: int
    latency_ms: int
    jev_requests: int
    jev_input_tokens: int


async def run_case(
    name: str, pipe: ResearchPipeline, query: str, *, mode: str, max_sources: int = 6
) -> BenchmarkCase:
    started = time.monotonic()
    result = await pipe.run(query, max_sources=max_sources, mode=mode)  # type: ignore[arg-type]
    latency_ms = int((time.monotonic() - started) * 1000)
    meta = result.metadata
    return BenchmarkCase(
        name=name,
        search_results=meta.search_results,
        fetched=meta.documents_fetched,
        blocks_seen=meta.blocks_seen,
        blocks_selected=meta.blocks_selected,
        evidence_items=meta.evidence_items,
        estimated_input_tokens=meta.estimated_input_tokens,
        latency_ms=latency_ms,
        jev_requests=meta.jev_requests,
        jev_input_tokens=meta.jev_input_tokens,
    )


async def compare(query: str, settings: Settings) -> dict[str, object]:
    """Run baseline then JEV on identical live queries and contrast the two."""
    settings.require_search_key()
    settings.require_typesafe_key()
    pipe = build_pipeline(settings)
    jev_case = await run_case("jev", pipe, query, mode="jev", max_sources=settings.max_sources)
    base_case = await run_case(
        "baseline", pipe, query, mode="baseline", max_sources=settings.max_sources
    )
    return _report_with_cases(query, settings, base_case, jev_case)


def _report_with_cases(
    query: str, settings: Settings, base_case: BenchmarkCase, jev_case: BenchmarkCase
) -> dict[str, object]:
    def reduction(before: int, after: int) -> float:
        return round((before - after) / before, 3) if before else 0.0

    return {
        "date": datetime.now(timezone.utc).isoformat(),
        "model": settings.typesafe_model,
        "query": query,
        "config": {
            "max_search_results": settings.max_search_results,
            "result_thresholds": [
                settings.result_relevant_threshold,
                settings.result_useful_threshold,
            ],
            "block_thresholds": [
                settings.block_relevant_threshold,
                settings.block_actionable_threshold,
            ],
            "max_evidence_tokens": settings.max_evidence_tokens,
        },
        "baseline": asdict(base_case),
        "jev": asdict(jev_case),
        "context_reduction": reduction(
            base_case.estimated_input_tokens, jev_case.estimated_input_tokens
        ),
        "fetch_reduction": reduction(base_case.fetched, jev_case.fetched),
        "note": (
            "Token counts are the documented chars/4 approximation, not exact tokenizer output."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare baseline vs JEV-filtered evidence.")
    parser.add_argument(
        "--query", default="How do I bound concurrent HTTP fetches with retries in Python?"
    )
    parser.add_argument("--out", default="benchmark_outputs/latest.json")
    args = parser.parse_args()

    try:
        settings = load_settings()
        settings.require_search_key()
        settings.require_typesafe_key()
    except EvidenceError as exc:
        print(f"Benchmark needs live API keys: {exc.message}", file=sys.stderr)
        sys.exit(2)

    async def _run() -> dict[str, object]:
        pipe = build_pipeline(settings)
        jev_case = await run_case(
            "jev", pipe, args.query, mode="jev", max_sources=settings.max_sources
        )
        base_case = await run_case(
            "baseline", pipe, args.query, mode="baseline", max_sources=settings.max_sources
        )
        return _report_with_cases(args.query, settings, base_case, jev_case)

    report = asyncio.run(_run())
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    base = report["baseline"]
    jev = report["jev"]
    assert isinstance(base, dict) and isinstance(jev, dict)
    print(f"baseline: fetched={base['fetched']} blocks={base['blocks_seen']}")
    print(f"jev: fetched={jev['fetched']} blocks={jev['blocks_selected']}")
    print(f"reduction: {report['context_reduction']} fetch: {report['fetch_reduction']}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
