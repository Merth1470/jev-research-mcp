"""Dashboard: config defaults, status/demo/research endpoints, index page."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from typing import Any

import pytest

from jev_evidence_mcp.config import Settings, load_settings
from jev_evidence_mcp.dashboard import create_server


def _url(server: ThreadingHTTPServer, path: str) -> str:
    host, port = server.server_address[:2]
    return f"http://{str(host)}:{int(port)}{path}"


def _get(server: ThreadingHTTPServer, path: str) -> tuple[int, str]:
    with urllib.request.urlopen(_url(server, path), timeout=30) as resp:  # noqa: S310
        return resp.status, resp.read().decode("utf-8")


def _post(server: ThreadingHTTPServer, path: str, payload: dict[str, Any]) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310 -- test hits local ephemeral server only
        _url(server, path), data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


@pytest.fixture
def server() -> Iterator[ThreadingHTTPServer]:
    srv = create_server("127.0.0.1", 0, Settings(search_provider="fake"))  # type: ignore[arg-type]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        thread.join(timeout=5)
        srv.server_close()


def test_ui_defaults(clean_env: None) -> None:
    settings = load_settings()
    assert settings.enable_ui is True
    assert settings.ui_host == "127.0.0.1"
    assert settings.ui_port == 8765
    assert settings.ui_open_browser is False


def test_ui_env_override(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("ENABLE_UI", "false")
    monkeypatch.setenv("UI_PORT", "8899")
    settings = load_settings()
    assert settings.enable_ui is False
    assert settings.ui_port == 8899


def test_status_reports_demo_without_keys(server: ThreadingHTTPServer) -> None:
    status, body = _get(server, "/api/status")
    assert status == 200
    data = json.loads(body)
    assert data["search_provider"] == "fake"
    assert data["demo_mode"] is True  # no JEV key -> demo
    assert data["max_sources"] > 0


def test_index_serves_html(server: ThreadingHTTPServer) -> None:
    status, body = _get(server, "/")
    assert status == 200
    assert "JEV Evidence MCP" in body
    assert "api/research" in body


def test_demo_returns_baseline_and_jev(server: ThreadingHTTPServer) -> None:
    status, body = _get(server, "/api/demo")
    assert status == 200
    data = json.loads(body)
    assert "baseline" in data and "jev" in data
    assert data["jev"]["fetched"] <= data["baseline"]["fetched"]
    assert "context_reduction" in data


def test_research_offline_returns_funnel_metadata(server: ThreadingHTTPServer) -> None:
    payload = {"query": "bound concurrent fetches?", "mode": "jev"}
    status, data = _post(server, "/api/research", payload)
    assert status == 200
    assert "error" not in data
    assert data["demo_mode"] is True
    meta = data["metadata"]
    assert meta["search_results"] > 0
    assert meta["blocks_seen"] >= meta["blocks_selected"]
    assert len(data["sources"]) > 0


def test_research_rejects_bad_mode(server: ThreadingHTTPServer) -> None:
    status, data = _post(server, "/api/research", {"query": "q", "mode": "telepathy"})
    assert status == 400
    assert data["error"]["code"] == "validation_error"
