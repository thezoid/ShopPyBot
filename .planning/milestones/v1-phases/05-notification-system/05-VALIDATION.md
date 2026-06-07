---
phase: 5
slug: notification-system
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-03
---

# Phase 5 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.4 + pytest-asyncio 1.3.0 (asyncio_mode=auto) |
| **Config file** | pyproject.toml |
| **Quick run** | `.venv/Scripts/python.exe -m pytest tests/ -q` |
| **Full suite** | `.venv/Scripts/python.exe -m pytest tests/ -q` |
| **Runtime** | ~3s (all network mocked; no live sends in suite) |

## Sampling Rate

- After every task commit: quick run
- After every wave: full suite
- Before verify-work: full suite green
- Max latency: ~5s

## Per-Requirement Verification Map

| Requirement | Test Type | Approach | Live? |
|-------------|-----------|----------|-------|
| NOTIF-01 (fan-out + isolation) | unit | Dispatcher with 3 notifiers, one raising; assert the other two still called + error logged + no exception propagates | no |
| NOTIF-02 (dedup edge-trigger) | unit | Simulate availability flap (unavail->avail->avail->unavail->avail); assert exactly 2 notifies (one per restock), using fake clock/state | no |
| NOTIF-03 (sound notifier) | unit | Mock utils.play_* ; assert sound notifier calls the right function on detected/purchased | no |
| NOTIF-04 (Discord embed) | unit | Mock requests.post; assert embed JSON has title/url/platform/timestamp(ISO-8601 Z)/action; assert 204 handled, 429 logged | no |
| NOTIF-05 (Email SMTP) | unit | Mock smtplib.SMTP; assert STARTTLS+login+send_message; EmailMessage has sender/recipients/subject/body | no |
| NOTIF-06 (Twilio opt-in) | unit | (a) sms disabled by default -> notifier absent; (b) sms.enabled true + missing creds -> clear config error at startup (not silent); (c) enabled+creds -> requests.post to Messages.json with basic auth + To/From/Body | no |
| SEC (no secret leak in logs) | unit | Force a channel failure; assert the log line contains exc class + status code but NOT the webhook URL / SID / token | no |

## Wave 0 Requirements

- [ ] `tests/conftest.py` — add fixtures: a fake Notifier (records calls / can be set to raise), a mock requests/smtplib helper, and a NotificationEvent factory.
- [ ] SQLite dedup columns (`last_seen_available`, `last_notified`) added with a migration-safe `ALTER TABLE ... ADD COLUMN` guard (idempotent) — covered by a models test before the dedup logic depends on it.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Instructions |
|----------|-------------|------------|--------------|
| Real Discord embed delivery | NOTIF-04 | Needs a live webhook | Set DISCORD_WEBHOOK_URL; trigger a detected event; confirm the embed appears in the channel |
| Real email delivery | NOTIF-05 | Needs a live SMTP account | Configure SMTP + env password; confirm the alert email arrives |
| Real SMS delivery | NOTIF-06 | Needs a paid Twilio account | Opt-in + Twilio env creds; confirm one SMS on restock |
| Misconfigured-Discord resilience | SC1 | Needs a live run | Set a bad webhook URL; confirm bot keeps running + email/sound still fire + error logged |

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependency
- [ ] No 3 consecutive tasks without automated verify
- [ ] Wave 0 covers fake notifier + dedup columns + event factory
- [ ] No watch-mode flags
- [ ] Secret-leak test present (logs scrubbed)
- [ ] nyquist_compliant: true when complete

**Approval:** pending
