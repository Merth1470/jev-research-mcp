# JEV Evidence MCP

A self-hosted, open-source MCP server that uses **TypeSafe JEV** as a semantic
evidence-selection layer for coding-agent web research.

Instead of dumping raw search results and full web pages into an expensive
downstream coding model, this server filters twice with JEV — once at the
search-result level (before fetching) and once at the content-block level
(after parsing) — and returns compact evidence blocks with provenance.

## 1. What this is

A local MCP server exposing one primary tool, `research`:

```
query ("how do I bound concurrent fetches with retries?")
  → search → JEV result filter → fetch selected pages → parse to blocks
  → JEV block filter → context restore → dedup → token budget
  → { sources: [{ title, url, domain, evidence: [...] }], metadata }
```

It selects evidence. It does not rewrite, summarize, or generate content.

## 2. Why it exists

Coding agents burn large amounts of expensive context on irrelevant web
content: 20 search hits fetched in full, boilerplate included. JEV (a
System One decision model) returns calibrated yes/no judgments with one
shared state and many questions per request, which makes it cheap to ask
"is this result/block useful?" for dozens of candidates in a single call.
Filtering *before* fetching also avoids network work entirely for discarded
sources.

## 3. Architecture

```
Coding Agent
    │  MCP tool: research(query, max_sources?, max_evidence_tokens?, mode?)
    ▼
SearchProvider (Brave Search API; Fake for offline/tests)
    │  normalized SearchResult{id,title,url,snippet,domain}
    ▼
JEV result filter — ONE state {task, candidates} + N questions (relevant,
useful, authoritative per candidate), batched (JEV_RESULT_BATCH_SIZE)
    │  deterministic policy: keep = relevant AND useful (conservative band)
    ▼
FetchProvider — plain async HTTP, bounded concurrency (MAX_CONCURRENT_FETCHES),
SSRF-checked, redirect-revalidated, size/timeout/content-type gated
    │  one failed page → diagnostic; never fails the whole request
    ▼
Parser — deterministic HTML → structured blocks (heading/paragraph/code/
list/quote/table), noise stripped, code formatting + hierarchy preserved
    │  oversized blocks split only, with original ID + parent context
    ▼
JEV block filter — per-document batches (JEV_BLOCK_BATCH_SIZE) of
relevant/actionable Noul questions
    │  deterministic policy: keep = relevant AND actionable
    ▼
Assembly — heading context restored → exact dedup (source preference on
duplicates, provenance kept) → whole-block token budget (chars/4 estimate)
    ▼
Compact evidence + provenance + metadata → Coding Agent
```

Key principle: **JEV decides, code disposes.** JEV answers semantic
questions; all HTTP, parsing, batching, thresholds, budgets, and error
handling are ordinary deterministic code. JEV output never mutates state
directly — every response is validated (IDs, types, ranges, missing/
duplicate/unexpected answers) before the policy layer reads it.

## 4. How it works

1. **Search** (`src/jev_evidence_mcp/search/`): Brave provider returns
   normalized candidates (URL/title/snippet/domain). Malformed rows are
   rejected structurally, never semantically.
2. **Result filtering** (`jev/questions.py` + `policy/results.py`): one
   shared state plus `relevant/useful/authoritative` Noul questions per
   candidate in a single JEV call per batch. Policy keeps
   `relevant AND useful`; values in the uncertain band
   `[threshold − margin, threshold)` are **retained** (false negatives hurt
   more than false positives). Authority only reorders survivors.
3. **Fetch** (`fetch/fetcher.py`, `security/ssrf.py`): only kept URLs are
   fetched, concurrently under a semaphore. Every URL (including redirect
   hops) must use http(s) and resolve to globally-routable IPs — localhost,
   loopback, RFC-1918, link-local, and cloud metadata addresses are blocked.
   Responses are streamed under `MAX_RESPONSE_BYTES`, gated by content type
   (binary rejected), and capped at `MAX_DOCUMENT_CHARS`.
4. **Parse** (`parse/parser.py`): script/style/nav/cookie-banner/footer
   noise removed structurally; headings, paragraphs, code (verbatim,
   language kept), lists, quotes, tables extracted with parent headings.
5. **Block filtering**: blocks batched per document into single JEV calls
   (`relevant`/`actionable` per block), same conservative policy.
6. **Assembly** (`evidence/`): selected blocks get their parent heading
   back (`### Enable streaming` + block), code fenced with language,
   exact duplicates collapsed (winner = highest authority/rank, losers kept
   as `also_seen_at` provenance), then a round-robin-per-source whole-block
   budget under `MAX_EVIDENCE_TOKENS` (chars/4 approximation — documented,
   not an exact tokenizer count).

## 5. Installation

Requires Python ≥ 3.10.

```bash
git clone <your-fork-url> jev-evidence-mcp
cd jev-evidence-mcp
pip install -e ".[dev]"   # runtime + dev tools (or pip install -e . for runtime only)
cp .env.example .env      # then fill in your own keys (never commit .env)
```

Verify:

```bash
ruff check src tests && ruff format --check src tests
mypy src tests
pytest
```

## 6. Configuration

All configuration is environment variables (see `.env.example`). Every
value is validated on load; errors name the variable without echoing secrets.

| Variable | Default | Meaning |
|---|---|---|
| `TYPESAFE_API_KEY` | — (required for `jev` mode) | Your TypeSafe key (`JEV_API_KEY` also accepted) |
| `TYPESAFE_MODEL` | `jev-latest` | JEV model |
| `TYPESAFE_BASE_URL` | `https://api.typesafe.ai` | API root (gateway-compatible) |
| `SEARCH_PROVIDER` | `brave` | `brave` or `fake` (offline) |
| `BRAVE_API_KEY` | — (required for Brave) | Your Brave Search key (`SEARCH_API_KEY` fallback) |
| `MAX_SEARCH_RESULTS` | `20` (≤ 50) | Search candidates |
| `FETCH_TIMEOUT_SECONDS` | `15` | Per-request timeout |
| `MAX_RESPONSE_BYTES` | `2000000` | Streaming cap |
| `MAX_REDIRECTS` | `5` | Redirect hops |
| `MAX_DOCUMENT_CHARS` | `200000` | Document cap (truncates, never OOMs) |
| `MAX_CONCURRENT_FETCHES` | `5` (≤ 20) | Fetch semaphore |
| `JEV_RESULT_BATCH_SIZE` | `20` | Candidates per JEV call |
| `JEV_BLOCK_BATCH_SIZE` | `30` | Blocks per JEV call |
| `JEV_MAX_STATE_CHARS` | `80000` | State cap |
| `JEV_MAX_BLOCK_CHARS_FOR_STATE` | `2000` | Per-block text sent to JEV (full text kept for evidence) |
| `MAX_BLOCKS_PER_DOCUMENT` | `300` | Parser cap |
| `RESULT_RELEVANT_THRESHOLD` / `RESULT_USEFUL_THRESHOLD` | `0.5` | Noul keep thresholds |
| `RESULT_UNCERTAIN_MARGIN` | `0.15` | Conservative retain band |
| `BLOCK_RELEVANT_THRESHOLD` / `BLOCK_ACTIONABLE_THRESHOLD` | `0.5` | Block thresholds |
| `BLOCK_UNCERTAIN_MARGIN` | `0.15` | Conservative retain band |
| `MAX_EVIDENCE_TOKENS` | `8000` | Evidence budget (approx tokens) |
| `MAX_SOURCES` | `10` | Server-side cap on `max_sources` |
| `ENABLE_CACHE` / `CACHE_TTL_SECONDS` | `true` / `3600` | Process-local page cache |
| `LOG_LEVEL` | `INFO` | `DEBUG` for verbose |

## 7. MCP configuration

Stdio transport (V1 supports stdio only):

```bash
python -m jev_evidence_mcp
```

Example client config — see [`examples/mcp_config.json`](examples/mcp_config.json)
(replace `/path/to/jev-evidence-mcp` with your checkout; keys are yours):

```json
{
  "mcpServers": {
    "jev-evidence": {
      "command": "python",
      "args": ["-m", "jev_evidence_mcp"],
      "cwd": "/path/to/jev-evidence-mcp",
      "env": {
        "TYPESAFE_API_KEY": "YOUR_TYPESAFE_API_KEY",
        "SEARCH_PROVIDER": "brave",
        "BRAVE_API_KEY": "YOUR_BRAVE_SEARCH_API_KEY"
      }
    }
  }
}
```

Tool schema — `research`:

| Argument | Type | Required | Notes |
|---|---|---|---|
| `query` | string | yes | Non-empty, ≤ 2000 chars |
| `max_sources` | integer | no | Clamped to server `MAX_SOURCES` |
| `max_evidence_tokens` | integer | no | Clamped server-side; whole blocks only |
| `mode` | string | no | `"jev"` (default) or `"baseline"` (no JEV, for comparison) |

Returns `{ query, sources: [{ title, url, domain, evidence: [{ text, type, language, parent_heading, block_id, url, score, also_seen_at }] }], metadata }`
or `{ query, sources: [], metadata: {}, error: { code, message } }` on failure.
Works with MCP Python SDK v1 (`FastMCP`) and v2 (`MCPServer`).

### 7a. Local dashboard (visualize the context cut)

`python -m jev_evidence_mcp` also starts a localhost dashboard (stdout stays
clean for MCP; the URL is printed to stderr):

```bash
python -m jev_evidence_mcp                # MCP stdio + dashboard at http://localhost:8765
python -m jev_evidence_mcp --ui-only      # dashboard only (preview the UI)
python -m jev_evidence_mcp --no-ui        # MCP stdio only
python -m jev_evidence_mcp --ui-port 8899 --open-browser
```

The page shows the 6 pipeline stages, an offline baseline-vs-JEV demo
(no keys needed), a live query box, and a kept-vs-cut funnel
(search → selected → fetched → blocks seen/kept → evidence → tokens).
Without `TYPESAFE_API_KEY`/`BRAVE_API_KEY` it runs the bundled demo stack
and labels results `demo`; with keys it runs your live pipeline (`live`).
Config: `ENABLE_UI`, `UI_HOST`, `UI_PORT`, `UI_OPEN_BROWSER`. No new
dependencies (stdlib HTTP server + one static HTML file).

## 8. Search provider configuration

V1 ships one concrete provider: **Brave Search API**
(`GET https://api.search.brave.com/res/v1/web/search`, `X-Subscription-Token`
header). Set `BRAVE_API_KEY` (or `SEARCH_API_KEY`). Your key is sent only to
Brave. To add a provider, implement the `SearchProvider` protocol
(`search(query, max_results) -> list[SearchResult]`) and wire it in
`server.build_pipeline`. `SEARCH_PROVIDER=fake` serves built-in fixtures for
offline development and tests.

## 9. JEV configuration

Set `TYPESAFE_API_KEY` (SDK default name; `JEV_API_KEY` accepted as alias).
The adapter uses the **official `typesafe-sdk`** (`TypeSafeClient` /
`AsyncTypeSafeClient`, `Noul` questions, `system_one(state, questions)`)
against `POST {TYPESAFE_BASE_URL}/v1/systemone`. A tiny isolated HTTP fallback
(`jev/http_provider.py`) speaks the same documented contract and is used only
if the SDK path is unavailable. The rest of the app depends only on the
`DecisionProvider` interface (`decide_questions(state, questions, meta)`),
so the SDK can evolve without touching pipeline code.

Question contracts are fixed in `jev/questions.py` (result: relevant / useful
/ authoritative; block: relevant / actionable) — explicit interpretations, no
vague "is this good?" prompts.

## 10. Example usage

```python
# Via MCP (coding agent side): call tool "research"
# { "query": "How do I bound concurrent HTTP fetches with retries in Python?",
#   "max_sources": 6 }
#
# Response (shape):
# {
#   "query": "...",
#   "sources": [{
#     "title": "Async Fetch Guide",
#     "url": "https://example.com/guide",
#     "domain": "example.com",
#     "evidence": [{
#       "text": "### Enable streaming\n\nSet this option to true.",
#       "type": "paragraph", "language": None,
#       "parent_heading": "Enable streaming",
#       "block_id": "b1", "url": "https://example.com/guide",
#       "score": 0.91, "also_seen_at": []
#     }]
#   }],
#   "metadata": { "search_results": 20, "selected_results": 6,
#     "documents_fetched": 6, "blocks_seen": 400, "blocks_selected": 50, ... }
# }
```

Offline benchmark (no keys needed):

```bash
python -m jev_evidence_mcp.benchmark.bench --out benchmark_outputs/latest.json
```

## 11. Privacy model

The repository ships **software only**. The author's infrastructure receives
nothing — there is no telemetry, analytics, update check, or phone-home in
the code or its dependencies' usage (network calls go to exactly three
places: your configured search provider, the TypeSafe JEV API, and the
source URLs returned by search). Queries, documents, and keys stay on your
machine except where necessarily sent to those providers:

- search query + `max_results` → your search provider (Brave) to retrieve candidates;
- task + candidate/block text → TypeSafe JEV API for yes/no judgments;
- HTTP GET → each selected source URL to fetch content.

No other network destinations are contacted. Logs contain counts, timings,
and truncated queries — never API keys or authorization headers.

## 12. Security considerations

- **SSRF**: search results are untrusted. Only `http(s)` URLs without
  credentials are fetched; hostnames are resolved and *every* A/AAAA record
  must be globally routable (`ip.is_global` covers loopback, private,
  link-local, reserved, multicast for v4/v6); metadata-service literals are
  denied; every redirect hop is revalidated under `MAX_REDIRECTS`.
- **Bounds everywhere**: response bytes streamed under a cap, document chars
  capped, JEV state capped, concurrency semaphored, retries bounded with
  backoff (transient only — never auth/validation/security errors).
- **Untrusted inputs validated**: search JSON, JEV answers (IDs, Noul ranges,
  missing/duplicate/unexpected), fetched HTML (never executed, parsed as text
  only), tool arguments (empty/oversized rejected, limits clamped).
- **Secrets**: from your environment only; error messages and logs never
  echo them (covered by tests).

## 13. Testing

```bash
pytest                      # full suite (offline; ~145 tests)
pytest tests/test_live_smoke.py   # live JEV check — only runs with TYPESAFE_API_KEY
```

Coverage: config/bounds, search normalization, batching, SSRF + redirect
validation, fetcher (size/timeout/content-type/errors), parser fixtures
(noise vs. docs/code/lists/tables), question batching shape, JEV validation
(missing/unexpected/duplicate/out-of-range), deterministic policies
(including spec'd keep/drop/uncertain fixtures), dedup/tokens/assembly
(context, fences, budget, provenance), offline providers, pipeline
invariants (discarded results never fetched; one failure ≠ total failure),
MCP protocol (advertise/schema/execute/structured errors), benchmark, cache.

## 14. Benchmarking

`python -m jev_evidence_mcp.benchmark.bench` compares `baseline` (no JEV)
vs `jev` on identical fixtures and writes JSON with date, model, config,
thresholds, and per-mode measurements (results, fetches, blocks
before/after, approx tokens, latency, JEV requests/tokens).

Measured on the bundled offline fixtures (2026-09-22, fake decision
provider, thresholds 0.5/0.5, `MAX_EVIDENCE_TOKENS=8000`):

| Metric | Baseline | JEV-filtered |
|---|---|---|
| Pages fetched | 10 | 8 (−20%) |
| Blocks seen | 80 | 64 |
| Est. input tokens (chars/4 approx) | ~488 | ~372 (−23.8%) |
| JEV requests | 0 | 9 |

These are fixture measurements, not general claims: live savings depend on
query, sources, and thresholds. Re-run the benchmark for your workload and
quote your own numbers.

## 15. Limitations

- JEV is a hosted API: `jev` mode needs a key and network; offline use is
  `mode="baseline"` or `SEARCH_PROVIDER=fake`.
- V1 does single-pass retrieval only (no adaptive second pass).
- Dedup is exact-match only (whitespace-normalized); no near-duplicate or
  semantic similarity.
- Token counts are a chars/4 approximation, not a real tokenizer.
- Fetcher is plain HTTP: JavaScript-rendered pages yield little or no content.
- Brave is the only bundled search provider (interface is open for more).
- MCP transport is stdio only.

## 16. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Missing TYPESAFE_API_KEY` | Set it in `.env`/environment for `jev` mode; or use `mode="baseline"` |
| `Brave search rejected the API key (401/403)` | Check `BRAVE_API_KEY` (or `SEARCH_API_KEY`) |
| `JEV rejected the API key` | Check `TYPESAFE_API_KEY`; test with `tests/test_live_smoke.py` |
| `All N selected pages failed to fetch` | Sources unreachable/blocked; check network, SSRF logs at `DEBUG` |
| Empty `sources` with `search_results > 0` | Thresholds too strict for the query; lower `*_THRESHOLD` or widen margin |
| `JEV rate limit exceeded` | Bounded retries exhausted; wait and retry |
| MCP tool returns `validation_error` for `mode` | Use `"jev"` or `"baseline"` exactly |

## 17. Development setup

```bash
pip install -e ".[dev]"
ruff check src tests && ruff format --check src tests
mypy src tests
pytest
python -m build   # or: pip wheel . --no-deps  (validates packaging)
```

Commit discipline: one subsystem per commit (`feat: …`, `test: …`, `docs: …`),
verified with status/diff/tests/lint/type-check before each commit. No secrets
in the tree (`.env`, caches, logs, `benchmark_outputs/` are gitignored).

## License

MIT — see [LICENSE](LICENSE).
