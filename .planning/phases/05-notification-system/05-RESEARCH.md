# Phase 5: Notification System - Research

**Researched:** 2026-05-14
**Domain:** asyncio fan-out dispatch + multi-channel notification delivery (Discord webhook, SMTP, Twilio SMS, pygame sound)
**Confidence:** HIGH

## Summary

- Phase 5 mirrors Phase 4 almost exactly: ABC + `notifiers/` discovery + per-channel async `send()` + a single `notification_writer` consumer task on an `asyncio.Queue`. Treat the whole phase as "Phase 4 again, but for notifications instead of purchases."
- Six requirements (NOTIF-01..06) map cleanly to four notifier classes plus one orchestrator change plus one models migration. Suggested 5-plan layout (one wave-0 + 4 implementation plans) at the bottom of this doc.
- All channel SDKs are sync. Wrap every `send()` body in `asyncio.to_thread(...)`. Do NOT add `aiosmtplib` or `httpx.AsyncClient`: v1 notification volume is < 1/min/item; per-send sync I/O is well within budget and keeps the dependency surface tiny. [ASSUMED — confirm at Wave 0 if traffic estimates change]
- One new pinned dependency only: `twilio==9.10.9` (latest stable, released 2026-05-07, supports Python 3.13). `requests` (already 2.33.1) covers Discord; stdlib `smtplib` covers email.
- Discord 429 handling: honor the `Retry-After` HEADER once, single retry, then give up + log. The body's `retry_after` field is in SECONDS (float) per official docs; header is seconds. Webhook limit is 30/minute/webhook — well above v1 polling rate even with 10 items.
- SMTP default: port 587 + STARTTLS (`smtplib.SMTP` then `.starttls()`). Gmail, Office365, Fastmail, SES, SendGrid all accept this. Skip connection pooling.
- Dedup goes in the writer, not the plugin task: orchestrator pushes raw events; writer checks `should_notify(url, restock_window_seconds)` before fan-out and calls `mark_notified(url)` after. Single-writer means no race window.
- Two-lock SMS opt-in: validate at `__init__` time (CONTEXT pitfall #2). If either lock fails, set `self.enabled = False` and log a one-time WARNING that distinguishes the failing lock (config-off vs env-off vs both-off — CONTEXT pitfall #10).
- All secrets via env vars: `SHOPBOT_DISCORD_WEBHOOK_URL`, `SHOPBOT_SMTP_PASSWORD`, `SHOPBOT_TWILIO_ACCOUNT_SID`, `SHOPBOT_TWILIO_AUTH_TOKEN`, `SHOPBOT_TWILIO_FROM`, `SHOPBOT_ENABLE_SMS`. Read once in `__init__`, not in `send()` (pitfall: changes during runtime won't be picked up; also avoids per-event env stat).
- pygame mixer: project already calls `pygame.mixer.music.load`+`.play` synchronously from `play_*_sound`. Wrap the existing helpers in `asyncio.to_thread` inside `shopbot_notifier_sound.send()`. Add a small `threading.Lock` inside the notifier guarding the to_thread call — pygame.mixer.music is a single channel and concurrent `.load()`+`.play()` from different worker threads can truncate the load.
- Test strategy: monkeypatch `requests.post`, `smtplib.SMTP`/`smtplib.SMTP_SSL`, and `twilio.rest.Client.messages.create` directly with `monkeypatch.setattr`. No new test deps. Existing pytest-asyncio==1.3.0 + `asyncio_mode=auto` from Plan 04-01 covers async test wiring.

**Primary recommendation:** Build the ABC + sound notifier + models migration first (Wave 1, all in-process, no network). Then ship Discord, Email, SMS as three parallel plans in Wave 2 (independent files, no shared state). Wire main.py last in Wave 3.

## Project Constraints (from CLAUDE.md)

The following directives from `./CLAUDE.md` constrain planning and must be honored:

- **camelCase** for variables and functions; **PascalCase** for classes/types. Booleans prefixed `is`/`has`/`can`/`should`. (Project file currently mixes snake_case in `models.py` / `main.py` — match the existing local convention per Phase 4 SUMMARY's `appConfigStub` fix: new test fixtures use camelCase, but functions that mirror existing snake_case API stay snake_case. See `should_notify`/`mark_notified` naming below.)
- Functions under 30 lines, files under 300 lines, nesting depth max 3.
- No em dashes in user-facing output; no emojis unless requested; no `---`/`***`/`___` horizontal rules.
- No silent exception swallowing. Notifier failure: log via `writeLog` with actionable context including channel name and event URL.
- No new dependencies unless necessary. New dep `twilio` is justified (no stdlib SMS path); rationale included in the SMS plan.
- Tests: shared fixtures in `tests/conftest.py`. Use existing `tmpDbPath`, `appConfigStub`, `fakePluginFactory` fixtures from Plan 04-01.
- Secrets via env vars only, never config.yml (SEC-01).
- Validate all external input server-side: this applies here to the `NotificationsConfig` Pydantic validation (Phase 1 D-07: `extra=forbid`).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NOTIF-01 | Fan-out dispatcher; per-channel failures isolated | `asyncio.gather(..., return_exceptions=True)` inside `notification_writer` (Section 10). Loop over results, log exceptions per notifier name. |
| NOTIF-02 | Dedup: one notification per item per restock event; SQLite `last_notified` timestamp | `last_notified_at TIMESTAMP NULL` column + idempotent `ALTER TABLE` (Section 4); `should_notify`/`mark_notified` helpers in `models.py` (Section 8). |
| NOTIF-03 | Sound notifier wraps `play_available_sound`/`play_buy_sound`/`play_notification_sound` | Sync helpers wrapped in `asyncio.to_thread` + `threading.Lock` (Section 5). |
| NOTIF-04 | Discord webhook notifier posts standardized embed | `requests.post` to webhook URL with embed JSON; 429 retry policy honors `Retry-After` (Section 1); embed schema (Section 1). |
| NOTIF-05 | Email/SMTP notifier; configurable sender/recipient in config | stdlib `smtplib.SMTP` + `.starttls()` on port 587 default; password from env (Section 2). |
| NOTIF-06 | SMS/Twilio notifier (opt-in only) | Two-lock check at `__init__` (config.sms.enabled AND `SHOPBOT_ENABLE_SMS=true`); `twilio==9.10.9` (Section 3). |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Notifier discovery | App startup (orchestrator) | — | Symmetric with plugin_registry; runs once in `main()` before TaskGroup |
| Event creation | Orchestrator (poll_plugin) | — | Plugins stay ignorant of NotificationEvent; orchestrator owns event shape |
| Dedup decision | notification_writer task | SQLite (models layer) | Single-writer eliminates race; SQL is data store |
| Fan-out dispatch | notification_writer task | Per-notifier `send()` | Writer owns `asyncio.gather` + isolation; notifier owns one channel |
| HTTP / SMTP / SMS I/O | Worker thread (via to_thread) | Notifier `send()` | All SDKs sync; offload to thread pool, do not block the loop |
| Sound playback | Worker thread (via to_thread) | pygame mixer (process-global) | pygame.mixer.music is process-global single-channel |
| Secrets surface | Notifier `__init__` | Process env | Read once at instantiation; never at send time |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `twilio` | 9.10.9 | SMS via Twilio REST API | Official SDK; latest stable 2026-05-07; supports Python 3.7-3.13; widely used. [VERIFIED: pypi.org/project/twilio] |
| `requests` | 2.33.1 (already pinned) | Discord webhook POST | Already in tree; wrap in `to_thread`; no need for httpx async for v1 volume. |
| `smtplib` (stdlib) | — | SMTP send | Stdlib; no dep added. STARTTLS is built in. |
| `email.mime.text` / `email.mime.multipart` (stdlib) | — | MIME message build | Stdlib. |
| `pygame` | 2.6.1 (already pinned) | Sound playback | Existing in tree. |
| `pydantic` | 2.13.3 (already pinned) | Config validation | Existing in tree. Extends `AppConfig` with `notifications` field. |
| `pytest-asyncio` | 1.3.0 (already pinned) | Async test runner | Installed in Plan 04-01. `asyncio_mode=auto` already set. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `requests` + `to_thread` | `httpx` async | Adds dep; v1 polling rate (1/min/item) makes async I/O premature; sync+to_thread reuses existing dep. |
| `smtplib` + `to_thread` | `aiosmtplib` | Adds dep; same rate argument; stdlib path is simpler. |
| `twilio` SDK | Raw `requests` to Twilio REST API | SDK gives `TwilioRestException` typed errors and signed-request handling for ~free. Worth the one dep. |
| Per-message SMTP connection | Connection pool / keep-alive | At <1 send/min/channel, no benefit. Adds shutdown complexity. |

### Version Verification

`twilio==9.10.9` verified at pypi.org/project/twilio as of 2026-05-07 release. Run `pip index versions twilio` at plan implementation time to re-confirm before pinning.

**Installation:**

```
pip install twilio==9.10.9
```

Append to `requirements.txt` after `pytest-asyncio==1.3.0`.

## Architecture Patterns

### System Architecture Diagram

```
                  poll_plugin task (per plugin)
                            |
                            | check_availability == True
                            |
                            v
         await notification_queue.put(NotificationEvent(...))
                            |
                            v
                   notification_queue
                  (asyncio.Queue maxsize=200)
                            |
                            v
              notification_writer (single consumer)
                            |
                  +---------+---------+
                  | should_notify(url)?  --- NO --> drop event, task_done
                  |
                 YES
                  |
                  v
   asyncio.gather(*(n.send(event) for n in notifiers if n.enabled),
                  return_exceptions=True)
                  |
       +----------+----------+----------+
       v          v          v          v
   SoundNotif  DiscordNotif EmailNotif SmsNotif
   (to_thread) (to_thread)  (to_thread)(to_thread)
                                          ^
                                          | two-lock check
                                          | passed at __init__
   per-notifier exception caught -> writeLog(name, error) -> writer continues
                  |
                  v
            mark_notified(url)
                  |
                  v
            queue.task_done()
```

### Recommended Project Structure

```
notifiers/
├── __init__.py
├── shopbot_notifier_sound.py
├── shopbot_notifier_discord.py
├── shopbot_notifier_email.py
└── shopbot_notifier_sms.py

notifier_base.py                # at repo root, peer of plugin_base.py
notifier_registry.py            # at repo root, peer of plugin_registry.py
                                #   (NotificationEvent dataclass lives here OR in notifier_base.py)
models.py                       # extended: + last_notified_at column, should_notify, mark_notified
config_schema.py                # extended: + NotificationsConfig nested model + AppConfig.notifications
main.py                         # extended: + notification_queue, + notification_writer task, +
                                #   NotificationEvent creation site in _poll_once
```

### Pattern 1: Notifier ABC (mirror RetailerPlugin)

```python
# notifier_base.py
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


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
    async def send(self, event: NotificationEvent) -> None: ...

    async def shutdown(self) -> None:
        return None
```

### Pattern 2: Discovery (parallel registry)

Recommended path: create `notifier_registry.py` that mirrors `plugin_registry.py` line-for-line with these substitutions:

- `PLUGIN_PREFIX = "shopbot_plugin_"` becomes `NOTIFIER_PREFIX = "shopbot_notifier_"`
- `RetailerPlugin` becomes `Notifier`
- `domain_pattern` check (and `verify_coverage`) drops out entirely — notifiers have no URL routing
- `discover_async` keeps the same stagger pattern for safety, but stagger can be 0 (no chromedriver port race for notifiers); choose 0 to keep startup fast

Skip the temptation to "generalize the existing helper to `discover_modules(dir, abc_class, prefix)`." That is a YAGNI violation: we have exactly two callers, both ship in the same commit eventually. Reusing the file pattern twice is cheaper than a 3rd abstraction.

### Pattern 3: notification_writer (mirror purchase_writer)

```python
# main.py addition
async def notification_writer(
    queue: asyncio.Queue,
    notifiers: list[Notifier],
    restock_window_seconds: int,
) -> None:
    """Single consumer for fan-out dispatch. Mirrors purchase_writer.

    Per Phase 4 Pitfall 4-10, a crash here is FATAL — no outer try/except.
    Per-notifier exceptions are isolated via gather(return_exceptions=True).
    The dedup check + mark_notified live inside this writer (single-writer guarantees no race).
    """
    while True:
        event = await queue.get()
        try:
            if not await asyncio.to_thread(should_notify, event.url, restock_window_seconds):
                continue
            active = [n for n in notifiers if n.enabled]
            results = await asyncio.gather(
                *(n.send(event) for n in active),
                return_exceptions=True,
            )
            for n, r in zip(active, results):
                if isinstance(r, Exception):
                    writeLog(f"notifier {n.name} failed on {event.url}: {r}", "ERROR")
            try:
                await asyncio.to_thread(mark_notified, event.url)
            except Exception as e:
                writeLog(f"mark_notified failed for {event.url}: {e}", "ERROR")
        finally:
            queue.task_done()
```

### Anti-Patterns to Avoid

- **Reading env vars inside `send()`** — env vars resolve once at process start in practice; reading per event is wasted syscalls and makes test monkeypatching brittle.
- **Catching `BaseException` in fan-out** — `return_exceptions=True` already neutralizes per-coroutine raises. Wrapping in a broader try inside `send()` hides bugs.
- **Putting dedup inside `poll_plugin`** — multi-producer dedup needs a lock or a write-then-read SQL pattern. Keep dedup in the single-consumer writer to avoid that complexity.
- **Adding outer try/except around the writer loop** — Phase 4 Pitfall 4-10. Writer crashes are fatal by design.
- **Mixing channel state in NotificationEvent** — the event is "what happened," not "what to send." Channel-specific formatting lives in each `send()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SMTP STARTTLS handshake | Raw socket TLS upgrade | `smtplib.SMTP().starttls()` | Stdlib handles cert verification, line termination, SMTP state machine. |
| Twilio request signing | Raw POST to `api.twilio.com` with basic auth | `twilio.rest.Client` | SDK handles retry, error types, auth, helper URL building. |
| Discord embed JSON validation | Manual schema check | Let Discord 400 you and log the body | Embed spec is small; failing fast on Discord's 400 is fine for v1. |
| Per-notifier circuit breaker | Custom failure counter + cooldown | None (v1) | Out of scope; one missed alert is acceptable. v2 idea. |
| MIME multipart construction | String formatting | `email.mime.multipart.MIMEMultipart` + `email.mime.text.MIMEText` | Quoted-printable + boundary handling is fiddly. |

**Key insight:** Notifications are stateless one-shot calls. We do NOT need queueing-with-retry, durable delivery guarantees, or back-pressure controls beyond `asyncio.Queue(maxsize=200)`. A skipped alert because a webhook is briefly down is acceptable; a bot that wedges because a notification path is buggy is not.

---

## Research Question 1: Discord Webhook + 429 Handling

### Verified Facts

- 429 response body: `{ "message": "You are being rate limited.", "retry_after": <float seconds>, "global": true|false }` [CITED: https://discord.com/developers/docs/topics/rate-limits]
- `Retry-After` HTTP header is also sent (HTTP-standard seconds; integer or float). [CITED: same]
- Webhook URL format: `https://discord.com/api/webhooks/<id>/<token>` (server admin generates).
- Webhook rate limit: 30 requests/minute/webhook URL. v1 polling rate is well below this even with 10 items polling every 5s.
- Embed object schema (relevant subset): `title` (str ≤ 256), `description` (str ≤ 4096), `url` (str), `color` (int, decimal RGB), `timestamp` (ISO 8601 with `Z` or `+00:00`), `fields` (list of `{name, value, inline}`).

### Recommended Policy

**Honor `Retry-After` header once, single retry, then give up + log.**

Rationale:
- Exponential backoff with N retries blocks the writer task for that channel; with `gather(return_exceptions=True)` the other channels are unaffected, but each retry consumes the writer for the gather duration.
- v1 SLA: a missed Discord alert is acceptable; a wedged writer is not.
- Single retry covers transient bucket exhaustion. Persistent 429 means we are misconfigured; logging is the right response.

### Minimal Embed Payload

```python
import requests
from datetime import timezone

def _build_payload(event):
    color = 0x2ECC71 if event.action == "detected" else 0x3498DB
    return {
        "embeds": [{
            "title": f"{event.platform}: {event.item_name}",
            "description": f"Action: **{event.action}**",
            "url": event.url,
            "color": color,
            "timestamp": event.timestamp.astimezone(timezone.utc).isoformat(),
            "fields": [
                {"name": "Platform", "value": event.platform, "inline": True},
                {"name": "Action",   "value": event.action,   "inline": True},
            ],
        }]
    }


def _post_with_one_retry(webhook_url: str, payload: dict) -> None:
    r = requests.post(webhook_url, json=payload, timeout=10)
    if r.status_code == 429:
        # Prefer header; fall back to body field. Cap at 30s to bound writer block.
        wait = float(r.headers.get("Retry-After") or r.json().get("retry_after", 1))
        time.sleep(min(wait, 30.0))
        r = requests.post(webhook_url, json=payload, timeout=10)
    r.raise_for_status()
```

Inside the notifier's async `send()`: `await asyncio.to_thread(_post_with_one_retry, self.url, payload)`.

### Webhook URL Source

Read from env `SHOPBOT_DISCORD_WEBHOOK_URL` in `__init__`. If env var missing and config says `discord.enabled=true`: set `self.enabled = False`, log WARNING distinguishing the missing surface (mirrors SMS two-lock pattern from D-04).

---

## Research Question 2: SMTP TLS vs STARTTLS

### Verified Facts

- Port 465 = SMTPS (implicit TLS): use `smtplib.SMTP_SSL(host, 465)`.
- Port 587 = Submission with STARTTLS: use `smtplib.SMTP(host, 587)` then `.starttls()` then `.login()`.
- Gmail (`smtp.gmail.com`), Office365 (`smtp.office365.com`), Fastmail, AWS SES, SendGrid all support both; 587/STARTTLS is the modern recommended default per RFC 6409.

### Recommendation

**Default to port 587 + STARTTLS.** Make port configurable; auto-select SSL vs STARTTLS by port:

```python
def _send_smtp(host, port, user, password, msg) -> None:
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(user, password)
            s.send_message(msg)
```

### Minimal MIME Build

```python
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def _build_message(event, from_addr, to_addr) -> MIMEMultipart:
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

### Connection Pooling

Skip. v1 send rate is ≤ 1/min/channel. Per-send `with smtplib.SMTP(...) as s:` is correct and simpler.

---

## Research Question 3: Twilio Python SDK

### Verified Facts

- Latest stable: **9.10.9**, released 2026-05-07. [VERIFIED: pypi.org/project/twilio]
- Supports Python 3.7-3.13. Project targets Python 3.11+ — compatible.
- Minimal usage:

```python
from twilio.rest import Client

client = Client(account_sid, auth_token)
message = client.messages.create(
    to="+15551234567",
    from_=os.environ["SHOPBOT_TWILIO_FROM"],
    body=f"{event.platform} stock: {event.item_name} {event.url}",
)
```

- Note `from_` (trailing underscore) because `from` is a Python keyword. CONTEXT pitfall #5 (`from_addr` confusion) is encoded by this constraint.
- Errors: `twilio.base.exceptions.TwilioRestException`. Catch this specifically; let unexpected exceptions propagate (they bubble through `gather(return_exceptions=True)` and get logged).

### Test Credentials Path

Twilio provides test credentials (Account SID prefixed `AC...test...`) that hit a stub endpoint and never send real SMS. Per CONTEXT.md Claude's Discretion: in `test_mode`, the SMS notifier is the right place to skip entirely — set `self.enabled = False` if `app_config.debug.test_mode is True`. Simpler than coordinating test-credential injection; cheaper than accidental sends.

### Recommended Pin

`twilio==9.10.9` in `requirements.txt`. Pin tightly per INFRA-01.

---

## Research Question 4: Idempotent SQLite ALTER TABLE

SQLite supports `ALTER TABLE items ADD COLUMN last_notified_at TIMESTAMP NULL` natively. Plain `ADD COLUMN` is NOT idempotent — re-running raises `sqlite3.OperationalError: duplicate column name`. Wrap with a `PRAGMA table_info` precheck.

```python
def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _migrate_add_last_notified_at(conn) -> None:
    if not _column_exists(conn, "items", "last_notified_at"):
        conn.execute(
            "ALTER TABLE items ADD COLUMN last_notified_at TIMESTAMP NULL"
        )
```

Wire inside `initialize_db()` after the `CREATE TABLE IF NOT EXISTS items (...)` block. The CREATE statement still ships the column for fresh installs (idempotency via `IF NOT EXISTS` + the table_info check covers all four paths: fresh-install, fresh-init-after-delete, existing-v1-no-column, existing-v2-column-present).

### CREATE TABLE update (Wave 1 plan)

```sql
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    link TEXT NOT NULL UNIQUE,
    auto_buy BOOLEAN NOT NULL,
    quantity INTEGER NOT NULL,
    purchased BOOLEAN NOT NULL DEFAULT 0,
    last_notified_at TIMESTAMP NULL          -- new in Phase 5
)
```

The migration call below adds the column to legacy DBs:

```python
def initialize_db(delete: bool = False) -> None:
    # ... existing code through CREATE TABLE IF NOT EXISTS ...
    with _connect() as conn:
        # ... existing journal_mode + CREATE TABLE ...
        _migrate_add_last_notified_at(conn)
```

---

## Research Question 5: pygame Thread Safety

### Findings

- `pygame.mixer.music` is a **single-channel** (single-track) API. Calling `.load()` while another track is playing replaces it. Concurrent calls from multiple threads can interleave a `.load()` between another thread's `.load()` and `.play()`, causing silent truncation.
- `pygame.mixer.Sound` supports up to 8 simultaneous channels by default; using `Sound` instead of `music` would be more concurrent-friendly. But `utils.py` currently uses `pygame.mixer.music`, and changing that is outside Phase 5 scope.
- pygame's official docs do not explicitly guarantee `mixer.music` thread safety. [CITED: pygame docs — best-effort claim, treat as MEDIUM confidence]

### Recommendation

Wrap pygame calls inside `shopbot_notifier_sound.py` with a class-level `threading.Lock`. This is cheap (3 lines), prevents the interleave, and contains the kludge to one notifier:

```python
import asyncio
import threading
from utils import play_available_sound, play_buy_sound

class SoundNotifier(Notifier):
    name = "sound"
    _lock = threading.Lock()

    def __init__(self, sound_config) -> None:
        self.enabled = sound_config.enabled

    async def send(self, event: NotificationEvent) -> None:
        if event.action == "purchased":
            fn = play_buy_sound
        else:
            fn = play_available_sound
        await asyncio.to_thread(self._play_locked, fn)

    @classmethod
    def _play_locked(cls, fn) -> None:
        with cls._lock:
            fn()
```

### Action-to-sound Mapping

- `action="detected"` → `play_available_sound()` (existing semantic)
- `action="purchased"` → `play_buy_sound()` (existing semantic)
- `play_notification_sound()` from utils.py is currently unused by the orchestrator post-Phase-4; the sound notifier does not need to call it. Document this in the plan.

---

## Research Question 6: Async Test Patterns

### Recommendation: monkeypatch directly

Use stdlib `unittest.mock` (already available, no new dep) plus pytest's `monkeypatch` fixture. This matches the Phase 4 style and adds zero new test deps.

### Discord notifier test

```python
import pytest
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_discordNotifierPostsEmbed(monkeypatch):
    posted = []
    def fakePost(url, json, timeout):
        posted.append((url, json))
        r = MagicMock()
        r.status_code = 204
        r.raise_for_status = lambda: None
        return r
    monkeypatch.setattr("notifiers.shopbot_notifier_discord.requests.post", fakePost)
    monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/x")
    from notifiers.shopbot_notifier_discord import DiscordNotifier
    n = DiscordNotifier(discordConfig)
    await n.send(event)
    assert posted[0][1]["embeds"][0]["url"] == event.url
```

### SMTP notifier test

```python
@pytest.mark.asyncio
async def test_emailNotifierUsesStarttls(monkeypatch):
    sent = []
    class FakeSmtp:
        def __init__(self, host, port, timeout): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def ehlo(self): pass
        def starttls(self): sent.append("starttls")
        def login(self, u, p): sent.append("login")
        def send_message(self, m): sent.append(("send", m["Subject"]))
    monkeypatch.setattr("notifiers.shopbot_notifier_email.smtplib.SMTP", FakeSmtp)
    monkeypatch.setenv("SHOPBOT_SMTP_PASSWORD", "x")
    # ...
```

### Twilio notifier test

Patch `twilio.rest.Client` at the notifier's import path:

```python
@pytest.mark.asyncio
async def test_smsNotifierCallsTwilioCreate(monkeypatch):
    created = []
    class FakeMessages:
        def create(self, **kw): created.append(kw)
    class FakeClient:
        def __init__(self, sid, token): pass
        @property
        def messages(self): return FakeMessages()
    monkeypatch.setattr("notifiers.shopbot_notifier_sms.Client", FakeClient)
    monkeypatch.setenv("SHOPBOT_ENABLE_SMS", "true")
    monkeypatch.setenv("SHOPBOT_TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("SHOPBOT_TWILIO_AUTH_TOKEN", "x")
    monkeypatch.setenv("SHOPBOT_TWILIO_FROM", "+15550001111")
    # ...
```

Reject `responses` library and `pytest-smtpd` as new deps: monkeypatch is sufficient, and the existing Phase 4 test pattern already uses monkeypatch heavily.

---

## Research Question 7: NotificationEvent Shape

### Final Shape (locked recommendation)

```python
@dataclass(frozen=True)
class NotificationEvent:
    item_name: str
    url: str
    platform: str
    timestamp: datetime         # tz-aware UTC (Pitfall 9 from CONTEXT.md)
    action: Literal["detected", "purchased"]
```

- `frozen=True`: enables hashability if dedup ever moves off-DB (cache key), and prevents accidental in-flight mutation.
- `timestamp`: tz-aware `datetime` (`datetime.now(timezone.utc)`). NOT ISO 8601 string — each notifier formats per its channel needs (Discord wants ISO 8601, SMTP wants RFC 2822-ish, SMS wants short).
- `action`: `Literal["detected", "purchased"]` only. Other future actions ("error", "captcha") deferred to v2.

### Event Creation Site

**Orchestrator (poll_plugin), not plugin.** Plugins must remain ignorant of NotificationEvent — that keeps Phase 2's plugin contract minimal. Add event creation in `main._poll_once`:

```python
# in _poll_once, after available is True:
play_available_sound()  # remove once sound notifier is wired (see Question 10)
writeLog(f"{name} is available: {make_tiny(link)}", "SUCCESS")
await notification_queue.put(NotificationEvent(
    item_name=name,
    url=link,
    platform=plugin.name,
    timestamp=datetime.now(timezone.utc),
    action="detected",
))
if autoBuy:
    await _attempt_purchase(plugin, link, app_config, purchase_queue, notification_queue)
elif open_browser:
    webbrowser.open(link)
```

And in `_attempt_purchase`, on success:

```python
# inside _attempt_purchase, after auto_buy succeeds:
play_buy_sound()        # remove once sound notifier is wired
await purchase_queue.put((link,))
await notification_queue.put(NotificationEvent(
    item_name="(unknown)",       # see Open Question O-3 below
    url=link,
    platform=plugin.name,
    timestamp=datetime.now(timezone.utc),
    action="purchased",
))
```

---

## Research Question 8: should_notify / mark_notified Atomicity

### Single-Writer Argument

Only `notification_writer` calls `should_notify` and `mark_notified`. No race window exists between the read and the write. The orchestrator's `poll_plugin` does NOT touch dedup state — it produces raw events.

### Failure Mode

If `mark_notified` fails after a successful `gather` of notifier sends: next event re-fires all channels. Acceptable trade-off for v1 per CONTEXT.md Specifics pitfall #1 (catch + log + continue; do NOT crash writer).

### Helper Signatures (snake_case to match models.py local convention)

```python
def should_notify(link: str, restock_window_seconds: int) -> bool:
    """True if last_notified_at is NULL or older than restock_window_seconds."""
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
    """Set last_notified_at = CURRENT_TIMESTAMP for the given link."""
    with _connect() as conn:
        conn.execute(
            "UPDATE items SET last_notified_at = CURRENT_TIMESTAMP WHERE link = ?",
            (link,),
        )
```

Note: `CURRENT_TIMESTAMP` in SQLite stores UTC tz-naive in `YYYY-MM-DD HH:MM:SS` format. The `fromisoformat` parse + tzinfo backfill above is correct for Python 3.11+. [VERIFIED: read of models.py existing patterns]

### Dedup Per Action

**Important:** The dedup window should NOT block a `purchased` event when a `detected` event for the same item just fired. They are semantically different — "we saw stock" vs. "we bought it." Two options:

- (A) Include `action` in the dedup key. `last_notified_detected_at` + `last_notified_purchased_at` columns. **Heavier schema.**
- (B) Skip dedup entirely for `action="purchased"` (always fire). **Simpler.** Purchased events are by definition rare (one-shot) so the dedup window adds no value.

**Recommend (B).** Implementation: `notification_writer` checks `if event.action == "detected" and not should_notify(event.url, restock_window): continue`. Purchased events bypass the gate. `mark_notified` only fires after detected events (purchased events don't pollute the dedup state).

---

## Research Question 9: NotificationsConfig Pydantic Shape

```python
# config_schema.py additions

from pydantic import BaseModel, Field, EmailStr


class SoundNotifierConfig(BaseModel):
    enabled: bool = True


class DiscordNotifierConfig(BaseModel):
    enabled: bool = False
    # webhook_url comes from SHOPBOT_DISCORD_WEBHOOK_URL env, not config.yml (SEC-01).


class EmailNotifierConfig(BaseModel):
    enabled: bool = False
    from_addr: EmailStr | None = None
    to_addr: EmailStr | None = None
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


# in AppConfig:
class AppConfig(BaseSettings):
    # ...existing fields...
    notifications: NotificationsConfig = NotificationsConfig()
```

### Why this shape

- All channel sub-models default to `enabled=False` except sound (matches existing behavior — sound already fires today).
- All channel-specific connection details (host, port, addrs) optional with `None` default. The notifier's `__init__` validates required fields are present when `enabled=True` and sets `self.enabled=False` with a WARNING log if anything is missing.
- `from_addr` / `to_addr` use `EmailStr` for Pydantic email validation at config load time. NOTE: `EmailStr` requires `email-validator` package. If we want to avoid the dep, downgrade to `str` — sufficient for v1. **Recommend `str`** to keep the dep footprint at +1 (twilio only).
- Restock window is at the top-level of `notifications`, not per-channel — single source of truth for dedup window.

### Env var override surface

`pydantic-settings` already routes `SHOPBOT_NOTIFICATIONS__DISCORD__ENABLED=true` to `notifications.discord.enabled` via the existing `env_nested_delimiter="__"`. No schema change needed for env override — config.yml is the primary path; env can override for testing.

---

## Research Question 10: Phase 4 Integration Touchpoints

### main.py Changes (Plan: orchestrator integration)

1. **Import additions:**
   ```python
   from datetime import datetime, timezone
   from notifier_base import NotificationEvent
   from notifier_registry import discover_notifiers
   from models import should_notify, mark_notified
   ```

2. **In `main()` after `discover_async(...)`:**
   ```python
   notifiers = await discover_notifiers(Path("notifiers"), app_config=app_config)
   ```

3. **Queue setup (next to purchase_queue):**
   ```python
   notification_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
   ```

4. **TaskGroup additions:**
   ```python
   async with asyncio.TaskGroup() as tg:
       tg.create_task(purchase_writer(purchase_queue))
       tg.create_task(notification_writer(
           notification_queue, notifiers, app_config.notifications.restock_window_seconds
       ))
       for plugin in registry:
           tg.create_task(poll_plugin(
               plugin, app_config, purchase_queue, notification_queue, stop_event,
           ))
   ```

5. **Shutdown loop extension:**
   ```python
   async def _shutdown_plugins_and_notifiers(registry, notifiers) -> None:
       await asyncio.gather(
           *(asyncio.shield(p.shutdown()) for p in registry),
           *(asyncio.shield(n.shutdown()) for n in notifiers),
           return_exceptions=True,
       )
   ```

6. **`poll_plugin` / `_poll_once` signature widens to accept `notification_queue`:** event creation site is `_poll_once` (after `available=True`) and `_attempt_purchase` (after auto_buy success).

7. **Sound notifier conflict with existing inline `play_available_sound()` / `play_buy_sound()` calls:** the existing inline calls in `main.py` should be REMOVED once the sound notifier is wired. Otherwise sound fires twice. Make this explicit in the orchestrator integration plan: delete the two `play_*_sound()` lines from `_poll_once` and `_attempt_purchase`.

### Test-mode behavior

CONTEXT.md says (Claude's discretion): "in test_mode, disable Twilio entirely, keep Discord + Email." Implementation: at `notifier_registry.discover_notifiers` time, after instantiation, run a pass:

```python
if app_config.debug.test_mode:
    for n in instances:
        if n.name == "sms":
            n.enabled = False
            writeLog("test_mode: SMS notifier disabled", "INFO")
```

Or push the check into the SMS notifier's `__init__` (it already needs the test_mode flag for the two-lock check). **Recommend the latter** — keeps the policy local to the notifier.

---

## Research Question 11: Anti-Patterns to Encode as must_haves

Numbered for direct copy into plan `must_haves.truths`:

1. Notifiers MUST read secrets (env vars) exactly once, in `__init__`. Reading in `send()` is FORBIDDEN — verified via static AST check or by setting an env var after `__init__` and asserting it is NOT picked up.
2. The `notification_writer` MUST NOT have an outer try/except wrapping its `while True` loop. A writer crash is FATAL by design (mirrors Phase 4 Pitfall 4-10). Inner try/except/finally around the event-processing body is REQUIRED for `queue.task_done()`.
3. Per-notifier exceptions inside `gather()` MUST NOT propagate — `return_exceptions=True` is required, and the writer MUST iterate the results to log each exception with the notifier's `.name` and the event URL.
4. `queue.task_done()` MUST be called in a `finally` block, not at the end of a try block. Otherwise the event-processing exception path skips `task_done` and `queue.join()` hangs (Phase 4 Pitfall 4-5).
5. `pygame.mixer.music.load()` and `.play()` calls inside the sound notifier MUST be guarded by a `threading.Lock` (class-level). Concurrent worker threads otherwise interleave and truncate.
6. SMS notifier MUST verify BOTH locks (config.notifications.sms.enabled is True AND env SHOPBOT_ENABLE_SMS=="true") at `__init__` time. Failing at send time means burned cycles on every event.
7. SMS notifier's two-lock failure log MUST distinguish "config off" from "env off" from "both off" so the user can debug (CONTEXT.md Specifics pitfall #10).
8. NotificationEvent.timestamp MUST be tz-aware UTC (`datetime.now(timezone.utc)`). Tz-naive timestamps poison SQLite storage and break `datetime - last` arithmetic in `should_notify`.
9. `should_notify`/`mark_notified` MUST use the `_connect()` context manager from `models.py`. Raw `sqlite3.connect` calls in those helpers FORBIDDEN (mirrors the Plan 04-02 AST static guard).
10. The `ALTER TABLE items ADD COLUMN last_notified_at` migration in `initialize_db` MUST be idempotent via a `PRAGMA table_info(items)` precheck. Re-running otherwise raises `OperationalError: duplicate column name`.
11. The Discord webhook 429 retry MUST be capped (≤ 30 seconds and ≤ 1 retry). Unbounded retry blocks the writer for that gather call.
12. Twilio `messages.create` call MUST use `from_=` (trailing underscore), NEVER `from=` (Python keyword) or `from_addr=` (wrong Twilio kwarg).
13. The SMS notifier MUST set `self.enabled = False` (NOT call `sys.exit` or raise) when locks fail or when `app_config.debug.test_mode is True`. Disabling cleanly keeps other channels live.
14. `notification_writer` MUST NOT call `mark_notified` for `action="purchased"` events. Purchased events are not deduped (rare, semantically distinct from "detected").
15. The orchestrator MUST remove the inline `play_available_sound()` / `play_buy_sound()` calls from `main._poll_once` and `main._attempt_purchase` when the sound notifier is wired. Otherwise sounds fire twice per event.
16. Discord webhook URL, SMTP password, Twilio creds MUST NOT appear in `config.yml`, `sample.config.yml`, logs, or commit history. Env-var-only (SEC-01 extension).
17. `notification_writer`'s `mark_notified` call MUST be wrapped in try/except — a transient SQL failure here MUST log + continue, NOT crash the writer (CONTEXT.md Specifics pitfall #1).

---

## Recommended Plan Layout

Five plans across three waves. Wave 0 ships test infrastructure; Waves 1 + 2 ship code in parallel where safe.

### Wave 0 (sequential, blocks everything)

**Plan 05-01 — Test infra + ABC + config schema + models migration**
- Append `twilio==9.10.9` to `requirements.txt`.
- Create `notifier_base.py` with `Notifier` ABC and `NotificationEvent` dataclass.
- Extend `config_schema.py` with `NotificationsConfig` + `SoundNotifierConfig` + `DiscordNotifierConfig` + `EmailNotifierConfig` + `SmsNotifierConfig` + `notifications: NotificationsConfig` field on AppConfig.
- Extend `models.py`: add `last_notified_at` to CREATE TABLE, add `_migrate_add_last_notified_at(conn)` helper, add `should_notify(link, window_seconds)` + `mark_notified(link)`, hook migration into `initialize_db`.
- Create RED skeleton tests:
  - `tests/test_notifier_base.py` — ABC contract (`send` is abstract async, `shutdown` is async with default)
  - `tests/test_models_notification_dedup.py` — `should_notify` returns True for null, True after window, False inside window; `mark_notified` updates column; idempotent migration.
  - `tests/test_notifier_registry.py` — RED on `discover_notifiers` (does not exist yet).
  - `tests/test_notification_writer.py` — RED on `notification_writer` symbol (does not exist yet).
  - `tests/test_notifiers_*.py` — RED on each notifier class (do not exist yet). One file per channel.
- All tests RED at end of plan. Subsequent plans drive RED -> GREEN per file.

### Wave 1 (parallel-safe, depends only on Wave 0)

**Plan 05-02 — notifier_registry + sound notifier**
- Create `notifier_registry.py` mirroring `plugin_registry.py` (drop `domain_pattern` + `verify_coverage`).
- Create `notifiers/__init__.py` + `notifiers/shopbot_notifier_sound.py`.
- Drive `tests/test_notifier_registry.py` and `tests/test_notifiers_sound.py` to GREEN.
- No network, no external deps. Lowest risk; ships first.

**Plan 05-03 — Discord notifier**
- Create `notifiers/shopbot_notifier_discord.py` with embed builder + `_post_with_one_retry`.
- Read `SHOPBOT_DISCORD_WEBHOOK_URL` from env; disable cleanly if missing.
- Drive `tests/test_notifiers_discord.py` to GREEN (monkeypatch `requests.post`; cover 204 success, 429-once-then-success, 429-once-then-give-up).

**Plan 05-04 — Email notifier**
- Create `notifiers/shopbot_notifier_email.py` with port-587-STARTTLS default, port-465-SSL alt path, MIMEMultipart builder.
- Read `SHOPBOT_SMTP_PASSWORD` from env; disable if missing.
- Drive `tests/test_notifiers_email.py` to GREEN (monkeypatch `smtplib.SMTP` + `smtplib.SMTP_SSL`; cover STARTTLS sequence, port routing, send_message arg shape).

**Plan 05-05 — SMS notifier (two-lock opt-in)**
- Create `notifiers/shopbot_notifier_sms.py`.
- Two-lock check at `__init__`: config.notifications.sms.enabled AND env SHOPBOT_ENABLE_SMS=="true". Disable + log distinguishing WARNING if either lock fails. Also disable if `app_config.debug.test_mode is True`.
- Use `twilio.rest.Client(sid, token).messages.create(to=..., from_=..., body=...)`.
- Catch `twilio.base.exceptions.TwilioRestException` and re-raise with sanitized message (no creds leaked).
- Drive `tests/test_notifiers_sms.py` to GREEN.

**Wave 1 parallel-safety:** All four plans touch only newly-created files in `notifiers/` plus their own dedicated test files. Zero shared mutation. Safe to run as 4 parallel tasks once Wave 0 lands.

### Wave 2 (sequential, depends on all of Wave 1)

**Plan 05-06 — Orchestrator integration**
- Modify `main.py`:
  - Add `notification_queue = asyncio.Queue(maxsize=200)`.
  - Call `await discover_notifiers(Path("notifiers"), app_config=app_config)` after `discover_async`.
  - Add `notification_writer(...)` task to TaskGroup.
  - Widen `poll_plugin` / `_poll_once` / `_attempt_purchase` signatures to thread `notification_queue` through.
  - Add `NotificationEvent(action="detected")` put in `_poll_once` after `available=True`.
  - Add `NotificationEvent(action="purchased")` put in `_attempt_purchase` after auto_buy success.
  - REMOVE the inline `play_available_sound()` and `play_buy_sound()` calls from main.py (sound notifier now owns this).
  - Extend `_shutdown_plugins` to `_shutdown_plugins_and_notifiers` (shield both).
- Drive `tests/test_notification_writer.py` to GREEN (fan-out, gather isolation, dedup gating, mark_notified-on-detected-only, task_done in finally).
- Add 2-3 integration smoke tests in `tests/test_orchestrator.py`: NotificationEvent created with tz-aware UTC; sound notifier inline-call sites are removed (AST grep); `notification_writer` is in the TaskGroup.

### Wave gating summary

| Wave | Plans | Parallel-safe? | Blocking dep |
|------|-------|----------------|--------------|
| 0 | 05-01 | No (1 plan) | — |
| 1 | 05-02, 05-03, 05-04, 05-05 | **Yes (4-way)** | 05-01 complete |
| 2 | 05-06 | No (integration) | All of Wave 1 complete |

---

## New Dependency Pins

| Package | Version | Justification | Already in tree? |
|---------|---------|---------------|-------------------|
| `twilio` | 9.10.9 | SMS via Twilio REST API; official SDK; gives `TwilioRestException` typing | NO — new dep |
| (no test deps) | — | monkeypatch + unittest.mock cover all four notifiers without `responses`, `pytest-smtpd`, or `respx` | n/a |

Append to `requirements.txt` after `pytest-asyncio==1.3.0`:

```
twilio==9.10.9
```

## Validation Architecture

Per-requirement automated test coverage (`workflow.nyquist_validation = true` is the project default).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 + pytest-asyncio 1.3.0 (`asyncio_mode=auto`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run | `python -m pytest tests/test_notifiers_*.py tests/test_notification_writer.py tests/test_models_notification_dedup.py -x` |
| Full suite | `python -m pytest --ignore=tests/test_utils.py` |
| Phase gate | All NOTIF-* targeted tests green + full suite green |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| NOTIF-01 | Per-channel failure isolated; other channels still fire | unit + integration | `pytest tests/test_notification_writer.py::test_oneFailedNotifierDoesNotBlockOthers -x` | NO — Plan 05-01 RED |
| NOTIF-01 | Writer crash is fatal (no outer try/except) | AST static | `pytest tests/test_notification_writer.py::test_writerCrashIsFatal -x` | NO — Plan 05-01 RED |
| NOTIF-02 | `should_notify` returns False inside window | unit | `pytest tests/test_models_notification_dedup.py::test_shouldNotifyFalseInsideWindow -x` | NO — Plan 05-01 RED |
| NOTIF-02 | `should_notify` returns True after window | unit | `pytest tests/test_models_notification_dedup.py::test_shouldNotifyTrueAfterWindow -x` | NO — Plan 05-01 RED |
| NOTIF-02 | `mark_notified` updates the column | unit | `pytest tests/test_models_notification_dedup.py::test_markNotifiedSetsTimestamp -x` | NO — Plan 05-01 RED |
| NOTIF-02 | Migration idempotent | unit | `pytest tests/test_models_notification_dedup.py::test_migrationIdempotent -x` | NO — Plan 05-01 RED |
| NOTIF-02 | Dedup gate skipped for action=purchased | unit | `pytest tests/test_notification_writer.py::test_purchasedActionBypassesDedup -x` | NO — Plan 05-01 RED |
| NOTIF-03 | Sound notifier wraps play_*_sound in to_thread | AST | `pytest tests/test_notifiers_sound.py::test_sendUsesAsyncToThread -x` | NO — Plan 05-01 RED |
| NOTIF-03 | Sound notifier holds threading.Lock | unit | `pytest tests/test_notifiers_sound.py::test_concurrentSendsSerialized -x` | NO — Plan 05-01 RED |
| NOTIF-03 | Inline play_*_sound removed from main.py | AST grep | `pytest tests/test_orchestrator.py::test_noInlineSoundCalls -x` | (exists — extend) |
| NOTIF-04 | Embed payload shape | unit | `pytest tests/test_notifiers_discord.py::test_embedShape -x` | NO — Plan 05-01 RED |
| NOTIF-04 | 429 honored once then succeeds | unit | `pytest tests/test_notifiers_discord.py::test_429RetryOnce -x` | NO — Plan 05-01 RED |
| NOTIF-04 | 429 honored once then gives up | unit | `pytest tests/test_notifiers_discord.py::test_429GiveUpAfterOne -x` | NO — Plan 05-01 RED |
| NOTIF-04 | Webhook URL read from env at __init__ | unit | `pytest tests/test_notifiers_discord.py::test_urlReadAtInit -x` | NO — Plan 05-01 RED |
| NOTIF-05 | STARTTLS sequence on port 587 | unit | `pytest tests/test_notifiers_email.py::test_starttlsOn587 -x` | NO — Plan 05-01 RED |
| NOTIF-05 | SMTP_SSL on port 465 | unit | `pytest tests/test_notifiers_email.py::test_smtpsslOn465 -x` | NO — Plan 05-01 RED |
| NOTIF-05 | MIME multipart subject/from/to | unit | `pytest tests/test_notifiers_email.py::test_messageHeaders -x` | NO — Plan 05-01 RED |
| NOTIF-05 | Password from env, not config | unit | `pytest tests/test_notifiers_email.py::test_passwordFromEnv -x` | NO — Plan 05-01 RED |
| NOTIF-06 | Two-lock check disables when config off | unit | `pytest tests/test_notifiers_sms.py::test_disabledIfConfigOff -x` | NO — Plan 05-01 RED |
| NOTIF-06 | Two-lock check disables when env off | unit | `pytest tests/test_notifiers_sms.py::test_disabledIfEnvOff -x` | NO — Plan 05-01 RED |
| NOTIF-06 | Both locks pass enables notifier | unit | `pytest tests/test_notifiers_sms.py::test_enabledWhenBothLocksPass -x` | NO — Plan 05-01 RED |
| NOTIF-06 | test_mode disables SMS | unit | `pytest tests/test_notifiers_sms.py::test_testModeDisablesSms -x` | NO — Plan 05-01 RED |
| NOTIF-06 | Twilio kwargs use from_= not from= | AST | `pytest tests/test_notifiers_sms.py::test_twilioFromUnderscore -x` | NO — Plan 05-01 RED |

### Sampling Rate

- **Per task commit:** Plan-targeted test file (e.g., `pytest tests/test_notifiers_discord.py -x` inside Plan 05-03).
- **Per wave merge:** All Phase 5 tests (`pytest tests/test_notifiers_*.py tests/test_notification_writer.py tests/test_models_notification_dedup.py -x`).
- **Phase gate:** Full suite green before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `tests/test_notifier_base.py` — ABC contract assertions
- [ ] `tests/test_models_notification_dedup.py` — covers NOTIF-02
- [ ] `tests/test_notifier_registry.py` — discovery semantics
- [ ] `tests/test_notification_writer.py` — covers NOTIF-01 + dedup gating + task_done
- [ ] `tests/test_notifiers_sound.py` — covers NOTIF-03
- [ ] `tests/test_notifiers_discord.py` — covers NOTIF-04
- [ ] `tests/test_notifiers_email.py` — covers NOTIF-05
- [ ] `tests/test_notifiers_sms.py` — covers NOTIF-06

Shared fixtures from Plan 04-01 (`tmpDbPath`, `appConfigStub`, `fakePluginFactory`) cover most needs. New fixture: `fakeNotifierFactory` parallel to `fakePluginFactory` — builds Notifier subclasses with configurable `send` behavior (return None / raise / record call). Add to `tests/conftest.py` in Plan 05-01.

## Pitfalls (Will Become must_haves.truths)

See "Research Question 11: Anti-Patterns" above for the numbered 17-item list. All 17 are derived from either the CONTEXT.md specifics block, Phase 4 SUMMARY hard-won lessons, or this research's tool verification of Discord/SMTP/Twilio specifics.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | (SMTP/Twilio auth handled by SDK; not user-facing auth) |
| V3 Session Management | no | Stateless one-shot calls |
| V4 Access Control | no | Out-of-process notification; no user perms |
| V5 Input Validation | yes | Pydantic `NotificationsConfig` validates config.yml; `extra=forbid` already set on AppConfig |
| V6 Cryptography | yes | `smtplib.SMTP().starttls()` + `requests` HTTPS — never hand-roll TLS |
| V7 Error Handling | yes | Notifier exceptions logged with `writeLog`; no creds in messages (sanitize TwilioRestException output) |
| V8 Data Protection | yes | Secrets via env vars only (SEC-01 extension); never in config.yml/logs/commits |
| V10 Configuration | yes | Two-lock SMS opt-in; defaults all `enabled=False` except sound |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Webhook URL leaked in commit | Info Disclosure | Env var only; .gitignore enforces no .env commits |
| Twilio cred leak via log | Info Disclosure | Catch `TwilioRestException` and `writeLog` sanitized message; never `str(exception)` raw |
| SMTP password in config.yml | Info Disclosure | Pydantic schema does NOT include `smtp_password` field; env var only |
| Accidental SMS bill from prod-shell env | Tampering (cost) | Two-lock check (D-04) at __init__; warns clearly if one lock is off |
| Discord rate-limit denial-of-service | Availability (self-inflicted) | Single retry + cap at 30s; do not block writer indefinitely |
| Notifier exception crashes bot | Denial of Service | `asyncio.gather(return_exceptions=True)` isolates per-notifier failures |
| Pygame interleave from concurrent threads | Denial of Service (silent UX) | Class-level `threading.Lock` in SoundNotifier |
| SQL injection via item link | Tampering | Parameterized queries already used in models.py; same pattern in `should_notify`/`mark_notified` |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | v1 notification volume stays at ≤ 1/min/item (justifies sync + to_thread over httpx/aiosmtplib) | Summary, Standard Stack | Higher rates would block worker threads. Mitigation: revisit pool size in main.py if volume changes. |
| A2 | pygame.mixer.music thread safety is best-effort; threading.Lock needed | Q5 | If pygame is actually thread-safe, lock is harmless (small perf hit). If pygame is worse than assumed, lock may be insufficient — would need `pygame.mixer.Sound` migration in utils.py. Verify by stress test if multi-channel sound issues surface. |
| A3 | EmailStr Pydantic type adds the email-validator transitive dep; we picked `str` to avoid it | Q9 | If we want stricter validation, accept the extra dep. Low risk. |
| A4 | Test mode disables SMS by default (per CONTEXT.md Claude's discretion) | Q10 | If test environments need to exercise the SMS code path, expose a separate flag. Trivial to relax later. |
| A5 | Dedup is by `link` (URL) not `id` (DB primary key) | Q8 helpers | Items dedup correctly because `link` has UNIQUE constraint in items table. Verified by reading models.py CREATE TABLE. |

## Open Questions

- **O-1**: Should `mark_notified` failures decrement a counter and disable the writer after N consecutive failures? **Recommendation:** No, v1 keeps it simple — log + continue (CONTEXT.md Specifics pitfall #1). v2 if SQL flakiness is observed.
- **O-2**: Should the orchestrator log a metric (count of events skipped due to dedup vs. fired) for ops visibility? **Recommendation:** Out of scope; v2 idea (analytics deferred per CONTEXT.md).
- **O-3**: For `action="purchased"` events, the orchestrator needs the item name. `_attempt_purchase` currently only has `link`. Either widen `_attempt_purchase` signature to thread `name` through, OR query `models.get_items()` for the row. **Recommendation:** Widen the signature in Plan 05-06 — cheaper than an extra SQL roundtrip and `name` is already in scope at the `_poll_once` caller.
- **O-4**: Should the sound notifier respect `app_config.debug.test_mode` and skip playback? **Recommendation:** No — sound is local, free, and useful as a "yes the test_mode loop reached the available branch" signal. Don't gate it on test_mode.
- **O-5**: `sample.config.yml` needs a `notifications:` example block (planner task in 05-01 or 05-06). Confirm scope at plan-time. **Recommendation:** Include in Plan 05-01 (Wave 0 ships schema; sample.config.yml is part of the schema deliverable).

## Sources

### Primary (HIGH confidence)
- `.planning/phases/05-notification-system/05-CONTEXT.md` — Locked decisions D-01..D-04, target shapes, pitfalls 1-10
- `.planning/REQUIREMENTS.md` — NOTIF-01..06 authoritative wording
- `.planning/phases/04-async-orchestrator/04-RESEARCH.md` + `04-*-SUMMARY.md` — Queue + writer pattern, async test infra, WAL + _connect contract
- `plugin_base.py`, `plugin_registry.py`, `models.py`, `main.py`, `config_schema.py`, `utils.py`, `credentials.py` — Direct codebase read
- https://discord.com/developers/docs/topics/rate-limits — Discord 429 + Retry-After spec (CITED)
- https://pypi.org/project/twilio/ — twilio 9.10.9 latest stable (VERIFIED 2026-05-07)

### Secondary (MEDIUM confidence)
- pygame.mixer.music thread-safety best-effort claim — official pygame docs do not guarantee, library convention is to serialize. Mitigated with `threading.Lock`.
- SMTP port 587/STARTTLS as modern default — RFC 6409 + provider docs (Gmail, Office365, SES). Single-source-per-provider but consistent.

### Tertiary (LOW confidence)
- None — all critical claims verified against codebase or official sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — twilio version verified at pypi; all other deps already in tree
- Architecture: HIGH — Phase 4 pattern is a known-good template, direct mirror
- Pitfalls: HIGH — CONTEXT.md specifics + Phase 4 hard-won lessons + verified channel-specific traps
- Discord retry policy: HIGH — official docs cited
- SMTP port choice: MEDIUM — multi-provider consistent but project-specific provider unknown
- pygame thread safety: MEDIUM — defensive lock is cheap and well-bounded

**Research date:** 2026-05-14
**Valid until:** 2026-06-13 (30 days; twilio releases monthly so re-verify version pin before plan implementation if more than 2 weeks elapse)
