---
phase: 33-config-refactor
plan: 02
subsystem: config
tags: [pydantic, config-schema, plugin-framework, extra-allow]

# Dependency graph
requires:
  - phase: 33-config-refactor (plan 01)
    provides: Canonical delay_seconds/delay_jitter field names on all 7 platform models (harmonized field set CFG-02 builds on)
provides:
  - PlatformsConfig with ConfigDict(extra="allow") -- undeclared platforms.<key> sections pass through as raw dicts instead of being silently dropped
  - RetailerPlugin.get_platform_config(model_cls) helper -- validates a plugin's own per-platform section against its own model, getattr-safe
  - Fixture-plugin test proof (tests/test_platform_config_extension.py) that a new undeclared platforms.costco section loads and validates with core/config_schema.py touched by nothing beyond the extra="allow" line
affects: [34-feature-completion, 35-audit-fixes-doc-hygiene, future community plugins]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "getattr-safe plugin-side config resolution: get_platform_config(model_cls) mirrors the existing _session_enabled/_session_platform_key idiom in core/plugin_base.py"
    - "extra='allow' passthrough for a generic extension point, keeping the 7 declared platform models' strict validation completely untouched"

key-files:
  created:
    - tests/test_platform_config_extension.py
  modified:
    - core/config_schema.py
    - core/plugin_base.py

key-decisions:
  - "extra=\"allow\" added as the first class-body statement on PlatformsConfig (candidate (a) from RESEARCH.md) -- zero core-schema edits required for a new plugin's platform section; the 7 declared fields keep full Field-level validation, proven by test_known_platform_strict_validation_intact."
  - "get_platform_config resolves the four cases (missing config/key/section -> model_cls() defaults; built-in platform -> already-validated instance; new plugin dict -> model_cls(**raw), fail-loud ValidationError on bad data; else -> model_cls() fallback) exactly per RESEARCH.md's verified code shape."
  - "Fixture test uses a TEST-MODULE-scope CostcoPlatformConfig, not one defined inside the dynamically exec'd tmp plugin file, and does NOT importlib.import_module the tmp plugin -- core/registry.py's _discover_plugins loads plugin files via spec_from_file_location + exec_module without registering them in sys.modules, so import_module would raise ModuleNotFoundError. This was the plan-checker-caught blocker; the plan was already revised to this approach before execution."
  - "[Rule 1 - Bug] Fixed the plan's proposed fixture-construction snippet: AppConfig(**{\"platforms\": {...}}) silently no-ops because AppConfig.settings_customise_sources excludes init_settings from its returned source tuple (only env_settings + YamlConfigSettingsSource are wired in). Switched the fixture test to the codebase's established yaml_file=<Path> injection pattern (writes a real config.yml under tmp_path), matching tests/conftest.py and tests/test_config_schema.py."

patterns-established:
  - "Pattern: generic per-platform config extension point -- extra=\"allow\" on the aggregate config model + a plugin-side get_platform_config(model_cls) helper is the sanctioned way for a new community plugin to declare its own config section without ANY core/config_schema.py edit."

requirements-completed: [CFG-02]

# Metrics
duration: 12min
completed: 2026-07-02
---

# Phase 33 Plan 02: Config Refactor - Generic Per-Platform Config Summary

**A plugin can now declare its own `platforms.<key>` config section and validate it via `RetailerPlugin.get_platform_config(model_cls)` with zero edits to `core/config_schema.py`, proven by a fixture-plugin test, while the 7 built-in platforms keep full strict validation.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-02T23:15:00Z (approx, first Read calls)
- **Completed:** 2026-07-02T23:27:00Z
- **Tasks:** 2 (RED, GREEN)
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- `PlatformsConfig` gains `model_config = ConfigDict(extra="allow")` as its first class-body statement — an undeclared `platforms.<key>` section now passes through as a raw dict instead of being silently dropped (the literal bug CFG-02 fixes), while the 7 declared platform fields keep full strict validation unchanged
- `RetailerPlugin.get_platform_config(model_cls)` added to `core/plugin_base.py`: getattr-safe, returns `model_cls()` defaults on missing config/key/section, the already-validated instance for a built-in platform, or `model_cls(**raw)` for a new plugin's passthrough dict (raises `ValidationError` on bad data, fail-loud, matching the 7 platforms)
- Fixture-plugin test (`tests/test_platform_config_extension.py`) proves a brand-new `platforms.costco` section loads and validates via the plugin's own test-module-scope model, with `core/config_schema.py` touched by nothing beyond the single `extra="allow"` line
- Known-platform strictness proven intact: `PlatformsConfig(**{"amazon": {"delay_seconds": -5}})` still raises `ValidationError`
- Full suite green: 898 passed, 2 skipped (baseline 894 + 4 net-new tests)

## Task Commits

Each task was committed atomically (TDD RED -> GREEN):

1. **Task 1: RED — fixture-plugin test proving a new undeclared section validates with core schema untouched, plus known-platform strictness** - `1624ef6` (test)
2. **Task 2: GREEN — add extra='allow' to PlatformsConfig and the get_platform_config helper on RetailerPlugin** - `8622dda` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `tests/test_platform_config_extension.py` (created) - `CostcoPlatformConfig` at test-module scope; `test_new_plugin_platform_section_validates_without_core_edits`, `test_new_plugin_section_invalid_value_raises`, `test_known_platform_strict_validation_intact`, `test_get_platform_config_defaults_when_section_absent`
- `core/config_schema.py` - `ConfigDict` added to the pydantic import; `PlatformsConfig.model_config = ConfigDict(extra="allow")` with explanatory comment; the 7 declared platform fields unchanged
- `core/plugin_base.py` - `from pydantic import BaseModel` import added; `get_platform_config(self, model_cls)` method added to `RetailerPlugin` with the four-case return logic and full docstring; `PLUGIN_API_VERSION` unchanged at 2

## Decisions Made
- Implemented candidate (a) from RESEARCH.md exactly as recommended: `extra="allow"` + plugin-side `get_platform_config` helper — no per-platform hardcoding, no construction-order changes, no `dict[str, PlatformConfigBase]` breaking change to the 7 existing call sites.
- Fixture test follows the plan's REVISED approach: `CostcoPlatformConfig` defined at test-module scope, tmp plugin file only declares `CostcoPlugin(platform_key='costco')`, no `importlib.import_module` of the exec_module-loaded tmp plugin.
- Fixed the fixture test's `AppConfig` construction to use `yaml_file=<Path>` injection instead of the plan's proposed `AppConfig(**{"platforms": {...}})` kwargs, which silently no-ops under this codebase's `settings_customise_sources` override (see Deviations below).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed fixture test construction: AppConfig(**kwargs) silently ignores "platforms" data**
- **Found during:** Task 2 GREEN verification (`pytest tests/test_platform_config_extension.py tests/test_config_schema.py -q` after adding `extra="allow"` and `get_platform_config`) — 2 of 4 new tests still failed unexpectedly (`test_new_plugin_platform_section_validates_without_core_edits` and `test_new_plugin_section_invalid_value_raises`)
- **Issue:** The plan's interfaces section and RESEARCH.md's fixture-pattern code example both used `AppConfig(**{"platforms": {"costco": {...}}})` to inject the fixture platform section. `AppConfig.settings_customise_sources` (an existing, pre-33 override) returns `(env_settings, YamlConfigSettingsSource(...))` — it does NOT include `init_settings` in the returned source tuple. Because of this, direct constructor kwargs passed to `AppConfig(**values)` are silently discarded by pydantic-settings' source-merging; `getattr(cfg.platforms, "costco", None)` returned `None` even though the kwarg was passed. Verified live: `AppConfig(**{"platforms": {"amazon": {"delay_seconds": 999.0}}}).platforms.amazon.delay_seconds` returns `30.0` (the default), not `999.0` — confirming this is a general property of `AppConfig`, not specific to the new `costco` key.
- **Fix:** Rewrote `_build_costco_registry` in the test file to write a real `config.yml` under `tmp_path` (via `yaml.dump`) and construct `AppConfig(yaml_file=config_yml)` — the established, working injection pattern already used throughout this codebase's test suite (`tests/conftest.py:tmp_config_yml`, `tests/test_config_schema.py:valid_config_yml`).
- **Files modified:** `tests/test_platform_config_extension.py` (both changes made within Task 2's GREEN verification loop, before the GREEN commit)
- **Verification:** Re-ran the targeted test file; all 32 tests in `tests/test_platform_config_extension.py` + `tests/test_config_schema.py` passed. Full suite confirmed green (898 passed, 2 skipped) with no regression to the CFG-01 baseline.
- **Committed in:** `8622dda` (Task 2 GREEN commit — the corrected test construction was committed directly alongside the implementation, no separate fix commit needed since this was caught before the GREEN commit was made)

---

**Total deviations:** 1 auto-fixed (1 bug — test-construction fix, no production-code behavior change)
**Impact on plan:** No scope creep. `core/config_schema.py` still received ONLY the `ConfigDict` import + the single `extra="allow"` line for CFG-02, exactly as the plan required. The fix was isolated entirely to the test file's fixture-construction helper.

## Issues Encountered
None beyond the fixture-construction fix documented above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- CFG-02 fully delivered: a plugin can declare a previously-undeclared `platforms.<key>` section that loads and validates via its own model with `core/config_schema.py` touched by nothing beyond the single `extra="allow"` line; the 7 built-in platforms retain strict validation (invalid known-platform field still raises `ValidationError`); `get_platform_config` never raises `AttributeError` on missing config/key/section.
- Full suite green (898 passed, 2 skipped) — Phase 33 (Config Refactor) is now fully complete: CFG-01 (33-01) and CFG-02 (33-02) both landed, in the correct sequence (both touched `core/config_schema.py`; CFG-02 built on CFG-01's harmonized field set as required).
- Phase 34 (Feature Completion) can proceed with no blockers from Phase 33.

---
*Phase: 33-config-refactor*
*Completed: 2026-07-02*

## Self-Check: PASSED

All created/modified files found on disk; both task commit hashes (1624ef6, 8622dda) found in git log.
