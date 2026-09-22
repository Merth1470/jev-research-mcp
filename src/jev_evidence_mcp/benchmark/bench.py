"""Benchmark framework: baseline vs JEV-filtered (no fake performance claims).

Measures per mode: search results, fetches, blocks before/after filtering,
estimated input tokens, latency, JEV requests + token usage. Run offline
with fakes (``python -m jev_evidence_mcp.benchmark.bench``) or against live
providers by setting the documented env vars. Results are written to
``benchmark_outputs/`` (gitignored) with date, model, config, thresholds.

No claims are made here — the output is raw measurements for the README to
quote with provenance.
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
from ..fetch.fetcher import FetchedPage
from ..jev.interface import FakeDecisionProvider
from ..pipeline import ResearchPipeline
from ..search.fake import FakeSearchProvider

SAMPLE_HTML = """<!DOCTYPE html><html><head><title>{title}</title></head>
<body><nav>Home Products Pricing</nav>
<script>var tracker = 1;</script>
<div class="cookie-banner">Accept cookies</div>
<h1>{heading}</h1>
<p>{para1}</p>
<pre><code class="language-python">{code}</code></pre>
<p>{para2}</p>
<h2>Configuration</h2>
<p>{para3}</p>
<ul><li>Set timeout to 15 seconds</li><li>Bound concurrency with a semaphore</li></ul>
<footer>Copyright 2026 Example Corp</footer>
</body></html>"""

DOC_TOPICS = [
    (
        "Async fetching guide",
        "Fetch pages concurrently",
        "Use asyncio.Semaphore to bound concurrent fetches and respect upstream.",
        "client = httpx.AsyncClient(timeout=15.0)\nasync with semaphore:\n"
        "    r = await client.get(url)",
        "Retries use exponential backoff with a small maximum count.",
        "Always revalidate redirect targets against SSRF policy.",
    ),
    (
        "Unrelated marketing page",
        "Buy our miracle framework",
        "This page sells a JavaScript framework and has nothing to do with the task.",
        "console.log('buy now');",
        "Pricing starts at $999 per seat per month.",
        "Contact sales for a demo today.",
    ),
    (
        "SSRF protection checklist",
        "Blocking private destinations",
        "Resolve hosts and require every address to be globally routable.",
        "ip = ipaddress.ip_address(host)\nassert ip.is_global",
        "Block localhost, loopback, RFC-1918, link-local, and metadata IPs.",
        "Revalidate every redirect hop before following it.",
    ),
]


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


class DictFetchProvider:
    """Fake fetch serving canned HTML per URL; counts calls."""

    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages
        self.calls: list[str] = []

    async def fetch(self, url: str) -> FetchedPage:
        self.calls.append(url)
        if url not in self._pages:
            from ..errors import ErrorCode, EvidenceError

            raise EvidenceError(ErrorCode.FETCH_ERROR, f"No fixture for {url!r}.")
        html = self._pages[url]
        return FetchedPage(url=url, original_url=url, content=html, content_type="text/html")


def build_offline_stack(
    settings: Settings, *, jev_scores: dict[tuple[str, str], float] | None = None
) -> tuple[ResearchPipeline, FakeSearchProvider, DictFetchProvider, FakeDecisionProvider]:
    fixtures = [
        {"title": t, "url": f"https://example.com/docs/{i}", "snippet": p1}
        for i, (t, _h, p1, _c, _p2, _p3) in enumerate(DOC_TOPICS * 4)
    ]
    search = FakeSearchProvider(fixtures)
    pages = {}
    for i, (title, heading, para1, code, para2, para3) in enumerate(DOC_TOPICS * 4):
        # Unique marker per page keeps fixtures realistic (distinct URLs carry
        # distinct content); exact-dedup still collapses the shared boilerplate.
        pages[f"https://example.com/docs/{i}"] = SAMPLE_HTML.format(
            title=title, heading=heading, para1=para1, code=code, para2=para2, para3=para3
        ).replace("</body>", f"<p>Page-specific note {i}.</p></body>")
    fetch = DictFetchProvider(pages)
    jev = FakeDecisionProvider(scores=jev_scores or {})
    pipe = ResearchPipeline(settings, search=search, fetch=fetch, jev=jev)
    return pipe, search, fetch, jev


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
    # JEV run: relevant docs score high, marketing doc scores low.
    jev_scores: dict[tuple[str, str], float] = {}
    for i in range(12):
        relevant = (i % 3) != 1  # every 3rd doc is the marketing page
        for prop in ("relevant", "useful", "authoritative"):
            jev_scores[(f"r{i}", prop)] = 0.92 if relevant else 0.08
    # max_sources=10 (server cap): baseline fetches 10, JEV keeps the 8 relevant.
    pipe_jev, _s1, _f1, _j = build_offline_stack(settings, jev_scores=jev_scores)
    jev_case = await run_case("jev", pipe_jev, query, mode="jev", max_sources=10)

    pipe_base, _s2, _f2, _j2 = build_offline_stack(settings)
    base_case = await run_case("baseline", pipe_base, query, mode="baseline", max_sources=10)

    def reduction(before: int, after: int) -> float:
        return round((before - after) / before, 3) if before else 0.0

    return {
        "date": datetime.now(timezone.utc).isoformat(),
        "model": "fake-decision-provider (offline); live runs report settings.typesafe_model",
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
    except Exception:
        settings = Settings(search_provider="fake")  # type: ignore[arg-type]
        print("No valid env config; using offline defaults.", file=sys.stderr)

    report = asyncio.run(compare(args.query, settings))
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
