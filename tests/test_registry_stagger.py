"""Phase 4 RED skeleton for ASYNC-02 (see 04-01-PLAN.md).

All tests in this file are expected to FAIL until Plan 04-03 lands.
ASYNC-02: discover_async sleeps 1.5s between plugin instantiations to avoid
chromedriver TCP port conflicts; first plugin must not sleep before construction.
"""
import asyncio
import textwrap
from pathlib import Path

import pytest

from plugin_registry import discover_async  # noqa: F401 — ImportError is the RED signal


def _writeStubPlugin(pluginDir: Path, suffix: str) -> None:
    """Drop a minimal RetailerPlugin subclass into pluginDir."""
    body = textwrap.dedent(f"""
        from plugin_base import RetailerPlugin


        class StubPlugin{suffix.capitalize()}(RetailerPlugin):
            domain_pattern = ["{suffix}.example"]
            name = "{suffix}"

            def __init__(self, **kwargs):
                self.platform_config = kwargs.get("platform_config")

            def check_availability(self, url):
                return False

            def auto_buy(self, url, config):
                return False
    """).strip() + "\n"
    (pluginDir / f"shopbot_plugin_{suffix}.py").write_text(body, encoding="utf-8")


async def test_staggerBetweenPlugins(tmp_plugins_dir, monkeypatch):
    """Two plugins => exactly one 1.5s sleep recorded between them."""
    _writeStubPlugin(tmp_plugins_dir, "one")
    _writeStubPlugin(tmp_plugins_dir, "two")

    recordedSleeps: list[float] = []
    realSleep = asyncio.sleep

    async def trackingSleep(delay: float, *args, **kwargs):
        recordedSleeps.append(delay)
        await realSleep(0)

    monkeypatch.setattr("asyncio.sleep", trackingSleep)

    await discover_async(tmp_plugins_dir, app_config=None, cvvs={})

    assert recordedSleeps == [1.5], (
        f"expected exactly one 1.5s stagger between two plugins, got {recordedSleeps}"
    )


async def test_firstPluginNoSleep(tmp_plugins_dir, monkeypatch):
    """Single plugin => no sleep before construction (stagger is between plugins)."""
    _writeStubPlugin(tmp_plugins_dir, "solo")

    recordedSleeps: list[float] = []
    realSleep = asyncio.sleep

    async def trackingSleep(delay: float, *args, **kwargs):
        recordedSleeps.append(delay)
        await realSleep(0)

    monkeypatch.setattr("asyncio.sleep", trackingSleep)

    await discover_async(tmp_plugins_dir, app_config=None, cvvs={})

    assert recordedSleeps == [], (
        f"expected no sleeps for a single plugin, got {recordedSleeps}"
    )
