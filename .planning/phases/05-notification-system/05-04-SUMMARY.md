---
phase: 05-notification-system
plan: 04
subsystem: email-notifier
tags:
  - python
  - notifications
  - email
  - smtp
  - starttls
  - wave-1
dependency_graph:
  requires:
    - notifier_base.Notifier + NotificationEvent (Plan 05-01)
    - config_schema.EmailNotifierConfig (Plan 05-01)
    - notifier_registry._instantiate kwargs contract (Plan 05-02)
    - stdlib smtplib + email.mime (no new deps)
  provides:
    - notifiers.shopbot_notifier_email.EmailNotifier (NOTIF-05)
    - MIME multipart message builder (_build_message)
    - Port-routed SMTP send (_send_smtp): 465 -> SMTP_SSL, else SMTP + STARTTLS
  affects:
    - Wave 2 (Plan 05-06 notification_writer) picks up EmailNotifier via discover_notifiers
tech_stack:
  added: []
  patterns:
    - asyncio.to_thread wrapping sync smtplib
    - Env-only secret surface (SHOPBOT_SMTP_PASSWORD captured once at __init__)
    - Port-driven TLS routing (465 implicit SSL, others STARTTLS)
    - MIMEMultipart('alternative') with MIMEText plain part
    - Per-send connection via `with smtplib.SMTP(...) as s:` (no pool)
    - AST grep test enforcing password never reaches writeLog argument
key_files:
  created:
    - notifiers/shopbot_notifier_email.py
  modified:
    - tests/test_notifiers_email.py (RED skeleton -> GREEN suite)
decisions:
  - "Password held as `self._password` (single underscore) to keep the AST grep regression test pattern simple while signaling private"
  - "Validation aggregated in `_validate()` helper returning a comma-joined string of missing field names; single WARNING enumerates all gaps instead of N separate warnings"
  - "Port routing: explicit `if self._port == 465: SMTP_SSL else: SMTP + STARTTLS` (matches RESEARCH Q2 default-587 modern submission)"
  - "STARTTLS sequence is exactly ehlo -> starttls -> ehlo -> login -> send_message; second ehlo is required by RFC 3207 after TLS handshake to refresh extensions"
  - "15s timeout on both SMTP and SMTP_SSL constructors (T-05-04-SMTP-HANG mitigation; worst-case writer block bounded)"
  - "Subject template `[ShopPyBot] {platform}: {item_name}` matches plan; plain-text body includes item_name + platform + action + url + ISO timestamp"
  - "GREEN tests use kwargs (`sub_config=...`) not the RED skeleton's positional form, matching Plan 05-02 registry contract (same precedent as 05-03)"
metrics:
  duration_minutes: 3
  completed: 2026-05-15
  tasks_completed: 1
  files_changed: 2
---

# Phase 5 Plan 04: Email Notifier Summary

EmailNotifier (NOTIF-05) ships as a Notifier subclass that sends a MIME multipart message via stdlib smtplib wrapped in asyncio.to_thread, with port-driven TLS routing (465 -> SMTP_SSL, else SMTP + STARTTLS) and SHOPBOT_SMTP_PASSWORD read once at __init__.

## One-liner

SMTP email notifier with env-only password surface, port-routed TLS (587 STARTTLS / 465 SSL), 15s timeout, and MIME multipart body.

## What Was Built

### `notifiers/shopbot_notifier_email.py` (96 lines)

- `EmailNotifier(Notifier)` with class attribute `name = "email"`
- `__init__(*, sub_config, app_config)` matching notifier_registry._instantiate contract
- Three-state enable logic:
  - sub_config.enabled is False -> quiet opt-out (self.enabled=False, no log)
  - sub_config.enabled is True + any required field missing -> self.enabled=False + single WARNING enumerating all missing fields by name (host, user, from, to, env var name)
  - sub_config.enabled is True + all fields + env present -> self.enabled=True; instance holds host, port, user, from, to, password
- `self._password` captured once at __init__; runtime env changes ignored
- `async send(event)` builds MIME message + awaits `asyncio.to_thread(self._send_smtp, message)`
- `_send_smtp(message)`:
  - port == 465: `with smtplib.SMTP_SSL(host, 465, timeout=15) as s: login + send_message`
  - else: `with smtplib.SMTP(host, port, timeout=15) as s: ehlo -> starttls -> ehlo -> login -> send_message`
- `_validate(sub_config, password)`: returns comma-joined string of missing fields ("" if all present)
- `_build_message(event, from_addr, to_addr)`: MIMEMultipart("alternative") with Subject `[ShopPyBot] {platform}: {item_name}`, From/To headers, plain-text MIMEText body containing item_name + platform + action + url + ISO timestamp

### `tests/test_notifiers_email.py` (GREEN, 12 tests)

- `test_emailNotifierImportable`: import + Notifier subclass check
- `test_sendIsCoroutine`: inspect.iscoroutinefunction check
- `test_starttlsOn587`: monkeypatch SMTP with _FakeSmtp; assert exact action sequence ["ehlo", "starttls", "ehlo", "login", "send_message"]
- `test_smtpsslOn465`: monkeypatch SMTP_SSL with _FakeSmtpSsl; assert ["login", "send_message"] and no starttls
- `test_passwordFromEnvAtInit`: env set, init, env changed after -> instance._password unchanged
- `test_passwordEnvMissingDisables`: delenv before init -> self.enabled is False
- `test_messageHeaders`: Subject startswith "[ShopPyBot]", contains platform + item_name; From/To match config; body contains item_name + url + action + ISO timestamp
- `test_passwordNotLogged`: AST walk over module source; for every writeLog Call, every arg subtree is checked - no Attribute node with attr "_password" allowed
- `test_disabledIfConfigOff`: sub_config.enabled=False -> self.enabled=False (no warning)
- `test_disabledIfHostMissing`: smtp_host=None -> self.enabled=False + WARNING fires
- `test_smtpPasswordAbsentFromSchema`: regression - smtp_password not in EmailNotifierConfig.model_fields
- `test_envReadExactlyOnceInSource`: source contains exactly one `os.environ` occurrence

## Threat Surface Mitigations (from PLAN threat_model)

| Threat ID | Disposition | Mitigation Landed |
|-----------|-------------|-------------------|
| T-05-04-PW-IN-LOG | mitigate | AST grep test_passwordNotLogged walks every writeLog Call and rejects any Attribute(attr="_password") subtree; WARNINGs reference only the env var name string, never the value |
| T-05-04-PW-IN-CONFIG | mitigate | smtp_password absent from EmailNotifierConfig (verified by test_smtpPasswordAbsentFromSchema); AppConfig extra=forbid hard-fails if user adds it to YAML |
| T-05-04-TLS-DOWNGRADE | mitigate | STARTTLS unconditional on non-465 ports; no context override; smtplib uses default SSL context; test_starttlsOn587 asserts exact ehlo->starttls->ehlo->login sequence |
| T-05-04-SMTP-HANG | mitigate | 15s `_SMTP_TIMEOUT_SECONDS` passed to both SMTP and SMTP_SSL constructors |
| T-05-04-EMAIL-MISROUTE | accept | User-controlled to_addr; misconfiguration is user error per plan disposition |

## Verification

- `python -c "from notifiers.shopbot_notifier_email import EmailNotifier; from notifier_base import Notifier; assert issubclass(EmailNotifier, Notifier)"` PASS
- `rg -c "os.environ" notifiers/shopbot_notifier_email.py` = 1 (single read at __init__)
- `rg "smtplib.SMTP_SSL|smtplib.SMTP" notifiers/shopbot_notifier_email.py` matches both code paths
- `rtk pytest -q tests/test_notifiers_email.py` -> 12 passed
- `rtk pytest -x -q --ignore=tests/test_notifiers_sms.py --ignore=tests/test_notification_writer.py --ignore=tests/test_utils.py` -> 251 passed (Wave 1 sibling RED files for SMS + writer remain RED for their own plans; pre-existing test_utils.py breakage excluded per 05-03 precedent)

## Deviations from Plan

### Plan Adjustments (vs RED skeleton in 05-01)

- RED skeleton called `EmailNotifier(_emailConfig(port=587))` with a single positional arg. The registry contract from Plan 05-02 requires `sub_config=...` / `app_config=...` kwargs. Per the same precedent set in Plan 05-03, the GREEN tests use the kwargs form. The EmailNotifier `__init__` signature matches DiscordNotifier exactly (`*, sub_config=None, app_config=None`).
- GREEN test file was a full rewrite of the RED skeleton (RED skeleton's `_FakeSmtp` was kept compatible; added `_FakeSmtpSsl` variant that raises if starttls is ever called against it, hardening the 465-no-starttls assertion).

### Auto-fixed Issues

None.

## Authentication Gates

None.

## Known Stubs

None.

## Commits

| Hash | Message | Files |
|------|---------|-------|
| ce81a35 | feat(05-04): EmailNotifier (NOTIF-05) STARTTLS-587 + SSL-465 + MIME multipart | notifiers/shopbot_notifier_email.py (new), tests/test_notifiers_email.py (RED -> GREEN) |

## Self-Check: PASSED

- notifiers/shopbot_notifier_email.py exists (96 lines, well under 200-line cap)
- tests/test_notifiers_email.py rewritten to GREEN (12 tests, all passing)
- Commit ce81a35 present in git log
- All plan success criteria satisfied
- STATE.md and ROADMAP.md untouched (per execution directive)
