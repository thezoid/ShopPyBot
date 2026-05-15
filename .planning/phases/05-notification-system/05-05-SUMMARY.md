---
phase: 05-notification-system
plan: 05
subsystem: sms-notifier
tags:
  - python
  - notifications
  - sms
  - twilio
  - two-lock
  - opt-in
  - wave-1
dependency_graph:
  requires:
    - notifier_base.Notifier + NotificationEvent (Plan 05-01)
    - config_schema.SmsNotifierConfig (Plan 05-01; account_sid/auth_token/from_number absent by SEC-01)
    - twilio==9.10.9 (pinned by Plan 05-01)
  provides:
    - notifiers.shopbot_notifier_sms.SmsNotifier (NOTIF-06)
    - Two-lock opt-in gate with three distinguishable failure messages
    - Sanitized TwilioRestException re-raise (code + status only)
  affects:
    - Wave 2 (Plan 05-06 notification_writer) picks up SmsNotifier via discover_notifiers
tech_stack:
  added: []
  patterns:
    - asyncio.to_thread wrapping sync twilio.rest.Client.messages.create
    - Two-lock opt-in (config.enabled AND SHOPBOT_ENABLE_SMS=='true')
    - Env-only credential surface (SID/token/from captured once at __init__)
    - test_mode forced disable (cost containment, CONTEXT D-04 third scenario)
    - from_= trailing-underscore keyword (Python reserved word)
    - Sanitized error re-raise (RuntimeError with code+status; no creds/body)
    - AST grep tests enforcing no-leak invariants
key_files:
  created:
    - notifiers/shopbot_notifier_sms.py
  modified:
    - tests/test_notifiers_sms.py
decisions:
  - "sub_config accepted as positional-or-keyword param to match RED skeleton call style SmsNotifier(_smsCfg(...), app_config=...) from Plan 05-01"
  - "Three distinguishable failure logs per CONTEXT D-04: both-off=INFO, config-off+env-on=WARNING, env-off+config-on=WARNING"
  - "TwilioRestException re-raised as RuntimeError(code, status) with `from None` to drop the original exception chain (prevents Twilio internal data resurfacing through __cause__)"
  - "msg body short template `[ShopPyBot] {item_name} {action}: {url}` (SMS char limits)"
  - "test_mode check placed AFTER two-lock pass: failing the lock check should report the lock failure first, not test_mode"
  - "Credential presence check uses helper _missing_twilio_creds returning a joined string of missing items so a single WARNING line names every gap"
metrics:
  duration_minutes: 8
  completed: 2026-05-15
  tasks_completed: 1
  files_changed: 2
---

# Phase 5 Plan 05: SMS Notifier (Two-Lock) Summary

SmsNotifier (NOTIF-06) ships as a Notifier subclass requiring BOTH `notifications.sms.enabled=True` in config AND `SHOPBOT_ENABLE_SMS=='true'` env (CONTEXT D-04), with `test_mode` forced disable and sanitized TwilioRestException handling so auth tokens never reach logs.

## One-liner

Twilio SMS notifier with strict two-lock opt-in (config + env), env-only credentials, test_mode disable, and sanitized error re-raise that never leaks SID, token, or message body.

## What Was Built

`notifiers/shopbot_notifier_sms.py` defines `SmsNotifier(Notifier)` with class attribute `name = "sms"`. `__init__` performs a single env read pass for `SHOPBOT_ENABLE_SMS`, `SHOPBOT_TWILIO_ACCOUNT_SID`, `SHOPBOT_TWILIO_AUTH_TOKEN`, and `SHOPBOT_TWILIO_FROM`, then runs the D-04 two-lock check producing three distinguishable log messages depending on which surface is missing. When both locks pass and `debug.test_mode is False` and all Twilio env vars are present, the Twilio `Client(sid, token)` is instantiated once and cached as `self._client`; `self.enabled = True`. Otherwise `self.enabled = False`.

`send(event)` calls `asyncio.to_thread(self._send_sms, event)`. `_send_sms` calls `self._client.messages.create(to=self._to, from_=self._from, body=...)` with the trailing-underscore `from_=` kwarg (Python reserved word). `TwilioRestException` is caught and re-raised as `RuntimeError(f"Twilio send failed (code={e.code}, status={e.status})")` using `from None` to drop the cause chain so Twilio internal data cannot resurface via `__cause__`.

The message body template is `"[ShopPyBot] {item_name} {action}: {url}"` (short enough for typical SMS segment limits).

`tests/test_notifiers_sms.py` ships 15 GREEN tests covering: import, the full two-lock matrix (both off / config off / env off / both on), `test_mode` disable, missing Twilio creds disable, from_= kwarg in actual send path, AST verification that `messages.create` uses `from_=` (and not `from` / `from_addr`), AST verification that `os.environ` is accessed only in `__init__`, AST verification that `writeLog` calls never reference `self._account_sid`/`self._auth_token`/`self._from`, snapshot-at-init proof via two-instance test, sanitized TwilioRestException re-raise, and a regression check that `SmsNotifierConfig.model_fields` does not contain `account_sid`/`auth_token`/`from_number`.

## Verification

- `python -c "from notifiers.shopbot_notifier_sms import SmsNotifier; from notifier_base import Notifier; assert issubclass(SmsNotifier, Notifier)"`: passes
- `rtk grep -c "os.environ" notifiers/shopbot_notifier_sms.py`: 4 matches, all in `__init__`
- `python -m pytest -q tests/test_notifiers_sms.py`: 15 passed
- `python -m pytest -q --ignore=tests/test_notifiers_discord.py --ignore=tests/test_notifiers_email.py --ignore=tests/test_notification_writer.py --ignore=tests/test_utils.py`: 242 passed (Wave 1 sibling RED files and the pre-existing `test_utils.py` RED skeleton remain RED as expected)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] sub_config signature relaxed from keyword-only to positional-or-keyword**
- Found during: Task 1, first pytest run
- Issue: `<interfaces>` block in the plan declared `def __init__(self, *, sub_config, app_config)` (keyword-only), but the RED skeleton from Plan 05-01 calls `SmsNotifier(_smsCfg(enabled=False), app_config=_AppCfgStub())` with `sub_config` positional. The keyword-only signature would have produced `TypeError: __init__() takes 1 positional argument` on every existing RED test.
- Fix: Removed the `*,` marker so `sub_config` accepts positional or keyword. `app_config` remains keyword-friendly via its default `None`.
- Files modified: `notifiers/shopbot_notifier_sms.py`
- Commit: GREEN feat commit

No other deviations. Threat model T-05-05-* mitigations all implemented as specified.

## Commits

- `test(05-05): expand RED tests for SMS notifier two-lock`
- `feat(05-05): SmsNotifier with D-04 two-lock opt-in (NOTIF-06)`

## Self-Check: PASSED

- notifiers/shopbot_notifier_sms.py: FOUND
- tests/test_notifiers_sms.py: FOUND (modified)
- 2 commits present in `git log --oneline`
