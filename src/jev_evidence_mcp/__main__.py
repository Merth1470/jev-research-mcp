"""CLI entrypoint: ``python -m jev_evidence_mcp`` runs the MCP server over stdio."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

_load_dotenv: Callable[..., bool] | None
try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:  # pragma: no cover - optional convenience
    _load_dotenv = None


def main() -> None:
    # Load .env for local runs (real deployments use exported variables).
    if _load_dotenv is not None:
        _load_dotenv()
    from .config import load_settings
    from .errors import EvidenceError
    from .server import _run_stdio, configure_logging, create_mcp_server

    try:
        settings = load_settings()
    except EvidenceError as exc:
        print(f"Configuration error: {exc.message}", file=sys.stderr)
        sys.exit(2)
    configure_logging(settings.log_level)
    mcp = create_mcp_server(settings)
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport != "stdio":
        print(f"Unsupported MCP_TRANSPORT={transport!r}; V1 supports stdio.", file=sys.stderr)
        sys.exit(2)
    _run_stdio(mcp)


if __name__ == "__main__":
    main()
