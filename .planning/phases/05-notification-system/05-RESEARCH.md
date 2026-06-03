# Phase 5: Notification System - Research

**Researched:** 2026-06-03
**Domain:** Fan-out notification dispatcher — Discord webhook, SMTP, Twilio SMS, sound wrapping, SQLite dedup
**Confidence:** HIGH (all external API specifics verified against official docs; stdlib patterns cited from docs.python.org)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `Notifier` ABC with async `send(event)` method; config-driven dispatcher mirrors the RetailerPlugin registry pattern.
- Fan-out isolation: each notifier wrapped in its own try/except; a failing channel logs (channel name + error) and does NOT block other channels.
- Blocking sends (Discord POST, SMTP, Twilio HTTP) run via `run_in_executor` — never stall the async loop.
- Trigger point: orchestrator calls `dispatcher.notify(event)`; plugins do not notify themselves.
- Sound notifier wraps `play_available_sound()` / `play_buy_sound()` / `play_notification_sound()` from `utils.py`.
- **ZERO new packages.** Discord via `requests`. Email via stdlib `smtplib` + `email`. Twilio via raw `requests` POST. No `twilio` package.
- Dedup is edge-triggered: notify on unavailable -> available transition; suppress while still available. Per-item state + `last_notified` in SQLite via the Phase-4 write queue.
- Non-secret settings in `notifications` section of `config.yml`. Secrets from env only: `DISCORD_WEBHOOK_URL`, `SMTP_PASSWORD`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`.
- SMS DISABLED by default. Enabling requires `notifications.sms.enabled: true` AND Twilio env creds; if enabled without creds, raise a clear config error (not silent no-op).

### Claude's Discretion
- Module layout (`notifications/` package with one file per notifier, or `core/notifications.py`).
- Exact event dataclass shape.
- SQLite schema change (new column on items vs new table for last_notified/state).
- Embed/email formatting details, provided locked decisions hold.

### Deferred Ideas (OUT OF SCOPE)
- New platforms + per-platform delay/jitter/headless config (Phase 6).
- Rich notification templating / per-channel message customization beyond the standardized embed.
- A notification history UI or digest/batching.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NOTIF-01 | Notification dispatcher fan-outs to all configured channels; per-channel failures isolated | Notifier ABC + dispatcher loop with per-channel try/except; confirmed pattern in orchestrator |
| NOTIF-02 | Dedup: one notification per item per restock event; SQLite `last_notified` per item | Edge-trigger schema (two-column approach); write-queue path identical to Phase 4 |
| NOTIF-03 | Sound notifier wraps `play_available_sound()` / `play_buy_sound()` / `play_notification_sound()` | utils.py functions confirmed; simple wrapper pattern |
| NOTIF-04 | Discord webhook notifier posts standardized embed (name/URL/platform/timestamp/action) | Exact JSON payload shape verified against official Discord docs |
| NOTIF-05 | Email/SMTP notifier; configurable sender/recipient in config | stdlib smtplib + email.message.EmailMessage STARTTLS pattern verified from docs.python.org |
| NOTIF-06 | SMS/Twilio notifier; opt-in only; disabled by default; missing creds = clear error | Twilio Messages.json endpoint verified; startup validation pattern defined |
</phase_requirements>

---

## Summary

Phase 5 adds a fan-out notification dispatcher that sits between the orchestrator and four delivery channels: sound, Discord webhook, email (SMTP), and SMS (Twilio). The architecture is fully locked — the research task is to pin the exact API contracts so the planner can write precise task actions without ambiguity.

All three network channels have been verified against official documentation. Discord uses a single HTTP POST with an `embeds` array; success is HTTP 204, rate limits return HTTP 429 with a `Retry-After` header. Twilio uses HTTP Basic Auth (SID:token) against `https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json` with form-encoded body; success is HTTP 201. SMTP uses stdlib `smtplib.SMTP` on port 587 with `starttls()` + `login()` + `send_message()`, or `SMTP_SSL` on port 465 — both are pure stdlib, zero new packages.

The dedup data model requires two new columns on the existing `items` table: `last_seen_available` (INTEGER/BOOLEAN, default 0) and `last_notified` (TEXT/ISO-8601 timestamp, nullable). Edge-trigger logic: notify when `last_seen_available` transitions 0 -> 1; suppress if it is already 1. Reset to 0 on unavailable. All writes go through the Phase-4 write queue.

**Primary recommendation:** Use a `notifications/` sub-package (one file per notifier) registered by a `NotificationDispatcher` in `core/notifications.py`. The dispatcher is constructed in `async_main`, passed into `run_plugin`, and called in `_check_and_buy` after availability is confirmed and again after a successful purchase.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Dispatcher fan-out + isolation | Async Core | — | Lives in orchestrator layer; mirrors RetailerPlugin registry pattern |
| Sound delivery | Local Process | — | Wraps existing pygame calls in utils.py; synchronous, no network |
| Discord embed delivery | Network (outbound only) | Async Core (executor) | Blocking HTTP POST; run via run_in_executor |
| Email delivery | Network (outbound only) | Async Core (executor) | Blocking SMTP; run via run_in_executor |
| SMS delivery | Network (outbound only) | Async Core (executor) | Blocking HTTP POST; run via run_in_executor |
| Dedup state tracking | Database | Async Core (write queue) | SQLite columns on items table; all writes through write queue |
| Secret management | Environment | Config Schema | Env vars only; config.yml holds enable flags + non-secret settings |
| Startup config validation | Config Schema | main.py | Pydantic validator raises on SMS-enabled + missing creds |

---

## Standard Stack

### Core (zero new packages — all existing or stdlib)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `requests` | 2.33.1 (pinned) | Discord webhook POST + Twilio REST POST | Already in requirements.txt; standard HTTP client |
| `smtplib` | stdlib | SMTP connection management | Python stdlib since 2.0; no install needed |
| `email.message.EmailMessage` | stdlib | Construct RFC 5322 messages | Python stdlib; `send_message()` auto-handles BCC stripping |
| `sqlite3` | stdlib | Dedup state storage | Already used; extend existing schema |
| `dataclasses` or `pydantic` | stdlib / 2.13.3 | NotificationEvent data carrier | Pydantic already present; use dataclass for simplicity unless validation is needed |

### No Alternatives Considered
Architecture is locked to zero new packages. All channel transports are verified to work without additional dependencies.

**Version verification:** `requests==2.33.1` confirmed in `requirements.txt` (current as of pinning date). No new packages to verify.

---

## Package Legitimacy Audit

> No new packages are installed in this phase. All transports use existing dependencies (`requests` 2.33.1, stdlib `smtplib`, stdlib `email`).

| Package | Registry | Disposition |
|---------|----------|-------------|
| `requests` | PyPI (existing pin) | Already approved — in requirements.txt |
| `smtplib` | stdlib | No install required |
| `email` | stdlib | No install required |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
orchestrator._check_and_buy()
        |
        | available=True (or purchase complete)
        v
NotificationDispatcher.notify(event: NotificationEvent)
        |
        |-- try/except (per channel, isolated) --------+
        |                                               |
        +--[SoundNotifier]                              |
        |   play_available_sound() / play_buy_sound()   |
        |   (sync, no executor needed)                  |
        |                                               |
        +--[DiscordNotifier]  -- run_in_executor -->    |
        |   requests.post(DISCORD_WEBHOOK_URL, json=...) |
        |                                               |
        +--[EmailNotifier]    -- run_in_executor -->    |
        |   smtplib.SMTP(...).send_message(msg)         |
        |                                               |
        +--[SmsNotifier]      -- run_in_executor -->    |
            requests.post(TWILIO_URL, auth=..., data=...) |
                                                       |
                                       channel error: log + continue
                                       (NOTIF-01: no cross-channel bleed)

Dedup (NOTIF-02):
        orchestrator._check_and_buy()
                |
                | availability result
                v
        get_item_availability_state_sync(link) -> was_available
        if not was_available AND now available:
            -> write_queue.put(("notify", event))
            -> write_queue.put(("set_available", link))
        if not now available AND was_available:
            -> write_queue.put(("clear_available", link))

write_queue_drain (extended):
        "notify"        -> dispatcher.notify(event) [async, in loop]
        "set_available" -> set_item_available_sync(link, ts)
        "clear_available" -> clear_item_available_sync(link)
```

### Recommended Project Structure

```
core/
├── orchestrator.py          # existing — add dispatcher param + dedup logic
├── config_schema.py         # existing — add NotificationsConfig submodel
notifications/
├── __init__.py              # exports: Notifier, NotificationEvent, NotificationDispatcher
├── base.py                  # Notifier ABC: async send(event) -> None
├── dispatcher.py            # NotificationDispatcher: fan-out with per-channel isolation
├── sound_notifier.py        # wraps utils.play_*_sound()
├── discord_notifier.py      # requests.post to webhook with embed JSON
├── email_notifier.py        # smtplib STARTTLS or SMTP_SSL
└── sms_notifier.py          # requests.post to Twilio Messages.json
tests/
├── test_notifications.py    # all notifier unit tests + dispatcher fan-out + dedup
```

### Pattern 1: Notifier ABC

**What:** Abstract base class with a single async `send` method.
**When to use:** All channels implement this.

```python
# Source: CONTEXT.md decision + mirrors core/plugin_base.py RetailerPlugin ABC
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class NotificationEvent:
    item_name: str
    item_url: str
    platform: str          # e.g. "Amazon", "BestBuy"
    timestamp: datetime    # UTC; formatters convert to ISO-8601 as needed
    action: str            # "detected" | "purchased"

class Notifier(ABC):
    @abstractmethod
    async def send(self, event: NotificationEvent) -> None: ...
```

### Pattern 2: Dispatcher Fan-out with Per-Channel Isolation

**What:** Iterate registered notifiers; each wrapped in try/except; log channel name + error on failure.
**When to use:** All notification delivery.

```python
# Source: CONTEXT.md decision; mirrors run_plugin error isolation pattern
import asyncio

class NotificationDispatcher:
    def __init__(self, notifiers: list[Notifier]):
        self._notifiers = notifiers

    async def notify(self, event: NotificationEvent) -> None:
        loop = asyncio.get_running_loop()
        for notifier in self._notifiers:
            try:
                # Blocking channels override _send_blocking; sound calls sync directly
                await notifier.send(event)
            except Exception as exc:
                from logger import writeLog
                writeLog(
                    f"[{notifier.__class__.__name__}] notification failed: {exc}",
                    "ERROR",
                )
                # Scrub: do NOT log exc if it contains URLs or tokens
```

### Pattern 3: Discord Webhook Embed Payload

**What:** Exact JSON structure for a Discord embed POST.
**When to use:** `DiscordNotifier.send()`

```python
# Source: [CITED: docs.discord.com/developers/resources/webhook]
# Timestamp must be UTC ISO-8601: "YYYY-MM-DDTHH:MM:SS.mmmZ"
# Color is a decimal integer (RGB hex converted): 0x5865F2 = 5793266 (Discord blurple)
# Success: HTTP 204 No Content
# Rate limit: HTTP 429 with Retry-After header (seconds); log and do not retry in this phase

import requests
from datetime import timezone

def _build_discord_payload(event: NotificationEvent) -> dict:
    color = 0x57F287 if event.action == "detected" else 0xFEE75C  # green / yellow
    return {
        "embeds": [
            {
                "title": f"{event.item_name} — {event.action.capitalize()}",
                "url": event.item_url,
                "color": color,
                "timestamp": event.timestamp.astimezone(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z"
                ),
                "fields": [
                    {"name": "Platform", "value": event.platform, "inline": True},
                    {"name": "Action", "value": event.action, "inline": True},
                ],
            }
        ]
    }

def _send_discord_blocking(webhook_url: str, payload: dict) -> None:
    resp = requests.post(webhook_url, json=payload, timeout=10)
    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After", "unknown")
        raise RuntimeError(f"Discord rate-limited; retry after {retry_after}s")
    resp.raise_for_status()
    # 204 No Content is success — raise_for_status() passes through
```

### Pattern 4: Twilio SMS via Raw requests

**What:** HTTP Basic Auth POST to Messages.json endpoint.
**When to use:** `SmsNotifier.send()`

```python
# Source: [CITED: twilio.com/docs/sms/api/message-resource#create-a-message-resource]
# Endpoint: POST https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json
# Auth: HTTPBasicAuth(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
# Body: application/x-www-form-urlencoded {To, From, Body}
# Success: HTTP 201 Created, JSON body contains status="queued"
# Common errors: 21211 (invalid To), 21212 (invalid From), 20003 (auth failure)

import requests
from requests.auth import HTTPBasicAuth

def _send_sms_blocking(
    account_sid: str,
    auth_token: str,
    from_number: str,
    to_number: str,
    body: str,
) -> None:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    resp = requests.post(
        url,
        auth=HTTPBasicAuth(account_sid, auth_token),
        data={"To": to_number, "From": from_number, "Body": body},
        timeout=10,
    )
    resp.raise_for_status()
    # 201 = success; 4xx/5xx raises requests.HTTPError
```

### Pattern 5: SMTP Email via stdlib

**What:** STARTTLS on port 587 (or SMTP_SSL on port 465) using context manager.
**When to use:** `EmailNotifier.send()`

```python
# Source: [CITED: docs.python.org/3/library/smtplib.html]
# Use send_message() over sendmail(): auto-handles BCC stripping, RFC 5322 headers
# Catch specific exceptions at the channel boundary (CLAUDE.md: no bare except)

import smtplib
from email.message import EmailMessage

def _send_email_blocking(
    host: str,
    port: int,
    sender: str,
    recipients: list[str],
    password: str,
    subject: str,
    body: str,
    use_ssl: bool = False,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(sender, password)
            smtp.send_message(msg)
    # Exceptions to catch at dispatcher boundary:
    # smtplib.SMTPAuthenticationError — wrong credentials
    # smtplib.SMTPConnectError — host/port unreachable
    # smtplib.SMTPRecipientsRefused — all recipients rejected
    # smtplib.SMTPSenderRefused — sender address rejected
    # smtplib.SMTPDataError — server refused message data
    # smtplib.SMTPException — base catch for any other SMTP error
    # OSError / TimeoutError — network-level failures
```

### Pattern 6: Dedup Edge-Trigger Logic

**What:** Two new columns on `items`; write-queue-driven state machine.
**When to use:** In `_check_and_buy` before calling `dispatcher.notify()`.

```python
# Schema addition (ALTER TABLE or CREATE TABLE with new columns in initialize_db):
#   last_seen_available INTEGER NOT NULL DEFAULT 0  -- 0=unavailable, 1=available
#   last_notified TEXT                              -- ISO-8601 UTC or NULL

# Read function (sync, called via run_in_executor — same pattern as get_items_sync):
def get_item_notification_state_sync(link: str) -> tuple[bool, str | None]:
    """Returns (last_seen_available, last_notified) for dedup checks."""
    ...

# Write functions (sync, dispatched through write_queue):
def set_item_available_sync(link: str, notified_at: str) -> None:
    """Set last_seen_available=1, last_notified=notified_at."""
    ...

def clear_item_available_sync(link: str) -> None:
    """Set last_seen_available=0 (item went out of stock)."""
    ...

# Edge-trigger logic in _check_and_buy (pseudocode):
#   was_available, _ = get_item_notification_state_sync(link)  # via run_in_executor
#   if available and not was_available:
#       await dispatcher.notify(event)                         # FIRE — rising edge only
#       await write_queue.put(("set_available", link, now_iso))
#   elif not available and was_available:
#       await write_queue.put(("clear_available", link))       # reset for next restock
```

### Pattern 7: Config Schema Extension

**What:** `NotificationsConfig` submodel added to `AppConfig`.
**When to use:** At startup; Pydantic validates; SMS startup-gate validator fires here.

```python
# Source: mirrors existing config_schema.py patterns
from pydantic import BaseModel, model_validator
import os

class DiscordConfig(BaseModel):
    enabled: bool = False
    # DISCORD_WEBHOOK_URL comes from env — not in config

class EmailConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_ssl: bool = False           # True for port 465
    sender: str = ""
    recipients: list[str] = []

class SmsConfig(BaseModel):
    enabled: bool = False
    to_number: str = ""              # recipient; From comes from TWILIO_FROM env
    # TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM come from env only

    @model_validator(mode="after")
    def require_creds_if_enabled(self) -> "SmsConfig":
        if self.enabled:
            missing = [
                v for v in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM")
                if not os.environ.get(v)
            ]
            if missing:
                raise ValueError(
                    f"notifications.sms.enabled=true requires environment variables: "
                    f"{', '.join(missing)}"
                )
        return self

class NotificationsConfig(BaseModel):
    sound: bool = True               # sound is always-on unless explicitly disabled
    discord: DiscordConfig = DiscordConfig()
    email: EmailConfig = EmailConfig()
    sms: SmsConfig = SmsConfig()
```

### Anti-Patterns to Avoid

- **Logging secrets in error paths:** Never log `exc` directly if it may contain the webhook URL or auth token. Log `exc.__class__.__name__` + a scrubbed message. This applies to all three network channels.
- **Bare except in dispatcher:** Use `except Exception as exc` (per CLAUDE.md). A `BaseException` bare catch would swallow `KeyboardInterrupt`.
- **Calling `dispatcher.notify()` for every poll tick:** This is the NOTIF-02 trap. The dispatcher call must be gated on the rising edge only (transition 0->1 in `last_seen_available`).
- **Running SMTP inside the async loop:** SMTP connect + starttls + login + send are all blocking I/O. Must use `run_in_executor`. Same applies to all `requests.post` calls.
- **SMS silent no-op on missing creds:** The Pydantic validator must fire at startup (in `SmsConfig`), not lazily at send time.
- **Double-writing dedup state:** Do not call `set_item_available_sync` directly from the poll coroutine — route through the write queue to avoid concurrent write conflicts (same discipline as `update_item_purchased`).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SMTP TLS negotiation | Custom TLS socket wrapper | `smtplib.SMTP.starttls()` | stdlib handles EHLO, STARTTLS handshake, SSL upgrade |
| Discord rate limit back-off | Exponential retry loop | Log 429 + `Retry-After`, surface to caller | Retry loops stall the executor thread; Phase 5 scope is log-and-continue |
| Timestamp formatting | Manual strftime guesses | `datetime.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")` | Discord requires UTC ISO-8601 with Z suffix |
| Email MIME construction | Manual header concatenation | `email.message.EmailMessage.set_content()` | Handles charset, encoding, BCC stripping automatically |
| HTTP Basic Auth for Twilio | Manual base64 header | `requests.auth.HTTPBasicAuth(sid, token)` | requests handles encoding; avoids token exposure in string formatting |

**Key insight:** The stdlib covers SMTP completely and `requests` covers both Twilio and Discord. Any custom transport layer adds complexity with no benefit in this scope.

---

## Runtime State Inventory

> SKIPPED: this is a greenfield feature phase, not a rename/refactor/migration. No existing notification state to migrate.

---

## Common Pitfalls

### Pitfall 1: Secret Leakage Through Exception Logging
**What goes wrong:** `writeLog(f"Discord error: {exc}")` logs the full exception string, which for a `requests.HTTPError` includes the request URL — potentially embedding the webhook URL (a sensitive secret) in the log file.
**Why it happens:** Python's `requests.HTTPError.__str__()` includes the full URL.
**How to avoid:** Log `exc.__class__.__name__` + a static message. Do NOT include `str(exc)` or `repr(exc)` for any network notifier error path. Example:
```python
except requests.HTTPError as exc:
    writeLog(f"[DiscordNotifier] HTTP {exc.response.status_code} — delivery failed", "ERROR")
    # NOT: writeLog(f"Discord error: {exc}")  — leaks webhook URL
```
**Warning signs:** Log lines containing `https://discord.com/api/webhooks/` or Twilio account SIDs.

### Pitfall 2: SMS Charges Without Explicit Opt-In
**What goes wrong:** A user copies `sample.config.yml` with `sms.enabled: true` as an example value, doesn't have Twilio creds, but the bot starts silently. Twilio errors appear in logs but real numbers may already have been charged.
**Why it happens:** Validation happens at send time rather than startup.
**How to avoid:** The `SmsConfig.require_creds_if_enabled` validator fires at `AppConfig()` construction — before any plugin or dispatcher is initialized. The bot exits with an actionable Pydantic error message before the loop starts.
**Warning signs:** `SmsConfig.enabled=True` in config without corresponding env var check at startup.

### Pitfall 3: Dedup Firing on Every Poll Tick
**What goes wrong:** Every call to `_check_and_buy` when `available=True` calls `dispatcher.notify()`, producing one Discord/email/SMS per poll cycle.
**Why it happens:** Not reading per-item state before notifying — just notifying whenever available.
**How to avoid:** Read `last_seen_available` from DB before the notify call. Only dispatch if the flag transitions 0->1. The DB read uses `run_in_executor` like all other sync DB calls.
**Warning signs:** Multiple identical Discord embeds for the same item within minutes.

### Pitfall 4: Blocking SMTP in the Async Loop
**What goes wrong:** `smtplib.SMTP` connection + `starttls()` + `login()` can each block 5-30 seconds. Calling these directly in a coroutine stalls the entire event loop, freezing all plugin polls.
**Why it happens:** SMTP is synchronous I/O with no async variant in stdlib.
**How to avoid:** Wrap the entire `_send_email_blocking` call in `loop.run_in_executor(None, ...)`. Same pattern already established for `get_items_sync` and `update_item_purchased_sync`.
**Warning signs:** Other plugin polls stall during email delivery.

### Pitfall 5: Discord Embed Timestamp Rejected (400)
**What goes wrong:** Discord returns 400 Bad Request for embeds with incorrect timestamp format.
**Why it happens:** Using `datetime.isoformat()` without UTC conversion — produces offset-aware local times like `2026-06-03T10:00:00-04:00` instead of the required `Z` suffix.
**How to avoid:** Always convert to UTC before formatting: `dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")`. [CITED: birdie0.github.io/discord-webhooks-guide/structure/embed/timestamp.html]
**Warning signs:** Discord returns 400 with `Invalid Form Body` containing `timestamp`.

### Pitfall 6: Write-Queue Bypass for Dedup State
**What goes wrong:** Calling `set_item_available_sync` directly from a poll coroutine creates a concurrent-write path outside the serializing write queue, potentially causing `database is locked` errors under load.
**Why it happens:** The dedup writes look small/harmless compared to `update_item_purchased`.
**How to avoid:** Route ALL SQLite writes through the write queue — including `set_available` and `clear_available`. The write queue drain handles typed tuples: `("set_available", link, ts)`, `("clear_available", link)`, `("purchased", link)`.

---

## Code Examples

### Discord Webhook: Complete Minimal POST
```python
# Source: [CITED: docs.discord.com/developers/resources/webhook]
import os
import requests
from datetime import datetime, timezone

def post_discord_embed(event) -> None:
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
    ts = event.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    payload = {
        "embeds": [{
            "title": f"{event.item_name} — {event.action.capitalize()}",
            "url": event.item_url,
            "color": 0x57F287 if event.action == "detected" else 0xFEE75C,
            "timestamp": ts,
            "fields": [
                {"name": "Platform", "value": event.platform, "inline": True},
                {"name": "Action",   "value": event.action,   "inline": True},
            ],
        }]
    }
    resp = requests.post(webhook_url, json=payload, timeout=10)
    if resp.status_code == 429:
        retry = resp.headers.get("Retry-After", "?")
        raise RuntimeError(f"rate-limited; retry after {retry}s")
    resp.raise_for_status()  # 204 passes through; 4xx/5xx raises HTTPError
```

### Twilio SMS: Complete Minimal POST
```python
# Source: [CITED: twilio.com/docs/sms/api/message-resource#create-a-message-resource]
import os
import requests
from requests.auth import HTTPBasicAuth

def post_twilio_sms(to_number: str, body: str) -> None:
    sid   = os.environ["TWILIO_ACCOUNT_SID"]
    token = os.environ["TWILIO_AUTH_TOKEN"]
    from_ = os.environ["TWILIO_FROM"]
    url   = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    resp  = requests.post(
        url,
        auth=HTTPBasicAuth(sid, token),
        data={"To": to_number, "From": from_, "Body": body},
        timeout=10,
    )
    resp.raise_for_status()  # 201 = success; 4xx raises HTTPError
```

### SMTP Email: Complete Minimal Send
```python
# Source: [CITED: docs.python.org/3/library/smtplib.html]
import os
import smtplib
from email.message import EmailMessage

def send_email(host: str, port: int, sender: str, recipients: list[str], subject: str, body: str) -> None:
    password = os.environ["SMTP_PASSWORD"]
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = ", ".join(recipients)
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(sender, password)
        smtp.send_message(msg)
    # Caller catches: smtplib.SMTPAuthenticationError, smtplib.SMTPConnectError,
    # smtplib.SMTPRecipientsRefused, smtplib.SMTPException, OSError
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Direct `input()` blocking calls | `asyncio.Event` + write queue (Phase 4) | All new DB writes must go through write queue — dedup writes included |
| Global shared driver | Per-plugin `self.driver` | No shared mutable state to contend with for notification dispatch |
| Sequential item polling | `asyncio.TaskGroup` per plugin | Dispatcher must be safe to call from multiple concurrent coroutines — `asyncio.gather` fan-out in dispatcher is safe; no shared mutable state in dispatcher |

**Deprecated/outdated in this codebase:**
- Direct `play_available_sound()` call in `_check_and_buy`: Phase 5 replaces this with a dispatcher call; the sound notifier wraps the pygame calls internally.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Discord `raise_for_status()` passes on 204 No Content (no body to parse) | Code Examples | Low — 204 is a non-error 2xx; requests treats it as success; verified by community sources |
| A2 | Twilio trial accounts require the destination number to be verified (error 21608) | Common Pitfalls (SMS) | Low — this is a trial-account restriction, not a production one; affects only test environments |
| A3 | SMTP sender and login username are the same field | Code Examples | Medium — some SMTP relays (SendGrid, SES) use API key as password but different sender address; `smtp_username` may need to be a separate config field |

---

## Open Questions (RESOLVED)

> RESOLVED: (1) SMTP sender vs login username — add a distinct smtp_username field defaulting to sender (Plan 05-01 T1). (2) Dispatcher call for purchases in _check_and_buy — direct `await dispatcher.notify(event)` from the async poll coroutine, NOT routed through the sync write queue (Plan 05-05 T2). (3) Sound notifier + pygame thread-safety — keep sound on the main thread / guard repeat init (Plan 05-02 T1).

1. **SMTP sender vs login username**
   - What we know: Most consumer SMTP (Gmail, Outlook) uses the sender email as login. Transactional relays (SendGrid, SES) use a separate API key or SMTP username.
   - What's unclear: Whether the project targets consumer SMTP only or relay services.
   - Recommendation: Add an optional `smtp_username` field to `EmailConfig` defaulting to `sender`. This adds one config field but covers both cases cleanly.

2. **Dispatcher call in `_check_and_buy` for purchases**
   - What we know: Current `_check_and_buy` fires `play_buy_sound()` after `success=True`. Phase 5 replaces this with `dispatcher.notify(purchased_event)`.
   - What's unclear: Whether the dedup state should be reset to `last_seen_available=0` after purchase (item is "bought" so it won't be re-bought; `purchased=1` in the items table already handles this) or left as `1`.
   - Recommendation: Leave `last_seen_available=1` after purchase; the `purchased=1` flag already gates the item from re-entering the poll loop. No dedup state reset needed.

3. **Sound notifier inside `run_in_executor`**
   - What we know: `play_available_sound()` calls `pygame.mixer.music.play()`, which is non-blocking on the pygame side (it starts playback and returns immediately). However, `pygame.mixer.init()` is called on each `play_sound()` invocation.
   - What's unclear: Whether the pygame calls are thread-safe when called from `run_in_executor`.
   - Recommendation: Keep sound calls on the main thread (same as current behavior); have `SoundNotifier.send()` call the pygame functions directly without `run_in_executor`. Only network I/O goes into the executor.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `requests` | Discord + Twilio notifiers | Yes | 2.33.1 (pinned) | — |
| `smtplib` | Email notifier | Yes | stdlib | — |
| `email.message` | Email notifier | Yes | stdlib | — |
| `sqlite3` | Dedup state | Yes | stdlib | — |
| `pytest` | Test suite | Yes | 8.3.4 (pinned) | — |
| `pytest-asyncio` | Async test cases | Yes | 1.3.0 (pinned) | — |
| SMTP server | Email delivery (runtime) | Unknown | — | Config-gated: only active if `email.enabled=true` |
| Twilio account | SMS delivery (runtime) | Unknown | — | Disabled by default; startup validator gates accidental activation |
| Discord webhook URL | Discord delivery (runtime) | Unknown | — | Config-gated: only active if `discord.enabled=true` |

**Missing dependencies with no fallback:** None — all code-path dependencies are stdlib or already pinned.

**Missing dependencies with fallback:** SMTP server, Twilio account, Discord webhook URL are runtime concerns, not code-time concerns. Their absence is handled by the `enabled` flags in config.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` (asyncio_mode=auto, inferred from existing test patterns) |
| Quick run command | `pytest tests/test_notifications.py -x -q` |
| Full suite command | `pytest -q` (72 existing + new notification tests) |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NOTIF-01 | Fan-out: failing notifier does not block others | unit | `pytest tests/test_notifications.py::test_failing_notifier_does_not_block -x` | Wave 0 |
| NOTIF-01 | All enabled notifiers called on a single event | unit | `pytest tests/test_notifications.py::test_all_notifiers_called -x` | Wave 0 |
| NOTIF-02 | Rising edge fires exactly one notification | unit | `pytest tests/test_notifications.py::test_dedup_single_notify_per_restock -x` | Wave 0 |
| NOTIF-02 | Suppress re-notify while still available | unit | `pytest tests/test_notifications.py::test_dedup_suppresses_while_available -x` | Wave 0 |
| NOTIF-02 | Re-notify after unavailable -> available cycle | unit | `pytest tests/test_notifications.py::test_dedup_renotify_after_restock -x` | Wave 0 |
| NOTIF-03 | SoundNotifier calls correct pygame function per action | unit | `pytest tests/test_notifications.py::test_sound_notifier_detected -x` | Wave 0 |
| NOTIF-04 | Discord payload contains all required embed fields | unit | `pytest tests/test_notifications.py::test_discord_payload_shape -x` | Wave 0 |
| NOTIF-04 | Discord timestamp is UTC ISO-8601 with Z suffix | unit | `pytest tests/test_notifications.py::test_discord_timestamp_format -x` | Wave 0 |
| NOTIF-04 | Discord 429 raises RuntimeError with Retry-After | unit | `pytest tests/test_notifications.py::test_discord_rate_limit -x` | Wave 0 |
| NOTIF-05 | Email sends via STARTTLS with correct headers | unit | `pytest tests/test_notifications.py::test_email_starttls -x` | Wave 0 |
| NOTIF-05 | SMTPAuthenticationError caught at channel boundary | unit | `pytest tests/test_notifications.py::test_email_auth_error_isolated -x` | Wave 0 |
| NOTIF-06 | SMS enabled without creds raises config error at startup | unit | `pytest tests/test_notifications.py::test_sms_misconfigured_raises -x` | Wave 0 |
| NOTIF-06 | SMS POST uses correct URL + Basic Auth + form params | unit | `pytest tests/test_notifications.py::test_sms_payload -x` | Wave 0 |
| NOTIF-06 | SMS disabled by default (no creds = no error) | unit | `pytest tests/test_notifications.py::test_sms_disabled_by_default -x` | Wave 0 |

### Mockable vs Live Network

| Test | Mockable | Method |
|------|---------|--------|
| Discord payload shape | Yes | `unittest.mock.patch("requests.post")` — assert call_args |
| Discord 429 handling | Yes | Mock `requests.post` returning `MagicMock(status_code=429, headers={"Retry-After":"5"})` |
| Twilio payload + auth | Yes | `unittest.mock.patch("requests.post")` — assert call_args including auth |
| SMTP STARTTLS send | Yes | `unittest.mock.patch("smtplib.SMTP")` as context manager mock |
| Fan-out isolation | Yes | One notifier raises; assert others called via `AsyncMock.assert_awaited` |
| Dedup logic | Yes | Patch `get_item_notification_state_sync`; drive state transitions |
| SMS misconfig error | Yes | Set env + config, instantiate `SmsConfig` / `AppConfig`, assert `ValidationError` |
| Live Discord delivery | No — manual | POST with real webhook URL; confirm message appears in channel |
| Live Twilio SMS | No — manual | Real account SID + verified To number; confirm SMS received |
| Live SMTP send | No — manual | Real SMTP relay; confirm email received |

### Sampling Rate
- **Per task commit:** `pytest tests/test_notifications.py -x -q`
- **Per wave merge:** `pytest -q` (full suite, including 72 existing tests)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_notifications.py` — all 14 tests listed above
- [ ] `notifications/__init__.py` — package stub (needed for imports to resolve)
- [ ] `notifications/base.py` — `Notifier` ABC + `NotificationEvent` dataclass (needed by all notifier test files)

*(No new fixtures needed in conftest.py — existing `tmp_data_dir` covers dedup DB tests.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Notifications are outbound only; no inbound auth surface |
| V3 Session Management | No | No session state in notification dispatch |
| V4 Access Control | No | Internal module; no external access control surface |
| V5 Input Validation | Yes | Event fields (item_name, item_url) are internally generated — not user input — but URL must not contain newlines before embedding in SMTP body |
| V6 Cryptography | No | TLS is handled by smtplib.SMTP.starttls() and requests (stdlib SSL); no custom crypto |
| V7 Error Handling | Yes | Error paths must not log secrets (webhook URL, SMTP password, Twilio tokens) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Webhook URL leakage via exception logging | Information Disclosure | Never log `str(exc)` for `requests.HTTPError`; log only status code + static message |
| SMTP password in logs | Information Disclosure | `SMTP_PASSWORD` sourced from env only; never passed as string in log messages |
| Twilio SID/token in log output | Information Disclosure | Same as webhook: log HTTP status code, not exception string which includes URL |
| SSRF via misconfigured webhook URL | SSRF | Low risk — URL comes from env var set by the operator, not from user input. No user-supplied URLs are POSTed to. |
| Twilio account SID exposure in URL | Information Disclosure | The Twilio endpoint URL contains the Account SID. Do not log the full URL — log only a scrubbed version like `twilio/Messages.json` |
| SMS charges from misconfigured `to_number` | Elevation of Privilege | Startup validator gates `sms.enabled=true` + creds check; test_mode flag should also suppress SMS sends in test mode |

**Security enforcement notes:**
- The dispatcher's `except Exception` block must log `exc.__class__.__name__` only for network notifiers — never `str(exc)`.
- `DISCORD_WEBHOOK_URL` grants write access to a Discord channel; treat it as a secret (env-only). Rotate it if leaked.
- `SMTP_PASSWORD` must never appear in log output even in debug mode.
- The Twilio Account SID appears in the endpoint URL; do not log `resp.request.url`.

---

## Sources

### Primary (HIGH confidence)
- [CITED: docs.discord.com/developers/resources/webhook] — embed payload shape, field list, 204 success response
- [CITED: docs.discord.com/developers/topics/rate-limits] — 429 response, Retry-After header, X-RateLimit-* headers
- [CITED: birdie0.github.io/discord-webhooks-guide/structure/embed/timestamp.html] — UTC ISO-8601 timestamp format, Z suffix requirement
- [CITED: twilio.com/docs/sms/api/message-resource#create-a-message-resource] — Messages.json endpoint, Basic Auth, form params, 201 success
- [CITED: twilio.com/docs/api/errors] — error codes 21211, 21212, 20003, 21608
- [CITED: docs.python.org/3/library/smtplib.html] — SMTP exception hierarchy, STARTTLS pattern, SMTP_SSL pattern, send_message vs sendmail

### Secondary (MEDIUM confidence)
- WebSearch (multiple sources): Discord 429 behavior with Retry-After confirmed by community docs + GitHub discord-api-docs issues
- WebSearch: Twilio 201 Created + `status="queued"` confirmed by Twilio usage docs

### Tertiary (LOW confidence)
- None — all critical claims have HIGH confidence citations.

---

## Metadata

**Confidence breakdown:**
- Discord API payload: HIGH — verified against official docs.discord.com
- Twilio REST endpoint: HIGH — verified against official twilio.com docs
- SMTP stdlib patterns: HIGH — verified against official docs.python.org
- Dedup schema design: HIGH — derived from existing Phase-4 patterns in codebase (no external dependency)
- Config schema extension: HIGH — mirrors existing config_schema.py conventions directly

**Research date:** 2026-06-03
**Valid until:** 2026-09-03 (Discord/Twilio APIs are stable; smtplib stdlib is version-stable; re-verify if Twilio announces API deprecations)
