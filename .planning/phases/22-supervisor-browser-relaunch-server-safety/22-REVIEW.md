---
phase: 22-supervisor-browser-relaunch-server-safety
reviewed: 2026-06-12T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - core/orchestrator.py
  - core/plugin_base.py
  - tests/test_orchestrator.py
  - tests/test_plugin_base.py
  - tests/test_relaunch.py
  - tests/test_signal_bridge.py
  - tests/test_supervisor.py
findings:
  critical: 2
  warning: 4
  info: 1
  total: 7
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-06-12T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 22 implements the supervisor restart loop (REL-01/02/03), browser relaunch sequence
(REL-03), write-queue flush (SRV-02), and per-item timeout (REL-06). The core invariants
hold: CancelledError propagates correctly, the failure-budget deque evicts old timestamps,
and the relaunch sequence (teardown -> setup -> restore_session -> login) is correct.
Two security defects are present: one logs full exception strings that can contain
credentials/tokens, and the OSError classifier over-matches non-browser errors causing
spurious relaunches. Four additional warnings cover correctness and reliability gaps.

## Critical Issues

### CR-01: Credential leak via `{exc}` in check_availability error log

**File:** `core/orchestrator.py:419`
**Issue:** `writeLog(f"[...] check error: {exc}", "ERROR")` interpolates the full
exception string. nodriver exceptions on network/auth failures routinely include the
request URL, response body fragments, or header values in their message. These can
contain session tokens, OAuth credentials, or Amazon/BestBuy login cookies embedded
in redirect URLs. All other error logs in this file correctly use `exc.__class__.__name__`
-- this one is inconsistent and is the only place that leaks the full string.
**Fix:**
```python
writeLog(f"[{plugin.__class__.__name__}] check error: {exc.__class__.__name__}", "ERROR")
```

### CR-02: `_is_browser_dead_exc` over-matches any `OSError`, triggering spurious relaunches

**File:** `core/orchestrator.py:63`
**Issue:** `isinstance(exc, (ConnectionError, OSError))` returns True for ALL OSError
subclasses: `PermissionError`, `FileNotFoundError`, `BlockingIOError`, etc. An OSError
raised from disk-I/O (e.g. log file rotation, sqlite temp file, sounds directory access)
that escapes from `run_plugin` and reaches `supervise`'s `except Exception` block will
classify as a browser death and call `plugin.relaunch()` + `registry.assign_proxy()`.
This masks the real error, burns the proxy rotation budget, and may cause a working
browser to be torn down unnecessarily. The intent per the docstring is socket/port errors
only.
**Fix:** Tighten to connection-specific OSError subclasses:
```python
_BROWSER_DEAD_OS_ERRORS = (ConnectionError, ConnectionRefusedError, ConnectionResetError,
                            ConnectionAbortedError, BrokenPipeError, OSError)

def _is_browser_dead_exc(exc: Exception) -> bool:
    # Restrict OSError to message-string heuristic to avoid matching disk/fs errors
    if isinstance(exc, ConnectionError):
        return True
    if isinstance(exc, OSError) and not isinstance(exc, (PermissionError, FileNotFoundError,
                                                          IsADirectoryError, NotADirectoryError)):
        return True
    if isinstance(exc, RuntimeError) and "WebSocket" in str(exc):
        return True
    try:
        import websockets.exceptions as _ws_exc
        if isinstance(exc, _ws_exc.ConnectionClosed):
            return True
    except ImportError:
        pass
    return False
```
Alternatively, check `exc.errno` against socket error codes (errno.ECONNREFUSED,
errno.ECONNRESET, etc.) for a cleaner gate.

## Warnings

### WR-01: `write_queue.put()` inside `asyncio.timeout` context -- correctness depends on unbounded queue

**File:** `core/orchestrator.py:293-294`
**Issue:** `_check_and_buy` (which contains all `write_queue.put()` calls) runs inside
`async with asyncio.timeout(item_timeout)`. The comment in `_attempt_buy` at line 307
states "No enqueue here -- callers keep write_queue.put() outside the retry loop (WR-02)"
but the actual `write_queue.put()` calls inside `_check_and_buy` / `_enqueue_buy_result`
are still inside the timeout boundary in `run_plugin`. If the queue were ever bounded
(maxsize > 0), a full queue would cause `put()` to suspend, and the timeout could fire
while `put()` is waiting, silently dropping the write. The queue is currently unbounded
so it does not trigger in practice. The architecture comment is also misleading: WR-02
says put is "outside the timeout" but structurally it is inside.
**Fix:** Document explicitly that `asyncio.Queue()` must remain unbounded (no maxsize)
for the per-item timeout to be safe, or move `_enqueue_buy_result` to be awaited after
the `asyncio.timeout` block. The safest fix is a guard assertion:
```python
write_queue: asyncio.Queue = asyncio.Queue()  # MUST remain unbounded (REL-06 safety)
assert write_queue.maxsize == 0, "write_queue must be unbounded for per-item timeout safety"
```

### WR-02: `attempt` counter never resets after browser relaunch -- unbounded backoff growth

**File:** `core/orchestrator.py:147`
**Issue:** `attempt` is declared at line 108 and incremented at line 147 after every
failure, but never reset after a successful `run_plugin` call. After a plugin accumulates
N failures (even if spread across days), the next failure computes `compute_delay(N, ...)`
which may be extremely large (exponential backoff). A plugin that runs stably for weeks,
then crashes once, will restart with a delay as if it had crashed N times in a row.
**Fix:** Reset `attempt = 0` at the top of the `while True` loop or after each successful
return from `run_plugin`:
```python
while True:
    try:
        await run_plugin(...)
        attempt = 0  # successful run; reset backoff
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        ...
        attempt += 1
```

### WR-03: `_write_queue_drain` logs full `{exc}` string on DB write failure

**File:** `core/orchestrator.py:508`
**Issue:** `writeLog(f"DB write failed for {item!r}: {exc}", "ERROR")` -- `{exc}` is
the full exception string, which for sqlite3 errors can include partial SQL, table names,
or constraint values (order IDs, URLs). This is lower severity than CR-01 since SQLite
errors rarely contain credentials, but is inconsistent with the rest of the module and
leaks internal DB schema details.
**Fix:**
```python
writeLog(f"DB write failed for {item!r}: {exc.__class__.__name__}", "ERROR")
```

### WR-04: `_staggered_setup` setup-error log leaks full exception string

**File:** `core/orchestrator.py:551`
**Issue:** `f"Plugin {plugin.__class__.__name__} setup failed: {exc} -- skipping"` --
nodriver setup errors can contain CDP endpoint URLs, WebSocket connection strings, or
proxy auth strings if proxy setup is included in `plugin.setup()`. Same pattern as CR-01,
lower severity because it only fires at startup, not per-poll-cycle.
**Fix:**
```python
writeLog(
    f"Plugin {plugin.__class__.__name__} setup failed: {exc.__class__.__name__} -- skipping",
    "WARNING",
)
```

## Info

### IN-01: Test helper `_make_registry_with_plugins` duplicated between test files

**File:** `tests/test_supervisor.py:35-42`, `tests/test_orchestrator.py:58-64`
**Issue:** Identical helper function defined twice. The versions differ only in that
`test_supervisor.py` adds `registry.assign_proxy = MagicMock()`. This is test-only
duplication but will drift over time.
**Fix:** Consolidate into `tests/conftest.py` as a fixture parameterised by
`has_assign_proxy: bool`, or move to a shared `tests/helpers.py` module.

---

_Reviewed: 2026-06-12T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
