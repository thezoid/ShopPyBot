---
phase: 27-sse-infrastructure
reviewed: 2026-06-27T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - web/sse_hub.py
  - web/routes/sse.py
  - web/__init__.py
  - web/log_reader.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 27: Code Review Report

**Reviewed:** 2026-06-27
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

The SSE infrastructure is structurally sound. The cross-thread invariant holds: `web/sse_hub.py` does not import from `core/` or `orchestrator.py`, and all `SseHub` method calls originate from `_poll_loop` on uvicorn's event loop. The lifespan wiring, generator cleanup, bounded-queue drop-oldest, and `max_frames` test-boundary design are all correct. Generator cleanup in `finally` covers all exit paths (break, CancelledError, aclose). The `tail_log_lines` midnight-rollover logic is sound.

One critical bug was found: `web/log_reader.py` hardcodes the log directory as `<repo_root>/logs/` but `logger.py` writes logs to the OS-standard path returned by `core.paths.log_dir()` (e.g., `C:\Users\...\AppData\Local\shoppybot\Logs` on Windows). After the one-time migration runs, all SSE log frames delivered to the dashboard are sourced from an empty or stale directory, making the live log stream silently broken in production.

Three warnings follow: a blocking file write on the event loop in the error handler, a `frame_count` miscounting that makes the `max_frames` parameter off-by-one from the caller's perspective on the `retry:` prefix line, and a stale docstring claim about per-iteration keepalive resolution.

## Critical Issues

### CR-01: log_reader reads from wrong directory after migration -- SSE log frames are always empty in production

**File:** `web/log_reader.py:6`

**Issue:** `_LOG_DIR` is hardcoded to `pathlib.Path(__file__).parent.parent / "logs"`, which resolves to `<repo_root>/logs/`. However `logger.py` resolves the write path via `core.paths.log_dir()`, which returns the OS-standard user log directory (e.g., `C:\Users\...\AppData\Local\shoppybot\Logs` on Windows, `~/.local/share/shoppybot/log` on Linux). After `migrate_legacy_paths()` runs on first boot, the legacy `logs/` directory is deleted and all future log writes go to the OS path. On every subsequent run `tail_log_lines()` reads from the now-empty or absent `<repo_root>/logs/` directory and always returns `([], 0)`. Every `event: log` SSE frame is silently suppressed and the live log panel on the dashboard is permanently blank.

The `read_recent_logs()` and `read_logs_filtered()` functions used by `GET /api/logs` are affected identically.

**Fix:**
```python
# web/log_reader.py
import datetime
import pathlib

from core.paths import log_dir as _resolve_log_dir   # same source as logger.py


def _read_today_lines() -> list[str]:
    log_dir = _resolve_log_dir()
    fname = datetime.datetime.now().strftime("%Y%B%d") + ".log"
    log_path = log_dir / fname
    if not log_path.exists():
        return []
    return log_path.read_text(encoding="utf-8", errors="replace").splitlines()
```

Remove the module-level `_LOG_DIR` constant entirely; resolve the path dynamically on each call so the `SHOPBOT_DATA_DIR` env-var override that tests use is respected without monkeypatching a second constant.

## Warnings

### WR-01: writeLog called directly from the event loop in _poll_loop error handler -- blocks uvicorn

**File:** `web/sse_hub.py:105-106`

**Issue:** When `svc.get_status()` or `tail_log_lines()` raises a non-CancelledError exception, the handler calls `writeLog(...)` synchronously from `_poll_loop`, which runs on uvicorn's event loop. `writeLog` opens and writes to a file (`log_file_path`, line 49 of `logger.py`) using a standard blocking `open()`. This blocks the event loop for the duration of the disk write. It also lazily imports `core.paths`, triggering `platformdirs.PlatformDirs` resolution on the hot path of an already-failing poll. In normal operation errors are rare, so the impact is low-frequency, but any burst of repeated poll errors will introduce measurable event-loop stalls.

**Fix:**
```python
except Exception as exc:
    from logger import writeLog
    # Offload to thread: writeLog does a blocking file write.
    asyncio.create_task(
        asyncio.to_thread(writeLog, f"SSE poll error: {exc.__class__.__name__}", "WARNING")
    )
```

Alternatively, use Python's `logging` module (already imported in `core/service.py`) from the event loop directly, which is thread-safe and non-blocking.

### WR-02: frame_count includes the retry: prefix line -- max_frames=N delivers N-1 data frames

**File:** `web/routes/sse.py:67-81`

**Issue:** `frame_count` is initialised to 0, the `retry: 3000\n\n` line is yielded and then `frame_count` is incremented to 1 (line 71). The loop condition is `frame_count < max_frames`. A caller passing `max_frames=3` will receive: `retry:` (count=1), one queue frame or keepalive (count=2), one more frame (count=3) -- then the loop exits. The total yielded items is 3, but only 2 are data/keepalive frames. For the test in `test_sse_retry_line_and_keepalive`, `max_frames=3` is used and the assertion `": keep-alive" in combined` passes because two keepalives fit. This is not a functional bug in production (route passes `max_frames=None`), but the semantics of the parameter are misleading: `max_frames=N` means "N total yields including the retry line", not "N data frames". Any future test author who writes `max_frames=1` expecting to get one data frame after the retry line gets nothing and the test silently passes because the generator exits immediately after the retry line.

**Fix:** Either exclude the retry line from `frame_count` tracking, or rename the parameter to `max_yields` and document the counting convention explicitly in the docstring:

```python
# Option A: don't count the retry line
yield "retry: 3000\n\n"
# frame_count += 1  <-- remove this
while max_frames is None or frame_count < max_frames:
    ...
    frame_count += 1
```

### WR-03: _event_generator docstring claims per-iteration keepalive resolution but ka is resolved once at call time

**File:** `web/routes/sse.py:54-55`

**Issue:** The module-level docstring (line 5-6) says "The generator reads the current keepalive timeout from the web.sse_hub module at call time". `_event_generator`'s own docstring (line 54-55) says "reads sse_hub._KEEPALIVE_SECS at each call so that test monkeypatches are respected." Both are technically accurate (`ka` is resolved when `_event_generator()` is called), but "at each call" in the context of a generator is easily misread as "on each iteration of the while loop". `ka` is captured on line 64 and never re-read. If a test monkeypatches `sse_hub._KEEPALIVE_SECS` after the generator object is created but before the first `__anext__()` call, the value will not be captured -- the capture happens at the `_event_generator(...)` call site (object creation), not at `__anext__()`. In `test_sse_retry_line_and_keepalive`, the override is passed via the `keepalive_secs` kwarg, so this is a documentation-accuracy issue rather than a test failure.

**Fix:**
```python
# Resolve keepalive once at entry; keepalive_secs kwarg overrides module default.
# To change the interval for an active generator you must close and reopen it.
ka = keepalive_secs if keepalive_secs is not None else sse_hub._KEEPALIVE_SECS
```

Update the module docstring to say "at generator creation time" rather than "at call time" to be precise.

## Info

### IN-01: tail_log_lines midnight-rollover returns all lines of the new file including previously-seen overlap window

**File:** `web/log_reader.py:62-63`

**Issue:** When `after_line > total` (rollover detected), the function returns `(lines, total)` -- all lines of the new day's file. If the new file already has content when the rollover is first detected (because the poll missed exactly midnight), every line in that file is delivered as "new", including any lines that were written before the detection. This is strictly correct behaviour (no lines are lost), but the dashboard log panel may show a burst of duplicated-looking lines if there is already content in the new day's file at detection time. This is a known and acceptable trade-off for a once-per-day event, but it should be documented on the function.

**Fix:** Add a note to the docstring:
```
Midnight rollover: if after_line > total, returns ALL lines of the new file.
If the file already had content at rollover detection, those lines are returned
as new (no duplication relative to prior state, but a burst may appear).
```

### IN-02: _LOG_DIR resolved at module import time -- SHOPBOT_DATA_DIR env override set after import has no effect on log_reader

**File:** `web/log_reader.py:6`

**Issue:** (Related to CR-01; independent of the wrong-path bug.) Even if the path were correct, the module-level `_LOG_DIR = pathlib.Path(__file__).parent.parent / "logs"` is evaluated once at import time. Tests that set `SHOPBOT_DATA_DIR` after importing `web.log_reader` will read the wrong directory. `core.paths.log_dir()` re-evaluates `os.environ.get("SHOPBOT_DATA_DIR")` on every call, making it override-safe. This is subsumed by the CR-01 fix (dynamic resolution removes the constant) but worth noting as the underlying design principle.

**Fix:** Subsumed by CR-01 fix.

---

_Reviewed: 2026-06-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
