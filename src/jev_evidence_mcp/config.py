"""Environment-based configuration with validation on load.

All secrets come from the user's own environment. Nothing is sent anywhere
except the user-configured search provider, the JEV API, and the source
URLs returned by search. Secrets are never logged.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .errors import ErrorCode, EvidenceError


def _get_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name, "")
        if value.strip():
            return value.strip()
    return default


def _get_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise EvidenceError(
            ErrorCode.CONFIGURATION_ERROR, f"Invalid numeric value for {name}: {raw!r}"
        ) from exc


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return default
    try:
        return int(float(raw.strip()))
    except ValueError as exc:
        raise EvidenceError(
            ErrorCode.CONFIGURATION_ERROR, f"Invalid integer value for {name}: {raw!r}"
        ) from exc


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    """Validated runtime configuration (no secrets in repr)."""

    model_config = {"extra": "forbid"}

    # JEV / TypeSafe
    typesafe_api_key: str = Field(default="", description="User's TypeSafe API key")
    typesafe_model: str = Field(default="jev-latest")
    typesafe_base_url: str = Field(default="https://api.typesafe.ai")

    # Search
    search_provider: Literal["brave", "fake"] = Field(default="brave")
    brave_api_key: str = Field(default="")
    max_search_results: int = Field(default=20, ge=1, le=50)

    # Fetch / HTTP
    fetch_timeout_seconds: float = Field(default=15.0, ge=1.0, le=120.0)
    max_response_bytes: int = Field(default=2_000_000, ge=10_000, le=20_000_000)
    max_redirects: int = Field(default=5, ge=0, le=10)
    max_document_chars: int = Field(default=200_000, ge=1_000, le=2_000_000)
    max_concurrent_fetches: int = Field(default=5, ge=1, le=20)

    # JEV batching
    jev_result_batch_size: int = Field(default=20, ge=1, le=50)
    jev_block_batch_size: int = Field(default=30, ge=1, le=100)
    jev_max_state_chars: int = Field(default=80_000, ge=1_000, le=500_000)
    jev_max_block_chars_for_state: int = Field(default=2_000, ge=200, le=20_000)
    max_blocks_per_document: int = Field(default=300, ge=10, le=2_000)

    # Selection thresholds (Noul probabilities in [0,1])
    result_relevant_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    result_useful_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    result_uncertain_margin: float = Field(default=0.15, ge=0.0, le=0.5)
    block_relevant_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    block_actionable_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    block_uncertain_margin: float = Field(default=0.15, ge=0.0, le=0.5)

    # Evidence budget
    max_evidence_tokens: int = Field(default=8_000, ge=100, le=100_000)
    max_sources: int = Field(default=10, ge=1, le=20)

    # Cache / logging
    enable_cache: bool = Field(default=True)
    cache_ttl_seconds: float = Field(default=3600.0, ge=0.0, le=86400.0)
    log_level: str = Field(default="INFO")

    # Local dashboard (visualizes pipeline + context cut on localhost)
    enable_ui: bool = Field(default=True)
    ui_host: str = Field(default="127.0.0.1")
    ui_port: int = Field(default=8765, ge=1, le=65535)
    ui_open_browser: bool = Field(default=False)

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"invalid LOG_LEVEL: {value!r}")
        return upper

    @field_validator("ui_host")
    @classmethod
    def _validate_ui_host(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("UI_HOST must not be empty.")
        return value.strip()

    def require_typesafe_key(self) -> str:
        if not self.typesafe_api_key:
            raise EvidenceError(
                ErrorCode.CONFIGURATION_ERROR,
                "Missing TYPESAFE_API_KEY. Set it in your environment (see .env.example).",
            )
        return self.typesafe_api_key

    def require_search_key(self) -> str:
        if self.search_provider == "fake":
            return ""
        if not self.brave_api_key:
            raise EvidenceError(
                ErrorCode.CONFIGURATION_ERROR,
                "Missing BRAVE_API_KEY (or SEARCH_API_KEY). "
                "Set it in your environment or use SEARCH_PROVIDER=fake for offline use.",
            )
        return self.brave_api_key


def load_settings() -> Settings:
    """Build Settings from the environment; raises EvidenceError on bad values."""
    try:
        return Settings(
            typesafe_api_key=_get_env("TYPESAFE_API_KEY", "JEV_API_KEY"),
            typesafe_model=_get_env(
                "TYPESAFE_MODEL", "TYPESAFE_DEFAULT_MODEL", default="jev-latest"
            ),
            typesafe_base_url=_get_env("TYPESAFE_BASE_URL", default="https://api.typesafe.ai"),
            search_provider=_get_env("SEARCH_PROVIDER", default="brave").lower(),  # type: ignore[arg-type]
            brave_api_key=_get_env("BRAVE_API_KEY", "SEARCH_API_KEY"),
            max_search_results=_get_int("MAX_SEARCH_RESULTS", 20),
            fetch_timeout_seconds=_get_float("FETCH_TIMEOUT_SECONDS", 15.0),
            max_response_bytes=_get_int("MAX_RESPONSE_BYTES", 2_000_000),
            max_redirects=_get_int("MAX_REDIRECTS", 5),
            max_document_chars=_get_int("MAX_DOCUMENT_CHARS", 200_000),
            max_concurrent_fetches=_get_int("MAX_CONCURRENT_FETCHES", 5),
            jev_result_batch_size=_get_int("JEV_RESULT_BATCH_SIZE", 20),
            jev_block_batch_size=_get_int("JEV_BLOCK_BATCH_SIZE", 30),
            jev_max_state_chars=_get_int("JEV_MAX_STATE_CHARS", 80_000),
            jev_max_block_chars_for_state=_get_int("JEV_MAX_BLOCK_CHARS_FOR_STATE", 2_000),
            max_blocks_per_document=_get_int("MAX_BLOCKS_PER_DOCUMENT", 300),
            result_relevant_threshold=_get_float("RESULT_RELEVANT_THRESHOLD", 0.5),
            result_useful_threshold=_get_float("RESULT_USEFUL_THRESHOLD", 0.5),
            result_uncertain_margin=_get_float("RESULT_UNCERTAIN_MARGIN", 0.15),
            block_relevant_threshold=_get_float("BLOCK_RELEVANT_THRESHOLD", 0.5),
            block_actionable_threshold=_get_float("BLOCK_ACTIONABLE_THRESHOLD", 0.5),
            block_uncertain_margin=_get_float("BLOCK_UNCERTAIN_MARGIN", 0.15),
            max_evidence_tokens=_get_int("MAX_EVIDENCE_TOKENS", 8_000),
            max_sources=_get_int("MAX_SOURCES", 10),
            enable_cache=_get_bool("ENABLE_CACHE", True),
            cache_ttl_seconds=_get_float("CACHE_TTL_SECONDS", 3600.0),
            log_level=_get_env("LOG_LEVEL", default="INFO"),
            enable_ui=_get_bool("ENABLE_UI", True),
            ui_host=_get_env("UI_HOST", default="127.0.0.1"),
            ui_port=_get_int("UI_PORT", 8765),
            ui_open_browser=_get_bool("UI_OPEN_BROWSER", False),
        )
    except EvidenceError:
        raise
    except Exception as exc:  # pydantic validation errors -> configuration error
        raise EvidenceError(ErrorCode.CONFIGURATION_ERROR, f"Invalid configuration: {exc}") from exc
