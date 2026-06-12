"""CLI tests: status subcommand (table / JSON / empty-state / no-network)."""

import json
import socket

import pytest
from unittest.mock import MagicMock, patch


_STATUS_PAYLOAD = {
    "running": True,
    "uptime_secs": 42.0,
    "plugins": {
        "AmazonPlugin": {
            "status": "running",
            "last_heartbeat": 100.0,
            "consecutive_errors": 0,
            "items_checked": 5,
            "orders_confirmed": 1,
        }
    },
}

_STATUS_PAYLOAD_EMPTY = {
    "running": False,
    "uptime_secs": 0.0,
    "plugins": {},
}


def test_status_table(capsys, tmp_data_dir):
    """main(["status"]) prints a text table with running header and plugin name."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.get_status.return_value = _STATUS_PAYLOAD
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["status"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "AmazonPlugin" in out
    assert "running=" in out


def test_status_json(capsys, tmp_data_dir):
    """main(["status","--json"]) exits 0 and emits parseable JSON matching the payload."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.get_status.return_value = _STATUS_PAYLOAD
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["status", "--json"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["running"] is True
    assert "AmazonPlugin" in parsed["plugins"]
    assert parsed["uptime_secs"] == 42.0


def test_status_empty(capsys, tmp_data_dir):
    """main(["status"]) with no plugin data prints the no-data fallback line and exits 0."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.get_status.return_value = _STATUS_PAYLOAD_EMPTY
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["status"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "No plugin data yet." in out


def test_status_no_network(capsys, tmp_data_dir):
    """main(["status"]) makes no socket connections (in-process state only)."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.get_status.return_value = _STATUS_PAYLOAD

    def _block_socket(*args, **kwargs):
        raise AssertionError("status must not open a socket")

    with patch("core.service.BotService", return_value=mock_svc):
        with patch.object(socket, "socket", side_effect=_block_socket):
            with pytest.raises(SystemExit) as exc_info:
                main(["status"])
    assert exc_info.value.code == 0
    mock_svc.get_status.assert_called_once()
