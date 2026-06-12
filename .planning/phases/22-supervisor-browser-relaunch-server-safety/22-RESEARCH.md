# Phase 22: Supervisor + Browser Relaunch + Server Safety - Research

**Researched:** 2026-06-12
**Domain:** asyncio TaskGroup supervision, nodriver browser lifecycle, signal handling, SQLite read isolation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Supervision Model & Failure Budget (REL-01, REL-02)**
- A `supervise(plugin, ...)` wrapper coroutine runs `run_plugin` in a try/except loop and catches ALL exceptions so none reach the `asyncio.TaskGroup` boundary (REL-01). Every other plugin's coroutine keeps running.
- Failure budget threshold N = `CheckoutConfig.alert_on_errors` (default 3) within a module-constant rolling window (~600s). Reuses existing `alert_on_errors` field (P18).
- Restart backoff via `core/retry.py` `compute_delay`; supervisor constructs its own `RetryPolicy` from `CheckoutConfig` backoff fields.
- After budget exceeded: plugin is PARKED, notification dispatched ("plugin X parked after N failures"), other plugins unaffected.

**Browser Relaunch & Lifecycle (REL-03)**
- Dead/disconnected Chrome detected by catching nodriver connection/browser-dead exceptions.
- Concrete `relaunch()` ABC method sequence: `teardown()` -> `assign_proxy` -> `setup()` (new browser + `apply_stealth` + proxy auth) -> `restore_session()` (no-op stub) -> `login()`.
- `apply_stealth` MUST be called on the relaunched browser (roadmap criterion 3).
- Additive `async def restore_session(self) -> bool` no-op default returns False. No `PLUGIN_API_VERSION` bump.

**Read Isolation + Per-Item Timeout + Signals (REL-05, REL-06, SRV-02)**
- Each `run_in_executor` DB READ in `run_plugin` wrapped in try/except `sqlite3.OperationalError` -> log + skip poll cycle.
- Each item's `_check_and_buy` runs under `async with asyncio.timeout(item_timeout_secs)`. On timeout: log + continue to next item. `write_queue.put()` calls stay OUTSIDE the timeout context.
- SIGTERM/SIGINT via `loop.add_signal_handler` on POSIX; fall back to `signal.signal` on Windows (`NotImplementedError`).
- On teardown: drain write-queue before `registry.teardown_all()`.

### Claude's Discretion
- (none listed)

### Deferred Ideas (OUT OF SCOPE)
- Real encrypted session/cookie persistence (Fernet, CDP set_cookies restore) -> Phase 23 (REL-04).
- Health surface / per-plugin liveness + heartbeat + health_degraded alert -> Phase 24 (REL-07).
- Live validation of supervisor restart + relaunch under a real browser crash -> UAT debt.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REL-01 | Supervisor wraps each plugin task; unhandled exception absorbed before TaskGroup boundary; plugin restarts with exponential backoff; other plugins keep running | TaskGroup semantics verified; supervise() pattern confirmed; CancelledError propagation rule confirmed |
| REL-02 | Plugin exceeding failure budget (N failures in window) parked; operator notified via dispatcher | failure-budget deque pattern verified; alert_on_errors field confirmed in CheckoutConfig |
| REL-03 | Bot detects dead/disconnected Chrome; cold-restarts plugin browser; re-applies stealth, proxy, login | nodriver exception surface verified; stealth non-persistence confirmed; relaunch() sequence designed |
| REL-05 | Transient SQLite errors on read path caught; single failed read degrades gracefully, not crash | sqlite3.OperationalError identified as correct exception; isolation scope defined |
| REL-06 | Each item's check/buy cycle runs under orchestrator timeout; stalled page cannot freeze other items | asyncio.timeout() behavior verified; write_queue.put() outside confirmed safe |
| SRV-02 | SIGTERM/SIGINT trigger cooperative teardown; signal bridge uses platform-appropriate path | loop.add_signal_handler NotImplementedError on Windows confirmed; signal.signal fallback verified |
</phase_requirements>

## Summary

Phase 22 introduces five orthogonal reliability layers into `core/orchestrator.py` and `core/plugin_base.py`. The keystone is the `supervise()` wrapper: Python's `asyncio.TaskGroup` propagates ALL unhandled child-task exceptions as an `ExceptionGroup`, cancelling every sibling task. A supervised wrapper that catches `Exception` (but re-raises `CancelledError`) guarantees the TaskGroup never sees a plugin crash. This was verified empirically: a bad task that raises causes the good task to never complete in a bare TaskGroup.

The nodriver browser-death exception surface was read directly from installed nodriver 0.50.3 source. When Chrome dies mid-operation, `tab.send()` raises `RuntimeError("WebSocket is not connected")` if the socket is already None, or `ConnectionError("Connection closed")` if a pending future is resolved by the background `_listener` cleanup, or `websockets.exceptions.ConnectionClosed` if `ws.send()` itself fails. The `relaunch()` sequence's `teardown()` -> `Browser.create()` path is confirmed safe. The stealth-persistence research flag from STATE.md is now resolved: `add_script_to_evaluate_on_new_document` is a per-session CDP command that is NOT persisted across a `Browser.stop()` + `Browser.create()`. Every concrete plugin's `setup()` already calls `apply_stealth(self.driver.main_tab)`, so calling `setup()` in `relaunch()` guarantees stealth is re-injected.

Windows `loop.add_signal_handler` raises `NotImplementedError` on `ProactorEventLoop` (verified). The fallback is `signal.signal(SIGTERM/SIGINT, lambda *_: loop.call_soon_threadsafe(root_task.cancel))`, which mirrors the existing `BotService.stop()` pattern. The write-queue flush and signal bridge integrate cleanly into `async_main`'s existing `finally` block.

**Primary recommendation:** Implement `supervise()` as a module-level coroutine in `core/orchestrator.py` that wraps `run_plugin` in a restart loop with failure-budget tracking. Add `relaunch()` and `restore_session()` as concrete/default methods on the `RetailerPlugin` ABC. Wire the signal bridge and write-queue flush into `async_main`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| supervise() wrapper + failure budget | Orchestrator (`core/orchestrator.py`) | Config (`core/config_schema.py`) | TaskGroup runs in orchestrator; config supplies N and backoff params |
| Browser relaunch sequence | Plugin ABC (`core/plugin_base.py`) | Registry (`core/registry.py`) | Browser lifecycle lives in plugin; proxy assignment lives in registry |
| restore_session() stub | Plugin ABC (`core/plugin_base.py`) | Phase 23 | Additive no-op; Phase 23 fills it |
| SQLite read isolation | Orchestrator (`core/orchestrator.py`) | Models layer | run_plugin owns the read calls; wrapping is local to run_plugin |
| Per-item timeout | Orchestrator (`core/orchestrator.py`) | Config (`core/config_schema.py`) | _check_and_buy is called in run_plugin; item_timeout_secs from CheckoutConfig |
| Signal bridge (POSIX + Windows) | Orchestrator (`core/orchestrator.py`) | Service (`core/service.py`) | async_main owns the event loop; service.py's stop() pattern is the model |
| Write-queue flush on shutdown | Orchestrator (`core/orchestrator.py`) | Models layer | Already partially implemented; needs pre-teardown drain of remaining items |
| Restart backoff math | `core/retry.py` (shared) | Orchestrator | compute_delay is the single source of backoff math (REL-08) |

## Standard Stack

### Core (no new dependencies)

| Component | Location | Purpose | Why Standard |
|-----------|----------|---------|--------------|
| `asyncio.TaskGroup` | stdlib | Concurrent plugin coroutines | Already in use; supervisor wraps around it |
| `asyncio.timeout()` | stdlib | Per-item ceiling | Already used for per-step timeouts in P21; mirrors same idiom |
| `RetryPolicy` / `compute_delay` | `core/retry.py` | Restart backoff | REL-08: single backoff source; P21-verified |
| `collections.deque` | stdlib | Failure-budget window tracking | O(1) append/popleft; monotonic timestamp comparison |
| `signal.signal` | stdlib | Windows SIGTERM/SIGINT fallback | Only stdlib option for Windows signal handling |
| `sqlite3.OperationalError` | stdlib | Read-path transient error class | Correct granularity: locks/IO, not schema errors |

**No new packages required.** [VERIFIED: codebase inspection]

## Package Legitimacy Audit

No new external packages are introduced in this phase. All implementation uses the existing installed dependencies and stdlib.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
SIGTERM/SIGINT
     |
     v (loop.add_signal_handler OR signal.signal fallback)
[async_main]
     |-- root_task.cancel() -> CancelledError propagates into TaskGroup
     |
     v
[asyncio.TaskGroup]
     |-- write-queue-drain task (cancelled on shutdown)
     |-- supervise(plugin_A, ...) task   <-- absorbs ALL exceptions
     |-- supervise(plugin_B, ...) task
     |       |
     |       v (try/except Exception loop)
     |    [run_plugin]
     |       |
     |       v (for each item)
     |    [asyncio.timeout(item_timeout_secs)]
     |       |
     |       v
     |    [_check_and_buy]        <-- TimeoutError caught, continue
     |       |
     |       v (write_queue.put is OUTSIDE timeout)
     |    [write_queue.put(...)]
     |
     | -- CancelledError propagates OUT of supervise() -> clean TaskGroup exit
     |
     v (finally block in async_main)
[write-queue flush: drain remaining items manually]
     |
     v
[registry.teardown_all()]  <-- browsers closed last
```

### Recommended Project Structure

No new files or directories. All changes are in:
```
core/
├── orchestrator.py   # supervise(), per-item timeout, read isolation, signal bridge, write-queue flush
├── plugin_base.py    # relaunch() concrete method + restore_session() no-op default
└── retry.py          # unchanged (reused via import)
```

### Pattern 1: supervise() Wrapper

**What:** A coroutine that wraps `run_plugin` in a restart loop, absorbing all `Exception` subclasses before they can propagate to the `TaskGroup`. `CancelledError` is NOT caught so clean shutdown works.

**When to use:** Wrap every `create_task(run_plugin(...))` call in `async_main`.

**Critical invariant:** The outer coroutine passed to `tg.create_task()` must NEVER raise `Exception`. Only `CancelledError` (or `BaseException` subclasses like `SystemExit`) should escape.

```python
# Source: verified by direct asyncio.TaskGroup behavior test in this session
_FAILURE_WINDOW_SECS = 600  # module constant

async def supervise(plugin, write_queue, poll_interval, dispatcher, cfg) -> None:
    """Wrap run_plugin; absorb all exceptions; restart with backoff; park on budget exceeded."""
    from collections import deque
    import time
    from core.retry import RetryPolicy, compute_delay

    checkout_cfg = getattr(cfg, "checkout", None)
    n_budget = getattr(checkout_cfg, "alert_on_errors", 3)
    policy = RetryPolicy(
        max_attempts=999,  # infinite restart attempts; budget gates the park
        backoff_base=getattr(checkout_cfg, "backoff_base", 2.0),
        backoff_jitter=getattr(checkout_cfg, "backoff_jitter", 0.5),
    )
    failure_times: deque = deque()
    attempt = 0

    while True:
        try:
            await run_plugin(plugin, write_queue, poll_interval, dispatcher=dispatcher)
        except asyncio.CancelledError:
            raise  # MUST propagate for clean shutdown (TaskGroup cancel)
        except Exception as exc:
            now = time.monotonic()
            failure_times.append(now)
            # Evict failures outside the rolling window
            while failure_times and (now - failure_times[0]) > _FAILURE_WINDOW_SECS:
                failure_times.popleft()

            writeLog(
                f"[{plugin.__class__.__name__}] crashed ({exc.__class__.__name__}): {attempt+1} failures in window",
                "ERROR",
            )

            if len(failure_times) >= n_budget:
                # Park: notify + stop restarting
                writeLog(
                    f"[{plugin.__class__.__name__}] failure budget exceeded -- parked",
                    "ERROR",
                )
                if dispatcher is not None:
                    from notifications.base import NotificationEvent
                    from datetime import datetime, timezone
                    evt = NotificationEvent(
                        item_name="",
                        item_url="",
                        platform=plugin.__class__.__name__,
                        timestamp=datetime.now(timezone.utc),
                        action="plugin_parked",
                    )
                    await dispatcher.notify(evt)
                return  # exits supervise(); TaskGroup task ends cleanly

            delay = compute_delay(attempt, policy)
            writeLog(f"[{plugin.__class__.__name__}] restarting in {delay:.1f}s", "WARNING")

            # Browser-death path: trigger relaunch before re-entering run_plugin
            if _is_browser_dead_exc(exc):
                try:
                    await plugin.relaunch()
                except Exception as relaunch_exc:
                    writeLog(
                        f"[{plugin.__class__.__name__}] relaunch failed: {relaunch_exc.__class__.__name__}",
                        "ERROR",
                    )
                    # Count as another failure; will park eventually

            await asyncio.sleep(delay)
            attempt += 1
```

### Pattern 2: Browser-Death Detection

**What:** A helper that classifies an exception as browser-dead vs. transient plugin error. Browser-dead -> trigger `relaunch()`. Any `Exception` -> supervise loop handles restart.

**Confirmed exception types from nodriver 0.50.3 source inspection:**

```python
# Source: nodriver/core/connection.py lines 422-433, 479-480 (installed 0.50.3)
import websockets.exceptions

def _is_browser_dead_exc(exc: Exception) -> bool:
    """Return True if the exception indicates a dead/disconnected Chrome process.

    Confirmed exception surface from nodriver 0.50.3 connection.py:
    - RuntimeError("WebSocket is not connected") -- socket is None (L424)
    - ConnectionError("Connection closed") -- _fail_pending_futures path (L480)
    - ConnectionError("Connection closing") -- aclose() path (L241)
    - websockets.exceptions.ConnectionClosed -- direct ws.send() failure
    Also covers OSError/ConnectionRefusedError during relaunch aopen() if Chrome
    port not yet available.
    """
    if isinstance(exc, (ConnectionError, OSError)):
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

### Pattern 3: relaunch() ABC Method

**What:** A concrete method on `RetailerPlugin` that executes the full cold-restart sequence. Called by `supervise()` on browser-death.

**Critical finding (roadmap research flag resolved):** `add_script_to_evaluate_on_new_document` is a per-session CDP command. It is NOT stored to disk or persisted across `Browser.stop()` + `Browser.create()`. The new Chrome process starts with zero registered scripts. Since every concrete plugin's `setup()` calls `apply_stealth(self.driver.main_tab)` (verified in `plugins/shopbot_plugin_amazon.py`), calling `setup()` in `relaunch()` is sufficient to guarantee stealth re-injection.

```python
# In core/plugin_base.py -- concrete (not abstract) so existing plugins inherit it
async def relaunch(self) -> None:
    """Cold-restart the browser: teardown -> proxy -> setup (stealth + proxy auth) -> restore_session -> login.

    Called by supervise() on browser-death detection. Sequence is ordered:
    1. teardown() -- close the dead browser process (safe to call if already dead)
    2. assign_proxy -- advance proxy pool for the new browser instance
    3. setup() -- Browser.create() + apply_stealth() + setup_proxy_auth() (stealth MUST re-inject)
    4. restore_session() -- no-op stub in Phase 22; Phase 23 replaces with Fernet cookie restore
    5. login() -- re-authenticate with the retail platform
    """
    plugin_name = self.__class__.__name__
    writeLog(f"[{plugin_name}] relaunch: tearing down", "INFO")
    try:
        await self.teardown()
    except Exception as exc:
        writeLog(f"[{plugin_name}] teardown error during relaunch: {exc.__class__.__name__}", "WARNING")

    # Proxy re-assignment: the registry reference must be available
    # supervise() passes registry so relaunch() can call registry.assign_proxy(self)
    # OR: plugin stores _registry ref set during initial setup
    # Decision: pass registry into relaunch() OR store as self._registry at setup time
    # (planner chooses; both are clean -- see Open Question 1)

    writeLog(f"[{plugin_name}] relaunch: starting new browser", "INFO")
    await self.setup()  # calls apply_stealth() internally -- VERIFIED

    session_restored = await self.restore_session()
    if not session_restored:
        writeLog(f"[{plugin_name}] relaunch: restore_session returned False; re-logging in", "INFO")
        await self.login()
    else:
        writeLog(f"[{plugin_name}] relaunch: session restored; skipping login", "INFO")

async def restore_session(self) -> bool:
    """Restore browser session from encrypted cookies. No-op stub; Phase 23 replaces.

    Returns False always in Phase 22. Additive non-abstract method; PLUGIN_API_VERSION stays 2.
    """
    return False
```

### Pattern 4: Per-Item Timeout with write_queue.put Outside

**What:** `async with asyncio.timeout(item_timeout_secs)` wraps only the `_check_and_buy` call. The `write_queue.put()` calls inside `_check_and_buy` stay where they are (already outside `_attempt_buy`'s retry loop per WR-02). `TimeoutError` is caught at the item loop level.

**Verified:** `asyncio.TimeoutError is TimeoutError` on Python 3.13 (confirmed). The context manager raises `TimeoutError` (builtin).

```python
# In run_plugin -- replace the bare _check_and_buy call
from core.config_schema import CheckoutConfig
item_timeout = getattr(getattr(cfg, "checkout", None), "item_timeout_secs", 120)
# ... (get item_timeout from plugin.config in run_plugin context)

for name, link, auto_buy, quantity, purchased in items:
    if purchased:
        continue
    if not any(p in (link or "") for p in plugin.domain_patterns):
        continue
    # write_queue.put() calls are already inside _check_and_buy and _enqueue_buy_result
    # Those functions call write_queue.put() OUTSIDE _attempt_buy -- they remain outside
    # the timeout so a timed-out item cannot orphan a pending DB write (REL-06).
    try:
        async with asyncio.timeout(item_timeout):
            await _check_and_buy(plugin, name, link, auto_buy, write_queue, dispatcher=dispatcher)
    except TimeoutError:
        writeLog(
            f"[{plugin.__class__.__name__}] item timeout ({item_timeout}s): {name} -- skipping",
            "WARNING",
        )
        # continue to next item
```

**Important nuance:** `write_queue.put()` in `_check_and_buy` is called AFTER `_check_and_buy` already has a result (available/not). The timeout fires DURING `_check_and_buy` execution. If the item times out before reaching `write_queue.put()`, the put is simply not reached -- no orphan. If the item reaches `write_queue.put()` before the timeout, the write is already enqueued and safe. This is correct behavior. [VERIFIED: flow analysis of existing orchestrator.py]

### Pattern 5: SQLite Read Isolation

**What:** Wrap each `run_in_executor` DB READ call in `run_plugin` with `try/except sqlite3.OperationalError`. Do NOT catch `sqlite3.DatabaseError` (parent class) -- that would mask schema corruption which should propagate.

```python
# Source: STATE.md research flag "Pitfall 11" + verified sqlite3 exception hierarchy
import sqlite3

# In run_plugin, replace bare run_in_executor read calls:
try:
    items = await loop.run_in_executor(None, get_items_sync)
except sqlite3.OperationalError as exc:
    writeLog(f"[{plugin.__class__.__name__}] DB read error: {exc} -- skipping poll cycle", "WARNING")
    await asyncio.sleep(poll_interval)
    continue
```

Calls to wrap (all READ-path `run_in_executor` in `run_plugin`):
- `get_items_sync` -- main item list read
- `get_item_notification_state_sync` -- inside `_check_and_buy` (called via run_in_executor there)
- `get_last_price_sync` / `get_item_price_config_sync` / `get_price_alert_state_sync` -- inside `_evaluate_price_triggers`

For reads INSIDE `_check_and_buy`, the existing `try/except Exception` blocks already catch errors and continue. The additional requirement is to catch `sqlite3.OperationalError` at the `run_plugin` level for the items-list read (the outer loop trigger).

### Pattern 6: Windows Signal Bridge

**What:** Platform-conditional signal registration. On POSIX, use `loop.add_signal_handler`. On Windows (ProactorEventLoop), `add_signal_handler` raises `NotImplementedError` (verified on Python 3.13/Windows 11).

```python
# Source: verified by direct execution on Windows 11, Python 3.13
import signal
import sys

def _register_signals(loop, root_task: asyncio.Task) -> None:
    """Register SIGTERM/SIGINT handlers for cooperative teardown (SRV-02).

    POSIX: loop.add_signal_handler (thread-safe, runs in event loop)
    Windows: signal.signal fallback with loop.call_soon_threadsafe bridge
    """
    def _shutdown_handler(*_) -> None:
        writeLog("Shutdown signal received -- initiating teardown", "INFO")
        loop.call_soon_threadsafe(root_task.cancel)

    try:
        loop.add_signal_handler(signal.SIGTERM, _shutdown_handler)
        loop.add_signal_handler(signal.SIGINT, _shutdown_handler)
    except NotImplementedError:
        # Windows ProactorEventLoop does not support add_signal_handler
        signal.signal(signal.SIGTERM, _shutdown_handler)
        signal.signal(signal.SIGINT, _shutdown_handler)
```

**Integration point:** `async_main` does not have direct access to its own task. The signal bridge must be wired from the caller of `async_main`, OR `asyncio.current_task()` can be read inside `async_main` after `asyncio.run()` creates it. Pattern: assign `asyncio.current_task()` at the top of `async_main` to get the root task reference, then pass to `_register_signals`.

**Constraint:** `service.py`'s `BotService.stop()` already uses `loop.call_soon_threadsafe(task.cancel)`. The new signal bridge uses the same mechanism, consistent with established pattern.

### Pattern 7: Write-Queue Flush Before teardown_all

**What:** After `asyncio.TaskGroup` exits (all tasks cancelled), drain remaining items from the write queue before closing browsers.

**Pitfall:** The current `await asyncio.wait_for(write_queue.join(), timeout=10)` in the `finally` block will time out after 10s because the `_write_queue_drain` task was cancelled mid-item. The in-flight item's `task_done()` was never called, leaving `unfinished_tasks > 0`. The 10s timeout is a safety valve but the in-flight item MAY be lost.

**Better approach:** After the TaskGroup exits, perform a manual drain pass before `queue.join()`:

```python
# In async_main finally block -- replace existing queue flush
async def _flush_write_queue(queue: asyncio.Queue, loop) -> None:
    """Drain remaining items after TaskGroup exits (write-queue drain task was cancelled).

    Processes items synchronously so pending DB writes are not lost on SIGTERM.
    """
    while not queue.empty():
        item = queue.get_nowait()
        try:
            await _dispatch_write(loop, item)
        except Exception as exc:
            writeLog(f"Write-queue flush error for {item!r}: {exc}", "ERROR")
        finally:
            queue.task_done()

# In async_main finally:
finally:
    loop = asyncio.get_running_loop()
    await _flush_write_queue(write_queue, loop)
    # queue.join() should now return immediately (or very quickly)
    try:
        await asyncio.wait_for(write_queue.join(), timeout=5)
    except asyncio.TimeoutError:
        writeLog("Write queue join timed out after manual flush", "WARNING")
    await registry.teardown_all()
```

**Verified:** Manual drain approach confirmed correct by direct test in this session. After `_write_queue_drain` cancellation, `queue.qsize()` shows remaining items. Manual `get_nowait()` + `task_done()` + `_dispatch_write()` processes them correctly.

### Anti-Patterns to Avoid

- **Catching BaseException in supervise():** Catches `SystemExit`, `KeyboardInterrupt`, and `CancelledError`. Only `except Exception` is correct. `CancelledError` must propagate for clean shutdown.
- **Catching CancelledError and resuming:** Once `CancelledError` is raised in `supervise()`, re-raising is mandatory. Swallowing it prevents the TaskGroup from completing shutdown.
- **Calling queue.join() without manual drain:** After the drain task is cancelled, `join()` will hang for the in-flight item's unfinished count. Always do a manual drain pass first.
- **Using asyncio.timeout inside write_queue.put:** `put()` on an unbounded Queue is instant (no actual await needed). Even if put were slow, it MUST NOT be inside the item timeout context.
- **Calling loop.add_signal_handler on Windows without try/except:** Always wrap in `try/except NotImplementedError` with `signal.signal` fallback.
- **Storing relaunch failure as a separate failure counter:** The same failure-budget counter tracks all restart failures including relaunch failures. No separate counter needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff with jitter | Custom backoff math in supervise() | `compute_delay(attempt, policy)` from `core/retry.py` | REL-08: single source; already tested |
| Failure-budget windowing | Ring buffer / heap | `collections.deque` with monotonic timestamps | Standard Python pattern; O(1) ops |
| Cross-platform signals | Custom OS detection | `try: add_signal_handler; except NotImplementedError: signal.signal` | Simplest correct pattern |
| Browser-process liveness check | Polling `browser.stopped` property | Catch exceptions on tab operations | nodriver exposes `browser.stopped` property but exception-on-use is the natural detection surface |

**Key insight:** All reliability machinery reuses existing code. The supervisor is pure async Python using stdlib only.

## Common Pitfalls

### Pitfall 1: CancelledError Swallowed in supervise()
**What goes wrong:** `except Exception` catches `CancelledError` in Python versions where it inherits from `Exception` (it inherits from `BaseException` in Python 3.8+, so this is actually safe -- but worth confirming).
**Root cause:** Confusion about CancelledError's inheritance chain.
**How to avoid:** Verified: `asyncio.CancelledError` inherits from `BaseException`, NOT `Exception`, in Python 3.8+. Therefore `except Exception` does NOT catch `CancelledError`. The pattern is safe as written. [VERIFIED: Python 3.13 test in this session]
**Warning signs:** Plugin cannot be stopped with Ctrl+C; shutdown hangs indefinitely.

### Pitfall 2: Stealth Not Re-Injected After Relaunch
**What goes wrong:** `add_script_to_evaluate_on_new_document` is assumed persistent; new browser navigates without stealth patches; bot detected.
**Root cause:** CDP scripts are session-scoped. They live in the devtools session, NOT in a Chrome profile or disk cache.
**How to avoid:** Call `relaunch()` which calls `setup()` which calls `apply_stealth()`. NEVER call `Browser.create()` directly without also calling `apply_stealth()` on the new tab. [VERIFIED: nodriver 0.50.3 source + CDP documentation]
**Warning signs:** Ban responses immediately after relaunch; `navigator.webdriver` returns true.

### Pitfall 3: TaskGroup ExceptionGroup vs. bare except
**What goes wrong:** Wrapping the entire `async with asyncio.TaskGroup()` in a bare `except Exception` without `except*` misses the `ExceptionGroup` wrapper. The current code already uses `except* KeyboardInterrupt` (correct); supervise() eliminates the need for the TaskGroup to catch plugin exceptions at all.
**How to avoid:** Supervise() absorbs everything so the TaskGroup only ever sees `CancelledError` (clean shutdown) or `KeyboardInterrupt` (already handled). [VERIFIED: empirical test of TaskGroup behavior]

### Pitfall 4: Queue.join() Deadlock After Drain-Task Cancellation
**What goes wrong:** `_write_queue_drain` is cancelled while an item is in-flight (gotten but not task_done'd). `queue.join()` waits forever (or until 10s timeout) for that item's unfinished count.
**Root cause:** asyncio.Queue uses an internal `_unfinished_tasks` counter incremented by `put()` and decremented by `task_done()`. Cancellation skips `task_done()`.
**How to avoid:** Always do a manual drain pass (`get_nowait()` loop) before `queue.join()` in the finally block. [VERIFIED: direct test in this session]

### Pitfall 5: proxy assign_proxy Call Order in relaunch()
**What goes wrong:** `setup()` is called before `assign_proxy(plugin)`. Plugin's `_proxy` is stale (old entry, possibly retired). New browser connects through retired proxy.
**How to avoid:** Always call `assign_proxy` BEFORE `setup()` in the relaunch sequence. The plugin's `setup()` method reads `self._proxy` to build browser args. [VERIFIED: shopbot_plugin_amazon.py setup() reads `getattr(self, "_proxy", None)` before calling `build_proxy_browser_args`]

### Pitfall 6: signal.signal Handler Threading on Windows
**What goes wrong:** On Windows, `signal.signal` handlers run in the main Python thread. If `async_main` is running in the main thread (via `asyncio.run()`), calling `loop.call_soon_threadsafe(task.cancel)` from the signal handler is correct and safe because the handler itself runs in the main thread but the loop may be in its IO poll at that moment.
**How to avoid:** Always use `loop.call_soon_threadsafe` (not `loop.call_soon`) in the signal handler, even though on Windows the handler IS in the main thread. The threadsafe variant is always safe and documents intent clearly.
**Note:** `signal.signal(SIGTERM, ...)` on Windows only fires if the process receives an actual SIGTERM (e.g., from Docker). Ctrl+C fires SIGINT which also maps to the same handler.

### Pitfall 7: sqlite3.OperationalError vs. sqlite3.DatabaseError Scope
**What goes wrong:** Catching `sqlite3.DatabaseError` (the parent) also catches `sqlite3.IntegrityError`, `sqlite3.ProgrammingError`, etc. -- which are programmer errors that should surface, not be swallowed.
**Root cause:** Overly broad exception scope.
**How to avoid:** Catch ONLY `sqlite3.OperationalError` for transient read failures. [VERIFIED: STATE.md Pitfall 11; sqlite3 exception hierarchy confirmed]

## Code Examples

### supervise() wrapper insert point in async_main
```python
# Source: core/orchestrator.py async_main -- replace existing create_task calls
# Before (L499-503):
#     for plugin in registry._active_plugins:
#         tg.create_task(
#             run_plugin(plugin, write_queue, poll_interval, dispatcher=dispatcher),
#             name=f"poll-{plugin.__class__.__name__}",
#         )
#
# After:
    for plugin in registry._active_plugins:
        tg.create_task(
            supervise(plugin, write_queue, poll_interval, dispatcher=dispatcher, cfg=cfg),
            name=f"poll-{plugin.__class__.__name__}",
        )
```

### run_plugin read isolation (items-list only)
```python
# Source: core/orchestrator.py run_plugin L172 -- wrap the get_items_sync call
async def run_plugin(plugin, write_queue, poll_interval, dispatcher=None, cfg=None) -> None:
    loop = asyncio.get_running_loop()
    checkout_cfg = getattr(cfg, "checkout", None) if cfg else None
    item_timeout = getattr(checkout_cfg, "item_timeout_secs", 120)

    while True:
        try:
            items = await loop.run_in_executor(None, get_items_sync)
        except sqlite3.OperationalError as exc:
            writeLog(f"[{plugin.__class__.__name__}] items read error: {exc} -- skipping", "WARNING")
            await asyncio.sleep(_get_plugin_sleep(plugin, poll_interval))
            continue

        for name, link, auto_buy, quantity, purchased in items:
            if purchased:
                continue
            if not any(p in (link or "") for p in plugin.domain_patterns):
                continue
            try:
                async with asyncio.timeout(item_timeout):
                    await _check_and_buy(plugin, name, link, auto_buy, write_queue, dispatcher=dispatcher)
            except TimeoutError:
                writeLog(
                    f"[{plugin.__class__.__name__}] timeout ({item_timeout}s): {name} -- skipping",
                    "WARNING",
                )
        await asyncio.sleep(_get_plugin_sleep(plugin, poll_interval))
```

## Runtime State Inventory

Not applicable -- this is a greenfield feature phase (new code paths, no renames or data migrations).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Bare `run_plugin` in TaskGroup | `supervise(run_plugin)` in TaskGroup | Phase 22 | One plugin crash can no longer kill all siblings |
| No restart on browser death | `relaunch()` with full stealth restore | Phase 22 | Browser death is recoverable without operator intervention |
| No per-item ceiling | `asyncio.timeout(item_timeout_secs)` | Phase 22 | Stalled items cannot freeze the whole retailer loop |
| SIGTERM silently kills Chrome | Signal bridge + write-queue flush + teardown_all | Phase 22 | Container/systemd stop is clean; no orphaned Chrome processes |
| `CancelledError` and exceptions conflated | `except Exception` (not `except BaseException`) | Phase 22 | CancelledError propagates correctly through supervise() |

**Deprecated/outdated:**
- Phase 21's per-step `asyncio.timeout` is NOT replaced by the per-item timeout; they are complementary layers. Per-step bounds each DOM action (~30s); per-item bounds the entire item cycle (~120s).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `assign_proxy` should be called by the supervisor before relaunch's `setup()`. The planner must choose between passing `registry` into `relaunch()` vs. storing `self._registry` on the plugin at initial setup. | Architecture Patterns Pattern 3 | Either approach is correct; wrong choice adds one extra line. Low risk. |
| A2 | The notification dispatcher accepts `action="plugin_parked"` without schema validation errors (no strict action allowlist found in NotificationEvent). | Pattern 1 | If NotificationEvent validates action values, park notification dispatch fails silently. |

**If this table is empty:** No -- two low-risk assumptions noted above. Both are implementation-detail choices for the planner.

## Open Questions

1. **How does supervise() get a reference for assign_proxy?**
   - What we know: `registry.assign_proxy(plugin)` must be called before `setup()` in `relaunch()`. The `registry` object exists in `async_main`'s scope but not in `plugin_base.py`.
   - What's unclear: Best wiring -- pass registry into `relaunch(plugin)` as a parameter, OR have the orchestrator call `registry.assign_proxy(plugin)` before calling `plugin.relaunch()` (i.e., supervise() does the assign_proxy call, not relaunch()).
   - Recommendation: Simplest pattern -- supervise() calls `registry.assign_proxy(plugin)` directly before calling `plugin.relaunch()`. The registry reference is in async_main's closure so supervise() receives it as a parameter. `relaunch()` itself does NOT need a registry reference.

2. **Should NotificationEvent.action have "plugin_parked" added to any allowlist?**
   - What we know: NotificationEvent is in `notifications/base.py`. The action field is a plain `str` (no Literal type constraint seen in earlier research).
   - What's unclear: Whether any downstream notifier validates the action value or uses it in routing.
   - Recommendation: Check `notifications/base.py` at plan time. If action is unrestricted `str`, no change needed. If it has a Literal type, add "plugin_parked".

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | `asyncio.timeout()` | Yes | 3.13.13 | n/a |
| nodriver | Browser lifecycle | Yes | 0.50.3 | n/a |
| websockets | Browser-death exception type | Yes | 14.1 | Catch ConnectionError only (sufficient) |
| collections.deque | Failure-budget window | Yes | stdlib | n/a |
| signal | SIGTERM/SIGINT bridge | Yes | stdlib | n/a |

**Missing dependencies with no fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio 1.3.0 (asyncio_mode=auto) |
| Config file | `pytest.ini` or `pyproject.toml` (existing) |
| Quick run command | `pytest tests/test_orchestrator.py -x` |
| Full suite command | `pytest` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REL-01 | Crash one plugin, assert siblings keep running | unit | `pytest tests/test_supervisor.py::test_crash_one_plugin_others_survive -x` | No -- Wave 0 |
| REL-01 | supervise() re-raises CancelledError (not absorbed) | unit | `pytest tests/test_supervisor.py::test_supervise_propagates_cancelled -x` | No -- Wave 0 |
| REL-02 | N=3 failures within 600s -> plugin parked, dispatcher notified | unit | `pytest tests/test_supervisor.py::test_failure_budget_parks_plugin -x` | No -- Wave 0 |
| REL-02 | Failure outside 600s window does not count toward budget | unit | `pytest tests/test_supervisor.py::test_failure_budget_window_eviction -x` | No -- Wave 0 |
| REL-03 | relaunch() calls teardown -> assign_proxy -> setup -> restore_session -> login in order | unit | `pytest tests/test_plugin_base.py::test_relaunch_sequence_order -x` | No -- Wave 0 |
| REL-03 | relaunch() calls setup() which calls apply_stealth (stealth re-injected) | unit | `pytest tests/test_plugin_base.py::test_relaunch_apply_stealth_called -x` | No -- Wave 0 |
| REL-05 | sqlite3.OperationalError on get_items_sync -> log + skip cycle, no crash | unit | `pytest tests/test_orchestrator.py::test_read_isolation_operational_error -x` | No -- Wave 0 |
| REL-05 | sqlite3.DatabaseError (not OperationalError) is NOT caught (propagates) | unit | `pytest tests/test_orchestrator.py::test_read_isolation_database_error_propagates -x` | No -- Wave 0 |
| REL-06 | Item timeout fires -> log + continue to next item | unit | `pytest tests/test_orchestrator.py::test_item_timeout_continues_to_next -x` | No -- Wave 0 |
| REL-06 | write_queue.put after timeout fires still executes (outside context) | unit | `pytest tests/test_orchestrator.py::test_write_queue_put_outside_timeout -x` | No -- Wave 0 |
| SRV-02 | Windows path: signal.signal used when add_signal_handler raises NotImplementedError | unit | `pytest tests/test_orchestrator.py::test_signal_bridge_windows_fallback -x` | No -- Wave 0 |
| SRV-02 | POSIX path: loop.add_signal_handler used when available | unit | `pytest tests/test_orchestrator.py::test_signal_bridge_posix_path -x` | No -- Wave 0 |
| SRV-02 | Write-queue flush drains remaining items before teardown_all | unit | `pytest tests/test_orchestrator.py::test_write_queue_flush_before_teardown -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_supervisor.py tests/test_orchestrator.py tests/test_plugin_base.py -x`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_supervisor.py` -- covers REL-01, REL-02 (supervise loop + failure budget)
- [ ] Additional tests in `tests/test_orchestrator.py` -- covers REL-05, REL-06, SRV-02
- [ ] Additional tests in `tests/test_plugin_base.py` -- covers REL-03 (relaunch sequence)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | login() is retailer-specific, not user auth |
| V3 Session Management | Yes (partial) | restore_session() stub is safe; Phase 23 owns the actual cookie handling |
| V4 Access Control | No | n/a |
| V5 Input Validation | No | No new external input |
| V6 Cryptography | No | Phase 22 ships a no-op stub only; Phase 23 owns Fernet |

### Known Threat Patterns for Supervisor + Signal Handling

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Signal handler writes to shared state without lock | Tampering | Use `loop.call_soon_threadsafe` -- the only thread-safe bridge |
| Park notification leaks plugin internals | Info Disclosure | NotificationEvent action="plugin_parked"; item_name/url are empty strings for park events |
| CVV in error messages during relaunch | Info Disclosure | Use `exc.__class__.__name__` not `str(exc)` in all relaunch/supervise log calls |

## Sources

### Primary (HIGH confidence)
- nodriver 0.50.3 installed source (`core/connection.py`, `core/browser.py`) -- browser-death exceptions, stop() semantics, aopen/attach flow
- Python 3.13 stdlib documentation -- asyncio.TaskGroup, asyncio.timeout, asyncio.CancelledError inheritance
- `core/orchestrator.py` (codebase) -- existing TaskGroup structure, write-queue drain, async_main layout
- `core/plugin_base.py` (codebase) -- existing ABC methods, setup/teardown signatures
- `core/retry.py` (codebase) -- RetryPolicy, compute_delay API
- `core/config_schema.py` (codebase) -- CheckoutConfig fields verified
- `core/stealth.py` (codebase) -- apply_stealth() confirmed called on main_tab in setup()
- `plugins/shopbot_plugin_amazon.py` (codebase) -- setup() pattern with apply_stealth confirmed

### Secondary (MEDIUM confidence)
- CDP `Page.addScriptToEvaluateOnNewDocument` documentation -- session-scoped, not persisted across process restart (confirmed from nodriver 0.50.3 cdp/page.py + CDP protocol knowledge)
- Python signal module documentation -- signal.signal() behavior on Windows

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH -- all components are existing codebase or verified stdlib
- Architecture: HIGH -- exception surface confirmed from installed source; TaskGroup semantics empirically verified
- Pitfalls: HIGH -- all pitfalls either verified by direct test or by source inspection
- stealth-persistence answer: HIGH -- confirmed by reading CDP page.py and connection.py from installed nodriver 0.50.3; no guessing

**Research date:** 2026-06-12
**Valid until:** 2026-07-12 (nodriver 0.50.3 pinned; stdlib stable)
