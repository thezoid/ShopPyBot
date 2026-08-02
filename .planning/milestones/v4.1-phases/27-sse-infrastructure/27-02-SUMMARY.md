---
phase: 27-sse-infrastructure
plan: "02"
requirements: [SSE-02]
subsystem: web
tags: [sse, log-reader, asyncio, pub-sub, bridge-core]
dependency_graph:
  requires: [27-01]
  provides: [web/log_reader.py::tail_log_lines, web/sse_hub.py::SseHub, web/sse_hub.py::_poll_loop]
  affects: [web/__init__.py (27-03 wiring), web/routes/sse.py (27-03)]
tech_stack:
  added: []
  patterns: [asyncio.to_thread, bounded-drop-oldest-queue, cursor-based-log-tail]
key_files:
  modified: [web/log_reader.py]
  created: [web/sse_hub.py]
decisions:
  - "Drop-oldest strategy (A1): get_nowait() to evict oldest before put_nowait(); both calls on uvicorn's loop so no thread-safety concern"
  - "Module-level constants _POLL_INTERVAL_SECS=1.0 and _KEEPALIVE_SECS=15.0 as test-override seams (A3: module-level not constructor args)"
  - "tail_log_lines rollover branch returns (lines, total) when after_line > total, resetting cursor to new file total"
  - "_poll_loop lazy-imports writeLog inside except block to avoid import-time coupling with logger module"
metrics:
  duration: "120s"
  completed: "2026-06-27"
  tasks: 2
  files: 2
---

# Phase 27 Plan 02: SSE Bridge Core Summary

One-liner: Cursor-based log tail and bounded drop-oldest SSE pub-sub hub with sole-producer poll loop on uvicorn's event loop.

## What Was Built

**Task 1 — tail_log_lines in web/log_reader.py:**
Appended `tail_log_lines(after_line: int) -> tuple[list[str], int]` after `read_logs_filtered`. Calls the existing `_read_today_lines()` (midnight rollover automatic), returns `(lines[after_line:], total)` for normal reads, and resets with `(lines, total)` when `after_line > total` (rollover branch). No new imports. Turns all 3 RED tests in `tests/test_log_reader.py` GREEN.

**Task 2 — web/sse_hub.py (new file):**
`SseHub` class with `subscribe() -> asyncio.Queue(maxsize=100)`, `unsubscribe(q)`, and `broadcast(event, payload)` that iterates a set snapshot and applies drop-oldest logic (guard QueueEmpty on get_nowait, guard QueueFull on put_nowait for the race). Module-level `_POLL_INTERVAL_SECS = 1.0` and `_KEEPALIVE_SECS = 15.0` for test injection. `_poll_loop` async coroutine reads `svc.get_status()` and `tail_log_lines(cursor)` via `asyncio.to_thread`, broadcasts status and log events each tick, propagates `CancelledError`, and logs any other exception by class name only (SSE-03 invariant). Zero imports from `core/` or `orchestrator`.

## Test State

| Test file | Status after this plan |
|-----------|----------------------|
| tests/test_log_reader.py | GREEN (3/3 pass) |
| tests/test_sse.py | RED (6/6 fail, 404 — route not wired until 27-03) |
| Full suite (excl. test_sse.py) | 779 passed, 2 skipped |

## Decisions Made

- Drop-oldest (A1): `get_nowait()` before `put_nowait()` on the same event loop; QueueEmpty/QueueFull guards cover the full/empty race. No external dependency.
- Module-level constants (A3): `_POLL_INTERVAL_SECS` and `_KEEPALIVE_SECS` defined at module top so tests can override via `web.sse_hub._POLL_INTERVAL_SECS = 0.05` before constructing the app.
- Rollover reset: `if after_line > total: return lines, total` returns all lines from the new file with cursor set to its total (not the stale cursor). Verified by `test_tail_rollover_resets_cursor`.
- `writeLog` lazy-imported inside the `except Exception` block to match codebase import pattern and avoid import-time coupling.

## Threat Mitigations Applied

| Threat ID | Mitigation |
|-----------|-----------|
| T-27-03 | web/sse_hub.py has zero imports from core/ or orchestrator (grep confirmed; matches only in docstrings) |
| T-27-02 | asyncio.Queue(maxsize=100) with drop-oldest in broadcast; producer never blocks |
| T-27-04 | cursor-based tail_log_lines (no full re-read per tick); _poll_loop catches per-tick Exception and continues |
| T-27-01 | error branch logs exc.__class__.__name__ only; grep confirms zero str(exc) in code lines |

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: tail_log_lines | af2c249 | web/log_reader.py |
| Task 2: SseHub + _poll_loop | 734fd35 | web/sse_hub.py (new) |

## Self-Check: PASSED

- web/log_reader.py modified: confirmed (tail_log_lines appended)
- web/sse_hub.py created: confirmed (97 lines, SseHub + _poll_loop + constants)
- af2c249 commit: confirmed in git log
- 734fd35 commit: confirmed in git log
- tests/test_log_reader.py: 3 passed
- No new imports in core/ from web/sse_hub (architecture invariant holds)
- web/routes/sse.py: NOT created (correct — 27-03 owns this)
- web/__init__.py: NOT modified (correct — 27-03 owns this)
