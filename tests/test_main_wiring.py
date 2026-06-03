"""Tests for main.py wiring to core.orchestrator.async_main.

Covers:
- main.async_main is core.orchestrator.async_main (not a local definition)
- main() calls asyncio.run with async_main coroutine
- CVV gate: collect_cvv() skipped in test_mode (WR-02)
- CVV gate: collect_cvv() skipped when test_mode=True even with BestBuy auto_buy item
- CVV gate: collect_cvv() called when test_mode=False and BestBuy auto_buy item exists
- AppConfig ValidationError -> SystemExit(1) (CORE-05)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_cfg(test_mode=True, bb_items=None):
    """Return a MagicMock AppConfig with the given settings."""
    items = []
    for link, auto_buy in (bb_items or []):
        item = MagicMock()
        item.link = link
        item.auto_buy = auto_buy
        item.name = "Item"
        item.quantity = 1
        items.append(item)

    cfg = MagicMock()
    cfg.debug.test_mode = test_mode
    cfg.available.items = items
    return cfg


# ---------------------------------------------------------------------------
# Delegation: main.async_main IS core.orchestrator.async_main
# ---------------------------------------------------------------------------


def test_main_async_main_is_orchestrator():
    """main.async_main must be the imported core.orchestrator.async_main, not a local fn."""
    import main as main_module
    import core.orchestrator as orch_module

    assert main_module.async_main is orch_module.async_main, (
        "main.async_main must be core.orchestrator.async_main (delegation seam)"
    )


# ---------------------------------------------------------------------------
# Delegation: asyncio.run is called with async_main coroutine
# ---------------------------------------------------------------------------


def test_main_calls_asyncio_run():
    """main() calls asyncio.run(); the argument is a coroutine from async_main."""
    import importlib
    import main as main_module
    importlib.reload(main_module)

    fake_cfg = _make_fake_cfg(test_mode=True)

    with (
        patch.object(main_module, "AppConfig", return_value=fake_cfg),
        patch.object(main_module, "async_main", new=AsyncMock()) as mock_am,
        patch.object(main_module, "initialize_db"),
        patch.object(main_module, "add_items"),
        patch("main.asyncio.run") as mock_run,
    ):
        mock_run.return_value = None
        main_module.main()

    assert mock_run.called, "asyncio.run must be called from main()"
    # Confirm the passed argument is a coroutine object
    passed = mock_run.call_args[0][0]
    assert asyncio.iscoroutine(passed), (
        f"asyncio.run must receive a coroutine, got {type(passed)}"
    )
    # Close it to avoid unawaited-coroutine ResourceWarning
    passed.close()


# ---------------------------------------------------------------------------
# CVV gate: None in test_mode (WR-02)
# ---------------------------------------------------------------------------


def test_cvv_not_collected_in_test_mode():
    """collect_cvv() must NOT be called when test_mode=True."""
    import importlib
    import main as main_module
    importlib.reload(main_module)

    fake_cfg = _make_fake_cfg(test_mode=True)

    with (
        patch.object(main_module, "AppConfig", return_value=fake_cfg),
        patch.object(main_module, "async_main", new=AsyncMock()),
        patch.object(main_module, "initialize_db"),
        patch.object(main_module, "add_items"),
        patch.object(main_module, "collect_cvv") as mock_cvv,
        patch("main.asyncio.run") as mock_run,
    ):
        mock_run.return_value = None
        main_module.main()

    mock_cvv.assert_not_called()


def test_cvv_none_when_test_mode_true_with_bb_item():
    """CVV is not collected even when a BestBuy auto_buy item exists, if test_mode=True."""
    import importlib
    import main as main_module
    importlib.reload(main_module)

    fake_cfg = _make_fake_cfg(
        test_mode=True,
        bb_items=[("https://www.bestbuy.com/p/1", True)],
    )

    with (
        patch.object(main_module, "AppConfig", return_value=fake_cfg),
        patch.object(main_module, "async_main", new=AsyncMock()),
        patch.object(main_module, "initialize_db"),
        patch.object(main_module, "add_items"),
        patch.object(main_module, "collect_cvv") as mock_cvv,
        patch("main.asyncio.run") as mock_run,
    ):
        mock_run.return_value = None
        main_module.main()

    mock_cvv.assert_not_called()


# ---------------------------------------------------------------------------
# CVV gate: collected when test_mode=False and BestBuy auto_buy item present
# ---------------------------------------------------------------------------


def test_cvv_collected_when_needed():
    """collect_cvv() is called when test_mode=False and a BestBuy auto_buy item exists."""
    import importlib
    import main as main_module
    importlib.reload(main_module)

    fake_cfg = _make_fake_cfg(
        test_mode=False,
        bb_items=[("https://www.bestbuy.com/p/1", True)],
    )

    with (
        patch.object(main_module, "AppConfig", return_value=fake_cfg),
        patch.object(main_module, "async_main", new=AsyncMock()),
        patch.object(main_module, "initialize_db"),
        patch.object(main_module, "add_items"),
        patch.object(main_module, "collect_cvv", return_value="123") as mock_cvv,
        patch("main.asyncio.run") as mock_run,
    ):
        mock_run.return_value = None
        main_module.main()

    mock_cvv.assert_called_once()


# ---------------------------------------------------------------------------
# AppConfig ValidationError -> SystemExit(1) (CORE-05)
# ---------------------------------------------------------------------------


def test_invalid_config_exits_with_1(tmp_path, monkeypatch):
    """ValidationError from AppConfig() raises SystemExit(1) before anything else runs."""
    import yaml
    import importlib
    import main as main_module
    importlib.reload(main_module)

    # Write a broken config (item missing required 'name' field) in tmp_path
    cfg_dict = {
        "available": {
            "items": [{"link": "https://example.com", "auto_buy": True}]
        }
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(cfg_dict))

    # Patch AppConfig to use our broken config file
    from core.config_schema import AppConfig
    from pydantic import ValidationError

    def broken_appconfig(**kwargs):
        return AppConfig(yaml_file=config_file)

    with patch.object(main_module, "AppConfig", side_effect=broken_appconfig):
        with pytest.raises(SystemExit) as exc_info:
            main_module.main()

    assert exc_info.value.code == 1
