---
phase: 06-platform-expansion
plan: "02"
subsystem: orchestrator
tags: [anti-detection, jitter, async, config]
dependency_graph:
  requires: [06-01]
  provides: [ANTI-01, SC2-jitter]
  affects: [core/orchestrator.py, tests/test_orchestrator_jitter.py]
tech_stack:
  added: []
  patterns:
    - getattr-based platform_key lookup for config-driven jitter
    - random.uniform(min_delay, max_delay) per-plugin sleep with poll_interval fallback
key_files:
  created:
    - tests/test_orchestrator_jitter.py
  modified:
    - core/orchestrator.py
decisions:
  - "_get_plugin_sleep uses try/except Exception (not bare except) per module docstring contract"
  - "platform_key lookup uses getattr chain: no hardcoded class-name string munging"
  - "Amazon/BestBuy fallback is silent and automatic: they have no platform_key, so poll_interval applies unchanged"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-03"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 6 Plan 02: Orchestrator Per-Platform Jitter Summary

One-liner: Per-plugin jitter sleep via `_get_plugin_sleep` using `random.uniform(min_delay, max_delay)` with fallback to shared `poll_interval`, proven config-only by ANTI-01 unit tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add _get_plugin_sleep helper and wire into run_plugin | 58214cc | core/orchestrator.py |
| 2 | Fill tests/test_orchestrator_jitter.py (ANTI-01) | e8f662b | tests/test_orchestrator_jitter.py |

## What Was Built

### Task 1: _get_plugin_sleep + run_plugin wiring

Added `import random` and the `_get_plugin_sleep(plugin, poll_interval)` module-level function to `core/orchestrator.py`. The function:

1. Reads `getattr(plugin, "platform_key", None)` -- absent on Amazon/BestBuy plugins, present on new Phase-6 plugins.
2. Looks up `getattr(plugin.config.platforms, platform_key, None)` -- safely returns None for unknown keys.
3. Reads `min_delay` and `max_delay` via `getattr` -- missing on Amazon/BestBuy configs (they have `delay_seconds`/`delay_jitter` instead).
4. Returns `random.uniform(min_delay, max_delay)` when both are present; otherwise returns `poll_interval`.
5. Wraps the entire lookup in `except Exception` (not bare except, per module docstring contract).

The single line change in `run_plugin`: `await asyncio.sleep(_get_plugin_sleep(plugin, poll_interval))`.

### Task 2: ANTI-01 jitter tests

Replaced the scaffold placeholder in `tests/test_orchestrator_jitter.py` with 7 unit tests:

- `test_jitter_in_range_for_walmart_config`: single call returns float in [8.0, 15.0].
- `test_jitter_stays_in_range_over_50_iterations`: SC2 proof -- 50 calls all in bounds.
- `test_fallback_when_no_platform_key`: plugin with no `platform_key` attribute returns poll_interval.
- `test_fallback_when_platform_key_is_none`: explicit `None` platform_key returns poll_interval.
- `test_fallback_for_amazon_shaped_config`: `AmazonPlatformConfig` (has `delay_seconds`, no `min_delay`) returns poll_interval.
- `test_fallback_for_platform_config_with_neither_delay_field`: bare `SimpleNamespace()` returns poll_interval.
- `test_fallback_when_platform_key_not_in_config`: unknown key not in `PlatformsConfig` returns poll_interval.

## Verification

Full suite: `126 passed, 6 skipped` -- skips are downstream plan scaffolds (06-03 through 06-05, unchanged).

```
tests/test_orchestrator.py          16 passed  (no regression)
tests/test_orchestrator_jitter.py    7 passed  (ANTI-01 new)
```

Acceptance criteria check:
- `_get_plugin_sleep` present in orchestrator.py: YES (58214cc)
- `import random` present: YES
- `run_plugin` calls `asyncio.sleep(_get_plugin_sleep(plugin, poll_interval))`: YES
- No bare `except:` introduced: YES (uses `except Exception`)
- Jitter tests assert in-range for walmart over 50 iterations: YES
- Fallback for no platform_key: YES
- Fallback for Amazon-shaped config: YES
- SC2 proven config-only (no code change needed for min=8/max=15): YES

## Deviations from Plan

None -- plan executed exactly as written.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes beyond what was already declared in the plan's threat model (T-06-04, T-06-05, T-06-SC all addressed by Plan 06-01 config schema constraints and the getattr fallback pattern).

## Self-Check

Files created/modified:
- core/orchestrator.py: present and contains _get_plugin_sleep + import random
- tests/test_orchestrator_jitter.py: present with 7 passing tests

Commits:
- 58214cc: feat(06-02): add _get_plugin_sleep helper and wire into run_plugin
- e8f662b: test(06-02): implement ANTI-01 jitter tests (SC2 config-only behavior)

## Self-Check: PASSED
