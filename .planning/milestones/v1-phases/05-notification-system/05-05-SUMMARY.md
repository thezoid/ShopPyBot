---
phase: 05-notification-system
plan: "05"
subsystem: notifications + orchestrator
tags: [dispatcher, dedup, edge-trigger, write-queue, discord, notifications]
dependency_graph:
  requires: ["05-01", "05-02", "05-03", "05-04"]
  provides: ["build_dispatcher factory", "dedup edge-trigger wiring", "typed write-queue ops"]
  affects: ["core/orchestrator.py", "notifications/__init__.py"]
tech_stack:
  added: []
  patterns:
    - "build_dispatcher factory (config-driven notifier selection)"
    - "rising/falling edge dedup gate on get_item_notification_state_sync"
    - "typed write-queue tuples: (purchased|set_available|clear_available, ...)"
    - "_dispatch_write extracted coroutine for single-responsibility drain"
key_files:
  created: []
  modified:
    - notifications/__init__.py
    - core/orchestrator.py
    - tests/test_notifications.py
    - tests/test_orchestrator.py
decisions:
  - "dispatcher=None default on run_plugin/_check_and_buy preserves backward compat with existing tests"
  - "build_dispatcher skips DiscordNotifier when DISCORD_WEBHOOK_URL absent (no crash on missing env)"
  - "legacy bare-link queue items still route to update_item_purchased_sync for backward compat"
  - "_try_auto_buy extracted to keep _check_and_buy under 30 lines"
  - "last_seen_available left as 1 after purchase per RESEARCH Open Question 2; purchased flag gates re-poll"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-03"
  tasks_completed: 2
  tasks_total: 3
  files_changed: 4
---

# Phase 05 Plan 05: Dispatcher Factory + Dedup Edge-Trigger Wiring Summary

**One-liner:** `build_dispatcher(cfg)` factory selects notifiers from config flags; orchestrator notifies exactly once per restock rising edge, routes all dedup/purchase writes through the serializing write queue via typed tuples.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | build_dispatcher factory + typed write-queue drain | fd407ac | notifications/__init__.py, core/orchestrator.py |
| 2 | Dedup edge-trigger wiring in the poll loop | 3844183 | core/orchestrator.py, tests/test_orchestrator.py |
| 3 | Live Discord human-verify (checkpoint) | - | BLOCKED: awaiting human |

## What Was Built

### Task 1: build_dispatcher factory + typed write-queue drain

`notifications/__init__.py` gains `build_dispatcher(cfg) -> NotificationDispatcher`:
- Reads `cfg.notifications` enable flags
- `SoundNotifier` added when `notifications.sound` is True
- `DiscordNotifier` added when `discord.enabled` AND `DISCORD_WEBHOOK_URL` env var is set (no crash if env absent)
- `EmailNotifier(email_cfg)` added when `email.enabled`
- `SmsNotifier(sms_cfg)` added when `sms.enabled` (creds already validated by Pydantic at startup)

`core/orchestrator.py` `_write_queue_drain` restructured:
- New `_dispatch_write(loop, item)` coroutine handles typed tuple routing
- `("purchased", link)` maps to `update_item_purchased_sync`
- `("set_available", link, ts)` maps to `set_item_available_sync`
- `("clear_available", link)` maps to `clear_item_available_sync`
- Legacy bare-link items still map to purchased for backward compatibility

### Task 2: Dedup edge-trigger wiring

`core/orchestrator.py` reworked:
- `_build_event()` helper constructs `NotificationEvent` from plugin context
- `run_plugin()` and `_check_and_buy()` accept `dispatcher=None` param (backward compat)
- `_check_and_buy()` reads `get_item_notification_state_sync(link)` via `run_in_executor` before deciding to notify
- Rising edge (available=True, was_available=False): `dispatcher.notify(detected_event)` + enqueue `("set_available", link, now_iso)`
- Falling edge (available=False, was_available=True): enqueue `("clear_available", link)`, no notify
- No-op: available=False, was_available=False: no queue writes, no notify
- Suppress: available=True, was_available=True: no notify (suppressed)
- `_try_auto_buy()` extracted for single responsibility: `dispatcher.notify(purchased_event)` + enqueue `("purchased", link)` on success
- `async_main()` calls `build_dispatcher(cfg)` and passes dispatcher into each `run_plugin` task
- Direct `play_available_sound()` and `play_buy_sound()` calls removed; sound now delivered by `SoundNotifier` inside the dispatcher

## Tests Added

### test_notifications.py (7 new)
- `test_build_dispatcher_sound_only`: sound=True -> exactly [SoundNotifier]
- `test_build_dispatcher_no_sound_empty`: sound=False, all off -> empty
- `test_build_dispatcher_discord_added_when_enabled`: discord.enabled + env -> DiscordNotifier included
- `test_build_dispatcher_discord_skipped_without_env`: discord.enabled but no env var -> DiscordNotifier skipped
- `test_build_dispatcher_email_added_when_enabled`: email.enabled -> EmailNotifier included
- `test_build_dispatcher_sms_added_when_enabled`: sms.enabled + Twilio env -> SmsNotifier included
- `test_build_dispatcher_all_channels`: all enabled -> all 4 types present

### test_orchestrator.py (9 new)
- `test_drain_typed_purchased_tuple`: ("purchased", link) -> update_item_purchased_sync only
- `test_drain_typed_set_available_tuple`: ("set_available", link, ts) -> set_item_available_sync only
- `test_drain_typed_clear_available_tuple`: ("clear_available", link) -> clear_item_available_sync only
- `test_check_and_buy_notifies_on_rising_edge`: unavail->avail fires exactly one detected notify
- `test_check_and_buy_suppresses_while_available`: avail->avail fires no notify
- `test_check_and_buy_enqueues_clear_on_unavailable`: avail->unavail enqueues clear, no notify
- `test_check_and_buy_no_queue_when_unavailable_stays_unavailable`: unavail->unavail: nothing
- `test_check_and_buy_purchase_dispatches_purchased_event`: auto_buy success fires purchased event
- `test_dedup_renotify_after_full_cycle`: unavail->avail->avail->unavail->avail yields exactly 2 detected

**Suite result: 112 passed (was 96 before phase 05-05), 3 pre-existing warnings**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test helper passed NotificationsConfig instead of AppConfig wrapper**
- **Found during:** Task 1 (GREEN phase, test_build_dispatcher_sound_only)
- **Issue:** `_make_notifications_config()` returned a bare `NotificationsConfig`; `build_dispatcher(cfg)` dereferences `cfg.notifications`, causing AttributeError
- **Fix:** Wrapped in `_FakeCfg` dataclass with `.notifications` attribute; factory signature stays clean (takes AppConfig-like, not NotificationsConfig)
- **Files modified:** tests/test_notifications.py
- **Commit:** fd407ac

**2. [Rule 2 - Missing] MagicMock.__name__ unreliable in fake_executor**
- **Found during:** Task 1 (first drain test run); `fake_executor` called `fn.__name__` on a MagicMock, causing AttributeError swallowed by drain's except block
- **Fix:** Removed `fn.__name__` call from test fake_executor; tests use pre-created `MagicMock(return_value=None)` instances passed via `patch(target, mock)` for reliable identity assertions
- **Files modified:** tests/test_orchestrator.py
- **Commit:** fd407ac

## Threat Model Compliance

| Threat ID | Status |
|-----------|--------|
| T-05-14 | Mitigated: notify gated on 0->1 rising edge; suppressed while available |
| T-05-15 | Mitigated: all dedup writes through write queue; no direct sync write from coroutines |
| T-05-16 | Pending human-verify: log scrub verified in unit tests (dispatcher secret scrub test from 05-04); live run log inspection is the checkpoint |
| T-05-17 | Accepted: event fields internally generated, not user input |

## Human-Verify Checkpoint (Task 3)

The final task is a `checkpoint:human-verify` for live Discord embed delivery. This cannot be unit-tested. The human must:

1. Create a Discord webhook and set `$env:DISCORD_WEBHOOK_URL = "<url>"`
2. Set `notifications.discord.enabled: true` in `config.yml`
3. Run the bot against a known in-stock item (or force `check_availability` to return True)
4. Confirm in Discord: one embed appears with item name + "Detected" title, clickable URL, Platform/Action fields, timestamp; does NOT repeat each tick (dedup works)
5. Misconfig resilience: set `$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/bad"`, confirm bot keeps running, sound still plays, log shows scrubbed Discord error (no webhook URL in log)
6. Inspect `logs/` latest file: confirm no webhook URL substring appears

**Resume signal:** Type "approved" once embed rendered correctly and bad-webhook run stayed up with scrubbed log, or describe what failed.

## Known Stubs

None. All notification paths are fully wired. Discord, Email, and SMS channels are disabled by default; they require explicit config opt-in.

## Self-Check: PASSED

- `notifications/__init__.py` contains `build_dispatcher`: FOUND
- `core/orchestrator.py` contains `_dispatch_write`, `_check_and_buy` (26 lines), `_try_auto_buy`: FOUND
- Task 1 commit fd407ac: FOUND
- Task 2 commit 3844183: FOUND
- `from notifications import build_dispatcher` import: OK
- `from core.orchestrator import _check_and_buy, _write_queue_drain, _dispatch_write` import: OK
- Full suite: 112 passed
