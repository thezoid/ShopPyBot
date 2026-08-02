---
plan: 26-02
phase: 26-read-only-api-endpoints
status: complete
wave: 2
requirements: [OBS-08, SSE-03]
completed: 2026-06-27
key_files:
  created: []
  modified:
    - models.py
    - web/log_reader.py
    - web/routes/api.py
---

# Plan 26-02 Summary — Read Endpoints + Log Filtering

## What was built

- **`models.get_confirmed_orders_sync()`** — returns confirmed orders (name, order_id,
  confirmed_at, checkout_attempts) for purchased items; empty list when none. Uses the
  existing `with get_db_connection() as conn:` pattern.
- **`web/log_reader.read_logs_filtered(n, level, search)`** — last-n slice then optional
  `[LEVEL]` prefix + case-insensitive substring filters (AND-combined); no filters returns
  the same result as `read_recent_logs(n)`.
- **`GET /api/history`** — `{"confirmed_orders": [...]}`, async-safe via `asyncio.to_thread`.
- **`GET /api/price-history/{link_b64}`** — `{"series": [{"t","price"}]}` oldest-first
  (reversed from the newest-first SQL); `{"series": []}` for non-Amazon / no data / bad b64
  (200, never raises); `price` in dollars (`cents/100`).
- **`GET /api/logs?level=&search=&n=`** — query-param filtering via `read_logs_filtered`,
  `n` clamped to 1..500, async-safe via `asyncio.to_thread`; no params → last 50 lines.
- All new GET reads omit `check_origin` (reads, not mutations).

## Verification

`pytest tests/test_api_observability.py tests/test_models.py -q` → 22 passed, 1 failed.
The single remaining failure (`test_health_last_error_scrubbed`) is Plan 26-03's scope
(HealthRegistry.record_last_error) and is expected to stay RED until 26-03 lands.

## Deviations

- **Execution interruption:** the executor agent stalled mid-Task-3 after only swapping the
  `read_recent_logs` → `read_logs_filtered` import (leaving `web/routes/api.py` in a broken
  half-edit). The orchestrator completed Task 3 inline: rewrote the `get_logs` handler to
  accept `level`/`search`/`n`, clamp `n`, and call `read_logs_filtered` under
  `asyncio.to_thread`; ran the suite; committed (`b60d324`). Tasks 1 (`121e3db`) and 2
  (`cf2066d`) were already committed by the agent before the stall.

## Self-Check: PASSED
