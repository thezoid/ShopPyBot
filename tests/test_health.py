"""Tests for HealthRegistry in core/health.py.

Covers REL-07: per-plugin health store for orchestrator write / BotService.get_status read.
"""

import json

import pytest

from core.health import HealthRegistry


def test_registry_idle_before_use():
    reg = HealthRegistry()
    assert reg.get_snapshot() == {}


def test_heartbeat_sets_heartbeat_age_secs():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    snap = reg.get_snapshot()
    assert snap["PluginA"]["heartbeat_age_secs"] is not None


def test_default_status_is_idle():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    snap = reg.get_snapshot()
    assert snap["PluginA"]["status"] == "idle"


def test_set_status_updates_status():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    reg.set_status("PluginA", "running")
    snap = reg.get_snapshot()
    assert snap["PluginA"]["status"] == "running"


def test_record_and_reset_errors():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    reg.record_error("PluginA")
    reg.record_error("PluginA")
    snap = reg.get_snapshot()
    assert snap["PluginA"]["consecutive_errors"] == 2
    reg.reset_errors("PluginA")
    snap2 = reg.get_snapshot()
    assert snap2["PluginA"]["consecutive_errors"] == 0


def test_inc_counters():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    reg.inc_items_checked("PluginA")
    reg.inc_items_checked("PluginA")
    reg.inc_orders_confirmed("PluginA")
    snap = reg.get_snapshot()
    assert snap["PluginA"]["items_checked"] == 2
    assert snap["PluginA"]["orders_confirmed"] == 1


def test_arm_disarm_degraded():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    assert reg.is_degraded_armed("PluginA") is False
    reg.arm_degraded("PluginA")
    assert reg.is_degraded_armed("PluginA") is True
    reg.disarm_degraded("PluginA")
    assert reg.is_degraded_armed("PluginA") is False


def test_snapshot_strips_private_keys():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    snap = reg.get_snapshot()
    for key in snap["PluginA"]:
        assert not key.startswith("_"), f"Private key leaked into snapshot: {key}"


def test_snapshot_is_deep_copy():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    reg.inc_items_checked("PluginA")
    snap = reg.get_snapshot()
    snap["PluginA"]["items_checked"] = 999
    snap2 = reg.get_snapshot()
    assert snap2["PluginA"]["items_checked"] == 1


def test_snapshot_is_json_serializable():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    reg.set_status("PluginA", "running")
    reg.inc_items_checked("PluginA")
    reg.inc_orders_confirmed("PluginA")
    result = json.dumps(reg.get_snapshot())
    assert len(result) > 0


def test_snapshot_public_keys_exact():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    snap = reg.get_snapshot()
    expected_keys = {
        "status", "consecutive_errors",
        "items_checked", "orders_confirmed", "last_error",
        "heartbeat_age_secs",
    }
    assert set(snap["PluginA"].keys()) == expected_keys


def test_snapshot_excludes_last_heartbeat():
    """AF-02: the raw last_heartbeat monotonic float never crosses the public snapshot boundary."""
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    snap = reg.get_snapshot()
    assert "last_heartbeat" not in snap["PluginA"]


def test_heartbeat_age_secs_fresh():
    """heartbeat_age_secs is a non-negative float after calling heartbeat()."""
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    snap = reg.get_snapshot()
    assert snap["PluginA"]["heartbeat_age_secs"] is not None
    assert snap["PluginA"]["heartbeat_age_secs"] >= 0.0


def test_heartbeat_age_secs_never():
    """heartbeat_age_secs is None when the plugin is registered but never heartbeated."""
    reg = HealthRegistry()
    reg._ensure("PluginA")          # registered but never heartbeated
    snap = reg.get_snapshot()
    assert snap["PluginA"]["heartbeat_age_secs"] is None
