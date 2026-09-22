"""Classified errors. Every external failure maps to one of these codes.

A failed webpage must not fail the whole research request; only
configuration/authentication failures and total pipeline failures abort.
Per-page failures are collected as diagnostics on the affected source.
"""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    CONFIGURATION_ERROR = "configuration_error"
    AUTHENTICATION_ERROR = "authentication_error"
    SEARCH_ERROR = "search_error"
    FETCH_ERROR = "fetch_error"
    PARSE_ERROR = "parse_error"
    JEV_ERROR = "jev_error"
    VALIDATION_ERROR = "validation_error"
    SECURITY_REJECTION = "security_rejection"
    TIMEOUT = "timeout"
    INTERNAL_ERROR = "internal_error"


class EvidenceError(Exception):
    """Typed application error that never carries secrets."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.code.value}] {self.message}"
