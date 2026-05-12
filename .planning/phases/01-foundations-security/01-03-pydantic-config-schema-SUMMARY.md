---
phase: 01-foundations-security
plan: 03
subsystem: config
tags:
  - pydantic
  - pydantic-settings
  - config
  - validation
  - security
dependency_graph:
  requires:
    - 01-01 (pinned pydantic + pydantic-settings[yaml], conftest fixtures clean_env/tmp_config_yml)
  provides:
    - AppConfig (BaseSettings) entry point for Plan 05 wiring
    - PlatformConfig + PlatformCredentials per-platform model (D-02 init contract)
    - reject_deprecated_keys migration trap (D-06)
  affects:
    - main.py and bot modules (Plan 05 swaps `from config import config` for AppConfig)
    - REQUIREMENTS.md CORE-01 wording (D-01 alignment)
tech_stack:
  added: []
  patterns:
    - pydantic-settings YAML source via settings_customise_sources (env > YAML)
    - model_validator(mode='before') for legacy-key migration trap
    - SettingsConfigDict(extra='forbid', env_prefix='SHOPBOT_', env_nested_delimiter='__')
key_files:
  created:
    - config_schema.py
    - tests/test_config_schema.py
  modified:
    - sample.config.yml
    - .planning/REQUIREMENTS.md
  deleted:
    - tests/test_config.py
decisions:
  - "Env source listed before YAML source in settings_customise_sources tuple so SHOPBOT_* env vars override YAML (SEC-01)."
  - "reject_deprecated_keys runs at mode='before' so the migration block fires before any field validation, ensuring the user sees the migration message not a generic extra-forbidden error."
  - "PlatformCredentials has email + password only; CVV deliberately omitted (collected at runtime via getpass per SEC-02 / D-04)."
metrics:
  duration_minutes: 6
  tasks_completed: 2
  files_touched: 5
  completed: 2026-05-12
requirements_addressed:
  - CORE-05
  - CORE-06
  - CORE-07
  - SEC-01
---

# Phase 1 Plan 03: Pydantic Config Schema Summary

Pydantic `AppConfig(BaseSettings)` validates `config.yml` at startup with strict per-platform credential nesting, env-var override, and a hard-fail migration trap for the legacy `app.amz_*` / `app.bb_*` keys.

## What Was Built

- `config_schema.py` (98 lines) defines the full schema tree: `AppConfig` (BaseSettings) over nested `SeleniumConfig`, `DebugConfig`, `AvailableConfig` of `ItemConfig`, and a `platforms: dict[str, PlatformConfig]` map where each platform holds an `enabled` flag plus a `PlatformCredentials(email, password)` block.
- `settings_customise_sources` orders init > env > YAML so `SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL` and equivalents take precedence over anything in `config.yml`, satisfying SEC-01.
- `reject_deprecated_keys` (a `@model_validator(mode="before")` classmethod) inspects the raw dict for the five legacy app-block keys (`amz_email`, `amz_pwd`, `bb_email`, `bb_password`, `bb_cvv`) and raises `ValueError` carrying a copy-pasteable migration block when any are present. Per D-06 there is no auto-remap and no back-compat shim.
- `sample.config.yml` rewritten: no plaintext credentials, `platforms.amazon` and `platforms.bestbuy` blocks include inline comments naming the env vars and the CVV opt-in flow (`SHOPBOT_ALLOW_CVV_ENV` + `SHOPBOT_BESTBUY_CVV`).
- `tests/test_config_schema.py` has 7 contract tests: valid load, missing `selenium` field message, `extra=forbid` rejects unknown top-level keys, per-platform credential reachability, deprecated `amz_email` and `bb_cvv` hard-fails, env-var override of YAML.
- `tests/test_config.py` deleted (it imported `from config import load_config` which is being retired in Plan 05; collection error on master is now resolved).
- REQUIREMENTS.md CORE-01 wording aligned with Phase 1 D-01 (drops the `driver` parameter from ABC method signatures; plugins own `self.driver` per D-02).

## Tasks Executed

| Task | Name                                                | Commit  | Status |
| ---- | --------------------------------------------------- | ------- | ------ |
| 1    | Write failing config schema tests (RED)             | 622c0cb | done   |
| 2    | Implement config_schema.py + sample + REQUIREMENTS  | 91faed5 | done   |

## Verification

- `rtk pytest -x tests/test_config_schema.py` -> 7 passed
- `rtk pytest tests/test_config_schema.py tests/test_models.py tests/test_plugin_base.py tests/test_python_version.py tests/test_requirements.py` -> 15 passed
- `sample.config.yml` contains no `amz_email`, `amz_pwd`, `bb_cvv` substrings; contains `platforms:` and `SHOPBOT_PLATFORMS__AMAZON` substrings.
- REQUIREMENTS.md CORE-01 line contains `self, url` and `self.driver`; does not contain `(driver,` or `driver, url`.
- Full-suite `rtk pytest` not run because `tests/test_utils.py` has a pre-existing `pygame` ModuleNotFoundError on this machine (out of scope; tracked for INFRA backlog).

## Deviations from Plan

None. Plan executed exactly as written. The only minor textual choice was using a colon instead of an em dash in the `config_schema.py` module docstring and inline comments, per the user CLAUDE.md no-em-dash rule (no functional impact; not a deviation from plan semantics).

## TDD Gate Compliance

- RED gate: `test(01-03): add failing AppConfig schema tests (RED)` at 622c0cb -> tests failed with `ModuleNotFoundError: No module named 'config_schema'` as expected.
- GREEN gate: `feat(01-03): add AppConfig pydantic schema + migration trap` at 91faed5 -> all 7 tests pass.
- REFACTOR: not needed; implementation followed the RESEARCH.md Pattern 2 verbatim.

## Threat Flags

None. No new network endpoints, auth paths, or trust boundaries introduced beyond the YAML/env surfaces already enumerated in the plan's threat register. All STRIDE entries (T-1-SEC-01, T-1-CORE-05, T-1-CORE-06, T-1-CORE-07, T-1-YAML-RCE, T-1-EXTRA-FORBID) are mitigated as planned.

## Known Stubs

None. The schema is complete and consumed by Plan 05.

## Follow-ups

- Plan 05 swaps every `from config import config` consumer to read `AppConfig` and deletes the legacy `config.py` shim.
- `tests/test_utils.py` collection error (pygame missing) is pre-existing; addressed under Plan 01 backlog if not resolved by then.

## Self-Check: PASSED

- FOUND: config_schema.py
- FOUND: tests/test_config_schema.py
- FOUND: sample.config.yml (modified)
- FOUND: .planning/REQUIREMENTS.md (modified, CORE-01 D-01 wording)
- MISSING (intentional): tests/test_config.py (deleted)
- FOUND commit: 622c0cb (Task 1 RED)
- FOUND commit: 91faed5 (Task 2 GREEN)
