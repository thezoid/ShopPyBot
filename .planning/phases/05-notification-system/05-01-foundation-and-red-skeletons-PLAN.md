---
phase: 05-notification-system
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - requirements.txt
  - notifier_base.py
  - config_schema.py
  - models.py
  - sample.config.yml
  - tests/conftest.py
  - tests/test_notifier_base.py
  - tests/test_models_notification_dedup.py
  - tests/test_notifier_registry.py
  - tests/test_notification_writer.py
  - tests/test_notifiers_sound.py
  - tests/test_notifiers_discord.py
  - tests/test_notifiers_email.py
  - tests/test_notifiers_sms.py
autonomous: true
requirements:
  - NOTIF-01
  - NOTIF-02
  - NOTIF-03
  - NOTIF-04
  - NOTIF-05
  - NOTIF-06
tags:
  - python
  - notifications
  - abc
  - pydantic
  - sqlite
  - migration
  - test-infra
  - wave-0

must_haves:
  truths:
    - "notifier_base.py defines `class Notifier(ABC)` with `name: str = \"\"`, `enabled: bool = False`, abstract `async def send(self, event) -> None`, and non-abstract `async def shutdown(self) -> None` returning None by default (D-01)"
    - "notifier_base.py defines `@dataclass(frozen=True) class NotificationEvent` with fields `item_name: str`, `url: str`, `platform: str`, `timestamp: datetime`, `action: Literal['detected', 'purchased']` (CONTEXT specifics)"
    - "config_schema.py adds `SoundNotifierConfig`, `DiscordNotifierConfig`, `EmailNotifierConfig`, `SmsNotifierConfig`, and `NotificationsConfig` Pydantic BaseModels with all defaults `enabled=False` except sound which defaults `enabled=True`"
    - "NotificationsConfig has `restock_window_seconds: int = Field(default=600, ge=0, le=86400)` top-level (single dedup window source) and one sub-model per channel (D-02 specifies window placement)"
    - "AppConfig gains `notifications: NotificationsConfig = NotificationsConfig()` field; extra=forbid is preserved; existing fields untouched"
    - "EmailNotifierConfig fields: `enabled: bool = False`, `from_addr: str | None`, `to_addr: str | None`, `smtp_host: str | None`, `smtp_port: int = 587` (ge=1, le=65535), `smtp_user: str | None`. smtp_password is INTENTIONALLY ABSENT from the schema (SEC-01: env var only)"
    - "DiscordNotifierConfig has only `enabled: bool = False`. webhook_url is INTENTIONALLY ABSENT from the schema (SEC-01: env var SHOPBOT_DISCORD_WEBHOOK_URL only)"
    - "SmsNotifierConfig fields: `enabled: bool = False`, `to: str | None`. account_sid / auth_token / from_number are INTENTIONALLY ABSENT (SEC-01: env vars only)"
    - "models.py CREATE TABLE statement adds `last_notified_at TIMESTAMP NULL` column (D-02)"
    - "models.py defines `_migrate_add_last_notified_at(conn)` helper that calls `PRAGMA table_info(items)` first and only issues `ALTER TABLE items ADD COLUMN last_notified_at TIMESTAMP NULL` when the column is absent (idempotent migration per CONTEXT pitfall #7)"
    - "initialize_db() calls _migrate_add_last_notified_at after the CREATE TABLE block so existing v1 databases get the column without dropping data"
    - "models.py defines `should_notify(link: str, restock_window_seconds: int) -> bool` using `with _connect() as conn:` (NO raw sqlite3.connect); returns True if `last_notified_at` is NULL or now-last > window seconds; tz-aware UTC arithmetic"
    - "models.py defines `mark_notified(link: str) -> None` using `with _connect() as conn:` and `UPDATE items SET last_notified_at = CURRENT_TIMESTAMP WHERE link = ?` parameterized"
    - "requirements.txt pins `twilio==9.10.9` on a single new line after `pytest-asyncio==1.3.0`; no duplicates introduced"
    - "sample.config.yml gains a `notifications:` example block documenting restock_window_seconds + each channel's enabled flag + email host/port/from/to + SMS to-number with a clear `Set to true AND export SHOPBOT_ENABLE_SMS=true` comment for SMS (D-04 documented for end users)"
    - "tests/conftest.py adds a `fakeNotifierFactory` fixture (parallel to fakePluginFactory) building Notifier subclasses with configurable send behavior (return None / raise / record call)"
    - "Eight RED skeleton test files exist (test_notifier_base, test_models_notification_dedup, test_notifier_registry, test_notification_writer, test_notifiers_sound/discord/email/sms); each fails today at collection (ImportError on missing symbol) or execution (AttributeError); zero PASS"
    - "Pre-existing Phase 1/2/3/4 pytest suite remains green (no regressions)"
  artifacts:
    - path: "notifier_base.py"
      provides: "Notifier ABC + NotificationEvent dataclass"
      contains: "class Notifier"
      min_lines: 30
    - path: "config_schema.py"
      provides: "NotificationsConfig + per-channel sub-models attached to AppConfig"
      contains: "class NotificationsConfig"
    - path: "models.py"
      provides: "last_notified_at column + idempotent migration + should_notify/mark_notified helpers"
      contains: "def should_notify"
    - path: "requirements.txt"
      provides: "twilio==9.10.9 pin"
      contains: "twilio==9.10.9"
    - path: "sample.config.yml"
      provides: "notifications example block with SMS two-lock warning"
      contains: "notifications:"
    - path: "tests/conftest.py"
      provides: "fakeNotifierFactory shared fixture"
      contains: "fakeNotifierFactory"
    - path: "tests/test_notifier_base.py"
      provides: "RED ABC contract assertions (send abstract, shutdown async default)"
      min_lines: 20
    - path: "tests/test_models_notification_dedup.py"
      provides: "RED NOTIF-02 unit tests (should_notify, mark_notified, migration idempotency)"
      min_lines: 40
    - path: "tests/test_notifier_registry.py"
      provides: "RED discovery tests (discover_notifiers symbol absent today)"
      min_lines: 20
    - path: "tests/test_notification_writer.py"
      provides: "RED NOTIF-01 + dedup gate + task_done in finally tests"
      min_lines: 40
    - path: "tests/test_notifiers_sound.py"
      provides: "RED NOTIF-03 tests (to_thread wrap + threading.Lock)"
      min_lines: 20
    - path: "tests/test_notifiers_discord.py"
      provides: "RED NOTIF-04 tests (embed shape, 429-once, env-at-init)"
      min_lines: 30
    - path: "tests/test_notifiers_email.py"
      provides: "RED NOTIF-05 tests (STARTTLS on 587, SSL on 465, MIME headers, env password)"
      min_lines: 30
    - path: "tests/test_notifiers_sms.py"
      provides: "RED NOTIF-06 tests (two-lock pass/fail, test_mode disable, from_= kwarg)"
      min_lines: 30
  key_links:
    - from: "config_schema.AppConfig"
      to: "NotificationsConfig"
      via: "notifications: NotificationsConfig field on AppConfig"
      pattern: "notifications:\\s*NotificationsConfig"
    - from: "models.initialize_db"
      to: "_migrate_add_last_notified_at"
      via: "call after CREATE TABLE block"
      pattern: "_migrate_add_last_notified_at\\(conn\\)"
    - from: "models.should_notify"
      to: "models._connect"
      via: "with _connect() as conn"
      pattern: "with\\s+_connect\\(\\)"
    - from: "tests/conftest.py"
      to: "fakeNotifierFactory"
      via: "pytest fixture exported for writer + per-notifier tests"
      pattern: "fakeNotifierFactory"
---

<objective>
Wave 0: ship the foundation that every Phase 5 plan builds on. Define the `Notifier` ABC + `NotificationEvent` dataclass; extend `AppConfig` with a strict `NotificationsConfig` Pydantic schema; add the `last_notified_at` column to the items table with an idempotent migration; expose `should_notify` / `mark_notified` helpers using the Phase 4 `_connect()` context manager; pin `twilio==9.10.9`; document the schema in `sample.config.yml`; add the shared `fakeNotifierFactory` fixture; and lay down eight RED skeleton test files (one per downstream contract) so Waves 1 and 2 have failing-test targets to drive against.

Purpose: Phase 5 fans out across six requirements implemented by four parallel-safe notifier plans (Wave 1) plus one orchestrator-integration plan (Wave 2). Without this Wave 0 foundation, each downstream plan would re-invent the ABC, fragment the schema, and risk drift on the SQLite dedup contract. Single source of truth for shapes lives here. Every Wave 1/2 plan flips RED files in this commit to GREEN as it lands.

Output: notifier_base.py + extended config_schema.py + extended models.py + extended sample.config.yml + extended requirements.txt + extended tests/conftest.py + eight RED test files.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/05-notification-system/05-CONTEXT.md
@.planning/phases/05-notification-system/05-RESEARCH.md
@.planning/phases/04-async-orchestrator/04-01-async-test-infra-PLAN.md
@.planning/phases/04-async-orchestrator/04-02-sqlite-wal-context-managers-PLAN.md
@.planning/phases/04-async-orchestrator/04-05-async-main-orchestrator-PLAN.md
@plugin_base.py
@plugin_registry.py
@config_schema.py
@models.py
@utils.py
@logger.py
@requirements.txt
@sample.config.yml
@tests/conftest.py
</context>

<interfaces>
Target `notifier_base.py` (new file, full contents):

```python
"""Notifier contract for ShopPyBot (Phase 5).

Mirrors RetailerPlugin from plugin_base.py. Notifiers fan out from the
orchestrator's notification_writer via asyncio.gather(return_exceptions=True),
so each notifier's send() runs concurrently and per-channel failures are
isolated.

Per CONTEXT D-01: name + enabled are class attributes; send is the only
required abstract method; shutdown is a non-abstract async no-op that
subclasses override only when they hold resources (SMTP pool, persistent
HTTP client). NotificationEvent is frozen=True for hashability + safety in
flight.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

NOTIFIER_API_VERSION: int = 1


@dataclass(frozen=True)
class NotificationEvent:
    item_name: str
    url: str
    platform: str
    timestamp: datetime
    action: Literal["detected", "purchased"]


class Notifier(ABC):
    name: str = ""
    enabled: bool = False

    @abstractmethod
    async def send(self, event: NotificationEvent) -> None:
        raise NotImplementedError

    async def shutdown(self) -> None:
        return None
```

Target `config_schema.py` additions (insert after existing nested models, before `AppConfig`):

```python
class SoundNotifierConfig(BaseModel):
    enabled: bool = True  # sound currently fires today; keep on by default


class DiscordNotifierConfig(BaseModel):
    enabled: bool = False
    # webhook_url comes from SHOPBOT_DISCORD_WEBHOOK_URL env, not config.yml (SEC-01).


class EmailNotifierConfig(BaseModel):
    enabled: bool = False
    from_addr: str | None = None
    to_addr: str | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str | None = None
    # smtp_password comes from SHOPBOT_SMTP_PASSWORD env, not config.yml.


class SmsNotifierConfig(BaseModel):
    enabled: bool = False
    to: str | None = None
    # account_sid / auth_token / from_number come from env vars.


class NotificationsConfig(BaseModel):
    restock_window_seconds: int = Field(default=600, ge=0, le=86400)
    sound:   SoundNotifierConfig   = SoundNotifierConfig()
    discord: DiscordNotifierConfig = DiscordNotifierConfig()
    email:   EmailNotifierConfig   = EmailNotifierConfig()
    sms:     SmsNotifierConfig     = SmsNotifierConfig()
```

Add field on AppConfig:

```python
class AppConfig(BaseSettings):
    # ... existing fields ...
    notifications: NotificationsConfig = NotificationsConfig()
```

Target `models.py` additions:

```python
from datetime import datetime, timezone

def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _migrate_add_last_notified_at(conn) -> None:
    """Idempotent migration: add last_notified_at column if absent (Phase 5 NOTIF-02)."""
    if not _column_exists(conn, "items", "last_notified_at"):
        conn.execute(
            "ALTER TABLE items ADD COLUMN last_notified_at TIMESTAMP NULL"
        )


def should_notify(link: str, restock_window_seconds: int) -> bool:
    """True if no prior notification recorded OR last notification older than window."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT last_notified_at FROM items WHERE link = ?", (link,)
        ).fetchone()
        if row is None or row[0] is None:
            return True
        last = datetime.fromisoformat(row[0])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last).total_seconds() > restock_window_seconds


def mark_notified(link: str) -> None:
    """Set last_notified_at = CURRENT_TIMESTAMP for `link`."""
    with _connect() as conn:
        conn.execute(
            "UPDATE items SET last_notified_at = CURRENT_TIMESTAMP WHERE link = ?",
            (link,),
        )
```

Update CREATE TABLE to include `last_notified_at TIMESTAMP NULL` and call `_migrate_add_last_notified_at(conn)` inside `initialize_db` after the CREATE.

Target `requirements.txt` delta (append after pytest-asyncio==1.3.0):

```
twilio==9.10.9
```

Target `sample.config.yml` addition (append a new top-level `notifications:` block; document SMS two-lock):

```yaml
# Phase 5: notification channels. Each channel defaults to disabled except sound.
# Secrets are read from env vars, NEVER from this file (SEC-01).
#   Discord: SHOPBOT_DISCORD_WEBHOOK_URL
#   Email:   SHOPBOT_SMTP_PASSWORD
#   SMS:     SHOPBOT_TWILIO_ACCOUNT_SID, SHOPBOT_TWILIO_AUTH_TOKEN,
#            SHOPBOT_TWILIO_FROM, SHOPBOT_ENABLE_SMS
notifications:
  restock_window_seconds: 600   # dedup: one notification per item per 10 minutes
  sound:
    enabled: true
  discord:
    enabled: false              # set true AND export SHOPBOT_DISCORD_WEBHOOK_URL
  email:
    enabled: false              # set true AND export SHOPBOT_SMTP_PASSWORD
    from_addr: null
    to_addr: null
    smtp_host: null
    smtp_port: 587              # 587=STARTTLS (default), 465=SMTPS
    smtp_user: null
  sms:
    enabled: false              # Set to true AND export SHOPBOT_ENABLE_SMS=true to enable.
                                # See SECURITY.md for billing-risk warning (Twilio charges per message).
    to: null
```

Target `tests/conftest.py` fixture addition (append; do not replace):

```python
@pytest.fixture
def fakeNotifierFactory():
    """Build minimal Notifier subclasses with controllable send() behavior."""
    from notifier_base import Notifier

    def _make(*, name: str = "fakeNotifier",
              enabled: bool = True,
              sendRaises: Exception | None = None,
              sendRecorder: list | None = None):
        class _FakeNotifier(Notifier):
            def __init__(self):
                self.name = name
                self.enabled = enabled
                self.sendCalls = 0
            async def send(self, event):
                self.sendCalls += 1
                if sendRecorder is not None:
                    sendRecorder.append((self.name, event))
                if sendRaises is not None:
                    raise sendRaises
        return _FakeNotifier()
    return _make
```

RED skeleton test files: each file imports a not-yet-existent symbol (or asserts a not-yet-existent behavior) so collection or execution fails today. Documented at the top with:

```python
"""Phase 5 RED skeleton for NOTIF-0X (see 05-01-PLAN.md).
All tests in this file are expected to FAIL until Plan 05-0Y lands.
"""
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Foundation files (notifier_base + config + models migration + helpers + sample config + twilio pin + fakeNotifierFactory fixture)</name>
  <files>notifier_base.py, config_schema.py, models.py, sample.config.yml, requirements.txt, tests/conftest.py</files>
  <read_first>
    - notifier_base.py absence: confirm file does not yet exist (Glob)
    - plugin_base.py (mirror the ABC shape, including module docstring style)
    - config_schema.py (current AppConfig + existing nested models; preserve extra=forbid, env_nested_delimiter, settings_customise_sources, reject_deprecated_keys validator)
    - models.py (current _connect contract from Phase 4-02; the existing CREATE TABLE block; existing initialize_db structure)
    - sample.config.yml (top-level keys; choose insertion point near other top-level config blocks)
    - requirements.txt (existing pin order; insert after pytest-asyncio==1.3.0 line)
    - tests/conftest.py (existing fakePluginFactory; mirror its style)
    - .planning/phases/05-notification-system/05-RESEARCH.md sections: Pattern 1 (ABC), Research Question 4 (idempotent migration), Research Question 8 (helper signatures), Research Question 9 (NotificationsConfig shape)
  </read_first>
  <behavior>
    - `python -c "from notifier_base import Notifier, NotificationEvent, NOTIFIER_API_VERSION; print(NOTIFIER_API_VERSION)"` prints `1`.
    - `python -c "from notifier_base import Notifier; import inspect; assert inspect.iscoroutinefunction(Notifier.send); assert inspect.iscoroutinefunction(Notifier.shutdown)"` exits 0.
    - `python -c "from config_schema import NotificationsConfig; c = NotificationsConfig(); assert c.restock_window_seconds == 600; assert c.sound.enabled is True; assert c.discord.enabled is False; assert c.email.enabled is False; assert c.email.smtp_port == 587; assert c.sms.enabled is False"` exits 0.
    - `python -c "from config_schema import EmailNotifierConfig; assert 'smtp_password' not in EmailNotifierConfig.model_fields"` exits 0 (SEC-01 surface).
    - `python -c "from config_schema import DiscordNotifierConfig; assert 'webhook_url' not in DiscordNotifierConfig.model_fields"` exits 0.
    - `python -c "from models import should_notify, mark_notified, _migrate_add_last_notified_at"` exits 0.
    - Running `initialize_db(delete=True)` twice in succession on the same DB path does not raise (idempotency).
    - On a legacy DB created without the column, calling `initialize_db()` adds the column without dropping or recreating other rows.
    - `should_notify(unknown_link, 600)` returns True for a link not present in the items table (no row); also True for a row with NULL last_notified_at.
    - `should_notify(link, 600)` returns False immediately after `mark_notified(link)` and True after the window elapses (use a manual UPDATE with an old timestamp to simulate elapsed time in tests, OR window=0).
    - `mark_notified` uses the `_connect()` context manager (no raw sqlite3.connect; AST grep confirms).
    - `requirements.txt` contains exactly one `twilio==9.10.9` line.
    - `sample.config.yml` parses as valid YAML and the `notifications` block matches NotificationsConfig defaults; the SMS comment block names both `SHOPBOT_ENABLE_SMS=true` and SECURITY.md.
    - `fakeNotifierFactory` fixture is collectible by pytest and instantiates a Notifier subclass whose `send` raises configured exceptions and increments `sendCalls`.
    - Existing pytest suite (Phase 1/2/3/4) still passes green.
  </behavior>
  <action>
    1. Create `notifier_base.py` with the full contents shown in <interfaces>. Match plugin_base.py's docstring/import style. Functions stay under 30 lines. The module is < 60 lines total.

    2. Open `config_schema.py`. Insert the four sub-models (`SoundNotifierConfig`, `DiscordNotifierConfig`, `EmailNotifierConfig`, `SmsNotifierConfig`) and the parent `NotificationsConfig` after the existing nested models (after `AppSettings`, before `AppConfig`). Add `notifications: NotificationsConfig = NotificationsConfig()` as a new field on `AppConfig` adjacent to the existing `app: AppSettings = AppSettings()` line. Do NOT add smtp_password / webhook_url / sid / token fields anywhere — these are env-only by SEC-01.

    3. Open `models.py`. Update the `CREATE TABLE IF NOT EXISTS items` SQL to add a new column `last_notified_at TIMESTAMP NULL` (place after the existing `purchased` column line). Add the `_column_exists` and `_migrate_add_last_notified_at` private helpers after `_connect`. Call `_migrate_add_last_notified_at(conn)` inside `initialize_db` after the CREATE TABLE block. Add `should_notify(link, restock_window_seconds)` and `mark_notified(link)` as new public functions per the <interfaces> code. Import `datetime` and `timezone` at the top of the file.

    4. Open `sample.config.yml`. Append the `notifications:` block shown in <interfaces> at the end of the file (preserve existing leading blocks). Validate via `python -c "import yaml; yaml.safe_load(open('sample.config.yml'))"`.

    5. Open `requirements.txt`. Append `twilio==9.10.9` directly after the existing `pytest-asyncio==1.3.0` line. Run `rtk pip install -r requirements.txt` to install. Confirm via `rtk pip show twilio` -> `Version: 9.10.9`.

    6. Open `tests/conftest.py`. Append the `fakeNotifierFactory` fixture from <interfaces>. Keep camelCase consistent with the existing `fakePluginFactory` style.

    7. Run `rtk pytest -x -q` over the existing suite (excluding the not-yet-created test files; they will be added in Task 2). All Phase 1/2/3/4 tests must remain green. Any regression here means the new schema fields broke env-var loading or the `last_notified_at` column changed an existing SELECT contract — investigate immediately.
  </action>
  <verify>
    <automated>rtk pip show twilio</automated>
    <automated>python -c "from notifier_base import Notifier, NotificationEvent, NOTIFIER_API_VERSION; print(NOTIFIER_API_VERSION)"</automated>
    <automated>python -c "import inspect; from notifier_base import Notifier; assert inspect.iscoroutinefunction(Notifier.send); assert inspect.iscoroutinefunction(Notifier.shutdown)"</automated>
    <automated>python -c "from config_schema import NotificationsConfig; c=NotificationsConfig(); assert c.restock_window_seconds==600 and c.sound.enabled is True and c.discord.enabled is False and c.email.smtp_port==587 and c.sms.enabled is False"</automated>
    <automated>python -c "from config_schema import EmailNotifierConfig, DiscordNotifierConfig, SmsNotifierConfig; assert 'smtp_password' not in EmailNotifierConfig.model_fields and 'webhook_url' not in DiscordNotifierConfig.model_fields and 'account_sid' not in SmsNotifierConfig.model_fields"</automated>
    <automated>python -c "from models import should_notify, mark_notified, _migrate_add_last_notified_at"</automated>
    <automated>python -c "import yaml; yaml.safe_load(open('sample.config.yml'))"</automated>
    <automated>rtk grep -n "fakeNotifierFactory" tests/conftest.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_notifier_base.py --ignore=tests/test_models_notification_dedup.py --ignore=tests/test_notifier_registry.py --ignore=tests/test_notification_writer.py --ignore=tests/test_notifiers_sound.py --ignore=tests/test_notifiers_discord.py --ignore=tests/test_notifiers_email.py --ignore=tests/test_notifiers_sms.py</automated>
  </verify>
  <acceptance_criteria>
    - notifier_base.py exists with ABC + dataclass + NOTIFIER_API_VERSION
    - config_schema.py exposes NotificationsConfig with four sub-models, env-only secret fields ABSENT
    - models.py CREATE TABLE includes last_notified_at; migration idempotent; should_notify/mark_notified use _connect()
    - sample.config.yml has notifications block with SMS two-lock comment
    - requirements.txt pins twilio==9.10.9 (single line, no duplicate)
    - tests/conftest.py exposes fakeNotifierFactory
    - Pre-existing Phase 1/2/3/4 test suite passes
  </acceptance_criteria>
  <done>Foundation shapes locked. Wave 1 plans can subclass Notifier and call should_notify/mark_notified directly.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: RED skeleton test files for all eight Phase 5 contracts</name>
  <files>tests/test_notifier_base.py, tests/test_models_notification_dedup.py, tests/test_notifier_registry.py, tests/test_notification_writer.py, tests/test_notifiers_sound.py, tests/test_notifiers_discord.py, tests/test_notifiers_email.py, tests/test_notifiers_sms.py</files>
  <read_first>
    - notifier_base.py (just-created from Task 1; imports for ABC-contract tests)
    - models.py (just-extended from Task 1; should_notify/mark_notified entry points)
    - tests/conftest.py (fakeNotifierFactory + tmpDbPath from Phase 4)
    - tests/test_orchestrator.py (Phase 4 GREEN style: AST grep + coroutine inspection)
    - tests/test_models_wal.py (Phase 4 GREEN style for models tests)
    - .planning/phases/05-notification-system/05-RESEARCH.md sections: Phase Requirements -> Test Map; Sample test patterns (Discord/SMTP/Twilio monkeypatch shapes)
  </read_first>
  <behavior>
    Each new test file contains 2-4 RED tests targeting one downstream plan. Every test must fail today either at collection (ImportError on a symbol that does not exist yet) or at execution (AttributeError / NotImplementedError on a stub call). Collection failure IS the canonical RED state for symbols that arrive in later plans.

    `tests/test_notifier_base.py` (ABC contract, Wave 0 GREEN already from Task 1 — but include for traceability):
      - test_sendIsAbstractCoroutine: assert `inspect.iscoroutinefunction(Notifier.send) is True` and `Notifier.send.__isabstractmethod__ is True`. EXPECTED PASS today (Task 1 ships the ABC).
      - test_shutdownDefaultReturnsNone: subclass Notifier with a trivial concrete send; assert `await instance.shutdown()` returns None. EXPECTED PASS today.
      - test_notificationEventIsFrozen: `NotificationEvent(...)` then attempt attribute assignment; assert FrozenInstanceError. EXPECTED PASS today.
      NOTE: This file is the one exception to the RED-only rule — it tests Task 1's deliverable directly so we have a regression net.

    `tests/test_models_notification_dedup.py` (covers NOTIF-02):
      - test_shouldNotifyTrueForNullColumn: insert a row with last_notified_at NULL; assert `should_notify(link, 600) is True`. EXPECTED PASS today (Task 1 ships the helper).
      - test_shouldNotifyFalseInsideWindow: insert + mark_notified(link); assert `should_notify(link, 600) is False` immediately. EXPECTED PASS.
      - test_shouldNotifyTrueAfterWindow: insert + manually UPDATE last_notified_at to a timestamp 700 seconds ago; assert `should_notify(link, 600) is True`. EXPECTED PASS.
      - test_markNotifiedSetsTimestamp: insert; mark_notified; SELECT last_notified_at; assert non-null. EXPECTED PASS.
      - test_migrationIdempotent: call `initialize_db(delete=True)`, then call again (without delete); assert no exception (the second call must hit the PRAGMA-table_info short-circuit). EXPECTED PASS.
      NOTE: This file is also GREEN-on-day-zero because Task 1 ships the helpers; it serves as the regression net for NOTIF-02.

    `tests/test_notifier_registry.py` (Wave 1 / Plan 05-02 target):
      - test_discoverNotifiersIsAsyncCoroutine: `from notifier_registry import discover_notifiers; assert inspect.iscoroutinefunction(discover_notifiers)`. EXPECTED FAIL: ImportError (notifier_registry.py does not exist yet — created in Plan 05-02).
      - test_discoverFindsShopbotNotifierFiles: stub two `shopbot_notifier_*.py` files in tmp_path; call discover_notifiers; assert two Notifier instances returned. EXPECTED FAIL: ImportError.

    `tests/test_notification_writer.py` (Wave 2 / Plan 05-06 target — covers NOTIF-01):
      - test_notificationWriterIsAsyncCoroutine: `from main import notification_writer; assert inspect.iscoroutinefunction(notification_writer)`. EXPECTED FAIL: ImportError.
      - test_oneFailedNotifierDoesNotBlockOthers: build two fakeNotifierFactory instances (one raising RuntimeError, one succeeding); put one event on a queue; run notification_writer for ~0.5s; assert the succeeding notifier's sendCalls == 1 AND the writer is still running. EXPECTED FAIL: ImportError.
      - test_purchasedActionBypassesDedup: monkeypatch should_notify to always return False; put a NotificationEvent(action="purchased") on the queue; assert the notifier still fires (dedup gate skipped for purchased). EXPECTED FAIL: ImportError.
      - test_taskDoneCalledInFinally: monkeypatch should_notify to raise RuntimeError; put one event; assert queue.join() returns within 1s (task_done ran in finally). EXPECTED FAIL: ImportError.

    `tests/test_notifiers_sound.py` (Plan 05-02 target — covers NOTIF-03):
      - test_soundNotifierImportable: `from notifiers.shopbot_notifier_sound import SoundNotifier`. EXPECTED FAIL: ImportError.
      - test_sendUsesAsyncToThread: ast.parse the notifier file; assert at least one `asyncio.to_thread` call inside `send`. EXPECTED FAIL: file does not exist.
      - test_classLockExists: assert `SoundNotifier._lock` is a `threading.Lock` instance. EXPECTED FAIL: ImportError.

    `tests/test_notifiers_discord.py` (Plan 05-03 target — covers NOTIF-04):
      - test_discordNotifierImportable: `from notifiers.shopbot_notifier_discord import DiscordNotifier`. EXPECTED FAIL: ImportError.
      - test_urlReadAtInit: monkeypatch env SHOPBOT_DISCORD_WEBHOOK_URL="x"; instantiate; pop env; assert instance still has the URL (read once at init). EXPECTED FAIL: ImportError.
      - test_embedShape: monkeypatch requests.post recorder; send event; assert payload["embeds"][0] has keys {title, description, url, color, timestamp, fields}. EXPECTED FAIL: ImportError.
      - test_429RetryOnce: fake requests.post returns 429 with Retry-After=0.01 then 204; assert exactly two requests recorded. EXPECTED FAIL: ImportError.
      - test_429GiveUpAfterOne: fake returns 429 twice in a row; assert send returns without raising AND records exactly two POST attempts. EXPECTED FAIL: ImportError.

    `tests/test_notifiers_email.py` (Plan 05-04 target — covers NOTIF-05):
      - test_emailNotifierImportable: `from notifiers.shopbot_notifier_email import EmailNotifier`. EXPECTED FAIL: ImportError.
      - test_starttlsOn587: monkeypatch smtplib.SMTP -> FakeSmtp recorder; send event with port=587; assert recorded calls include "starttls" then "login" then "send_message". EXPECTED FAIL.
      - test_smtpsslOn465: monkeypatch smtplib.SMTP_SSL -> FakeSmtpSsl recorder; send event with port=465; assert recorded calls include "login" then "send_message" but NOT "starttls". EXPECTED FAIL.
      - test_passwordFromEnv: monkeypatch SHOPBOT_SMTP_PASSWORD="x"; assert EmailNotifier reads it at __init__ and disables cleanly when env absent. EXPECTED FAIL.
      - test_messageHeaders: assert the MIME message has Subject containing platform + item_name, plus From/To. EXPECTED FAIL.

    `tests/test_notifiers_sms.py` (Plan 05-05 target — covers NOTIF-06):
      - test_smsNotifierImportable: `from notifiers.shopbot_notifier_sms import SmsNotifier`. EXPECTED FAIL: ImportError.
      - test_disabledIfConfigOff: pass SmsNotifierConfig(enabled=False) with all env vars set; assert instance.enabled is False AND a WARNING log distinguishes "config off". EXPECTED FAIL.
      - test_disabledIfEnvOff: pass SmsNotifierConfig(enabled=True, to="+1") without SHOPBOT_ENABLE_SMS; assert instance.enabled is False AND WARNING distinguishes "env off". EXPECTED FAIL.
      - test_enabledWhenBothLocksPass: config.enabled=True + env SHOPBOT_ENABLE_SMS=true + Twilio env vars set; assert instance.enabled is True. EXPECTED FAIL.
      - test_testModeDisablesSms: both locks pass, app_config.debug.test_mode=True; assert instance.enabled is False. EXPECTED FAIL.
      - test_twilioFromUnderscore: ast.parse the notifier file; assert `keyword.arg == "from_"` appears in the `messages.create` call (NEVER `from=` or `from_addr=`). EXPECTED FAIL.
  </behavior>
  <action>
    1. Create `tests/test_notifier_base.py`. Import `Notifier`, `NotificationEvent`, `NOTIFIER_API_VERSION`. Add the three GREEN-on-day-zero tests for the ABC contract (these PASS today; that is OK — they regression-net Task 1's deliverable). Use camelCase test names.

    2. Create `tests/test_models_notification_dedup.py`. Use the `tmpDbPath` fixture. Call `initialize_db(delete=True)` then `add_items(...)` in each test setup. Five tests as described. These PASS today (Task 1 ships the helpers); they regression-net NOTIF-02.

    3. Create `tests/test_notifier_registry.py`. `from notifier_registry import discover_notifiers` at the top (this ImportErrors at collection today — that is the RED signal for Plan 05-02). Add the two tests.

    4. Create `tests/test_notification_writer.py`. `from main import notification_writer` at the top (ImportError today — RED for Plan 05-06). Add the four tests. Use `fakeNotifierFactory` for the failed/successful notifier pair. Use `monkeypatch.setattr("models.should_notify", ...)` to control dedup.

    5. Create `tests/test_notifiers_sound.py`. `from notifiers.shopbot_notifier_sound import SoundNotifier` at the top (ImportError today). Add three tests including the AST-grep for `asyncio.to_thread` inside `send`.

    6. Create `tests/test_notifiers_discord.py`. `from notifiers.shopbot_notifier_discord import DiscordNotifier` at the top. Add the five tests. Build a `FakeResponse` helper for status_code + headers + raise_for_status + json().

    7. Create `tests/test_notifiers_email.py`. `from notifiers.shopbot_notifier_email import EmailNotifier` at the top. Add the five tests. Build a `FakeSmtp` context-manager class recorder.

    8. Create `tests/test_notifiers_sms.py`. `from notifiers.shopbot_notifier_sms import SmsNotifier` at the top. Add the six tests. Build a `FakeTwilioClient` recorder. Use `monkeypatch.setenv` / `monkeypatch.delenv` to toggle the two-lock surface.

    9. Each file gets the module docstring header:
       ```python
       """Phase 5 RED skeleton for NOTIF-0X (see 05-01-PLAN.md).
       Tests that fail at collection (ImportError) are the canonical RED signal for
       Plan 05-0Y; Plan 05-0Y flips them GREEN. Tests in this file that PASS today
       (e.g. NOTIF-02 helpers shipped by 05-01) are regression nets, not RED targets.
       """
       ```

    10. Run `rtk pytest -q tests/test_notifier_base.py tests/test_models_notification_dedup.py` — these MUST pass today (regression nets for Task 1).

    11. Run `rtk pytest -q tests/test_notifier_registry.py tests/test_notification_writer.py tests/test_notifiers_sound.py tests/test_notifiers_discord.py tests/test_notifiers_email.py tests/test_notifiers_sms.py` — every test in these six files MUST fail (collection ImportError or execution error). Zero PASS.

    12. Run `rtk pytest -x -q` over the full suite minus the six RED files (--ignore each). Pre-existing Phase 1/2/3/4 suite MUST remain green.
  </action>
  <verify>
    <automated>rtk pytest -q tests/test_notifier_base.py tests/test_models_notification_dedup.py</automated>
    <automated>rtk pytest tests/test_notifier_registry.py tests/test_notification_writer.py tests/test_notifiers_sound.py tests/test_notifiers_discord.py tests/test_notifiers_email.py tests/test_notifiers_sms.py 2>&1 | rtk grep -E "FAILED|ERROR|error"</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_notifier_registry.py --ignore=tests/test_notification_writer.py --ignore=tests/test_notifiers_sound.py --ignore=tests/test_notifiers_discord.py --ignore=tests/test_notifiers_email.py --ignore=tests/test_notifiers_sms.py</automated>
    <automated>rtk grep -l "Phase 5 RED skeleton" tests/</automated>
  </verify>
  <acceptance_criteria>
    - All eight new test files committed with the module docstring header
    - tests/test_notifier_base.py + tests/test_models_notification_dedup.py PASS today (regression nets for Task 1)
    - The other six RED test files have zero PASS today (collection ImportError or execution error per test)
    - Pre-existing Phase 1/2/3/4 suite green
    - Test names use camelCase per CLAUDE.md
  </acceptance_criteria>
  <done>Eight test files committed: two as Wave 0 regression nets (GREEN today) and six as Wave 1/2 RED targets driving downstream plans to GREEN.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| sample.config.yml | Documents SECRET surface; must NOT instruct users to put webhook_url / smtp_password / Twilio creds in YAML |
| config_schema.py | Pydantic extra=forbid is the strict load gate; missing forbid = secret in YAML can silently load |
| models.py last_notified_at migration | Legacy v1 databases must not lose data on upgrade |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-01-SECRET-IN-CONFIG | Information Disclosure | config_schema.py | mitigate | smtp_password / webhook_url / SID / token fields ABSENT from Pydantic schema; extra=forbid causes startup failure if user adds them to YAML; sample.config.yml comments name the env vars only |
| T-05-01-MIGRATION-DATA-LOSS | Tampering (data) | models.initialize_db | mitigate | _migrate_add_last_notified_at uses PRAGMA table_info precheck; ALTER TABLE ADD COLUMN preserves existing rows; idempotent on re-run |
| T-05-01-FROZEN-EVENT-MUT | Tampering (in-flight) | NotificationEvent dataclass | mitigate | frozen=True dataclass raises FrozenInstanceError on any attribute assignment |
| T-05-01-CVV-EQUIVALENT | Information Disclosure | sample.config.yml comment | mitigate | comment explicitly directs SMS users to SECURITY.md billing-risk warning; two-lock requirement spelled out |
</threat_model>

<verification>
- `rtk pip show twilio` shows Version: 9.10.9
- `rtk grep -n "twilio==9.10.9" requirements.txt` returns one match
- `python -c "from notifier_base import Notifier, NotificationEvent"` succeeds
- `python -c "from config_schema import NotificationsConfig, SoundNotifierConfig, DiscordNotifierConfig, EmailNotifierConfig, SmsNotifierConfig"` succeeds
- `python -c "from models import should_notify, mark_notified, _migrate_add_last_notified_at"` succeeds
- `python -c "import yaml; yaml.safe_load(open('sample.config.yml'))"` succeeds
- `rtk grep -n "fakeNotifierFactory" tests/conftest.py` returns the fixture definition line
- `rtk pytest -q tests/test_notifier_base.py tests/test_models_notification_dedup.py` shows all PASS
- `rtk pytest tests/test_notifier_registry.py tests/test_notification_writer.py tests/test_notifiers_sound.py tests/test_notifiers_discord.py tests/test_notifiers_email.py tests/test_notifiers_sms.py` shows ZERO PASS (every test ERROR or FAIL)
- Pre-existing Phase 1/2/3/4 test suite remains green
</verification>

<success_criteria>
- Notifier ABC + NotificationEvent dataclass shipped (D-01)
- last_notified_at column + idempotent migration + should_notify/mark_notified helpers shipped (D-02)
- NotificationsConfig + per-channel sub-models on AppConfig with env-only secret surface (D-04 supports SMS contract)
- twilio==9.10.9 pinned
- sample.config.yml documents the schema and SMS two-lock
- fakeNotifierFactory fixture available
- Eight test files: two GREEN regression nets + six RED targets for Wave 1 + Wave 2
- Phase 1-4 suite unaffected
</success_criteria>

<output>
After completion, create `.planning/phases/05-notification-system/05-01-SUMMARY.md`
</output>
