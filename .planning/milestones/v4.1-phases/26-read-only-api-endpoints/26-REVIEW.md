---
phase: 26-read-only-api-endpoints
reviewed: 2026-06-27T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - web/routes/api.py
  - web/log_reader.py
  - models.py
  - core/service.py
  - core/health.py
  - core/orchestrator.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 26: Code Review Report

**Reviewed:** 2026-06-27
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Six files covering the Phase 26 read-only observability API (history, price-history, logs, status), HealthRegistry secret scrubbing, BotService delegation, and the orchestrator supervise path were reviewed at standard depth.

No critical security vulnerabilities or data-loss bugs were found. The SSE-03 scrubbing contract (`exc.__class__.__name__` only, never `str(exc)`) is correctly implemented end-to-end: `HealthRegistry.record_last_error` stores the class name, `get_snapshot()` strips private keys, and `supervise()` passes the raw exception to the registry. The MOD-02 constraint (no direct `models` import in `web/routes/api.py`) holds: the file imports only from `web.security` and `web.log_reader`. SQL in `get_confirmed_orders_sync` is parameterized-free (no user input in the query) and uses correct columns. Price-history tuple indexing is correct (`r[0]` = cents, `r[2]` = timestamp). The base64 bad-input path returns `{"series": []}` with 200 as specified.

Three warnings and three info items were found. The most significant warning is a logical filtering bug in `read_logs_filtered`: the `n` cap applies to the raw line slice before filtering, so a filtered request for 50 `[ERROR]` lines may return far fewer than `n` results without any indication, and pathological log files with many non-matching lines could return empty results for any `n <= 500`. The second warning is a thread-safety gap in `BotService.get_status()` and `BotService.start()/stop()` where `_running`, `_loop`, and `_task` are read and written across threads without a lock. The third warning is the `_flush_write_queue` / `write_queue.join()` double-drain sequence that risks processing confirmed-order writes twice after clean shutdown.

## Warnings

### WR-01: Log filter operates on n-line tail, not n matching lines

**File:** `web/log_reader.py:37-43`
**Issue:** `read_logs_filtered` calls `read_recent_logs(n)` first (tail last `n` raw lines), then filters that slice by level/search. If the last `n` lines contain zero matching lines the endpoint returns `[]` even though matching lines exist earlier in the file. The caller (`/api/logs`) passes the user-supplied `n` directly, so `?level=ERROR&n=50` means "look at only the last 50 lines and then keep only ERROR lines" -- not "return the last 50 ERROR lines". This is a correctness mismatch with what the endpoint documents ("Return recent log lines, optionally filtered") and will silently produce empty or sparse results in any moderately busy log file. The doc-string in `read_logs_filtered` acknowledges this ("Filtering is applied to the n-line slice") but the API docstring does not, creating a user-visible inconsistency.

**Fix:** Scan a larger read window when filters are active, or read the full file and filter before tailing:
```python
def read_logs_filtered(n=50, level=None, search=None):
    # When filters are active, read more lines to find n matching ones.
    if level is None and search is None:
        return read_recent_logs(n)
    # Read entire file and filter, then return last n matches.
    fname = datetime.datetime.now().strftime("%Y%B%d") + ".log"
    log_path = _LOG_DIR / fname
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if level is not None:
        prefix = f"[{level.upper()}]"
        lines = [l for l in lines if l.startswith(prefix)]
    if search is not None:
        needle = search.lower()
        lines = [l for l in lines if needle in l.lower()]
    return lines[-n:]
```

### WR-02: BotService shared state accessed across threads without a lock

**File:** `core/service.py:73-85`, `core/service.py:163-227`
**Issue:** `_running`, `_start_time`, `_loop`, and `_task` are written by the daemon thread (inside `_run_loop`) and read by the FastAPI event loop (via `get_status()`, `stop()`). Python's GIL prevents torn writes on simple assignments to a single reference, but the multi-field check-then-act in `start()` (line 170: `if self._running or ...`) and the capture-then-use in `stop()` (lines 218-224: `loop = self._loop; task = self._task; if not self._running or loop is None`) have a TOCTOU window where `_running` becomes `False` between the guard and the `task.cancel()` call, or `stop()` reads a `_loop` that the daemon thread is simultaneously closing. For the current single-dashboard use case this is unlikely to manifest, but the `BotService.stop()` path specifically captures `loop` and `task` and then calls `loop.call_soon_threadsafe(task.cancel)` with no guarantee that `loop` is still open.

**Fix:** Add a `threading.Lock` guarding `_running`, `_loop`, and `_task` transitions, or document the race explicitly if acceptable:
```python
self._lock = threading.Lock()

def get_status(self):
    with self._lock:
        running = self._running
        start_time = self._start_time
    uptime = (time.monotonic() - start_time) if start_time and running else 0.0
    return {"running": running, "uptime_secs": uptime, "plugins": self._health_registry.get_snapshot()}
```

### WR-03: Double-drain race on shutdown may process confirmed-order writes twice

**File:** `core/orchestrator.py:707-712`
**Issue:** After the `TaskGroup` exits, `_flush_write_queue` drains remaining items (line 707), then `write_queue.join()` is called with a 5s timeout (line 709). The `join()` call waits for all `task_done()` signals to be issued. However, `_flush_write_queue` already called `task_done()` for each item it drained (line 570). If `_write_queue_drain` was mid-item when it was cancelled and left an item with `queue.get_nowait()` called but `task_done()` not yet called, the join is correct. But if `_flush_write_queue` races with any remaining in-flight item from a partially-cancelled `_write_queue_drain`, both the flush function and the cancellation's finally path could process the same queue item. In practice `_write_queue_drain` is a task inside the `TaskGroup` and is cancelled before `finally` runs, so the risk is limited to items that were `get()`-ted but whose `task_done()` was not yet called. The current ordering (`_flush_write_queue` then `join`) means the `join` call after a full flush should return immediately (all items drained, all `task_done()` called), but any `OperationalError` during flush would leave the queue in an inconsistent count state causing `join()` to hang until the 5s timeout. The `timeout` guard prevents deadlock but the log warning is silent about what was lost.

**Fix:** Log all items skipped due to timeout, or assert the queue is empty after flush:
```python
await _flush_write_queue(write_queue, loop)
if not write_queue.empty():
    writeLog(f"Write queue not empty after flush ({write_queue.qsize()} items) -- data loss risk", "ERROR")
try:
    await asyncio.wait_for(write_queue.join(), timeout=5)
except asyncio.TimeoutError:
    writeLog(f"Write queue join timed out -- {write_queue.qsize()} items may be lost", "WARNING")
```

## Info

### IN-01: price-history r[1] (currency) is fetched but never returned to the client

**File:** `web/routes/api.py:169`
**Issue:** `get_price_history_sync` returns `(price_cents, currency, scraped_at)`. The series comprehension uses `r[0]` (price_cents) and `r[2]` (scraped_at) but silently drops `r[1]` (currency). For a USD-only deployment this is harmless, but the currency column exists in the schema and is included in the query result. If multi-currency support is ever added the API response will still be missing it.

**Fix:** Include currency in the series payload now so the API contract is future-stable:
```python
series = [{"t": r[2], "price": r[0] / 100, "currency": r[1]} for r in rows]
```

### IN-02: HealthRegistry.get_snapshot() returns live last_heartbeat monotonic timestamp

**File:** `core/health.py:78-83`
**Issue:** `last_heartbeat` is stored as `time.monotonic()` (epoch-relative machine uptime, not wall-clock) and is surfaced verbatim in the `/api/status` JSON. Dashboard consumers cannot convert this to a wall-clock time or a human-readable "last seen N seconds ago" without also receiving the current monotonic reference point. This is not wrong but will confuse any client that tries to display it as a timestamp.

**Fix:** Either store wall-clock time (`time.time()`) for `last_heartbeat`, or add a `now_monotonic` field to the snapshot so clients can compute age:
```python
def get_snapshot(self) -> dict[str, dict]:
    now = time.monotonic()
    return {
        name: {k: v for k, v in rec.items() if not k.startswith("_")}
        for name, rec in self._plugins.items()
    }
    # Suggested: include {"_now_monotonic": now} in the envelope, not per-plugin
```

### IN-03: /api/logs search parameter is user-controlled and logged verbatim in operator logs

**File:** `web/routes/api.py:31-49`, `web/log_reader.py:41-43`
**Issue:** The `search` query parameter is passed directly to `line.lower()` substring matching with no length cap. A client can send a very large `search` string (e.g., 1 MB) and it will be compared against every log line. This is not an injection risk (it is a pure Python `in` check) but the lack of a length cap is a minor denial-of-service surface and was called out in the review notes ("operator log CONTENT is not scrubbed"). The review note confirms log content is intentionally not scrubbed; however the `search` input itself also has no length limit.

**Fix:** Add a length cap on `search` before using it:
```python
if search is not None:
    search = search[:200]  # prevent oversized search strings
```

---

_Reviewed: 2026-06-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
