# Phase 4: Async Orchestrator - Context

**Gathered:** 2026-05-12
**Status:** Ready for research and planning
**Source:** /gsd-discuss-phase 4 (interactive)

<domain>
## Phase Boundary

Phase 4 converts the blocking `while True` poll loop in `main.py` into a concurrent `asyncio.TaskGroup` that runs each plugin in its own task. Selenium calls stay synchronous and are bridged into the async loop via `asyncio.to_thread()` / a shared `ThreadPoolExecutor`. SQLite writes go through a single async write queue. All blocking `input()` calls become `asyncio.to_thread(input)`. A new `shutdown()` method on the plugin ABC ensures Chrome drivers exit cleanly on Ctrl-C.

Five in-scope requirements: ASYNC-01, ASYNC-02, ASYNC-03, ASYNC-04, ASYNC-05.

Out of scope (defer):
- Selenium → nodriver swap (D-01 below; defer to Phase 6 or a dedicated future phase)
- New platform plugins (Walmart, Target, GameStop, Square Enix, NewEgg) — Phase 6
- Notification system overhaul — Phase 5
- Per-plugin polling cadence (stays global, single `app.delay` in config for v1)
- Async logging (current sync logger is fine for expected N=2 plugins in v1; revisit if perf becomes an issue)

</domain>

<decisions>
## Implementation Decisions

### Driver runtime (ASYNC-01 supporting)

**D-01: Stay on Selenium for Phase 4. nodriver swap deferred.**
- Each plugin keeps its existing `self.driver = build_driver(...)` Selenium WebDriver instance from Phase 1/2.
- All Selenium calls inside plugin `check_availability`, `auto_buy`, `login`, `detect_captcha`, and `shutdown` get wrapped in `await asyncio.to_thread(...)` at the call sites in the orchestrator (or, optionally, plugins can be async-decorated and use `to_thread` internally — planner picks the cleaner pattern).
- A single shared `concurrent.futures.ThreadPoolExecutor` is set as the default executor in main() (`asyncio.get_event_loop().set_default_executor(...)`) sized to `max(4, len(plugins) * 2)` so OTP-blocked plugins don't starve other plugins.
- Rationale: Phase 4 is a control-flow refactor, not a driver swap. Two refactors in one phase compounds risk. nodriver migration becomes its own scoped effort (likely Phase 6 alongside new plugins, since new plugins benefit most from nodriver's anti-detection).
- Trade-off accepted: ThreadPoolExecutor overhead per call is acceptable for an N=2 plugin v1; nodriver's async-native model would reduce overhead but the savings don't justify the dual refactor right now.

### Blocking input() migration (ASYNC-03)

**D-02: Use `asyncio.to_thread(input, prompt)` for all OTP and confirmation prompts.**
- Amazon's `amz_sign_in` currently blocks on `input("Press Enter after OTP...")`. The new pattern is `await asyncio.to_thread(input, "Press Enter after OTP...")`.
- Other plugin tasks keep polling and detecting availability while the user types the OTP in the same terminal.
- No new dependencies (no `aioconsole`). Stdlib-only.
- Rationale: simplest pattern, works on Linux/Mac/Windows, no extra library to vendor, terminal UX is what users already expect.
- CAPTCHA pause is per-plugin local: when one plugin detects a CAPTCHA, only that plugin's task awaits the user; other plugin tasks continue. This is a deliberate change from the legacy blocking behavior where everything paused.

### Write-queue serialization (ASYNC-05)

**D-03: `asyncio.Queue` + single consumer task drains `update_item_purchased()` calls.**
- Module-level `purchase_queue: asyncio.Queue[tuple[str, ...]]` (item URL + any extra metadata).
- A dedicated `async def purchase_writer():` task runs alongside the plugin TaskGroup. It loops over `await queue.get()` and calls `await asyncio.to_thread(update_item_purchased, url)`.
- Plugins call `await purchase_queue.put((url,))` from their `auto_buy()` after the place-order confirmation, instead of calling `update_item_purchased()` directly.
- `Queue(maxsize=100)` to bound memory if writes back up (extremely unlikely at v1 scale).
- Rationale: one place to add retries, instrumentation, or batch logic later. Lower lock contention than per-call `asyncio.Lock`. SQLite WAL (ASYNC-04) handles the durability layer underneath.

### Async shutdown (new — supports ASYNC-01 cleanup guarantee)

**D-04: Amend `RetailerPlugin` ABC with `async def shutdown(self) -> None` (non-abstract, default implementation).**
- Default body: `await asyncio.to_thread(self.driver.quit)` so subclasses with no special cleanup just inherit correct behavior.
- Plugins with extra cleanup (e.g., async write queues, open file handles) override `shutdown` to add their own steps before/after `super().shutdown()`.
- Orchestrator catches `KeyboardInterrupt` / `asyncio.CancelledError` at the TaskGroup boundary in `main()` and runs `await asyncio.gather(*(p.shutdown() for p in registry), return_exceptions=True)` before exiting.
- `asyncio.shield` wraps each plugin's `shutdown()` call so a slow `driver.quit()` cannot be cancelled mid-flight.
- This is the third additive change to the Phase 1 ABC (after Phase 1 D-01 driver-arg drop and Phase 2 D-01 list[str] domain_pattern + login_at_startup). It is a non-breaking addition: existing Amazon and BestBuy plugins inherit the default and need no edits. `PLUGIN_API_VERSION` stays at 1.
- Tests: assert `RetailerPlugin.shutdown` exists, is a coroutine, default body calls `self.driver.quit` via `to_thread`. Each plugin's test file gets a `test_shutdown_quits_driver` mock-based check.

### Claude's Discretion

The planner / researcher decides:

- **Where ThreadPoolExecutor sizing happens** — main.py vs a small `concurrency.py` helper module. Pick whichever keeps main.py readable.
- **Plugin task error handling** — when a plugin task raises an unhandled exception inside the TaskGroup, the recommended pattern is to log it via writeLog, cancel that one plugin's task, and let TaskGroup continue running the others. Plan should encode this as a per-plugin try/except wrapper inside the orchestrator, not inside each plugin.
- **Polling cadence** — stays global (`app.delay` in AppConfig). Per-plugin cadence is a v2 idea unless the planner discovers it's free to add.
- **Logging concurrency safety** — current `writeLog` writes to stdout + a daily file. Under N=2 concurrent plugins this is fine on POSIX; if Windows file-locking becomes an issue, the planner can add a `threading.Lock` around the file write. Don't preemptively add an async logger.
- **Test patterns for async code** — `pytest-asyncio` will be required (new dev dependency). Pin it in requirements.txt.
- **Stagger implementation** (ASYNC-02 — 1.5s between plugin startups) — `await asyncio.sleep(1.5 * index)` inside each task before constructing the driver, OR sequential discovery with `await asyncio.sleep(1.5)` between instantiations in `plugin_registry.discover()`. Planner picks; second option keeps the orchestrator simpler.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1-3 outputs (locked contracts)
- `plugin_base.py` — RetailerPlugin ABC with `PLUGIN_API_VERSION = 1`, `domain_pattern: list[str]`, `login_at_startup: bool`. Phase 4 D-04 adds `async def shutdown()` (non-abstract).
- `plugin_registry.py` — `discover()`, `route_url()`, `verify_coverage()` from Phase 2. Phase 4 may add `async def discover_async()` or amend `discover()` to await between plugin instantiations for the stagger.
- `config_schema.py` — AppConfig Pydantic shape. May need a new `app.max_concurrent_plugins` field or similar; planner decides.
- `driver.py` — `build_driver(driver_path, log_path)`. Unchanged this phase.
- `credentials.py` — `collect_cvvs(app_config)`. Called once at startup, unchanged.
- `logger.py` — `writeLog`, `configure`. Used as-is.
- `models.py` — `update_item_purchased`, `add_items`, `get_items`. The write queue in D-03 wraps `update_item_purchased`. `add_items` is a one-time startup call so it stays synchronous.
- `main.py` — the entrypoint Phase 2 wired up. Phase 4 rewrites `main()` as `async def main()` and replaces the `while True` body with the TaskGroup orchestrator.
- `plugins/shopbot_plugin_amazon.py` and `shopbot_plugin_bestbuy.py` — existing Phase 2 plugins. May need light edits if their internal `input()` calls or sync method bodies need to be awaited.

### Project decisions
- `.planning/PROJECT.md` — concurrency design (asyncio.TaskGroup + ThreadPoolExecutor, one driver per plugin, 1.5s stagger)
- `.planning/REQUIREMENTS.md` — ASYNC-01 through ASYNC-05 wording (authoritative for must_haves)
- `.planning/phases/01-foundations-security/01-CONTEXT.md` — Phase 1 D-01 (no driver param on ABC)
- `.planning/phases/02-plugin-migration/02-CONTEXT.md` — Phase 2 D-01..D-04 (registry, hard-cut, login lifecycle, two-phase load)
- `.planning/phases/02-plugin-migration/02-RESEARCH.md` — RetailerPlugin contract details, plugin testing patterns

### New dependency
- `pytest-asyncio` — required for async test patterns; pin in requirements.txt

</canonical_refs>

<specifics>
## Specific Implementation Notes

### Target main() shape (rough sketch — planner refines)

```
async def main():
    args = parse_args()
    app_config = AppConfig(...)
    configure_logger(app_config.debug.logging_level)
    cvvs = await asyncio.to_thread(collect_cvvs, app_config)
    app_config.selenium.driver_path = get_chromedriver_path(...)

    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=max(4, len(...))))

    registry = await discover_async(Path("plugins"), app_config, cvvs)
    verify_coverage(registry, app_config.available.items)

    initialize_db()
    add_items([(it.name, it.link, it.auto_buy, it.quantity, False)
               for it in app_config.available.items])

    purchase_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    for plugin in registry:
        if plugin.login_at_startup:
            await asyncio.to_thread(plugin.login, app_config)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(purchase_writer(purchase_queue))
            for plugin in registry:
                tg.create_task(poll_plugin(plugin, app_config, purchase_queue))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await asyncio.gather(
            *(asyncio.shield(p.shutdown()) for p in registry),
            return_exceptions=True,
        )
```

### `poll_plugin` shape

```
async def poll_plugin(plugin, app_config, queue):
    while True:
        for item in get_items_for_plugin(plugin):
            try:
                available = await asyncio.to_thread(plugin.check_availability, item.link)
                if not available:
                    continue
                play_available_sound()
                if item.auto_buy:
                    await asyncio.to_thread(plugin.auto_buy, item.link, app_config)
                    play_buy_sound()
                    await queue.put((item.link,))
            except Exception as e:
                writeLog(f"{plugin.name}: {e}", "ERROR")
        await asyncio.sleep(app_config.app.delay)
```

### `purchase_writer` shape

```
async def purchase_writer(queue):
    while True:
        url, *_ = await queue.get()
        try:
            await asyncio.to_thread(update_item_purchased, url)
        except Exception as e:
            writeLog(f"Write failed for {url}: {e}", "ERROR")
        finally:
            queue.task_done()
```

### Pitfalls to encode as must_haves

1. `await asyncio.to_thread(plugin.driver.quit)` not `plugin.driver.quit()` directly — Selenium's quit can block for seconds on driver hang.
2. ThreadPoolExecutor must be set BEFORE the TaskGroup starts; setting it inside causes the first to_thread calls to use the default fixed-size pool.
3. `asyncio.shield` around shutdown() prevents Ctrl-C-during-shutdown from leaving zombie chromedriver.exe processes (a real Windows problem).
4. `asyncio.Queue.task_done()` must be called even on write failure or `queue.join()` hangs forever.
5. SQLite connections cannot be shared across threads. `update_item_purchased` opens its own connection each call (current behavior) — verify this is still the case before ASYNC-04 WAL changes land.
6. `KeyboardInterrupt` on Windows requires `asyncio.WindowsProactorEventLoopPolicy` or explicit `signal.signal(signal.SIGINT, ...)` to propagate into asyncio cleanly.
7. The 1.5s stagger MUST happen BEFORE `build_driver` is called for each plugin, not after, or the port conflict can still hit during the chromedriver TCP bind window.

</specifics>

<deferred>
## Deferred Ideas

- nodriver swap — likely Phase 6 alongside new platforms (D-01 trade-off accepted)
- Per-plugin polling cadence — v2 if a use case appears
- Async logging — only if the current sync writer becomes a bottleneck (unlikely at N=2 plugins)
- Web UI / system-tray OTP signaling — terminal `input()` via `to_thread` is fine for v1
- Plugin task auto-restart on crash — for v1, crashed plugin task is logged and skipped; user restarts the bot
- aioconsole / native async stdin — not worth the dependency
- Plugin priority / weighted polling — out of scope; all plugins polled at the same cadence

</deferred>

*Phase: 04-async-orchestrator*
*Context gathered: 2026-05-12 via /gsd-discuss-phase 4*
