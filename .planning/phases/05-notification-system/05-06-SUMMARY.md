---
phase: 05-notification-system
plan: 06
subsystem: orchestrator-integration
tags:
  - python
  - asyncio
  - taskgroup
  - orchestrator
  - notification
  - fan-out
  - integration
  - wave-2
requirements:
  - NOTIF-01
  - NOTIF-02
dependency-graph:
  requires:
    - 05-01 (NotificationEvent, should_notify, mark_notified, RED skeleton)
    - 05-02 (discover_notifiers, SoundNotifier shutdown contract)
    - 05-03 (Discord notifier)
    - 05-04 (Email notifier)
    - 05-05 (SMS notifier two-lock)
    - 04-05 (purchase_writer + TaskGroup shape to mirror)
  provides:
    - main.notification_writer coroutine (queue consumer, fan-out, dedup gate, mark_notified)
    - notification_queue (maxsize=200) wired into TaskGroup alongside purchase_queue
    - NotificationEvent put-sites in _poll_once (detected) and _attempt_purchase (purchased)
    - Shutdown gather covering both registry plugins and notifiers under asyncio.shield
  affects:
    - main.py (orchestrator extended; inline sound calls removed)
    - tests/test_notification_writer.py (RED to GREEN)
    - tests/test_orchestrator.py (extended with Phase 5 AST assertions)
tech-stack:
  added: []
  patterns:
    - "single-consumer + fan-out via asyncio.gather(return_exceptions=True)"
    - "AST-based invariant assertions for orchestrator wiring"
    - "asyncio.shield over per-resource shutdown coroutines"
key-files:
  created:
    - .planning/phases/05-notification-system/05-06-SUMMARY.md
  modified:
    - main.py
    - tests/test_notification_writer.py
    - tests/test_orchestrator.py
decisions:
  - "notification_writer outer loop has no try/except — crash is FATAL by design (Phase 4 Pitfall 4-10)"
  - "Dedup gate (should_notify) lives inside the single writer — eliminates producer race"
  - "Purchased events bypass dedup gate AND do not call mark_notified"
  - "mark_notified failure caught in inner try/except so writer survives DB blips"
  - "Inline play_*_sound calls REMOVED from main.py; SoundNotifier owns playback"
  - "Single gather in shutdown finally covers plugins + notifiers (two starred generators)"
metrics:
  duration: "approximately 25 minutes"
  completed: "2026-05-15"
  tasks: 2
  files_modified: 3
---

# Phase 5 Plan 06: Orchestrator Integration Summary

Wave 2 integration completing Phase 5: wires notification_queue, notification_writer consumer, and NotificationEvent put-sites into the Phase 4 async orchestrator so detected stock and successful purchases fan out concurrently across all enabled notifiers with per-channel failure isolation and per-restock-window dedup.

## What Shipped

- `main.notification_writer(queue, notifiers, restock_window_seconds)` async consumer mirroring `purchase_writer`. Outer `while True` has no try/except (FATAL by design); inner try/except/finally guarantees `queue.task_done()` and isolates `should_notify`/`mark_notified` failures.
- `notification_queue: asyncio.Queue = asyncio.Queue(maxsize=200)` created inside `main()` next to `purchase_queue`.
- `notifiers = await discover_notifiers(Path("notifiers"), app_config=app_config)` runs after `verify_coverage`.
- TaskGroup now starts `purchase_writer`, `notification_writer`, then one `poll_plugin` per registry entry.
- `_poll_once` enqueues `NotificationEvent(action="detected")` immediately after `available=True` and before any auto-buy branch.
- `_attempt_purchase` enqueues `NotificationEvent(action="purchased")` after `purchase_queue.put((link,))`.
- All `NotificationEvent` constructions use `datetime.now(timezone.utc)` (tz-aware).
- Detected events run the `should_notify` dedup gate; purchased events bypass it.
- Per-event fan-out via `asyncio.gather(*(n.send(event) for n in active), return_exceptions=True)`; each `Exception` result logged with notifier name + event URL.
- `mark_notified` called via `asyncio.to_thread` only for detected events, wrapped in its own try/except so DB hiccups do not crash the writer.
- Inline `play_available_sound()` / `play_buy_sound()` calls removed from `_poll_once` and `_attempt_purchase`; the `from utils import play_available_sound, play_buy_sound` import is gone. `SoundNotifier` owns playback now.
- `_shutdown_all(registry, notifiers)` replaces `_shutdown_plugins(registry)`; a single `asyncio.gather` covers both starred generators wrapped in `asyncio.shield`.
- `poll_plugin` and `_poll_once` and `_attempt_purchase` signatures widened to thread `notification_queue` (and item `name` for `_attempt_purchase` to build the event payload).

## Tests

- `tests/test_notification_writer.py` replaced with five GREEN tests:
  - `test_notificationWriterIsAsyncCoroutine`
  - `test_oneFailedNotifierDoesNotBlockOthers` (NOTIF-01 isolation)
  - `test_purchasedActionBypassesDedup` (NOTIF-02 carve-out — also asserts `mark_notified` NOT called)
  - `test_taskDoneCalledInFinally` (queue.join resolves even when inner body raises)
  - `test_markNotifiedFailureLoggedNotCrashed` (new regression: writer survives `mark_notified` raising)
- `tests/test_orchestrator.py` extended with five AST-based Phase 5 assertions:
  - `test_noInlineSoundCalls`
  - `test_notificationWriterInTaskGroup`
  - `test_notificationEventTimestampsTzAware` (walks every `NotificationEvent` Call site)
  - `test_mainImportsDiscoverNotifiers`
  - `test_shutdownGathersNotifiers`
- Phase 4 `test_pluginCrashIsolated` adjusted (test-side only) to pass a stub `notification_queue` through the widened `poll_plugin` signature.

## Verification

| Command | Result |
|---------|--------|
| `python -c "import inspect; from main import notification_writer; assert inspect.iscoroutinefunction(notification_writer)"` | pass |
| `rtk grep -c "play_available_sound\|play_buy_sound" main.py` | 0 matches |
| `rtk grep -n "await notification_queue.put" main.py` | 2 sites (detected, purchased) |
| `rtk grep -n "datetime.now(timezone.utc)" main.py` | 2+ sites |
| `rtk grep -n "tg.create_task(notification_writer" main.py` | 1 site, after purchase_writer |
| `rtk grep -n "for n in notifiers" main.py` | shutdown gather only |
| `rtk pytest -q tests/test_notification_writer.py tests/test_orchestrator.py` | 18 passed |
| `rtk pytest --ignore=tests/test_notifiers_sms.py --ignore=tests/test_utils.py` | 261 passed |

## Commits

| Task | Type | Hash | Subject |
|------|------|------|---------|
| 1 | feat | 97ab845 | wire notification_writer + queue into async orchestrator |
| 2 | test | 16114a0 | GREEN notification_writer + extend orchestrator Phase 5 asserts |

## Deviations from Plan

### Auto-fixed Issues

1. `[Rule 1 - Bug]` Plan 05-01 RED tests patched `models.should_notify` / `models.mark_notified`. Since `main.py` binds those names at import time (`from models import should_notify, mark_notified`), patching `models.<name>` does not redirect the calls used inside `notification_writer`. Fix: GREEN tests patch `main.should_notify` and `main.mark_notified` directly. This matches Python's standard "patch where it is used, not where it is defined" rule and is the only way the dedup/mark assertions can fire. Plan 05-01 reference was incorrect; Plan 05-06 GREEN tests are authoritative.
   - Files modified: `tests/test_notification_writer.py`
   - Commit: `16114a0`

2. `[Rule 3 - Blocking]` Phase 4 `test_pluginCrashIsolated` calls `poll_plugin(good, appConfigStub, queue, stop)`. Task 1 widens `poll_plugin` to require `notification_queue`. Fix: test now constructs a stub `notifQueue = asyncio.Queue()` and passes it positionally. This is the test-side adjustment the plan explicitly authorized as acceptable.
   - Files modified: `tests/test_orchestrator.py`
   - Commit: `97ab845`

3. `[Rule 2 - Hardening]` The plan's `_shutdown_plugins` helper was renamed to `_shutdown_all(registry, notifiers)` so the single-gather-with-two-starred-generators pattern lives in one helper rather than duplicating shutdown logic across two helpers. Functionally identical to the plan's inline gather; just keeps `main()` thin and AST tests still match (`for n in notifiers` + `asyncio.shield` both present).
   - Files modified: `main.py`

## Deferred Issues

- `tests/test_notifiers_sms.py` fails to collect: `ModuleNotFoundError: No module named 'twilio'`. Pre-existing — twilio is the Plan 05-01 dependency; this environment does not have it installed. Out of scope for Plan 05-06.
- `tests/test_utils.py` fails to collect: `ImportError: cannot import name 'make_tiny' from 'utils'`. Pre-existing — `make_tiny` lives in `main.py`, not `utils.py`. Out of scope (untouched by Plan 05-06; last commit by `0177274` long before Phase 5).

## Known Stubs

None. The notification system is end-to-end live: discovery loads real notifiers, writer drains the queue, fan-out fires real `send()` calls, dedup is real, mark_notified is real, shutdown cleans up real resources.

## Phase 5 Exit Criteria

- Misconfigured Discord does not crash or block other channels: `test_oneFailedNotifierDoesNotBlockOthers` enforces gather isolation.
- One notification per restock event, not per poll tick: detected branch calls `should_notify` then `mark_notified`; `test_shouldNotifyFalseInsideWindow` (05-01) plus the writer's gate enforce this.
- Discord embed includes name/URL/platform/timestamp/action: Plan 05-03 contract; this plan supplies the `NotificationEvent` payload with all five fields.
- SMS opt-in with two locks, clear config error when env missing: Plan 05-05.

## Self-Check: PASSED

- main.py exists and contains `async def notification_writer`: FOUND
- tests/test_notification_writer.py exists and has 5 GREEN tests: FOUND
- tests/test_orchestrator.py exists with 5 new Phase 5 assertions: FOUND
- Commit `97ab845` exists: FOUND
- Commit `16114a0` exists: FOUND
- `tests/test_notification_writer.py` and `tests/test_orchestrator.py` together: 18 passed
- Full suite (excluding pre-existing-broken `test_notifiers_sms.py` and `test_utils.py`): 261 passed
