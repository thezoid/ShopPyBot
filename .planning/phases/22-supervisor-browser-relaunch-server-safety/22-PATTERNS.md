# Phase 22: Supervisor + Browser Relaunch + Server Safety - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 3 (core/orchestrator.py, core/plugin_base.py, core/retry.py) + tests
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `core/orchestrator.py` (supervise wrapper) | supervisor/coroutine | event-driven | `core/orchestrator.py` run_plugin L172 + TaskGroup L497 | exact |
| `core/orchestrator.py` (_is_browser_dead_exc) | utility/helper | request-response | `core/plugin_base.py` _handle_ban L50 | role-match |
| `core/orchestrator.py` (per-item asyncio.timeout) | orchestration | request-response | `core/orchestrator.py` run_plugin item loop L172-183 | exact-insert |
| `core/orchestrator.py` (sqlite read isolation) | orchestration | CRUD | `core/orchestrator.py` run_plugin L176 (bare call, pre-wrap) | exact-insert |
| `core/orchestrator.py` (signal bridge + write-queue flush) | lifecycle | event-driven | `core/service.py` BotService.stop() L179-195 | role-match |
| `core/plugin_base.py` (relaunch + restore_session) | ABC method | request-response | `core/plugin_base.py` get_price L78, place_order_guarded L96, get_active_tab L87 | exact (additive concrete method pattern) |
| `core/retry.py` | utility | batch | `core/retry.py` as-is (import only) | exact |
| `tests/test_supervisor.py` (new) | test | unit | `tests/test_orchestrator.py` L69-123 + `tests/conftest.py` fake_plugin L125 | role-match |
| `tests/test_plugin_base.py` (additions) | test | unit | `tests/test_plugin_base.py` L70-80 (async no-op defaults) | exact |
| `tests/test_orchestrator.py` (additions) | test | unit | `tests/test_orchestrator.py` L202-219 + conftest L125 | exact |

## Pattern Assignments

### `core/orchestrator.py` -- supervise() wrapper

**Analog:** `core/orchestrator.py` async_main TaskGroup block L496-511

**Imports pattern** (existing orchestrator.py L14-42 -- supervise adds):
```python
import signal
import sqlite3
import time
from collections import deque
from core.retry import RetryPolicy, compute_delay  # already imported RetryPolicy, with_retry
```

**Existing create_task pattern to replace** (L499-503):
```python
# BEFORE -- bare run_plugin in TaskGroup:
for plugin in registry._active_plugins:
    tg.create_task(
        run_plugin(plugin, write_queue, poll_interval, dispatcher=dispatcher),
        name=f"poll-{plugin.__class__.__name__}",
    )

# AFTER -- wrap with supervise():
for plugin in registry._active_plugins:
    tg.create_task(
        supervise(plugin, write_queue, poll_interval, dispatcher=dispatcher, cfg=cfg),
        name=f"poll-{plugin.__class__.__name__}",
    )
```

**supervise() structure** (new module-level coroutine, place before async_main):
```python
_FAILURE_WINDOW_SECS = 600

async def supervise(plugin, write_queue, poll_interval, dispatcher, cfg) -> None:
    checkout_cfg = getattr(cfg, "checkout", None)
    n_budget = getattr(checkout_cfg, "alert_on_errors", 3)
    policy = RetryPolicy(
        max_attempts=999,
        backoff_base=getattr(checkout_cfg, "backoff_base", 2.0),
        backoff_jitter=getattr(checkout_cfg, "backoff_jitter", 0.5),
    )
    failure_times: deque = deque()
    attempt = 0
    while True:
        try:
            await run_plugin(plugin, write_queue, poll_interval, dispatcher=dispatcher, cfg=cfg)
        except asyncio.CancelledError:
            raise   # MUST propagate -- CancelledError inherits BaseException not Exception
        except Exception as exc:
            now = time.monotonic()
            failure_times.append(now)
            while failure_times and (now - failure_times[0]) > _FAILURE_WINDOW_SECS:
                failure_times.popleft()
            writeLog(f"[{plugin.__class__.__name__}] crashed: {exc.__class__.__name__}", "ERROR")
            if len(failure_times) >= n_budget:
                writeLog(f"[{plugin.__class__.__name__}] parked after {n_budget} failures", "ERROR")
                if dispatcher is not None:
                    await dispatcher.notify(_build_event("", "", plugin.__class__.__name__, "plugin_parked"))
                return   # clean exit from TaskGroup task
            if _is_browser_dead_exc(exc):
                try:
                    await plugin.relaunch()
                except Exception as rel_exc:
                    writeLog(f"[{plugin.__class__.__name__}] relaunch error: {rel_exc.__class__.__name__}", "ERROR")
            delay = compute_delay(attempt, policy)
            writeLog(f"[{plugin.__class__.__name__}] restart in {delay:.1f}s", "WARNING")
            await asyncio.sleep(delay)
            attempt += 1
```

**Key constraint (RESEARCH Pitfall 1):** `except Exception` does NOT catch `asyncio.CancelledError` because `CancelledError` inherits from `BaseException`, not `Exception`, in Python 3.8+. Verified on Python 3.13.

### `core/orchestrator.py` -- _is_browser_dead_exc helper

**Analog:** `core/plugin_base.py` _handle_ban L50-62 (exception-type-check helper returning bool)

**_handle_ban pattern to copy structure from** (plugin_base.py L50-62):
```python
def _handle_ban(self, body_text: str) -> bool:
    if not _is_ban_response(0, body_text):
        return False
    proxy = getattr(self, "_proxy", None)
    pool = getattr(self, "_pool", None)
    if proxy and pool:
        pool.record_failure(proxy)
    return True
```

**New helper** (place at module level in orchestrator.py, before supervise()):
```python
def _is_browser_dead_exc(exc: Exception) -> bool:
    """Return True if exc indicates a dead/disconnected Chrome process.

    Exception surface from nodriver 0.50.3 connection.py:
    - RuntimeError("WebSocket is not connected") -- socket is None
    - ConnectionError("Connection closed") / ("Connection closing")
    - websockets.exceptions.ConnectionClosed -- ws.send() failure
    - OSError/ConnectionRefusedError -- port not yet available on relaunch
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

### `core/orchestrator.py` -- per-item asyncio.timeout in run_plugin

**Analog:** `core/orchestrator.py` run_plugin item loop L172-183 (existing call site to wrap)

**Existing run_plugin item loop** (L172-183):
```python
async def run_plugin(plugin, write_queue: asyncio.Queue, poll_interval: float, dispatcher=None) -> None:
    loop = asyncio.get_running_loop()
    while True:
        items = await loop.run_in_executor(None, get_items_sync)
        for name, link, auto_buy, quantity, purchased in items:
            if purchased:
                continue
            if not any(p in (link or "") for p in plugin.domain_patterns):
                continue
            await _check_and_buy(plugin, name, link, auto_buy, write_queue, dispatcher=dispatcher)
        await asyncio.sleep(_get_plugin_sleep(plugin, poll_interval))
```

**Modified run_plugin** (add cfg parameter, sqlite isolation, per-item timeout):
```python
async def run_plugin(plugin, write_queue: asyncio.Queue, poll_interval: float, dispatcher=None, cfg=None) -> None:
    loop = asyncio.get_running_loop()
    checkout_cfg = getattr(cfg, "checkout", None)
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
                    f"[{plugin.__class__.__name__}] item timeout ({item_timeout}s): {name} -- skipping",
                    "WARNING",
                )
        await asyncio.sleep(_get_plugin_sleep(plugin, poll_interval))
```

**Critical:** `write_queue.put()` calls live inside `_check_and_buy` / `_enqueue_buy_result`, which are called after the result is already known. A timeout during `_check_and_buy` simply prevents reaching `put()` -- no orphan write (REL-06).

### `core/orchestrator.py` -- signal bridge + write-queue flush in async_main

**Analog:** `core/service.py` BotService.stop() L179-195

**service.py stop() pattern** (the model):
```python
# core/service.py L179-195
def stop(self) -> None:
    if not self._running or self._loop is None:
        return
    loop = self._loop
    task = self._task
    if task is not None and loop is not None:
        loop.call_soon_threadsafe(task.cancel)   # <-- thread-safe cancel pattern
    if self._thread is not None:
        self._thread.join(timeout=15.0)
```

**New _register_signals helper** (place near async_main):
```python
def _register_signals(loop, root_task: asyncio.Task) -> None:
    """Register SIGTERM/SIGINT for cooperative teardown (SRV-02).

    POSIX: loop.add_signal_handler (thread-safe, in event loop).
    Windows ProactorEventLoop: raises NotImplementedError; fallback to signal.signal.
    Uses loop.call_soon_threadsafe in both paths (mirrors BotService.stop() pattern).
    """
    def _shutdown(*_) -> None:
        writeLog("Shutdown signal received -- initiating teardown", "INFO")
        loop.call_soon_threadsafe(root_task.cancel)

    try:
        loop.add_signal_handler(signal.SIGTERM, _shutdown)
        loop.add_signal_handler(signal.SIGINT, _shutdown)
    except NotImplementedError:
        # Windows ProactorEventLoop does not support add_signal_handler
        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)
```

**async_main integration point** (top of async_main, after loop = asyncio.get_running_loop()):
```python
root_task = asyncio.current_task()
_register_signals(loop, root_task)
```

**Write-queue flush** -- replace existing finally block (L506-511):
```python
# BEFORE (L506-511):
finally:
    try:
        await asyncio.wait_for(write_queue.join(), timeout=10)
    except asyncio.TimeoutError:
        writeLog("Write queue flush timed out on shutdown", "WARNING")
    await registry.teardown_all()

# AFTER:
finally:
    await _flush_write_queue(write_queue, loop)
    try:
        await asyncio.wait_for(write_queue.join(), timeout=5)
    except asyncio.TimeoutError:
        writeLog("Write queue join timed out after manual flush", "WARNING")
    await registry.teardown_all()
```

**New _flush_write_queue helper** (place near _write_queue_drain L383):
```python
async def _flush_write_queue(queue: asyncio.Queue, loop) -> None:
    """Drain remaining items after TaskGroup exits (drain task was cancelled).

    The _write_queue_drain task may have an in-flight item with task_done() not yet
    called (queue.join() would hang). Manual get_nowait() + task_done() drains it.
    """
    while not queue.empty():
        item = queue.get_nowait()
        try:
            await _dispatch_write(loop, item)
        except Exception as exc:
            writeLog(f"Write-queue flush error for {item!r}: {exc}", "ERROR")
        finally:
            queue.task_done()
```

### `core/plugin_base.py` -- relaunch() and restore_session()

**Analog:** `core/plugin_base.py` get_price L78-85, get_active_tab L87-94, place_order_guarded L96-118 (additive concrete methods on ABC, no version bump)

**Additive concrete method pattern** (plugin_base.py L78-94):
```python
async def get_price(self, url: str) -> int | None:
    """Return the current item price as integer cents, or None if unsupported.

    Default returns None (price monitoring unsupported for this plugin).
    PLUGIN_API_VERSION stays 2 -- additive non-abstract method (PRICE-02).
    Override in platform plugins that can scrape a live price.
    """
    return None

def get_active_tab(self):
    """Return the live tab for confirmation detection after auto_buy().

    Default returns driver.main_tab. Override in plugins that store the
    last-navigated tab explicitly (Amazon, BestBuy).
    PLUGIN_API_VERSION stays 2 -- additive concrete method (BUY-03).
    """
    return getattr(self.driver, "main_tab", None)
```

**New methods to add** (place after teardown() L128-130):
```python
async def relaunch(self) -> None:
    """Cold-restart the browser: teardown -> setup (stealth + proxy) -> restore_session -> login.

    Called by supervise() on browser-death detection.
    proxy re-assignment (assign_proxy) is the supervisor's responsibility BEFORE calling relaunch().
    PLUGIN_API_VERSION stays 2 -- additive concrete method (REL-03).

    Stealth is guaranteed re-injected: every plugin's setup() calls apply_stealth(self.driver.main_tab).
    CDP add_script_to_evaluate_on_new_document is session-scoped and NOT persisted across
    Browser.stop() + Browser.create(). setup() is the single injection point. [VERIFIED nodriver 0.50.3]
    """
    plugin_name = self.__class__.__name__
    writeLog(f"[{plugin_name}] relaunch: tearing down", "INFO")
    try:
        await self.teardown()
    except Exception as exc:
        writeLog(f"[{plugin_name}] teardown error during relaunch: {exc.__class__.__name__}", "WARNING")
    writeLog(f"[{plugin_name}] relaunch: starting new browser", "INFO")
    await self.setup()
    session_restored = await self.restore_session()
    if not session_restored:
        writeLog(f"[{plugin_name}] restore_session=False; re-logging in", "INFO")
        await self.login()

async def restore_session(self) -> bool:
    """Restore browser session from encrypted cookies. No-op stub for Phase 22.

    Returns False always. Phase 23 replaces with Fernet cookie restore (REL-04).
    PLUGIN_API_VERSION stays 2 -- additive non-abstract method.
    """
    return False
```

### `core/retry.py` -- import only, no changes

**Analog:** `core/retry.py` as written (full file, 72 lines)

**Import pattern** (orchestrator.py already imports RetryPolicy and with_retry at L24):
```python
from core.retry import RetryPolicy, with_retry, compute_delay
```

`compute_delay` is the only new symbol needed -- add it to the existing import line. No changes to retry.py itself.

## Shared Patterns

### Additive No-Op ABC Method
**Source:** `core/plugin_base.py` L78-85 (get_price) and L87-94 (get_active_tab)
**Apply to:** restore_session() and relaunch() in plugin_base.py
```python
# Pattern: concrete method with docstring citing PLUGIN_API_VERSION stays 2 + phase note
async def get_price(self, url: str) -> int | None:
    """... PLUGIN_API_VERSION stays 2 -- additive non-abstract method (PRICE-02). ..."""
    return None
```

### Exception-Type-Check Helper (bool return)
**Source:** `core/plugin_base.py` _handle_ban L50-62
**Apply to:** _is_browser_dead_exc in orchestrator.py
Pattern: module-level function, guard clauses with isinstance checks, return False as default.

### Thread-Safe Cancel Bridge
**Source:** `core/service.py` BotService.stop() L192
**Apply to:** _register_signals signal handler in orchestrator.py
```python
loop.call_soon_threadsafe(root_task.cancel)  # always use threadsafe variant
```

### Error Logging Convention
**Source:** `core/orchestrator.py` _attempt_buy L196-200
**Apply to:** supervise() and relaunch() log calls
```python
# Use exc.__class__.__name__ not str(exc) to avoid leaking credentials in error text
writeLog(f"[{plugin.__class__.__name__}] error: {exc.__class__.__name__}", "ERROR")
```

### try/except Exception + continue in item loops
**Source:** `core/orchestrator.py` _check_and_buy L299-303
**Apply to:** per-item TimeoutError handler and sqlite read isolation
```python
try:
    available = await plugin.check_availability(link)
except Exception as exc:
    writeLog(f"[{plugin.__class__.__name__}] check error: {exc}", "ERROR")
    return
```

## No Analog Found

All target capabilities have close analogs. No files require RESEARCH.md patterns only.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/test_supervisor.py` | test | unit | File does not exist yet; pattern from conftest fake_plugin + test_orchestrator task tracking |

## Test Fixture Patterns

### fake_plugin fixture (conftest.py L125-154)
Used for all supervisor/orchestrator tests. The fixture builder accepts `available`, `bought`, `domains`, `config`. For Phase 22 tests, extend with a `raises` parameter or a counter to simulate crashes:

```python
# Pattern: extend fake_plugin to raise on nth call
class _CrashingPlugin(RetailerPlugin):
    domain_patterns = ["crash.example.com"]
    _call_count = 0

    async def check_availability(self, url: str) -> bool:
        self._call_count += 1
        if self._call_count <= crash_after:
            raise RuntimeError("simulated crash")
        return False

    async def auto_buy(self, url: str) -> bool:
        return False
```

### mock_nodriver_start fixture (conftest.py L217-251)
Used for relaunch() tests to verify setup() is called on the new browser. Pattern: patch `nodriver.start` with recorder, assert `recorder.browser.main_tab.send` was awaited (apply_stealth sends CDP commands via tab.send).

### _make_registry_with_plugins helper (test_orchestrator.py L55-62)
```python
def _make_registry_with_plugins(*plugins):
    registry = MagicMock(spec=PluginRegistry)
    registry._active_plugins = list(plugins)
    registry._all_plugins = list(plugins)
    registry.teardown_all = AsyncMock()
    return registry
```
Copy this verbatim into test_supervisor.py.

### NotificationEvent action field
**Source:** `notifications/base.py` L44 -- `action: str` is a plain unrestricted string (no Literal constraint). The park notification `action="plugin_parked"` requires no schema change.

## Key Line References

| Symbol | File | Lines |
|--------|------|-------|
| run_plugin (pre-modification target) | core/orchestrator.py | 172-183 |
| TaskGroup block (supervise insert point) | core/orchestrator.py | 496-511 |
| _write_queue_drain | core/orchestrator.py | 383-393 |
| _dispatch_write | core/orchestrator.py | 347-380 |
| async_main finally block | core/orchestrator.py | 506-511 |
| _handle_ban (exception-check pattern) | core/plugin_base.py | 50-62 |
| get_price / get_active_tab (additive method pattern) | core/plugin_base.py | 78-94 |
| teardown() (called in relaunch) | core/plugin_base.py | 128-130 |
| BotService.stop() (signal bridge analog) | core/service.py | 179-195 |
| RetryPolicy / compute_delay | core/retry.py | 21-44 |
| CheckoutConfig fields | core/config_schema.py | 265-272 |
| assign_proxy (called by supervise before relaunch) | core/registry.py | 75-91 |
| fake_plugin fixture | tests/conftest.py | 125-154 |
| _make_registry_with_plugins | tests/test_orchestrator.py | 55-62 |
| test_taskgroup_creates_per_plugin_tasks | tests/test_orchestrator.py | 69-123 |

## Metadata

**Analog search scope:** core/, plugins/, tests/, notifications/
**Files scanned:** 12
**Pattern extraction date:** 2026-06-12
