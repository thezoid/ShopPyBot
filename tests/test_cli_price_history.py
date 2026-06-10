"""CLI price-history subcommand tests (PRICE-06).

Tests: stdout table format, --limit, no-item message, no network call.
"""

import pytest
from unittest.mock import MagicMock, patch


def test_cli_price_history(capsys, tmp_data_dir):
    """main(["items","price-history","Widget"]) with one history row exits 0.

    Stdout must contain the formatted price ($49.99), currency (USD), and
    the recorded-at timestamp.
    """
    from core.service import main

    recorded_at = "2026-06-09T12:00:00+00:00"
    mock_svc = MagicMock()
    mock_svc.get_price_history.return_value = [(4999, "USD", recorded_at)]
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["items", "price-history", "Widget"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "$49.99" in out
    assert "USD" in out
    assert recorded_at in out


def test_cli_price_history_no_item(capsys, tmp_data_dir):
    """Unknown item name (empty history) prints a no-history message and exits 0."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.get_price_history.return_value = []
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["items", "price-history", "UnknownItem"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "UnknownItem" in out
    # Must contain a meaningful no-history indicator (not just silence)
    assert len(out.strip()) > 0


def test_cli_price_history_limit(tmp_data_dir):
    """--limit N passes limit=N to BotService.get_price_history."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.get_price_history.return_value = [
        (100, "USD", "2026-06-09T10:00:00+00:00"),
        (200, "USD", "2026-06-09T11:00:00+00:00"),
        (300, "USD", "2026-06-09T12:00:00+00:00"),
    ]
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["items", "price-history", "Widget", "--limit", "3"])
    assert exc_info.value.code == 0
    mock_svc.get_price_history.assert_called_once_with("Widget", 3)


def test_cli_price_history_no_network(tmp_data_dir):
    """Handler calls only BotService.get_price_history -- no network/registry side-effects."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.get_price_history.return_value = []
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["items", "price-history", "Widget"])
    assert exc_info.value.code == 0
    # Only get_price_history must have been called on the service mock.
    # run/start/stop imply network/browser activity and must not be called.
    mock_svc.run.assert_not_called()
    mock_svc.start.assert_not_called()
    mock_svc.get_price_history.assert_called_once()
