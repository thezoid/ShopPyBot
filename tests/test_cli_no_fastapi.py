"""CLI-04 tests: CLI works without FastAPI installed.

Tests are skip-marked to plan 09-04 -- handle_web is a stub in plan 09-01
that will gain its lazy-import body in plan 09-04.
"""

import sys

import pytest


@pytest.mark.skip(reason="plan 09-04")
def test_web_no_fastapi(monkeypatch, capsys):
    """handle_web returns 1 and prints pip hint when fastapi is absent."""
    monkeypatch.setitem(sys.modules, "fastapi", None)
    if "core.cli.web" in sys.modules:
        del sys.modules["core.cli.web"]
    from core.cli.web import handle_web

    result = handle_web(None, None)
    assert result == 1
    assert "pip install .[web]" in capsys.readouterr().err


@pytest.mark.skip(reason="plan 09-04")
def test_run_works_without_fastapi(monkeypatch, tmp_data_dir):
    """run/setup/items must not import fastapi at top level."""
    monkeypatch.setitem(sys.modules, "fastapi", None)
    from unittest.mock import MagicMock, patch

    mock_svc = MagicMock()
    mock_svc.get_config.return_value = MagicMock(
        debug=MagicMock(test_mode=True),
        available=MagicMock(items=[]),
    )
    with patch("core.service.BotService", return_value=mock_svc):
        from core.service import main

        main(["run"])
    mock_svc.run.assert_called_once()
