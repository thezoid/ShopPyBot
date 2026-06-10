---
phase: 16-price-monitoring
plan: 01
subsystem: database
tags: [sqlite, models, pydantic, price-monitoring, idempotent-migration]

# Dependency graph
requires:
  - phase: 15-plugin-ecosystem-registry
    provides: RetailerPlugin ABC and BotService patterns that price monitoring extends

provides:
  - price_history append-only SQLite table with item_link, price_cents INTEGER, currency, scraped_at
  - Four idempotent items columns: target_price, price_drop_pct, price_alert_armed, price_last_notified
  - Eight parameterized _sync models functions for price history and price-alert dedup
  - ItemConfig optional target_price (int cents) and price_drop_pct (float) Pydantic fields

affects: [16-02, 16-03, 16-04, orchestrator, cli]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Idempotent migration: PRAGMA table_info guard + ALTER TABLE ADD COLUMN + CREATE TABLE IF NOT EXISTS"
    - "Separate dedup columns for price alerts vs stock alerts (never share last_seen_available/last_notified)"
    - "All SQL parameterized with ? placeholders -- no f-strings or .format in SQL literals (T-16-SQLI)"
    - "Integer cents throughout: price_cents INTEGER NOT NULL, target_price INTEGER, price_drop_pct REAL"

key-files:
  created:
    - tests/test_price_history.py
  modified:
    - models.py
    - core/config_schema.py

key-decisions:
  - "Separate-update strategy: update_item_price_config_sync called after add_items_sync; add_items_sync signature unchanged (no tuple shape break)"
  - "price_alert_armed and price_last_notified columns are strictly separate from last_seen_available/last_notified"
  - "get_last_price_sync reads from price_history (newest-first); caller must read BEFORE append to get previous price"
  - "target_price NULL = monitoring off; price_drop_pct NULL = monitoring off; both NULL allowed"

patterns-established:
  - "Price dedup column guard: set_price_alert_armed_sync only touches price_alert_armed + price_last_notified"
  - "All new models _sync functions follow get_db_connection() context manager pattern"

requirements-completed: [PRICE-01, PRICE-02, PRICE-05]

# Metrics
duration: 5min
completed: 2026-06-09
---

# Phase 16 Plan 01: Price Monitoring Data Layer Summary

**Idempotent SQLite migration adding price_history table, four items columns, eight parameterized _sync functions, and Optional ItemConfig price fields for per-item price monitoring**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-09T23:21:21Z
- **Completed:** 2026-06-09T23:26:11Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 3

## Accomplishments

- price_history table (id, item_link, price_cents INTEGER, currency TEXT DEFAULT 'USD', scraped_at) via idempotent CREATE TABLE IF NOT EXISTS
- Four new items columns added via PRAGMA table_info guard: target_price INTEGER, price_drop_pct REAL, price_alert_armed INTEGER NOT NULL DEFAULT 0, price_last_notified TEXT
- Eight _sync functions: append_price_history_sync, get_price_history_sync, get_last_price_sync, get_price_alert_state_sync, set_price_alert_armed_sync, clear_price_alert_armed_sync, update_item_price_config_sync, get_item_price_config_sync
- ItemConfig gains Optional[int] target_price and Optional[float] price_drop_pct; all existing fields unchanged
- Full suite: 501 passed, 2 skipped (up from 493 baseline; 8 new tests added, 0 regressions)

## Task Commits

1. **Task 1: Wave 0 -- failing migration + models tests** - `19a7376` (test)
2. **Task 2: Migration + models price functions + ItemConfig fields** - `0b58e1c` (feat)

## Files Created/Modified

- `tests/test_price_history.py` - 8 unit tests: table creation, idempotency, append/read, last-price, dedup state roundtrip, dedup column independence, price config read/write
- `models.py` - idempotent migration extension + 8 new _sync functions; all SQL parameterized
- `core/config_schema.py` - Optional import added; ItemConfig extended with target_price/price_drop_pct

## Decisions Made

- Separate-update strategy: `update_item_price_config_sync` is a standalone function called after `add_items_sync`; the existing 5-tuple signature of `add_items_sync` is preserved so no existing tests or callers break.
- `get_last_price_sync` reads from price_history (not a separate column) to keep the schema minimal, consistent with the locked CONTEXT.md decision on append-only history.
- Strict column separation: `set_price_alert_armed_sync` only updates `price_alert_armed` and `price_last_notified`; it never references `last_seen_available` or `last_notified`. Proven by `test_price_dedup_independent_from_stock_dedup`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 (plugin ABC get_price() hook) can now import `append_price_history_sync` and `get_last_price_sync` from models.
- Plan 03 (orchestrator wiring) can call `update_item_price_config_sync` from the BotService startup path using ItemConfig.target_price and ItemConfig.price_drop_pct.
- All downstream plans depend on these schema objects; they are in place and unit-proven.

---

*Phase: 16-price-monitoring*
*Completed: 2026-06-09*

## Self-Check: PASSED

- `tests/test_price_history.py`: FOUND
- `models.py` (contains price_history): FOUND
- `core/config_schema.py` (contains target_price): FOUND
- Commit `19a7376`: FOUND
- Commit `0b58e1c`: FOUND
- 501 passed, 2 skipped: VERIFIED
