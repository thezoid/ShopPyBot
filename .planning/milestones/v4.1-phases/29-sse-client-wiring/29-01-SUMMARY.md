---
phase: 29-sse-client-wiring
plan: "01"
requirements: [SSE-01]
subsystem: test
tags: [sse, tdd, red-scaffold, dashboard]
dependency_graph:
  requires: []
  provides: [tests/test_sse_wiring.py]
  affects: []
tech_stack:
  added: []
  patterns: [TestClient static-template assertion, pytest fixture reuse]
key_files:
  created:
    - tests/test_sse_wiring.py
  modified: []
decisions:
  - test_no_onmessage_for_named_events asserts absent pattern (GREEN at Wave 0, guards forever against Pitfall 1)
  - test_setinterval_only_in_fallback asserts "typeof EventSource not found" rather than wrong-branch placement (correctly RED for Wave 0 since feature-detect itself absent)
  - W29-A8/A9/A10 cross-referenced in module docstring; not duplicated (live in test_web_dashboard.py/test_design_system.py)
metrics:
  duration: 233s
  completed: 2026-06-27
---

# Phase 29 Plan 01: Wave 0 RED Scaffold Summary

**One-liner:** Static-template RED scaffold for SSE client wiring (W29-A1..A11) via pytest TestClient assertions on GET / HTML.

## What Was Built

`tests/test_sse_wiring.py` -- 9 test functions covering all automatable Phase 29 assertions:

| Test | W29-Ax | Assertion | Status at Wave 0 |
|------|--------|-----------|-----------------|
| test_eventsource_constructed | A1 | `new EventSource('/api/events')` in resp.text | RED |
| test_named_status_listener | A2 | `addEventListener('status'` in resp.text | RED |
| test_named_log_listener | A3 | `addEventListener('log'` in resp.text | RED |
| test_no_onmessage_for_named_events | guard | `.onmessage` NOT in resp.text | GREEN (expected) |
| test_feature_detect_present | A4 | `typeof EventSource` in resp.text | RED |
| test_render_status_extracted | A5 | `renderStatus` in resp.text | RED |
| test_no_dup_guard_present | A6 | `_lastLogLine` in resp.text | RED |
| test_indicator_element_present | A7 | `id="sse-indicator"` in resp.text | RED |
| test_setinterval_only_in_fallback | A11 | both setInterval(poll* after else branch of feature-detect | RED |

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- `pytest tests/test_sse_wiring.py -q` -- 8 failed, 1 passed (RED for right reason; COLLECT clean)
- `pytest tests/test_observability_ui.py tests/test_web_dashboard.py tests/test_design_system.py -q` -- 24 passed (no regression)

## Known Stubs

None. Test-only plan; no production code.

## Threat Flags

None. In-process TestClient; no new network surface.

## Self-Check: PASSED

- `tests/test_sse_wiring.py` -- FOUND (commit 40302ca)
- 8 RED, 1 GREEN, 0 collection errors -- confirmed by pytest run
