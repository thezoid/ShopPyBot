"""CLI-01 tests: run subcommand and bare shoppybot dispatch.

Tests that belong to this plan (09-01) are active.
Tests for other plans carry skip markers to their owning plan.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.service import main


def test_bare_defaults_to_run(tmp_data_dir):
    """main([]) -- bare invocation -- must call BotService.run() once and exit 0."""
    mock_svc = MagicMock()
    mock_svc.get_config.return_value = MagicMock(
        debug=MagicMock(test_mode=True),
        available=MagicMock(items=[]),
    )
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main([])
    assert exc_info.value.code == 0
    mock_svc.run.assert_called_once()


def test_bare_invocation_propagates_nonzero_exit(tmp_data_dir):
    """main([]) must propagate non-zero exit code from handle_run (CR-01).

    When handle_run returns 1 (e.g. CVV gate failure), bare shoppybot must
    exit with code 1, not 0.
    """
    mock_svc = MagicMock()
    mock_svc.get_config.return_value = MagicMock(
        debug=MagicMock(test_mode=True),
        available=MagicMock(items=[]),
    )
    with patch("core.service.BotService", return_value=mock_svc):
        with patch("core.cli.run.handle_run", return_value=1) as mock_run:
            with pytest.raises(SystemExit) as exc_info:
                main([])
    assert exc_info.value.code == 1
    mock_run.assert_called_once()


def test_run_subcommand_calls_botservice_run(tmp_data_dir):
    """main(["run"]) must call BotService.run() once.

    The explicit 'run' subcommand dispatches through sys.exit(0) on success,
    so we catch SystemExit(0) and verify run was still called.
    """
    mock_svc = MagicMock()
    mock_svc.get_config.return_value = MagicMock(
        debug=MagicMock(test_mode=True),
        available=MagicMock(items=[]),
    )
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["run"])
    assert exc_info.value.code == 0
    mock_svc.run.assert_called_once()


def test_help_exits_zero():
    """main(["--help"]) must raise SystemExit(0) without starting the bot."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
