"""Configuration: env parsing, bounds, missing-secret errors."""

from __future__ import annotations

import pytest

from jev_evidence_mcp.config import Settings, load_settings
from jev_evidence_mcp.errors import ErrorCode, EvidenceError


def test_defaults_are_safe(clean_env: None) -> None:
    settings = load_settings()
    assert settings.max_search_results == 20
    assert settings.max_sources == 10
    assert settings.max_evidence_tokens == 8_000
    assert settings.fetch_timeout_seconds == 15.0
    assert settings.max_concurrent_fetches == 5


def test_env_override(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("MAX_SEARCH_RESULTS", "7")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    settings = load_settings()
    assert settings.max_search_results == 7
    assert settings.log_level == "DEBUG"


def test_invalid_number_is_configuration_error(
    monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    monkeypatch.setenv("MAX_SEARCH_RESULTS", "banana")
    with pytest.raises(EvidenceError) as exc_info:
        load_settings()
    assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR


def test_pathological_values_rejected_by_bounds(
    monkeypatch: pytest.MonkeyPatch, clean_env: None
) -> None:
    monkeypatch.setenv("MAX_SEARCH_RESULTS", "1000000")
    with pytest.raises(EvidenceError) as exc_info:
        load_settings()
    assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR


def test_unknown_search_provider_wrapped(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SEARCH_PROVIDER", "bogus")
    with pytest.raises(EvidenceError) as exc_info:
        load_settings()
    assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR


def test_missing_typesafe_key_error_names_variable(clean_env: None) -> None:
    settings = load_settings()
    with pytest.raises(EvidenceError) as exc_info:
        settings.require_typesafe_key()
    assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR
    assert "TYPESAFE_API_KEY" in exc_info.value.message
    assert "sk-" not in exc_info.value.message  # never echo secrets


def test_jev_alias_key_accepted(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    assert load_settings().require_typesafe_key() == "test-key"


def test_search_key_required_for_brave(clean_env: None) -> None:
    settings = load_settings()
    assert settings.search_provider == "brave"
    with pytest.raises(EvidenceError) as exc_info:
        settings.require_search_key()
    assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR


def test_search_key_never_echoed_in_error(clean_env: None) -> None:
    settings = load_settings()
    with pytest.raises(EvidenceError) as exc_info:
        settings.require_search_key()
    assert "BRAVE_API_KEY" in exc_info.value.message


def test_thresholds_must_be_probabilities(clean_env: None) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(result_relevant_threshold=1.5)
