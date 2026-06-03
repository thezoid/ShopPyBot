"""ANTI-01 orchestrator jitter unit tests.

Plan: 06-02
Requirements: ANTI-01

Covers:
- _get_plugin_sleep returns a value in [min_delay, max_delay] when the plugin's
  platform config defines both fields (walmart example: min=8, max=15)
- _get_plugin_sleep returns poll_interval when plugin has no platform_key attribute
- _get_plugin_sleep returns poll_interval for an Amazon/BestBuy-shaped config that
  has delay_seconds/delay_jitter but NOT min_delay/max_delay
- SC2: config-only behavior -- setting min=8/max=15 yields values in [8, 15] across
  50 iterations without any code change
"""

from types import SimpleNamespace

import pytest

from core.config_schema import (
    WalmartPlatformConfig,
    AmazonPlatformConfig,
    PlatformsConfig,
    AppConfig,
)
from core.orchestrator import _get_plugin_sleep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plugin(platform_key=None, platforms_ns=None):
    """Return a lightweight fake plugin with optional platform_key and config."""
    plugin = SimpleNamespace()
    if platform_key is not None:
        plugin.platform_key = platform_key
    cfg = SimpleNamespace()
    cfg.platforms = platforms_ns if platforms_ns is not None else PlatformsConfig()
    plugin.config = cfg
    return plugin


# ---------------------------------------------------------------------------
# Test: walmart bounds -- returns value in [8.0, 15.0]
# ---------------------------------------------------------------------------


def test_jitter_in_range_for_walmart_config():
    """_get_plugin_sleep returns a float in [8.0, 15.0] for walmart min=8/max=15."""
    walmart_cfg = WalmartPlatformConfig(min_delay=8.0, max_delay=15.0)
    platforms = SimpleNamespace(walmart=walmart_cfg)
    plugin = _make_plugin(platform_key="walmart", platforms_ns=platforms)

    result = _get_plugin_sleep(plugin, poll_interval=30.0)

    assert isinstance(result, float)
    assert 8.0 <= result <= 15.0, f"Expected value in [8.0, 15.0], got {result}"


def test_jitter_stays_in_range_over_50_iterations():
    """SC2: all 50 calls with walmart min=8/max=15 return values in [8.0, 15.0]."""
    walmart_cfg = WalmartPlatformConfig(min_delay=8.0, max_delay=15.0)
    platforms = SimpleNamespace(walmart=walmart_cfg)
    plugin = _make_plugin(platform_key="walmart", platforms_ns=platforms)

    out_of_range = []
    for _ in range(50):
        value = _get_plugin_sleep(plugin, poll_interval=30.0)
        if not (8.0 <= value <= 15.0):
            out_of_range.append(value)

    assert not out_of_range, (
        f"Got {len(out_of_range)} values outside [8.0, 15.0]: {out_of_range[:5]}"
    )


# ---------------------------------------------------------------------------
# Test: fallback when platform_key absent
# ---------------------------------------------------------------------------


def test_fallback_when_no_platform_key():
    """_get_plugin_sleep returns poll_interval when plugin has no platform_key."""
    # No platform_key attribute on plugin
    plugin = SimpleNamespace(config=SimpleNamespace(platforms=PlatformsConfig()))
    result = _get_plugin_sleep(plugin, poll_interval=30.0)
    assert result == 30.0, f"Expected 30.0 fallback, got {result}"


def test_fallback_when_platform_key_is_none():
    """_get_plugin_sleep returns poll_interval when platform_key is None."""
    plugin = _make_plugin(platform_key=None)
    result = _get_plugin_sleep(plugin, poll_interval=25.0)
    assert result == 25.0, f"Expected 25.0 fallback, got {result}"


# ---------------------------------------------------------------------------
# Test: fallback for Amazon/BestBuy-shaped config (no min_delay/max_delay)
# ---------------------------------------------------------------------------


def test_fallback_for_amazon_shaped_config():
    """_get_plugin_sleep falls back to poll_interval for Amazon config lacking min/max_delay."""
    amazon_cfg = AmazonPlatformConfig(delay_seconds=30.0, delay_jitter=10.0)
    platforms = SimpleNamespace(amazon=amazon_cfg)
    # plugin.platform_key="amazon" but AmazonPlatformConfig has no min_delay/max_delay
    plugin = _make_plugin(platform_key="amazon", platforms_ns=platforms)

    result = _get_plugin_sleep(plugin, poll_interval=30.0)
    assert result == 30.0, f"Expected 30.0 fallback for amazon config, got {result}"


def test_fallback_for_platform_config_with_neither_delay_field():
    """_get_plugin_sleep falls back to poll_interval when platform config has no delay fields."""
    bare_cfg = SimpleNamespace()  # no min_delay, no max_delay
    platforms = SimpleNamespace(madeup=bare_cfg)
    plugin = _make_plugin(platform_key="madeup", platforms_ns=platforms)

    result = _get_plugin_sleep(plugin, poll_interval=42.0)
    assert result == 42.0, f"Expected 42.0 fallback, got {result}"


# ---------------------------------------------------------------------------
# Test: fallback when platform_key has no match in platforms config
# ---------------------------------------------------------------------------


def test_fallback_when_platform_key_not_in_config():
    """_get_plugin_sleep returns poll_interval when platform_key has no matching config key."""
    plugin = _make_plugin(platform_key="unknown_platform")
    # plugin.config.platforms is a real PlatformsConfig; "unknown_platform" is not a field
    result = _get_plugin_sleep(plugin, poll_interval=20.0)
    assert result == 20.0, f"Expected 20.0 fallback for unknown key, got {result}"
