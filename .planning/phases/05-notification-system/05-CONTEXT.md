# Phase 5: Notification System - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

A fan-out notification dispatcher that delivers stock alerts across all configured channels (sound, Discord webhook, Email/SMTP, SMS/Twilio), isolates per-channel failures, and dedupes to one notification per restock event. Covers NOTIF-01..NOTIF-06.

NOT in scope: new platforms (Phase 6), per-platform delay config (Phase 6), a notification UI/dashboard, or rich templating beyond the standardized embed.
</domain>

<decisions>
## Implementation Decisions

### Dispatcher & Notifier Architecture (NOTIF-01, NOTIF-03)
- Define a `Notifier` ABC with an async `send(event)` method; channels are registered in a dispatcher based on config (mirrors the RetailerPlugin registry pattern).
- Fan-out isolation: the dispatcher invokes each notifier inside its own try/except; a single channel raising is logged (with the channel name + error) and does NOT block or prevent the other channels from firing (NOTIF-01 / success criterion 1).
- Blocking network sends (Discord POST, SMTP, Twilio HTTP) run via `run_in_executor` so they never stall the async event loop (consistent with Phase 4).
- Trigger point: the orchestrator calls `dispatcher.notify(event)` on stock-detected and on purchased; plugins do not notify themselves. The event carries item name, URL, platform, timestamp, and action taken (detected / purchased).
- Sound notifier (NOTIF-03) wraps the existing `play_available_sound()` / `play_buy_sound()` / `play_notification_sound()` from utils.py.

### Dependencies (NOTIF-04/05/06) — ZERO new packages
- Discord (NOTIF-04): `requests` POST of an embed JSON to the webhook URL.
- Email (NOTIF-05): stdlib `smtplib` + `email`.
- SMS/Twilio (NOTIF-06): raw HTTP to the Twilio REST API via `requests` (already a dependency). Do NOT add the `twilio` package — it is opt-in/off by default and a raw POST avoids a heavy dependency.

### Dedup, Config & Credentials (NOTIF-02, NOTIF-06)
- "Restock event" is edge-triggered: notify when an item transitions unavailable -> available; suppress further notifications while it remains available. Track per-item availability state + `last_notified` in SQLite (NOTIF-02) so multiple in/out flaps within a poll cycle produce exactly one notification per restock event, not one per poll tick. Reuse the Phase-4 WAL/write-queue path for these DB writes (no concurrent-write regressions).
- Non-secret settings live in a new `notifications` section of config.yml (per-channel enable flags, email sender/recipients, etc.).
- Secrets are sourced from environment variables only, never config.yml or logs (consistent with Phase 1): Discord webhook URL (sensitive — anyone with it can post), SMTP password, Twilio auth token/SID.
- SMS is DISABLED by default. Enabling requires an explicit `notifications.sms.enabled: true` AND the Twilio env credentials; if enabled without credentials, fail with a clear config error (not a silent no-op) (NOTIF-06 / success criterion 4).

### Claude's Discretion
- Module layout (e.g. a `notifications/` package with one file per notifier, or a `core/notifications.py`), the exact event dataclass shape, the SQLite schema change (new column vs new table for last_notified/state), and embed/email formatting details, provided the locked decisions hold.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `utils.py`: `play_available_sound()`, `play_buy_sound()`, `play_notification_sound()` (pygame) — the sound notifier wraps these.
- `core/orchestrator.py` (Phase 4): the async loop + single write-queue + run_in_executor pattern — the dispatcher is invoked here and reuses run_in_executor for blocking sends; DB writes for last_notified go through the existing write queue.
- `models.py` (Phase 4): WAL `get_db_connection()` context manager + `*_sync` functions — extend with a last_notified / availability-state read+write (`*_sync`, driven via the write queue).
- `core/config_schema.py`: typed AppConfig — add a `notifications` submodel (enable flags + non-secret settings); secrets stay in env.
- `requests` is already a pinned dependency (used for make_tiny) — reused for Discord + Twilio.

### Established Patterns
- Secrets only via env, never logged or in config (Phase 1) — applies to webhook URL, SMTP password, Twilio token.
- Async + run_in_executor for blocking I/O (Phase 4) — applies to all network notifiers.
- Config-driven registration + per-item isolation (Phase 2 registry, Phase 4 per-plugin error isolation) — the dispatcher mirrors this for channels.

### Integration Points
- Dispatcher constructed at startup (reads config + env), invoked by the orchestrator's per-plugin coroutine on availability/purchase transitions.
- last_notified/state persisted in SQLite via the Phase-4 write queue.
</code_context>

<specifics>
## Specific Ideas

- Success criterion 1 demands a misconfigured Discord (bad webhook) NOT crash the bot and not block email/sound — the per-channel try/except must be demonstrable (a unit test with a failing notifier among working ones).
- Success criterion 4 demands SMS accidental-activation produces a clear config error, not a silent no-op — testable with sms.enabled true + missing creds.
- Discord embed must include: item name, URL, platform, timestamp, action taken (detected/purchased).
</specifics>

<deferred>
## Deferred Ideas

- New platforms + per-platform delay/jitter/headless config (Phase 6).
- Rich notification templating / per-channel message customization beyond the standardized embed.
- A notification history UI or digest/batching.
</deferred>

---

*Phase: 5-notification-system*
*Context gathered: 2026-06-03*
