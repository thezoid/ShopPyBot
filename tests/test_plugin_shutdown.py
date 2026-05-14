"""Phase 4 RED skeleton for D-04 / ASYNC-01 cleanup (see 04-01-PLAN.md).

All tests in this file are expected to FAIL until Plan 04-03 lands.
D-04: RetailerPlugin grows an `async def shutdown(self) -> None` with default
body `await asyncio.to_thread(self.driver.quit)`. Plugins without a driver
attribute return None without raising.
"""
import inspect
from unittest.mock import MagicMock

import pytest

from plugin_base import RetailerPlugin


def test_shutdownIsCoroutine():
    """RetailerPlugin.shutdown must be defined and be a coroutine function."""
    assert hasattr(RetailerPlugin, "shutdown"), "RetailerPlugin must define shutdown()"
    assert inspect.iscoroutinefunction(RetailerPlugin.shutdown), (
        "RetailerPlugin.shutdown must be `async def` per D-04"
    )


async def test_defaultShutdownQuitsDriver():
    """Default shutdown() must call self.driver.quit via asyncio.to_thread."""
    class _Plugin(RetailerPlugin):
        domain_pattern = ["x.example"]

        def __init__(self) -> None:
            super().__init__(platform_config=None)
            self.driver = MagicMock()

        def check_availability(self, url: str) -> bool:
            return False

        def auto_buy(self, url: str, config) -> bool:
            return False

    plugin = _Plugin()
    await plugin.shutdown()
    plugin.driver.quit.assert_called_once()


async def test_shutdownNoDriverAttribute():
    """A plugin without self.driver must return None from shutdown without raising."""
    class _NoDriverPlugin(RetailerPlugin):
        domain_pattern = ["y.example"]

        def __init__(self) -> None:
            super().__init__(platform_config=None)

        def check_availability(self, url: str) -> bool:
            return False

        def auto_buy(self, url: str, config) -> bool:
            return False

    plugin = _NoDriverPlugin()
    result = await plugin.shutdown()
    assert result is None
