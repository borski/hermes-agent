"""Tests for active-session /mcp management.

Note on patching: another test in this directory (`test_cli_init`)
does `importlib.reload(cli)`, which replaces the `cli.HermesCLI`
class object mid-suite.  Capturing `HermesCLI` at module import here
would freeze a reference to the pre-reload class, while
`patch("cli.HermesCLI._reload_mcp", ...)` would later patch the
post-reload class — the instance's method lookup wouldn't see the
patch and the real `_reload_mcp` would run (and fail on missing
`agent` attribute).  Resolve `cli.HermesCLI` lazily and patch
instance methods directly to stay robust to module reloads.
"""

from unittest.mock import patch


def _make_cli():
    import cli as cli_mod
    cli_obj = cli_mod.HermesCLI.__new__(cli_mod.HermesCLI)
    cli_obj._app = None
    cli_obj._last_invalidate = 0.0
    cli_obj._command_running = False
    cli_obj._command_status = ""
    return cli_obj


class TestMcpSlashCommand:
    def test_enable_changes_config_and_reloads(self, capsys):
        cli_obj = _make_cli()

        with patch.object(
            cli_obj, "_reload_mcp"
        ) as reload_mock, patch.object(
            cli_obj, "_invalidate"
        ), patch(
            "hermes_cli.mcp_config.set_mcp_servers_enabled",
            return_value=(["alpha"], [], []),
        ):
            assert cli_obj.process_command("/mcp enable alpha")

        out = capsys.readouterr().out
        assert "Enabled 'alpha'" in out
        assert "Reloading MCP servers for this session" in out
        reload_mock.assert_called_once_with()

    def test_disable_with_no_changes_does_not_reload(self, capsys):
        cli_obj = _make_cli()

        with patch.object(
            cli_obj, "_reload_mcp"
        ) as reload_mock, patch(
            "hermes_cli.mcp_config.set_mcp_servers_enabled",
            return_value=([], ["beta"], []),
        ):
            assert cli_obj.process_command("/mcp disable beta")

        out = capsys.readouterr().out
        assert "already disabled" in out
        reload_mock.assert_not_called()

    def test_reload_reloads_active_session(self):
        cli_obj = _make_cli()

        with patch.object(
            cli_obj, "_reload_mcp"
        ) as reload_mock, patch.object(
            cli_obj, "_invalidate"
        ):
            assert cli_obj.process_command("/mcp reload")

        reload_mock.assert_called_once_with()

    def test_unknown_action_prints_usage(self, capsys):
        cli_obj = _make_cli()

        assert cli_obj.process_command("/mcp frobnicate")

        out = capsys.readouterr().out
        assert "Unknown MCP action" in out
        assert "Usage: /mcp" in out
