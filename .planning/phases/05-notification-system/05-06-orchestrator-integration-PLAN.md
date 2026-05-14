---
phase: 05-notification-system
plan: 06
type: execute
wave: 2
depends_on: ["01", "02", "03", "04", "05"]
files_modified:
  - main.py
  - tests/test_notification_writer.py
  - tests/test_orchestrator.py
autonomous: true
requirements:
  - NOTIF-01
  - NOTIF-02
tags:
  - python
  - asyncio
  - taskgroup
  - orchestrator
  - notification
  - fan-out
  - integration
  - wave-2

must_haves:
  truths:
    - "main.py defines `async def notification_writer(queue: asyncio.Queue, notifiers: list[Notifier], restock_window_seconds: int) -> None` mirroring purchase_writer (D-03)"
    - "notification_writer drains `await queue.get()` in a `while True` loop; the outer loop has NO try/except wrapper — a crash here is FATAL by design (mirrors Phase 4 Pitfall 4-10 + RESEARCH Q11.2)"
    - "Inner body wraps event processing in try/except/finally; `queue.task_done()` is called in the `finally` block (CONTEXT pitfall #8 + RESEARCH Q11.4)"
    - "For events with `action == 'detected'`, notification_writer calls `await asyncio.to_thread(should_notify, event.url, restock_window_seconds)`; if False, the event is dropped (continue) and `task_done` still fires in finally"
    - "For events with `action == 'purchased'`, notification_writer SKIPS the should_notify gate entirely (RESEARCH Q8 + Q11.14). Purchased events always fan out"
    - "Fan-out uses `await asyncio.gather(*(n.send(event) for n in [x for x in notifiers if x.enabled]), return_exceptions=True)` — per-notifier exceptions are NEVER propagated (NOTIF-01 isolation + RESEARCH Q11.3)"
    - "After gather, notification_writer iterates `zip(active, results)` and for each `Exception` instance logs `writeLog(f\"notifier {n.name} failed on {event.url}: {r}\", \"ERROR\")` — every failure logged with notifier name + event URL"
    - "After successful detected-event fan-out, notification_writer calls `await asyncio.to_thread(mark_notified, event.url)` wrapped in its own try/except: mark_notified failures log ERROR and continue, NEVER crash the writer (CONTEXT pitfall #1 + RESEARCH Q11.17)"
    - "Purchased events do NOT call mark_notified (RESEARCH Q8 + Q11.14)"
    - "main.py adds `notification_queue: asyncio.Queue = asyncio.Queue(maxsize=200)` next to the existing purchase_queue (D-03 maxsize)"
    - "main.py calls `notifiers = await discover_notifiers(Path('notifiers'), app_config=app_config)` after the existing `discover_async(Path('plugins'), ...)` call"
    - "main.py TaskGroup adds `tg.create_task(notification_writer(notification_queue, notifiers, app_config.notifications.restock_window_seconds))` after the existing purchase_writer task"
    - "poll_plugin signature widens to accept `notification_queue` as a keyword arg (or positional after purchase_queue); _poll_once signature widens to accept it; _attempt_purchase signature widens to accept it AND the item name (RESEARCH O-3)"
    - "_poll_once enqueues `NotificationEvent(item_name=name, url=link, platform=plugin.name, timestamp=datetime.now(timezone.utc), action='detected')` via `await notification_queue.put(...)` AFTER `available=True` is confirmed (RESEARCH Q7 event creation site)"
    - "_attempt_purchase enqueues `NotificationEvent(item_name=name, url=link, platform=plugin.name, timestamp=datetime.now(timezone.utc), action='purchased')` AFTER successful auto_buy and AFTER the purchase_queue.put call"
    - "NotificationEvent timestamps use `datetime.now(timezone.utc)` (tz-aware UTC). NEVER `datetime.now()` (tz-naive) — CONTEXT pitfall #9 + RESEARCH Q11.8. Verified via AST grep: every `NotificationEvent(...)` Call in main.py has a `timestamp` keyword whose value is a Call to `datetime.now` with at least one argument (timezone.utc)"
    - "The inline `play_available_sound()` call in main._poll_once is REMOVED (sound notifier owns it now); inline `play_buy_sound()` in main._attempt_purchase is REMOVED. CONTEXT pitfall + RESEARCH Q11.15: otherwise sounds fire twice per event. Verified by AST grep: `play_available_sound`/`play_buy_sound` no longer appear in main.py"
    - "main.py finally-block shutdown extends to await both plugins AND notifiers: `await asyncio.gather(*(asyncio.shield(p.shutdown()) for p in registry), *(asyncio.shield(n.shutdown()) for n in notifiers), return_exceptions=True)` (RESEARCH Q10.5)"
    - "All RED tests in tests/test_notification_writer.py from Plan 05-01 flip to GREEN"
    - "tests/test_orchestrator.py gains new assertions: inline play_*_sound removed, notification_writer is in the TaskGroup, NotificationEvent uses tz-aware UTC timestamps"
    - "Full pytest suite remains green across Phase 1/2/3/4/5"
  artifacts:
    - path: "main.py"
      provides: "Async orchestrator extended with notification_queue + notification_writer + NotificationEvent put sites + shutdown extension"
      contains: "async def notification_writer"
      min_lines: 200
    - path: "tests/test_notification_writer.py"
      provides: "GREEN tests for NOTIF-01 (fan-out, isolation, task_done in finally) + dedup gating + purchased bypasses dedup"
    - path: "tests/test_orchestrator.py"
      provides: "Extended Phase 4 GREEN tests with Phase 5 assertions (no inline play_*_sound, notification_writer in TaskGroup, tz-aware timestamps)"
  key_links:
    - from: "main.main"
      to: "discover_notifiers"
      via: "await discover_notifiers(Path('notifiers'), app_config=app_config)"
      pattern: "await\\s+discover_notifiers"
    - from: "main.main TaskGroup"
      to: "notification_writer"
      via: "tg.create_task(notification_writer(...))"
      pattern: "create_task\\(notification_writer"
    - from: "main._poll_once"
      to: "notification_queue.put"
      via: "after available=True"
      pattern: "notification_queue\\.put"
    - from: "main._attempt_purchase"
      to: "notification_queue.put"
      via: "after auto_buy + purchase_queue.put"
      pattern: "notification_queue\\.put"
    - from: "main.notification_writer"
      to: "asyncio.gather"
      via: "return_exceptions=True fan-out"
      pattern: "gather\\(.*return_exceptions\\s*=\\s*True"
    - from: "main.notification_writer"
      to: "models.should_notify / models.mark_notified"
      via: "asyncio.to_thread wrap"
      pattern: "to_thread\\(should_notify\\|to_thread\\(mark_notified"
    - from: "main.main finally"
      to: "asyncio.shield(n.shutdown())"
      via: "extends Phase 4 shutdown to notifiers"
      pattern: "asyncio\\.shield.*shutdown.*for n in notifiers"
---

<objective>
Wave 2 integration: wire the Plan 05-01 foundation + the four Wave 1 notifiers into `main.py`. Add a module-level `notification_queue`; discover notifiers at startup via `discover_notifiers`; add `notification_writer` to the TaskGroup as a critical task (mirrors `purchase_writer`); emit `NotificationEvent` from `_poll_once` (action="detected") and `_attempt_purchase` (action="purchased"); remove the inline `play_*_sound` calls (sound notifier owns them now); extend the shutdown gather to include notifiers under `asyncio.shield`. Flip the remaining RED tests in `tests/test_notification_writer.py` to GREEN and extend `tests/test_orchestrator.py` with Phase 5 assertions.

Purpose: This is the final Phase 5 plan. After this lands, the bot fans out stock alerts across all four channels concurrently, isolates per-channel failures, dedupes detected events per `restock_window_seconds`, ALWAYS fires purchased events, and cleans up notifiers under shield on Ctrl-C. The phase exit criteria from the roadmap ("misconfigured Discord does not crash or block other channels"; "one notification per restock event, not per poll tick"; "embed includes name/URL/platform/timestamp/action"; "SMS opt-in") all become testable here.

Output: extended main.py + GREEN tests/test_notification_writer.py + extended tests/test_orchestrator.py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/05-notification-system/05-CONTEXT.md
@.planning/phases/05-notification-system/05-RESEARCH.md
@.planning/phases/05-notification-system/05-01-foundation-and-red-skeletons-PLAN.md
@.planning/phases/05-notification-system/05-02-registry-and-sound-notifier-PLAN.md
@.planning/phases/05-notification-system/05-03-discord-notifier-PLAN.md
@.planning/phases/05-notification-system/05-04-email-notifier-PLAN.md
@.planning/phases/05-notification-system/05-05-sms-notifier-two-lock-PLAN.md
@.planning/phases/04-async-orchestrator/04-05-async-main-orchestrator-PLAN.md
@.planning/phases/04-async-orchestrator/04-05-SUMMARY.md
@main.py
@notifier_base.py
@notifier_registry.py
@models.py
@config_schema.py
@logger.py
@tests/conftest.py
@tests/test_notification_writer.py
@tests/test_orchestrator.py
</context>

<interfaces>
Target additions to `main.py` (insert near purchase_writer; do not duplicate Phase 4 code):

```python
# Additional imports at top of main.py
from datetime import datetime, timezone
from notifier_base import NotificationEvent, Notifier
from notifier_registry import discover_notifiers
from models import should_notify, mark_notified


async def notification_writer(
    queue: asyncio.Queue,
    notifiers: list[Notifier],
    restock_window_seconds: int,
) -> None:
    """Single consumer for fan-out notification dispatch (NOTIF-01).

    Mirrors purchase_writer. A crash here is FATAL by design (Phase 4 Pitfall
    4-10). Per-notifier exceptions isolated via gather(return_exceptions=True).
    Dedup check + mark_notified happen INSIDE this writer for the detected
    action (single-writer eliminates race). Purchased events bypass dedup.
    """
    while True:
        event = await queue.get()
        try:
            if event.action == "detected":
                allowed = await asyncio.to_thread(
                    should_notify, event.url, restock_window_seconds
                )
                if not allowed:
                    continue
            active = [n for n in notifiers if n.enabled]
            results = await asyncio.gather(
                *(n.send(event) for n in active),
                return_exceptions=True,
            )
            for n, r in zip(active, results):
                if isinstance(r, Exception):
                    writeLog(
                        f"notifier {n.name} failed on {event.url}: {r}",
                        "ERROR",
                    )
            if event.action == "detected":
                try:
                    await asyncio.to_thread(mark_notified, event.url)
                except Exception as e:
                    writeLog(
                        f"mark_notified failed for {event.url}: {e}",
                        "ERROR",
                    )
        finally:
            queue.task_done()
```

Modifications to `main._poll_once` (preserving Phase 4 shape, with surgical Phase 5 changes):

```python
async def _poll_once(
    plugin, app_config, purchase_queue, notification_queue, openBrowser,
) -> None:
    items = await asyncio.to_thread(get_items)
    for name, link, autoBuy, _qty, purchased in items:
        if purchased:
            continue
        matched = route_url(link, [plugin])
        if matched is None:
            continue
        try:
            available = await asyncio.to_thread(plugin.check_availability, link)
        except Exception as e:
            writeLog(
                f"{plugin.name}: check_availability raised on {link}: {e}",
                "ERROR",
            )
            continue
        if not available:
            continue
        # DELETED: play_available_sound()   (sound notifier owns this now)
        writeLog(f"{name} is available: {make_tiny(link)}", "SUCCESS")
        await notification_queue.put(NotificationEvent(
            item_name=name,
            url=link,
            platform=plugin.name,
            timestamp=datetime.now(timezone.utc),
            action="detected",
        ))
        if autoBuy:
            await _attempt_purchase(
                plugin, link, name, app_config, purchase_queue, notification_queue,
            )
        elif openBrowser:
            webbrowser.open(link)
```

Modifications to `main._attempt_purchase`:

```python
async def _attempt_purchase(
    plugin, link, name, app_config, purchase_queue, notification_queue,
) -> None:
    try:
        await asyncio.to_thread(plugin.auto_buy, link, app_config)
        # DELETED: play_buy_sound()    (sound notifier owns this now)
        await purchase_queue.put((link,))
        await notification_queue.put(NotificationEvent(
            item_name=name,
            url=link,
            platform=plugin.name,
            timestamp=datetime.now(timezone.utc),
            action="purchased",
        ))
    except Exception as e:
        writeLog(
            f"{plugin.name}: auto_buy raised on {link}: {e}",
            "ERROR",
        )
```

Modifications to `main.poll_plugin` (widen signature):

```python
async def poll_plugin(
    plugin, app_config, purchase_queue, notification_queue, stop_event,
) -> None:
    openBrowser = app_config.open_browser
    delay = app_config.app.delay
    while not stop_event.is_set():
        try:
            await _poll_once(
                plugin, app_config, purchase_queue, notification_queue, openBrowser,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            writeLog(f"{plugin.name}: unexpected error: {e}", "ERROR")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass
```

Modifications to `main.main` (add notifier discovery + queue + writer + shutdown extension):

```python
async def main() -> None:
    # ... existing AppConfig load + logger configure + cvvs + chromedriver path ...
    registry = await discover_async(
        Path("plugins"), app_config=app_config, cvvs=cvvs,
    )
    verify_coverage(registry, app_config.available.items)
    notifiers = await discover_notifiers(
        Path("notifiers"), app_config=app_config,
    )

    # ... existing ThreadPoolExecutor + login + seed_items ...

    purchase_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    notification_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    stop_event = asyncio.Event()
    _install_signal_handler(stop_event)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(purchase_writer(purchase_queue))
            tg.create_task(notification_writer(
                notification_queue,
                notifiers,
                app_config.notifications.restock_window_seconds,
            ))
            for plugin in registry:
                tg.create_task(poll_plugin(
                    plugin, app_config, purchase_queue, notification_queue, stop_event,
                ))
    except* KeyboardInterrupt:
        pass
    except* asyncio.CancelledError:
        pass
    finally:
        writeLog("Shutting down plugins and notifiers", "INFO")
        await asyncio.gather(
            *(asyncio.shield(p.shutdown()) for p in registry),
            *(asyncio.shield(n.shutdown()) for n in notifiers),
            return_exceptions=True,
        )
        executor.shutdown(wait=True, cancel_futures=False)
        writeLog("ShopPyBot stopped cleanly", "INFO")
```

Top-of-file import deletion: remove `from utils import play_available_sound, play_buy_sound` (no longer referenced after the inline removals).
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add notification_writer + notification_queue + NotificationEvent put sites to main.py; remove inline play_*_sound</name>
  <files>main.py</files>
  <read_first>
    - main.py (full current Phase 4 state; locate purchase_writer, _poll_once, _attempt_purchase, poll_plugin, main, _shutdown logic)
    - notifier_base.py (NotificationEvent dataclass shape)
    - notifier_registry.py (discover_notifiers signature)
    - models.py (should_notify, mark_notified signatures)
    - config_schema.py (AppConfig.notifications.restock_window_seconds path)
    - .planning/phases/04-async-orchestrator/04-05-async-main-orchestrator-PLAN.md (Phase 4 main.py shape — preserve everything not explicitly changed here)
    - .planning/phases/05-notification-system/05-RESEARCH.md Q10 (Phase 4 integration touchpoints — full enumeration)
  </read_first>
  <behavior>
    - `from main import notification_writer; inspect.iscoroutinefunction(notification_writer) is True`.
    - notification_writer's outer `while True` has NO try/except wrapper at the loop level (AST verified: walk for the function's While node, assert its body is `[Assign(get), Try(...)]` not `[Try(While(...))]`).
    - The Try inside notification_writer has a `finally` block calling `queue.task_done()`.
    - For action="detected", notification_writer calls `should_notify` via to_thread; for action="purchased", it does NOT call should_notify.
    - notification_writer calls `mark_notified` via to_thread ONLY for action="detected"; AST verified (walk the function for the mark_notified Call and assert it appears inside an `if event.action == "detected":` block).
    - Fan-out uses `asyncio.gather(..., return_exceptions=True)` — AST verified.
    - After gather, results are iterated with `zip(active, results)` and each Exception is logged via writeLog with the notifier name AND event URL.
    - main.py imports `NotificationEvent`, `Notifier`, `discover_notifiers`, `should_notify`, `mark_notified`, `datetime`, `timezone`.
    - main.py defines `notification_queue: asyncio.Queue = asyncio.Queue(maxsize=200)` inside `main()`.
    - main.py's TaskGroup contains exactly one `notification_writer(...)` create_task call AND that call is positioned AFTER `purchase_writer(...)`.
    - poll_plugin signature accepts `notification_queue` (positional or keyword).
    - _poll_once enqueues a NotificationEvent with action="detected" AFTER the `if not available: continue` check.
    - _attempt_purchase enqueues a NotificationEvent with action="purchased" AFTER `purchase_queue.put((link,))`.
    - All four NotificationEvent constructor calls in main.py use `timestamp=datetime.now(timezone.utc)` — AST verified by walking for Call(NotificationEvent) and checking the timestamp keyword is a Call to `datetime.now` with at least one positional/keyword arg referencing `timezone.utc` or `tz=timezone.utc`.
    - main.py contains ZERO calls to `play_available_sound` or `play_buy_sound` — AST grep verified. The `from utils import play_available_sound, play_buy_sound` import is removed.
    - The shutdown finally-block gather call includes BOTH `asyncio.shield(p.shutdown()) for p in registry` AND `asyncio.shield(n.shutdown()) for n in notifiers` (single gather, two starred generators).
    - mark_notified failure (monkeypatched to raise) does NOT crash notification_writer — the inner try/except catches it, logs ERROR, queue.task_done still fires in the outer finally.
    - Phase 4 behavior preserved: purchase_writer still exists unchanged; Windows event loop policy unchanged; SIGINT handler unchanged; executor sizing unchanged.
  </behavior>
  <action>
    1. Read `main.py` in full. Identify the exact insertion points: top imports, after purchase_writer (insert notification_writer), inside _poll_once (modify), inside _attempt_purchase (modify signature + add put), inside poll_plugin (widen signature), inside main (add discover_notifiers, notification_queue, TaskGroup additions, shutdown extension).

    2. **Imports.** At the top of main.py:
       - Add `from datetime import datetime, timezone`
       - Add `from notifier_base import NotificationEvent, Notifier`
       - Add `from notifier_registry import discover_notifiers`
       - Add `from models import should_notify, mark_notified` (extend the existing models import line)
       - REMOVE `from utils import play_available_sound, play_buy_sound` (both unused after this plan)

    3. **notification_writer.** Insert the `notification_writer` async function immediately after the existing `purchase_writer` function. Copy the body from <interfaces> exactly. Keep the docstring naming Phase 4 Pitfall 4-10 + NOTIF-01.

    4. **_poll_once.** Modify in place:
       - Widen signature to `(plugin, app_config, purchase_queue, notification_queue, openBrowser)`.
       - Delete the `play_available_sound()` line.
       - After the `writeLog(f"{name} is available...")` line, insert the `await notification_queue.put(NotificationEvent(...))` with action="detected" per <interfaces>.
       - Update the `_attempt_purchase` call to pass `purchase_queue` and `notification_queue`.

    5. **_attempt_purchase.** Modify in place:
       - Widen signature to `(plugin, link, name, app_config, purchase_queue, notification_queue)`.
       - Delete the `play_buy_sound()` line.
       - After `await purchase_queue.put((link,))`, insert `await notification_queue.put(NotificationEvent(...))` with action="purchased".

    6. **poll_plugin.** Widen signature to `(plugin, app_config, purchase_queue, notification_queue, stop_event)`. Update the internal `await _poll_once(...)` call to pass `notification_queue`.

    7. **main.** Edits inside `async def main()`:
       - After the existing `verify_coverage(registry, app_config.available.items)` line, add `notifiers = await discover_notifiers(Path("notifiers"), app_config=app_config)`.
       - After the existing `purchase_queue` line, add `notification_queue: asyncio.Queue = asyncio.Queue(maxsize=200)`.
       - Inside the `async with asyncio.TaskGroup() as tg:` block, after the existing `tg.create_task(purchase_writer(purchase_queue))` line, add `tg.create_task(notification_writer(notification_queue, notifiers, app_config.notifications.restock_window_seconds))`.
       - Update the `poll_plugin` task creation to pass `notification_queue`.
       - In the `finally:` block, REPLACE the existing single gather over `registry` shutdowns with a single gather over BOTH `registry` shutdowns and `notifiers` shutdowns (use two starred generators in the same gather call as shown in <interfaces>).
       - Update the `writeLog("Shutting down plugins"...)` line to `writeLog("Shutting down plugins and notifiers", "INFO")`.

    8. Run `rtk pytest -x -q tests/test_orchestrator.py tests/test_purchase_writer.py tests/test_main_smoke.py` — Phase 4 tests must STILL pass (poll_plugin / purchase_writer behavior preserved; only signatures widened with optional-to-keyword params if needed for test backcompat). If Phase 4 tests break due to signature widening, update them to pass a stub notification_queue (acceptable test-side adjustment, NOT a behavior change).

    9. Run `rtk pytest -x -q tests/test_notification_writer.py` — these MUST be RED before this task lands and GREEN after (Task 2 verifies; this task makes them runnable).

    10. AST self-check before finishing:
        - `rtk grep -n "play_available_sound\|play_buy_sound" main.py` returns ZERO matches.
        - `rtk grep -n "notification_queue" main.py` returns the put sites + TaskGroup setup.
        - `rtk grep -n "datetime.now(timezone.utc)" main.py` matches at least the two NotificationEvent timestamp sites.
  </action>
  <verify>
    <automated>python -c "import inspect; from main import notification_writer; assert inspect.iscoroutinefunction(notification_writer)"</automated>
    <automated>rtk grep -c "play_available_sound\|play_buy_sound" main.py</automated>
    <automated>rtk grep -n "await notification_queue.put" main.py</automated>
    <automated>rtk grep -n "datetime.now(timezone.utc)" main.py</automated>
    <automated>rtk grep -n "tg.create_task(notification_writer" main.py</automated>
    <automated>rtk grep -n "asyncio.shield" main.py</automated>
    <automated>rtk pytest -x -q tests/test_orchestrator.py tests/test_purchase_writer.py tests/test_main_smoke.py</automated>
  </verify>
  <acceptance_criteria>
    - notification_writer coroutine exists in main.py with the contract from <interfaces>
    - notification_queue created with maxsize=200 inside main()
    - notification_writer added to TaskGroup AFTER purchase_writer
    - poll_plugin / _poll_once / _attempt_purchase signatures widened to thread notification_queue
    - NotificationEvent put sites present in _poll_once (detected) and _attempt_purchase (purchased)
    - All NotificationEvent timestamps use datetime.now(timezone.utc)
    - Zero references to play_available_sound or play_buy_sound in main.py
    - main shutdown gather covers BOTH plugins AND notifiers under asyncio.shield
    - Phase 4 test suite (test_orchestrator.py / test_purchase_writer.py / test_main_smoke.py) still passes
  </acceptance_criteria>
  <done>main.py extended with notification fan-out. Test suite remains green; tests/test_notification_writer.py is now runnable (Task 2 drives it to GREEN).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Flip test_notification_writer to GREEN; extend test_orchestrator with Phase 5 assertions</name>
  <files>tests/test_notification_writer.py, tests/test_orchestrator.py</files>
  <read_first>
    - main.py (Task 1 just landed)
    - tests/test_notification_writer.py (RED tests from Plan 05-01)
    - tests/test_orchestrator.py (existing Phase 4 GREEN tests; insertion point for Phase 5 assertions)
    - tests/conftest.py (fakeNotifierFactory + appConfigStub + tmpDbPath)
    - .planning/phases/05-notification-system/05-RESEARCH.md Q11 (numbered must_haves driving test assertions)
  </read_first>
  <behavior>
    - All RED tests in tests/test_notification_writer.py from Plan 05-01 now PASS:
      - test_notificationWriterIsAsyncCoroutine: passes (Task 1 ships notification_writer).
      - test_oneFailedNotifierDoesNotBlockOthers: build two fakeNotifierFactory instances — one raising RuntimeError on send, one recording. Put one detected event on a queue. Monkeypatch should_notify to return True. Spawn the writer as a task; wait until queue.empty() (or queue.join with timeout 1s); assert the recording notifier's sendCalls == 1 AND the writer task is not done (still running, no exception); cancel + await the task. PASS.
      - test_purchasedActionBypassesDedup: monkeypatch should_notify to ALWAYS return False; put a NotificationEvent(action="purchased") on the queue; assert the fakeNotifier records the call (dedup gate skipped) AND mark_notified was NOT called (purchased never marks). PASS.
      - test_taskDoneCalledInFinally: monkeypatch should_notify to raise RuntimeError; put one event; assert queue.join() returns within 1s — proves task_done fired in the outer finally even though the inner check raised. PASS.
    - tests/test_orchestrator.py gains the following new tests (extend, do not replace):
      - test_noInlineSoundCalls: ast.parse main.py; walk for Name nodes 'play_available_sound' and 'play_buy_sound'; assert ZERO matches.
      - test_notificationWriterInTaskGroup: ast.parse main.py; locate the TaskGroup block; assert one of its create_task calls passes notification_writer as the target.
      - test_notificationEventTimestampsTzAware: ast.parse main.py; for each Call to NotificationEvent, locate the `timestamp` keyword; assert its value is a Call where func is `datetime.now` AND at least one arg matches `timezone.utc` (either positional or kwarg `tz=`).
      - test_mainImportsDiscoverNotifiers: ast.parse main.py; assert `from notifier_registry import discover_notifiers` (or equivalent) appears.
      - test_shutdownGathersNotifiers: ast.parse main.py; locate the asyncio.gather call inside the finally block; assert its starred args contain a generator over `notifiers`.
    - The new orchestrator tests do NOT actually run main(); they are pure AST assertions over the file (fast, deterministic).
    - Full pytest suite is GREEN: Phase 1/2/3/4 unchanged plus all Phase 5 RED files now GREEN.
  </behavior>
  <action>
    1. Open `tests/test_notification_writer.py`. Replace the RED skeleton tests with GREEN implementations that actually exercise notification_writer:
       - Import: `from main import notification_writer`, `from notifier_base import NotificationEvent`, `from datetime import datetime, timezone`.
       - Use `fakeNotifierFactory` fixture to build the failing + succeeding pair.
       - Use `monkeypatch.setattr("main.should_notify", lambda *a, **kw: <controlled>)` and `monkeypatch.setattr("main.mark_notified", lambda *a, **kw: <controlled>)` to control dedup behavior in tests.
       - Each test spawns `notification_writer` as an asyncio.create_task with a small queue (maxsize=10); puts events; uses `asyncio.wait_for(queue.join(), timeout=2.0)` to drain; then `task.cancel(); await asyncio.gather(task, return_exceptions=True)` to clean up.
       - The four tests: notificationWriterIsAsyncCoroutine (Task 1 verification), oneFailedNotifierDoesNotBlockOthers (NOTIF-01), purchasedActionBypassesDedup (NOTIF-02 carve-out), taskDoneCalledInFinally (pitfall #8).
       - Add one MORE regression test: test_markNotifiedFailureLoggedNotCrashed — monkeypatch mark_notified to raise, queue a detected event with should_notify True; assert the writer keeps running (task not done) AND writeLog was called with "mark_notified failed" substring.

    2. Open `tests/test_orchestrator.py`. APPEND new tests (do not modify Phase 4 tests). Use ast-based assertions:
       ```python
       import ast
       
       def _read_main_ast():
           return ast.parse(open("main.py").read())
       
       def test_noInlineSoundCalls():
           tree = _read_main_ast()
           names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
           assert "play_available_sound" not in names
           assert "play_buy_sound" not in names
       
       def test_notificationWriterInTaskGroup():
           tree = _read_main_ast()
           # Walk for any Call where func.attr == "create_task" and the arg is a Call to a Name "notification_writer"
           found = False
           for node in ast.walk(tree):
               if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "create_task":
                   if node.args and isinstance(node.args[0], ast.Call):
                       called = node.args[0].func
                       if isinstance(called, ast.Name) and called.id == "notification_writer":
                           found = True
                           break
           assert found, "notification_writer not added to TaskGroup"
       
       def test_notificationEventTimestampsTzAware():
           tree = _read_main_ast()
           for node in ast.walk(tree):
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "NotificationEvent":
                   ts = next((kw for kw in node.keywords if kw.arg == "timestamp"), None)
                   assert ts is not None
                   v = ts.value
                   assert isinstance(v, ast.Call)
                   # datetime.now(timezone.utc) or datetime.now(tz=timezone.utc)
                   func_name = ""
                   if isinstance(v.func, ast.Attribute):
                       func_name = v.func.attr
                   assert func_name == "now"
                   has_utc = any(
                       (isinstance(a, ast.Attribute) and a.attr == "utc")
                       for a in (v.args + [kw.value for kw in v.keywords])
                   )
                   assert has_utc, f"NotificationEvent timestamp not tz-aware UTC"
       
       def test_mainImportsDiscoverNotifiers():
           tree = _read_main_ast()
           ok = any(
               isinstance(n, ast.ImportFrom)
               and n.module == "notifier_registry"
               and any(a.name == "discover_notifiers" for a in n.names)
               for n in ast.walk(tree)
           )
           assert ok
       
       def test_shutdownGathersNotifiers():
           src = open("main.py").read()
           assert "for n in notifiers" in src or "for n in self.notifiers" in src
           assert "asyncio.shield" in src
       ```

    3. Run `rtk pytest -q tests/test_notification_writer.py tests/test_orchestrator.py`. All GREEN.

    4. Run the FULL Phase 5 + Phase 4 suite: `rtk pytest -q tests/test_notifier_base.py tests/test_models_notification_dedup.py tests/test_notifier_registry.py tests/test_notification_writer.py tests/test_notifiers_sound.py tests/test_notifiers_discord.py tests/test_notifiers_email.py tests/test_notifiers_sms.py tests/test_orchestrator.py tests/test_purchase_writer.py tests/test_main_smoke.py tests/test_registry_stagger.py tests/test_models_wal.py tests/test_plugin_shutdown.py`. All GREEN.

    5. Run the FULL suite: `rtk pytest -q`. All GREEN.
  </action>
  <verify>
    <automated>rtk pytest -q tests/test_notification_writer.py</automated>
    <automated>rtk pytest -q tests/test_orchestrator.py</automated>
    <automated>rtk pytest -q tests/test_notifier_base.py tests/test_models_notification_dedup.py tests/test_notifier_registry.py tests/test_notifiers_sound.py tests/test_notifiers_discord.py tests/test_notifiers_email.py tests/test_notifiers_sms.py</automated>
    <automated>rtk pytest -q</automated>
  </verify>
  <acceptance_criteria>
    - tests/test_notification_writer.py: all five tests GREEN (four from RED skeleton + new mark_notified-failure regression test)
    - tests/test_orchestrator.py: five new AST tests pass alongside existing Phase 4 tests
    - All eight Phase 5 test files green
    - Full project pytest suite green
    - No new dependencies added beyond Plan 05-01's twilio pin
  </acceptance_criteria>
  <done>Phase 5 complete. Full notification fan-out operational with NOTIF-01 isolation + NOTIF-02 dedup + per-channel implementations from Wave 1.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| notification_queue producer/consumer | One consumer (writer), N producers (poll_plugin tasks); writer crash is FATAL by design |
| Per-notifier exceptions | Must be isolated via gather(return_exceptions=True); leak = NOTIF-01 failure |
| Dedup decision | Single-writer eliminates race; should_notify/mark_notified called in writer only |
| Shutdown ordering | Plugins + notifiers must both run shutdown under shield; one slow shutdown cannot block others |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-06-WRITER-CRASH | Denial of Service | notification_writer | mitigate | Outer while loop has NO try/except (Phase 4 Pitfall 4-10); a critical-infrastructure crash tears down the TaskGroup so the bot stops loudly rather than silently dropping notifications. Inner try/except/finally guarantees task_done in finally |
| T-05-06-CHANNEL-CONTAGION | Denial of Service | notification_writer fan-out | mitigate | asyncio.gather(return_exceptions=True) isolates per-notifier failures; each Exception logged with notifier name + event URL; writer continues |
| T-05-06-DEDUP-RACE | Tampering | should_notify/mark_notified | mitigate | Single-writer model — only notification_writer reads + writes last_notified_at; no producer concurrency on the dedup state |
| T-05-06-DOUBLE-SOUND | Denial of Service (UX) | main.py _poll_once + sound notifier | mitigate | Inline play_available_sound/play_buy_sound REMOVED from main.py; sound notifier owns playback (RESEARCH Q11.15); AST test enforces |
| T-05-06-SHUTDOWN-HANG | Denial of Service | main.py finally gather | mitigate | All notifier shutdowns wrapped in asyncio.shield + gather(return_exceptions=True); one notifier's slow shutdown cannot block others; Ctrl-C during shutdown does not interrupt cleanup |
| T-05-06-MARK-FAIL-CRASH | Denial of Service | notification_writer mark_notified | mitigate | mark_notified failure caught in dedicated try/except inside notification_writer; logged ERROR; writer continues (CONTEXT pitfall #1) |
| T-05-06-PURCHASED-DEDUP-MISS | Functional | notification_writer | mitigate | action="purchased" bypasses should_notify gate entirely (RESEARCH Q8); test_purchasedActionBypassesDedup enforces |
</threat_model>

<verification>
- `python -c "import inspect; from main import notification_writer; assert inspect.iscoroutinefunction(notification_writer)"`
- `rtk grep -c "play_available_sound\|play_buy_sound" main.py` returns 0
- `rtk grep -n "datetime.now(timezone.utc)" main.py` matches both NotificationEvent put sites
- `rtk grep -n "tg.create_task(notification_writer" main.py` matches one line
- `rtk grep -n "for n in notifiers" main.py` matches the shutdown gather
- `rtk pytest -q tests/test_notification_writer.py tests/test_orchestrator.py` shows all GREEN
- `rtk pytest -q` (full suite) shows all GREEN
- Phase 5 exit criteria from ROADMAP.md satisfied:
  - Discord misconfigured -> bot keeps running (NOTIF-01 isolation tested)
  - Item in/out of stock multiple times in one poll cycle -> exactly one notification per restock event (NOTIF-02 dedup tested via test_shouldNotifyFalseInsideWindow + test_shouldNotifyTrueAfterWindow + writer's should_notify gate)
  - Discord embed includes name/URL/platform/timestamp/action (NOTIF-04 tested in Plan 05-03)
  - SMS opt-in with two locks, clear config error when env missing (NOTIF-06 tested in Plan 05-05)
</verification>

<success_criteria>
- main.py extended with notification_queue + notification_writer + NotificationEvent put sites + shutdown extension
- Inline play_*_sound calls removed from main.py
- notification_writer mirrors purchase_writer pattern with fan-out + dedup gate + task_done in finally
- Purchased events bypass dedup; detected events use should_notify + mark_notified
- All Phase 5 RED test files now GREEN
- Phase 4 test suite still green; full project suite green
- Phase 5 exit criteria from roadmap satisfied
</success_criteria>

<output>
After completion, create `.planning/phases/05-notification-system/05-06-SUMMARY.md`
</output>
