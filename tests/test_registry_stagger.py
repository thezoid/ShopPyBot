"""Phase 4 GREEN: tests for ASYNC-02 (1.5s stagger in discover_async).

Covers: stagger between plugins, no leading sleep for first plugin,
stagger_seconds override, failed-instantiation still triggers stagger for
the next plugin (sleep is per path-iteration, not per successful load).
"""
import textwrap
from pathlib import Path

import pytest

from plugin_registry import DEFAULT_STAGGER_SECONDS, discover_async


PLUGIN_TEMPLATE = textwrap.dedent("""\
    from plugin_base import RetailerPlugin

    class {className}(RetailerPlugin):
        domain_pattern = ["{domain}"]
        def __init__(self, platform_config=None, cvv=None, driver_path=None):
            super().__init__(platform_config=platform_config)
        def check_availability(self, url): return False
        def auto_buy(self, url, config): return False
""")


def _writePlugin(directory: Path, slug: str, className: str, domain: str) -> None:
    (directory / f"shopbot_plugin_{slug}.py").write_text(
        PLUGIN_TEMPLATE.format(className=className, domain=domain)
    )


@pytest.fixture
def fakeAsyncSleep(monkeypatch):
    sleeps: list[float] = []

    async def _fake(delay):
        sleeps.append(delay)

    monkeypatch.setattr("plugin_registry.asyncio.sleep", _fake)
    return sleeps


async def test_staggerBetweenTwoPlugins(tmp_plugins_dir, fakeAsyncSleep):
    _writePlugin(tmp_plugins_dir, "alpha", "Alpha", "alpha.example")
    _writePlugin(tmp_plugins_dir, "beta", "Beta", "beta.example")
    plugins = await discover_async(tmp_plugins_dir, app_config=None, cvvs={})
    assert len(plugins) == 2
    assert fakeAsyncSleep == [DEFAULT_STAGGER_SECONDS]


async def test_firstPluginNoSleep(tmp_plugins_dir, fakeAsyncSleep):
    _writePlugin(tmp_plugins_dir, "alpha", "Alpha", "alpha.example")
    plugins = await discover_async(tmp_plugins_dir, app_config=None, cvvs={})
    assert len(plugins) == 1
    assert fakeAsyncSleep == []


async def test_staggerOverride(tmp_plugins_dir, fakeAsyncSleep):
    _writePlugin(tmp_plugins_dir, "a", "A", "a.example")
    _writePlugin(tmp_plugins_dir, "b", "B", "b.example")
    _writePlugin(tmp_plugins_dir, "c", "C", "c.example")
    await discover_async(
        tmp_plugins_dir, app_config=None, cvvs={}, stagger_seconds=0.25
    )
    assert fakeAsyncSleep == [0.25, 0.25]


async def test_failedInstantiationStillStaggersNext(tmp_plugins_dir, fakeAsyncSleep):
    """A plugin that fails to load does NOT skip the stagger before the NEXT plugin.

    Sleep happens at every path-iteration boundary past the first, regardless of
    whether the preceding load succeeded. Locks in the contract; any future
    optimization that conditions the sleep on success must update this test.
    """
    _writePlugin(tmp_plugins_dir, "ok", "Ok", "ok.example")
    (tmp_plugins_dir / "shopbot_plugin_broken.py").write_text(
        "raise RuntimeError('broken')\n"
    )
    _writePlugin(tmp_plugins_dir, "good", "Good", "good.example")
    plugins = await discover_async(tmp_plugins_dir, app_config=None, cvvs={})
    assert len(plugins) == 2
    assert fakeAsyncSleep == [DEFAULT_STAGGER_SECONDS, DEFAULT_STAGGER_SECONDS]
