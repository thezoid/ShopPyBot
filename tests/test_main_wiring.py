"""Tests for main.py wiring to core.service.BotService.

Covers:
- main.BotService is core.service.BotService (delegation seam: main -> BotService -> async_main)
- main() calls BotService(cfg).run(cvv) (not async_main directly)
- CVV gate: collect_cvv() skipped in test_mode (WR-02)
- CVV gate: collect_cvv() skipped when test_mode=True even with BestBuy auto_buy item
- CVV gate: collect_cvv() called when test_mode=False and BestBuy auto_buy item exists
- AppConfig ValidationError -> SystemExit(1) (CORE-05)

NOTE (GSD-flagged single allowed change): the delegation seam moved from
main->async_main to main->BotService->async_main in plan 07-03. The two
delegation tests below assert the new seam. The three CVV-gate tests have
their run-path patches repointed from main.asyncio.run/main.async_main to
main.BotService; CVV gate intent is fully preserved.
"""

from unittest.mock import MagicMock, patch, call

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
# Delegation: main.BotService IS core.service.BotService
# ---------------------------------------------------------------------------


def test_main_botservice_is_core_service():
    """main.BotService must be core.service.BotService (delegation seam: main -> BotService)."""
    import main as main_module
    import core.service as svc_module

    assert main_module.BotService is svc_module.BotService, (
        "main.BotService must be core.service.BotService (delegation seam)"
    )


# ---------------------------------------------------------------------------
# Delegation: main() calls BotService(cfg).run(cvv)
# ---------------------------------------------------------------------------


def test_main_delegates_to_botservice_run():
    """main() must construct BotService(cfg) and call .run(cvv) -- not asyncio.run directly."""
    import importlib
    import main as main_module
    importlib.reload(main_module)

    fake_cfg = _make_fake_cfg(test_mode=True)

    mock_service_instance = MagicMock()
    mock_botservice_cls = MagicMock(return_value=mock_service_instance)

    with (
        patch.object(main_module, "AppConfig", return_value=fake_cfg),
        patch.object(main_module, "initialize_db"),
        patch.object(main_module, "add_items"),
        patch.object(main_module, "update_item_price_config_sync"),
        patch.object(main_module, "BotService", mock_botservice_cls),
    ):
        main_module.main()

    mock_botservice_cls.assert_called_once_with(fake_cfg)
    mock_service_instance.run.assert_called_once_with(None)


# ---------------------------------------------------------------------------
# CVV gate: None in test_mode (WR-02)
# ---------------------------------------------------------------------------


def test_cvv_not_collected_in_test_mode():
    """collect_cvv() must NOT be called when test_mode=True."""
    import importlib
    import main as main_module
    importlib.reload(main_module)

    fake_cfg = _make_fake_cfg(test_mode=True)

    mock_service_instance = MagicMock()

    with (
        patch.object(main_module, "AppConfig", return_value=fake_cfg),
        patch.object(main_module, "initialize_db"),
        patch.object(main_module, "add_items"),
        patch.object(main_module, "update_item_price_config_sync"),
        patch.object(main_module, "collect_cvv") as mock_cvv,
        patch.object(main_module, "BotService", return_value=mock_service_instance),
    ):
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

    mock_service_instance = MagicMock()

    with (
        patch.object(main_module, "AppConfig", return_value=fake_cfg),
        patch.object(main_module, "initialize_db"),
        patch.object(main_module, "add_items"),
        patch.object(main_module, "update_item_price_config_sync"),
        patch.object(main_module, "collect_cvv") as mock_cvv,
        patch.object(main_module, "BotService", return_value=mock_service_instance),
    ):
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

    mock_service_instance = MagicMock()

    with (
        patch.object(main_module, "AppConfig", return_value=fake_cfg),
        patch.object(main_module, "initialize_db"),
        patch.object(main_module, "add_items"),
        patch.object(main_module, "update_item_price_config_sync"),
        patch.object(main_module, "collect_cvv", return_value="123") as mock_cvv,
        patch.object(main_module, "BotService", return_value=mock_service_instance),
    ):
        main_module.main()

    mock_cvv.assert_called_once()
    # Confirm the collected CVV is forwarded into BotService.run()
    mock_service_instance.run.assert_called_once_with("123")


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
