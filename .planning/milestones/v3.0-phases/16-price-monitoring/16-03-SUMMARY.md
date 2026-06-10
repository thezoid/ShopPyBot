---
phase: 16-price-monitoring
plan: "03"
subsystem: orchestrator, service, startup
tags: [price-monitoring, orchestrator, dedup, tdd, run_in_executor]

dependency_graph:
  requires:
    - phase: 16-price-monitoring
      plan: "01"
      provides: append_price_history_sync, get_last_price_sync, get_item_price_config_sync, price dedup _sync functions
    - phase: 16-price-monitoring
      plan: "02"
      provides: RetailerPlugin.get_price() ABC hook, NotificationEvent price fields
  provides:
    - _check_and_buy price path: get_price() call + record + evaluate each poll cycle
    - _evaluate_price_triggers + _check_price_triggers + _build_price_drop_event helpers
    - Single price_drop alert per dedup window (price_alert_armed/price_last_notified)
    - BotService.get_price_history(name, limit) accessor for CLI plan (Plan 04)
    - startup seeds per-item target_price/price_drop_pct via update_item_price_config_sync
  affects:
    - core/orchestrator.py
    - core/service.py
    - main.py
    - tests/test_price_alert.py
    - tests/test_main_wiring.py

tech_stack:
  added: []
  patterns:
    - "Separate try/except for get_price() after check_availability -- never called when check_availability raised (Pitfall 2)"
    - "Read get_last_price_sync BEFORE append_price_history_sync to avoid same-cycle self-comparison (Pitfall 3)"
    - "Price dedup via price_alert_armed/price_last_notified -- never touches last_seen_available/last_notified (Pitfall 1)"
    - "Disarm on non-trigger: clear_price_alert_armed_sync when price recovers so next drop re-fires (Pitfall 5)"
    - "All sqlite3 calls via run_in_executor(None, fn, ...) in async context (T-16-DBLOCK)"
    - "Patch core.orchestrator module bindings (not models) for run_in_executor spy tests"

key_files:
  created:
    - tests/test_price_alert.py
  modified:
    - core/orchestrator.py
    - core/service.py
    - main.py
    - tests/test_main_wiring.py

decisions:
  - "_evaluate_price_triggers reads (target_price, price_drop_pct) from DB each cycle via get_item_price_config_sync; no config cache"
  - "test_price_alert dedup/disarm tests count only price_drop events; notifier also captures stock detected events which are expected and not asserted against"
  - "Spy tests patch core.orchestrator.get_last_price_sync (module-level binding) not models.get_last_price_sync so run_in_executor(None, fn) resolves the patched reference"
  - "test_main_wiring patches update_item_price_config_sync to prevent MagicMock->sqlite3 type error from seeding loop with mock items"

metrics:
  duration: 8min
  completed: 2026-06-10
  tasks: 3
  files: 5
---

# Phase 16 Plan 03: Orchestrator Price Wiring Summary

Price monitoring wired end-to-end: `_check_and_buy` calls `get_price()` each poll cycle, records non-None prices to `price_history`, evaluates absolute-target and percentage-drop triggers with separate dedup columns, dispatches a single `price_drop` event per armed window, and seeds per-item config at startup via `update_item_price_config_sync`; `BotService.get_price_history` accessor added for the CLI plan.

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-09T23:52:00Z
- **Completed:** 2026-06-10T00:02:40Z
- **Tasks:** 3 (RED already committed; GREEN for orchestrator + service/main + test corrections)
- **Files modified:** 5

## Accomplishments

- `core/orchestrator.py`: six new imports from models, five pure helpers (`_cents_to_display`, `_pct_from_target`, `_pct_drop_from_last`, `_check_price_triggers`, `_build_price_drop_event`), one async helper `_evaluate_price_triggers`, and `_check_and_buy` extended with the price path after `check_availability`
- get_price() called in separate try/except; `price_cents > 0` guard (T-16-NEG)
- `get_last_price_sync` read before `append_price_history_sync` per Pitfall 3
- Dedup: armed state via `price_alert_armed`; disarms on price recovery via `clear_price_alert_armed_sync` (Pitfall 5)
- Stock dedup columns (`last_seen_available`, `last_notified`) untouched by price path (Pitfall 1, T-16-DEDUP)
- `core/service.py`: `BotService.get_price_history(name, limit)` accessor; name-to-link via `get_items_sync()` exact match
- `main.py`: per-item `update_item_price_config_sync` loop after `add_items` (Pitfall 7)
- Full suite: 518 passed, 2 skipped (up from 507; 11 new tests in test_price_alert.py)

## Task Commits

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 (RED) | Failing price alert tests | `7ac5f2e` | tests/test_price_alert.py |
| 2 (GREEN) | Orchestrator price path + trigger eval + dispatch | `1a3bda3` | core/orchestrator.py |
| 3 | Startup config seeding + BotService.get_price_history | `d3380ee` | core/service.py, main.py |
| fix | Correct test spy patches + dedup count + main_wiring | `76df36b` | tests/test_price_alert.py, tests/test_main_wiring.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test spy patches targeted wrong module binding**

- **Found during:** Task 2 GREEN phase
- **Issue:** `test_last_price_read_before_append` patched `models.get_last_price_sync` but orchestrator binds the name at import time via `from models import get_last_price_sync`; `run_in_executor(None, get_last_price_sync, ...)` holds the original reference, so the module-level patch was never intercepted.
- **Fix:** Changed patches to `core.orchestrator.get_last_price_sync` and `core.orchestrator.append_price_history_sync` (the module's own binding).
- **Files modified:** tests/test_price_alert.py
- **Commit:** 76df36b

**2. [Rule 1 - Bug] Dedup/disarm tests counted all events including stock detected**

- **Found during:** Task 2 GREEN phase
- **Issue:** `test_price_alert_dedup_fires_once` and `test_price_alert_disarms_on_recovery` asserted `len(notifier.events) == 1` but the fake_plugin with `available=True` also triggers a stock `detected` event; both `price_drop` and `detected` were captured by the same notifier.
- **Fix:** Changed assertions to count only `price_drop` events via list comprehension filter.
- **Files modified:** tests/test_price_alert.py
- **Commit:** 76df36b

**3. [Rule 1 - Bug] test_main_wiring broke after main.py seeding loop added**

- **Found during:** Task 3 GREEN phase
- **Issue:** Existing `test_main_wiring.py` tests patch `initialize_db` and `add_items` but not `update_item_price_config_sync`; the new seeding loop iterates `cfg.available.items` and passes `MagicMock.target_price` to SQLite, raising `sqlite3.ProgrammingError: type 'MagicMock' is not supported`.
- **Fix:** Added `patch.object(main_module, "update_item_price_config_sync")` to the four affected test contexts.
- **Files modified:** tests/test_main_wiring.py
- **Commit:** 76df36b

## Known Stubs

None. All implemented fields are wired and tested end-to-end.

## Threat Surface Scan

No new trust boundaries introduced. All mitigations from threat register applied:

| Threat | Mitigation Applied |
|--------|-------------------|
| T-16-NEG | `price_cents is not None and price_cents > 0` guard before append/evaluate |
| T-16-DEDUP | price path uses only `price_alert_armed`/`price_last_notified`; column independence asserted by `test_price_dedup_independent` |
| T-16-DBLOCK | All sqlite3 calls via `run_in_executor(None, fn, ...)` |
| T-16-SQLI | Uses Plan-01 parameterized models functions; no new raw SQL |

## Self-Check: PASSED

- `core/orchestrator.py` contains `_evaluate_price_triggers`: FOUND
- `core/service.py` contains `get_price_history`: FOUND
- `main.py` contains `update_item_price_config_sync`: FOUND
- `tests/test_price_alert.py` exists: FOUND
- Commit `7ac5f2e` (RED): FOUND
- Commit `1a3bda3` (Task 2): FOUND
- Commit `d3380ee` (Task 3): FOUND
- Commit `76df36b` (fix): FOUND
- 518 passed, 2 skipped: VERIFIED
