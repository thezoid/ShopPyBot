"""CI enforcement tests for BUY-02: place_order_guarded reroute across all 7 plugins.

Tests:
- test_no_raw_place_order_click_in_plugins: static grep assertion — every plugin with
  a known place-order selector must also reference place_order_guarded (T-18-10).
- test_all_plugins_monitor_only_no_purchase_write: 7 real plugin classes loaded via
  importlib; place_order_guarded called with monitor_only=True returns False and never
  invokes the click callable (T-18-11).
- test_monitor_only_gate_via_orchestrator: fake_plugin with monitor_only=True through
  _check_and_buy asserts zero ("purchased", ...) writes to the write queue (BUY-01/02
  cross-check, T-18-11).

asyncio_mode=auto (pyproject.toml) -- no @pytest.mark.asyncio decorator needed.
"""

import asyncio
import importlib
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.orchestrator import _check_and_buy
from core.plugin_base import RetailerPlugin


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLUGINS_DIR = Path(__file__).parent.parent / "plugins"

_PLUGIN_MODULE_NAMES = [
    "shopbot_plugin_amazon",
    "shopbot_plugin_bestbuy",
    "shopbot_plugin_walmart",
    "shopbot_plugin_target",
    "shopbot_plugin_gamestop",
    "shopbot_plugin_newegg",
    "shopbot_plugin_squareenix",
]

# Selectors that must only appear guarded (via place_order_guarded).
_PLACE_ORDER_SELECTORS = [
    "#submitOrderButtonId",
    ".button--place-order",
    "place-order-button",
    "placeOrder",
    "place-order",
    "Place Order",
]


# ---------------------------------------------------------------------------
# Helper: load a real plugin class from the plugins/ directory
# ---------------------------------------------------------------------------


def _load_plugin_class(module_name: str) -> type:
    """Import module_name from plugins/ and return the RetailerPlugin subclass."""
    spec = importlib.util.spec_from_file_location(
        module_name, _PLUGINS_DIR / f"{module_name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, RetailerPlugin) and obj is not RetailerPlugin:
            return obj
    raise RuntimeError(f"No RetailerPlugin subclass found in {module_name}")


def _make_monitor_only_config() -> MagicMock:
    """Return a MagicMock config with monitor_only=True, test_mode=False."""
    cfg = MagicMock()
    cfg.debug.monitor_only = True
    cfg.debug.test_mode = False
    cfg.available.items = []
    return cfg


# ---------------------------------------------------------------------------
# T-18-10: Static grep enforcement
# ---------------------------------------------------------------------------


def test_no_raw_place_order_click_in_plugins():
    """BUY-02 static guard: every plugin with a place-order selector must use place_order_guarded.

    Iterates all shopbot_plugin_*.py files; any file that (a) defines auto_buy AND
    (b) contains a known place-order selector string MUST also contain
    place_order_guarded, or CI fails with the offending file and selector.

    Two-tier check (WR-03):
    Tier 1 (file-level): selector present but place_order_guarded entirely absent.
    Tier 2 (line-level): any line that contains BOTH a place-order selector AND a
    direct .click() call (with parentheses) is a raw unguarded click, even if
    place_order_guarded exists elsewhere in the file.

    Known limitation: a plugin that retrieves a place-order element on one line and
    calls .click() on a different line (via a held reference) would not be caught by
    Tier 2. Full AST-level analysis would be required for complete coverage. This is
    documented here so future authors do not treat this test as a complete guarantee.
    """
    violations = []
    for plugin_file in sorted(_PLUGINS_DIR.glob("shopbot_plugin_*.py")):
        source = plugin_file.read_text(encoding="utf-8")
        if "auto_buy" not in source:
            continue

        # Tier 1: file has selector but place_order_guarded is entirely absent.
        for selector in _PLACE_ORDER_SELECTORS:
            if selector in source and "place_order_guarded" not in source:
                violations.append(
                    f"{plugin_file.name}: contains selector {selector!r} "
                    "but does not reference place_order_guarded()"
                )

        # Tier 2: any line with a place-order selector AND a direct .click() call.
        for lineno, line in enumerate(source.splitlines(), start=1):
            if ".click()" in line:
                for selector in _PLACE_ORDER_SELECTORS:
                    if selector in line:
                        violations.append(
                            f"{plugin_file.name}:{lineno}: raw .click() on "
                            f"place-order selector {selector!r} -- must use place_order_guarded"
                        )

    assert not violations, (
        "The following plugins have raw place-order selectors outside place_order_guarded:\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# T-18-11: 7-plugin monitor_only guard suppression
# ---------------------------------------------------------------------------


async def test_all_plugins_monitor_only_no_purchase_write():
    """BUY-02: all 7 real plugin classes with monitor_only=True suppress the place-order click.

    For each plugin:
    - Construct with monitor_only=True, test_mode=False config.
    - Call place_order_guarded(click_fn) directly where click_fn is an AsyncMock.
    - Assert the return value is False (suppressed).
    - Assert click_fn was NOT awaited (no live order placed).
    """
    failures = []
    for module_name in _PLUGIN_MODULE_NAMES:
        plugin_class = _load_plugin_class(module_name)
        cfg = _make_monitor_only_config()
        plugin = plugin_class(config=cfg)

        click_fn = AsyncMock(name=f"{module_name}.place_order.click")
        result = await plugin.place_order_guarded(click_fn)

        if result is not False:
            failures.append(f"{module_name}: place_order_guarded returned {result!r}, expected False")
        if click_fn.await_count != 0:
            failures.append(
                f"{module_name}: click_fn was awaited {click_fn.await_count} time(s), expected 0"
            )

    assert not failures, (
        "place_order_guarded did not suppress for the following plugins:\n"
        + "\n".join(failures)
    )


# ---------------------------------------------------------------------------
# BUY-01/02 orchestrator cross-check: monitor_only gate via _check_and_buy
# ---------------------------------------------------------------------------


async def test_monitor_only_gate_via_orchestrator(fake_plugin):
    """BUY-01/02: fake_plugin with monitor_only=True through _check_and_buy yields zero
    ("purchased", ...) writes to the write_queue.

    The orchestrator's monitor_only gate in _check_and_buy fires before _try_auto_buy,
    so the write queue never receives a "purchased" tuple even when auto_buy=True.

    WR-01: DB sync functions called by _check_and_buy are patched so the test
    genuinely asserts the monitor_only gate rather than relying on exception-swallowing
    from missing tables.
    """
    cfg = MagicMock()
    cfg.debug.monitor_only = True
    cfg.debug.test_mode = False
    cfg.available.items = []

    plugin = fake_plugin(
        domains=["fake.example.com"],
        available=True,
        bought=True,
        config=cfg,
    )

    write_queue = asyncio.Queue()
    with (
        patch("core.orchestrator.get_item_notification_state_sync", return_value=(False, None)),
        patch("core.orchestrator.get_last_price_sync", return_value=None),
        patch("core.orchestrator.append_price_history_sync"),
        patch("core.orchestrator.get_item_price_config_sync", return_value=None),
        patch("core.orchestrator.writeLog"),
    ):
        await _check_and_buy(
            plugin, "Test Item", "https://fake.example.com/item", True, write_queue
        )

    # Drain the queue and assert no ("purchased", ...) tuple was enqueued.
    enqueued = []
    while not write_queue.empty():
        enqueued.append(write_queue.get_nowait())

    purchased_writes = [item for item in enqueued if isinstance(item, tuple) and item[0] == "purchased"]
    assert not purchased_writes, (
        f"Expected zero 'purchased' writes under monitor_only=True, got: {purchased_writes}"
    )
