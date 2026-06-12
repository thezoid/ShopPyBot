---
phase: 22-supervisor-browser-relaunch-server-safety
verified: 2026-06-12T00:00:00Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Kill the Chrome process while the bot is polling a real URL; confirm supervise() detects a ConnectionError or RuntimeError('WebSocket'), calls relaunch(), and the plugin resumes polling."
    expected: "No other plugin is interrupted; the crashed plugin restarts with backoff; full stealth re-injection confirmed via nodriver CDP logs."
    why_human: "Requires a live Chrome process, real nodriver session, and OS-level SIGKILL to Chrome PID. Cannot replicate with asyncio mocks."
  - test: "Send SIGTERM (Linux/macOS) or taskkill /F (Windows) to the running bot process during active polling."
    expected: "Shutdown signal received log appears; write-queue flushes all pending DB writes; teardown_all() closes all Chrome instances; process exits 0."
    why_human: "Requires the process to be running with live Chrome and SQLite under real load. Signal delivery and queue drain sequence cannot be reliably confirmed with unit mocks alone."
---

# Phase 22: Supervisor / Browser-Relaunch / Server-Safety Verification Report

**Phase Goal:** A single plugin crash or browser death cannot take down the rest of the bot; plugins restart automatically with backoff and full stealth/proxy/login restoration; the bot shuts down cleanly on SIGTERM.
**Verified:** 2026-06-12T00:00:00Z
**Status:** human_needed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | REL-01: supervise() absorbs plugin exceptions; CancelledError re-raised | VERIFIED | `orchestrator.py:118-119` — `except asyncio.CancelledError: raise` before `except Exception`; `test_supervisor.py::test_crash_one_plugin_others_survive` and `test_supervise_propagates_cancelled` pass. |
| 2 | REL-02: failure budget parks plugin + dispatcher notify on budget breach | VERIFIED | `orchestrator.py:111,122-133` — deque evicts timestamps outside 600s window; `_park_plugin` dispatches `plugin_parked`. `test_failure_budget_parks_plugin` and `test_failure_budget_window_eviction` pass. |
| 3 | REL-03: browser-dead -> assign_proxy -> relaunch() (teardown->setup->restore_session->login); apply_stealth via setup() | VERIFIED | `orchestrator.py:135-144` — `_is_browser_dead_exc` gate, `registry.assign_proxy(plugin)`, `plugin.relaunch()`. `plugin_base.py:148-172` — relaunch sequence verified in order. `test_browser_dead_triggers_relaunch`, `test_relaunch_sequence_order`, `test_relaunch_apply_stealth_called` pass. |
| 4 | REL-05: sqlite3.OperationalError on items read skips cycle (NOT crash); sqlite3.DatabaseError propagates | VERIFIED | `orchestrator.py:285-291` — `except sqlite3.OperationalError` logs WARNING + `continue`; no catch for DatabaseError. `test_read_isolation_operational_error` and `test_read_isolation_database_error_propagates` pass. |
| 5 | REL-06: per-item asyncio.timeout; timed-out item continues to next; write_queue unbounded (maxsize==0 asserted) | VERIFIED | `orchestrator.py:303-309` — `async with asyncio.timeout(item_timeout):` + `except TimeoutError: ... continue`. `orchestrator.py:658` — `assert write_queue.maxsize == 0`. `test_item_timeout_continues_to_next` and `test_write_queue_is_unbounded` pass. |
| 6 | SRV-02: SIGTERM/SIGINT cooperative teardown; Windows NotImplementedError -> signal.signal fallback; write-queue drain before teardown_all | VERIFIED | `orchestrator.py:609-626` — `_register_signals` with POSIX/Windows branch. `orchestrator.py:674-679` — `_flush_write_queue` then `write_queue.join(timeout=5)` then `teardown_all()`. All 5 `test_signal_bridge.py` tests pass. |

**Score:** 6/6 truths verified

### Post-Code-Review Fix Verification

| Fix | Claim | Verified |
|-----|-------|---------|
| CR-01: exc.__class__.__name__ in check error log | `orchestrator.py:429` — `{exc.__class__.__name__}` confirmed, no bare `{exc}` | VERIFIED |
| CR-02: bare OSError excluded from _is_browser_dead_exc | `orchestrator.py:54-77` — only `ConnectionError`, `RuntimeError("WebSocket...")`, `websockets.exceptions.ConnectionClosed` matched; `OSError`, `PermissionError`, `FileNotFoundError` return False | VERIFIED |
| WR-02: attempt resets after healthy run | `orchestrator.py:117` — `attempt = 0` immediately after `await run_plugin(...)` return | VERIFIED |
| WR-01: maxsize==0 assertion | `orchestrator.py:658` — `assert write_queue.maxsize == 0, "..."` | VERIFIED |
| WR-03/WR-04: exc.__class__.__name__ in drain/setup logs | `orchestrator.py:518,563` — both use `{exc.__class__.__name__}` | VERIFIED |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/orchestrator.py` | supervise(), run_plugin(), _register_signals(), _flush_write_queue(), async_main() | VERIFIED | 680 lines; all functions substantive and wired into async_main |
| `core/plugin_base.py` | relaunch(), restore_session(), PLUGIN_API_VERSION==2 | VERIFIED | `relaunch()` at L132, `restore_session()` at L166 returns False, `PLUGIN_API_VERSION = 2` at L7 |
| `tests/test_supervisor.py` | REL-01/02/03 + WR-02 + _is_browser_dead_exc classification | VERIFIED | 453 lines; 7 substantive tests, all passing |
| `tests/test_relaunch.py` | REL-03 sequence order + apply_stealth + teardown error swallowing | VERIFIED | 154 lines; 4 substantive tests, all passing |
| `tests/test_signal_bridge.py` | SRV-02 POSIX + Windows + handler + flush | VERIFIED | 154 lines; 5 substantive tests, all passing |
| `tests/test_orchestrator.py` | REL-05 + REL-06 + write_queue unbounded | VERIFIED | Tests at L905-1125; 4 targeted tests passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `supervise()` | `_is_browser_dead_exc()` | L135 | WIRED | Called on every exception before relaunch decision |
| `supervise()` | `registry.assign_proxy()` | L137 | WIRED | Called before `plugin.relaunch()` on browser-dead path |
| `supervise()` | `plugin.relaunch()` | L139 | WIRED | Awaited after assign_proxy |
| `plugin.relaunch()` | `plugin.setup()` | `plugin_base.py:158` | WIRED | Awaited in sequence after teardown |
| `plugin.relaunch()` | `plugin.restore_session()` | `plugin_base.py:159` | WIRED | Awaited; returns False stub; login called when False |
| `async_main()` | `_register_signals()` | L638 | WIRED | Called immediately after `root_task = asyncio.current_task()` |
| `async_main()` | `_flush_write_queue()` | L674 | WIRED | Called in finally block before `write_queue.join()` and `teardown_all()` |
| `run_plugin()` | `asyncio.timeout(item_timeout)` | L303 | WIRED | Wraps each `_check_and_buy` call |
| `run_plugin()` | `sqlite3.OperationalError` guard | L285 | WIRED | Catches only OperationalError; DatabaseError escapes |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| REL-01/02/03 tests pass | `pytest tests/test_supervisor.py tests/test_relaunch.py tests/test_signal_bridge.py -q` | 16 passed in 0.76s | PASS |
| REL-05/REL-06 + write_queue tests | `pytest test_orchestrator.py::{read_isolation,item_timeout,write_queue_is_unbounded} -v` | 4 passed in 0.62s | PASS |
| Full suite | `pytest -x -q` | 693 passed, 2 skipped, 2 warnings in 24.66s | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| REL-01 | 22-01-PLAN.md | Plugin crash absorbed; siblings keep running | SATISFIED | supervise() except Exception; CancelledError re-raised; TaskGroup isolation tested |
| REL-02 | 22-01-PLAN.md | Failure budget parks plugin + dispatcher notify | SATISFIED | deque window + _park_plugin + dispatcher.notify("plugin_parked") |
| REL-03 | 22-02-PLAN.md | Browser-dead -> relaunch full sequence + stealth re-applied | SATISFIED | assign_proxy + relaunch() sequence + setup() stealth injection point |
| REL-05 | 22-03-PLAN.md | sqlite3.OperationalError skips cycle; DatabaseError propagates | SATISFIED | Targeted except clause in run_plugin; two tests confirm both paths |
| REL-06 | 22-03-PLAN.md | Per-item timeout; write_queue unbounded; no orphan | SATISFIED | asyncio.timeout per item; assert maxsize==0; comment at call site |
| SRV-02 | 22-04-PLAN.md | SIGTERM/SIGINT cooperative teardown; Windows fallback; queue drain | SATISFIED | _register_signals + _flush_write_queue + finally ordering |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `core/orchestrator.py` | 535 | `_flush_write_queue` logs `{exc}` (not `{exc.__class__.__name__}`) in flush error path | Warning | Low — flush errors are SQLite errors, rarely contain credentials; inconsistent with other logs but not a blocker. This was WR-03 applied to `_write_queue_drain` (L518) but the _flush_write_queue counterpart at L535 still uses bare `{exc}`. |

**Note on flush log inconsistency:** `_write_queue_drain` at L518 was fixed (WR-03) to use `exc.__class__.__name__`. The parallel `_flush_write_queue` at L535 still uses bare `{exc}`. This is a minor inconsistency — not a security blocker since flush-path errors are SQLite exceptions with no credential content — but it is observable.

### Human Verification Required

#### 1. Live Browser Crash -> Restart

**Test:** Run the bot against a real item URL. Use the OS to kill the Chrome process (`taskkill /F /PID <chrome_pid>` on Windows). Observe bot logs.
**Expected:** The crashed plugin logs a ConnectionError crash, calls assign_proxy, calls relaunch() (teardown -> setup -> login), and resumes polling. Other plugins are unaffected.
**Why human:** Requires a live Chrome process + real nodriver WebSocket session. asyncio mocks cannot replicate OS-level process death.

#### 2. SIGTERM Clean Teardown

**Test:** Start the bot under normal conditions with multiple plugins active. Send `taskkill /F /IM python.exe` (Windows) or `kill -TERM <pid>` (Linux). Check logs and that Chrome windows close.
**Expected:** "Shutdown signal received -- initiating teardown" in log; write-queue flushes all pending DB writes; all Chrome windows close; process exits cleanly.
**Why human:** Requires OS signal delivery to a running process with live Chrome and SQLite write load.

### Gaps Summary

No gaps blocking goal achievement. All 6 success criteria are verified with substantive implementation and passing tests.

One minor inconsistency (warning, not blocker): `_flush_write_queue` at L535 logs bare `{exc}` instead of `exc.__class__.__name__`. This was not caught by the code-review fix pass (WR-03 fixed the drain task but not the flush helper). Low-severity; suggest fixing in a cleanup commit.

---

_Verified: 2026-06-12T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
