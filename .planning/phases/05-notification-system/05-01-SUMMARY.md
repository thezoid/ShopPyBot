---
phase: 05-notification-system
plan: 01
subsystem: notifications-foundation
tags:
  - python
  - notifications
  - abc
  - pydantic
  - sqlite
  - migration
  - test-infra
  - wave-0
dependency_graph:
  requires:
    - phase-04-async-orchestrator (TaskGroup, _connect context manager)
    - plugin_base.py (RetailerPlugin pattern mirrored by Notifier ABC)
    - config_schema.AppConfig (extended with notifications field)
  provides:
    - notifier_base.Notifier (ABC) + NotificationEvent (frozen dataclass)
    - config_schema.NotificationsConfig + 4 channel sub-models
    - models.should_notify / mark_notified / _migrate_add_last_notified_at
    - fakeNotifierFactory pytest fixture
    - 8 test files (2 GREEN regression nets, 6 RED Wave 1/2 targets)
  affects:
    - all of Wave 1 (Plans 05-02..05-05) subclass Notifier
    - Wave 2 (Plan 05-06) consumes should_notify/mark_notified + NotificationsConfig
tech_stack:
  added:
    - twilio==9.10.9 (pip)
  patterns:
    - ABC + frozen dataclass for typed event payloads
    - Idempotent SQLite ALTER TABLE via PRAGMA table_info precheck
    - Pydantic env-only secret surface (fields ABSENT from schema)
key_files:
  created:
    - notifier_base.py
    - tests/test_notifier_base.py
    - tests/test_models_notification_dedup.py
    - tests/test_notifier_registry.py
    - tests/test_notification_writer.py
    - tests/test_notifiers_sound.py
    - tests/test_notifiers_discord.py
    - tests/test_notifiers_email.py
    - tests/test_notifiers_sms.py
  modified:
    - config_schema.py
    - models.py
    - requirements.txt
    - sample.config.yml
    - tests/conftest.py
decisions:
  - "Notifier ABC mirrors RetailerPlugin: send abstract async, shutdown non-abstract async no-op"
  - "Secrets (Discord webhook, SMTP password, Twilio creds) deliberately ABSENT from Pydantic schema; env-var only (SEC-01)"
  - "ALTER TABLE migration guarded by PRAGMA table_info precheck (CONTEXT pitfall 7); idempotent across fresh-install + legacy-v1 + re-init paths"
  - "Dedup helpers (should_notify, mark_notified) use Phase 4 _connect() context manager; no raw sqlite3.connect"
  - "twilio==9.10.9 (latest stable verified per RESEARCH Q3) appended after pytest-asyncio==1.3.0"
  - "SoundNotifierConfig defaults enabled=True (preserves pre-Phase-5 behavior); all others default enabled=False"
metrics:
  duration_minutes: 4
  completed: 2026-05-15
  tasks_completed: 2
  files_changed: 14
---

# Phase 5 Plan 01: Foundation and RED Skeletons Summary

Foundation Wave 0 ships the Notifier ABC + frozen NotificationEvent dataclass, the NotificationsConfig Pydantic schema with env-only secret surface, the idempotent last_notified_at migration plus should_notify and mark_notified helpers, the twilio==9.10.9 pin, the sample.config.yml notifications block with the SMS two-lock warning, the fakeNotifierFactory fixture, and 8 test skeleton files (2 GREEN regression nets + 6 RED targets) that Waves 1 and 2 drive to GREEN.

## What Shipped

### Notifier contract (notifier_base.py)

`Notifier(ABC)` with class attributes `name: str = ""` and `enabled: bool = False`, one abstract coroutine `async def send(self, event: NotificationEvent) -> None`, and a non-abstract default `async def shutdown(self) -> None` returning None. `NotificationEvent` is a `@dataclass(frozen=True)` with `item_name`, `url`, `platform`, `timestamp` (tz-aware UTC), `action: Literal["detected", "purchased"]`. Module exports `NOTIFIER_API_VERSION = 1`.

### Config schema (config_schema.py)

Five new Pydantic models inserted between `AppSettings` and `AppConfig`:

- `SoundNotifierConfig(enabled=True)` (only channel defaulted on)
- `DiscordNotifierConfig(enabled=False)` (webhook_url NOT in schema; env only)
- `EmailNotifierConfig(enabled=False, from_addr, to_addr, smtp_host, smtp_port=587, smtp_user)` (smtp_password NOT in schema)
- `SmsNotifierConfig(enabled=False, to)` (sid/token/from-number NOT in schema)
- `NotificationsConfig(restock_window_seconds=600 [0..86400], sound, discord, email, sms)`

`AppConfig` gains `notifications: NotificationsConfig = NotificationsConfig()`. `extra=forbid` preserved on AppConfig, so any user attempt to put secrets in YAML fails at startup.

### Models migration (models.py)

CREATE TABLE now includes `last_notified_at TIMESTAMP NULL`. `_column_exists(conn, table, column)` + `_migrate_add_last_notified_at(conn)` provide the idempotent ALTER TABLE for legacy v1 databases. `initialize_db` calls the migration after CREATE TABLE. `should_notify(link, restock_window_seconds) -> bool` returns True for NULL or out-of-window timestamps with tz-aware UTC arithmetic; `mark_notified(link)` sets CURRENT_TIMESTAMP via parameterized SQL. Both helpers use `with _connect() as conn:`.

### Sample config (sample.config.yml)

Top-level `notifications:` block with restock_window_seconds, per-channel `enabled` flags, email connection details, SMS recipient placeholder, and explicit comments naming the env vars (SHOPBOT_DISCORD_WEBHOOK_URL, SHOPBOT_SMTP_PASSWORD, SHOPBOT_ENABLE_SMS, SHOPBOT_TWILIO_*) plus the SECURITY.md billing-risk pointer.

### Test infra

`tests/conftest.py` gains `fakeNotifierFactory` (parallel to `fakePluginFactory`): builds Notifier subclasses with configurable `name`, `enabled`, `sendRaises`, and `sendRecorder`.

### Test files

| File | State today | Drives |
|------|-------------|--------|
| test_notifier_base.py | GREEN (6 tests) | Regression net for Task 1 ABC contract |
| test_models_notification_dedup.py | GREEN (7 tests) | Regression net for NOTIF-02 helpers |
| test_notifier_registry.py | RED (collection ImportError) | Plan 05-02 |
| test_notification_writer.py | RED (collection ImportError) | Plan 05-06 |
| test_notifiers_sound.py | RED (collection ImportError) | Plan 05-02 |
| test_notifiers_discord.py | RED (collection ImportError) | Plan 05-03 |
| test_notifiers_email.py | RED (collection ImportError) | Plan 05-04 |
| test_notifiers_sms.py | RED (collection ImportError) | Plan 05-05 |

## Verification Results

- `pip show twilio` -> Version: 9.10.9
- `python -c "from notifier_base import Notifier, NotificationEvent, NOTIFIER_API_VERSION; print(NOTIFIER_API_VERSION)"` -> `1`
- ABC inspection: `Notifier.send` and `Notifier.shutdown` are coroutine functions
- `NotificationsConfig()` defaults verified: restock_window_seconds=600, sound.enabled=True, discord/email/sms.enabled=False, email.smtp_port=587
- Env-only secret surface verified: `smtp_password` NOT in EmailNotifierConfig.model_fields, `webhook_url` NOT in DiscordNotifierConfig.model_fields, `account_sid` NOT in SmsNotifierConfig.model_fields
- `python -c "import yaml; yaml.safe_load(open('sample.config.yml'))"` succeeds
- `pytest -q tests/test_notifier_base.py tests/test_models_notification_dedup.py` -> 13 passed
- `pytest tests/test_notifier_registry.py tests/test_notification_writer.py tests/test_notifiers_sound.py tests/test_notifiers_discord.py tests/test_notifiers_email.py tests/test_notifiers_sms.py` -> 6 collection errors (zero PASS) as required
- Full pre-existing suite (excluding new RED files and pre-existing deferred test_utils.py): 209 passed

## Deviations from Plan

None. Plan executed exactly as written. Plan called for "Eight RED skeleton test files" while explicitly noting two of them (test_notifier_base + test_models_notification_dedup) are GREEN-on-day-zero regression nets and the remaining six are the RED targets; that is what landed.

## Commits

| Task | Hash | Message |
|------|------|---------|
| 1 | 2b375b3 | feat(05-01): Notifier ABC + NotificationsConfig + last_notified_at migration + twilio pin |
| 2 | 873102b | test(05-01): RED skeletons + Wave 0 regression nets for Phase 5 notifications |

## TDD Gate Compliance

Plan type is `execute` (not plan-level `tdd`), so the strict RED-then-GREEN gate ordering does not apply at the plan level. Per-task TDD applied: Task 1 ships the foundation + a regression net that PASSES on day zero; Task 2 ships the test skeletons. Six of the eight new test files are RED-by-design (collection ImportError on symbols arriving in Plans 05-02..05-06); two are GREEN regression nets per the plan's explicit instruction.

## Known Stubs

None. All shipped code paths are wired end-to-end. The six RED test files reference symbols that do not yet exist (notifier_registry.discover_notifiers, main.notification_writer, notifiers.shopbot_notifier_*) but these are deliberate RED targets documented in the plan; downstream Wave 1/2 plans deliver those symbols.

## Threat Flags

None. The threat surface introduced by this plan (NotificationsConfig schema + sample.config.yml comment block + ALTER TABLE migration + NotificationEvent dataclass) is fully covered by the plan's threat_model:

- T-05-01-SECRET-IN-CONFIG mitigated: secret fields (smtp_password, webhook_url, account_sid, auth_token, from_number) are ABSENT from the Pydantic schema; extra=forbid causes startup failure if a user tries to add them to YAML.
- T-05-01-MIGRATION-DATA-LOSS mitigated: _migrate_add_last_notified_at uses PRAGMA table_info precheck before ALTER TABLE; rerun is a no-op.
- T-05-01-FROZEN-EVENT-MUT mitigated: `@dataclass(frozen=True)` raises FrozenInstanceError on assignment.
- T-05-01-CVV-EQUIVALENT mitigated: sample.config.yml SMS block names both SHOPBOT_ENABLE_SMS=true and SECURITY.md.

## Self-Check: PASSED

Files verified present:
- FOUND: notifier_base.py
- FOUND: config_schema.py (extended with NotificationsConfig)
- FOUND: models.py (extended with should_notify, mark_notified, _migrate_add_last_notified_at)
- FOUND: requirements.txt (twilio==9.10.9 line)
- FOUND: sample.config.yml (notifications block)
- FOUND: tests/conftest.py (fakeNotifierFactory)
- FOUND: tests/test_notifier_base.py
- FOUND: tests/test_models_notification_dedup.py
- FOUND: tests/test_notifier_registry.py
- FOUND: tests/test_notification_writer.py
- FOUND: tests/test_notifiers_sound.py
- FOUND: tests/test_notifiers_discord.py
- FOUND: tests/test_notifiers_email.py
- FOUND: tests/test_notifiers_sms.py

Commits verified:
- FOUND: 2b375b3 (Task 1)
- FOUND: 873102b (Task 2)
