---
phase: 04-async-orchestrator
plan: "01"
subsystem: config + test-infrastructure
tags: [config, fixtures, asyncio, poll_interval, tdd]
dependency_graph:
  requires: []
  provides:
    - cfg.app.poll_interval typed field (default 30)
    - fake_plugin fixture (no-browser RetailerPlugin for orchestrator tests)
    - event_shim fixture (thread-safe asyncio.Event driver)
  affects:
    - core/config_schema.py
    - tests/conftest.py
    - tests/test_config_schema.py
tech_stack:
  added: []
  patterns:
    - AppSettingsConfig(BaseModel) submodel mounted on AppConfig(BaseSettings)
    - TDD RED/GREEN cycle for config field
    - AsyncMock-based fake plugin factory fixture
    - loop.call_soon_threadsafe as thread-safe Event bridge
key_files:
  created: []
  modified:
    - core/config_schema.py
    - tests/conftest.py
    - tests/test_config_schema.py
decisions:
  - "poll_interval: int = 30 as single shared field; per-platform jitter deferred to Phase 6"
  - "AppSettingsConfig mounts as cfg.app; legacy _LEGACY_KEYS['app'] credential keys coexist without collision"
  - "event_shim uses loop.call_soon_threadsafe exclusively (RESEARCH Pitfall 1 compliance)"
metrics:
  duration_minutes: 15
  completed_date: "2026-06-03T14:22:19Z"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
---

# Phase 04 Plan 01: poll_interval Config + Async Test Fixtures Summary

Wave 0 groundwork: typed poll_interval config field via AppSettingsConfig and shared fake_plugin/event_shim fixtures that all downstream orchestrator waves depend on.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for poll_interval | f1330e8 | tests/test_config_schema.py |
| 1 (GREEN) | AppSettingsConfig implementation | d736ebf | core/config_schema.py |
| 2 | fake_plugin + event_shim fixtures | c34c1ba | tests/conftest.py |

## What Was Built

### Task 1: cfg.app.poll_interval

Added `AppSettingsConfig(BaseModel)` to `core/config_schema.py`:

- Single field `poll_interval: int = 30` (locked Phase 4 decision)
- Mounted on `AppConfig` as `app: AppSettingsConfig = AppSettingsConfig()`
- No collision with `_LEGACY_KEYS["app"]` -- legacy keys are credential names (amz_email etc.), not poll_interval
- Pydantic types poll_interval as int; non-int YAML raises ValidationError at startup (T-04-01 mitigated)

Two new tests in `tests/test_config_schema.py`:
- `test_poll_interval_default`: asserts `cfg.app.poll_interval == 30` with no app section in YAML
- `test_poll_interval_yaml_override`: asserts value reads 15 when `app.poll_interval: 15` in YAML

### Task 2: fake_plugin and event_shim Fixtures

Added to `tests/conftest.py`:

`fake_plugin` factory fixture:
- Returns a builder function `_build(domains, available, bought, config)`
- Builds a concrete `RetailerPlugin` subclass with no real browser
- `setup` and `teardown` are `AsyncMock` instances
- `check_availability` and `auto_buy` return configurable bool values
- Instance supports attaching asyncio.Event attributes for downstream Event tests

`event_shim` fixture:
- Returns `_fire(event, loop)` helper
- Calls `loop.call_soon_threadsafe(event.set)` -- the exact thread-safe bridge the real `_stdin_listener_thread` will use (RESEARCH Pitfall 1)
- Lets downstream tests prove a coroutine waiting on `event.wait()` resumes correctly

## Deviations from Plan

None -- plan executed exactly as written. TDD RED/GREEN cycle followed; no jitter fields added; no new dependencies.

## Threat Model Coverage

| Threat | Status |
|--------|--------|
| T-04-01: poll_interval tampering | Mitigated: Pydantic types as int; ValidationError on bad YAML |
| T-04-02: absurdly low poll_interval DoS | Accepted: local single-user tool per threat register |
| T-04-03: fixture info disclosure | Accepted: no credentials touched in fixtures |

## Known Stubs

None.

## Self-Check: PASSED

- core/config_schema.py: AppSettingsConfig + poll_interval field present
- tests/test_config_schema.py: poll_interval default + override tests present (7 passed)
- tests/conftest.py: fake_plugin + event_shim + call_soon_threadsafe present
- Full suite: 47 passed
- Commits f1330e8, d736ebf, c34c1ba all verified in git log
