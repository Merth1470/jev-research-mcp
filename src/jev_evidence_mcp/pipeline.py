"""End-to-end research pipeline.

``research() -> search -> batched JEV result filter -> bounded concurrent
fetch -> parse -> batched JEV block filter -> context restore -> dedup ->
budget -> structured response``. Baseline mode skips both JEV stages for
comparison benchmarks. One failed page never fails the request; per-page
diagnostics ride along on the affected source.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Literal

from .batch import batch_list
from .cache import MemoryCache
from .config import Settings
from .errors import ErrorCode, EvidenceError
from .evidence.assemble import assemble_evidence
from .evidence.tokens import estimate_tokens
from .fetch.fetcher import FetchedPage, FetchProvider
from .jev.interface import DecisionProvider
from .jev.questions import (
    build_block_questions,
    build_block_state,
    build_result_questions,
    build_result_state,
)
from .models import Block, ParsedDocument, ResearchMetadata, ResearchResult, SearchResult
from .parse.parser import parse_html_to_document
from .policy.blocks import kept_blocks, select_blocks
from .policy.results import kept_results, select_results
from .search.base import SearchProvider

logger = logging.getLogger("jev_evidence_mcp")

Mode = Literal["jev", "baseline"]


@dataclass
class PipelineStats:
    jev_requests: int = 0
    jev_input_tokens: int = 0
    jev_output_tokens: int = 0
    blocks_seen: int = 0
    diagnostics: list[str] = field(default_factory=list)


class ResearchPipeline:
    def __init__(
        self,
        settings: Settings,
        *,
        search: SearchProvider,
        fetch: FetchProvider,
        jev: DecisionProvider | None,
        page_cache: MemoryCache[FetchedPage] | None = None,
    ) -> None:
        self._settings = settings
        self._search = search
        self._fetch = fetch
        self._jev = jev
        self._cache = page_cache or MemoryCache[FetchedPage](
            ttl_seconds=settings.cache_ttl_seconds if settings.enable_cache else 0.0
        )

    async def run(
        self,
        query: str,
        *,
        max_sources: int | None = None,
        max_evidence_tokens: int | None = None,
        mode: Mode = "jev",
    ) -> ResearchResult:
        started = time.monotonic()
        cleaned = (query or "").strip()
        if not cleaned:
            raise EvidenceError(ErrorCode.VALIDATION_ERROR, "Query must not be empty.")
        if len(cleaned) > 2000:
            raise EvidenceError(ErrorCode.VALIDATION_ERROR, "Query exceeds 2000 characters.")
        s = self._settings
        n_sources = max(1, min(int(max_sources or s.max_sources), s.max_sources))
        budget = max(100, min(int(max_evidence_tokens or s.max_evidence_tokens), 100_000))
        stats = PipelineStats()

        # 1. Search (bounded).
        try:
            results = await self._search.search(cleaned, s.max_search_results)
        except EvidenceError:
            raise
        except Exception as exc:
            raise EvidenceError(ErrorCode.SEARCH_ERROR, f"Search provider failed: {exc}") from exc
        logger.info("research started: query=%r search_results=%d", cleaned[:80], len(results))

        if not results:
            return self._empty_result(cleaned, started, mode, search_count=0)

        # 2. Result filtering (JEV batched) or baseline passthrough.
        authority_by_url: dict[str, float] = {}
        if mode == "jev":
            if self._jev is None:
                raise EvidenceError(
                    ErrorCode.CONFIGURATION_ERROR,
                    "JEV mode requires a DecisionProvider (missing TYPESAFE_API_KEY?).",
                )
            selected = await self._filter_results(cleaned, results, stats, authority_by_url)
        else:
            selected = list(results)
            for result in results:
                authority_by_url[result.url] = 0.5
        selected = selected[:n_sources]
        logger.info("result selection: kept=%d/%d", len(selected), len(results))
        if not selected:
            return self._empty_result(cleaned, started, mode, search_count=len(results))

        # 3. Bounded concurrent fetch (failures are per-page diagnostics).
        pages, failed = await self._fetch_all(selected)
        logger.info("fetch: ok=%d failed=%d", len(pages), failed)
        if not pages:
            raise EvidenceError(
                ErrorCode.FETCH_ERROR,
                f"All {len(selected)} selected pages failed to fetch; no evidence available.",
            )

        # 4. Parse into structured blocks.
        docs: list[ParsedDocument] = []
        for page in pages:
            try:
                docs.append(
                    parse_html_to_document(
                        page.content,
                        url=page.url,
                        max_blocks=s.max_blocks_per_document,
                    )
                )
            except Exception as exc:
                stats.diagnostics.append(f"parse failed for {page.url!r}: {exc}")
        stats.blocks_seen = sum(len(d.blocks) for d in docs)

        # 5. Block filtering (JEV batched) or baseline passthrough.
        kept_by_url: dict[str, list[Block]] = {}
        block_rank: dict[str, float] = {}
        if mode == "jev":
            assert self._jev is not None
            kept_by_url, block_rank = await self._filter_blocks(cleaned, docs, stats)
        else:
            for doc in docs:
                kept_by_url[doc.url] = list(doc.blocks)
                for block in doc.blocks:
                    block_rank[f"{doc.url}::{block.id}"] = 0.5
        selected_count = sum(len(v) for v in kept_by_url.values())
        logger.info("block selection: kept=%d/%d", selected_count, stats.blocks_seen)

        # 6-8. Assemble: context restore -> dedup w/ source preference -> budget.
        sources = assemble_evidence(
            docs=docs,
            kept_by_url=kept_by_url,
            block_rank=block_rank,
            authority_by_url=authority_by_url,
            max_tokens=budget,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        estimated_input = sum(estimate_tokens(src.url) for src in sources) + sum(
            estimate_tokens(item.text) for src in sources for item in src.evidence
        )
        metadata = ResearchMetadata(
            search_results=len(results),
            selected_results=len(selected),
            documents_fetched=len(pages),
            documents_failed=failed,
            blocks_seen=stats.blocks_seen,
            blocks_selected=selected_count,
            evidence_items=sum(len(src.evidence) for src in sources),
            estimated_input_tokens=estimated_input,
            jev_requests=stats.jev_requests,
            jev_input_tokens=stats.jev_input_tokens,
            latency_ms=latency_ms,
            mode=mode,
        )
        logger.info(
            "research done: sources=%d evidence=%d jev_requests=%d latency_ms=%d",
            len(sources),
            metadata.evidence_items,
            stats.jev_requests,
            latency_ms,
        )
        return ResearchResult(query=cleaned, sources=sources, metadata=metadata)

    def _empty_result(
        self, query: str, started: float, mode: Mode, *, search_count: int
    ) -> ResearchResult:
        return ResearchResult(
            query=query,
            sources=[],
            metadata=ResearchMetadata(
                search_results=search_count,
                latency_ms=int((time.monotonic() - started) * 1000),
                mode=mode,
            ),
        )

    async def _filter_results(
        self,
        query: str,
        results: list[SearchResult],
        stats: PipelineStats,
        authority_by_url: dict[str, float],
    ) -> list[SearchResult]:
        assert self._jev is not None
        s = self._settings
        ordered = list(results)
        kept_all: list[SearchResult] = []
        for batch in batch_list(ordered, s.jev_result_batch_size):
            state = build_result_state(query, batch, max_state_chars=s.jev_max_state_chars)
            questions, meta = build_result_questions(batch)
            try:
                decisions = await self._jev.decide_questions(
                    state=state, questions=questions, meta=meta
                )
            except EvidenceError:
                raise
            except Exception as exc:
                raise EvidenceError(
                    ErrorCode.JEV_ERROR, f"JEV result filtering failed: {exc}"
                ) from exc
            stats.jev_requests += 1
            stats.jev_input_tokens += decisions.input_tokens
            stats.jev_output_tokens += decisions.output_tokens
            verdicts = select_results(
                batch,
                decisions,
                relevant_threshold=s.result_relevant_threshold,
                useful_threshold=s.result_useful_threshold,
                uncertain_margin=s.result_uncertain_margin,
            )
            for verdict in verdicts:
                if verdict.authoritative is not None:
                    authority_by_url[verdict.result.url] = verdict.authoritative
                else:
                    authority_by_url.setdefault(verdict.result.url, 0.5)
            kept_all.extend(kept_results(verdicts))
        # Re-sort survivors globally by per-batch rank order stability: the
        # batches were already rank-sorted; concatenation preserves that.
        return kept_all

    async def _fetch_all(self, selected: list[SearchResult]) -> tuple[list[FetchedPage], int]:
        s = self._settings
        semaphore = asyncio.Semaphore(s.max_concurrent_fetches)
        failed = 0

        async def _one(url: str) -> FetchedPage | None:
            nonlocal failed
            cached = self._cache.get(url)
            if cached is not None:
                return cached
            async with semaphore:
                try:
                    page = await self._fetch.fetch(url)
                except EvidenceError as exc:
                    failed += 1
                    logger.warning("fetch failed for %r: %s", url, exc)
                    return None
                except Exception as exc:  # never let one page kill the request
                    failed += 1
                    logger.warning("fetch failed for %r: %s", url, exc)
                    return None
            self._cache.put(url, page)
            return page

        pages = await asyncio.gather(*[_one(r.url) for r in selected])
        ok = [p for p in pages if p is not None]
        return ok, failed

    async def _filter_blocks(
        self, query: str, docs: list[ParsedDocument], stats: PipelineStats
    ) -> tuple[dict[str, list[Block]], dict[str, float]]:
        assert self._jev is not None
        s = self._settings
        kept_by_url: dict[str, list[Block]] = {}
        block_rank: dict[str, float] = {}
        for doc in docs:
            if not doc.blocks:
                kept_by_url[doc.url] = []
                continue
            doc_kept: list[Block] = []
            for batch in batch_list(doc.blocks, s.jev_block_batch_size):
                state = build_block_state(
                    query,
                    batch,
                    source_url=doc.url,
                    max_block_chars=s.jev_max_block_chars_for_state,
                )
                questions, meta = build_block_questions(batch)
                try:
                    decisions = await self._jev.decide_questions(
                        state=state, questions=questions, meta=meta
                    )
                except EvidenceError:
                    raise
                except Exception as exc:
                    raise EvidenceError(
                        ErrorCode.JEV_ERROR, f"JEV block filtering failed: {exc}"
                    ) from exc
                stats.jev_requests += 1
                stats.jev_input_tokens += decisions.input_tokens
                stats.jev_output_tokens += decisions.output_tokens
                verdicts = select_blocks(
                    batch,
                    decisions,
                    relevant_threshold=s.block_relevant_threshold,
                    actionable_threshold=s.block_actionable_threshold,
                    uncertain_margin=s.block_uncertain_margin,
                )
                for verdict in verdicts:
                    block_rank[f"{doc.url}::{verdict.block.id}"] = verdict.rank_score
                doc_kept.extend(kept_blocks(verdicts))
            # kept_blocks returns document order per batch; merge batches in order.
            doc_kept.sort(key=lambda b: b.position)
            kept_by_url[doc.url] = doc_kept
        return kept_by_url, block_rank
