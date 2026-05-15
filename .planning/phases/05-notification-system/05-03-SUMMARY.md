---
phase: 05-notification-system
plan: 03
subsystem: discord-notifier
tags:
  - python
  - notifications
  - discord
  - webhook
  - requests
  - wave-1
dependency_graph:
  requires:
    - notifier_base.Notifier + NotificationEvent (Plan 05-01)
    - config_schema.DiscordNotifierConfig (Plan 05-01)
    - notifier_registry._instantiate kwargs contract (Plan 05-02)
    - requests==2.33.1 (already pinned, Phase 1)
  provides:
    - notifiers.shopbot_notifier_discord.DiscordNotifier (NOTIF-04)
    - Embed payload builder (_build_payload) honoring Discord embed schema
    - 429-aware single-retry POST (_post_with_one_retry, _retry_after_seconds)
  affects:
    - Wave 2 (Plan 05-06 notification_writer) picks up DiscordNotifier via discover_notifiers
tech_stack:
  added: []
  patterns:
    - asyncio.to_thread wrapping sync requests.post
    - Env-only secret surface (SHOPBOT_DISCORD_WEBHOOK_URL captured once at __init__)
    - 429 Retry-After header parse with body fallback, capped at 30s, one retry
    - AST grep test enforcing webhook URL never reaches writeLog argument
key_files:
  created:
    - notifiers/shopbot_notifier_discord.py
  modified:
    - tests/test_notifiers_discord.py (RED skeleton -> GREEN suite)
decisions:
  - "Webhook URL stored as public attribute `self.webhook_url` (not name-mangled) to match RED skeleton expectation from Plan 05-01"
  - "Env var read in __init__ via inline literal `os.environ.get(\"SHOPBOT_DISCORD_WEBHOOK_URL\", ...)` to satisfy plan verify grep pattern exactly once"
  - "429 retry: Retry-After header parsed first, body retry_after second, default 1.0s third; min(wait, 30.0) cap bounds writer block"
  - "Second 429 swallowed (WARNING log + return) instead of raised: missed alert is acceptable per CONTEXT pitfall #11; blocking the writer is not"
  - "raise_for_status() on non-429 4xx/5xx propagates to notification_writer's gather(return_exceptions=True) for per-notifier isolation (NOTIF-01)"
  - "Embed color constants: 0x2ECC71 (green) for action=='detected', 0x3498DB (blue) for action=='purchased' per RESEARCH Q1"
  - "Timestamp formatted via event.timestamp.astimezone(timezone.utc).isoformat() (Discord wants ISO 8601 with offset)"
metrics:
  duration_minutes: 4
  completed: 2026-05-15
  tasks_completed: 1
  files_changed: 2
---

# Phase 5 Plan 03: Discord Notifier Summary

DiscordNotifier (NOTIF-04) ships as a Notifier subclass that POSTs a Discord embed to a webhook URL read once from `SHOPBOT_DISCORD_WEBHOOK_URL` env at instantiation, with a 429-aware single-retry policy (Retry-After header honored, capped at 30s, second 429 logs WARNING and returns cleanly).

## One-liner

Discord webhook notifier with env-only secret surface, embed builder, and bounded 429 single-retry policy that never wedges the notification writer.

## What Was Built

### `notifiers/shopbot_notifier_discord.py` (98 lines)

- `DiscordNotifier(Notifier)` with class attribute `name = "discord"`
- `__init__(*, sub_config, app_config)` matching notifier_registry._instantiate contract
- Two-state enable logic:
  - sub_config.enabled is False -> quiet opt-out (self.enabled=False, no log)
  - sub_config.enabled is True + env missing -> self.enabled=False + WARNING naming the env var
  - sub_config.enabled is True + env present -> self.enabled=True
- `self.webhook_url` captured once at __init__; runtime env changes ignored
- `async send(event)` wraps `_post_with_one_retry` via `asyncio.to_thread`
- `_post_with_one_retry(payload)`:
  - First POST with 10s timeout
  - On 429: read `_retry_after_seconds`, sleep min(wait, 30.0), retry once
  - On second 429: log WARNING ("giving up", with event url only), return without raising
  - On non-429 4xx/5xx: raise_for_status propagates to writer gather
- `_build_payload(event)`: returns {"embeds": [{title, description, url, color, timestamp, fields}]} with action-based color (0x2ECC71 detected / 0x3498DB purchased)
- `_retry_after_seconds(response)`: header first (float parse), body `retry_after` field second, 1.0 default; ValueError-safe

### `tests/test_notifiers_discord.py` (GREEN, 12 tests)

- `test_discordNotifierImportable`: import + Notifier subclass check
- `test_urlReadAtInit`: setenv -> init -> setenv changed -> webhook_url unchanged
- `test_embedShape`: detected event posts payload with all required keys + color 0x2ECC71 + parseable ISO timestamp
- `test_purchasedColor`: purchased event -> color 0x3498DB
- `test_429RetryOnce`: 429 then 204 -> 2 POSTs, sleep=[0.01], no raise
- `test_429RetryAfterCapAt30`: 429 with Retry-After=9999 -> sleep=[30.0]
- `test_429GiveUpAfterOne`: 429 twice -> 2 POSTs, no raise, WARNING with "giving up" logged
- `test_500PropagatesAsException`: 500 -> requests.HTTPError raised
- `test_disabledIfEnvMissing`: delenv + enabled config -> self.enabled=False + WARNING
- `test_disabledIfConfigOff`: setenv + disabled config -> self.enabled=False + no logs (quiet)
- `test_webhookUrlNotLogged`: AST walk asserting no writeLog Call argument references self.webhook_url or a discord.com/api/webhooks string literal
- `test_envReadExactlyOnce`: source contains exactly one `os.environ` occurrence

## Threat Surface Mitigations (from PLAN threat_model)

| Threat ID | Disposition | Mitigation Landed |
|-----------|-------------|-------------------|
| T-05-03-WEBHOOK-LEAK | mitigate | webhook_url referenced only by `requests.post(self.webhook_url, ...)`; writeLog give-up message uses payload's event URL (public link); test_webhookUrlNotLogged AST grep enforces |
| T-05-03-RETRY-DOS | mitigate | single retry; min(wait, 30.0) cap; second 429 returns without raising |
| T-05-03-ENV-RUNTIME-CHANGE | mitigate | os.environ.get called in __init__ only; stored on instance; test_urlReadAtInit enforces |
| T-05-03-NETWORK-FAILURE | mitigate | requests.post timeout=10s; worst-case blocking = 10 + 30 + 10 = 50s per send |

## Verification

- `python -c "from notifiers.shopbot_notifier_discord import DiscordNotifier; from notifier_base import Notifier; assert issubclass(DiscordNotifier, Notifier)"` PASS
- `rg "os.environ.get.*SHOPBOT_DISCORD_WEBHOOK_URL" notifiers/shopbot_notifier_discord.py` matches exactly 1 line (line 31)
- `rg -c "os.environ" notifiers/shopbot_notifier_discord.py` = 1
- `python -m pytest -q tests/test_notifiers_discord.py` -> 12 passed
- `python -m pytest -q --ignore=tests/test_notifiers_email.py --ignore=tests/test_notifiers_sms.py --ignore=tests/test_notification_writer.py --ignore=tests/test_utils.py` -> 239 passed (sibling Wave 1 RED files remain RED for their own plans, as expected)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Pre-existing test_utils.py collection error ignored**
- **Found during:** broader suite verification
- **Issue:** `tests/test_utils.py` imports `make_tiny` from `utils`, but `utils.py` no longer exports that symbol (pre-existing breakage unrelated to Phase 5).
- **Fix:** Added `--ignore=tests/test_utils.py` to the suite invocation (matches RESEARCH Q "Full suite" command which already excludes it).
- **Files modified:** none (verification command only)
- **Out of scope:** would need a separate fix; logged here for visibility.

**2. [Rule 1 - Robustness] _retry_after_seconds wrapped float() in try/except**
- **Found during:** implementation review
- **Issue:** RESEARCH Q1 sample code does `float(body.get("retry_after", 1))` raw; a malformed body could raise TypeError.
- **Fix:** Wrapped float() of body field in try/except returning 1.0 default. Same protection already used for the header path. Keeps the notifier robust against an upstream malformed JSON.
- **Files modified:** notifiers/shopbot_notifier_discord.py
- **Commit:** a140d8e

### Plan Adjustments (vs RED skeleton in 05-01)

- RED skeleton called `DiscordNotifier(DiscordNotifierConfig(enabled=True))` (single positional arg). The registry contract from Plan 05-02 requires `sub_config=...` / `app_config=...` kwargs. Per the Plan 05-03 action step 2 explicit instruction to "flip RED tests to GREEN", the GREEN tests use the kwargs form. The DiscordNotifier `__init__` signature matches Plan 05-02's SoundNotifier exactly (`*, sub_config=None, app_config=None`).

## Authentication Gates

None.

## Known Stubs

None.

## Commits

| Hash | Message | Files |
|------|---------|-------|
| a140d8e | feat(05-03): DiscordNotifier (NOTIF-04) embed + 429 single-retry policy | notifiers/shopbot_notifier_discord.py (new), tests/test_notifiers_discord.py (RED->GREEN) |

## Self-Check: PASSED

- notifiers/shopbot_notifier_discord.py exists (98 lines, < 150 line cap)
- tests/test_notifiers_discord.py rewritten to GREEN (12 tests, all passing)
- Commit a140d8e present in git log
- All plan success criteria satisfied
- STATE.md and ROADMAP.md untouched (per execution directive)
