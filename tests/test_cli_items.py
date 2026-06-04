"""CLI-03 tests: items subcommand (list/add/remove)."""

import pytest
from unittest.mock import MagicMock, patch


def test_items_list_table(capsys, tmp_data_dir):
    """main(["items","list"]) prints a text table containing name and URL."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.list_items.return_value = [
        ("Widget", "https://ex.com", False, 1, False)
    ]
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["items", "list"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "Widget" in out
    assert "https://ex.com" in out


def test_items_add(tmp_data_dir):
    """main(["items","add",...]) calls BotService.add_item with correct args."""
    from core.service import main

    mock_svc = MagicMock()
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["items", "add", "--name", "Widget", "--url", "https://ex.com"])
    assert exc_info.value.code == 0
    mock_svc.add_item.assert_called_once_with("Widget", "https://ex.com", False, 1)


def test_items_remove(capsys, tmp_data_dir):
    """main(["items","remove",...]) calls remove_item and prints the item name."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.list_items.return_value = [
        ("Widget", "https://ex.com", False, 1, False)
    ]
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["items", "remove", "--url", "https://ex.com"])
    assert exc_info.value.code == 0
    mock_svc.remove_item.assert_called_once_with("https://ex.com")
    out = capsys.readouterr().out
    assert "Widget" in out


def test_items_remove_not_found(tmp_data_dir):
    """items remove with unknown URL exits with code 1."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.list_items.return_value = []
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["items", "remove", "--url", "https://missing.com"])
    assert exc_info.value.code == 1


def test_items_no_leaf_exits_2_and_does_not_start_bot(tmp_data_dir, capsys):
    """main(["items"]) with no leaf subcommand must exit 2 and never start the bot (WR-06)."""
    from core.service import main

    mock_svc = MagicMock()
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["items"])
    assert exc_info.value.code == 2
    mock_svc.run.assert_not_called()
    mock_svc.start.assert_not_called()
