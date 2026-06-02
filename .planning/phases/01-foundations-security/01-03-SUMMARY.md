---
phase: 01-foundations-security
plan: "03"
subsystem: config-schema
tags: [pydantic-settings, config, validation, security, env-vars]
dependency_graph:
  requires: [01-01]
  provides: [AppConfig, config-schema, startup-validation]
  affects: [main.py (plan 05), all plans needing typed config]
tech_stack:
  added: []
  patterns: [BaseSettings, YamlConfigSettingsSource, model_validator-before, env_nested_delimiter, yaml_file-injection]
key_files:
  created:
    - core/config_schema.py
    - tests/test_config_schema.py
  modified: []
decisions:
  - "yaml_file= constructor kwarg sets class-level _active_yaml_file sentinel so settings_customise_sources (classmethod) can read it; no PrivateAttr conflict"
  - "No env_prefix used: single-user tool, simpler UX (DEBUG__LOGGING_LEVEL vs SHOPBOT_DEBUG__LOGGING_LEVEL)"
  - "YAML path resolved absolutely via Path(__file__).parent.parent / config.yml to prevent CWD-relative silent misconfiguration (RESEARCH Pitfall 2)"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-02"
  tasks: 2
  files_changed: 2
---

# Phase 01 Plan 03: AppConfig pydantic-settings Schema Summary

AppConfig BaseSettings replacing raw yaml.safe_load() with typed nested models, startup validation, legacy-key DeprecationWarning, and env var credential override.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement AppConfig pydantic-settings schema | c7765d9 | core/config_schema.py |
| 2 | Write test_config_schema.py covering CORE-05/06/07 and SEC-01 | ee4dae2 | tests/test_config_schema.py |

## What Was Built

`core/config_schema.py`: AppConfig(BaseSettings) with nested models ItemConfig, AvailableConfig, DebugConfig, AmazonPlatformConfig, BestBuyPlatformConfig, PlatformsConfig. Legacy-key validator emits DeprecationWarning for old app.amz_email/bb_email keys. env_settings precedence over YAML so credentials never live in config.yml. Absolute YAML path resolution prevents silent CWD-relative misconfiguration.

`tests/test_config_schema.py`: 5 tests covering all 4 requirements. Uses yaml_file= constructor kwarg for test YAML injection. Full suite: 14 passed.

## Verification Results

```
5 passed in 0.19s  (tests/test_config_schema.py -x -q)
14 passed, 1 warning in 1.16s  (full suite)
```

The single warning is a pre-existing pygame pkg_resources deprecation, unrelated to this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _yaml_file constructor kwarg collides with pydantic PrivateAttr**
- **Found during:** Task 1 verification
- **Issue:** PATTERNS.md shows test injection as `AppConfig(_yaml_file=f)`. Using `_yaml_file` as a class attribute on a pydantic BaseSettings subclass causes pydantic to treat it as a `ModelPrivateAttr`, which raises `AttributeError: 'ModelPrivateAttr' object has no attribute 'is_file'` when `settings_customise_sources` tries to read it.
- **Fix:** Renamed constructor kwarg to `yaml_file=` (no underscore). Stores the resolved path in a class-level sentinel `_active_yaml_file` via `AppConfig._active_yaml_file = Path(yaml_file)` inside `__init__`. The classmethod `settings_customise_sources` reads the sentinel via `getattr(cls, '_active_yaml_file', _DEFAULT_YAML_PATH)`. Tests adapted to use `yaml_file=` instead of `_yaml_file=`.
- **Files modified:** core/config_schema.py, tests/test_config_schema.py
- **Commit:** c7765d9, ee4dae2

## Known Stubs

None -- AppConfig loads from a real YAML file at construction time. No hardcoded empty values flow to any UI or consumer.

## Threat Flags

None -- no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what the threat model covers. The AppConfig trust boundary (config.yml -> AppConfig) is explicitly modeled in the plan's STRIDE register (T-01-CFG, T-01-CRED, T-01-CFGPATH) and all three are mitigated by this implementation.

## Self-Check: PASSED

- core/config_schema.py: EXISTS
- tests/test_config_schema.py: EXISTS
- Commit c7765d9: EXISTS (feat(01-03))
- Commit ee4dae2: EXISTS (test(01-03))
- `python -m pytest tests/test_config_schema.py -x -q` exits 0: CONFIRMED (5 passed)
- AppConfig.model_fields has no credential fields: CONFIRMED (only debug, available, platforms)
- env var override works: CONFIRMED (DEBUG__LOGGING_LEVEL=1 overrides YAML logging_level=5)
