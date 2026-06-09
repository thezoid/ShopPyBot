"""CLI tests: plugins subcommand (list with table/JSON/no-network; bare-plugins exit 2)."""

import json
import socket

import pytest
from unittest.mock import MagicMock, patch


_PLUGIN_ROW = {
    "name": "AmazonPlugin",
    "domain_patterns": ["amazon.com", "amazon.co.uk"],
    "difficulty": "hard",
    "requires_proxy": True,
    "requires_captcha": True,
}


def test_plugins_list_table(capsys, tmp_data_dir):
    """main(["plugins","list"]) prints a text table with name and a domain pattern."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.list_plugins.return_value = [_PLUGIN_ROW]
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["plugins", "list"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "AmazonPlugin" in out
    assert "amazon.com" in out


def test_plugins_list_json(capsys, tmp_data_dir):
    """main(["plugins","list","--json"]) exits 0 and emits parseable JSON with difficulty key."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.list_plugins.return_value = [_PLUGIN_ROW]
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["plugins", "list", "--json"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert "difficulty" in parsed[0]


def test_plugins_no_leaf_exits_2(tmp_data_dir, capsys):
    """main(["plugins"]) exits 2 and never starts the bot (WR-06 mirror for plugins)."""
    from core.service import main

    mock_svc = MagicMock()
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["plugins"])
    assert exc_info.value.code == 2
    mock_svc.run.assert_not_called()
    mock_svc.start.assert_not_called()


def test_plugins_list_empty(capsys, tmp_data_dir):
    """main(["plugins","list"]) with no plugins prints 'No plugins loaded.' and exits 0."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.list_plugins.return_value = []
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["plugins", "list"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "No plugins loaded." in out


def test_plugins_list_no_network(capsys, tmp_data_dir):
    """main(["plugins","list"]) makes no socket connections (no network call)."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.list_plugins.return_value = [_PLUGIN_ROW]

    def _block_socket(*args, **kwargs):
        raise AssertionError("plugins list must not open a socket")

    with patch("core.service.BotService", return_value=mock_svc):
        with patch.object(socket, "socket", side_effect=_block_socket):
            with pytest.raises(SystemExit) as exc_info:
                main(["plugins", "list"])
    assert exc_info.value.code == 0
