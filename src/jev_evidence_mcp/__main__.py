"""CLI entrypoint: ``python -m jev_evidence_mcp`` runs MCP-over-stdio + local dashboard."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence

_load_dotenv: Callable[..., bool] | None
try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:  # pragma: no cover - optional convenience
    _load_dotenv = None


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    desc = "JEV Evidence MCP server + local dashboard."
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument("--no-ui", action="store_true", help="Disable localhost dashboard.")
    parser.add_argument("--ui-host", default=None, help="Dashboard host (default UI_HOST).")
    parser.add_argument("--ui-port", type=int, default=None, help="Dashboard port (UI_PORT).")
    parser.add_argument("--open-browser", action="store_true", help="Open dashboard in browser.")
    parser.add_argument(
        "--ui-only",
        action="store_true",
        help="Run only the dashboard (no MCP stdio); useful for previewing the UI.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    # Load .env for local runs (real deployments use exported variables).
    if _load_dotenv is not None:
        _load_dotenv()
    from .config import load_settings
    from .errors import EvidenceError
    from .server import _run_stdio, configure_logging, create_mcp_server

    args = _parse_args(argv)
    try:
        settings = load_settings()
    except EvidenceError as exc:
        # Start anyway on safe defaults; the user can fix config via env or
        # the dashboard UI. Missing/invalid keys become structured tool
        # errors instead of a startup crash.
        print(f"Configuration warning: {exc.message}", file=sys.stderr)
        print("Starting with safe defaults; configure via env or the dashboard.", file=sys.stderr)
        from .config import Settings

        settings = Settings()
    if args.no_ui:
        settings.enable_ui = False
    if args.ui_host:
        settings.ui_host = args.ui_host
    if args.ui_port:
        settings.ui_port = args.ui_port
    if args.open_browser:
        settings.ui_open_browser = True
    configure_logging(settings.log_level)

    dashboard_server = None
    dashboard_url = ""
    if settings.enable_ui:
        try:
            from .dashboard import start_dashboard_in_background

            dashboard_server, _, dashboard_url = start_dashboard_in_background(settings)
            if settings.ui_open_browser and dashboard_url:
                try:
                    import logging
                    import webbrowser

                    webbrowser.open(dashboard_url)
                except Exception as exc:  # never crash the server over a browser
                    logging.getLogger("jev_evidence_mcp").debug("open browser failed: %s", exc)
        except OSError as exc:
            print(f"Dashboard unavailable (port in use?): {exc}", file=sys.stderr)
        except Exception as exc:  # dashboard must never kill the MCP server
            print(f"Dashboard failed to start: {exc}", file=sys.stderr)

    if args.ui_only:
        if dashboard_server is None:
            print("UI-only mode requested but the dashboard failed to start.", file=sys.stderr)
            sys.exit(2)
        try:
            dashboard_server.serve_forever()
        except KeyboardInterrupt:
            pass
        return

    mcp = create_mcp_server(settings)
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport != "stdio":
        print(f"Unsupported MCP_TRANSPORT={transport!r}; V1 supports stdio.", file=sys.stderr)
        sys.exit(2)
    _run_stdio(mcp)


if __name__ == "__main__":
    main()
