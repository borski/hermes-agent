"""Tests for active-session /mcp management."""

from unittest.mock import patch

from cli import HermesCLI


def _make_cli():
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj._app = None
    cli_obj._last_invalidate = 0.0
    cli_obj._command_running = False
    cli_obj._command_status = ""
    return cli_obj


class TestMcpSlashCommand:
    def test_enable_changes_config_and_reloads(self, capsys):
        cli_obj = _make_cli()

        with patch(
            "cli.HermesCLI._reload_mcp", autospec=True
        ) as reload_mock, patch(
            "cli.HermesCLI._invalidate", autospec=True
        ), patch(
            "hermes_cli.mcp_config.set_mcp_servers_enabled",
            return_value=(["alpha"], [], []),
        ):
            assert cli_obj.process_command("/mcp enable alpha")

        out = capsys.readouterr().out
        assert "Enabled 'alpha'" in out
        assert "Reloading MCP servers for this session" in out
        reload_mock.assert_called_once_with(cli_obj)

    def test_disable_with_no_changes_does_not_reload(self, capsys):
        cli_obj = _make_cli()

        with patch(
            "cli.HermesCLI._reload_mcp", autospec=True
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

        with patch(
            "cli.HermesCLI._reload_mcp", autospec=True
        ) as reload_mock, patch(
            "cli.HermesCLI._invalidate", autospec=True
        ):
            assert cli_obj.process_command("/mcp reload")

        reload_mock.assert_called_once_with(cli_obj)

    def test_unknown_action_prints_usage(self, capsys):
        cli_obj = _make_cli()

        assert cli_obj.process_command("/mcp frobnicate")

        out = capsys.readouterr().out
        assert "Unknown MCP action" in out
        assert "Usage: /mcp" in out
