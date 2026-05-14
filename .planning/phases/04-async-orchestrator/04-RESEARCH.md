# Phase 4: Async Orchestrator - Research

**Researched:** 2026-05-14
**Domain:** Python asyncio orchestration over blocking Selenium + SQLite
**Confidence:** HIGH (Python 3.11+ stdlib semantics) / MEDIUM (SQLite WAL behavior under N=2-5 writers)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01** Stay on Selenium for Phase 4. Each plugin keeps `self.driver = build_driver(...)`. All Selenium calls bridged via `await asyncio.to_thread(...)`. Single shared `ThreadPoolExecutor` set as default executor in `main()` sized `max(4, len(plugins) * 2)`. nodriver swap deferred to Phase 6.
- **D-02** Blocking `input()` → `await asyncio.to_thread(input, prompt)`. Other plugin tasks keep polling during OTP. No `aioconsole` dependency. CAPTCHA pause is per-plugin local.
- **D-03** `asyncio.Queue` + single `purchase_writer` consumer task drains all `update_item_purchased()` calls. `Queue(maxsize=100)`.
- **D-04** Amend `RetailerPlugin` ABC with non-abstract `async def shutdown(self) -> None` defaulting to `await asyncio.to_thread(self.driver.quit)`. Orchestrator awaits all under `asyncio.shield` in a `finally` block. `PLUGIN_API_VERSION` stays at 1 (additive change).
- Polling cadence stays global (`app.delay`). Per-plugin cadence is v2.
- `pytest-asyncio` is a new dev dependency to pin.

### Claude's Discretion

- ThreadPoolExecutor sizing site (main.py vs small `concurrency.py` helper).
- Per-plugin task error-handling wrapper (recommended: try/except inside orchestrator, not inside each plugin).
- Stagger implementation site (sequential discovery vs per-task `asyncio.sleep(1.5 * index)` — research below recommends discovery-time per CONTEXT pitfall 7).
- Logging concurrency safety (don't preemptively add async logger; add `threading.Lock` only if needed).
- Async test patterns and `pytest-asyncio` mode.

### Deferred Ideas (OUT OF SCOPE)

- nodriver swap (Phase 6).
- Per-plugin polling cadence.
- Async logging.
- Web UI / system-tray OTP signaling.
- Plugin task auto-restart on crash.
- `aioconsole` / native async stdin.
- Plugin priority / weighted polling.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ASYNC-01 | Orchestrator runs all active plugins concurrently using `asyncio.TaskGroup`; one thread per plugin via `ThreadPoolExecutor` | Q1 (TaskGroup error isolation pattern), Q2 (executor sizing), Q3 (Selenium-in-asyncio idiom) |
| ASYNC-02 | Plugin WebDriver instances staggered on startup (1.5s delay) to avoid ChromeDriver port conflicts | Q7 (stagger site = sequential discovery) |
| ASYNC-03 | All `input()` blocking calls replaced with `asyncio.Event` + notification pattern | Q9 (D-02 supersedes literal `asyncio.Event` wording; `to_thread(input)` is the implementation) |
| ASYNC-04 | SQLite uses WAL mode and `busy_timeout=5000`; all connection usage wrapped in context managers | Q4 (WAL + busy_timeout, PRAGMA-once-at-init, context manager refactor) |
| ASYNC-05 | Single async write queue serializes all `update_item_purchased()` calls | Q4 + D-03 (purchase_writer consumer task, also `add_items` startup-only stays sync) |

Note on ASYNC-03 wording: REQUIREMENTS.md text says "`asyncio.Event` + notification pattern" but D-02 (locked) replaces that with `asyncio.to_thread(input)`. Locked decision wins. The plan should reference the requirement ID but implement per D-02; verifier acceptance criterion is "no `input()` call blocks the event loop" not literally "uses asyncio.Event".
</phase_requirements>

## Summary

- **TaskGroup default cancels siblings on any unhandled exception.** This is incompatible with "one plugin crash should not stop others." [VERIFIED: Python 3.11+ docs]. Recommended fix: wrap each `poll_plugin(...)` body in `try/except Exception` inside the orchestrator so unhandled exceptions never propagate out of the task. Let `CancelledError` and `KeyboardInterrupt` propagate.
- **Use `loop.set_default_executor(ThreadPoolExecutor(max_workers=max(4, len(plugins) * 2)))` once at startup BEFORE the TaskGroup opens.** `asyncio.to_thread` uses the loop's default executor [VERIFIED: cpython source / docs]. Sizing rationale: each plugin can have one Selenium call + one OTP-blocked `input()` in flight + headroom for `purchase_writer`.
- **Wrap Selenium calls at the orchestrator call site, not inside plugin methods.** Plugins stay sync (current Phase 2 contract preserved). Orchestrator does `await asyncio.to_thread(plugin.check_availability, url)`. Plugin authors keep writing sync code. Lowest cognitive load; aligns with D-04 (shutdown wraps `self.driver.quit` via `to_thread` in the default impl).
- **WAL mode + `busy_timeout=5000` is set ONCE at `initialize_db()`** with a PRAGMA persisted to the DB (WAL persists across connections; `busy_timeout` is per-connection so it must be set on every `sqlite3.connect()`). [VERIFIED: SQLite docs — `PRAGMA journal_mode=WAL` is persistent; `PRAGMA busy_timeout` is per-connection].
- **Refactor `models.py` connection usage to context managers** (`with sqlite3.connect(DB_PATH) as conn:`). Connection-as-context-manager commits on success / rolls back on exception, then we explicitly `conn.close()`.
- **Run the 1.5s stagger inside `plugin_registry.discover()` between instantiations**, not inside plugin tasks. CONTEXT pitfall 7 requires the sleep BEFORE `webdriver.Chrome()` opens its TCP port. Driver is built in plugin `__init__`, so the sleep MUST happen between `_instantiate(...)` calls. Add `discover_async()` or pass `stagger_seconds: float` to existing `discover()`.
- **Windows ProactorEventLoop has fragile Ctrl-C handling.** [CITED: Python docs `asyncio-platform-support`]. Recommended pattern: install `signal.signal(signal.SIGINT, ...)` that sets an `asyncio.Event` the orchestrator checks; OR use `asyncio.WindowsSelectorEventLoopPolicy` if Proactor-only features aren't needed (we don't use subprocess pipes, so Selector is fine).
- **`pytest-asyncio==1.3.0`** is current latest [VERIFIED: pip index 2026-05-14]. Recommend `asyncio_mode = "auto"` in `pyproject.toml` `[tool.pytest.ini_options]` so existing sync tests don't need decoration changes and new async tests don't need `@pytest.mark.asyncio`.
- **New dependency:** `pytest-asyncio==1.3.0` in `requirements.txt` under a comment marking it dev-only (no separate dev-requirements file in this repo).
- **Config schema addition (optional):** `app.delay: float = 5.0` on `AppConfig` so polling cadence is config-driven (currently no `delay` field exists). If the planner prefers, hardcode a constant — CONTEXT says "polling cadence stays global" but doesn't lock the location.
- **No `time.sleep()` allowed in the async path.** All sleeps must be `await asyncio.sleep(...)`. `time.sleep()` inside `to_thread`-wrapped code is acceptable (it only blocks the worker thread).
- **Stdin contention:** if two plugins prompt for `input()` simultaneously they'll race on terminal. Phase 2 already runs `login_at_startup` sequentially (main.py:118-120). Keep that sequential path. The only `input()` calls inside the polling loop are CAPTCHA pauses; in practice N=2 simultaneous CAPTCHAs are extremely rare and acceptable for v1.

**Primary recommendation:** Implement as 5 plans across 3 waves: (W0) test infra + WAL/context-manager refactor; (W1) ABC shutdown + registry stagger; (W2) orchestrator rewrite (main.py + helper funcs). Plan ordering reflects dependency: orchestrator needs ABC.shutdown and stagger-aware registry; tests need pytest-asyncio installed first.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Event loop / TaskGroup orchestration | `main.py` (async entrypoint) | — | Single owner of the loop. |
| Blocking I/O bridging | Orchestrator call sites (via `asyncio.to_thread`) | — | Keeps plugin contract sync; one place to audit thread offloading. |
| Plugin instantiation + 1.5s stagger | `plugin_registry.discover()` | — | Pre-driver-construction sleep is required (CONTEXT pitfall 7). |
| Plugin lifecycle cleanup | `RetailerPlugin.shutdown()` (ABC default) | Orchestrator (`asyncio.shield` wrapper) | Each plugin knows its own resources; orchestrator guarantees they run. |
| SQLite write serialization | `purchase_writer` async task | `asyncio.Queue` | Single consumer = single writer = no PRAGMA busy conflicts in normal path. |
| SQLite WAL config | `models.initialize_db()` (one-time PRAGMA) + every `sqlite3.connect()` (busy_timeout) | — | WAL is DB-persistent; busy_timeout is per-connection. |
| Signal handling (Ctrl-C) | `main()` via `signal.signal` or default-handler propagation | TaskGroup catches `CancelledError` | Windows quirks require explicit handler. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncio (stdlib) | 3.11+ | TaskGroup, to_thread, Queue, shield, Event | Required; TaskGroup is 3.11+. [VERIFIED: docs.python.org/3.11/library/asyncio-task.html] |
| concurrent.futures.ThreadPoolExecutor (stdlib) | 3.11+ | Shared executor for to_thread offloads | Default executor type used by `asyncio.to_thread`. [VERIFIED: cpython asyncio/threads.py] |
| sqlite3 (stdlib) | 3.11+ | DB driver with WAL support | Already used; only WAL/busy_timeout config changes. [VERIFIED: docs.python.org/3/library/sqlite3.html] |

### Supporting (new dev dep)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | 1.3.0 | Run `async def` test functions under pytest | All new tests for orchestrator, purchase_writer, async fixtures [VERIFIED: pip index 2026-05-14] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncio.TaskGroup | asyncio.gather(return_exceptions=True) | gather doesn't cancel siblings on error — but loses structured-concurrency lifetime guarantees. TaskGroup is the modern idiom. |
| asyncio.to_thread | loop.run_in_executor | to_thread is a thin wrapper added in 3.9; identical semantics, cleaner API. |
| Single ThreadPoolExecutor | per-plugin ThreadPoolExecutor(max_workers=1) | Per-plugin pool gives stricter isolation but blocks `purchase_writer` from sharing capacity. Single shared pool is simpler. |
| asyncio.Queue + writer task | asyncio.Lock around each update | Lock is simpler, queue gives ordering + future retry/batch hooks (D-03 rationale). Stick with queue. |

**Installation:**
```bash
pip install pytest-asyncio==1.3.0
```

**Version verification:**
- `pytest-asyncio==1.3.0` — latest as of 2026-05-14 via `pip index versions pytest-asyncio`. [VERIFIED: pip registry query]
- All other deps already pinned in `requirements.txt` (selenium 4.43.0, pydantic 2.13.3, etc.)

## Architecture Patterns

### System Architecture Diagram

```
                  ┌────────────────────────────────┐
                  │       async def main()         │
                  │  - load AppConfig              │
                  │  - configure logger            │
                  │  - to_thread(collect_cvvs)     │
                  │  - to_thread(get_chromedriver) │
                  │  - set_default_executor(pool)  │
                  │  - install SIGINT handler      │
                  └───────────────┬────────────────┘
                                  │
                                  ▼
              ┌───────── discover_async(plugins_dir) ─────────┐
              │  for each shopbot_plugin_*.py:                │
              │    load class, instantiate (build_driver runs)│
              │    await asyncio.sleep(1.5)  ← STAGGER        │
              └──────────────┬────────────────────────────────┘
                             │
                             ▼
                  verify_coverage(...)
                  to_thread(_seed_items)
                  sequential: to_thread(plugin.login) per plugin
                  with login_at_startup=True
                             │
                             ▼
           ┌─────────── async with TaskGroup() ─────────────┐
           │                                                 │
           │   ┌────────────┐  ┌──────────────┐  ┌────────┐  │
           │   │ poll_plugin│  │ poll_plugin  │  │purchase│  │
           │   │ (amazon)   │  │ (bestbuy)    │  │ _writer│  │
           │   └─────┬──────┘  └──────┬───────┘  └────┬───┘  │
           │         │                │                │     │
           │         ▼                ▼                │     │
           │   to_thread(             to_thread(       │     │
           │    plugin.check_         plugin.check_    │     │
           │    availability)         availability)    │     │
           │         │                │                │     │
           │     [if avail]       [if avail]           │     │
           │         ▼                ▼                │     │
           │   to_thread(             to_thread(       │     │
           │    plugin.auto_buy)      plugin.auto_buy) │     │
           │         │                │                │     │
           │   queue.put(url) ────────┴─────►queue.get │     │
           │                                       ▼   │     │
           │                            to_thread(update_item_purchased)
           │                                                 │
           │   await asyncio.sleep(app.delay) loop  ─────────┤
           └─────────────────────────────────────────────────┘
                             │
                             ▼ on KeyboardInterrupt / CancelledError
                  finally:
                  asyncio.gather(
                    *(asyncio.shield(p.shutdown()) for p in registry),
                    return_exceptions=True,
                  )
```

### Recommended Project Structure (deltas only)
```
main.py                  # async def main(), helpers poll_plugin / purchase_writer
plugin_base.py           # +async def shutdown() default impl
plugin_registry.py       # +async def discover_async() with stagger
models.py                # +PRAGMA journal_mode=WAL at init, +busy_timeout per connect, context managers
requirements.txt         # +pytest-asyncio==1.3.0
pyproject.toml           # +[tool.pytest.ini_options] asyncio_mode = "auto"
tests/test_orchestrator.py    # NEW
tests/test_purchase_writer.py # NEW
tests/test_registry_stagger.py# NEW
tests/test_models_wal.py      # NEW
tests/test_plugin_shutdown.py # NEW
```

### Pattern 1: Per-task crash isolation under TaskGroup

**What:** A child task that raises any non-Cancelled exception in a `TaskGroup` cancels all siblings and ultimately raises an `ExceptionGroup` out of the `async with` block. To match D-01 isolation goals, wrap each plugin poll-task body in `try/except Exception`.

**When to use:** Every long-running plugin task inside `async with TaskGroup() as tg`.

**Example:**
```python
# Source: docs.python.org/3.11/library/asyncio-task.html#asyncio.TaskGroup
async def poll_plugin(plugin, app_config, queue, stop_event):
    while not stop_event.is_set():
        try:
            for item in await asyncio.to_thread(_items_for_plugin, plugin):
                if item.purchased:
                    continue
                try:
                    available = await asyncio.to_thread(
                        plugin.check_availability, item.link
                    )
                except Exception as e:
                    writeLog(f"{plugin.name}: check_availability raised: {e}", "ERROR")
                    continue
                if not available:
                    continue
                play_available_sound()
                if item.auto_buy:
                    try:
                        await asyncio.to_thread(plugin.auto_buy, item.link, app_config)
                        play_buy_sound()
                        await queue.put((item.link,))
                    except Exception as e:
                        writeLog(f"{plugin.name}: auto_buy raised: {e}", "ERROR")
        except asyncio.CancelledError:
            raise  # propagate so TaskGroup tears down cleanly
        except Exception as e:
            # Defensive: never let an unhandled exception escape into TaskGroup.
            writeLog(f"{plugin.name}: unexpected error: {e}", "ERROR")
        await asyncio.sleep(app_config.app.delay)
```

### Pattern 2: Shared ThreadPoolExecutor as default executor

```python
# Source: docs.python.org/3.11/library/asyncio-eventloop.html#asyncio.loop.set_default_executor
from concurrent.futures import ThreadPoolExecutor

async def main():
    loop = asyncio.get_running_loop()
    max_workers = max(4, len(registry) * 2)
    executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="shopbot")
    loop.set_default_executor(executor)
    try:
        # ... TaskGroup ...
    finally:
        executor.shutdown(wait=True, cancel_futures=False)
```

### Pattern 3: ABC default async shutdown (D-04)

```python
# Source: this project — Phase 4 D-04
import asyncio
from abc import ABC, abstractmethod

class RetailerPlugin(ABC):
    # ... existing ...
    async def shutdown(self) -> None:
        """Default cleanup: quit the Selenium driver in a worker thread.

        Override to add extra cleanup; call super().shutdown() at the end.
        Override MUST be async. Plugins with no driver (test stubs) should
        override and no-op.
        """
        driver = getattr(self, "driver", None)
        if driver is None:
            return
        try:
            await asyncio.to_thread(driver.quit)
        except Exception as e:
            writeLog(f"{type(self).__name__}.shutdown: driver.quit raised: {e}", "WARNING")
```

### Pattern 4: SQLite WAL + busy_timeout + context manager

```python
# Source: sqlite.org/wal.html + sqlite.org/pragma.html#pragma_busy_timeout
import sqlite3
from contextlib import contextmanager

DB_PATH = "data/shop_py_bot.db"

@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)  # python-level wait in addition to PRAGMA
    conn.execute("PRAGMA busy_timeout = 5000;")    # ms; per-connection
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def initialize_db(delete: bool = False) -> None:
    if delete and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    with _connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL;")  # persists across opens
        conn.execute("""CREATE TABLE IF NOT EXISTS items (...)""")

def update_item_purchased(link: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE items SET purchased = 1 WHERE link = ?", (link,))
```

### Pattern 5: 1.5s stagger inside discover_async

```python
async def discover_async(
    plugins_dir: Path,
    *,
    app_config,
    cvvs: dict[str, str],
    stagger_seconds: float = 1.5,
) -> list[RetailerPlugin]:
    instances: list[RetailerPlugin] = []
    paths = sorted(_iter_plugin_paths(plugins_dir))
    for index, path in enumerate(paths):
        if index > 0:
            await asyncio.sleep(stagger_seconds)
        inst = await asyncio.to_thread(
            _load_and_instantiate, path, app_config, cvvs
        )
        if inst is not None:
            instances.append(inst)
    return instances
```

### Anti-Patterns to Avoid

- **`asyncio.gather(*tasks)` instead of TaskGroup.** Loses structured concurrency; cancellation propagation is harder to reason about. TaskGroup is the 3.11+ idiom.
- **`time.sleep(1.5)` inside the discovery coroutine.** Blocks the event loop. Use `await asyncio.sleep(1.5)`.
- **Catching `CancelledError` and swallowing it.** Breaks `TaskGroup` teardown. Re-raise after any per-task cleanup.
- **Setting default executor inside the TaskGroup body.** First few `to_thread` calls in `discover_async` race against the assignment. Set it before TaskGroup opens.
- **Sharing a single sqlite3.Connection across threads.** Python sqlite3 connections are not thread-safe by default. Each `to_thread` call must open its own connection.
- **`asyncio.run()` called recursively or inside an existing loop.** Call once at `if __name__ == "__main__": asyncio.run(main())`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Concurrent plugin orchestration | Threading + manual queue | `asyncio.TaskGroup` | Structured concurrency, exception propagation, cancellation semantics built-in. |
| Async stdin reader | Custom `select.select` on stdin | `asyncio.to_thread(input, prompt)` | Works on Windows; no extra deps; D-02 lock. |
| SQLite multi-writer coordination | Hand-rolled file lock | WAL journal mode + busy_timeout | SQLite already solves this. |
| Writer serialization | Manual `asyncio.Lock` around every call site | `asyncio.Queue` + single consumer (D-03) | Centralizes retry/instrumentation; lower contention. |
| Driver lifecycle cleanup | Per-plugin signal handlers | ABC `async def shutdown()` default (D-04) | One place; inheritable; future plugins get it free. |

**Key insight:** asyncio + a shared executor is the right boundary for "concurrent control flow over blocking calls." Don't fight the stdlib; the trap in this domain is reaching for threading primitives that asyncio already wraps.

## Common Pitfalls

### Pitfall 1: TaskGroup cancels all siblings on unhandled exception
**What goes wrong:** One plugin raises a transient `selenium.common.exceptions.WebDriverException`; TaskGroup cancels all other plugins; bot exits with `ExceptionGroup`.
**Why it happens:** Documented behavior of `asyncio.TaskGroup`: "the first time any of the tasks in the group fails with an exception other than `asyncio.CancelledError`, the remaining tasks in the group are cancelled." [VERIFIED: docs.python.org/3.11/library/asyncio-task.html#asyncio.TaskGroup]
**How to avoid:** Wrap each plugin task body in `try/except Exception` that logs and continues. Let `CancelledError` propagate.
**Warning signs:** Bot exits unexpectedly with no clear cause; logs show one plugin error followed by silence from all others.

### Pitfall 2: WAL mode set on one connection but not persisted
**What goes wrong:** Setting `PRAGMA journal_mode = WAL` is persistent at the DB-file level but ONLY if the connection actually writes to the DB before closing. A read-only initial PRAGMA without a write can be silently rolled back.
**Why it happens:** SQLite stores the journal mode in the file header at next checkpoint. Empty WAL connections close cleanly without writing the mode.
**How to avoid:** Set `PRAGMA journal_mode = WAL` inside `initialize_db()` and immediately follow with `CREATE TABLE IF NOT EXISTS` (which always writes). Verify with `cursor.fetchone()` returning `("wal",)`.
**Warning signs:** Concurrent test fails with `sqlite3.OperationalError: database is locked` despite WAL config.

### Pitfall 3: busy_timeout is per-connection, not per-database
**What goes wrong:** Setting `PRAGMA busy_timeout = 5000` once at init does not apply to later `sqlite3.connect()` calls.
**Why it happens:** `busy_timeout` is connection state. [VERIFIED: sqlite.org/pragma.html#pragma_busy_timeout]
**How to avoid:** Apply busy_timeout in the `_connect()` context manager so every connection gets it. Use `sqlite3.connect(DB_PATH, timeout=5.0)` as belt-and-suspenders (Python-level wait).

### Pitfall 4: ThreadPoolExecutor lifecycle leaks chromedriver.exe on Windows
**What goes wrong:** Process hangs on exit; orphaned `chromedriver.exe` in Task Manager.
**Why it happens:** `driver.quit()` not called or interrupted before completion; default executor not shut down with `wait=True`.
**How to avoid:** Wrap each `plugin.shutdown()` in `asyncio.shield(...)` so Ctrl-C-during-shutdown doesn't cancel `driver.quit`. Call `executor.shutdown(wait=True)` in `main()` finally block.
**Warning signs:** Subsequent runs fail with "ChromeDriver address already in use" or stale lockfiles in user profile dirs.

### Pitfall 5: Queue.task_done() missed on exception → join() hangs
**What goes wrong:** `purchase_writer` raises inside the loop body without `queue.task_done()`; any `await queue.join()` (used in tests) hangs forever.
**Why it happens:** `task_done` must match `get` 1:1. Documented in asyncio.Queue API.
**How to avoid:** Put `task_done()` in a `finally` block.

### Pitfall 6: Windows Ctrl-C signal handling under ProactorEventLoop
**What goes wrong:** On Windows, pressing Ctrl-C in a console running an async app sometimes fails to interrupt the loop; user has to kill the process.
**Why it happens:** ProactorEventLoop (Windows default since 3.8) handles signals less cleanly than SelectorEventLoop. [CITED: docs.python.org/3/library/asyncio-platforms.html#windows]
**How to avoid:** Either (a) explicitly install `signal.signal(signal.SIGINT, _sigint_handler)` where `_sigint_handler` sets an `asyncio.Event` the orchestrator monitors, OR (b) switch to `asyncio.WindowsSelectorEventLoopPolicy()` (we don't use subprocess pipes, so Selector is fine).
**Warning signs:** Ctrl-C printed but bot keeps logging; user must Ctrl-Break or close terminal.

### Pitfall 7: 1.5s stagger placed AFTER driver construction
**What goes wrong:** Two plugins instantiated within microseconds both call `webdriver.Chrome(...)`; chromedriver TCP port bind conflicts on Windows.
**Why it happens:** Chromedriver allocates a random ephemeral port at startup but the bind window has been observed to race on Windows. [CONTEXT.md pitfall 7]
**How to avoid:** Sleep BEFORE the next `_instantiate(...)` call in `discover_async`. The sleep must straddle plugin construction, not happen inside a plugin task that starts after construction.

### Pitfall 8: SQLite connection shared across threads
**What goes wrong:** `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread.`
**Why it happens:** Default `sqlite3.connect` is thread-checked.
**How to avoid:** Each `to_thread(update_item_purchased, ...)` opens its own connection (current pattern; preserve it). Do NOT cache a module-level connection.

### Pitfall 9: Mixing `time.sleep` and `asyncio.sleep`
**What goes wrong:** Calling `time.sleep(...)` from a coroutine blocks the event loop; all plugin tasks stall.
**Why it happens:** Easy to copy from sync code.
**How to avoid:** Lint rule (manual review) — in any `async def` body, only `await asyncio.sleep(...)`. `time.sleep` is fine inside the body of a function called via `to_thread` (Selenium WebDriverWait does this internally; that's OK because it's on a worker thread).
**Warning signs:** Bot stalls for periodic intervals; only one plugin makes progress at a time.

### Pitfall 10: purchase_writer dies silently
**What goes wrong:** An unhandled exception in `purchase_writer` kills the task; subsequent `queue.put(...)` calls succeed but no writes happen; bot re-buys items every loop.
**Why it happens:** Inside a TaskGroup, if `purchase_writer` raises Exception, ALL siblings are cancelled — but if we wrap it in try/except like plugin tasks, we may hide the death.
**How to avoid:** `purchase_writer` is critical infrastructure, not a plugin. If it raises, the bot SHOULD stop. Do NOT wrap its body in a defensive try/except. Let TaskGroup teardown happen.
**Decision boundary:** plugin task crashes are isolated; infrastructure task crashes are fatal.

### Pitfall 11: Stdin contention between concurrent plugins
**What goes wrong:** Amazon plugin shows "Press Enter after OTP..." while BestBuy plugin shows "Press Enter after solving the CAPTCHA..." — keystrokes route to whichever plugin called `input()` last.
**Why it happens:** Terminal stdin is shared singleton.
**How to avoid:** Phase 2 already serializes `login_at_startup` (main.py:118-120 — keep this). For runtime CAPTCHA prompts: accept the limitation for v1. Document in CONTRIBUTING that "two simultaneous CAPTCHA prompts may interleave; rare at N=2 plugins." Could add a global `asyncio.Lock("stdin_lock")` in a later phase if it becomes a real problem.

## Runtime State Inventory

Phase 4 is a control-flow refactor with no rename/migration component, but we still need to enumerate state that survives across runs.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `data/shop_py_bot.db` — items table; existing schema is compatible with WAL (no schema change). | Migration: existing DB files need `PRAGMA journal_mode=WAL` applied on first Phase 4 run. `initialize_db()` runs every startup so this is automatic. WAL adds two sidecar files (`-wal`, `-shm`). |
| Live service config | None — no n8n / Datadog / external service config in this project. | None. |
| OS-registered state | None — bot is launched manually; no scheduled task / pm2 registration. | None. |
| Secrets/env vars | `SHOPBOT_PLATFORMS__*` env vars from Phase 1. No new env vars in Phase 4. | None. |
| Build artifacts | None (no compiled artifacts). | None. |

**WAL sidecar files:** Add `data/*.db-wal` and `data/*.db-shm` to `.gitignore` if not already covered by `data/`. Verify in plan.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | TaskGroup, ExceptionGroup | ✓ | enforced by main.py sys.exit | — |
| pytest | existing tests | ✓ | 8.3.4 (requirements.txt) | — |
| pytest-asyncio | NEW for Phase 4 tests | ✗ | — | None — must install. Add to requirements.txt. |
| ChromeDriver | plugins' Selenium drivers | ✓ via webdriver_manager | auto | — |

**Missing dependencies with no fallback:**
- `pytest-asyncio==1.3.0` — must be added in Wave 0 before any async tests are written.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 + pytest-asyncio 1.3.0 (NEW) |
| Config file | `pyproject.toml` (add `[tool.pytest.ini_options]` block) |
| Quick run command | `pytest tests/test_orchestrator.py tests/test_purchase_writer.py tests/test_registry_stagger.py tests/test_models_wal.py tests/test_plugin_shutdown.py -x` |
| Full suite command | `pytest -x` |
| Async mode | `asyncio_mode = "auto"` (every `async def test_*` becomes asyncio test without decorator) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ASYNC-01 | TaskGroup runs N plugins concurrently | unit (asyncio) | `pytest tests/test_orchestrator.py::test_concurrent_polling -x` | ❌ Wave 0 |
| ASYNC-01 | Plugin task crash does not cancel siblings | unit (asyncio) | `pytest tests/test_orchestrator.py::test_plugin_crash_isolated -x` | ❌ Wave 0 |
| ASYNC-01 | Default executor set before TaskGroup opens | unit | `pytest tests/test_orchestrator.py::test_executor_configured_before_taskgroup -x` | ❌ Wave 0 |
| ASYNC-02 | discover_async sleeps 1.5s between instantiations | unit (asyncio, fake clock or monkeypatched sleep) | `pytest tests/test_registry_stagger.py::test_stagger_between_plugins -x` | ❌ Wave 0 |
| ASYNC-02 | First plugin instantiation does not sleep | unit (asyncio) | `pytest tests/test_registry_stagger.py::test_first_plugin_no_sleep -x` | ❌ Wave 0 |
| ASYNC-03 | input() never called directly in async path; `to_thread(input, ...)` used | static + unit | `pytest tests/test_orchestrator.py::test_input_via_to_thread -x` | ❌ Wave 0 |
| ASYNC-04 | initialize_db sets WAL mode (verified by PRAGMA query) | unit | `pytest tests/test_models_wal.py::test_journal_mode_is_wal -x` | ❌ Wave 0 |
| ASYNC-04 | Every connect() applies busy_timeout=5000 | unit | `pytest tests/test_models_wal.py::test_busy_timeout_applied -x` | ❌ Wave 0 |
| ASYNC-04 | Connection context manager rolls back on exception | unit | `pytest tests/test_models_wal.py::test_context_manager_rollback -x` | ❌ Wave 0 |
| ASYNC-05 | purchase_writer drains queue, calls update_item_purchased | unit (asyncio) | `pytest tests/test_purchase_writer.py::test_writer_drains_queue -x` | ❌ Wave 0 |
| ASYNC-05 | queue.task_done called on writer exception | unit (asyncio) | `pytest tests/test_purchase_writer.py::test_task_done_on_failure -x` | ❌ Wave 0 |
| D-04 (supports ASYNC-01) | ABC.shutdown is async coroutine | unit | `pytest tests/test_plugin_shutdown.py::test_shutdown_is_coroutine -x` | ❌ Wave 0 |
| D-04 | Default shutdown calls driver.quit via to_thread | unit (asyncio, mock) | `pytest tests/test_plugin_shutdown.py::test_default_shutdown_quits_driver -x` | ❌ Wave 0 |
| D-04 | Plugin without `self.driver` shutdown no-ops | unit (asyncio) | `pytest tests/test_plugin_shutdown.py::test_shutdown_no_driver_attribute -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_<changed_module>.py -x` (~5s)
- **Per wave merge:** `pytest -x` (full suite, ~15-30s)
- **Phase gate:** Full suite green + manual smoke (start bot, observe two plugins start 1.5s apart, Ctrl-C exits cleanly with no orphaned chromedriver.exe)

### Wave 0 Gaps

- [ ] `pyproject.toml` `[tool.pytest.ini_options]` block with `asyncio_mode = "auto"` (or new file if not present). Project currently has no pyproject; planner picks file location.
- [ ] `tests/conftest.py` shared async fixtures: `event_loop` (rarely needed in auto mode), `tmp_db_path` (sqlite tempfile), `app_config_fixture` (minimal AppConfig stub), `fake_plugin_factory` (RetailerPlugin subclass with mocked driver).
- [ ] `tests/test_orchestrator.py` — covers ASYNC-01, ASYNC-03.
- [ ] `tests/test_purchase_writer.py` — covers ASYNC-05.
- [ ] `tests/test_registry_stagger.py` — covers ASYNC-02.
- [ ] `tests/test_models_wal.py` — covers ASYNC-04.
- [ ] `tests/test_plugin_shutdown.py` — covers D-04 (supports ASYNC-01).
- [ ] Framework install: add `pytest-asyncio==1.3.0` to `requirements.txt`.

### Sample test patterns

```python
# tests/test_orchestrator.py
import asyncio
import pytest

async def test_plugin_crash_isolated(monkeypatch, fake_plugin_factory):
    """ASYNC-01: one plugin's check_availability raising must not cancel siblings."""
    good = fake_plugin_factory(name="good", check_returns=False)
    bad  = fake_plugin_factory(name="bad",  check_raises=RuntimeError("boom"))
    queue = asyncio.Queue()
    stop = asyncio.Event()

    async def run_briefly():
        async with asyncio.TaskGroup() as tg:
            tg.create_task(poll_plugin(good, _stub_config(), queue, stop))
            tg.create_task(poll_plugin(bad,  _stub_config(), queue, stop))
            await asyncio.sleep(0.05)
            stop.set()

    await run_briefly()  # must complete; if siblings were cancelled, TaskGroup raises
    assert good.check_calls > 0
    assert bad.check_calls > 0  # bad kept being polled despite raising


# tests/test_purchase_writer.py
async def test_writer_drains_queue(monkeypatch):
    calls = []
    monkeypatch.setattr("main.update_item_purchased", lambda url: calls.append(url))
    q: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(purchase_writer(q))
    await q.put(("https://a.example",))
    await q.put(("https://b.example",))
    await q.join()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == ["https://a.example", "https://b.example"]


# tests/test_registry_stagger.py
async def test_stagger_between_plugins(monkeypatch, tmp_path):
    sleeps: list[float] = []
    async def fake_sleep(s): sleeps.append(s)
    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    # ... create two stub shopbot_plugin_*.py in tmp_path ...
    await discover_async(tmp_path, app_config=None, cvvs={})
    assert sleeps == [1.5]  # exactly one sleep between two plugins, none before first


# tests/test_models_wal.py
def test_journal_mode_is_wal(tmp_path, monkeypatch):
    monkeypatch.setattr("models.DB_PATH", str(tmp_path / "test.db"))
    initialize_db(delete=True)
    with sqlite3.connect(str(tmp_path / "test.db")) as conn:
        row = conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0].lower() == "wal"


# tests/test_plugin_shutdown.py
async def test_default_shutdown_quits_driver():
    class P(RetailerPlugin):
        domain_pattern = ["x.com"]
        def check_availability(self, url): return False
        def auto_buy(self, url, config): return False
    p = P(platform_config=None)
    p.driver = MagicMock()
    await p.shutdown()
    p.driver.quit.assert_called_once()
```

## Security Domain

(`security_enforcement` not explicitly set; treat as enabled.)

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 1 already covered credentials. Phase 4 changes no auth surface. |
| V3 Session Management | no | No new sessions introduced. |
| V4 Access Control | no | No new access boundaries. |
| V5 Input Validation | yes | OTP `input()` prompts: validate not-empty before continuing (already done in `collect_cvvs` pattern). |
| V6 Cryptography | no | No new crypto. |
| V10 Coding | yes | Concurrency safety: SQLite thread isolation, no shared mutable state between plugin tasks. |
| V12 Files & Resources | yes | WAL sidecar files (`*.db-wal`, `*.db-shm`) must be `.gitignore`d to avoid leaking transient transaction data. |

### Known Threat Patterns for asyncio + Selenium stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Race on `update_item_purchased` (double-buy) | Tampering | Single writer task (D-03) serializes writes; WAL+busy_timeout handles unexpected concurrent writes. |
| Orphan chromedriver.exe holding open sockets | Denial-of-Service (against own machine) | `asyncio.shield(p.shutdown())` in finally block (D-04) |
| Stdin hijack between plugins | Tampering | Document; v2 stdin_lock if needed. |
| WAL file content disclosure via git commit | Information Disclosure | `.gitignore` for `data/*.db-wal` and `data/*.db-shm` |
| KeyboardInterrupt swallowed → unkillable bot | Availability | Explicit SIGINT handler; do not catch `KeyboardInterrupt` broadly. |

## Per-Question Research

### Q1: asyncio.TaskGroup error semantics

**Verified behavior (Python 3.11+):**
- When any child task raises a non-`CancelledError` exception, TaskGroup cancels all other tasks, awaits their teardown, and re-raises an `ExceptionGroup` from the `async with` block.
- `CancelledError` from a child propagates differently: if external code cancels a task, TaskGroup handles it without treating it as a failure of the group.
- `KeyboardInterrupt` and `SystemExit` propagate out of the TaskGroup as they are not subclasses of `Exception`.

Source: docs.python.org/3.11/library/asyncio-task.html#asyncio.TaskGroup [VERIFIED].

**Compatibility with ASYNC-01 isolation goal:** Default behavior is INCOMPATIBLE. Each plugin task body must catch `Exception` (not `BaseException`) and log/continue.

**Recommended pattern (also given in Architecture Patterns above):**
```python
async def poll_plugin(plugin, app_config, queue, stop_event):
    while not stop_event.is_set():
        try:
            # body: get_items, check_availability, auto_buy
            ...
        except asyncio.CancelledError:
            raise
        except Exception as e:
            writeLog(f"{plugin.name}: {e}", "ERROR")
        await asyncio.sleep(app_config.app.delay)
```

**Edge cases:**
- `KeyboardInterrupt` not caught here (propagates to main's finally).
- `SystemExit` likewise.
- `CancelledError` re-raised (TaskGroup teardown).

### Q2: ThreadPoolExecutor sizing and sharing

**Verified:** `asyncio.to_thread(func, *args, **kwargs)` uses `loop.run_in_executor(None, ...)`, which uses the loop's default executor. The default-default is a private `ThreadPoolExecutor(max_workers=min(32, os.cpu_count() + 4))` — but you should set your own via `loop.set_default_executor` to control sizing and lifetime. [VERIFIED: cpython Lib/asyncio/threads.py and asyncio/base_events.py]

**Sizing formula (recommended for this project):**
```
max_workers = max(4, len(plugins) * 2)
```
Rationale per plugin: 1 worker for in-flight Selenium call + 1 worker for OTP-blocked `input()`. Plus minimum 4 to give headroom for `purchase_writer`, `collect_cvvs`, and one-shot startup calls.

**Lifecycle:**
- Construct `ThreadPoolExecutor` after `len(plugins)` is known (post-discovery).
- Call `loop.set_default_executor(executor)` before the TaskGroup opens.
- In main's `finally`: `executor.shutdown(wait=True, cancel_futures=False)`. `wait=True` because we want `driver.quit` calls to complete; `cancel_futures=False` because pending futures should run to completion (last writes from the queue).

**Don't use per-call `executor=...`** — locked decision D-01 says "single shared". Per-call would diverge.

### Q3: Selenium inside asyncio idioms

Two options, recommend **Option A** (wrap at orchestrator call site):

**Option A (recommended):**
```python
available = await asyncio.to_thread(plugin.check_availability, item.link)
```
Pros: plugin code stays sync. Plugin authors write normal Selenium code with no `async` exposure. Aligns with Phase 1/2 ABC contract (no breaking changes). Single place to audit thread offloading.
Cons: orchestrator code has more boilerplate.

**Option B (rejected):**
Plugin methods become `async def` internally and call `to_thread` themselves. Pros: caller is simpler. Cons: breaks plugin contract (PLG-03 plugins ship sync methods today); raises plugin author cognitive load; violates "plugin code stays beginner-friendly" core value.

**Selenium thread-safety:** Selenium WebDriver instances are not thread-safe — calls against the same driver from multiple threads can interleave HTTP requests to chromedriver and corrupt state. Each plugin owns its own driver (PLG-03) so cross-plugin parallelism is fine. Within one plugin, `to_thread` calls on the same driver from the same plugin task serialize naturally (one `await` at a time). **No same-driver concurrency is created by Option A.** [VERIFIED by inspection: PLG-03 contract; no shared driver anywhere in current code.]

### Q4: SQLite WAL + busy_timeout under concurrent writes

**WAL semantics (verified, sqlite.org/wal.html):**
- WAL allows readers and one writer to coexist without blocking.
- Multiple writers still serialize, but `busy_timeout` makes the second writer wait instead of immediately erroring.
- WAL journal mode is **persistent** in the DB file header. Once set, it survives reopens.

**busy_timeout semantics (sqlite.org/pragma.html#pragma_busy_timeout):**
- Per-connection. Must be set on every `sqlite3.connect()`.
- Blocks the calling thread up to N ms when a lock is contended; then raises `sqlite3.OperationalError: database is locked`.
- 5000 ms is appropriate for N=2-5 plugins at v1 scale.

**Concurrent write profile in this app:**
- `update_item_purchased` is the only contended write. With `purchase_writer` (D-03) draining the queue serially, there's only ONE writer task ever. So WAL + busy_timeout is belt-and-suspenders against `add_items` (startup) accidentally overlapping or future contributors adding writes.
- `get_items`-style reads happen inside polling tasks. WAL lets them proceed concurrently with the writer. No timeout needed for readers in normal cases.

**Connection pattern recommendation:**
- One connection per call (current behavior). Each `to_thread`-invoked function opens its own.
- Do NOT persist a per-thread connection: thread identity across `to_thread` invocations is not stable; the executor can reuse worker threads but you don't control which.

**Where PRAGMA journal_mode=WAL goes:**
- ONCE inside `initialize_db()`. It writes to the file header.
- For safety: verify with `cursor.execute("PRAGMA journal_mode").fetchone()` and log a WARNING if not 'wal'.

**VACUUM caveat (informational):** WAL mode requires explicit `PRAGMA wal_checkpoint` before `VACUUM` can run. Not relevant for this app — no VACUUM in current code.

### Q5: pytest-asyncio patterns

**Latest stable: 1.3.0 (verified pip index 2026-05-14).** Pin exactly: `pytest-asyncio==1.3.0`.

**Recommended mode: `asyncio_mode = "auto"`.**
- "auto" treats every `async def test_*` function as an asyncio test without requiring `@pytest.mark.asyncio`.
- "strict" requires the marker. More explicit, but adds noise across many new test files.
- For a brownfield project adding asyncio for the first time, "auto" reduces decoration boilerplate. Existing sync tests are unaffected.

**Add to `pyproject.toml` (create if missing):**
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Async fixture pattern for AppConfig + tmp DB:**
```python
import pytest, pytest_asyncio
from unittest.mock import MagicMock

@pytest.fixture
def tmp_db_path(tmp_path, monkeypatch):
    p = tmp_path / "test.db"
    monkeypatch.setattr("models.DB_PATH", str(p))
    return p

@pytest.fixture
def app_config_stub():
    cfg = MagicMock()
    cfg.debug.test_mode = True
    cfg.debug.logging_level = 0
    cfg.app.delay = 0.01
    cfg.available.items = []
    cfg.open_browser = False
    return cfg
```

**Testing a TaskGroup that exits via KeyboardInterrupt:** Don't simulate KeyboardInterrupt directly (pytest-asyncio handles it specially). Instead, pass an `asyncio.Event` `stop_event` into the orchestrator and assert teardown after setting it.

**Testing purchase_writer drains:**
- Create `q = asyncio.Queue()`, put items, `task = asyncio.create_task(purchase_writer(q))`, await `q.join()` (this returns when all puts are matched by `task_done`), then `task.cancel()`.

**Mocking Selenium inside async tests:**
- Use a fake plugin subclass with `self.driver = MagicMock()`. The orchestrator calls `await asyncio.to_thread(plugin.check_availability, url)`; since `check_availability` is a sync method on the fake, it runs in the executor and returns the mocked value.

### Q6: Windows event loop policy quirks

**Default (Python 3.8+):** `WindowsProactorEventLoopPolicy`. Signal handling on Windows is delivered via the C runtime, not via the Win32 events the Proactor loop listens to. KeyboardInterrupt may not propagate into the loop until the next iteration. [CITED: docs.python.org/3/library/asyncio-platforms.html#windows]

**Two acceptable patterns:**

**Pattern A: explicit SIGINT handler + stop event** (recommended, cross-platform):
```python
import signal
import asyncio

async def main():
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _on_sigint():
        writeLog("SIGINT received; initiating shutdown", "INFO")
        stop_event.set()

    if sys.platform == "win32":
        # Proactor on Windows: signal.signal is reliable; loop.add_signal_handler is NOT.
        signal.signal(signal.SIGINT, lambda *_: loop.call_soon_threadsafe(_on_sigint))
    else:
        loop.add_signal_handler(signal.SIGINT, _on_sigint)
    # ... pass stop_event into poll_plugin and check it in the loop ...
```

**Pattern B: switch to Selector loop on Windows** (simpler if we don't need subprocess pipes):
```python
import sys, asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
```
We do NOT use `asyncio.create_subprocess_exec` or async pipes anywhere; Selector loop is safe.

**Recommendation: Pattern A** — keeps the door open for any future subprocess use, costs ~5 lines.

### Q7: 1.5s stagger implementation site

**Option A (recommended): inside `plugin_registry.discover_async()` between instantiations.**
- The driver TCP-bind race window is during `webdriver.Chrome(...)` inside plugin `__init__`. The sleep MUST be BEFORE that call.
- Sequential discovery is naturally where the sleep belongs.
- One place to test (`test_stagger_between_plugins`).

**Option B (rejected): inside each plugin's poll task with `await asyncio.sleep(1.5 * index)`.**
- Driver is already constructed in `__init__` by the time the poll task starts; race window already passed.
- Would only stagger first-poll timing, not driver startup.

**Implementation:** add `async def discover_async(...)` as a sibling of `discover(...)`. Keep `discover(...)` (sync) for any legacy callers or test fixtures that don't need stagger. `main()` calls `discover_async`.

### Q8: add_items / get_items concurrency

**add_items:** Called once at startup (main.py:122 today, will be `_seed_items` post-rewrite). No concurrency. Safe.

**get_items:** Called from inside each plugin's poll task (one per plugin). Read-only. WAL allows concurrent readers + one writer with zero blocking. [VERIFIED: sqlite.org/wal.html "Readers do not block writers and a writer does not block readers"].

**Action for the planner:** in `poll_plugin`, the current `get_items()` returns ALL items. Phase 4 can either:
- (a) keep `get_items()` returning all rows and filter in-Python by plugin (simple), or
- (b) add `get_items_for_plugin(plugin)` that filters in SQL by `domain_pattern` (faster at scale, but plugin_pattern is a Python list — would need WHERE link LIKE ... OR ... composition).

For v1 scale (10-50 items), option (a) is cheaper to implement and reason about. Recommend (a).

### Q9: input() inside an existing plugin

**Locked: D-02 says `asyncio.to_thread(input, prompt)`.**

**Architectural decision for the planner:** Inside Phase 2 plugins, `input()` calls are at:
- `shopbot_plugin_amazon.py:75` (CAPTCHA pause)
- `shopbot_plugin_amazon.py:96` (passkey dismissal during login)
- `shopbot_plugin_amazon.py:159` (MFA OTP)
- `shopbot_plugin_amazon.py:185` (test mode pause)
- `shopbot_plugin_amazon.py:245` (test mode pause)

These run inside SYNC plugin methods (`check_availability`, `login`, `auto_buy`). The orchestrator invokes those methods via `await asyncio.to_thread(plugin.method, ...)`. **Inside a worker thread, calling `input()` directly blocks ONLY that worker thread** — not the event loop, not other plugin tasks. [VERIFIED: Python threading semantics; `input()` is just blocking stdin read.]

**Therefore: plugin authors keep writing `input("...")` as sync code.** No changes needed to plugin internals for D-02. The "convert input() to asyncio" requirement is satisfied by the orchestrator's existing `to_thread` wrapping.

**Caveat for the planner:** verify this conclusion by writing an explicit test (`test_plugin_input_in_to_thread_does_not_block_loop`) that puts one plugin in `input()` while another plugin's `check_availability` is exercised — assert both make progress.

**Stdin contention:** see Pitfall 11. Acceptable for v1 at N=2 plugins.

### Q10: Pitfalls and anti-patterns

Summarized in Pitfalls section above. Numbered list for must_haves.truths in PLAN.md:

1. `await plugin.method(...)` is a TypeError for sync methods — always wrap with `asyncio.to_thread`.
2. `asyncio.run()` is called exactly once, inside `if __name__ == "__main__":`.
3. `asyncio.get_event_loop()` is deprecated in 3.12 — use `asyncio.get_running_loop()` inside coroutines.
4. `queue.task_done()` must be called in a `finally` block in `purchase_writer`.
5. Plugin task exceptions are caught (`except Exception`), `CancelledError` is re-raised.
6. `purchase_writer` exceptions are NOT caught — infrastructure failure should tear down the bot.
7. SQLite connections are NOT shared across threads — each call opens its own.
8. `loop.set_default_executor(...)` happens BEFORE the TaskGroup opens.
9. `time.sleep` is forbidden in any `async def` body; `asyncio.sleep` only.
10. Selenium `driver.quit` always goes via `asyncio.to_thread` (can block for seconds).
11. `asyncio.shield(p.shutdown())` wraps shutdown calls in the `finally` block.
12. WAL PRAGMA goes ONCE in `initialize_db()`; `busy_timeout` goes on every `sqlite3.connect()`.
13. Add `data/*.db-wal` and `data/*.db-shm` to `.gitignore`.
14. Windows SIGINT requires explicit `signal.signal(SIGINT, ...)` not `loop.add_signal_handler` under Proactor loop.
15. ThreadPoolExecutor `executor.shutdown(wait=True)` in main's finally.

### Q11: Anti-detection considerations

**Concurrent same-retailer polling:** Phase 4 v1 has one Amazon + one BestBuy plugin. No two plugins poll the same retailer. Cross-plugin same-retailer is not a concern until Phase 6 (Walmart, Target, etc.).

**Stagger as anti-detection:** ASYNC-02 (1.5s stagger) primarily addresses chromedriver port races, but it also has the side benefit that each plugin's first request to its retailer goes out at a different wall-clock time. Useful, no behavior change needed.

**Random jitter on stagger:** ASYNC-02 wording is "at least 1.5 seconds apart". Adding `random.uniform(0, 0.5)` on top is compatible. **Recommendation: do not add jitter in Phase 4** — keep stagger deterministic so the test (`test_stagger_between_plugins`) can assert exact values. ANTI-01 in Phase 6 will introduce per-platform `min_delay`/`max_delay` with jitter at the polling-cadence layer, where it actually affects retailer detection. Stagger at driver startup runs once per session and is not the relevant signal for retailer heuristics.

## Recommended Plan Layout

Five atomic plans grouped into three waves. Per-plan dependency reasoning provided.

### Wave 0 — Test Infrastructure (must precede all impl plans)

**Plan 04-01: Test infrastructure for async**
- Goal: `pytest-asyncio` installed, `pyproject.toml` configured, `tests/conftest.py` async fixtures in place. RED tests exist for all phase requirements (failing because production code doesn't exist yet).
- Files: `requirements.txt`, `pyproject.toml` (NEW), `tests/conftest.py` (NEW), `tests/test_orchestrator.py` (NEW skeleton), `tests/test_purchase_writer.py` (NEW skeleton), `tests/test_registry_stagger.py` (NEW skeleton), `tests/test_models_wal.py` (NEW skeleton), `tests/test_plugin_shutdown.py` (NEW skeleton).
- Acceptance: `pytest -x` runs the new files; tests are failing (RED) for the right reasons.
- Why first: every other plan needs the test scaffolding to land in TDD order.

### Wave 1 — Infrastructure plans (run in parallel after Wave 0)

These three plans don't touch `main.py` and can land in any order or in parallel.

**Plan 04-02: SQLite WAL + context-manager refactor (ASYNC-04)**
- Goal: `models.py` uses WAL mode set at `initialize_db`, busy_timeout on every connect, all DB operations via context manager.
- Files: `models.py`, `tests/test_models_wal.py`.
- Acceptance: `pytest tests/test_models_wal.py -x` green. `PRAGMA journal_mode` returns 'wal'. Context manager rolls back on exception. `.gitignore` covers `data/*.db-wal`/`-shm`.
- Why parallel-safe: pure module-internal refactor; signatures unchanged.

**Plan 04-03: Plugin ABC async shutdown (D-04)**
- Goal: `RetailerPlugin.shutdown()` defined as async with default implementation. Existing plugins inherit; no changes to Amazon/BestBuy plugin internals.
- Files: `plugin_base.py`, `tests/test_plugin_shutdown.py`.
- Acceptance: `pytest tests/test_plugin_shutdown.py -x` green. Shutdown is a coroutine. Default impl calls `to_thread(driver.quit)`. Plugins without `self.driver` no-op.
- Why parallel-safe: additive to ABC; no existing call sites need changes.

**Plan 04-04: Async plugin discovery with stagger (ASYNC-02)**
- Goal: `plugin_registry.discover_async()` introduced. Sleeps 1.5s between successive plugin instantiations. Reuses existing class-loading + `_instantiate` logic via `asyncio.to_thread`.
- Files: `plugin_registry.py`, `tests/test_registry_stagger.py`.
- Acceptance: `pytest tests/test_registry_stagger.py -x` green. `discover_async` returns identical results to `discover` for any input (test sample). Sleeps applied between plugins, not before the first.
- Why parallel-safe: `discover_async` is new; `discover` (sync) preserved for now.

### Wave 2 — Orchestrator (depends on Wave 1)

**Plan 04-05: Orchestrator rewrite — async main, TaskGroup, purchase_writer, signal handling (ASYNC-01, ASYNC-03, ASYNC-05)**
- Goal: `main.py` rewritten as `async def main()`. Uses `discover_async`, `TaskGroup`, `purchase_writer`, `asyncio.to_thread` for all blocking calls. Default executor set with `max(4, len(plugins) * 2)`. SIGINT handler installed. Plugin shutdown awaited under `asyncio.shield` in finally.
- Files: `main.py`, `plugins/shopbot_plugin_amazon.py` (no changes expected; verify input() calls are OK in to_thread context), `plugins/shopbot_plugin_bestbuy.py` (likewise), `tests/test_orchestrator.py`, `tests/test_purchase_writer.py`.
- Acceptance: `pytest -x` green (full suite). Manual smoke: bot starts, both plugins enter polling within 2 seconds of each other (1.5s + margin), Ctrl-C exits within 5 seconds with no orphaned chromedriver.exe.
- Why last: depends on ABC shutdown (Plan 04-03), discover_async (Plan 04-04), WAL models (Plan 04-02).

### Wave dependency graph

```
Wave 0: 04-01 (test infra)
            │
            ▼
Wave 1: 04-02 (models WAL) ──┐
        04-03 (ABC shutdown) ─┤
        04-04 (registry async)┤
                              ▼
Wave 2: 04-05 (orchestrator) — must follow 04-02, 04-03, 04-04
```

If the planner wants a 6th plan, split 04-05 into:
- **04-05a:** Async main + executor + signal handling + discover_async wiring (no purchase_writer yet — call `update_item_purchased` via `to_thread` directly).
- **04-05b:** Introduce `purchase_writer` + `asyncio.Queue` between plugins and `update_item_purchased`.
Recommendation: keep as 5 plans. 04-05 is cohesive; splitting adds an intermediate state where the writer-queue requirement isn't met.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `asyncio.gather(return_exceptions=True)` | `asyncio.TaskGroup` | Python 3.11 (Oct 2022) | Structured concurrency; cancellation semantics; project requires 3.11 so we use TaskGroup. |
| `loop.run_in_executor(None, ...)` | `asyncio.to_thread(...)` | Python 3.9 (Oct 2020) | Cleaner API; equivalent semantics. |
| Per-PRAGMA `synchronous=NORMAL` tuning | Just `journal_mode=WAL` | SQLite 3.7+ | WAL is the modern default for concurrent workloads. |
| `pytest-asyncio` strict mode | "auto" mode for new projects | pytest-asyncio 0.21+ | Less decoration boilerplate; explicit opt-out per-test if needed. |

**Deprecated/outdated:**
- `asyncio.get_event_loop()` — deprecated 3.12. Use `asyncio.get_running_loop()` inside coroutines, `asyncio.new_event_loop()` only if you need to create one.
- `@asyncio.coroutine` decorator — removed 3.11.
- `loop.set_event_loop_policy(policy)` for platform tweaks — still supported but consider whether you need it; `asyncio.run` creates a fresh loop.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | N=2 simultaneous CAPTCHA prompts is acceptable for v1 | Pitfall 11, Q9 | Users see interleaved stdin; UX confusion; mitigated by Phase 5 notifications and documentation. |
| A2 | `loop.set_default_executor` happens before any `to_thread` call so no race on first call | Q2 | If wrong, first `to_thread` calls use the default ThreadPoolExecutor (max_workers=min(32, cpu+4)) — not catastrophic, just sub-optimal sizing. |
| A3 | WAL mode survives the first `initialize_db()` of a brownfield DB without explicit checkpoint | Pitfall 2, Q4 | SQLite docs say PRAGMA persists; if our test fails, planner adds `cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")` after the journal_mode statement. |
| A4 | Plugin authors can keep writing sync `input()` inside their sync methods because the orchestrator wraps the method call in `to_thread` | Q9 | If wrong (some asyncio behavior I haven't accounted for), the test `test_plugin_input_in_to_thread_does_not_block_loop` will catch it; remediation is to add an `await asyncio.to_thread(input, prompt)` helper plugins call instead. |
| A5 | Selector event loop on Windows is acceptable (we use no subprocess pipes) | Q6 | If a future phase uses `asyncio.create_subprocess_exec`, switch back to Proactor or use the SIGINT handler pattern. Phase 4 doesn't introduce subprocess use. |
| A6 | `app.delay` config field can be added to AppConfig without breaking Phase 1 schema strictness | Plan layout | Phase 1 D-07 says schema is `extra=forbid`; ADDING a defined field is fine (default value preserves backward compat); only adding undefined keys to config.yml breaks. |
| A7 | `purchase_writer` task crashing should be fatal to the bot (no defensive try/except) | Pitfall 10 | If wrong (we'd rather log and continue), wrap body in try/except but include retry-with-backoff to avoid hot loop on persistent SQLite corruption. |

## Open Questions

1. **Where does the polling cadence value live?**
   - CONTEXT.md says "polling cadence stays global, single `app.delay` in config for v1" but `AppConfig` does not currently have a `delay` field. Options:
     - (a) Add `app: AppSection` with `delay: float = 5.0` to `AppConfig`.
     - (b) Hardcode `POLL_DELAY = 5.0` as a constant in main.py.
   - Recommend (a) — config-driven; future-proof for ANTI-01 (Phase 6) which adds per-platform delays.
   - **Planner decision needed.**

2. **Add `app.delay` requires a `sample.config.yml` update.**
   - If we add it, sample config must show it. Probably a tiny doc edit, not a plan.

3. **Per-plugin `get_items_for_plugin` (Q8 option b) vs in-Python filter (option a)?**
   - For v1 scale (10-50 items) option (a) is fine. Plan should encode (a). If planner thinks otherwise, flag.

4. **Should the orchestrator monitor `purchase_writer` health and restart it?**
   - Pitfall 10 says NO — let crashes propagate. If the planner wants resiliency, this becomes a separate must-have. Recommend defer.

5. **Granularity of plan 04-05:** keep as one cohesive plan or split into 04-05a/04-05b?
   - Recommended: keep as one. Splitting creates an intermediate state where ASYNC-05 isn't yet met.

6. **Should `main()` install a SIGTERM handler in addition to SIGINT?**
   - Useful if anyone runs the bot under systemd/Docker. For v1 personal-use target, SIGINT only is fine. Defer to Phase 5/6.

## Sources

### Primary (HIGH confidence)
- Python 3.11 `asyncio.TaskGroup` — docs.python.org/3.11/library/asyncio-task.html#asyncio.TaskGroup
- Python `asyncio.to_thread` — docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
- Python `loop.set_default_executor` — docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.set_default_executor
- Python asyncio platform notes (Windows Proactor) — docs.python.org/3/library/asyncio-platforms.html#windows
- SQLite WAL — sqlite.org/wal.html
- SQLite PRAGMA busy_timeout — sqlite.org/pragma.html#pragma_busy_timeout
- pytest-asyncio 1.3.0 — pip index versions pytest-asyncio (verified 2026-05-14)
- Project files verified by direct read: `main.py`, `plugin_base.py`, `plugin_registry.py`, `models.py`, `config_schema.py`, `driver.py`, `credentials.py`, `logger.py`, `plugins/shopbot_plugin_amazon.py`, `plugins/shopbot_plugin_bestbuy.py`, `requirements.txt`, `.planning/config.json`, `.planning/phases/04-async-orchestrator/04-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md`

### Secondary (MEDIUM confidence)
- pytest-asyncio mode recommendation ("auto") — pytest-asyncio README

### Tertiary (LOW confidence)
- Windows chromedriver TCP-bind race — claimed in CONTEXT.md pitfall 7, not independently verified in this session. Treat as project lore; stagger is cheap insurance regardless.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib, versions verified.
- Architecture: HIGH — TaskGroup pattern is well-documented; isolation wrapper is standard idiom.
- SQLite WAL: HIGH — docs are clear; behavior in low-N concurrent regime is well-characterized.
- Pitfalls: HIGH (most) / MEDIUM (Windows SIGINT — depends on user's terminal).
- Test patterns: HIGH — pytest-asyncio auto mode is the standard new-project default.

**Research date:** 2026-05-14
**Valid until:** ~2026-08 (90 days; Python 3.11+ asyncio semantics are stable, pytest-asyncio 1.x is stable).
