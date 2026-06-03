---
phase: 05-notification-system
plan: "01"
subsystem: notifications
tags: [config-schema, models, abc, dedup, sms-gate, test-scaffold]
dependency_graph:
  requires: []
  provides: [NotificationsConfig, NotificationEvent, Notifier, dedup-columns, sms-startup-gate]
  affects: [core/config_schema.py, models.py, notifications/, tests/]
tech_stack:
  added: []
  patterns: [pydantic-model-validator, abc-abstractmethod, dataclass, idempotent-alter-table]
key_files:
  created:
    - notifications/__init__.py
    - notifications/base.py
    - tests/test_notifications.py
  modified:
    - core/config_schema.py
    - models.py
    - tests/conftest.py
decisions:
  - smtp_username added as optional EmailConfig field defaulting to sender (RESEARCH Open Question 1)
  - Notifier ABC async send mirrors RetailerPlugin ABC pattern for consistency
  - fake_notifier fixture uses event loop properly (async def tests, asyncio_mode=auto)
  - Dedup state read returns (bool, str|None); False/None for unknown links (safe default)
metrics:
  duration: 8m
  completed: 2026-06-03
---

# Phase 5 Plan 01: Notification System Foundation Summary

Wave 0 foundation for Phase 5: config schema, dedup data model, Notifier contract, and the full 14-test scaffold every later plan verifies against.

## What Was Built

- `NotificationsConfig` submodel on `AppConfig` with four per-channel sub-configs (sound/discord/email/sms); SMS startup gate (`SmsConfig.require_creds_if_enabled`) raises a clear `ValidationError` listing missing `TWILIO_*` env vars when `sms.enabled=true` at construction time (NOTIF-06)
- Two idempotent dedup columns on the `items` table: `last_seen_available INTEGER NOT NULL DEFAULT 0` and `last_notified TEXT`; `initialize_db` guards via `PRAGMA table_info` so repeated restarts do not error or duplicate columns (NOTIF-02)
- Three `*_sync` state functions: `get_item_notification_state_sync`, `set_item_available_sync`, `clear_item_available_sync` -- all use the WAL `get_db_connection()` context manager
- `notifications/base.py`: `NotificationEvent` dataclass + `Notifier` ABC with `async send(event) -> None` abstractmethod
- `notifications/__init__.py`: exports `Notifier`, `NotificationEvent`; lazy-imports `NotificationDispatcher` (Plans 02-04 add it without breaking this import)
- `tests/conftest.py`: `fake_notifier` factory (records events, optionally raises) and `notification_event` factory fixtures
- `tests/test_notifications.py`: all 14 named tests from the RESEARCH test map; SMS config + ABC contract + dedup tests pass now; Plans 02-04 behaviors marked `xfail`

## Test Results

- Full suite: 82 passed, 9 xfailed, 3 pre-existing warnings (not introduced by this plan)
- New tests passing: 10 (SMS config gate, ABC contract, dedup round-trips, fixture smoke tests)
- New tests xfail: 9 (channel notifiers and dispatcher -- implemented in Plans 02-04)

## Deviations from Plan

None -- plan executed exactly as written.

## Threat Flags

None -- no new network endpoints, auth paths, or external write surfaces introduced. All secrets remain env-only; no secret field names appear in the schema.

## Known Stubs

None -- all dedup functions are fully implemented and round-trip verified; the xfail tests are placeholder scaffolds, not stubs that affect plan goals.

## Self-Check: PASSED

- `notifications/__init__.py` FOUND
- `notifications/base.py` FOUND
- `tests/test_notifications.py` FOUND
- Commits: 91cac29, 2d8b9cd, f42322e verified in git log
