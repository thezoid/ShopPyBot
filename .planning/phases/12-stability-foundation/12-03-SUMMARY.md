---
phase: 12-stability-foundation
plan: "03"
subsystem: web-tests
tags: [regression, td-4, mc-4, mod-02, banner, config-write]
dependency_graph:
  requires: []
  provides: [TD-4-config-seam-regression, MC-4-banner-render-assertion]
  affects: [tests/test_web_config.py, tests/test_web_dashboard.py, web/config_web.py]
tech_stack:
  added: []
  patterns: [TestClient regression, patch _DEFAULT_YAML_PATH, is_non_local=True banner gate]
key_files:
  created: []
  modified:
    - tests/test_web_config.py
    - tests/test_web_dashboard.py
    - web/config_web.py
decisions:
  - "TD-4 config seam: write_web_config direct-write to _DEFAULT_YAML_PATH is accepted under MOD-02 (BotService scoped to DB/registry/orchestrator); WEB_ALLOWLIST is the safety boundary"
  - "MC-4 banner gate: Jinja2 is_non_local conditional proven by asserting presence when True and absence when False (Pitfall 5)"
metrics:
  duration: "~4 minutes"
  completed: "2026-06-09T05:14:25Z"
  tasks_completed: 2
  files_modified: 3
---

# Phase 12 Plan 03: TD-4 Config-Seam Regression + MC-4 Banner-Render Assertions Summary

TD-4 config write seam closed via a new regression test asserting `write_web_config` writes directly to a patched `_DEFAULT_YAML_PATH` (accepted MOD-02 gap, documented with a greppable in-code comment); credential seam was already covered by the pre-existing `test_post_credentials_calls_store_set`. MC-4 banner behavior is now CI-enforced both ways via two `TestClient` regression tests on `is_non_local=True/False`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Document accepted MOD-02 write-seam gap + TD-4 config-write regression test | d1c9f6b | web/config_web.py, tests/test_web_config.py |
| 2 | Assert 0.0.0.0 bind-warning banner renders when is_non_local=True (MC-4) | 18b1709 | tests/test_web_dashboard.py |

## What Was Built

**Task 1 (TD-4 config seam):**
- Added a `MOD-02` accepted-gap comment block inside `write_web_config` in `web/config_web.py` explaining the direct `_DEFAULT_YAML_PATH` write path is accepted under MOD-02 scope (BotService covers DB/registry/orchestrator, not config file writes).
- Added `test_write_web_config_config_seam_direct_write_accepted_mod02_gap` to `tests/test_web_config.py`: patches `_DEFAULT_YAML_PATH`, calls `write_web_config("logging_level", "3")`, asserts the value is written to the YAML file. Docstring documents the TD-4 accepted gap explicitly.
- The credential seam (TD-4 second half) is already covered by `tests/test_web_credentials.py::test_post_credentials_calls_store_set` (named, not re-added).

**Task 2 (MC-4 banner render):**
- Added `test_banner_renders_when_non_local` to `tests/test_web_dashboard.py`: builds `TestClient(create_app(mock_svc, is_non_local=True))`, GETs `/`, asserts `"reachable beyond localhost"` and `"banner-warning"` are present.
- Added `test_banner_absent_when_local`: builds `TestClient(create_app(mock_svc, is_non_local=False))`, asserts `"reachable beyond localhost"` is absent. Proves the `{% if is_non_local %}` gate actually works.

## Verification Results

- `pytest -q tests/test_web_config.py tests/test_web_credentials.py`: 13 passed
- `pytest -q tests/test_web_dashboard.py`: 10 passed
- Full suite: 359 passed, 2 skipped (baseline was 356+2; +3 new tests)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

No new production code, no new trust boundaries. The MC-4 test strengthens the existing non-local exposure warning control. No additional threat surface introduced.

## Self-Check: PASSED

- `web/config_web.py` exists and contains "MOD-02": confirmed
- `tests/test_web_config.py` contains `test_write_web_config_config_seam_direct_write_accepted_mod02_gap`: confirmed
- `tests/test_web_dashboard.py` contains `is_non_local=True`: confirmed
- Commits d1c9f6b and 18b1709 exist in git log: confirmed
- Full suite green (359 passed, 2 skipped): confirmed
