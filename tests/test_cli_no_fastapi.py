"""CLI-04 tests: CLI works without FastAPI installed."""

import sys

import pytest


def test_web_no_fastapi(monkeypatch, capsys):
    """handle_web returns 1 and prints pip hint when fastapi is absent."""
    monkeypatch.setitem(sys.modules, "fastapi", None)
    # Purge any cached web/* and core.cli.web modules so the lazy
    # `from web import create_app` actually re-imports and hits the fastapi=None
    # ImportError. An earlier web-importing test (e.g. test_api_observability)
    # may have cached `web` in sys.modules; without this purge the cached module
    # is reused and the ImportError guard never fires. monkeypatch.delitem
    # auto-restores the original entries after the test (no cross-test leakage).
    for name in list(sys.modules):
        if name == "web" or name.startswith("web.") or name == "core.cli.web":
            monkeypatch.delitem(sys.modules, name, raising=False)
    from core.cli.web import handle_web

    result = handle_web(None, None)
    assert result == 1
    assert "pip install .[web]" in capsys.readouterr().err


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

        with pytest.raises(SystemExit) as exc_info:
            main(["run"])
        assert exc_info.value.code == 0
    mock_svc.run.assert_called_once()
