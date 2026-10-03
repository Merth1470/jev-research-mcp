"""Dashboard: config defaults, status/research/config endpoints, index page.

Live-data only: without API keys the dashboard reports not-ready and the
research endpoint returns a structured configuration error. Nothing here
serves fabricated results.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from jev_research_mcp.config import Settings, load_settings
from jev_research_mcp.dashboard import create_server

_CONFIG_ENV_VARS = (
    "SEARCH_PROVIDER",
    "BRAVE_API_KEY",
    "SEARCH_API_KEY",
    "TYPESAFE_API_KEY",
    "JEV_API_KEY",
    "TYPESAFE_MODEL",
    "MAX_SEARCH_RESULTS",
    "MAX_SOURCES",
    "MAX_EVIDENCE_TOKENS",
    "MAX_CONCURRENT_FETCHES",
    "RESULT_RELEVANT_THRESHOLD",
    "RESULT_USEFUL_THRESHOLD",
    "RESULT_UNCERTAIN_MARGIN",
    "BLOCK_RELEVANT_THRESHOLD",
    "BLOCK_ACTIONABLE_THRESHOLD",
    "BLOCK_UNCERTAIN_MARGIN",
)


@pytest.fixture(autouse=True)
def _isolate_env() -> Iterator[None]:
    saved = {key: os.environ.get(key) for key in _CONFIG_ENV_VARS}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def _serve(settings: Settings, env_path: Path) -> Iterator[ThreadingHTTPServer]:
    srv = create_server("127.0.0.1", 0, settings, env_path=env_path)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        thread.join(timeout=5)
        srv.server_close()


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
def server(tmp_path: Path) -> Iterator[ThreadingHTTPServer]:
    with _serve(Settings(), tmp_path / "test.env") as srv:
        yield srv


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


def test_status_reports_not_ready_without_keys(server: ThreadingHTTPServer) -> None:
    status, body = _get(server, "/api/status")
    assert status == 200
    data = json.loads(body)
    assert data["search_provider"] == "brave"
    assert data["ready"] is False
    assert "demo_mode" not in data
    assert data["max_sources"] > 0


def test_status_reports_ready_with_keys(tmp_path: Path) -> None:
    settings = Settings(brave_api_key="k-brave", typesafe_api_key="k-jev")
    with _serve(settings, tmp_path / "test.env") as srv:
        _, body = _get(srv, "/api/status")
        assert json.loads(body)["ready"] is True


def test_index_serves_html(server: ThreadingHTTPServer) -> None:
    status, body = _get(server, "/")
    assert status == 200
    assert "JEV Research MCP" in body
    assert "api/research" in body
    assert "demo" not in body.lower()  # live data only, no placeholder content


def test_removed_demo_endpoint_stays_gone(server: ThreadingHTTPServer) -> None:
    try:
        _get(server, "/api/demo")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
    else:  # pragma: no cover
        raise AssertionError("expected 404 for /api/demo")


def test_research_without_keys_returns_configuration_error(
    server: ThreadingHTTPServer,
) -> None:
    payload = {"query": "bound concurrent fetches?", "mode": "jev"}
    status, data = _post(server, "/api/research", payload)
    assert status == 200
    assert data["sources"] == []
    assert data["error"]["code"] == "configuration_error"
    assert "demo_mode" not in data


def test_research_rejects_bad_mode(server: ThreadingHTTPServer) -> None:
    status, data = _post(server, "/api/research", {"query": "q", "mode": "telepathy"})
    assert status == 400
    assert data["error"]["code"] == "validation_error"


def test_config_get_hides_secret_values(tmp_path: Path) -> None:
    settings = Settings(brave_api_key="super-secret-brave", typesafe_api_key="super-secret-jev")
    with _serve(settings, tmp_path / "test.env") as srv:
        status, body = _get(srv, "/api/config")
        assert status == 200
        assert "super-secret-brave" not in body
        assert "super-secret-jev" not in body
        data = json.loads(body)
        assert "brave_api_key" not in data
        assert "typesafe_api_key" not in data
        assert data["brave_configured"] is True
        assert data["typesafe_configured"] is True
        assert data["ready"] is True


def test_config_post_updates_and_persists(tmp_path: Path) -> None:
    env_file = tmp_path / "test.env"
    with _serve(Settings(), env_file) as srv:
        status, data = _post(
            srv,
            "/api/config",
            {"max_sources": 4, "result_relevant_threshold": 0.7, "typesafe_api_key": "k-test"},
        )
        assert status == 200
        assert data["ok"] is True
        assert data["persisted"] is True
        assert data["config"]["max_sources"] == 4
        assert data["config"]["result_relevant_threshold"] == 0.7
        assert data["config"]["typesafe_configured"] is True
        # Live in-memory + process env, and persisted to the .env file.
        assert os.environ.get("MAX_SOURCES") == "4"
        assert os.environ.get("TYPESAFE_API_KEY") == "k-test"
        saved = env_file.read_text(encoding="utf-8")
        assert "MAX_SOURCES=4" in saved
        assert "TYPESAFE_API_KEY=k-test" in saved
        assert "k-test" not in json.dumps(data["config"])


def test_config_post_rejects_unknown_provider(tmp_path: Path) -> None:
    with _serve(Settings(), tmp_path / "test.env") as srv:
        status, data = _post(srv, "/api/config", {"search_provider": "fake"})
        assert status == 400
        assert data["error"]["code"] == "configuration_error"


def test_config_post_rejects_invalid_unchanged(tmp_path: Path) -> None:
    with _serve(Settings(), tmp_path / "test.env") as srv:
        status, data = _post(srv, "/api/config", {"result_relevant_threshold": 5})
        assert status == 400
        assert data["error"]["code"] == "configuration_error"
        _, body = _get(srv, "/api/config")
        assert json.loads(body)["result_relevant_threshold"] == 0.5


def test_config_post_blank_keys_keep_existing(tmp_path: Path) -> None:
    settings = Settings(brave_api_key="keep-me")
    with _serve(settings, tmp_path / "test.env") as srv:
        status, data = _post(srv, "/api/config", {"max_sources": 7, "brave_api_key": "   "})
        assert status == 200
        assert data["config"]["max_sources"] == 7
        assert data["config"]["brave_configured"] is True
        assert os.environ.get("BRAVE_API_KEY") is None  # untouched, not wiped
