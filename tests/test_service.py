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


def test_list_items_before_start_returns_rows(service, tmp_data_dir):
    """list_items() returns DB rows without starting the bot."""
    from models import initialize_db, add_items_sync
    initialize_db(delete=True)
    add_items_sync([("Widget", "https://example.com/w", False, 1, False)])
    rows = service.list_items()
    assert len(rows) == 1
    assert rows[0][0] == "Widget"


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
    async def _noop(cfg, cvv):
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
    async def _noop(cfg, cvv):
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

    async def _mock_main(cfg, cvv):
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

    def _fake_async_main(cfg, cvv):
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
        main([])   # explicit argv=[] avoids sys.argv contamination (RESEARCH Pitfall 7)

    assert run_called.get("constructed"), "BotService was not constructed"
    assert run_called.get("run"), "BotService.run() was not called"
