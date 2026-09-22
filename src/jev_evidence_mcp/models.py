"""Validated internal data models (Pydantic).

External JSON (search APIs, JEV, fetched HTML) is validated at the boundary
before it becomes one of these typed objects.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    CODE = "code"
    LIST = "list"
    QUOTE = "quote"
    TABLE = "table"
    OTHER = "other"


class SearchResult(BaseModel):
    model_config = {"extra": "ignore"}

    id: str = Field(description="Stable candidate ID, e.g. r0, r1, ...")
    title: str = ""
    url: str = ""
    snippet: str = ""
    domain: str = ""
    published_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("url")
    @classmethod
    def _url_must_be_http(cls, value: str) -> str:
        lowered = value.lower()
        if lowered and not (lowered.startswith("http://") or lowered.startswith("https://")):
            raise ValueError(f"unsupported URL scheme: {value!r}")
        return value


class Block(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    type: BlockType = BlockType.PARAGRAPH
    text: str = ""
    heading_level: int | None = None
    parent_heading: str | None = None
    language: str | None = None
    position: int = 0
    chunk_index: int | None = None
    source_block_id: str | None = None


class ParsedDocument(BaseModel):
    model_config = {"extra": "forbid"}

    url: str
    title: str = ""
    source_domain: str = ""
    blocks: list[Block] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    model_config = {"extra": "forbid"}

    text: str
    type: str = "paragraph"
    language: str | None = None
    parent_heading: str | None = None
    block_id: str = ""
    url: str = ""
    score: float | None = None
    also_seen_at: list[str] = Field(default_factory=list)


class SourceEvidence(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = ""
    url: str = ""
    domain: str = ""
    evidence: list[EvidenceItem] = Field(default_factory=list)
    diagnostic: str | None = None


class ResearchMetadata(BaseModel):
    model_config = {"extra": "forbid"}

    search_results: int = 0
    selected_results: int = 0
    documents_fetched: int = 0
    documents_failed: int = 0
    blocks_seen: int = 0
    blocks_selected: int = 0
    evidence_items: int = 0
    estimated_input_tokens: int = 0
    jev_requests: int = 0
    jev_input_tokens: int = 0
    latency_ms: int = 0
    mode: Literal["jev", "baseline"] = "jev"


class ResearchResult(BaseModel):
    model_config = {"extra": "forbid"}

    query: str = ""
    sources: list[SourceEvidence] = Field(default_factory=list)
    metadata: ResearchMetadata = Field(default_factory=ResearchMetadata)
