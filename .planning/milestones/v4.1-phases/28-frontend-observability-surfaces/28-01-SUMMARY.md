---
phase: 28-frontend-observability-surfaces
plan: "01"
requirements: [OBS-01, OBS-03]
subsystem: tests
tags: [tdd, red-scaffold, health, observability, wave-0]
dependency_graph:
  requires: []
  provides:
    - "RED heartbeat_age_secs guard in tests/test_health.py"
    - "RED static-scaffold assertions in tests/test_observability_ui.py"
  affects:
    - "tests/test_health.py"
    - "tests/test_observability_ui.py"
tech_stack:
  added: []
  patterns:
    - "pytest.importorskip for optional fastapi dependency gate"
    - "TestClient(create_app(mock_svc)) fixture pattern (from test_web_dashboard.py)"
key_files:
  modified:
    - tests/test_health.py
  created:
    - tests/test_observability_ui.py
decisions:
  - "test_header_uptime_slot_present and test_uplot_script_and_css_present are GREEN at Wave 0 (Phase 25 already placed those elements); all other new tests are RED"
  - "mock_svc.get_status.return_value includes uptime_secs and plugins keys per 28-PATTERNS.md fixture spec"
  - "No monkeypatching of time.monotonic -- natural monotonic advance between heartbeat() and get_snapshot() is sufficient for the fresh/never distinction"
metrics:
  duration: "269s"
  completed: "2026-06-27"
  tasks: 2
  files: 2
---

# Phase 28 Plan 01: Wave 0 RED Scaffold Summary

Wave 0 RED scaffold for Phase 28 -- added heartbeat_age_secs snapshot-key tests to test_health.py and created the new static-scaffold test file test_observability_ui.py that asserts all three new dashboard sections, header uptime slot, log controls, MAX_LOG_LINES constant, and uPlot assets.

## What Was Built

### Task 1: Update snapshot-key guard + add heartbeat_age_secs unit tests (cfca436)

`tests/test_health.py` modified:
- `test_snapshot_public_keys_exact`: added `"heartbeat_age_secs"` to `expected_keys` set (RED -- key absent from `get_snapshot()` until 28-02)
- `test_heartbeat_age_secs_fresh`: asserts field is `not None` and `>= 0.0` after `heartbeat()` (RED)
- `test_heartbeat_age_secs_never`: asserts field is `None` when plugin only called `_ensure()`, `last_heartbeat == 0.0` sentinel (RED)

Existing 10 health tests remain GREEN. No production code changed.

### Task 2: Create static-scaffold tests for observability sections (c0987b3)

`tests/test_observability_ui.py` created (6 tests):

| Test | Status | Notes |
|------|--------|-------|
| test_dashboard_renders_health_section | RED | asserts `id="section-health"` + "Plugin Health" |
| test_header_uptime_slot_present | GREEN | Phase 25 placed `id="header-uptime"` |
| test_dashboard_renders_buys_section | RED | asserts `id="section-buys"` + "Confirmed Orders" + "Order ID" + "Checkout Attempts" |
| test_dashboard_renders_log_viewer_section | RED | asserts `id="section-log-viewer"`, `id="log-buffer"`, `id="log-level-filter"`, `id="log-search"` |
| test_log_dom_cap_constant | RED | asserts `"MAX_LOG_LINES = 500"` in rendered HTML |
| test_uplot_script_and_css_present | GREEN | both uplot assets already present from Phase 25 |

## Verification Results

```
tests/test_health.py tests/test_observability_ui.py: 7 failed (expected RED), 12 passed
tests/test_web_dashboard.py::test_no_innerHTML_with_api_data: PASSED (XSS guard intact)
```

RED tests fail for the right reason: missing keys/IDs/constants in the current codebase. No import errors, no syntax errors, all tests collect cleanly.

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None -- this plan creates only test files with no production code stubs.

## Threat Flags

None -- test-only plan; no new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- [x] tests/test_health.py modified: confirmed (cfca436)
- [x] tests/test_observability_ui.py created: confirmed (c0987b3)
- [x] cfca436 exists in git log: confirmed
- [x] c0987b3 exists in git log: confirmed
- [x] 3 health tests RED for right reason (KeyError/AssertionError on heartbeat_age_secs)
- [x] 4 observability UI tests RED for right reason (section ids absent from current dashboard.html)
- [x] 2 observability UI tests GREEN (header-uptime, uplot.min.css from Phase 25)
- [x] Existing 10 health tests GREEN
- [x] XSS guard (test_no_innerHTML_with_api_data) GREEN
- [x] No production code modified
