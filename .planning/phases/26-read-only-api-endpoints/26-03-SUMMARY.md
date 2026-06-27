---
plan: 26-03
phase: 26-read-only-api-endpoints
status: complete
wave: 2
requirements: [SSE-03]
completed: 2026-06-27
key_files:
  created: []
  modified:
    - core/health.py
    - core/orchestrator.py
    - core/service.py
    - web/routes/api.py
    - tests/test_health.py
    - tests/test_api_observability.py
    - tests/test_cli_no_fastapi.py
---

# Plan 26-03 Summary — Scrubbed last_error + Credential Guard (+ cross-cutting fixes)

## What was built (plan scope)

- **`core/health.py`** — `_ensure()` now initializes `last_error: None`; new
  `record_last_error(name, exc)` stores `exc.__class__.__name__` only (never `str(exc)`).
  `get_snapshot()` already passes through non-`_` keys, so `last_error` surfaces automatically.
- **`core/orchestrator.py`** — `supervise()` except block now calls
  `health.record_last_error(plugin_name, exc)` alongside `record_error`; degraded/park/relaunch
  logic untouched.
- Credential-leak guard (authored Wave 1) is GREEN: `/api/status` JSON and `get_status()`
  payload contain no `@`/`password`/`token`/`key=`/`cvv` strings (real HealthRegistry).

## Cross-cutting fixes discovered at the post-merge full-suite gate

These were caught by running the FULL suite after Wave 2 (the agent-stall recovery left only
the phase-26 test files run). Two real regressions + one latent test-isolation bug:

1. **Architecture (MOD-02): web must not import `models` directly.** Plan 26-02 (and its
   RESEARCH/PATTERNS) added `from models import …` to `web/routes/api.py`, violating the
   pre-existing `tests/test_web_mod02.py::test_web_no_direct_model_imports` guard. Corrected by
   adding `BotService.get_confirmed_orders()` and `BotService.get_price_history_by_link(link, limit)`
   to `core/service.py` and routing the endpoints through `request.app.state.svc` (the established
   web→service pattern, same as `list_items`). The endpoint test patch targets moved from
   `web.routes.api.<model_fn>` to configuring the mock service — assertions unchanged.
2. **Snapshot key guard:** `tests/test_health.py::test_snapshot_public_keys_exact` pinned the
   exact key set; updated to include the intended new `last_error` key.
3. **Test isolation (latent, exposed by ordering):** `test_cli_no_fastapi::test_web_no_fastapi`
   only purged `core.cli.web`, relying on `web` not being cached. The new (alphabetically first)
   `test_api_observability.py` imports `web` early, so the lazy-import ImportError guard never
   fired and the failure cascaded into `test_notifications`. Fixed by purging all cached `web*`
   modules via `monkeypatch.delitem` (auto-restored) before the import.

## Verification

`pytest -q` → **776 passed, 2 skipped, 0 failures.** All four ROADMAP criteria satisfied;
credential/scrub guard GREEN; no `str(exc)` in `core/health.py`; no new packages.

## Execution note

Plans 26-02 (Task 3) and 26-03 were completed **inline by the orchestrator** after the
26-02 executor agent stalled mid-Task-3 (see 26-02-SUMMARY). This avoided respawning a
long-running agent; all work is committed atomically.

## Self-Check: PASSED
