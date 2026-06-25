---
phase: 18
plan: "01"
subsystem: config_schema
tags: [config, pydantic, checkout, safety-gate, buy-01, buy-02]
dependency_graph:
  requires: []
  provides: [CheckoutConfig, DebugConfig.monitor_only, AppConfig.checkout]
  affects: [core/config_schema.py, tests/test_config_schema.py]
tech_stack:
  added: []
  patterns: [Field(ge=) numeric bounds, BaseModel default-instance wiring]
key_files:
  created: []
  modified:
    - core/config_schema.py
    - tests/test_config_schema.py
decisions:
  - "monitor_only: bool = False in DebugConfig; default is False per CONTEXT.md (not True; STATE.md line 120 was stale)"
  - "CheckoutConfig uses Field(ge=) scalar bounds only; no @field_validator needed"
  - "checkout: CheckoutConfig = CheckoutConfig() declared as explicit class attribute in AppConfig to prevent extra=ignore silently dropping the YAML key (T-18-03)"
metrics:
  duration: "369s (~6 min)"
  completed: "2026-06-11"
  tasks: 2
  files: 2
---

# Phase 18 Plan 01: Config Foundation Summary

**One-liner:** Added `DebugConfig.monitor_only: bool = False` and `CheckoutConfig` (6 numeric fields with `ge` bounds) wired into `AppConfig.checkout` for downstream consumption by Phases 21/22/24.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for monitor_only and CheckoutConfig | 3ca6a23 | tests/test_config_schema.py |
| 1+2 (GREEN) | Implement DebugConfig.monitor_only + CheckoutConfig + AppConfig wiring | 0436a44 | core/config_schema.py |

## Changes Made

### core/config_schema.py

- `DebugConfig`: added `monitor_only: bool = False` after `test_mode`
- New `CheckoutConfig(BaseModel)` placed after `CaptchaConfig`, before `AppConfig`:
  - `item_timeout_secs: int = Field(default=120, ge=1)`
  - `step_timeout_secs: int = Field(default=30, ge=1)`
  - `max_cart_retries: int = Field(default=3, ge=0)`
  - `backoff_base: float = Field(default=2.0, ge=0.0)`
  - `backoff_jitter: float = Field(default=0.5, ge=0.0)`
  - `alert_on_errors: int = Field(default=3, ge=0)`
- `AppConfig`: added `checkout: CheckoutConfig = CheckoutConfig()` after `captcha` field

### tests/test_config_schema.py

Added 8 new tests covering:
- `test_monitor_only_default_false`: default is False
- `test_checkout_config_defaults`: all 6 field defaults
- `test_appconfig_checkout_is_checkout_config_instance`: AppConfig.checkout is wired
- `test_checkout_override_not_dropped`: YAML key reaches the model (T-18-03)
- `test_checkout_item_timeout_zero_rejected`: ge=1 bound
- `test_checkout_step_timeout_zero_rejected`: ge=1 bound
- `test_checkout_max_cart_retries_negative_rejected`: ge=0 bound
- `test_checkout_backoff_base_negative_rejected`: ge=0.0 bound

## Verification

- Inline verify command prints `ok`
- `pytest tests/test_config_schema.py -x -q`: 22 passed
- Full suite: 556 passed, 2 skipped (no regressions)

## Deviations from Plan

None - plan executed exactly as written. TDD RED/GREEN gate sequence followed correctly.

## TDD Gate Compliance

- RED gate commit: `3ca6a23` (test(18-01): add failing tests...)
- GREEN gate commit: `0436a44` (feat(18-01): add DebugConfig.monitor_only...)
- REFACTOR: not needed (minimal, clean implementation)

## Known Stubs

None.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or trust boundary changes introduced. CheckoutConfig holds only numeric tuning knobs. Threats T-18-01, T-18-02, T-18-03 all mitigated as planned.

## Self-Check: PASSED

- core/config_schema.py: contains `monitor_only: bool = False` - FOUND
- core/config_schema.py: contains `class CheckoutConfig(BaseModel):` - FOUND
- core/config_schema.py: contains `checkout: CheckoutConfig = CheckoutConfig()` - FOUND
- tests/test_config_schema.py: 8 new tests present - FOUND
- Commit 3ca6a23 (RED): FOUND
- Commit 0436a44 (GREEN): FOUND
