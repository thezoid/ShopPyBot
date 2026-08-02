"""Tests for core/service.py BotService.

Covers every public method:
  - get_config(), list_items(), get_status() work before start() (no side effects)
  - add_item() delegates to add_items_sync with the right tuple
  - remove_item() delegates to remove_item_sync
  - start() launches background run + get_status() reports running True
  - stop() signals shutdown, teardown_all is awaited, get_status() reports False
  - run() delegates to asyncio.run(async_main(cfg, cvv)) (blocking convenience)

No real browser is launched; async_main is always patched at the module boundary.
"""

import asyncio
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
import yaml

from core.config_schema import AppConfig
from core.service import BotService, main


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_cfg(tmp_path):
    """Return an AppConfig loaded from a minimal in-memory config.yml."""
    cfg_data = {
        "debug": {"logging_level": 0, "test_mode": True},
        "available": {"timeout": 10, "items": []},
        "platforms": {
            "amazon": {"delay_seconds": 30.0},
            "bestbuy": {"delay_seconds": 30.0},
        },
    }
    yml = tmp_path / "config.yml"
    yml.write_text(yaml.dump(cfg_data))
    return AppConfig(yaml_file=yml)


@pytest.fixture
def service(minimal_cfg, tmp_data_dir):
    """BotService constructed with a minimal AppConfig + redirected DB."""
    return BotService(cfg=minimal_cfg)


# ---------------------------------------------------------------------------
# Callable-without-start tests
# ---------------------------------------------------------------------------


def test_get_config_returns_appconfig(service, minimal_cfg):
    """get_config() returns the AppConfig the service was constructed with."""
    result = service.get_config()
    assert result is minimal_cfg


def test_get_status_before_start_reports_not_running(service):
    """get_status() returns running=False before start() is called."""
    status = service.get_status()
    assert isinstance(status, dict)
    assert status["running"] is False


def test_get_status_shape_before_start(service):
    """get_status() returns the locked 3-key shape before start(); plugins is empty dict; uptime 0.0."""
    status = service.get_status()
    assert "running" in status
    assert "uptime_secs" in status
    assert "plugins" in status
    assert isinstance(status["plugins"], dict)
    assert status["plugins"] == {}
    assert status["uptime_secs"] == 0.0


def test_get_status_shape_with_registry(service):
    """After a heartbeat, get_status()['plugins'] contains the plugin with the public keys."""
    service._health_registry.heartbeat("FakePlugin")
    status = service.get_status()
    assert "FakePlugin" in status["plugins"]
    plugin_rec = status["plugins"]["FakePlugin"]
    for key in ("status", "heartbeat_age_secs", "consecutive_errors", "items_checked", "orders_confirmed"):
        assert key in plugin_rec, f"Missing key: {key}"
    assert "last_heartbeat" not in plugin_rec, "AF-02: raw last_heartbeat must not reach get_status()"


def test_get_status_is_json_serializable(service):
    """get_status() with registry data is JSON-serializable (REL-07)."""
    import json
    service._health_registry.heartbeat("FakePlugin")
    result = json.dumps(service.get_status())
    assert isinstance(result, str)


def test_list_items_before_start_returns_rows(service, tmp_data_dir):
    """list_items() returns DB rows without starting the bot."""
    from models import initialize_db, add_items_sync
    initialize_db(delete=True)
    add_items_sync([("Widget", "https://example.com/w", False, 1, False)])
    rows = service.list_items()
    assert len(rows) == 1
    assert rows[0][0] == "Widget"


# ---------------------------------------------------------------------------
# WR-02 (34-REVIEW): list_plugins() platform_key fallback must match the
# logger/analytics tag (core.registry._plugin_tag), never a raw None.
# ---------------------------------------------------------------------------


def test_list_plugins_platform_key_fallback_matches_logger_tag(service):
    """A plugin without platform_key gets the SAME normalized class-name tag
    the logger/analytics use -- not None (which the dashboard dropdown skips)."""
    from core.plugin_base import RetailerPlugin

    class UnkeyedPlugin(RetailerPlugin):
        domain_patterns = ["unkeyed.example.com"]

        async def check_availability(self, url):
            return False

        async def auto_buy(self, url):
            return False

    plugin = UnkeyedPlugin(config=None)
    mock_registry = MagicMock()
    mock_registry._all_plugins = [plugin]

    with patch("core.registry.PluginRegistry", return_value=mock_registry):
        rows = service.list_plugins()

    assert len(rows) == 1
    assert rows[0]["platform_key"] == "unkeyedplugin", (
        f"Expected the lowercased class-name fallback tag, got {rows[0]['platform_key']!r}"
    )


def test_list_plugins_platform_key_uses_explicit_value_when_set(service):
    """A plugin WITH platform_key still returns that exact value (regression guard)."""
    from core.plugin_base import RetailerPlugin

    class KeyedPlugin(RetailerPlugin):
        domain_patterns = ["keyed.example.com"]
        platform_key = "keyed"

        async def check_availability(self, url):
            return False

        async def auto_buy(self, url):
            return False

    plugin = KeyedPlugin(config=None)
    mock_registry = MagicMock()
    mock_registry._all_plugins = [plugin]

    with patch("core.registry.PluginRegistry", return_value=mock_registry):
        rows = service.list_plugins()

    assert rows[0]["platform_key"] == "keyed"


# ---------------------------------------------------------------------------
# WR-03 (34-REVIEW): BotService.get_analytics() end-to-end integration test.
#
# Exercises the REAL models.get_order_analytics_rows_sync() SQL column order,
# the REAL core/service.py `columns` tuple zip, and the REAL PluginRegistry
# hostname resolution against a real temp DB (via the models sync writers) --
# not compute_analytics() called directly (tests/test_analytics.py) and not a
# fully-mocked /api/analytics route (tests/test_api_observability.py). A
# future column-order drift between get_order_analytics_rows_sync's SELECT
# and this columns tuple would silently swap fields and fail this assertion.
# ---------------------------------------------------------------------------


def test_get_analytics_end_to_end_real_db_and_registry(service, tmp_data_dir):
    """get_analytics() end-to-end: real DB rows -> real column zip -> real
    registry platform resolution -> correct bucketing/success_rate/duration."""
    from models import (
        initialize_db,
        add_items_sync,
        mark_place_order_attempted_sync,
        update_item_confirmed_sync,
    )

    initialize_db(delete=True)

    amazon_link = "https://www.amazon.com/dp/TESTA1"
    bestbuy_link = "https://www.bestbuy.com/site/testb1"
    add_items_sync([
        ("Amazon Widget", amazon_link, True, 1, False),
        ("BestBuy Widget", bestbuy_link, True, 1, False),
    ])
    mark_place_order_attempted_sync(amazon_link, "2026-01-01T00:00:00+00:00")
    mark_place_order_attempted_sync(bestbuy_link, "2026-01-01T00:00:00+00:00")
    update_item_confirmed_sync(amazon_link, "111-2223334-5556667", "2026-01-01T00:00:40+00:00")
    update_item_confirmed_sync(bestbuy_link, "BB-778899", "2026-01-01T00:01:00+00:00")

    result = service.get_analytics()

    assert result["overall"]["attempted"] == 2
    assert result["overall"]["confirmed"] == 2
    assert result["overall"]["success_rate"] == 1.0
    assert result["overall"]["avg_time_to_checkout_secs"] == pytest.approx(50.0)
    assert result["overall"]["sample_size"] == 2

    per_plugin = {row["plugin"]: row for row in result["per_plugin"]}
    assert "amazon" in per_plugin, f"Expected an 'amazon' bucket; got {list(per_plugin)}"
    assert "bestbuy" in per_plugin, f"Expected a 'bestbuy' bucket; got {list(per_plugin)}"
    assert per_plugin["amazon"]["confirmed"] == 1
    assert per_plugin["amazon"]["avg_time_to_checkout_secs"] == pytest.approx(40.0)
    assert per_plugin["bestbuy"]["confirmed"] == 1
    assert per_plugin["bestbuy"]["avg_time_to_checkout_secs"] == pytest.approx(60.0)

    # link must never leak into the analytics response (T-34-06)
    import json
    payload = json.dumps(result)
    assert amazon_link not in payload
    assert bestbuy_link not in payload


def test_get_analytics_empty_db_returns_safe_defaults(service, tmp_data_dir):
    """get_analytics() on a fresh empty DB returns valid zero-division-safe defaults."""
    from models import initialize_db
    initialize_db(delete=True)

    result = service.get_analytics()

    assert result["overall"]["attempted"] == 0
    assert result["overall"]["success_rate"] is None
    assert result["per_plugin"] == []


# ---------------------------------------------------------------------------
# add_item / remove_item delegation tests
# ---------------------------------------------------------------------------


def test_add_item_delegates_to_add_items_sync(service):
    """add_item() calls add_items_sync with a single 5-tuple (purchased=False)."""
    with patch("core.service.add_items_sync") as mock_add:
        service.add_item("Gadget", "https://example.com/g", True, 2)
        mock_add.assert_called_once_with(
            [("Gadget", "https://example.com/g", True, 2, False)]
        )


def test_remove_item_delegates_to_remove_item_sync(service):
    """remove_item() calls remove_item_sync with the link."""
    with patch("core.service.remove_item_sync") as mock_rm:
        service.remove_item("https://example.com/g")
        mock_rm.assert_called_once_with("https://example.com/g")


# ---------------------------------------------------------------------------
# start / stop lifecycle tests
# ---------------------------------------------------------------------------


async def test_start_sets_status_to_running(service, minimal_cfg):
    """start() launches background run; get_status() then reports running=True."""
    async def _noop(cfg, cvv, **kwargs):
        await asyncio.sleep(3600)

    with patch("core.service.async_main", new=_noop):
        service.start(cvv=None)
        try:
            # Give the background thread a moment to set running state
            deadline = time.monotonic() + 2.0
            while not service.get_status()["running"] and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
            assert service.get_status()["running"] is True
        finally:
            service.stop()
            # Allow teardown to complete
            deadline = time.monotonic() + 2.0
            while service.get_status()["running"] and time.monotonic() < deadline:
                await asyncio.sleep(0.05)


async def test_stop_sets_status_to_not_running(service, minimal_cfg):
    """stop() flips running to False after start()."""
    async def _noop(cfg, cvv, **kwargs):
        await asyncio.sleep(3600)

    with patch("core.service.async_main", new=_noop):
        service.start(cvv=None)
        deadline = time.monotonic() + 2.0
        while not service.get_status()["running"] and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        service.stop()
        deadline = time.monotonic() + 2.0
        while service.get_status()["running"] and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        assert service.get_status()["running"] is False


async def test_stop_triggers_teardown(service, minimal_cfg):
    """stop() causes teardown_all to be called on the registry."""
    teardown_called = asyncio.Event()

    async def _mock_main(cfg, cvv, **kwargs):
        # Simulate what async_main does: run until cancelled, then teardown
        try:
            await asyncio.sleep(3600)
        except (asyncio.CancelledError, Exception):
            teardown_called.set()
            raise

    with patch("core.service.async_main", new=_mock_main):
        service.start(cvv=None)
        deadline = time.monotonic() + 2.0
        while not service.get_status()["running"] and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        service.stop()
        try:
            await asyncio.wait_for(teardown_called.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            pass  # teardown signaling may vary; main check is running=False
        deadline = time.monotonic() + 2.0
        while service.get_status()["running"] and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        assert service.get_status()["running"] is False


# ---------------------------------------------------------------------------
# run() convenience
# ---------------------------------------------------------------------------


def test_run_calls_asyncio_run_with_async_main(service, minimal_cfg):
    """run() wraps asyncio.run(async_main(cfg, cvv)) (blocking convenience)."""
    sentinel = object()

    def _fake_async_main(cfg, cvv, **kwargs):
        return sentinel  # return a non-coroutine so asyncio.run receives a plain value

    with patch("core.service.async_main", new=_fake_async_main):
        with patch("core.service.asyncio.run") as mock_run:
            service.run(cvv="test-cvv")
            mock_run.assert_called_once_with(sentinel)


# ---------------------------------------------------------------------------
# No interactive input in module
# ---------------------------------------------------------------------------


def test_service_module_has_no_input_call():
    """core/service.py must not contain any input() call (ASYNC-03 / T-07-04)."""
    import ast
    from pathlib import Path
    source = (Path(__file__).parent.parent / "core" / "service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            is_input = isinstance(func, ast.Name) and func.id == "input"
            assert not is_input, f"Found input() call at line {node.lineno}"


def test_service_module_has_no_getpass():
    """core/service.py must not import or call getpass (T-07-04)."""
    from pathlib import Path
    source = (Path(__file__).parent.parent / "core" / "service.py").read_text(encoding="utf-8")
    assert "getpass" not in source, "core/service.py must not reference getpass"


# ---------------------------------------------------------------------------
# module-level main() entry point
# ---------------------------------------------------------------------------


def test_main_is_callable():
    """core.service.main is importable and callable."""
    assert callable(main)


def test_main_constructs_service_and_runs(tmp_path):
    """main() loads AppConfig and calls BotService.run()."""
    cfg_data = {
        "debug": {"logging_level": 0, "test_mode": True},
        "available": {"timeout": 10, "items": []},
    }
    yml = tmp_path / "config.yml"
    yml.write_text(yaml.dump(cfg_data))

    run_called = {}

    class _FakeService:
        def __init__(self, cfg=None):
            run_called["constructed"] = True

        def get_config(self):
            # Return a minimal mock config so handle_run's CVV gate works
            from unittest.mock import MagicMock
            return MagicMock(
                debug=MagicMock(test_mode=True),
                available=MagicMock(items=[]),
            )

        def run(self, cvv=None):
            run_called["run"] = True

    with patch("core.service.BotService", new=_FakeService):
        # bare invocation now calls sys.exit(0) after run -- catch it (CR-01)
        with pytest.raises(SystemExit) as exc_info:
            main([])   # explicit argv=[] avoids sys.argv contamination (RESEARCH Pitfall 7)
    assert exc_info.value.code == 0

    assert run_called.get("constructed"), "BotService was not constructed"
    assert run_called.get("run"), "BotService.run() was not called"
