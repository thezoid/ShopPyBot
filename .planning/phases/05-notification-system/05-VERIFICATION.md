---
phase: 05-notification-system
status: passed
verified: 2026-06-03
score: 6/6 requirements; 3/4 success criteria fully verified, SC3 render needs a live human confirmation
method: unit suite (112 passed) + code inspection; one visual Discord-render confirmation deferred to user
---

# Phase 5 Verification — Notification System

**Status: PASSED** — 6/6 requirements implemented and unit-verified, 112 tests green. One success criterion (SC3 live embed *rendering* in a Discord channel) requires a visual human confirmation the orchestrator cannot perform (no webhook secret, no Discord visibility); the embed *construction* is unit-verified.

## Success Criteria (ROADMAP)

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | Misconfigured Discord does not crash/block other channels; error logged | PASS | `NotificationDispatcher` calls each notifier in its own try/except; `test_dispatcher_secret_scrub` proves a failing notifier (whose exception embeds a webhook URL) is logged scrubbed (class+status, URL ABSENT) AND the other notifiers still fire. The orchestrator `await dispatcher.notify(...)` cannot raise out, so the loop cannot crash from a channel failure. |
| 2 | One notification per restock event, not per poll tick | PASS | Edge-trigger in the poll loop: notify only on unavailable->available (read get_item_notification_state_sync, enqueue set_available); suppressed while available; clear_available on falling edge. Orchestrator unit tests assert one notify across a flap sequence. |
| 3 | Discord notification is an embed with name/URL/platform/timestamp/action | PARTIAL (construction PASS, live render = human confirm) | `DiscordNotifier` builds the embed JSON with title(name)+url+Platform/Action fields+ISO-8601-Z timestamp; unit test asserts the payload shape. The visual confirmation that Discord renders it correctly needs a real DISCORD_WEBHOOK_URL + a human looking at the channel. DEFERRED to user (see checkpoint in 05-05-SUMMARY.md). |
| 4 | SMS off by default; enabling needs opt-in; misconfig = clear error not silent no-op | PASS | NotificationsConfig SMS validator: sms.enabled true without Twilio env creds raises ValidationError at startup; SmsNotifier only built by build_dispatcher when enabled+credentialed. Config test covers it. |

## Requirement Coverage

NOTIF-01 (fan-out + per-channel isolation), NOTIF-02 (SQLite dedup last_seen_available/last_notified edge-trigger), NOTIF-03 (SoundNotifier wraps utils), NOTIF-04 (Discord embed), NOTIF-05 (Email smtplib STARTTLS), NOTIF-06 (Twilio SMS opt-in/off-by-default) — all implemented and unit-covered.

## Locked-Decision & Security Checks

- Zero new dependencies: Discord + Twilio via requests, Email via stdlib smtplib. CONFIRMED.
- Secrets env-only, never logged: webhook URL / SMTP password / Twilio SID+token sourced from env; the #1 research finding (never log str(exc) for requests errors) is implemented (dispatcher + notifiers log class+status only) and proven by the secret-scrub test. CONFIRMED.
- Blocking sends via run_in_executor; dispatcher.notify awaited directly in the async poll coroutine (not from the sync drain). CONFIRMED.
- Dedup writes flow through the Phase-4 WAL write queue (set_available/clear_available/purchased typed ops). CONFIRMED.

## Human Confirmation Needed (non-blocking, deferred to user)

SC3 live render + SC1 in a full bad-webhook run: requires a real Discord webhook + a live bot run with a forced/real in-stock item. Steps are recorded in 05-05-SUMMARY.md. The behavior is fully unit-proven; this is a visual/integration confirmation only.

## Regression

`.venv/Scripts/python.exe -m pytest tests/ -q` → 112 passed (3 warnings). Note: one benign RuntimeWarning about an un-awaited mock `sleep` in a test — test hygiene, not a defect; worth tidying in a future cleanup.
