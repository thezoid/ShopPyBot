# Phase 5: Notification System - Context

**Gathered:** 2026-05-12
**Status:** Ready for research and planning
**Source:** /gsd-discuss-phase 5 (interactive)

<domain>
## Phase Boundary

Phase 5 adds a fan-out notification dispatcher that delivers stock-detection alerts across configured channels (sound, Discord webhook, Email/SMTP, SMS/Twilio). One channel failure does not block other channels. Each item triggers at most one notification per restock event (deduplication). The dispatcher runs as an `asyncio.Queue` consumer task next to the Phase 4 `purchase_writer`, fed by plugin polling tasks.

Six in-scope requirements: NOTIF-01 through NOTIF-06.

Out of scope (defer):
- New platform plugins (Walmart, Target, GameStop, Square Enix, NewEgg) — Phase 6
- Web UI / dashboard for notification history — not on roadmap (v2 idea)
- Per-platform notification routing (e.g., only Discord for Amazon) — v2 if needed
- Notification analytics / counters / per-channel success rates — not on roadmap
- Slack / Telegram / Pushover / generic webhook channels — not on roadmap (contributor backlog)

</domain>

<decisions>
## Implementation Decisions

### Notifier interface (NOTIF-01)

**D-01: `Notifier` ABC subclass pattern, mirroring `RetailerPlugin`.**
- New `notifier_base.py` defines `class Notifier(ABC)` with:
  - `name: str = ""` (class attribute; defaults to filename stem; same convention as plugins)
  - `enabled: bool = False` (default-off so a contributor's broken notifier doesn't auto-activate)
  - `async def send(self, event: NotificationEvent) -> None` (abstract)
  - Optional `async def shutdown(self) -> None` non-abstract default (mirrors Phase 4 D-04 plugin shutdown)
- `NotificationEvent` is a dataclass with fields: `item_name: str`, `url: str`, `platform: str`, `timestamp: datetime`, `action: Literal["detected", "purchased"]`.
- Notifiers live in `notifiers/` as `shopbot_notifier_*.py` (parallel to `plugins/shopbot_plugin_*.py` convention). Same `importlib`-based discovery as Phase 2 plugins.
- Phase 5 ships four built-in notifiers: `shopbot_notifier_sound.py`, `shopbot_notifier_discord.py`, `shopbot_notifier_email.py`, `shopbot_notifier_sms.py`.
- Rationale: consistency with RetailerPlugin lowers contributor cognitive load. They already learned the ABC + discovery pattern; one mental model covers both extension points.

### Dedup state (NOTIF-02)

**D-02: Add `last_notified_at TIMESTAMP NULL` column to the existing `items` table.**
- Migration runs inside `initialize_db()` via idempotent `ALTER TABLE items ADD COLUMN ... IF NOT EXISTS` (SQLite supports `ADD COLUMN` natively; the orchestrator checks `PRAGMA table_info` first and skips ALTER if already present).
- Dedup rule (encoded as a helper, likely in `models.py` or `notification.py`): an item is eligible for notification if `last_notified_at IS NULL OR (now - last_notified_at) > restock_window`. After successful notification, set `last_notified_at = CURRENT_TIMESTAMP`.
- `restock_window` is configurable: `notifications.restock_window_seconds: int = 600` (10 minutes default). Tunes how long after the last alert a re-stock counts as a new event.
- Why a column not a separate `dedup_cache` table: single source of truth, no JOIN required during polling, easy to inspect with `sqlite3 data/shop_py_bot.db .schema`. Cost: a column nullable on existing rows, harmless backfill.
- Rationale rejected (in-memory dict): would re-notify on every restart, bad UX after crashes.

### Dispatch concurrency (NOTIF-01 isolation)

**D-03: `asyncio.Queue` + a single `notification_writer` consumer task. Mirrors Phase 4 `purchase_writer`.**
- Module-level `notification_queue: asyncio.Queue[NotificationEvent] = asyncio.Queue(maxsize=200)`.
- Plugin's `check_availability` returns True → orchestrator calls `await notification_queue.put(NotificationEvent(...))`. Plugin polling task continues immediately; webhook latency does not block next poll.
- `async def notification_writer(queue, notifiers):` drains the queue. For each event: `await asyncio.gather(*(n.send(event) for n in notifiers if n.enabled), return_exceptions=True)`. Per-notifier exceptions are collected, logged via writeLog, and do NOT crash the writer (this is the NOTIF-01 fan-out isolation requirement).
- `notification_writer` itself is fatal if it crashes — propagated via TaskGroup the same way `purchase_writer` is fatal (Phase 4 RESEARCH pitfall 10).
- The dedup check happens INSIDE the writer (not in the plugin task), so the queue holds raw events and the writer is the single decision point for "should this fire."
- Rationale: separates polling latency from webhook latency; one place to add retry policy; consistent with Phase 4 queue pattern users already understand.

### SMS opt-in (NOTIF-06)

**D-04: SMS requires BOTH `notifications.sms.enabled: true` in config AND `SHOPBOT_ENABLE_SMS=true` env var.**
- Two-lock model: missing either lock disables SMS. Config alone or env alone is insufficient.
- If `enabled: true` in config but env var is missing or not "true": `shopbot_notifier_sms.py` registers a one-time WARNING via writeLog at startup ("SMS configured but SHOPBOT_ENABLE_SMS env var not set; SMS disabled") and the notifier instance sets `self.enabled = False` so the dispatcher skips it.
- Twilio credentials (account SID, auth token, from-number) live in env vars only (SEC-01 precedent): `SHOPBOT_TWILIO_ACCOUNT_SID`, `SHOPBOT_TWILIO_AUTH_TOKEN`, `SHOPBOT_TWILIO_FROM`. Recipient number in config (`notifications.sms.to: "+1234567890"`).
- Rationale: prevents three accidental-charge scenarios:
  1. Someone copies sample.config.yml with `enabled: true` baked in → env lock blocks
  2. Someone exports SHOPBOT_ENABLE_SMS=true in a shared shell → config lock blocks
  3. Someone tests with real Twilio creds in env → config still needs explicit opt-in
- Sample config: `notifications.sms.enabled: false` with comment "Set to true AND export SHOPBOT_ENABLE_SMS=true to enable. See SECURITY.md for billing-risk warning."

### Claude's Discretion

The planner / researcher decides:

- **`notifications` config schema shape** — likely a nested Pydantic model `NotificationsConfig` with sub-models per channel (`sound`, `discord`, `email`, `sms`). Each sub-model has `enabled: bool` and channel-specific fields. Planner picks the field names.
- **Discord webhook retry / rate-limit handling** — Discord returns 429 with `Retry-After` header. Planner picks: exponential backoff with max 3 retries, or single retry with header-honored sleep, or no retry. Recommended: honor `Retry-After` once, then give up (a missed alert is OK; blocking the writer is not).
- **Email/SMTP details** — TLS vs STARTTLS, port defaults (465 vs 587), connection pooling vs per-send. Stdlib `smtplib` is fine; no need for aiosmtplib unless perf becomes an issue.
- **`sound` notifier integration** — NOTIF-03 says it wraps existing `play_available_sound`/`play_buy_sound`/`play_notification_sound` from `utils.py`. Sound calls are sync — they get wrapped in `asyncio.to_thread` inside `send()`. Selecting which sound for which event (available vs purchased) is implementation detail.
- **`notifiers/` discovery** — reuse `plugin_registry.discover` pattern OR add a parallel `notifier_registry.discover`. Recommend the latter for separation of concerns; or generalize the existing helper to a `discover_modules(dir, abc_class, prefix)` shape if it's clean.
- **Where dedup check goes** — inside `notification_writer` (read item.last_notified_at, decide, write back). Need a small `models.should_notify(url, restock_window)` helper + `models.mark_notified(url)`. Both go through `_connect()` per Phase 4 D-02.
- **NotificationEvent vs raw tuple on queue** — dataclass for type safety. Discord embed builder reads dataclass fields directly.
- **Test mode behavior** — when `app.debug.test_mode = True`, notifications still fire but Twilio uses Twilio's test credentials path (their test number) and Discord skips actual webhook POST (logs the would-be payload). Planner decides; recommend disabling Twilio entirely in test_mode, keeping Discord + Email as-is (logs catch them).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1-4 outputs (locked contracts)
- `plugin_base.py` — `RetailerPlugin` ABC. Phase 5 mirrors the pattern in a new `Notifier` ABC.
- `plugin_registry.py` — `discover()`, `discover_async()`. Phase 5 either reuses these (parameterized over ABC + prefix) or adds a parallel `notifier_registry.py`.
- `config_schema.py` — `AppConfig` Pydantic shape. Phase 5 adds a `notifications` nested model.
- `models.py` — `_connect()` context manager, items table schema, `update_item_purchased`. Phase 5 adds `last_notified_at` column + `should_notify` / `mark_notified` helpers.
- `main.py` — Phase 4 async orchestrator. Phase 5 adds a `notification_writer` task alongside `purchase_writer` in the TaskGroup and wires the `notification_queue` into the polling tasks.
- `utils.py` — sync `play_available_sound`, `play_buy_sound`, `play_notification_sound`. Sound notifier wraps these via `asyncio.to_thread`.
- `logger.py` — `writeLog`, `configure`. Used unchanged.
- `plugins/shopbot_plugin_amazon.py` + `shopbot_plugin_bestbuy.py` — existing plugins. Phase 5 does NOT modify them; the notification trigger lives in the orchestrator (when `plugin.check_availability` returns True, the orchestrator puts an event on the queue).

### Project decisions
- `.planning/PROJECT.md` — Discord webhook first, then Email/SMTP, SMS opt-in only
- `.planning/REQUIREMENTS.md` — NOTIF-01..06 wording (authoritative)
- `.planning/phases/04-async-orchestrator/04-CONTEXT.md` — Phase 4 queue + writer pattern (purchase_writer) that this phase mirrors

### New dependency candidates
- `requests` or `httpx` for Discord/SMTP HTTP calls — `requests` is already pinned in requirements.txt; reuse it via `asyncio.to_thread` (no new dependency).
- `twilio` Python SDK for SMS — new dependency, pin a known-good version. Planner picks.
- Stdlib `smtplib`, `email.mime.text`, `email.mime.multipart` for email — already available; no new dep.

</canonical_refs>

<specifics>
## Specific Implementation Notes

### Target NotificationEvent dataclass

```
@dataclass(frozen=True)
class NotificationEvent:
    item_name: str
    url: str
    platform: str
    timestamp: datetime
    action: Literal["detected", "purchased"]
```

### Target Notifier ABC shape

```
class Notifier(ABC):
    name: str = ""
    enabled: bool = False

    @abstractmethod
    async def send(self, event: NotificationEvent) -> None: ...

    async def shutdown(self) -> None:
        return None
```

### Dispatch flow (target)

```
# inside poll_plugin (main.py, Phase 4 extension)
if available:
    await notification_queue.put(NotificationEvent(item.name, item.link, plugin.name, datetime.now(), "detected"))

# inside notification_writer
while True:
    event = await queue.get()
    try:
        if not should_notify(event.url, restock_window):
            continue
        results = await asyncio.gather(
            *(n.send(event) for n in notifiers if n.enabled),
            return_exceptions=True,
        )
        for n, r in zip(notifiers, results):
            if isinstance(r, Exception):
                writeLog(f"Notifier {n.name} failed: {r}", "ERROR")
        mark_notified(event.url)
    finally:
        queue.task_done()
```

### Pitfalls to encode as must_haves

1. `notification_writer` exceptions during `mark_notified` MUST NOT crash the writer (catch + log + continue; the writer dying is fatal per Phase 4 pitfall 10, but a single SQL hiccup should not kill it).
2. SMS notifier MUST verify both locks (config.enabled AND SHOPBOT_ENABLE_SMS=true) at INSTANTIATION, not at send time. Failing at send time means burned cycles on every event.
3. Discord webhook URL is a SECRET — read from env var `SHOPBOT_DISCORD_WEBHOOK_URL`, not config.yml. Add to SEC-01 secret list (effectively).
4. SMTP password from env var `SHOPBOT_SMTP_PASSWORD` only (never config.yml). Sample config documents this.
5. Sound notifier MUST wrap `play_*_sound` in `asyncio.to_thread` (these are blocking pygame calls).
6. `should_notify(url, restock_window)` and `mark_notified(url)` use `_connect()` context manager from Phase 4 — no raw sqlite3.connect.
7. The `ALTER TABLE items ADD COLUMN last_notified_at` migration in `initialize_db` MUST be idempotent (check `PRAGMA table_info(items)` first); existing v1 deployments would otherwise fail on upgrade.
8. `notification_writer` catches `asyncio.CancelledError` to call `queue.task_done()` on shutdown so `queue.join()` (if used) doesn't hang.
9. NotificationEvent timestamp is `datetime.now(timezone.utc)` not `datetime.now()` (tz-naive datetimes confuse downstream consumers and SQLite).
10. Two-lock SMS check at startup must log clearly distinguishing "config says off" from "env var missing" from "both off" so user can debug.

</specifics>

<deferred>
## Deferred Ideas

- Slack / Telegram / Pushover / generic webhook channels — contributor backlog
- Per-platform notification routing (Discord for Amazon, Email for BestBuy) — v2
- Notification rate limiting (max N per hour) — v2 if needed
- Web UI / dashboard for notification history — not on roadmap
- Per-channel success-rate analytics — not on roadmap
- Retries with persistent queue (survives restart) — overkill for v1
- Multi-recipient SMS (group blast) — v2
- Custom Discord embed templates per platform — v2

</deferred>

*Phase: 05-notification-system*
*Context gathered: 2026-05-12 via /gsd-discuss-phase 5*
