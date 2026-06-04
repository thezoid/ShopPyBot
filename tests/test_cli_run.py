"""CLI-01 tests: run subcommand and bare shoppybot dispatch.

Tests that belong to this plan (09-01) are active.
Tests for other plans carry skip markers to their owning plan.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.service import main


def test_bare_defaults_to_run(tmp_data_dir):
    """main([]) -- bare invocation -- must call BotService.run() once."""
    mock_svc = MagicMock()
    mock_svc.get_config.return_value = MagicMock(
        debug=MagicMock(test_mode=True),
        available=MagicMock(items=[]),
    )
    with patch("core.service.BotService", return_value=mock_svc):
        main([])
    mock_svc.run.assert_called_once()


def test_run_subcommand_calls_botservice_run(tmp_data_dir):
    """main(["run"]) must call BotService.run() once."""
    mock_svc = MagicMock()
    mock_svc.get_config.return_value = MagicMock(
        debug=MagicMock(test_mode=True),
        available=MagicMock(items=[]),
    )
    with patch("core.service.BotService", return_value=mock_svc):
        main(["run"])
    mock_svc.run.assert_called_once()


def test_help_exits_zero():
    """main(["--help"]) must raise SystemExit(0) without starting the bot."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
