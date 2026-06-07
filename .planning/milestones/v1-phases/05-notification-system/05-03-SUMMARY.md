---
phase: 05-notification-system
plan: "03"
subsystem: notifications
tags: [email, smtp, sms, twilio, security, credentials]
dependency_graph:
  requires: ["05-01", "05-02"]
  provides: ["notifications/email_notifier.py", "notifications/sms_notifier.py"]
  affects: ["tests/test_notifications.py"]
tech_stack:
  added: []
  patterns:
    - "smtplib.SMTP context-manager with starttls()+login()+send_message()"
    - "smtplib.SMTP_SSL context-manager with login()+send_message()"
    - "requests.post with HTTPBasicAuth for Twilio Messages.json"
    - "loop.run_in_executor for blocking SMTP and HTTP transports"
    - "env-only secrets; never stored as logged attributes"
key_files:
  created:
    - notifications/email_notifier.py
    - notifications/sms_notifier.py
  modified:
    - tests/test_notifications.py
decisions:
  - "SMTP_PASSWORD read at send() time from os.environ (not stored on instance) to minimise exposure window"
  - "SMTPAuthenticationError and all SMTP exceptions propagate to dispatcher boundary; EmailNotifier does not catch/log them"
  - "Twilio endpoint URL contains Account SID -- never logged; failure path logs scrubbed 'twilio/Messages.json' label + status only"
  - "Both notifiers use loop.run_in_executor to avoid blocking the async event loop (RESEARCH Pitfall 4)"
metrics:
  duration: "~4 minutes"
  completed: "2026-06-03"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 5 Plan 3: EmailNotifier + SmsNotifier Summary

EmailNotifier via stdlib smtplib STARTTLS/SMTP_SSL and SmsNotifier via Twilio Messages.json REST, both secret-safe with run_in_executor transport.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | EmailNotifier via stdlib smtplib STARTTLS | 1a377e7 | notifications/email_notifier.py, tests/test_notifications.py (RED: 3f1657a) |
| 2 | SmsNotifier via Twilio REST with SID-safe error path | 16e47fb | notifications/sms_notifier.py |

## What Was Built

**EmailNotifier** (`notifications/email_notifier.py`):

Subclasses `Notifier` ABC; takes `EmailConfig` in `__init__`. Resolves effective SMTP username as `smtp_username or sender`. `_send_email_blocking` builds an `EmailMessage` (Subject, From, To, body via `set_content`), then branches on `smtp_ssl`: `SMTP_SSL+login+send_message` for True; `SMTP+starttls+login+send_message` for False. `SMTP_PASSWORD` is read from `os.environ` at `send()` time -- never stored as an instance attribute. `async send()` runs the blocking function via `loop.run_in_executor`. SMTP exceptions (`SMTPAuthenticationError`, `SMTPConnectError`, `SMTPRecipientsRefused`, `SMTPException`, `OSError`) propagate; none are caught inside `send()`.

**SmsNotifier** (`notifications/sms_notifier.py`):

Subclasses `Notifier` ABC; takes `SmsConfig`. `_send_sms_blocking` builds the Twilio endpoint URL (containing SID) and calls `requests.post` with `HTTPBasicAuth(sid, token)` and form data `{To, From, Body}`. `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM` are read from `os.environ` at `send()` time. `resp.raise_for_status()` propagates `requests.HTTPError` for dispatcher isolation. The endpoint URL is never logged. `async send()` runs via `loop.run_in_executor`.

## Verification Results

```
tests/test_notifications.py -k "email or sms": 5 passed
Full suite: 92 passed, 2 xfailed (05-04 dispatcher stubs), 3 pre-existing warnings
```

## Deviations from Plan

None -- plan executed exactly as written.

## Threat Model Coverage

| Threat | Status |
|--------|--------|
| T-05-07: SMTP_PASSWORD in logs | Mitigated: password read at call time; exceptions propagate without logging password or str(exc) |
| T-05-08: Twilio SID/URL in logs | Mitigated: endpoint URL never logged; failure path uses scrubbed label only |
| T-05-09: Accidental SMS in test_mode | Mitigated by Plan 01 SmsConfig validator (startup gate remains green) |
| T-05-10: SMTP body newline injection | Mitigated: set_content() handles encoding; no raw header concatenation |

## Known Stubs

None -- both notifiers are fully wired; no placeholder data paths.

## Self-Check: PASSED

- notifications/email_notifier.py: FOUND
- notifications/sms_notifier.py: FOUND
- Commit 3f1657a (test RED): confirmed in git log
- Commit 1a377e7 (EmailNotifier GREEN): confirmed in git log
- Commit 16e47fb (SmsNotifier GREEN): confirmed in git log
- Full suite green: 92 passed
