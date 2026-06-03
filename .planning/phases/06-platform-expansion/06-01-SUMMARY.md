---
phase: 06-platform-expansion
plan: 01
subsystem: config
tags: [pydantic, config-schema, anti-detection, nodriver, pytest]

# Dependency graph
requires:
  - phase: 05-notifications
    provides: AppConfig / PlatformsConfig base with AmazonPlatformConfig/BestBuyPlatformConfig
provides:
  - 5 new Pydantic platform submodels (Walmart, Target, GameStop, SquareEnix, NewEgg) with min_delay/max_delay/headless/user_agents
  - headless and user_agents fields added to AmazonPlatformConfig and BestBuyPlatformConfig (SC3)
  - DEFAULT_USER_AGENTS module-level constant (ANTI-02 global fallback UA pool)
  - mock_nodriver_start conftest fixture for headless/UA assertion without Chrome launch
  - 7 skip-marked test scaffolds for Plans 06-02 through 06-05
affects:
  - 06-02 (orchestrator jitter -- reads min_delay/max_delay from platform config)
  - 06-03 (walmart/target/gamestop plugins -- read headless/user_agents)
  - 06-04 (squareenix/newegg plugins -- read headless/user_agents)
  - 06-05 (SECURITY.md rows verification)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-platform anti-detection config submodel: min_delay/max_delay with Field(ge=0.0), headless bool, user_agents list[str]"
    - "Config attribute squareenix (no underscore) matches plugin platform_key convention"
    - "SC3 pattern: declared headless field on submodel prevents extra=ignore silently dropping YAML key"
    - "mock_nodriver_start fixture: patches nodriver.start, records kwargs, yields recorder with .last_kwargs/.calls"

key-files:
  created:
    - tests/test_plugin_walmart.py
    - tests/test_plugin_target.py
    - tests/test_plugin_gamestop.py
    - tests/test_plugin_squareenix.py
    - tests/test_plugin_newegg.py
    - tests/test_orchestrator_jitter.py
    - tests/test_security_md.py
  modified:
    - core/config_schema.py
    - tests/conftest.py
    - tests/test_config_schema.py

key-decisions:
  - "squareenix config attribute uses no underscore to match plugin platform_key='squareenix' (RESEARCH Pitfall 4)"
  - "Amazon/BestBuy retain delay_seconds/delay_jitter naming; harmonization to min_delay/max_delay deferred (out of Phase-6 scope)"
  - "DEFAULT_USER_AGENTS placed at module level in config_schema.py (not a separate anti_detection.py helper)"
  - "User-agent override uses browser_args pattern (Option A) per RESEARCH Pattern 4 recommendation"

patterns-established:
  - "Pattern: new platform submodel = 4 fields (min_delay Field ge=0, max_delay Field ge=0, headless bool=True, user_agents list[str] default_factory=list)"
  - "Pattern: headless on platform submodel prevents extra=ignore silent drop -- always declare as a Pydantic field"
  - "Pattern: mock_nodriver_start fixture yields recorder object; test asserts recorder.last_kwargs['headless'] etc."

requirements-completed: [ANTI-01, ANTI-02, ANTI-03]

# Metrics
duration: 15min
completed: 2026-06-03
---

# Phase 6 Plan 01: Platform Expansion Config Foundation Summary

**Pydantic config schema extended with 5 new platform anti-detection submodels (min_delay/max_delay/headless/user_agents), Amazon/BestBuy headless field added (SC3), DEFAULT_USER_AGENTS pool constant defined, and 7 downstream test scaffolds created**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-03T00:00:00Z
- **Completed:** 2026-06-03T00:15:00Z
- **Tasks:** 2
- **Files modified:** 9 (2 modified, 7 created)

## Accomplishments

- Extended `core/config_schema.py` with 5 new Pydantic submodels (Walmart, Target, GameStop, SquareEnix, NewEgg) each carrying `min_delay`/`max_delay` with `Field(ge=0.0)` validation, `headless: bool = True`, and `user_agents: list[str]`; registered all 5 on `PlatformsConfig`
- Added `headless: bool = True` and `user_agents` to both `AmazonPlatformConfig` and `BestBuyPlatformConfig` (SC3 requirement: prevents `extra="ignore"` from silently dropping `platforms.amazon.headless: false` in YAML)
- Added `DEFAULT_USER_AGENTS` module-level constant (5 plausible Chrome/Firefox UA strings) and `mock_nodriver_start` conftest fixture; created 7 skip-marked test scaffolds for downstream plans

## Task Commits

1. **Task 1: Extend config_schema + tests** - `4a127a7` (feat)
2. **Task 2: mock_nodriver_start fixture + 7 scaffolds** - `d9e3c6c` (feat)

**Plan metadata:** (see final docs commit below)

## Files Created/Modified

- `core/config_schema.py` - Added `Field` import, `DEFAULT_USER_AGENTS` constant, `WalmartPlatformConfig`, `TargetPlatformConfig`, `GameStopPlatformConfig`, `SquareEnixPlatformConfig`, `NeweggPlatformConfig`; added `headless`/`user_agents` to Amazon/BestBuy configs; updated `PlatformsConfig`
- `tests/conftest.py` - Added `mock_nodriver_start` fixture
- `tests/test_config_schema.py` - Added 7 new tests covering all new schema behaviors
- `tests/test_plugin_walmart.py` - Skip scaffold for Plan 06-03 (PLG-04, ANTI-02/03, SC4)
- `tests/test_plugin_target.py` - Skip scaffold for Plan 06-03 (PLG-05, SC4)
- `tests/test_plugin_gamestop.py` - Skip scaffold for Plan 06-03 (PLG-06, SC4)
- `tests/test_plugin_squareenix.py` - Skip scaffold for Plan 06-04 (PLG-07)
- `tests/test_plugin_newegg.py` - Skip scaffold for Plan 06-04 (PLG-08)
- `tests/test_orchestrator_jitter.py` - Skip scaffold for Plan 06-02 (ANTI-01)
- `tests/test_security_md.py` - Skip scaffold for Plan 06-05 (SC4 SECURITY.md rows)

## Decisions Made

- `squareenix` (no underscore) used as both the PlatformsConfig attribute name and the expected `platform_key` value in future plugins; matches RESEARCH Pitfall 4 guidance
- `AmazonPlatformConfig`/`BestBuyPlatformConfig` retain legacy `delay_seconds`/`delay_jitter` field names; a comment in `config_schema.py` documents the intentional difference
- `DEFAULT_USER_AGENTS` placed at module level in `config_schema.py` (not a separate helper module) per RESEARCH open question resolution

## Deviations from Plan

None - plan executed exactly as written. SC3 was already the mandatory first task; all field names, constant names, and fixture names match the plan specification.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 06-02 can read `min_delay`/`max_delay` from any `PlatformsConfig` attribute via `getattr`
- Plans 06-03/04 can read `headless`/`user_agents` from all 7 platform configs; mock_nodriver_start fixture is available for their tests
- Plan 06-05 scaffold exists; SECURITY.md row tests are pre-registered
- Full suite: 119 passed, 7 skipped, 0 failures

## Self-Check: PASSED

- `core/config_schema.py` exists and contains WalmartPlatformConfig, DEFAULT_USER_AGENTS, squareenix, headless on Amazon/BestBuy
- `tests/conftest.py` contains mock_nodriver_start
- All 7 scaffold files exist and are collectable by pytest
- Commits `4a127a7` and `d9e3c6c` verified in git log

---
*Phase: 06-platform-expansion*
*Completed: 2026-06-03*
