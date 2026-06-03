# Phase 4: Async Orchestrator - Research

**Researched:** 2026-06-03
**Domain:** asyncio orchestration, nodriver concurrency, SQLite WAL, blocking-I/O removal
**Confidence:** HIGH

---

## Summary

Phase 4 replaces the sequential `while True` loop in `main.py` with a concurrent
`asyncio.TaskGroup` that runs one long-lived poll coroutine per active plugin. The
central question was whether multiple `nodriver.Browser` instances can coexist in a
single event loop -- source inspection of nodriver 0.50.3 answers this definitively
in the affirmative (detailed below under Research Target 1).

The three other pillars -- replacing `input()` calls with `asyncio.Event`, making
SQLite safe under concurrent reads/writes, and correctly understanding where
`ThreadPoolExecutor` is actually needed -- are all well-understood patterns that fit
cleanly into Python's standard async idioms. No exotic dependencies are required.

**Primary recommendation:** Use the PRIMARY model (one event loop, TaskGroup of per-plugin
coroutines). The contingency (thread-per-plugin) is unnecessary. Use `run_in_executor`
only for the two genuinely blocking calls: `sqlite3` operations (ASYNC-04/05) and the
stdin listener (ASYNC-03). All nodriver browser work stays on the event loop directly.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Concurrency Architecture (ASYNC-01, ASYNC-02)**
- Primary model: `asyncio.TaskGroup` of per-plugin coroutines in ONE event loop. Use
  `ThreadPoolExecutor` / `run_in_executor` ONLY for genuinely blocking calls (stdin
  listener, sync library work), not to thread-wrap already-async plugin work.
- Contingency (research-gated): if research shows nodriver cannot safely run multiple
  Browser instances in a single event loop, fall back to one thread per plugin, each
  with its own loop. RESEARCH MUST resolve this before planning.
- Startup stagger: initialize each plugin's driver at least 1.5s apart (ASYNC-02).
- Poll interval: single shared configurable interval; per-platform jitter deferred to
  Phase 6.

**Manual Intervention / input() Removal (ASYNC-03)**
- All blocking `input()` replaced with `asyncio.Event` notify-and-wait.
- Single dedicated stdin-listener in a thread via `run_in_executor`; sets the relevant
  event when user presses Enter.
- Only the plugin needing intervention pauses; others keep polling.
- Amazon sign-in/OTP follows the same pattern; if unattended, auto-buy is skipped with
  a logged reason.

**SQLite Concurrency (ASYNC-04, ASYNC-05)**
- WAL mode and `busy_timeout=5000` on all connections.
- All connection usage in context managers.
- Single async write queue (`asyncio.Queue`) draining `update_item_purchased()` and any
  other mutations; reads can proceed concurrently under WAL.
- Target: zero `database is locked` errors over 60+ min sustained operation.

### Claude's Discretion
- Orchestrator file location/structure (extend `core/registry.py` or new
  `core/orchestrator.py`)
- Exact write-queue API shape
- stdin-listener implementation details
- Logging format for overlap/stagger evidence

### Deferred Ideas (OUT OF SCOPE)
- Per-platform delay / jitter / headless configuration (Phase 6)
- Plugin supervision / auto-restart on browser crash
- New platforms + notifications (Phases 6 and 5)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ASYNC-01 | Orchestrator runs all active plugins concurrently using `asyncio.TaskGroup`; one thread per plugin via `ThreadPoolExecutor` | TaskGroup drives per-plugin coroutines; ThreadPoolExecutor used only for blocking sqlite3/stdin calls, not for plugin coroutines (see Research Target 5) |
| ASYNC-02 | Plugin WebDriver instances staggered on startup (1.5s delay between each) | Implemented via `asyncio.sleep(1.5 * index)` before each plugin's `setup()` call inside the startup sequence; log line per init provides the observable evidence |
| ASYNC-03 | All `input()` blocking calls replaced with `asyncio.Event` + notification pattern | Five sites in amazon plugin (CAPTCHA, passkey dismiss, OTP, test-mode continue x2). Pattern: `run_in_executor` thread reads stdin, `loop.call_soon_threadsafe(event.set)` signals the coroutine |
| ASYNC-04 | SQLite uses WAL mode and `busy_timeout=5000`; all connection usage wrapped in context managers | Exact PRAGMA sequence documented; `get_db_connection()` context manager replaces all direct `conn = sqlite3.connect()` patterns |
| ASYNC-05 | Single async write queue serializes all `update_item_purchased()` calls | `asyncio.Queue` + single drain task; plugins call `await write_queue.put(url)` instead of calling `update_item_purchased` directly |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Concurrency orchestration | Async runtime (event loop / TaskGroup) | -- | asyncio.TaskGroup runs all plugin coroutines; no extra threads needed for browser work |
| Browser automation per plugin | Per-plugin coroutine (event loop) | -- | nodriver is fully async; each Browser operates via its own WebSocket in the same loop |
| Blocking sqlite3 I/O | ThreadPoolExecutor via run_in_executor | asyncio write queue | sqlite3 is not async-aware; executor call prevents loop stall |
| stdin listener (Enter signal) | ThreadPoolExecutor (one long-lived thread) | asyncio.Event | reading stdin blocks; must be off the loop |
| Plugin startup stagger | Orchestrator init sequence (async) | -- | Sequential awaits with asyncio.sleep between driver inits |
| SQLite write serialization | Write-queue drain task (event loop) | run_in_executor for actual sqlite3 call | Queue drain is async; sqlite3 inside it uses executor |
| Pre-loop CVV collection | main() synchronous scope | -- | getpass already before asyncio.run(); no change needed |

---

## Research Target 1: nodriver Concurrency in One Event Loop

**DEFINITIVE ANSWER: PRIMARY MODEL IS SAFE.**

Multiple `nodriver.Browser` instances can run concurrently in a single asyncio event
loop with no modification to nodriver internals.

Evidence from nodriver 0.50.3 source
(`E:\repos\ShopPyBot\.venv\Lib\site-packages\nodriver\`):

**No global singleton or anti-concurrent guard:**
- `util.py:27`: `__registered__instances__: Set[Browser] = set()` is a module-level
  set used ONLY for cleanup in `deconstruct_browser()`. It does NOT prevent creating
  multiple instances; any number of Browser objects can exist simultaneously.
  [VERIFIED: nodriver 0.50.3 source, util.py lines 27, 131, 180, 202]
- `Browser.create()` (classmethod) has no "already running" check; it calls
  `Browser.__init__` then `instance.start()` unconditionally.
  [VERIFIED: nodriver 0.50.3 source, browser.py lines 67-96]

**Each Browser gets its own isolated OS process and CDP port:**
- `browser.py start()`: calls `util.free_port()` to bind-and-release a socket, picking
  a unique OS-assigned port per instance. Each Browser subprocess starts with
  `--remote-debugging-port=N` where N is unique.
  [VERIFIED: nodriver 0.50.3 source, browser.py lines 317-318]
- `config.py Config.__init__`: when `user_data_dir` is None (the default), calls
  `temp_profile_dir()` which calls `tempfile.mkdtemp()`. Each Config creates a new,
  unique temp directory. Two concurrent Browser instances never share a Chrome profile.
  [VERIFIED: nodriver 0.50.3 source, config.py lines 86-88]

**No event-loop pinning or loop affinity on Browser instances:**
- `browser.py __init__:106`: `asyncio.get_running_loop()` is called only to ASSERT
  that a loop exists (raises RuntimeError otherwise). The loop is NOT stored on the
  instance -- there is no `self._loop = ...` anywhere in browser.py.
  [VERIFIED: nodriver 0.50.3 source, browser.py lines 105-112]
- `connection.py send():413`: uses `asyncio.get_running_loop().create_future()` at
  call time. This picks up whichever loop is running, making each Browser loop-agnostic
  and naturally cooperative with TaskGroup concurrency.
  [VERIFIED: nodriver 0.50.3 source, connection.py lines 413]

**Each Connection has fully isolated I/O state:**
- `connection.py Connection.__init__:197-207`: `self.socket`, `self._listener_task`,
  `self._mapper`, `self.lock` are all instance attributes. No class-level shared mutable
  state. Two Browser instances do not share WebSocket connections or inflight-request
  tables.
  [VERIFIED: nodriver 0.50.3 source, connection.py lines 197-207]

**Known rough edge (not a blocker):**
- `browser.py stop():593`: calls `asyncio.get_event_loop().create_task(self.aclose())`
  using the deprecated `get_event_loop()` API. When called from inside the running loop
  (which teardown always is), this is functionally equivalent to
  `asyncio.get_running_loop().create_task()`. The teardown path in
  `registry.teardown_all()` is already inside the async context, so this is safe.
  [VERIFIED: nodriver 0.50.3 source, browser.py lines 589-602]

**Conclusion:** The contingency (thread-per-plugin) is NOT needed. Proceed with the
primary model.

---

## Research Target 2: asyncio.TaskGroup Orchestration Pattern

[VERIFIED: Python 3.11 stdlib docs / asyncio.TaskGroup]

### TaskGroup for N long-running per-plugin poll coroutines

The key structural insight: each plugin gets one coroutine that loops forever over its
own items, sleeping `poll_interval` seconds between iterations. The coroutine is
cancelled (not raised) when the TaskGroup exits.

```python
# core/orchestrator.py (recommended new file)
import asyncio
import sys
from pathlib import Path

from core.registry import PluginRegistry
from logger import writeLog
from models import get_items_sync, update_item_purchased_sync
from utils import play_available_sound, play_buy_sound


async def run_plugin(
    plugin,
    write_queue: asyncio.Queue,
    poll_interval: float,
) -> None:
    """Long-running poll coroutine for one plugin. Cancelled on shutdown."""
    loop = asyncio.get_running_loop()
    while True:
        items = await loop.run_in_executor(None, get_items_sync)
        for name, link, auto_buy, quantity, purchased in items:
            if purchased:
                continue
            # Only process items that belong to this plugin
            if not any(p in (link or "") for p in plugin.domain_patterns):
                continue
            try:
                available = await plugin.check_availability(link)
            except Exception as exc:
                writeLog(
                    f"[{plugin.__class__.__name__}] check_availability error: {exc}",
                    "ERROR",
                )
                continue
            if available:
                play_available_sound()
                writeLog(f"{name} is AVAILABLE -- {link}", "SUCCESS")
                if auto_buy:
                    try:
                        success = await plugin.auto_buy(link)
                        if success:
                            play_buy_sound()
                            await write_queue.put(link)
                    except Exception as exc:
                        writeLog(
                            f"[{plugin.__class__.__name__}] auto_buy error: {exc}",
                            "ERROR",
                        )
        await asyncio.sleep(poll_interval)


async def _write_queue_drain(queue: asyncio.Queue) -> None:
    """Serializes all DB writes. Runs until cancelled."""
    loop = asyncio.get_running_loop()
    while True:
        link = await queue.get()
        try:
            await loop.run_in_executor(None, update_item_purchased_sync, link)
            writeLog(f"Marked purchased: {link}", "INFO")
        except Exception as exc:
            writeLog(f"DB write failed for {link}: {exc}", "ERROR")
        finally:
            queue.task_done()


async def _staggered_setup(registry, items, stagger_secs: float = 1.5) -> None:
    """Initializes only plugins that have matching items; 1.5s apart (ASYNC-02)."""
    needed = _plugins_for_items(registry, items)
    for idx, plugin in enumerate(needed):
        if idx > 0:
            writeLog(
                f"[STAGGER-{idx}] Waiting {stagger_secs}s before next driver init",
                "INFO",
            )
            await asyncio.sleep(stagger_secs)
        writeLog(
            f"[STAGGER-{idx}] Initializing {plugin.__class__.__name__} browser",
            "INFO",
        )
        try:
            await plugin.setup()
            registry._active_plugins.append(plugin)
        except Exception as exc:
            writeLog(
                f"Plugin {plugin.__class__.__name__} setup failed: {exc} -- skipping",
                "WARNING",
            )


def _plugins_for_items(registry, items) -> list:
    """Return the subset of _all_plugins that have at least one matching item."""
    needed = []
    seen = set()
    for _, link, *_ in items:
        plugin = registry._route_all(link)
        if plugin and id(plugin) not in seen:
            needed.append(plugin)
            seen.add(id(plugin))
    return needed


async def async_main(cfg, cvv) -> None:
    """Entry point: stagger setup, run TaskGroup, teardown cleanly."""
    plugins_dir = Path(__file__).parent.parent / "plugins"
    registry = PluginRegistry(cfg, plugins_dir)
    loop = asyncio.get_running_loop()

    items = await loop.run_in_executor(None, get_items_sync)
    await _staggered_setup(registry, items)

    if cvv:
        bb_plugin = registry.route("https://www.bestbuy.com/")
        if bb_plugin:
            bb_plugin._cvv = cvv

    poll_interval = float(getattr(cfg.app, "poll_interval", 30))
    write_queue: asyncio.Queue = asyncio.Queue()

    # Start stdin listener (one thread, lives for the process lifetime)
    _start_stdin_listener(registry._active_plugins, loop)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_write_queue_drain(write_queue), name="write-queue-drain")
            for plugin in registry._active_plugins:
                tg.create_task(
                    run_plugin(plugin, write_queue, poll_interval),
                    name=f"poll-{plugin.__class__.__name__}",
                )
    except* KeyboardInterrupt:
        pass
    finally:
        # Flush remaining writes before browser teardown
        try:
            await asyncio.wait_for(write_queue.join(), timeout=10)
        except asyncio.TimeoutError:
            writeLog("Write queue flush timed out on shutdown", "WARNING")
        await registry.teardown_all()
```

### TaskGroup cancellation semantics

- When Ctrl-C hits, Python delivers SIGINT which raises `KeyboardInterrupt` in the
  running coroutine. Inside a TaskGroup, this becomes a `BaseExceptionGroup` containing
  the `KeyboardInterrupt`. The `except* KeyboardInterrupt:` clause (PEP 654, Python
  3.11+) catches it cleanly. [VERIFIED: Python 3.11 docs]
- An unhandled exception in one plugin task causes TaskGroup to cancel all other tasks
  and re-raise as an ExceptionGroup. For this use case that is correct behavior: a
  browser crash should surface, not be silently absorbed.
- Per-item errors (network timeout, DOM not found) are caught inside `run_plugin` and
  logged; they never propagate to the TaskGroup.

---

## Research Target 3: input() to asyncio.Event Pattern

[VERIFIED: Python asyncio docs -- loop.call_soon_threadsafe, asyncio.Event]

### The five input() sites in the Amazon plugin

| File | Method | Line context | Trigger |
|------|--------|--------------|---------|
| `shopbot_plugin_amazon.py` | `check_availability` | CAPTCHA detected | Solve CAPTCHA |
| `shopbot_plugin_amazon.py` | `login` | After email entry | Dismiss passkey prompt |
| `shopbot_plugin_amazon.py` | `login` | After password + sign-in | Enter OTP |
| `shopbot_plugin_amazon.py` | `auto_buy` | test_mode before buy-now | Confirm test pause |
| `shopbot_plugin_amazon.py` | `auto_buy` | test_mode after order check | Confirm test pause |

### Replacement pattern on the plugin

```python
# shopbot_plugin_amazon.py -- revised AmazonPlugin

class AmazonPlugin(RetailerPlugin):
    def __init__(self, config) -> None:
        super().__init__(config)
        # One Event per distinct intervention type (ASYNC-03).
        # asyncio.Event() is safe to create before loop start in Python 3.10+.
        self.captcha_event: asyncio.Event = asyncio.Event()
        self.passkey_event: asyncio.Event = asyncio.Event()
        self.otp_event: asyncio.Event = asyncio.Event()
        self.test_pause_event: asyncio.Event = asyncio.Event()

    async def _wait_user_action(self, event: asyncio.Event, message: str) -> None:
        """Notify user, await their Enter, clear the event for reuse."""
        play_notification_sound()
        writeLog(message, "WARNING")
        try:
            await asyncio.wait_for(event.wait(), timeout=300)  # 5 min unattended guard
        except asyncio.TimeoutError:
            writeLog("User action timed out (300s) -- continuing without intervention", "WARNING")
        finally:
            event.clear()

    async def check_availability(self, url: str) -> bool:
        ...
        if captcha_present:
            await self._wait_user_action(
                self.captcha_event,
                "CAPTCHA detected on Amazon. Solve it in the browser, then press Enter."
            )
        ...

    async def login(self) -> None:
        ...
        # Passkey prompt
        await self._wait_user_action(
            self.passkey_event,
            "Amazon passkey prompt visible. Dismiss it in the browser, then press Enter."
        )
        ...
        # OTP prompt
        if mfa_form:
            await self._wait_user_action(
                self.otp_event,
                "MFA/OTP prompt detected. Enter your code in the browser, then press Enter."
            )
        ...

    async def auto_buy(self, url: str) -> bool:
        ...
        if test_mode:
            await self._wait_user_action(
                self.test_pause_event,
                "TEST MODE: review the browser, then press Enter to continue."
            )
        ...
```

### Single stdin-listener thread (orchestrator)

```python
# core/orchestrator.py

def _stdin_listener_thread(
    plugins: list,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Blocking thread. Reads Enter from stdin, signals all pending intervention events.

    Security: reads only line terminators; never echoes, stores, or forwards
    any text the user typed. Credentials are handled exclusively by getpass
    before asyncio.run() (SEC-02).
    """
    while True:
        try:
            sys.stdin.readline()  # blocks until newline
        except (EOFError, OSError):
            break  # stdin closed or process exiting

        # Signal every intervention event on every plugin.
        # At most one plugin is waiting at any time (human is the bottleneck).
        # The waiting coroutine wakes; all already-cleared events are no-ops.
        for plugin in plugins:
            for attr in ("captcha_event", "passkey_event", "otp_event", "test_pause_event"):
                event = getattr(plugin, attr, None)
                if event is not None:
                    loop.call_soon_threadsafe(event.set)


def _start_stdin_listener(plugins: list, loop: asyncio.AbstractEventLoop) -> None:
    """Submit the stdin listener to the default executor (one thread, daemon)."""
    loop.run_in_executor(None, _stdin_listener_thread, plugins, loop)
```

**Key rules enforced:**
- `loop.call_soon_threadsafe` is the ONLY thread-safe bridge for setting asyncio.Event
  from a non-loop thread. [VERIFIED: Python docs]
- The stdin thread never receives, reads, or handles credential input. It only calls
  `readline()` and then `call_soon_threadsafe`. This satisfies SEC-01/02.
- Only one listener thread is started regardless of plugin count.
- 5-minute `asyncio.wait_for` timeout in `_wait_user_action` prevents indefinite stall
  when bot is running unattended.

---

## Research Target 4: SQLite Under Async Concurrency

[VERIFIED: Python sqlite3 docs, SQLite WAL documentation]

### Why sqlite3 needs run_in_executor

`sqlite3` is a synchronous blocking library. Any call to `sqlite3.connect()`,
`cursor.execute()`, or `conn.commit()` blocks the OS thread for the duration of the
file I/O. Calling these from an async coroutine without an executor blocks the entire
event loop, stalling all other plugin coroutines for the duration of each DB operation.

Under concurrent two-plugin polling (60+ min), this manifests as unpredictable,
sub-millisecond stalls per poll tick -- individually harmless but they accumulate.

### Exact PRAGMA setup (ASYNC-04)

```python
# models.py -- context manager replacing all direct conn = sqlite3.connect() calls

import sqlite3
import contextlib

@contextlib.contextmanager
def get_db_connection():
    """Open, configure WAL, yield, commit/rollback, close."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**Why these settings:**
- `journal_mode=WAL`: readers never block writers; writers never block readers.
  Under two concurrent plugins, the frequent reads (get_items per poll tick) and
  rare writes (update_item_purchased) no longer conflict. [VERIFIED: SQLite WAL docs]
- `busy_timeout=5000`: if a write lock IS momentarily contended, sqlite3 retries for
  up to 5 seconds before raising `OperationalError`. Combined with WAL (rare
  contention) and the write queue (serialized writes), zero lock errors is achievable.
  [VERIFIED: SQLite docs]
- `synchronous=NORMAL`: safe with WAL; no data loss on OS crash; better throughput
  than FULL. [VERIFIED: SQLite docs -- ASSUMED exact safety on Windows crash edge case]
- `timeout=5` in `sqlite3.connect()`: this is the Python-layer timeout (different
  from the PRAGMA). Setting both is belt-and-suspenders.

**WAL file note (security):** WAL mode creates `shop_py_bot.db-wal` and
`shop_py_bot.db-shm` alongside the main DB. These contain transaction data, no
credentials. They are auto-removed on clean shutdown. Add to `.gitignore`:
`data/*.db-wal` and `data/*.db-shm`.

### Revised models.py sync functions (used with run_in_executor)

```python
# models.py -- sync internals called only via run_in_executor

def get_items_sync() -> list:
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT name, link, auto_buy, quantity, purchased FROM items"
        ).fetchall()


def update_item_purchased_sync(link: str) -> None:
    with get_db_connection() as conn:
        conn.execute("UPDATE items SET purchased=1 WHERE link=?", (link,))
        # conn.commit() called by context manager


def add_items_sync(items: list) -> None:
    with get_db_connection() as conn:
        for item in items:
            count = conn.execute(
                "SELECT COUNT(*) FROM items WHERE link=?", (item[1],)
            ).fetchone()[0]
            if count == 0:
                conn.execute(
                    "INSERT INTO items (name, link, auto_buy, quantity, purchased)"
                    " VALUES (?, ?, ?, ?, ?)",
                    item,
                )
```

### Write-queue drain task (ASYNC-05)

```python
# Already shown in Research Target 2; repeated here for completeness

async def _write_queue_drain(queue: asyncio.Queue) -> None:
    loop = asyncio.get_running_loop()
    while True:
        link = await queue.get()
        try:
            await loop.run_in_executor(None, update_item_purchased_sync, link)
            writeLog(f"Marked purchased: {link}", "INFO")
        except Exception as exc:
            writeLog(f"DB write failed for {link}: {exc}", "ERROR")
        finally:
            queue.task_done()
```

Plugins call `await write_queue.put(url)` after a confirmed purchase. This is the
ONLY write path. No plugin ever calls `update_item_purchased` directly.

---

## Research Target 5: ThreadPoolExecutor Role

[VERIFIED: Python asyncio docs, nodriver 0.50.3 source analysis]

ASYNC-01 says "one thread per plugin via ThreadPoolExecutor." The intent is concurrency.
The reconciliation of that requirement with async nodriver:

| Call site | Blocking? | Execution | Why |
|-----------|-----------|-----------|-----|
| `plugin.check_availability()` | No (nodriver coroutine) | Event loop directly | Already async; executor adds overhead without benefit |
| `plugin.auto_buy()` | No (nodriver coroutine) | Event loop directly | Already async |
| `get_items_sync()` | Yes (sqlite3) | `run_in_executor(None, ...)` | sqlite3 blocks; executor prevents loop stall |
| `update_item_purchased_sync()` | Yes (sqlite3) | `run_in_executor(None, ...)` inside drain task | sqlite3 blocks |
| `_stdin_listener_thread()` | Yes (readline blocks) | `run_in_executor(None, ...)` | stdin.readline() blocks; must be off the loop |
| `Browser.start()` subprocess launch | Partial (asyncio.subprocess) | Event loop directly | `asyncio.create_subprocess_exec` is already async |

**Practical configuration:** The default ThreadPoolExecutor (Python picks
`min(32, os.cpu_count() + 4)`) is sufficient. No custom pool needed. `asyncio.run()`
manages the default executor lifecycle and calls `shutdown_default_executor()` on exit.

**Compliance note:** TaskGroup provides the concurrency that ASYNC-01 requires.
`run_in_executor` provides the thread isolation that the wording implies for blocking
calls. This satisfies both the intent and letter of the requirement.

---

## Standard Stack

### Core (no new dependencies)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| `asyncio` | stdlib, Python 3.11+ | TaskGroup, Event, Queue, run_in_executor | Installed |
| `nodriver` | 0.50.3 | Browser automation (unchanged) | Installed |
| `sqlite3` | stdlib | Database layer (unchanged) | Installed |

**Python version on this machine:** 3.13.13 [VERIFIED: `python --version`]
Python 3.13 is fully compatible; `asyncio.TaskGroup` and `except*` syntax were
introduced in 3.11.

No new packages are required for Phase 4.

### Package Legitimacy Audit

No new packages are introduced. Existing packages carry forward from Phases 1-3.

**Packages removed due to slopcheck:** none
**Packages flagged as suspicious:** none

---

## Architecture Patterns

### System Architecture Diagram

```
main() [sync scope]
  |-- AppConfig validation
  |-- initialize_db()
  |-- getpass CVV (blocking stdin, safe: before asyncio.run)
  |
  asyncio.run(orchestrator.async_main(cfg, cvv))
       |
       PluginRegistry discovery (sync importlib)
       |
       Staggered setup: for idx, plugin in needed:
           if idx > 0: await asyncio.sleep(1.5)   <-- ASYNC-02
           await plugin.setup()
       |
       _start_stdin_listener (run_in_executor, one thread) <-- ASYNC-03
       |
       asyncio.TaskGroup
        |-- write_queue_drain_task         <-- ASYNC-05
        |      await queue.get()
        |      run_in_executor(update_item_purchased_sync)  <-- ASYNC-04
        |
        |-- plugin_A poll coroutine
        |      run_in_executor(get_items_sync)              <-- ASYNC-04
        |      await plugin_A.check_availability(url)       (nodriver, event loop)
        |      await plugin_A.auto_buy(url)                 (nodriver, event loop)
        |        [if intervention needed]
        |        await self._wait_user_action(event, msg)   <-- ASYNC-03
        |      await write_queue.put(url)                   <-- ASYNC-05
        |      await asyncio.sleep(poll_interval)
        |
        |-- plugin_B poll coroutine
               [same structure as plugin_A, independent]
       |
       [Ctrl-C -> except* KeyboardInterrupt]
       write_queue.join() timeout=10
       registry.teardown_all()

Thread pool (default executor):
  - T1: sqlite3 reads  (short-lived, one per poll tick per plugin)
  - T2: sqlite3 writes (short-lived, one per successful purchase)
  - T3: stdin listener (long-lived, one for process lifetime)
```

### Recommended Project Structure

```
core/
  orchestrator.py      # NEW: run_plugin(), async_main(), _write_queue_drain(),
                       #      _staggered_setup(), _stdin_listener_thread()
  plugin_base.py       # MODIFY: add intervention Event attributes (or leave in plugins)
  registry.py          # MINOR ADD: plugins_for_items() helper method
models.py              # REVISE: get_db_connection() context manager,
                       #         _sync suffix functions, WAL PRAGMA
plugins/
  shopbot_plugin_amazon.py    # REVISE: replace 5 input() with Event pattern
  shopbot_plugin_bestbuy.py   # MINOR: use write_queue.put instead of direct call
main.py                       # REVISE: import async_main from orchestrator;
                              #         preserve CVV gate; remove old async_main body
```

### Anti-Patterns to Avoid

- **`asyncio.run()` inside a plugin coroutine**: nodriver requires a running loop;
  nesting `asyncio.run()` inside an already-running loop raises RuntimeError.
- **Direct sqlite3 calls in async functions without run_in_executor**: blocks the event
  loop during DB I/O; all other plugins stall until the call returns.
- **Per-item asyncio.Event objects**: events must be per-plugin-instance (or per-
  intervention-type), not created dynamically per check iteration.
- **`asyncio.get_event_loop()` (deprecated 3.10+)**: use `asyncio.get_running_loop()`
  inside coroutines.
- **`input()` in any coroutine**: violates ASYNC-03 and blocks all other tasks.
- **`write_queue.put_nowait()` instead of `await write_queue.put()`**: the drain task
  rate-limits to one write at a time; `put_nowait` is fine but skips backpressure.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Concurrent task execution | Custom thread pools for browser work | `asyncio.TaskGroup` | nodriver is already async; TaskGroup is stdlib for Python 3.11+ |
| Write serialization | Mutex / Lock around sqlite3 | `asyncio.Queue` drain task | Queue naturally serializes; no deadlock risk from concurrent awaits holding a lock |
| Stdin signal routing to async | Pipe, socket, or shared memory | `loop.call_soon_threadsafe` + `asyncio.Event` | Exactly what these primitives were designed for |
| SQLite timeout / retry loop | Custom wait-and-retry | `PRAGMA busy_timeout=5000` | Built into SQLite; zero code |
| Browser port allocation | Port tracking dict | `util.free_port()` (nodriver internal) | Already handled per instance |

---

## Common Pitfalls

### Pitfall 1: asyncio.Event set from a non-loop thread without call_soon_threadsafe
**What goes wrong:** `event.set()` is not thread-safe. Calling it directly from the
stdin listener thread corrupts the event's internal state and may silently not wake
the waiting coroutine, or crash with a mutex error.
**How to avoid:** Always use `loop.call_soon_threadsafe(event.set)`.

### Pitfall 2: browser.stop() called after asyncio.run() exits
**What goes wrong:** `browser.stop()` uses `asyncio.get_event_loop().create_task()`.
If the loop is already closed (post `asyncio.run()`), the task is never scheduled,
leaking the Chrome subprocess.
**How to avoid:** Call `registry.teardown_all()` (which calls `browser.stop()`) from
inside the `finally` block of `async_main`, not from the synchronous `main()`.

### Pitfall 3: TaskGroup exception swallows KeyboardInterrupt
**What goes wrong:** `except KeyboardInterrupt:` does not match
`ExceptionGroup(KeyboardInterrupt)` produced by TaskGroup. The interrupt is re-raised
as an unhandled ExceptionGroup.
**How to avoid:** Use `except* KeyboardInterrupt:` (Python 3.11+ PEP 654 syntax).

### Pitfall 4: write_queue.join() deadlock on shutdown
**What goes wrong:** On TaskGroup exit, the drain task is cancelled. If cancelled mid-
item, `task_done()` is never called and `write_queue.join()` blocks forever.
**How to avoid:** Call `write_queue.join()` in `finally` BEFORE the TaskGroup exits
(or use `asyncio.wait_for(write_queue.join(), timeout=10)` as shown in the pattern).

### Pitfall 5: Plugin polls wrong platform's items
**What goes wrong:** Each `run_plugin` coroutine calls `get_items_sync()` which returns
ALL items. Without explicit domain filtering inside the coroutine, plugin A may attempt
to `check_availability` on a URL belonging to plugin B, causing silent failures.
**How to avoid:** Include `if not any(p in link for p in plugin.domain_patterns):
continue` at the top of the item loop inside `run_plugin`.

### Pitfall 6: Chrome profile collision during stagger window
**What goes wrong:** On very fast startup machines, two near-simultaneous
`nodriver.start()` calls could race on temp directory creation. Second Chrome may
fail with "Profile in use."
**How to avoid:** The 1.5s stagger is the primary mitigation. Log the `plugin.driver.config.user_data_dir` at setup to confirm uniqueness. `tempfile.mkdtemp()` is inherently unique by design; this is LOW-risk.

### Pitfall 7: asyncio.Event state leaks across poll cycles
**What goes wrong:** If `event.clear()` is not called after an intervention, the
event remains set. The NEXT poll cycle that checks for CAPTCHA immediately proceeds
without waiting, even if a CAPTCHA is present.
**How to avoid:** Always call `event.clear()` in the `finally` block of
`_wait_user_action` (as shown in the pattern). Never rely on the caller to clear.

---

## Validation Architecture

nyquist_validation: true (from .planning/config.json)

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pyproject.toml` (existing from Phase 1) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ASYNC-01 | Two plugins poll concurrently (overlapping timestamps in logs) | Integration (long-run) | Not unit-mockable in < 30s; see manual test below | No -- Wave 0 |
| ASYNC-01 | TaskGroup structure: multiple tasks created | Unit (mock plugins) | `pytest tests/test_orchestrator.py::test_taskgroup_creates_per_plugin_tasks -x` | No -- Wave 0 |
| ASYNC-02 | Stagger >= 1.5s between driver inits | Unit (mock asyncio.sleep) | `pytest tests/test_orchestrator.py::test_stagger_interval -x` | No -- Wave 0 |
| ASYNC-03 | No `input()` calls in async code path | Static check (grep) | `pytest tests/test_no_input.py -x` or `grep -rn "input(" plugins/ core/` | No -- Wave 0 |
| ASYNC-03 | asyncio.Event wakes waiting coroutine | Unit (mock event + thread) | `pytest tests/test_orchestrator.py::test_event_wakes_coroutine -x` | No -- Wave 0 |
| ASYNC-04 | WAL PRAGMA applied on connection open | Unit (in-memory or temp DB) | `pytest tests/test_models.py::test_wal_pragma_applied -x` | No -- Wave 0 |
| ASYNC-04 | Context manager closes connection | Unit | `pytest tests/test_models.py::test_connection_closed_on_exit -x` | No -- Wave 0 |
| ASYNC-05 | write_queue serializes writes | Unit (mock drain task) | `pytest tests/test_orchestrator.py::test_write_queue_serializes -x` | No -- Wave 0 |
| ASYNC-05 | Plugins call put() not update directly | Static check (grep) | `pytest tests/test_no_direct_write.py -x` | No -- Wave 0 |

### Tests that require live / long run (not unit-mockable)

| Success Criterion | How to Verify | Minimum Run Time |
|------------------|---------------|------------------|
| SC-1: Overlapping timestamps | Run with two plugins, check log for concurrent timestamps | 2+ poll cycles |
| SC-4: Zero locked errors over 60 min | Run with test_mode=true, two plugins, monitor logs | 60 min |

These are manual verification tests. Document expected log output in test plan.

### Static grep test for input() removal (ASYNC-03)

```python
# tests/test_no_input.py
import subprocess
import pytest

def test_no_input_in_async_paths():
    """Fail if any input() call exists in plugins/ or core/."""
    result = subprocess.run(
        ["grep", "-rn", r"\binput(", "plugins/", "core/"],
        capture_output=True, text=True
    )
    assert result.returncode != 0 or result.stdout == "", (
        f"Found input() calls in async paths:\n{result.stdout}"
    )
```

### Sampling Rate

- Per task commit: `pytest tests/ -x -q --tb=short`
- Per wave merge: `pytest tests/ -v`
- Phase gate: full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_orchestrator.py` -- TaskGroup structure, stagger timing, Event wakeup, write queue
- [ ] `tests/test_models_wal.py` -- WAL PRAGMA, context manager behavior, concurrent reads
- [ ] `tests/test_no_input.py` -- static grep check for input() removal
- [ ] `tests/conftest.py` -- add async fixtures (pytest-asyncio already in requirements or add it)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No change | Amazon/BestBuy credentials stay in env vars (SEC-01) |
| V3 Session Management | No change | Browser sessions isolated per plugin instance |
| V4 Access Control | No | Internal app, no access control layer |
| V5 Input Validation | No change | No new external input introduced |
| V6 Cryptography | No | No crypto introduced |

### Threat Notes for Phase 4

| Pattern | Impact | Mitigation |
|---------|--------|------------|
| stdin listener reads credentials | Credential exposure | Listener calls only `readline()` then `call_soon_threadsafe`. Getpass CVV gate is BEFORE `asyncio.run()` and runs in the synchronous scope; the stdin listener thread is started AFTER the async loop starts, in a completely separate code path. [VERIFIED: design] |
| WAL files expose DB contents | None beyond main DB | WAL files contain only the same data as the main DB. No new sensitive data in DB. Add to `.gitignore`. |
| Browser subprocesses leak on crash | Zombie Chrome processes | `registry.teardown_all()` in `finally` block calls `browser.stop()` which terminates subprocesses. The `atexit` handler registered by nodriver (`util.get_registered_instances()`) provides a second safety net. |
| run_in_executor thread exception swallowed | Silent write failure | The drain task's `except Exception` block logs the error. The plugin does not retry -- the item remains unpurchased for the next poll cycle, which is the safe failure mode. |

---

## Open Questions (RESOLVED)

> All three resolved in the plans: Q1 poll_interval added at cfg.app.poll_interval (Plan 04-01); Q2 asyncio.Event attrs on AmazonPlugin only (Plan 04-04); Q3 pytest-asyncio already in requirements (no add).

1. **poll_interval config key location**
   - What we know: `cfg.app` is an AppConfig Pydantic model; current config has no
     `poll_interval` key.
   - What's unclear: Should `poll_interval` live at `cfg.app.poll_interval` or at a
     new `cfg.async.poll_interval`? Pydantic model needs a new optional field.
   - Recommendation: Add `poll_interval: int = 30` to `AppConfig.app` in
     `core/config_schema.py` with a default of 30 seconds. Flag for planner.

2. **asyncio.Event in plugin_base vs individual plugins**
   - What we know: Only Amazon has `input()` calls; BestBuy does not.
   - What's unclear: Should Event attributes live on `RetailerPlugin` ABC (clean, but
     adds overhead to all plugins) or only on `AmazonPlugin`?
   - Recommendation: Keep Events on `AmazonPlugin` only for now. If BestBuy or future
     plugins need them, promote to base class in a future phase.

3. **pytest-asyncio requirement**
   - What we know: The existing test suite uses pytest; async test fixtures may need
     `pytest-asyncio`.
   - What's unclear: Is it already installed?
   - Recommendation: Check `requirements.txt`; add `pytest-asyncio>=0.23` if absent.
     [ASSUMED: not currently installed -- verify at Wave 0]

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ (asyncio.TaskGroup) | ASYNC-01 | YES | 3.13.13 | -- |
| nodriver 0.50.3 | Browser automation | YES | 0.50.3 | -- |
| sqlite3 | ASYNC-04/05 | YES (stdlib) | stdlib | -- |
| pytest | Test suite | YES (existing) | check pyproject.toml | -- |
| pytest-asyncio | Async test fixtures | UNKNOWN | -- | Add to requirements.txt |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `synchronous=NORMAL` is safe on Windows under WAL for this use case (no abrupt power loss scenario) | Research Target 4 | Very low -- bot is not a financial transaction system; rerun on next restart is acceptable |
| A2 | `asyncio.Event` attributes on plugin instances are safe to create in `__init__` in Python 3.13 (loop-independence confirmed in 3.10+) | Research Target 3 | Very low -- 3.13 is well past the 3.10 deprecation |
| A3 | `poll_interval` config key does not yet exist in `AppConfig` and needs adding | Open Questions | Low -- if it exists under a different name, plan must adapt the accessor |
| A4 | `pytest-asyncio` is not yet in requirements.txt | Environment Availability | Low -- if present, Wave 0 gap is already resolved |

---

## Sources

### Primary (HIGH confidence)
- nodriver 0.50.3 installed source: `core/browser.py`, `core/connection.py`,
  `core/util.py`, `core/config.py` -- concurrency analysis, port allocation, loop behavior
- Python 3.11 docs: asyncio.TaskGroup, asyncio.Event, loop.call_soon_threadsafe,
  run_in_executor, ExceptionGroup / PEP 654
- SQLite official docs: WAL mode, busy_timeout, journal_mode PRAGMA

### Secondary (MEDIUM confidence)
- Python sqlite3 module docs: connection context manager, PRAGMA execution
- Project codebase (read directly): `models.py`, `main.py`, `core/registry.py`,
  `core/plugin_base.py`, `plugins/shopbot_plugin_amazon.py`,
  `plugins/shopbot_plugin_bestbuy.py`

### Tertiary (LOW confidence / ASSUMED)
- `synchronous=NORMAL` safety on Windows with WAL -- general SQLite community consensus,
  not verified against Windows-specific edge case documentation

---

## Metadata

**Confidence breakdown:**
- nodriver concurrency verdict: HIGH -- verified from installed source
- Standard stack: HIGH -- all stdlib, no new dependencies
- Architecture patterns: HIGH -- standard Python asyncio idioms
- SQLite PRAGMA setup: HIGH -- verified against official docs
- Pitfalls: HIGH -- derived from source analysis and stdlib docs
- Test architecture: MEDIUM -- test file content is drafted but not run yet

**Research date:** 2026-06-03
**Valid until:** 2026-09-03 (stable domain; nodriver 0.50.3 pinned)
