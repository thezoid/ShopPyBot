"""Phase 4 GREEN: tests for D-04 (async shutdown ABC default)."""
import asyncio
import inspect
from unittest.mock import MagicMock

import pytest

from plugin_base import RetailerPlugin


class _NoDriverPlugin(RetailerPlugin):
    domain_pattern = ["x.example"]

    def check_availability(self, url):
        return False

    def auto_buy(self, url, config):
        return False


class _WithDriverPlugin(RetailerPlugin):
    domain_pattern = ["y.example"]

    def __init__(self):
        super().__init__(platform_config=None)
        self.driver = MagicMock()

    def check_availability(self, url):
        return False

    def auto_buy(self, url, config):
        return False


def test_shutdownIsCoroutineFunction():
    assert inspect.iscoroutinefunction(RetailerPlugin.shutdown)


async def test_defaultShutdownQuitsDriver():
    plugin = _WithDriverPlugin()
    await plugin.shutdown()
    plugin.driver.quit.assert_called_once_with()


async def test_shutdownNoDriverAttribute():
    plugin = _NoDriverPlugin(platform_config=None)
    # No self.driver assigned; must not raise
    result = await plugin.shutdown()
    assert result is None


async def test_shutdownSwallowsDriverQuitException(caplog):
    plugin = _WithDriverPlugin()
    plugin.driver.quit.side_effect = RuntimeError("driver hang")
    # Must NOT propagate; orchestrator depends on this contract
    # for asyncio.gather(..., return_exceptions=True)
    await plugin.shutdown()
    plugin.driver.quit.assert_called_once_with()


async def test_subclassCanOverrideAndCallSuper():
    class _CustomCleanup(_WithDriverPlugin):
        def __init__(self):
            super().__init__()
            self.extraCleanupRan = False

        async def shutdown(self):
            self.extraCleanupRan = True
            await super().shutdown()

    plugin = _CustomCleanup()
    await plugin.shutdown()
    assert plugin.extraCleanupRan is True
    plugin.driver.quit.assert_called_once_with()
