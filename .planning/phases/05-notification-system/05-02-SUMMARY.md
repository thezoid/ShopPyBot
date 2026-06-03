---
phase: 05-notification-system
plan: "02"
subsystem: notifications
tags: [sound, discord, notifier, webhook, embed, pygame]
dependency_graph:
  requires: ["05-01"]
  provides: ["notifications/sound_notifier.py", "notifications/discord_notifier.py"]
  affects: ["tests/test_notifications.py"]
tech_stack:
  added: []
  patterns:
    - "Notifier ABC subclass with async send()"
    - "action-keyed dispatch (detected/purchased/fallback)"
    - "run_in_executor for blocking requests.post"
    - "secret-safe error logging (class name + status only)"
key_files:
  created:
    - notifications/sound_notifier.py
    - notifications/discord_notifier.py
  modified:
    - tests/test_notifications.py
decisions:
  - "Sound runs synchronously on the calling thread; no run_in_executor per RESEARCH Open Question 3 (pygame thread-safety unconfirmed)"
  - "DiscordNotifier.__init__ reads DISCORD_WEBHOOK_URL into a private attribute; never exposed in log output"
  - "429 raises RuntimeError with Retry-After value; no retry loop (T-05-05 accepted disposition)"
  - "HTTPError catch in send() re-raises after logging class name + status to preserve caller error isolation"
metrics:
  duration: "12 minutes"
  completed: "2026-06-03"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 5 Plan 02: SoundNotifier + DiscordNotifier Summary

SoundNotifier wraps the three `utils.py` pygame helpers with action-keyed dispatch, and DiscordNotifier posts a standardized Discord embed via `run_in_executor` with a secret-safe error path (no URL or `str(exc)` ever logged).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for SoundNotifier + DiscordNotifier | e4735d1 | tests/test_notifications.py |
| 1 (GREEN) + 2 (GREEN) | SoundNotifier + DiscordNotifier implementation | 42aa8d0 | notifications/sound_notifier.py, notifications/discord_notifier.py |

## TDD Gate Compliance

RED gate commit: `e4735d1` -- `test(05-02): add failing tests for SoundNotifier and DiscordNotifier`
GREEN gate commit: `42aa8d0` -- `feat(05-02): implement SoundNotifier and DiscordNotifier`

Both gates present and ordered correctly.

## What Was Built

### notifications/sound_notifier.py

`SoundNotifier(Notifier)` with a 10-line `send()` method:
- `action == "detected"` calls `play_available_sound()`
- `action == "purchased"` calls `play_buy_sound()`
- any other action falls back to `play_notification_sound()`
- No `run_in_executor` -- sound stays synchronous on the calling thread

### notifications/discord_notifier.py

`DiscordNotifier(Notifier)` plus two module-level helpers:
- `_build_discord_payload(event)` -- assembles the `embeds[0]` dict with title, url, color (green for detected / yellow for purchased), UTC Z-suffix timestamp, and inline Platform + Action fields
- `_send_discord_blocking(webhook_url, payload)` -- `requests.post(..., timeout=10)`, raises `RuntimeError` on 429 with Retry-After, passes 204 through `raise_for_status()`
- `send()` runs `_send_discord_blocking` via `loop.run_in_executor(None, ...)`
- `except requests.HTTPError` logs `[DiscordNotifier] HTTP {status} -- delivery failed` then re-raises; never logs `str(exc)` or webhook URL

## Test Results

```
7 passed  (sound + discord tests)
89 passed, 5 xfailed, 0 failures  (full suite)
```

## Deviations from Plan

None -- plan executed exactly as written. Both TDD phases (RED then GREEN) completed in order.

## Known Stubs

None. Both notifiers are fully wired.

## Threat Flags

No new security-relevant surface beyond what is documented in the plan threat model.

## Self-Check: PASSED

- FOUND: notifications/sound_notifier.py
- FOUND: notifications/discord_notifier.py
- FOUND: commit e4735d1 (RED tests)
- FOUND: commit 42aa8d0 (GREEN implementation)
- Full suite: 89 passed, 5 xfailed, 0 failures
