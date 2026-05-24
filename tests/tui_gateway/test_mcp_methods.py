"""Tests for the tui_gateway mcp.list and mcp.apply methods."""

from unittest.mock import patch

import pytest

from tui_gateway import server


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    """Redirect ``hermes_cli.config`` I/O to a temp dir for each test.

    Mirrors the pattern in tests/hermes_cli/test_mcp_config.py so module-
    level config caches in ``hermes_cli.config`` and ``hermes_cli.mcp_config``
    can never resolve to the real ``~/.hermes/config.yaml`` (which contains
    real secrets) — even if a test forgets to mock ``load_config``.

    Also pre-imports ``hermes_cli.mcp_config`` so its ``load_config`` binding
    (captured via ``from hermes_cli.config import load_config``) points at the
    real function. Without this pre-import, the first test that mocks
    ``hermes_cli.config.load_config`` *before* the ``mcp.list`` handler runs
    its deferred ``import hermes_cli.mcp_config`` poisons that binding with
    a MagicMock for the rest of the pytest run.
    """
    import hermes_cli.mcp_config  # noqa: F401 — bind load_config before any patch

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr("hermes_cli.config.get_hermes_home", lambda: tmp_path)
    monkeypatch.setattr(
        "hermes_cli.config.get_config_path", lambda: tmp_path / "config.yaml"
    )
    monkeypatch.setattr(
        "hermes_cli.config.get_env_path", lambda: tmp_path / ".env"
    )
    return tmp_path


def test_mcp_list_returns_sorted_servers_with_kind_and_state():
    cfg = {
        "mcp_servers": {
            "beta": {"command": "npx", "args": ["b"], "enabled": False},
            "alpha": {"url": "https://a.example/mcp", "enabled": True},
            "gamma": {"command": "uvx", "args": ["g"]},
        }
    }

    with patch("hermes_cli.config.load_config", return_value=cfg):
        resp = server._methods["mcp.list"](1, {})

    assert "result" in resp, resp
    rows = resp["result"]["servers"]
    assert [r["name"] for r in rows] == ["alpha", "beta", "gamma"]
    assert rows[0]["kind"] == "remote"
    assert rows[0]["enabled"] is True
    assert rows[1]["kind"] == "stdio"
    assert rows[1]["enabled"] is False
    assert rows[2]["enabled"] is True  # default-on when "enabled" missing


def test_mcp_list_with_no_servers_returns_empty_list():
    with patch("hermes_cli.config.load_config", return_value={}):
        resp = server._methods["mcp.list"](1, {})

    assert resp["result"]["servers"] == []


def test_mcp_apply_applies_enable_then_disable_then_reloads_session(monkeypatch):
    calls = []

    def fake_set(names, enabled):
        calls.append((list(names), enabled))
        return list(names), [], []

    refresh_called = {"count": 0}

    class _Agent:
        def refresh_tools(self):
            refresh_called["count"] += 1

    sid = "sess-tui"
    monkeypatch.setitem(server._sessions, sid, {"agent": _Agent()})

    try:
        with patch("hermes_cli.mcp_config._set_mcp_server_enabled", side_effect=fake_set), \
             patch("tools.mcp_tool.shutdown_mcp_servers") as shutdown_mock, \
             patch("tools.mcp_tool.discover_mcp_tools") as discover_mock, \
             patch("tui_gateway.server._emit"), \
             patch("tui_gateway.server._session_info", return_value={}):
            resp = server._methods["mcp.apply"](
                7,
                {
                    "enable": ["alpha"],
                    "disable": ["beta", "gamma"],
                    "session_id": sid,
                },
            )
    finally:
        server._sessions.pop(sid, None)

    assert "result" in resp, resp
    result = resp["result"]
    assert result["changed"] == ["alpha", "beta", "gamma"]
    assert result["reloaded"] is True
    assert calls == [(["alpha"], True), (["beta", "gamma"], False)]
    shutdown_mock.assert_called_once_with()
    discover_mock.assert_called_once_with()
    assert refresh_called["count"] == 1


def test_mcp_apply_no_changes_does_not_reload():
    with patch("hermes_cli.mcp_config._set_mcp_server_enabled", return_value=([], ["alpha"], [])), \
         patch("tools.mcp_tool.shutdown_mcp_servers") as shutdown_mock, \
         patch("tools.mcp_tool.discover_mcp_tools") as discover_mock:
        resp = server._methods["mcp.apply"](
            8,
            {"enable": ["alpha"], "disable": [], "session_id": ""},
        )

    assert resp["result"]["changed"] == []
    assert resp["result"]["unchanged"] == ["alpha"]
    assert resp["result"]["reloaded"] is False
    shutdown_mock.assert_not_called()
    discover_mock.assert_not_called()


def test_mcp_apply_reports_missing_servers():
    with patch("hermes_cli.mcp_config._set_mcp_server_enabled", return_value=([], [], ["ghost"])):
        resp = server._methods["mcp.apply"](
            9,
            {"enable": ["ghost"], "disable": [], "session_id": ""},
        )

    assert resp["result"]["missing"] == ["ghost"]
    assert resp["result"]["changed"] == []
    assert resp["result"]["reloaded"] is False
