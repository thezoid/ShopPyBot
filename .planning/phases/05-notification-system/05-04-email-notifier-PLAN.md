---
phase: 05-notification-system
plan: 04
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - notifiers/shopbot_notifier_email.py
  - tests/test_notifiers_email.py
autonomous: true
requirements:
  - NOTIF-05
tags:
  - python
  - notifications
  - email
  - smtp
  - starttls
  - wave-1

must_haves:
  truths:
    - "notifiers/shopbot_notifier_email.py defines `class EmailNotifier(Notifier)` with class attribute `name = 'email'`"
    - "EmailNotifier.__init__ reads `SHOPBOT_SMTP_PASSWORD` env var via `os.environ.get` ONCE at instantiation (CONTEXT pitfall #4). Reading env vars inside send() is FORBIDDEN — verified via AST grep"
    - "EmailNotifier.__init__ accepts `sub_config: EmailNotifierConfig, app_config` keyword args matching notifier_registry._instantiate contract"
    - "When sub_config.enabled=True but ANY of {smtp_host, smtp_user, from_addr, to_addr, env SHOPBOT_SMTP_PASSWORD} is missing/empty: __init__ sets self.enabled=False AND emits a WARNING via writeLog naming which field is missing"
    - "When sub_config.enabled=False: __init__ sets self.enabled=False quietly (no warning)"
    - "When all required fields + env present: self.enabled=True; the password is held in `self._password` (instance attr) and NEVER reread"
    - "EmailNotifier.send body uses `await asyncio.to_thread(self._send_smtp, message)` — no blocking smtplib calls in the async path"
    - "_send_smtp routes by smtp_port: port=465 -> use `smtplib.SMTP_SSL(host, 465, timeout=15)` then login+send_message (no starttls call); any other port -> use `smtplib.SMTP(host, port, timeout=15)` then `ehlo() -> starttls() -> ehlo() -> login -> send_message` (RESEARCH Q2 port-routing)"
    - "_send_smtp uses `with smtplib.SMTP(...) as s:` (or SMTP_SSL) so the connection is properly closed even on exception (per-send connection per RESEARCH Q2; no pooling)"
    - "_build_message returns a `MIMEMultipart('alternative')` with Subject `[ShopPyBot] {platform}: {item_name}`, From=from_addr, To=to_addr, and a single MIMEText body containing item name + platform + action + URL + timestamp ISO 8601"
    - "EmailNotifier MUST NOT log the SMTP password (RESEARCH Q11.16). AST grep walks writeLog Call args and asserts no reference to self._password"
    - "EmailNotifier MUST NOT include smtp_password as a Pydantic field anywhere (verified by Plan 05-01; this plan checks `'smtp_password' not in EmailNotifierConfig.model_fields` in a regression test)"
    - "All RED tests in tests/test_notifiers_email.py from Plan 05-01 now PASS"
    - "Full pytest suite remains green across Phase 1/2/3/4/5"
  artifacts:
    - path: "notifiers/shopbot_notifier_email.py"
      provides: "EmailNotifier (NOTIF-05) with STARTTLS-587 default + SMTP_SSL-465 alt + MIME multipart message"
      contains: "class EmailNotifier"
      min_lines: 80
    - path: "tests/test_notifiers_email.py"
      provides: "GREEN tests for NOTIF-05 (STARTTLS sequence, SSL routing, MIME headers, env password, password-not-logged)"
  key_links:
    - from: "notifiers/shopbot_notifier_email.py"
      to: "os.environ.get"
      via: "SHOPBOT_SMTP_PASSWORD read once in __init__"
      pattern: "os\\.environ\\.get\\([\"']SHOPBOT_SMTP_PASSWORD"
    - from: "EmailNotifier.send"
      to: "asyncio.to_thread"
      via: "wraps _send_smtp"
      pattern: "to_thread\\(.*_send_smtp"
    - from: "_send_smtp"
      to: "smtplib.SMTP / smtplib.SMTP_SSL"
      via: "port-driven routing"
      pattern: "smtplib\\.SMTP(_SSL)?"
---

<objective>
Wave 1 (parallel-safe): ship the Email/SMTP notifier (NOTIF-05). Reads `SHOPBOT_SMTP_PASSWORD` once at `__init__`; builds a MIME multipart message from a `NotificationEvent`; sends via stdlib `smtplib` wrapped in `asyncio.to_thread` with STARTTLS on port 587 (default) or implicit SSL on port 465 (alt). Flip RED tests in `tests/test_notifiers_email.py` to GREEN.

Purpose: Email is the primary fallback channel when Discord is unavailable (corporate networks block webhook URLs). Stdlib `smtplib` keeps the dependency surface at +1 across the whole phase (only `twilio`). Per-send connection avoids pool-management complexity at v1's < 1 send/min/channel rate.

Output: notifiers/shopbot_notifier_email.py + GREEN test file.
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
@tests/test_notifiers_email.py
</context>

<interfaces>
Target `notifiers/shopbot_notifier_email.py`:

```python
"""Email/SMTP notifier (NOTIF-05).

Sends a MIME multipart message via smtplib. Defaults to port 587 + STARTTLS
(RFC 6409 modern submission). Port 465 selects implicit SMTPS via SMTP_SSL.
Password from SHOPBOT_SMTP_PASSWORD env var — never config.yml (SEC-01).
"""
import asyncio
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from logger import writeLog
from notifier_base import Notifier, NotificationEvent

_SMTP_TIMEOUT_SECONDS = 15


class EmailNotifier(Notifier):
    name = "email"

    def __init__(self, *, sub_config, app_config) -> None:
        self._password = os.environ.get("SHOPBOT_SMTP_PASSWORD", "")
        wantedEnabled = bool(sub_config and sub_config.enabled)
        if not wantedEnabled:
            self.enabled = False
            return
        missing = _validate(sub_config, self._password)
        if missing:
            writeLog(
                f"Email notifier: missing required setting(s): {missing}; disabling.",
                "WARNING",
            )
            self.enabled = False
            return
        self._host = sub_config.smtp_host
        self._port = sub_config.smtp_port
        self._user = sub_config.smtp_user
        self._from = sub_config.from_addr
        self._to = sub_config.to_addr
        self.enabled = True

    async def send(self, event: NotificationEvent) -> None:
        message = _build_message(event, self._from, self._to)
        await asyncio.to_thread(self._send_smtp, message)

    def _send_smtp(self, message) -> None:
        if self._port == 465:
            with smtplib.SMTP_SSL(
                self._host, self._port, timeout=_SMTP_TIMEOUT_SECONDS
            ) as s:
                s.login(self._user, self._password)
                s.send_message(message)
        else:
            with smtplib.SMTP(
                self._host, self._port, timeout=_SMTP_TIMEOUT_SECONDS
            ) as s:
                s.ehlo()
                s.starttls()
                s.ehlo()
                s.login(self._user, self._password)
                s.send_message(message)


def _validate(sub_config, password: str) -> str:
    missing = []
    if not sub_config.smtp_host:
        missing.append("smtp_host")
    if not sub_config.smtp_user:
        missing.append("smtp_user")
    if not sub_config.from_addr:
        missing.append("from_addr")
    if not sub_config.to_addr:
        missing.append("to_addr")
    if not password:
        missing.append("SHOPBOT_SMTP_PASSWORD env var")
    return ", ".join(missing)


def _build_message(event, from_addr: str, to_addr: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[ShopPyBot] {event.platform}: {event.item_name}"
    msg["From"] = from_addr
    msg["To"] = to_addr
    body = (
        f"Item: {event.item_name}\n"
        f"Platform: {event.platform}\n"
        f"Action: {event.action}\n"
        f"URL: {event.url}\n"
        f"Time: {event.timestamp.isoformat()}\n"
    )
    msg.attach(MIMEText(body, "plain"))
    return msg
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement EmailNotifier (NOTIF-05) and drive RED tests to GREEN</name>
  <files>notifiers/shopbot_notifier_email.py, tests/test_notifiers_email.py</files>
  <read_first>
    - notifier_base.py (Notifier ABC, NotificationEvent dataclass)
    - config_schema.py (EmailNotifierConfig fields)
    - tests/test_notifiers_email.py (RED tests from Plan 05-01)
    - .planning/phases/05-notification-system/05-RESEARCH.md Q2 (SMTP STARTTLS vs SSL, MIME builder)
    - .planning/phases/05-notification-system/05-RESEARCH.md Q6 (test pattern for monkeypatching smtplib)
  </read_first>
  <behavior>
    - `from notifiers.shopbot_notifier_email import EmailNotifier` succeeds.
    - `inspect.iscoroutinefunction(EmailNotifier.send) is True`.
    - With all required fields + env SHOPBOT_SMTP_PASSWORD set: `instance.enabled is True`.
    - With env absent: `instance.enabled is False` AND a WARNING references `SHOPBOT_SMTP_PASSWORD`.
    - With sub_config.smtp_host=None (or empty): `instance.enabled is False` AND WARNING names `smtp_host`.
    - With sub_config.enabled=False: `instance.enabled is False` AND NO warning fires.
    - send() on port=587 routes through `smtplib.SMTP` and triggers `ehlo -> starttls -> ehlo -> login -> send_message` in order.
    - send() on port=465 routes through `smtplib.SMTP_SSL` and triggers `login -> send_message` (NO starttls).
    - The MIME message has Subject == `[ShopPyBot] {platform}: {item_name}`, From == from_addr, To == to_addr, body contains item_name + URL + action + timestamp.iso.
    - The password is captured at __init__: changing env after init does not change `instance._password`.
    - AST grep on writeLog calls: no Call argument references `self._password` (via Name or Attribute node).
    - All RED tests in tests/test_notifiers_email.py flip to GREEN.
  </behavior>
  <action>
    1. Create `notifiers/shopbot_notifier_email.py` with the full contents from <interfaces>. Methods stay < 30 lines. File stays < 200 lines.

    2. Flip `tests/test_notifiers_email.py` to GREEN. Build test infrastructure:
       - `FakeSmtp` class implementing context-manager protocol (`__init__(host, port, timeout)`, `__enter__/__exit__`, `ehlo()`, `starttls()`, `login(u, p)`, `send_message(msg)`). Each method appends to a shared `calls` list with its name + args.
       - `FakeSmtpSsl` mirroring FakeSmtp but for SMTP_SSL (no starttls method).
       - Use `monkeypatch.setattr("notifiers.shopbot_notifier_email.smtplib.SMTP", FakeSmtp)` and `monkeypatch.setattr("notifiers.shopbot_notifier_email.smtplib.SMTP_SSL", FakeSmtpSsl)`.
       - Build EmailNotifierConfig instances with explicit fields (don't use defaults for required fields).
       - Use `monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "secretpw")`.

    3. Test cases (matching the RED skeleton from Plan 05-01):
       - test_emailNotifierImportable: import succeeds.
       - test_starttlsOn587: port=587; after send, recorded calls include ["ehlo", "starttls", "ehlo", "login", "send_message"] in order.
       - test_smtpsslOn465: port=465; after send, recorded calls include ["login", "send_message"] and do NOT include "starttls".
       - test_passwordFromEnv: delenv before init; assert instance.enabled is False + WARNING fires.
       - test_messageHeaders: send; assert sent message Subject startswith "[ShopPyBot]" and contains platform + item_name; From/To match config.
       - test_passwordNotLogged: parse the notifier source file; walk writeLog calls; assert no argument references `self._password`.
       - test_disabledIfConfigOff: sub_config.enabled=False; assert instance.enabled is False + NO warning.
       - test_disabledIfHostMissing: sub_config.smtp_host=None; assert enabled is False + WARNING names "smtp_host".
       - test_smtpPasswordAbsentFromSchema: regression — `assert "smtp_password" not in EmailNotifierConfig.model_fields`.

    4. Run `rtk pytest -q tests/test_notifiers_email.py`. All GREEN.

    5. Run `rtk pytest -x -q --ignore=tests/test_notifiers_discord.py --ignore=tests/test_notifiers_sms.py --ignore=tests/test_notification_writer.py`. Pre-existing + this plan + 05-02 (if landed) green; Wave 1 sibling RED files remain RED.
  </action>
  <verify>
    <automated>python -c "from notifiers.shopbot_notifier_email import EmailNotifier; from notifier_base import Notifier; assert issubclass(EmailNotifier, Notifier)"</automated>
    <automated>rtk grep -n "os.environ.get.*SHOPBOT_SMTP_PASSWORD" notifiers/shopbot_notifier_email.py</automated>
    <automated>rtk grep -c "os.environ" notifiers/shopbot_notifier_email.py</automated>
    <automated>rtk grep -n "smtplib.SMTP_SSL\|smtplib.SMTP" notifiers/shopbot_notifier_email.py</automated>
    <automated>rtk pytest -q tests/test_notifiers_email.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_notifiers_discord.py --ignore=tests/test_notifiers_sms.py --ignore=tests/test_notification_writer.py</automated>
  </verify>
  <acceptance_criteria>
    - notifiers/shopbot_notifier_email.py exists with EmailNotifier subclass
    - Env var read exactly once at __init__ (rtk grep -c "os.environ" returns 1)
    - Port 587 uses SMTP + STARTTLS sequence; port 465 uses SMTP_SSL with no starttls
    - MIME multipart message structure matches NOTIF-05 spec
    - Password never appears in any writeLog argument (AST verified)
    - smtp_password absent from EmailNotifierConfig.model_fields
    - All tests in tests/test_notifiers_email.py GREEN
    - Pre-existing suite green
  </acceptance_criteria>
  <done>NOTIF-05 implemented. Wave 2 notification_writer will pick up EmailNotifier via discover_notifiers.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| SMTP password (env -> code) | Read once at __init__; must not leak via logs |
| smtp_host / smtp_user (config.yml) | User-controlled config; injected into SMTP handshake |
| Email recipient (to_addr) | Phase-5-controlled; could be misconfigured to wrong address |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-04-PW-IN-LOG | Information Disclosure | EmailNotifier.writeLog calls | mitigate | AST grep test enforces no self._password reference in any writeLog Call; writeLog WARNINGs reference only field names like "SHOPBOT_SMTP_PASSWORD env var" not the value |
| T-05-04-PW-IN-CONFIG | Information Disclosure | config_schema.EmailNotifierConfig | mitigate | smtp_password field absent from Pydantic schema; extra=forbid causes startup fail if user puts it in YAML |
| T-05-04-TLS-DOWNGRADE | Cryptography | _send_smtp | mitigate | STARTTLS unconditional on non-465 ports; no `starttls(context=None)` workaround; smtplib uses default SSL context |
| T-05-04-SMTP-HANG | Denial of Service | _send_smtp | mitigate | 15s timeout on every smtplib.SMTP / SMTP_SSL constructor |
| T-05-04-EMAIL-MISROUTE | Information Disclosure | _build_message To header | accept | User-controlled to_addr; misconfiguration is user error; v1 accepts this |
</threat_model>

<verification>
- `python -c "from notifiers.shopbot_notifier_email import EmailNotifier; from notifier_base import Notifier; assert issubclass(EmailNotifier, Notifier)"`
- `rtk grep -c "os.environ" notifiers/shopbot_notifier_email.py` returns 1 (single read at __init__)
- `rtk pytest -q tests/test_notifiers_email.py` shows all GREEN
- `rtk pytest -x -q --ignore=tests/test_notifiers_discord.py --ignore=tests/test_notifiers_sms.py --ignore=tests/test_notification_writer.py` green
</verification>

<success_criteria>
- EmailNotifier subclass of Notifier present in notifiers/
- SMTP password env-var-only, read once at __init__
- Port 587 + STARTTLS default; port 465 + SMTP_SSL alt
- MIME multipart message conforms to NOTIF-05 spec
- Password never logged
- tests/test_notifiers_email.py fully GREEN
</success_criteria>

<output>
After completion, create `.planning/phases/05-notification-system/05-04-SUMMARY.md`
</output>
