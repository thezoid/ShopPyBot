---
phase: 06-platform-expansion
plan: 01
subsystem: foundation
tags: [python, nodriver, pydantic, abc, schema, red-skeletons, wave-0]
dependency_graph:
  requires: []
  provides:
    - RetailerPlugin.open() async no-op default
    - RetailerPlugin.next_delay() default returning random.uniform(min_delay, max_delay)
    - RetailerPlugin.min_delay / max_delay class-attr defaults (3.0 / 8.0)
    - plugin_registry.discover_async awaiting inst.open() with skip-on-failure
    - plugin_registry._instantiate plumbing user_agents to plugins
    - driver.DEFAULT_USER_AGENTS + build_driver(headless, user_agents) signature
    - PlatformConfig.min_delay/max_delay/headless + validate_delay_range
    - PlatformConfig.credentials Optional
    - AppSettings.user_agents field
    - fakeBrowser pytest fixture
    - 5 RED plugin skeletons for Wave 1 (walmart/target/gamestop/squareenix/newegg)
  affects: [Wave 1 plans 06-02 through 06-06, Plan 06-07 main wiring]
tech-stack:
  added: [nodriver==0.50.3]
  patterns: [async no-op ABC defaults, additive ABC versioning, RED skeleton TDD handoff]
key-files:
  created:
    - tests/test_plugins_walmart.py
    - tests/test_plugins_target.py
    - tests/test_plugins_gamestop.py
    - tests/test_plugins_squareenix.py
    - tests/test_plugins_newegg.py
    - .planning/phases/06-platform-expansion/06-01-SUMMARY.md
  modified:
    - requirements.txt
    - plugin_base.py
    - plugin_registry.py
    - driver.py
    - config_schema.py
    - plugins/shopbot_plugin_amazon.py
    - plugins/shopbot_plugin_bestbuy.py
    - tests/conftest.py
    - tests/test_plugin_base.py
    - tests/test_registry_stagger.py
    - tests/test_driver_setup.py
    - tests/test_config_schema.py
    - tests/test_plugin_registry.py
decisions:
  - "ABC additive change: open() and next_delay() added as non-abstract defaults so Selenium plugins inherit no-op. PLUGIN_API_VERSION stays at 1 because no existing plugin contract breaks."
  - "user_agents kwarg added to Amazon/BestBuy __init__ as additive compat (currently stored but unused). Plan 06-07 wires it through to build_driver."
  - "build_driver chooses UA per call (random.choice on every invocation, no module-level cache) so plugin restarts present a fresh UA."
  - "PlatformConfig.credentials becomes Optional so check-only plugins (Walmart/Target/NewEgg) can declare a platforms.<name>: {enabled: true} block without dummy credentials."
  - "RED skeletons place imports INSIDE test functions (not at module top) so pytest collection succeeds; each test fails with ModuleNotFoundError when invoked. This lets Wave 1 plans overwrite the file cleanly."
metrics:
  duration: "~25 minutes"
  completed: 2026-05-15
---

# Phase 6 Plan 01: Foundation and RED Skeletons Summary

Wave 0 foundation for Phase 6 platform expansion: pin nodriver, extend the RetailerPlugin ABC with two non-abstract defaults (open, next_delay) and class-attr delay bounds, extend build_driver with headless and UA rotation kwargs, extend PlatformConfig with delay range + headless + optional credentials, plumb user_agents through plugin_registry, and ship 5 RED plugin skeletons that Wave 1 plans 06-02 through 06-06 will own and rewrite.

## What Was Built

**Dependencies**
- requirements.txt: `nodriver==0.50.3` pinned (current latest at execution time, verified via `pip index versions nodriver`).

**ABC contract (plugin_base.py)**
- Added `async def open(self) -> None` non-abstract no-op default. Selenium plugins inherit; nodriver plugins override to build self.driver asynchronously.
- Added `def next_delay(self) -> float` non-abstract default returning `random.uniform(self.min_delay, self.max_delay)` for ANTI-01 jitter.
- Added class attrs `min_delay = 3.0` and `max_delay = 8.0` as defensive defaults.
- `PLUGIN_API_VERSION` stays at 1 (additive change).

**Plugin registry (plugin_registry.py)**
- `_instantiate` reads `app_config.app.user_agents` via a safe getattr chain (`_safe_user_agents`) and passes as kwarg to plugin __init__.
- `discover_async` awaits `inst.open()` after `_load_and_instantiate` returns and before the next stagger sleep. Exceptions caught; WARNING logged with `type(inst).__name__`; plugin skipped (not added to registry).

**Driver factory (driver.py)**
- Added `DEFAULT_USER_AGENTS` module constant (6 Chrome desktop UAs: Win10/Win11, macOS, Linux, Chrome 135-140).
- `build_driver` signature extended with `headless: bool = False, user_agents: list[str] | None = None`.
- Replaced hardcoded `CHROME_UA` arg with `random.choice(user_agents or DEFAULT_USER_AGENTS)` per call.
- `headless=True` appends `--headless=new` (not the deprecated bare `--headless`).
- `CHROME_UA` constant retained for backwards compat but no longer used.

**Schema (config_schema.py)**
- `PlatformConfig.credentials` becomes `PlatformCredentials | None = None`.
- Added `min_delay: float = 3.0`, `max_delay: float = 8.0`, `headless: bool = False` fields.
- Added `validate_delay_range` model_validator (mode=after) raising ValueError on min_delay <= 0, max_delay <= 0, or min_delay > max_delay.
- `AppSettings.user_agents: list[str] | None = None` added at the app level.

**Selenium plugin back-compat**
- `plugins/shopbot_plugin_amazon.py` and `plugins/shopbot_plugin_bestbuy.py` __init__ now accept `user_agents=None` kwarg (stored as `self._user_agents`, currently unused). Plan 06-07 wires it to build_driver.

**Tests: GREEN extensions**
- test_plugin_base.py: open() coroutine no-op, next_delay range under defaults and instance overrides, class-attr defaults.
- test_registry_stagger.py: open() awaited exactly once per plugin, plugins with raising open() are skipped with WARNING.
- test_driver_setup.py: DEFAULT_USER_AGENTS shape, --headless=new presence (and absence by default), UA rotation via monkeypatched random.choice, user_agents kwarg override.
- test_config_schema.py: delay defaults, custom delays, validator rejects inverted/zero/negative ranges, credentials Optional, AppSettings.user_agents.
- conftest.py: `fakeBrowser` AsyncMock fixture (.get, .stop, .select, .select_all) for Wave 1.

**Tests: RED skeletons**
- tests/test_plugins_walmart.py (6 tests: importable, subclass, domain_pattern, risky autobuy gate off/on, PerimeterX risk note logged once)
- tests/test_plugins_target.py (5 tests)
- tests/test_plugins_gamestop.py (6 tests: includes captcha pause non-blocking)
- tests/test_plugins_squareenix.py (5 tests)
- tests/test_plugins_newegg.py (5 tests)

All 27 skeleton tests fail today with `ModuleNotFoundError` (plugin modules do not exist). Imports are inside test functions so collection succeeds.

## Verification

| Check | Result |
| --- | --- |
| `grep -n "nodriver==0.50.3" requirements.txt` | 1 match |
| `grep -n "async def open" plugin_base.py` | match |
| `grep -n "def next_delay" plugin_base.py` | match |
| `grep -n "await inst.open()" plugin_registry.py` | match |
| `grep -n "--headless=new" driver.py` | match |
| `grep -n "DEFAULT_USER_AGENTS" driver.py` | match |
| `grep -n "validate_delay_range" config_schema.py` | match |
| `grep -n "credentials: PlatformCredentials \| None" config_schema.py` | match |
| Foundation test files | 45 passed |
| RED skeleton files | 27 failed (all ModuleNotFoundError) |
| Pre-existing Phase 1-5 suite (regression) | 281 passed (was 261 baseline; +20 new GREEN tests) |

Pre-existing collection errors (`tests/test_notifiers_sms.py`: missing `twilio` install; `tests/test_utils.py`: stale `make_tiny` import) are unrelated to Phase 6 and were skipped via `--ignore` during the regression run. Twilio is pinned in requirements.txt; module just needs a `pip install` in the local venv. Out of scope for this plan.

## Deviations from Plan

None. Plan executed exactly as written.

The plan instructed adjusting Amazon/BestBuy `__init__` signatures to accept `user_agents=None`; while running the foundation regression, three pre-existing tests in `tests/test_plugin_registry.py` failed because their inline plugin string templates used the old `(platform_config, *, cvv=None, driver_path=None)` signature. Updating those templates to include `user_agents=None` is the minimal back-compat fix (same pattern explicitly called out in the plan for the real plugins). Tracked under task 1 commit; functionally identical to the additive plugin __init__ update.

## Commits

- `94254c5` feat(06-01): foundation for Phase 6 (nodriver, ABC, driver, schema)
- `38ed20b` test(06-01): GREEN foundation tests + RED Wave 1 plugin skeletons

## Wave 1 Handoff

Plans 06-02 (Walmart), 06-03 (Target), 06-04 (GameStop), 06-05 (Square Enix), 06-06 (NewEgg) each OWN one plugin file under `plugins/` and one test file under `tests/`. The RED skeletons in `tests/test_plugins_<retailer>.py` are placeholders intended for full rewrite by their respective Wave 1 plan: the import-error skeleton can be replaced wholesale with the GREEN test suite that Wave 1 writes. Plan 06-07 wires `user_agents` from `app_config.app.user_agents` through Amazon/BestBuy build_driver calls and updates `main.py` orchestration.

## Self-Check: PASSED

- requirements.txt contains `nodriver==0.50.3`: FOUND
- plugin_base.py contains `async def open` and `def next_delay`: FOUND
- plugin_registry.py contains `await inst.open()`: FOUND
- driver.py contains `--headless=new` and `DEFAULT_USER_AGENTS`: FOUND
- config_schema.py contains `validate_delay_range` and Optional credentials: FOUND
- All 5 RED skeleton files exist: FOUND
- Commits `94254c5` and `38ed20b`: FOUND in git log
- Phase 1-5 regression (281 passed): FOUND
