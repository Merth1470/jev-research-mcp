"""Local visualization dashboard for the JEV evidence pipeline.

Stdlib-only (no new dependencies): a small ``ThreadingHTTPServer`` that serves
a single static page (``ui/index.html``) plus three JSON endpoints:

- ``GET /api/status`` — config snapshot + whether live keys are present.
- ``GET /api/demo`` — offline baseline-vs-JEV comparison on bundled fixtures.
- ``POST /api/research`` — run the real pipeline (or the offline demo stack
  when keys are missing) and return sources + metadata + an optional
  baseline comparison so the UI can draw the "context cut" funnel.

The dashboard is started in a daemon thread by ``__main__`` so
``python -m jev_evidence_mcp`` serves both MCP-over-stdio (stdout) and the
dashboard (localhost HTTP). All dashboard logs go to stderr / logging so
stdout stays clean for the MCP protocol.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

logger = logging.getLogger("jev_evidence_mcp.dashboard")

_UI_DIR = Path(__file__).parent / "ui"
_INDEX = _UI_DIR / "index.html"

_FALLBACK_HTML = """<!doctype html><title>JEV dashboard</title>
<h1>JEV Evidence MCP</h1><p>Static UI file missing; API live at /api/status.</p>
"""


def _load_index() -> str:
    try:
        return _INDEX.read_text(encoding="utf-8")
    except OSError:
        return _FALLBACK_HTML


# Editable-via-UI settings (field -> env var). Secrets are handled separately
# below and are never returned by any endpoint.
_CONFIG_FIELDS: dict[str, str] = {
    "search_provider": "SEARCH_PROVIDER",
    "typesafe_model": "TYPESAFE_MODEL",
    "max_search_results": "MAX_SEARCH_RESULTS",
    "max_sources": "MAX_SOURCES",
    "max_evidence_tokens": "MAX_EVIDENCE_TOKENS",
    "max_concurrent_fetches": "MAX_CONCURRENT_FETCHES",
    "result_relevant_threshold": "RESULT_RELEVANT_THRESHOLD",
    "result_useful_threshold": "RESULT_USEFUL_THRESHOLD",
    "result_uncertain_margin": "RESULT_UNCERTAIN_MARGIN",
    "block_relevant_threshold": "BLOCK_RELEVANT_THRESHOLD",
    "block_actionable_threshold": "BLOCK_ACTIONABLE_THRESHOLD",
    "block_uncertain_margin": "BLOCK_UNCERTAIN_MARGIN",
}
_KEY_FIELDS: dict[str, str] = {
    "brave_api_key": "BRAVE_API_KEY",
    "typesafe_api_key": "TYPESAFE_API_KEY",
}


def _public_config(settings: Any) -> dict[str, Any]:
    """Config snapshot safe for the browser: booleans for secrets, never values."""
    has_jev = bool(settings.typesafe_api_key)
    has_search = settings.search_provider == "fake" or bool(settings.brave_api_key)
    return {
        "search_provider": settings.search_provider,
        "typesafe_model": settings.typesafe_model,
        "brave_configured": bool(settings.brave_api_key),
        "typesafe_configured": has_jev,
        "demo_mode": not (has_search and has_jev),
        "max_search_results": settings.max_search_results,
        "max_sources": settings.max_sources,
        "max_evidence_tokens": settings.max_evidence_tokens,
        "max_concurrent_fetches": settings.max_concurrent_fetches,
        "result_relevant_threshold": settings.result_relevant_threshold,
        "result_useful_threshold": settings.result_useful_threshold,
        "result_uncertain_margin": settings.result_uncertain_margin,
        "block_relevant_threshold": settings.block_relevant_threshold,
        "block_actionable_threshold": settings.block_actionable_threshold,
        "block_uncertain_margin": settings.block_uncertain_margin,
    }


def _persist_env_file(env_path: Path, entries: dict[str, str]) -> bool:
    """Upsert entries into a .env file, preserving comments and other lines."""
    try:
        lines: list[str] = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
        seen: set[str] = set()
        out: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                out.append(line)
                continue
            key = line.split("=", 1)[0].strip()
            if key in entries:
                out.append(f"{key}={entries[key]}")
                seen.add(key)
            else:
                out.append(line)
        for key, value in entries.items():
            if key not in seen:
                out.append(f"{key}={value}")
        env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
        return True
    except OSError as exc:
        logger.warning("could not persist config to %s: %s", env_path, exc)
        return False


def _demo_scores() -> dict[tuple[str, str], float]:
    """Fake JEV scores mirroring benchmark fixtures: every 3rd doc is noise."""
    scores: dict[tuple[str, str], float] = {}
    for i in range(12):
        relevant = (i % 3) != 1
        for prop in ("relevant", "useful", "authoritative"):
            scores[(f"r{i}", prop)] = 0.92 if relevant else 0.08
    return scores


def _resolve_pipeline(settings: Any, mode: str) -> tuple[Any, bool]:
    """Return (pipeline, demo_mode). Demo stack when live keys are missing."""
    has_jev_key = bool(getattr(settings, "typesafe_api_key", ""))
    provider = getattr(settings, "search_provider", "brave")
    has_search = provider == "fake" or bool(getattr(settings, "brave_api_key", ""))
    if has_search and (mode == "baseline" or has_jev_key):
        from .server import build_pipeline

        return build_pipeline(settings), False
    from .benchmark.bench import build_offline_stack

    pipe, _, _, _ = build_offline_stack(settings, jev_scores=_demo_scores())
    return pipe, True


def _run_research(
    settings: Any,
    query: str,
    max_sources: int | None,
    max_tokens: int | None,
    mode: str,
) -> dict[str, Any]:
    pipe, demo = _resolve_pipeline(settings, mode)
    kwargs: dict[str, Any] = {
        "max_sources": max_sources,
        "max_evidence_tokens": max_tokens,
        "mode": mode,
    }
    result = asyncio.run(pipe.run(query, **kwargs))
    payload: dict[str, Any] = result.model_dump()
    payload["demo_mode"] = demo
    # For jev runs, also run baseline once (cached fetches make it cheap) so
    # the UI can show tokens-before vs tokens-after.
    if mode == "jev" and not demo:
        try:
            base_kwargs = dict(kwargs, mode="baseline")
            base = asyncio.run(pipe.run(query, **base_kwargs))
            b_tok = base.metadata.estimated_input_tokens
            j_tok = result.metadata.estimated_input_tokens
            reduction = round((b_tok - j_tok) / b_tok, 3) if b_tok else 0.0
            payload["comparison"] = {
                "baseline_tokens": b_tok,
                "jev_tokens": j_tok,
                "context_reduction": reduction,
                "baseline_fetched": base.metadata.documents_fetched,
                "jev_fetched": result.metadata.documents_fetched,
            }
        except Exception as exc:  # comparison is best-effort only
            logger.debug("baseline comparison failed: %s", exc)
    return payload


class _Handler(BaseHTTPRequestHandler):
    server_version = "JevDashboard/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        logger.debug("%s - %s", self.address_string(), fmt % args)

    def _send_json(self, obj: Any, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _not_found(self, path: str) -> None:
        msg = f"Unknown path {path}"
        self._send_json({"error": {"code": "not_found", "message": msg}}, 404)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send_html(_load_index())
            return
        if path == "/api/status":
            self._handle_status()
            return
        if path == "/api/demo":
            self._handle_demo()
            return
        if path == "/api/config":
            self._handle_config()
            return
        self._not_found(path)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/config":
            length = int(self.headers.get("Content-Length") or 0)
            if length > 65536:
                err = {"error": {"code": "validation_error", "message": "Body too large."}}
                self._send_json(err, 400)
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError):
                err = {"error": {"code": "validation_error", "message": "Invalid JSON."}}
                self._send_json(err, 400)
                return
            self._handle_config_update(data if isinstance(data, dict) else {})
            return
        if path != "/api/research":
            self._not_found(path)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > 65536:
            err = {"error": {"code": "validation_error", "message": "Body too large."}}
            self._send_json(err, 400)
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            err = {"error": {"code": "validation_error", "message": "Invalid JSON."}}
            self._send_json(err, 400)
            return
        self._handle_research(data if isinstance(data, dict) else {})

    def _settings(self) -> Any:
        server_settings = getattr(self.server, "jev_settings", None)
        if server_settings is not None:
            return server_settings
        from .config import load_settings

        return load_settings()

    def _handle_status(self) -> None:
        from . import __version__

        try:
            settings = self._settings()
        except Exception as exc:
            err = {"error": {"code": "configuration_error", "message": str(exc)}}
            self._send_json(err, 500)
            return
        has_jev = bool(settings.typesafe_api_key)
        has_search = settings.search_provider == "fake" or bool(settings.brave_api_key)
        res_t = f"{settings.result_relevant_threshold}/{settings.result_useful_threshold}"
        blk_t = f"{settings.block_relevant_threshold}/{settings.block_actionable_threshold}"
        self._send_json(
            {
                "version": __version__,
                "search_provider": settings.search_provider,
                "jev_configured": has_jev,
                "search_configured": has_search,
                "demo_mode": not (has_search and has_jev),
                "result_threshold": res_t,
                "block_threshold": blk_t,
                "max_sources": settings.max_sources,
                "max_evidence_tokens": settings.max_evidence_tokens,
            }
        )

    def _handle_config(self) -> None:
        try:
            self._send_json(_public_config(self._settings()))
        except Exception as exc:
            err = {"error": {"code": "configuration_error", "message": str(exc)}}
            self._send_json(err, 500)

    def _handle_config_update(self, data: dict[str, Any]) -> None:
        from pydantic import ValidationError

        from .config import Settings

        settings = self._settings()
        updates: dict[str, Any] = {}
        for field in _CONFIG_FIELDS:
            if field in data and data[field] is not None and data[field] != "":
                updates[field] = data[field]
        key_updates: dict[str, str] = {}
        for field in _KEY_FIELDS:
            value = data.get(field)
            # Empty key fields mean "leave unchanged" (keys are never displayed,
            # so the browser cannot send them back); only non-empty values apply.
            if isinstance(value, str) and value.strip():
                key_updates[field] = value.strip()
        if not updates and not key_updates:
            err = {"error": {"code": "validation_error", "message": "No fields provided."}}
            self._send_json(err, 400)
            return
        try:
            merged: dict[str, Any] = settings.model_dump()
            merged.update(updates)
            merged.update(key_updates)
            validated = Settings(**merged)
        except ValidationError as exc:
            # Field names + messages only; never echo values (may be secrets).
            details = "; ".join(
                ".".join(str(part) for part in item.get("loc", ())) + ": " + item.get("msg", "")
                for item in exc.errors()
            )
            err = {"error": {"code": "configuration_error", "message": f"Invalid: {details}"}}
            self._send_json(err, 400)
            return
        except Exception as exc:
            err = {"error": {"code": "configuration_error", "message": f"Invalid: {exc}"}}
            self._send_json(err, 400)
            return
        entries: dict[str, str] = {}
        for field in updates:
            canonical = getattr(validated, field)
            os.environ[_CONFIG_FIELDS[field]] = str(canonical)
            setattr(settings, field, canonical)
            entries[_CONFIG_FIELDS[field]] = str(canonical)
        for field, value in key_updates.items():
            os.environ[_KEY_FIELDS[field]] = value
            setattr(settings, field, value)
            entries[_KEY_FIELDS[field]] = value
        env_path = getattr(self.server, "jev_env_path", None) or (Path.cwd() / ".env")
        persisted = _persist_env_file(Path(env_path), entries)
        self._send_json(
            {
                "ok": True,
                "config": _public_config(settings),
                "persisted": persisted,
                "message": "Updated. Applies immediately; saved to .env."
                if persisted
                else "Updated for this session; .env write failed (see logs).",
            }
        )

    def _handle_demo(self) -> None:
        try:
            from .benchmark.bench import compare
            from .config import Settings

            settings = Settings(search_provider="fake")  # type: ignore[arg-type]
            report = asyncio.run(compare("How do I bound concurrent fetches?", settings))
            self._send_json(report)
        except Exception as exc:
            logger.warning("demo failed: %s", exc)
            err = {"error": {"code": "internal_error", "message": str(exc)}}
            self._send_json(err, 500)

    def _handle_research(self, data: dict[str, Any]) -> None:
        query = str(data.get("query", "") or "")
        mode = str(data.get("mode", "jev") or "jev")
        if mode not in ("jev", "baseline"):
            err = {"error": {"code": "validation_error", "message": "Use 'jev'/'baseline'."}}
            self._send_json(err, 400)
            return
        try:
            max_sources = data.get("max_sources")
            max_tokens = data.get("max_evidence_tokens")
            payload = _run_research(
                self._settings(),
                query,
                int(max_sources) if max_sources is not None else None,
                int(max_tokens) if max_tokens is not None else None,
                mode,
            )
        except Exception as exc:
            from .errors import EvidenceError

            if isinstance(exc, EvidenceError):
                self._send_json(
                    {
                        "query": query,
                        "sources": [],
                        "metadata": {},
                        "error": {"code": exc.code.value, "message": exc.message},
                    }
                )
                return
            logger.exception("research failed")
            self._send_json(
                {
                    "query": query,
                    "sources": [],
                    "metadata": {},
                    "error": {"code": "internal_error", "message": str(exc)},
                },
                500,
            )
            return
        self._send_json(payload)


def create_server(
    host: str, port: int, settings: Any, *, env_path: Path | str | None = None
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), _Handler)
    server.daemon_threads = True
    server.jev_settings = settings  # type: ignore[attr-defined]
    server.jev_env_path = Path(env_path) if env_path is not None else None  # type: ignore[attr-defined]
    return server


def start_dashboard_in_background(
    settings: Any,
) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    """Start dashboard on settings.ui_host/ui_port; return (server, thread, url)."""
    host = getattr(settings, "ui_host", "127.0.0.1")
    port = int(getattr(settings, "ui_port", 8765))
    server = create_server(host, port, settings)
    thread = threading.Thread(target=server.serve_forever, name="jev-dashboard", daemon=True)
    thread.start()
    loopback = ("127.0.0.1", "0.0.0.0", "::")  # noqa: S104 -- display only, not a bind
    display_host = "localhost" if host in loopback else host
    url = f"http://{display_host}:{server.server_address[1]}"
    print(f"JEV dashboard at {url}", file=sys.stderr)
    logger.info("dashboard listening at %s", url)
    return server, thread, url
