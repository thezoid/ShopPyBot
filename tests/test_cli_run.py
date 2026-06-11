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


# ---------------------------------------------------------------------------
# monitor_only flag, config mutation, CVV short-circuit, ALLOWLIST (Plan 18-03 Task 2 -- BUY-01)
# ---------------------------------------------------------------------------


def test_monitor_only_flag_parses_true():
    """run --monitor-only yields args.monitor_only is True."""
    from core.cli import build_parser

    parser = build_parser()
    args, _ = parser.parse_known_args(["run", "--monitor-only"])
    assert args.monitor_only is True


def test_monitor_only_flag_absent_is_false():
    """run without --monitor-only yields args.monitor_only is False."""
    from core.cli import build_parser

    parser = build_parser()
    args, _ = parser.parse_known_args(["run"])
    assert args.monitor_only is False


def test_handle_run_monitor_only_mutates_config(tmp_data_dir):
    """handle_run with args.monitor_only=True sets cfg.debug.monitor_only = True."""
    from unittest.mock import MagicMock
    from core.cli.run import handle_run

    cfg = MagicMock()
    cfg.debug.test_mode = True
    cfg.debug.monitor_only = False
    cfg.available.items = []

    svc = MagicMock()
    svc.get_config.return_value = cfg

    args = MagicMock()
    args.monitor_only = True

    handle_run(args, svc)
    assert cfg.debug.monitor_only is True


def test_handle_run_monitor_only_skips_cvv_prompt(tmp_data_dir):
    """handle_run with monitor_only=True skips getpass even with bestbuy auto_buy item."""
    from unittest.mock import MagicMock, patch
    from core.cli.run import handle_run
    from core.config_schema import ItemConfig

    bb_item = MagicMock()
    bb_item.link = "https://www.bestbuy.com/product/123"
    bb_item.auto_buy = True

    cfg = MagicMock()
    cfg.debug.test_mode = False
    cfg.debug.monitor_only = False
    cfg.available.items = [bb_item]

    svc = MagicMock()
    svc.get_config.return_value = cfg

    args = MagicMock()
    args.monitor_only = True

    with patch("getpass.getpass") as mock_getpass:
        handle_run(args, svc)

    mock_getpass.assert_not_called()


def test_allowlist_contains_monitor_only():
    """ALLOWLIST in config_cmd.py must contain "monitor_only": ("debug", bool)."""
    from core.cli.config_cmd import ALLOWLIST

    assert "monitor_only" in ALLOWLIST, "monitor_only must be in ALLOWLIST"
    assert ALLOWLIST["monitor_only"] == ("debug", bool)
