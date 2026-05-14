---
phase: 05-notification-system
plan: 05
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - notifiers/shopbot_notifier_sms.py
  - tests/test_notifiers_sms.py
autonomous: true
requirements:
  - NOTIF-06
tags:
  - python
  - notifications
  - sms
  - twilio
  - two-lock
  - opt-in
  - wave-1

must_haves:
  truths:
    - "notifiers/shopbot_notifier_sms.py defines `class SmsNotifier(Notifier)` with class attribute `name = 'sms'`"
    - "SmsNotifier.__init__ enforces D-04 two-lock opt-in: BOTH `sub_config.enabled is True` AND env `SHOPBOT_ENABLE_SMS == 'true'` (case-insensitive equality on the literal string 'true') are required. Failing either lock sets `self.enabled = False`"
    - "Two-lock failure log MUST distinguish 'config off' vs 'env off' vs 'both off' (CONTEXT pitfall #10 + RESEARCH Q11.7). One of three distinct WARNING messages fires based on which surface is missing"
    - "All Twilio credentials read from env vars ONCE at __init__ (CONTEXT pitfall #4): `SHOPBOT_TWILIO_ACCOUNT_SID`, `SHOPBOT_TWILIO_AUTH_TOKEN`, `SHOPBOT_TWILIO_FROM`. Reading env vars inside send() is FORBIDDEN — verified via AST grep"
    - "When BOTH locks pass but any Twilio env var is missing: __init__ sets self.enabled=False AND a WARNING distinguishes which env var is missing"
    - "When `app_config.debug.test_mode is True`: __init__ sets self.enabled=False AND logs INFO 'test_mode: SMS notifier disabled' (RESEARCH Q3 test credentials path + Q11.13)"
    - "When all locks + envs pass AND test_mode is False: self.enabled=True; the Twilio `Client(account_sid, auth_token)` is constructed ONCE at __init__ and stored as `self._client`"
    - "SmsNotifier.send body uses `await asyncio.to_thread(self._send_sms, event)` — no blocking twilio calls in the async path"
    - "_send_sms calls `self._client.messages.create(to=self._to, from_=self._from, body=...)`. The `from_=` keyword (trailing underscore) is mandatory (Python reserved word); NEVER `from=` or `from_addr=` (CONTEXT pitfall #5 + RESEARCH Q11.12). Verified via AST grep on the file"
    - "_send_sms catches `twilio.base.exceptions.TwilioRestException` specifically and re-raises with a sanitized message that DOES NOT include the auth token, account SID, or message body details — only the Twilio error code + status (RESEARCH Q11 + threat model T-05-05-CRED-LEAK)"
    - "SmsNotifier MUST NOT log the auth_token, account_sid, from_number, or message body in any writeLog call (RESEARCH Q11.16). AST grep walks writeLog Call args and asserts no reference to those instance attributes"
    - "SmsNotifier MUST NOT include account_sid, auth_token, or from_number as Pydantic fields anywhere (verified by Plan 05-01; this plan checks `not any(k in SmsNotifierConfig.model_fields for k in ['account_sid','auth_token','from_number'])` in a regression test)"
    - "All RED tests in tests/test_notifiers_sms.py from Plan 05-01 now PASS"
    - "Full pytest suite remains green across Phase 1/2/3/4/5"
  artifacts:
    - path: "notifiers/shopbot_notifier_sms.py"
      provides: "SmsNotifier (NOTIF-06) with two-lock opt-in + Twilio SDK call + test_mode disable"
      contains: "class SmsNotifier"
      min_lines: 70
    - path: "tests/test_notifiers_sms.py"
      provides: "GREEN tests for NOTIF-06 (two-lock pass/fail/distinguishable, test_mode disable, from_= kwarg, creds-not-logged)"
  key_links:
    - from: "notifiers/shopbot_notifier_sms.py"
      to: "os.environ.get"
      via: "SHOPBOT_ENABLE_SMS + SHOPBOT_TWILIO_* read once in __init__"
      pattern: "os\\.environ\\.get\\([\"']SHOPBOT_"
    - from: "SmsNotifier.send"
      to: "asyncio.to_thread"
      via: "wraps _send_sms"
      pattern: "to_thread\\(.*_send_sms"
    - from: "_send_sms"
      to: "twilio.rest.Client.messages.create"
      via: "from_= keyword (trailing underscore)"
      pattern: "from_\\s*="
---

<objective>
Wave 1 (parallel-safe): ship the SMS/Twilio notifier (NOTIF-06) with the strict two-lock opt-in from CONTEXT D-04. BOTH `notifications.sms.enabled: true` in config AND env `SHOPBOT_ENABLE_SMS=true` must be set. Either alone disables SMS. All Twilio credentials live in env vars only. When `debug.test_mode is True`, SMS is forcibly disabled. The notifier uses the official `twilio` SDK (pinned 9.10.9 by Plan 05-01) and calls `messages.create(..., from_=..., ...)` with the trailing-underscore keyword. Flip RED tests in `tests/test_notifiers_sms.py` to GREEN.

Purpose: SMS is the highest-risk channel — every send costs money. CONTEXT D-04's two-lock model prevents three accidental-charge scenarios: copied sample.config.yml with enabled=true baked in, shared shell with env exported, and test runs with real creds. The two-lock failure log MUST distinguish which surface is missing so the user can debug without re-reading code.

Output: notifiers/shopbot_notifier_sms.py + GREEN test file.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/05-notification-system/05-CONTEXT.md
@.planning/phases/05-notification-system/05-RESEARCH.md
@.planning/phases/05-notification-system/05-01-foundation-and-red-skeletons-PLAN.md
@notifier_base.py
@config_schema.py
@logger.py
@tests/conftest.py
@tests/test_notifiers_sms.py
</context>

<interfaces>
Target `notifiers/shopbot_notifier_sms.py`:

```python
"""SMS/Twilio notifier (NOTIF-06).

Two-lock opt-in (CONTEXT D-04): BOTH notifications.sms.enabled=True in config
AND env SHOPBOT_ENABLE_SMS=='true' are required. Either alone keeps SMS
disabled. Twilio credentials come from env vars only (SEC-01). In test_mode,
SMS is forcibly disabled to prevent accidental charges during test runs.

All env vars and the Twilio Client are constructed ONCE at __init__. Reading
env vars or rebuilding the client inside send() is FORBIDDEN.
"""
import asyncio
import os

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from logger import writeLog
from notifier_base import Notifier, NotificationEvent


class SmsNotifier(Notifier):
    name = "sms"

    def __init__(self, *, sub_config, app_config) -> None:
        # Single env read pass
        envEnable = os.environ.get("SHOPBOT_ENABLE_SMS", "").strip().lower() == "true"
        self._account_sid = os.environ.get("SHOPBOT_TWILIO_ACCOUNT_SID", "")
        self._auth_token = os.environ.get("SHOPBOT_TWILIO_AUTH_TOKEN", "")
        self._from = os.environ.get("SHOPBOT_TWILIO_FROM", "")

        configOn = bool(sub_config and sub_config.enabled)

        # Two-lock check with distinguishable failure reason (CONTEXT pitfall #10)
        if not configOn and not envEnable:
            writeLog(
                "SMS notifier disabled: both notifications.sms.enabled and "
                "SHOPBOT_ENABLE_SMS are off.",
                "INFO",
            )
            self.enabled = False
            return
        if not configOn:
            writeLog(
                "SMS notifier disabled: SHOPBOT_ENABLE_SMS=true but "
                "notifications.sms.enabled is false in config.",
                "WARNING",
            )
            self.enabled = False
            return
        if not envEnable:
            writeLog(
                "SMS notifier disabled: notifications.sms.enabled=true but "
                "SHOPBOT_ENABLE_SMS env var is not set to 'true'.",
                "WARNING",
            )
            self.enabled = False
            return

        # test_mode forces disable (RESEARCH Q3 + Q11.13)
        if getattr(app_config.debug, "test_mode", False):
            writeLog("test_mode: SMS notifier disabled.", "INFO")
            self.enabled = False
            return

        # Twilio creds presence check
        missingCreds = _missing_twilio_creds(
            self._account_sid, self._auth_token, self._from, sub_config.to
        )
        if missingCreds:
            writeLog(
                f"SMS notifier disabled: missing Twilio setting(s): {missingCreds}.",
                "WARNING",
            )
            self.enabled = False
            return

        self._to = sub_config.to
        self._client = Client(self._account_sid, self._auth_token)
        self.enabled = True

    async def send(self, event: NotificationEvent) -> None:
        await asyncio.to_thread(self._send_sms, event)

    def _send_sms(self, event: NotificationEvent) -> None:
        body = f"{event.platform} {event.action}: {event.item_name} {event.url}"
        try:
            self._client.messages.create(
                to=self._to,
                from_=self._from,
                body=body,
            )
        except TwilioRestException as e:
            # Sanitized re-raise: code + status only, no creds/body
            raise RuntimeError(
                f"Twilio send failed (code={e.code}, status={e.status})"
            ) from None


def _missing_twilio_creds(account_sid: str, auth_token: str, from_num: str, to_num) -> str:
    missing = []
    if not account_sid:
        missing.append("SHOPBOT_TWILIO_ACCOUNT_SID env var")
    if not auth_token:
        missing.append("SHOPBOT_TWILIO_AUTH_TOKEN env var")
    if not from_num:
        missing.append("SHOPBOT_TWILIO_FROM env var")
    if not to_num:
        missing.append("notifications.sms.to config value")
    return ", ".join(missing)
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement SmsNotifier with two-lock opt-in (NOTIF-06) and drive RED tests to GREEN</name>
  <files>notifiers/shopbot_notifier_sms.py, tests/test_notifiers_sms.py</files>
  <read_first>
    - notifier_base.py (Notifier ABC, NotificationEvent dataclass)
    - config_schema.py (SmsNotifierConfig fields — note creds ABSENT by SEC-01)
    - tests/test_notifiers_sms.py (RED tests from Plan 05-01)
    - .planning/phases/05-notification-system/05-CONTEXT.md D-04 (two-lock model, three accidental-charge scenarios)
    - .planning/phases/05-notification-system/05-RESEARCH.md Q3 (Twilio SDK minimal usage, from_= keyword, TwilioRestException)
    - .planning/phases/05-notification-system/05-RESEARCH.md Q6 (test pattern for monkeypatching Client)
  </read_first>
  <behavior>
    - `from notifiers.shopbot_notifier_sms import SmsNotifier` succeeds (twilio dep pinned by Plan 05-01).
    - `inspect.iscoroutinefunction(SmsNotifier.send) is True`.
    - With sub_config.enabled=False AND env SHOPBOT_ENABLE_SMS unset: instance.enabled is False; INFO log "both...off" fires.
    - With sub_config.enabled=False AND env SHOPBOT_ENABLE_SMS=true: instance.enabled is False; WARNING log distinguishes "SHOPBOT_ENABLE_SMS=true but notifications.sms.enabled is false".
    - With sub_config.enabled=True AND env unset: instance.enabled is False; WARNING distinguishes "notifications.sms.enabled=true but SHOPBOT_ENABLE_SMS env var is not set to 'true'".
    - With both locks pass + all Twilio env vars set + sub_config.to set + test_mode=False: instance.enabled is True; `self._client` is a real Twilio Client instance.
    - With both locks pass + test_mode=True: instance.enabled is False; INFO log "test_mode: SMS notifier disabled".
    - With both locks pass + missing SHOPBOT_TWILIO_ACCOUNT_SID: instance.enabled is False; WARNING names which env var is missing.
    - All env vars + creds read EXACTLY ONCE at __init__. Setting a different env value after instantiation does NOT change `instance._account_sid` or any related attribute.
    - AST grep on the file: `os.environ.get` appears only in __init__, NEVER inside send() or _send_sms().
    - AST grep on the file: the `messages.create` call uses keyword `from_=` (trailing underscore) — assert by walking the file's AST for the Call node with `messages.create` and verifying its `keywords` list contains an entry with `.arg == 'from_'`. Reject if `'from'` or `'from_addr'` appears in those kwargs.
    - AST grep on writeLog calls: no Call argument references `self._account_sid`, `self._auth_token`, `self._from`, or any message body variable.
    - On TwilioRestException from `messages.create`: send() raises `RuntimeError(f"Twilio send failed (code={e.code}, status={e.status})")` WITHOUT including auth_token / account_sid / item URL / message body.
    - Regression: `'account_sid' not in SmsNotifierConfig.model_fields` and `'auth_token' not in SmsNotifierConfig.model_fields` and `'from_number' not in SmsNotifierConfig.model_fields`.
    - All RED tests in tests/test_notifiers_sms.py flip to GREEN.
  </behavior>
  <action>
    1. Create `notifiers/shopbot_notifier_sms.py` with the full contents from <interfaces>. Methods stay < 30 lines. File stays < 200 lines.

    2. Flip `tests/test_notifiers_sms.py` to GREEN. Build test infrastructure:
       - `FakeMessages` class with `create(**kw)` recording the kwargs into a shared list.
       - `FakeTwilioClient(sid, token)` recording the SID/token; exposes `messages` as a FakeMessages instance.
       - `monkeypatch.setattr("notifiers.shopbot_notifier_sms.Client", FakeTwilioClient)`.
       - `monkeypatch.setenv` / `monkeypatch.delenv` for each lock test.
       - Build `SmsNotifierConfig` with explicit enabled + to.
       - Build app_config stub with `debug.test_mode` toggleable.

    3. Test cases (matching the RED skeleton from Plan 05-01):
       - test_smsNotifierImportable: import succeeds.
       - test_disabledIfBothOff: sub_config.enabled=False, no env; assert enabled is False AND INFO log "both...off" captured.
       - test_disabledIfConfigOff: sub_config.enabled=False, env SHOPBOT_ENABLE_SMS=true; assert enabled is False AND WARNING with "notifications.sms.enabled is false" substring.
       - test_disabledIfEnvOff: sub_config.enabled=True, no env; assert enabled is False AND WARNING with "SHOPBOT_ENABLE_SMS env var is not set" substring.
       - test_enabledWhenBothLocksPass: sub_config.enabled=True, env=true, all Twilio env vars set, test_mode=False; assert instance.enabled is True AND `instance._client` is a FakeTwilioClient AND FakeTwilioClient received the expected sid/token.
       - test_testModeDisablesSms: both locks pass, debug.test_mode=True; assert instance.enabled is False AND INFO "test_mode: SMS notifier disabled".
       - test_missingTwilioCredsDisables: both locks pass + missing SHOPBOT_TWILIO_ACCOUNT_SID; assert disabled + WARNING names the env var.
       - test_twilioFromUnderscore: AST grep — parse the file, locate the messages.create Call, assert its keywords list contains an arg named `from_` and NO arg named `from` or `from_addr`.
       - test_credsReadOnce: build instance with envs; delenv all; build a second instance with no envs; assert the first instance's `_account_sid` is unchanged AND the second instance is disabled (proves __init__ snapshot).
       - test_credsNotLogged: AST grep all writeLog Calls; assert no arg references `self._account_sid`, `self._auth_token`, `self._from`, or any body-containing variable.
       - test_twilioRestExceptionSanitized: monkeypatch FakeMessages.create to raise `TwilioRestException(status=401, uri='x', msg='secret in here', code=20003)`; await send; assert the raised RuntimeError message contains `code=20003` and `status=401` and does NOT contain "secret in here".
       - test_credsAbsentFromSchema: regression — `'account_sid'`, `'auth_token'`, `'from_number'` all absent from `SmsNotifierConfig.model_fields`.

    4. Run `rtk pytest -q tests/test_notifiers_sms.py`. All GREEN.

    5. Run `rtk pytest -x -q --ignore=tests/test_notifiers_discord.py --ignore=tests/test_notifiers_email.py --ignore=tests/test_notification_writer.py`. Pre-existing + this plan + 05-02 (if landed) green; Wave 1 sibling RED files remain RED.
  </action>
  <verify>
    <automated>python -c "from notifiers.shopbot_notifier_sms import SmsNotifier; from notifier_base import Notifier; assert issubclass(SmsNotifier, Notifier)"</automated>
    <automated>rtk grep -n "os.environ.get.*SHOPBOT_ENABLE_SMS\|os.environ.get.*SHOPBOT_TWILIO_" notifiers/shopbot_notifier_sms.py</automated>
    <automated>rtk grep -n "from_\s*=" notifiers/shopbot_notifier_sms.py</automated>
    <automated>rtk grep -c "os.environ" notifiers/shopbot_notifier_sms.py</automated>
    <automated>rtk pytest -q tests/test_notifiers_sms.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_notifiers_discord.py --ignore=tests/test_notifiers_email.py --ignore=tests/test_notification_writer.py</automated>
  </verify>
  <acceptance_criteria>
    - notifiers/shopbot_notifier_sms.py exists with SmsNotifier subclass
    - Two-lock check produces distinguishable WARNINGs for the three failure modes
    - test_mode=True forcibly disables SMS
    - Twilio SDK Client built ONCE at __init__
    - messages.create uses `from_=` keyword (AST-verified)
    - TwilioRestException re-raised with sanitized RuntimeError (no creds/body leak)
    - All Twilio env vars read at __init__, never in send/_send_sms
    - account_sid/auth_token/from_number absent from SmsNotifierConfig.model_fields
    - All tests in tests/test_notifiers_sms.py GREEN
    - Pre-existing suite green
  </acceptance_criteria>
  <done>NOTIF-06 implemented with the strict two-lock opt-in. Wave 2 notification_writer will pick up SmsNotifier via discover_notifiers; in test_mode it disables itself cleanly.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Twilio creds (env -> code) | account_sid, auth_token, from_number, ENABLE_SMS flag — all env-only; must not leak |
| SmsNotifierConfig.to (config.yml) | Recipient phone number; user-controlled; injected into messages.create |
| test_mode flag (app_config.debug) | Forces SMS disable; must be respected for cost containment |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-05-ACCIDENTAL-CHARGE | Tampering (cost) | SmsNotifier.__init__ | mitigate | Two-lock: BOTH config.enabled=true AND env SHOPBOT_ENABLE_SMS=true required; three accidental-charge scenarios blocked per CONTEXT D-04 rationale |
| T-05-05-CRED-LEAK | Information Disclosure | SmsNotifier writeLog + TwilioRestException handler | mitigate | AST grep test enforces no self._account_sid/_auth_token/_from in writeLog Calls; TwilioRestException re-raised as RuntimeError with code+status only |
| T-05-05-TEST-MODE-BLEED | Tampering (cost) | SmsNotifier.__init__ | mitigate | test_mode=True forces self.enabled=False even when both locks pass; INFO log fires |
| T-05-05-PYTHON-KEYWORD | Tampering (functional) | _send_sms messages.create call | mitigate | `from_=` (trailing underscore) is the only correct kwarg; AST grep test enforces |
| T-05-05-CRED-IN-CONFIG | Information Disclosure | config_schema.SmsNotifierConfig | mitigate | account_sid / auth_token / from_number ABSENT from Pydantic schema; extra=forbid causes startup fail if user puts them in YAML |
</threat_model>

<verification>
- `python -c "from notifiers.shopbot_notifier_sms import SmsNotifier; from notifier_base import Notifier; assert issubclass(SmsNotifier, Notifier)"`
- `rtk grep -c "os.environ" notifiers/shopbot_notifier_sms.py` returns 4 (one per env var read at __init__)
- `rtk grep -n "from_\s*=" notifiers/shopbot_notifier_sms.py` matches the messages.create call
- `rtk pytest -q tests/test_notifiers_sms.py` shows all GREEN
- `rtk pytest -x -q --ignore=tests/test_notifiers_discord.py --ignore=tests/test_notifiers_email.py --ignore=tests/test_notification_writer.py` green
</verification>

<success_criteria>
- SmsNotifier subclass of Notifier present in notifiers/
- Two-lock opt-in enforced with distinguishable failure messages
- test_mode forcibly disables SMS
- Twilio SDK used with from_= keyword
- All credentials env-var-only, read once at __init__
- TwilioRestException sanitized on re-raise
- tests/test_notifiers_sms.py fully GREEN
</success_criteria>

<output>
After completion, create `.planning/phases/05-notification-system/05-05-SUMMARY.md`
</output>
