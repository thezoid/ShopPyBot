---
phase: 33-config-refactor
plan: 01
subsystem: config
tags: [pydantic, config-schema, orchestrator, jitter, back-compat-shim]

# Dependency graph
requires:
  - phase: 06-platform-expansion
    provides: the 5 community platform models (Walmart/Target/GameStop/SquareEnix/Newegg) with min_delay/max_delay fields and _get_plugin_sleep's original min_delay/max_delay consumption
provides:
  - Canonical delay_seconds/delay_jitter field names on all 7 platform models
  - _shim_legacy_delay_fields back-compat shim (model_validator mode="before") mapping legacy min_delay/max_delay -> canonical fields without clobbering explicit canonical values
  - _get_plugin_sleep reading canonical fields uniformly for all 7 platforms (Amazon/BestBuy poll jitter activated, Option A)
  - sample.config.yml documentation of canonical names + back-compat note
affects: [33-02-config-refactor (CFG-02 generic per-platform config, builds on this harmonized field set)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared model_validator(mode='before') shim mirrors the existing AppConfig.warn_legacy_keys idiom, scoped to per-platform submodels"
    - "delay_seconds + random.uniform(0, delay_jitter) base+jitter formula, matching core/retry.py's compute_delay idiom"

key-files:
  created: []
  modified:
    - core/config_schema.py
    - core/orchestrator.py
    - sample.config.yml
    - tests/test_config_schema.py
    - tests/test_orchestrator_jitter.py

key-decisions:
  - "Option A (pre-accepted in 33-CONTEXT.md/33-RESEARCH.md): _get_plugin_sleep reads canonical delay_seconds/delay_jitter uniformly for all 7 platforms, activating Amazon/BestBuy poll-cadence jitter (30s flat -> 30-40s jittered) for the first time -- recorded below as an operator-UAT item."
  - "Shim guard is has_legacy and not has_canonical -- explicit canonical values are never clobbered even when legacy keys are also present in the same construction."
  - "No clamping of the derived delay_jitter -- an inverted/negative legacy range (max_delay < min_delay) flows into Field(ge=0.0) and raises ValidationError naturally, matching the codebase's existing fail-loudly convention."
  - "Two new/renamed jitter tests deliberately use numeric ranges disjoint from pre-change defaults/fallback values (walmart canonical test uses 20/5 instead of 8/7; amazon activation test passes poll_interval=5.0 instead of 30.0) to avoid a boundary/default-coincidence false RED-pass -- discovered during the RED verification step and fixed before GREEN (TDD fail-fast gate)."

patterns-established:
  - "Pattern: back-compat field-rename shim -- module-level _shim_legacy_delay_fields() + per-model @model_validator(mode='before') classmethod, DRY across N models sharing the same legacy->canonical mapping."

requirements-completed: [CFG-01]

# Metrics
duration: 6min
completed: 2026-07-02
---

# Phase 33 Plan 01: Config Refactor - Canonical Delay Fields Summary

**Harmonized platform delay-config fields to `delay_seconds`/`delay_jitter` across all 7 platforms via a back-compat shim for the 5 community plugins, activating Amazon/BestBuy poll-cadence jitter (30s flat -> 30-40s) for the first time (Option A).**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-02T22:58:00Z (approx, first Read calls)
- **Completed:** 2026-07-02T23:05:30Z
- **Tasks:** 3 (RED, GREEN schema, GREEN orchestrator)
- **Files modified:** 5

## Accomplishments
- All 5 community platform models (Walmart/Target/GameStop/SquareEnix/Newegg) renamed from `min_delay`/`max_delay` to canonical `delay_seconds`/`delay_jitter`, each wired to a shared `_shim_legacy_delay_fields` back-compat shim
- Amazon/BestBuy `delay_seconds`/`delay_jitter` tightened to `Field(ge=0.0)` for schema consistency
- `_get_plugin_sleep` reads canonical fields uniformly for all 7 platforms; distribution-equivalence proven exact for the 5 community plugins, Amazon/BestBuy jitter activation proven by test
- `sample.config.yml` documents canonical names + back-compat note near `platforms:`
- Full suite green: 894 passed, 2 skipped (baseline 889 + 5 net-new tests)

## Task Commits

Each task was committed atomically (TDD RED -> GREEN):

1. **Task 1: RED — failing tests for canonical fields, shim, distribution equivalence, Amazon jitter activation** - `95e3100` (test)
2. **Task 2: GREEN — shared legacy-delay shim, 5 community models renamed, Amazon/BestBuy bounds tightened, sample.config.yml documented** - `48c28ce` (feat)
3. **Task 3: GREEN — `_get_plugin_sleep` reads canonical fields uniformly (Option A jitter activation)** - `a19649d` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `core/config_schema.py` - `_shim_legacy_delay_fields` module function; 5 community models renamed to `delay_seconds`/`delay_jitter` + `_legacy_delay_shim` validator each; Amazon/BestBuy `Field(ge=0.0)` tightening
- `core/orchestrator.py` - `_get_plugin_sleep` reads `delay_seconds`/`delay_jitter` via getattr, returns `delay_seconds + random.uniform(0, delay_jitter)`
- `sample.config.yml` - comment block above `platforms:` documenting canonical names + back-compat shim
- `tests/test_config_schema.py` - `test_walmart_platform_fields_load_from_yaml`/`test_squareenix_platform_config_reachable` updated to canonical assertions; added `test_legacy_delay_shim_maps_to_canonical`, `test_canonical_delay_precedence_over_legacy`, `test_legacy_delay_shim_emits_deprecation_warning`
- `tests/test_orchestrator_jitter.py` - added `test_jitter_in_range_for_walmart_canonical_config`, `test_legacy_community_config_preserves_delay_distribution`; renamed+rewrote `test_fallback_for_amazon_shaped_config` -> `test_amazon_config_activates_poll_jitter`

## Decisions Made
- Option A (Amazon/BestBuy jitter activation) implemented exactly as pre-accepted in 33-CONTEXT.md/33-RESEARCH.md — no per-platform hardcoding added to `_get_plugin_sleep`.
- Shim mapping implemented exactly per the RESEARCH.md-verified formula: `delay_seconds := min_delay`, `delay_jitter := max_delay - min_delay`, no clamping.
- SquareEnix's no-underscore YAML key (`squareenix`) preserved unchanged — only its delay fields were touched.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed two RED-phase tests that passed for the wrong reason before any implementation**
- **Found during:** Task 1 RED verification (`pytest tests/test_config_schema.py tests/test_orchestrator_jitter.py -q` after writing the new tests, before touching `config_schema.py`/`orchestrator.py`)
- **Issue:** Per the TDD fail-fast rule, all new/updated tests must genuinely fail pre-implementation. Two did not: (a) `test_jitter_in_range_for_walmart_canonical_config` constructed `WalmartPlatformConfig(delay_seconds=8.0, delay_jitter=7.0)` — pre-shim, pydantic's default `extra="ignore"` silently dropped those unknown kwargs and the model fell back to its own `min_delay=8.0`/`max_delay=15.0` defaults, which happen to produce the identical `[8.0, 15.0]` range the test asserted, passing for the wrong reason. (b) `test_amazon_config_activates_poll_jitter` (formerly `test_fallback_for_amazon_shaped_config`) called `_get_plugin_sleep(plugin, poll_interval=30.0)` and asserted `30.0 <= result <= 40.0` — pre-GREEN, the orchestrator's fallback branch returns exactly `poll_interval` (30.0), which trivially satisfies the inclusive lower bound of the new expected range, again passing for the wrong reason.
- **Fix:** Changed the walmart canonical test to use `delay_seconds=20.0, delay_jitter=5.0` (range `[20.0, 25.0]`), a range deliberately disjoint from the legacy defaults `[8.0, 15.0]` so it can only pass once the model genuinely reads canonical fields. Changed the amazon activation test to pass `poll_interval=5.0` (disjoint from `[30.0, 40.0]`) so it can only pass once `_get_plugin_sleep` actually computes the jittered value instead of falling back.
- **Files modified:** `tests/test_orchestrator_jitter.py` (both changes were made within Task 1, before the RED commit)
- **Verification:** Re-ran the targeted RED suite; all 8 new/updated tests failed genuinely (confirmed via full traceback inspection), 29 pre-existing tests stayed green, no import errors. GREEN (Tasks 2-3) then made all 8 pass for the correct reason.
- **Committed in:** `95e3100` (Task 1 RED commit — the corrected assertions were committed directly, no separate fix commit needed since this was caught before the RED commit was made)

---

**Total deviations:** 1 auto-fixed (1 bug — TDD RED-phase test-quality fix)
**Impact on plan:** Necessary for TDD process integrity; no scope creep. The plan's literal assertion text (`30.0 <= result <= 40.0`, `[8.0, 15.0]`) was preserved in the final assertions — only the *input* values used to drive those assertions were adjusted to avoid a coincidental pre-implementation pass.

## Issues Encountered
None beyond the RED-phase test-quality fix documented above.

## Operator-UAT Item (record per plan instruction)

**Amazon/BestBuy availability-poll cadence changed:** was a flat `poll_interval` (default 30s, zero variance); is now `delay_seconds + random.uniform(0, delay_jitter)` = 30-40s jittered, using each plugin's existing (previously dead) config defaults. This affects only the inter-poll-cycle sleep between availability checks — no DOM/checkout/CAPTCHA timing is touched. This is a documented, accepted behavior change (Option A, pre-decided in 33-CONTEXT.md at Claude's discretion while the operator was away) and is observable only against a live run. Already tracked in 33-VALIDATION.md as a Manual-Only Verification; no further action required to close CFG-01, but the operator should be aware live Amazon/BestBuy polling now varies 30-40s instead of a flat 30s.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- CFG-01 fully delivered: canonical field names on all 7 platform models, back-compat shim proven exact and non-clobbering, distribution equivalence proven for the 5 community plugins, Amazon/BestBuy jitter activation proven and documented.
- Full suite green (894 passed, 2 skipped) — CFG-02 (33-02, generic per-platform config) can proceed on this harmonized field set with no blockers.
- No `min_delay`/`max_delay` field DECLARATIONS remain anywhere in `core/config_schema.py`; `core/orchestrator.py` has zero remaining `min_delay`/`max_delay` reads (grep-verified).

---
*Phase: 33-config-refactor*
*Completed: 2026-07-02*

## Self-Check: PASSED

All created/modified files found on disk; all 3 task commit hashes (95e3100, 48c28ce, a19649d) found in git log.
