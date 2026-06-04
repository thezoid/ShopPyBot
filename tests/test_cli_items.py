"""CLI-03 tests: items subcommand (list/add/remove).

All tests are skip-marked to plan 09-03 -- handle_items_* are stubs in plan 09-01.
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.skip(reason="plan 09-03")
def test_items_list_table(capsys, tmp_data_dir):
    """main(["items","list"]) prints a text table containing name and URL."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.list_items.return_value = [
        ("Widget", "https://ex.com", False, 1, False)
    ]
    with patch("core.service.BotService", return_value=mock_svc):
        main(["items", "list"])
    out = capsys.readouterr().out
    assert "Widget" in out
    assert "https://ex.com" in out


@pytest.mark.skip(reason="plan 09-03")
def test_items_add(tmp_data_dir):
    """main(["items","add",...]) calls BotService.add_item with correct args."""
    from core.service import main

    mock_svc = MagicMock()
    with patch("core.service.BotService", return_value=mock_svc):
        main(["items", "add", "--name", "Widget", "--url", "https://ex.com"])
    mock_svc.add_item.assert_called_once_with("Widget", "https://ex.com", False, 1)


@pytest.mark.skip(reason="plan 09-03")
def test_items_remove(capsys, tmp_data_dir):
    """main(["items","remove",...]) calls remove_item and prints the item name."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.list_items.return_value = [
        ("Widget", "https://ex.com", False, 1, False)
    ]
    with patch("core.service.BotService", return_value=mock_svc):
        main(["items", "remove", "--url", "https://ex.com"])
    mock_svc.remove_item.assert_called_once_with("https://ex.com")
    out = capsys.readouterr().out
    assert "Widget" in out


@pytest.mark.skip(reason="plan 09-03")
def test_items_remove_not_found(tmp_data_dir):
    """items remove with unknown URL exits with code 1."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.list_items.return_value = []
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["items", "remove", "--url", "https://missing.com"])
    assert exc_info.value.code == 1
