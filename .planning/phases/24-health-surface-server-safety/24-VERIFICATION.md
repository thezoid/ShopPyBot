---
phase: 24-health-surface-server-safety
verified: 2026-06-12T00:00:00Z
status: human_needed
score: 3/3 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run bot on a headless Linux/Docker server with no audio device AND without pygame installed"
    expected: "Bot starts, runs its poll loop, and sound calls are silent no-ops; no ModuleNotFoundError, no pygame.error crash; logs show 'pygame not installed -- sound notifications disabled' or 'Audio device unavailable'"
    why_human: "CI environment has pygame installed and an audio device; the guarded-import path (ModuleNotFoundError branch) is tested by test_utils_imports_without_pygame via sys.modules injection, but end-to-end headless-server startup cannot be confirmed programmatically without a separate environment"
---

# Phase 24: Health Surface + Server Safety Verification Report

**Phase Goal:** Operators can query per-plugin liveness and error state from the CLI or web UI, receive alerts when a plugin degrades, and run the bot headlessly on a server without a pygame import crash.
**Verified:** 2026-06-12T00:00:00Z
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | REL-07: `get_status()` returns `{running, uptime_secs, plugins:{name:{status,last_heartbeat,consecutive_errors,items_checked,orders_confirmed}}}`, queryable from CLI (`shoppybot status`, `--json`, no network) and FastAPI `/status` (unchanged endpoint, JSON-serializable). HealthRegistry populated by `run_plugin` (heartbeat/items_checked), `supervise` (status), confirmation path (orders_confirmed). | VERIFIED | `core/service.py:73-85`: `get_status()` returns exact schema. `core/cli/status.py:54-61`: `handle_status` prints table or `--json`. `core/cli/__init__.py:169-182`: `status` subcommand registered with `--json` flag. `web/routes/api.py:24-28`: `GET /status` calls `svc.get_status()` -> `JSONResponse` (endpoint unchanged). `core/orchestrator.py:316-326`: `run_plugin` calls `health.heartbeat` + `health.set_status` + `health.inc_items_checked`. `core/orchestrator.py:451-452`: `_try_auto_buy` calls `health.inc_orders_confirmed`. `core/health.py:71-76`: `get_snapshot()` deep-copies, strips private `_` keys, result is JSON-safe (verified by `test_snapshot_is_json_serializable`). `tests/test_cli_status.py`: 4 tests confirm table output, JSON output, empty state, and no-socket (no-network) guarantee. All 755 tests pass. |
| 2 | REL-07: `consecutive_errors` crossing threshold dispatches `health_degraded` via existing fan-out, fires ONCE per episode (armed/disarmed), BEFORE `plugin_parked` (threshold `max(1, alert_on_errors-1)`). | VERIFIED | `core/orchestrator.py:136-150`: `supervise()` calls `health.record_error`, then reads live counter via `health.get_consecutive_errors(plugin_name)` (WR-01 fix applied: no full-copy snapshot), checks `degraded_threshold = max(1, n_budget - 1)`, gates on `not health.is_degraded_armed`, calls `dispatcher.notify(health_degraded)`, then `health.arm_degraded`. Re-arming on healthy run: `core/orchestrator.py:118-122` calls `health.disarm_degraded`. `core/health.py:54-64`: `arm_degraded`/`disarm_degraded`/`is_degraded_armed` are all implemented. `tests/test_supervisor.py`: 4 dedicated tests: `test_health_degraded_fires_once` (fires exactly 1x), `test_health_degraded_dedup` (no extra fires after arming), `test_health_degraded_rearms` (fires 2x after recovery), `test_health_degraded_distinct_from_parked` (both actions present, degraded precedes parked in call order). All pass. |
| 3 | SRV-01: Headless host -- silent no-op audio. `utils.py` imports successfully when pygame is NOT installed (guarded import, `ModuleNotFoundError`) AND when no audio device (`pygame.error` on `mixer.init`); `play_sound` is no-op + runtime `pygame.error` guarded; never crashes import. | VERIFIED | `utils.py:3-8`: `try: import pygame as _pygame; _PYGAME_AVAILABLE = True` / `except (ModuleNotFoundError, ImportError): _pygame = None; _PYGAME_AVAILABLE = False`. Import-guard catches both error types. `utils.py:16-29`: `_initialize_audio()` short-circuits False when `_PYGAME_AVAILABLE` is False; catches `_pygame.error` on `mixer.init`. `utils.py:35-51`: `play_sound` early-returns when `not _AUDIO_AVAILABLE`; wraps `load/play` in `except _pygame.error` (WR-03 fix). `tests/test_utils_audio.py:40-75`: `test_utils_imports_without_pygame` blocks pygame via `sys.modules["pygame"] = None`, reloads utils, asserts `_AUDIO_AVAILABLE=False`, `_PYGAME_AVAILABLE=False`, and `play_sound` returns None. WR-03 load/play error tests confirm no propagation. All 755 tests pass. |

**Score:** 3/3 truths verified

### P22 Invariant Check: supervise() exception containment

**CancelledError propagates:** `core/orchestrator.py:123-124`: `except asyncio.CancelledError: raise` -- correct; not absorbed by `except Exception`. Verified by `tests/test_supervisor.py::test_supervise_propagates_cancelled`.

**No exception reaches TaskGroup:** The `except Exception` block at line 125 absorbs all non-Cancel exceptions. Return on park (line 155) exits normally. `CancelledError` re-raise ensures TaskGroup shutdown propagates. Invariant intact after health hooks.

### get_snapshot() Deep-Copy Check

`core/health.py:71-76`: Returns a new dict comprehension (`{name: {k: v ...} ...}`) -- each inner record is also a new dict. Mutating the returned snapshot cannot modify the live `_plugins` store. Verified by `tests/test_health.py::test_snapshot_is_deep_copy`: sets `snap["PluginA"]["items_checked"] = 999`, then fetches a second snapshot and asserts the live value is still `1`.

### Credential Leak Check (new logs)

No credential content in new health-related log calls. `core/orchestrator.py` health log lines (`record_error`, `health_degraded`, `relaunching`) emit only class name and error type -- never CVV, API keys, or URLs. `core/service.py` startup logs emit only `pool_size` (integer) for proxy and integer/float caps for CAPTCHA -- no key values.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/health.py` | HealthRegistry class | VERIFIED | 77 lines, full API: heartbeat, set_status, record_error, reset_errors, inc_items_checked, inc_orders_confirmed, arm/disarm/is_degraded_armed, get_consecutive_errors, get_snapshot |
| `core/service.py` | BotService.get_status() | VERIFIED | Lines 73-85: returns exact REL-07 schema; `_health_registry` created in `__init__`, passed to `async_main` in both `start()` and `run()` |
| `core/orchestrator.py` | supervise() + run_plugin() health hooks | VERIFIED | All 6 mutator call sites confirmed (heartbeat, set_status x3, inc_items_checked, record_error, inc_orders_confirmed) |
| `core/cli/status.py` | handle_status with --json | VERIFIED | Table and JSON paths, no-network, heartbeat displayed as age (`Xs ago`) after IN-02 fix |
| `core/cli/__init__.py` | status subcommand registered | VERIFIED | Lines 169-182: `status` parser with `--json` flag, `set_defaults(func=handle_status)` |
| `web/routes/api.py` | GET /status endpoint | VERIFIED | Lines 24-28: unchanged endpoint calls `svc.get_status()` -> `JSONResponse` |
| `utils.py` | Guarded pygame import + no-op play_sound | VERIFIED | CR-01 + WR-03 fixes applied: guarded try/except import, `_PYGAME_AVAILABLE` flag, `_initialize_audio()` guards, `play_sound` wraps load/play |
| `tests/test_health.py` | HealthRegistry unit tests | VERIFIED | 10 tests including snapshot deep-copy, JSON-serializable, exact public key set |
| `tests/test_cli_status.py` | CLI status tests | VERIFIED | 4 tests: table, JSON, empty, no-network |
| `tests/test_utils_audio.py` | SRV-01 audio guard tests | VERIFIED | 7 tests including non-vacuous import-failure simulation (CR-01) and WR-03 load/play error swallow |
| `tests/test_supervisor.py` | REL-07 degraded alert tests | VERIFIED | 4 new tests: fires-once, dedup, re-arms, distinct-from-parked + all prior REL-01/02/03 tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `core/orchestrator.py::run_plugin` | `HealthRegistry.heartbeat` | `health.heartbeat(plugin_name)` line 318 | WIRED | Called at top of each poll cycle |
| `core/orchestrator.py::run_plugin` | `HealthRegistry.inc_items_checked` | `health.inc_items_checked(...)` line 326 | WIRED | Called per matched, non-purchased item |
| `core/orchestrator.py::supervise` | `HealthRegistry.set_status` | lines 120, 153, 159 | WIRED | Writes "running", "parked", "relaunching" |
| `core/orchestrator.py::supervise` | `HealthRegistry.record_error` + `get_consecutive_errors` | lines 138, 143 | WIRED | WR-01 fix: live counter read, not snapshot |
| `core/orchestrator.py::_try_auto_buy` | `HealthRegistry.inc_orders_confirmed` | line 452 | WIRED | Called after confirmed buy, outside retry loop |
| `core/service.py::get_status` | `HealthRegistry.get_snapshot` | line 84 | WIRED | Returns deep copy, schema-complete |
| `core/cli/status.py::handle_status` | `BotService.get_status` | line 56 | WIRED | No network call; in-process state only |
| `web/routes/api.py::get_status` | `BotService.get_status` | line 28 | WIRED | JSONResponse wraps snapshot |
| `utils.py` | `_pygame` (guarded) | try/except import block lines 3-8 | WIRED | `ModuleNotFoundError` caught; `_pygame = None` fallback |

### Data-Flow Trace (Level 4)

`get_status()` data source: `HealthRegistry._plugins` dict -- populated by live mutator calls from `run_plugin` and `supervise`. `get_snapshot()` performs a dict comprehension (deep copy) of live data. The data source is in-memory state written on every poll cycle; it is not static or empty by design (empty before the first poll, which is correct and reflected as `running=False`/empty plugins in pre-start state). FLOWING.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `python -m pytest -q` | `755 passed, 2 skipped` | PASS |
| `utils.py` imports without crashing | `python -c "import utils; print(utils._PYGAME_AVAILABLE)"` | N/A (covered by test_utils_imports_without_pygame via sys.modules injection) | PASS via test |
| `get_status()` returns correct schema | test_health.py::test_snapshot_public_keys_exact | exact key set `{status, last_heartbeat, consecutive_errors, items_checked, orders_confirmed}` | PASS |

### Probe Execution

Step 7c: SKIPPED -- no `scripts/*/tests/probe-*.sh` files found; phase has no declared probes.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| REL-07 | 24-01, 24-02, 24-03, 24-04 | Per-plugin health surface + degraded alert | SATISFIED | HealthRegistry, get_status(), supervise() hooks, CLI status, /status endpoint all implemented and tested |
| SRV-01 | 24-05 | Silent no-op audio on headless host | SATISFIED | Guarded import + _AUDIO_AVAILABLE guard + play_sound no-op; all audio tests pass |

### Anti-Patterns Found

No TBD, FIXME, or XXX markers found in phase-modified files. No stubs or placeholder returns detected in the implementation files reviewed.

### Human Verification Required

#### 1. Live Headless-Server Run (UAT Debt -- SRV-01)

**Test:** Deploy to a Linux server (or Docker container) that has no audio device and does not have pygame installed (e.g., `pip uninstall pygame`). Start the bot with `python main.py` or `shoppybot run`.
**Expected:** Bot starts without any `ModuleNotFoundError` or `pygame.error` traceback. Log output includes `"pygame not installed -- sound notifications disabled"` (or `"Audio device unavailable"` if pygame is installed but no device). The poll loop runs normally.
**Why human:** The import-failure branch is unit-tested via `sys.modules` injection in `test_utils_imports_without_pygame`, but an end-to-end boot on an actual device-less host cannot be confirmed programmatically in the current CI environment (pygame is installed and an audio device is present on the dev machine).

### Gaps Summary

No gaps. All three success criteria are fully implemented and verified against the actual codebase. The review-identified blocker (CR-01: bare `import pygame`) and all warnings (WR-01 snapshot race, WR-02 TOCTOU in `stop()`, WR-03 unguarded `load/play`) were fixed and confirmed present in `utils.py`, `core/health.py`, `core/orchestrator.py`, and `core/service.py` respectively. The test suite confirms 755 passed, 2 skipped, 0 failures -- matching the stated post-fix baseline.

Status is `human_needed` solely because of the deferred live headless-server UAT item (SRV-01 end-to-end). All automated checks pass.

---

_Verified: 2026-06-12T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
