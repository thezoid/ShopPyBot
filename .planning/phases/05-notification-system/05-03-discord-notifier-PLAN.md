---
phase: 05-notification-system
plan: 03
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - notifiers/shopbot_notifier_discord.py
  - tests/test_notifiers_discord.py
autonomous: true
requirements:
  - NOTIF-04
tags:
  - python
  - notifications
  - discord
  - webhook
  - requests
  - wave-1

must_haves:
  truths:
    - "notifiers/shopbot_notifier_discord.py defines `class DiscordNotifier(Notifier)` with class attribute `name = 'discord'`"
    - "DiscordNotifier.__init__ reads `SHOPBOT_DISCORD_WEBHOOK_URL` env var via `os.environ.get` ONCE at instantiation (CONTEXT pitfall #4 + RESEARCH Q11.1). Reading env vars inside send() is FORBIDDEN — verified via AST grep on the file"
    - "DiscordNotifier.__init__ accepts `sub_config: DiscordNotifierConfig, app_config` keyword args matching notifier_registry._instantiate contract"
    - "When `sub_config.enabled is True` BUT env SHOPBOT_DISCORD_WEBHOOK_URL is missing or empty: __init__ sets `self.enabled = False` AND emits a WARNING via writeLog naming the missing env var (mirrors SMS two-lock distinguishable error pattern)"
    - "When `sub_config.enabled is False`: __init__ sets `self.enabled = False` quietly (no warning; user explicitly turned it off)"
    - "DiscordNotifier.send body builds a Discord embed payload with fields {title, description, url, color, timestamp, fields}; timestamp is `event.timestamp.astimezone(timezone.utc).isoformat()`; color is `0x2ECC71` for action=='detected' else `0x3498DB` for action=='purchased' (RESEARCH Q1 payload shape)"
    - "DiscordNotifier.send wraps the actual HTTP call in `await asyncio.to_thread(self._post_with_one_retry, payload)` — no requests.post call in the async path directly"
    - "_post_with_one_retry on 429 response: read `Retry-After` HEADER first (fallback to `retry_after` body field then to default 1s), cap the wait at 30.0 seconds, sleep, retry exactly ONCE, then call raise_for_status. Two POSTs maximum per send() invocation (CONTEXT pitfall #3 + RESEARCH Q11.11)"
    - "On a second consecutive 429: _post_with_one_retry MUST NOT raise — it logs a WARNING via writeLog and returns (skipping raise_for_status). A missed alert is acceptable; blocking the writer is not"
    - "Non-429, non-2xx responses propagate via `raise_for_status` — these are caught by `notification_writer`'s `asyncio.gather(return_exceptions=True)` and logged with the notifier name (NOTIF-01 isolation)"
    - "DiscordNotifier does NOT call requests.get / requests.put / any other HTTP verb; only POST to the webhook URL"
    - "The webhook URL string MUST NOT appear in any writeLog call (CONTEXT pitfall + RESEARCH Q11.16 secret containment)"
    - "All RED tests in tests/test_notifiers_discord.py from Plan 05-01 now PASS"
    - "Full pytest suite remains green across Phase 1/2/3/4/5"
  artifacts:
    - path: "notifiers/shopbot_notifier_discord.py"
      provides: "DiscordNotifier (NOTIF-04) with embed builder + Retry-After-honoring single-retry POST"
      contains: "class DiscordNotifier"
      min_lines: 60
    - path: "tests/test_notifiers_discord.py"
      provides: "GREEN tests for NOTIF-04 (embed shape, 429-once-success, 429-twice-giveup, env-at-init, URL not in logs)"
  key_links:
    - from: "notifiers/shopbot_notifier_discord.py"
      to: "os.environ.get"
      via: "SHOPBOT_DISCORD_WEBHOOK_URL read once in __init__"
      pattern: "os\\.environ\\.get\\([\"']SHOPBOT_DISCORD_WEBHOOK_URL"
    - from: "DiscordNotifier.send"
      to: "asyncio.to_thread"
      via: "wraps _post_with_one_retry"
      pattern: "to_thread\\(.*_post_with_one_retry"
    - from: "_post_with_one_retry"
      to: "requests.post"
      via: "single 429-aware retry loop"
      pattern: "requests\\.post"
---

<objective>
Wave 1 (parallel-safe): ship the Discord webhook notifier (NOTIF-04). Reads `SHOPBOT_DISCORD_WEBHOOK_URL` once at `__init__`; builds a Discord embed payload from a `NotificationEvent`; POSTs via `requests` wrapped in `asyncio.to_thread`; honors a 429 `Retry-After` HEADER for ONE retry capped at 30 seconds, then gives up cleanly. Flip RED tests in `tests/test_notifiers_discord.py` to GREEN.

Purpose: Discord is the highest-value channel for the open-source target audience (CONTEXT D-04 priority). The embed contract is well-specified by Discord docs (RESEARCH Q1). The single-retry policy keeps the notification_writer responsive: a missed alert is acceptable, a wedged writer is not.

Output: notifiers/shopbot_notifier_discord.py + GREEN test file.
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
@tests/test_notifiers_discord.py
</context>

<interfaces>
Target `notifiers/shopbot_notifier_discord.py`:

```python
"""Discord webhook notifier (NOTIF-04).

Posts a Discord embed to a webhook URL read from SHOPBOT_DISCORD_WEBHOOK_URL
env var. On a 429 response, honors the Retry-After header once (capped at 30
seconds), then gives up + logs. NEVER blocks the writer for more than one retry.

Webhook URL is read ONCE at __init__ (CONTEXT pitfall #4). Reading env vars
inside send() is FORBIDDEN by the must_haves contract.
"""
import asyncio
import os
import time
from datetime import timezone

import requests

from logger import writeLog
from notifier_base import Notifier, NotificationEvent

_DETECTED_COLOR = 0x2ECC71
_PURCHASED_COLOR = 0x3498DB
_MAX_RETRY_WAIT_SECONDS = 30.0
_HTTP_TIMEOUT_SECONDS = 10


class DiscordNotifier(Notifier):
    name = "discord"

    def __init__(self, *, sub_config, app_config) -> None:
        wantedEnabled = bool(sub_config and sub_config.enabled)
        self._webhook_url = os.environ.get("SHOPBOT_DISCORD_WEBHOOK_URL", "")
        if not wantedEnabled:
            self.enabled = False
            return
        if not self._webhook_url:
            writeLog(
                "Discord notifier: config.discord.enabled=true but "
                "SHOPBOT_DISCORD_WEBHOOK_URL env var is missing; disabling.",
                "WARNING",
            )
            self.enabled = False
            return
        self.enabled = True

    async def send(self, event: NotificationEvent) -> None:
        payload = _build_payload(event)
        await asyncio.to_thread(self._post_with_one_retry, payload)

    def _post_with_one_retry(self, payload: dict) -> None:
        r = requests.post(
            self._webhook_url, json=payload, timeout=_HTTP_TIMEOUT_SECONDS
        )
        if r.status_code == 429:
            wait = _retry_after_seconds(r)
            time.sleep(min(wait, _MAX_RETRY_WAIT_SECONDS))
            r = requests.post(
                self._webhook_url, json=payload, timeout=_HTTP_TIMEOUT_SECONDS
            )
            if r.status_code == 429:
                writeLog(
                    f"Discord notifier: 429 after one retry; giving up "
                    f"(event url={payload['embeds'][0].get('url')})",
                    "WARNING",
                )
                return
        r.raise_for_status()


def _build_payload(event: NotificationEvent) -> dict:
    color = _PURCHASED_COLOR if event.action == "purchased" else _DETECTED_COLOR
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


def _retry_after_seconds(response) -> float:
    header = response.headers.get("Retry-After")
    if header is not None:
        try:
            return float(header)
        except ValueError:
            pass
    try:
        body = response.json()
    except Exception:
        return 1.0
    return float(body.get("retry_after", 1.0))
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement DiscordNotifier (NOTIF-04) and drive RED tests to GREEN</name>
  <files>notifiers/shopbot_notifier_discord.py, tests/test_notifiers_discord.py</files>
  <read_first>
    - notifier_base.py (Notifier ABC, NotificationEvent dataclass)
    - config_schema.py (DiscordNotifierConfig — fields and defaults)
    - tests/test_notifiers_discord.py (RED tests from Plan 05-01)
    - .planning/phases/05-notification-system/05-RESEARCH.md Q1 (Discord 429 spec, embed shape, payload code)
    - .planning/phases/05-notification-system/05-RESEARCH.md Q6 (test pattern for monkeypatching requests.post)
  </read_first>
  <behavior>
    - `from notifiers.shopbot_notifier_discord import DiscordNotifier` succeeds.
    - `DiscordNotifier` is a subclass of `Notifier`; `inspect.iscoroutinefunction(DiscordNotifier.send) is True`.
    - With env SHOPBOT_DISCORD_WEBHOOK_URL set + sub_config.enabled=True: `instance.enabled is True`.
    - With env absent + sub_config.enabled=True: `instance.enabled is False` AND a WARNING log fires referencing "SHOPBOT_DISCORD_WEBHOOK_URL".
    - With env set + sub_config.enabled=False: `instance.enabled is False` AND no warning fires (quiet opt-out).
    - The webhook URL is captured at __init__: setting a new env value AFTER instantiation does NOT change `instance._webhook_url`.
    - The webhook URL string MUST NOT appear in any writeLog call argument (AST grep: walk the file for writeLog calls and assert no string literal or f-string interpolation references `self._webhook_url` or the URL pattern).
    - send() with action="detected" produces a payload whose embed has color == 0x2ECC71; action="purchased" produces color == 0x3498DB.
    - send() with a tz-naive event.timestamp raises AttributeError or works via astimezone(utc) — verify the test uses tz-aware (NotificationEvent should always carry tz-aware per Plan 05-01 must_have).
    - 429 on first POST + 200 on retry: send() succeeds with NO exception; total of two requests.post calls recorded; the retry waited for at most min(Retry-After, 30) seconds.
    - 429 on first POST + 429 on retry: send() returns without raising; writeLog WARNING fires with "giving up" message; total of two requests.post calls.
    - 500 on first POST: raise_for_status raises; the exception propagates (caught by notification_writer in Plan 05-06).
    - Test fixtures use `monkeypatch.setenv` and `monkeypatch.setattr("notifiers.shopbot_notifier_discord.requests.post", fakePost)` per RESEARCH Q6 pattern.
    - All RED tests in tests/test_notifiers_discord.py flip to GREEN.
  </behavior>
  <action>
    1. Create `notifiers/shopbot_notifier_discord.py` with the full contents from <interfaces>. Methods stay < 30 lines. File stays < 150 lines. Add NO new dependencies (requests is already pinned via Phase 1).

    2. Flip `tests/test_notifiers_discord.py` to GREEN. Build the helpers test infrastructure needs:
       - `FakeResponse(status_code, headers=None, json_body=None)` with `raise_for_status` method that raises requests.HTTPError on 4xx/5xx.
       - `fakePost(url, json, timeout)` recorder that returns `FakeResponse` instances in sequence (use a list of responses indexed by call count).
       - Use `monkeypatch.setattr("notifiers.shopbot_notifier_discord.requests.post", fakePost)`.
       - Use `monkeypatch.setenv("SHOPBOT_DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/test")`.
       - Monkeypatch `time.sleep` to be a no-op so 429 retry tests don't actually wait.
       - Build NotificationEvent with `datetime.now(timezone.utc)` for tz-aware timestamps.

    3. Test cases (matching the RED skeleton from Plan 05-01):
       - test_discordNotifierImportable: import succeeds.
       - test_urlReadAtInit: setenv before init; delenv after init; assert `instance._webhook_url` still holds the original value.
       - test_embedShape: send a "detected" event; assert posted payload structure matches the spec keys + color=0x2ECC71.
       - test_429RetryOnce: queue [FakeResponse(429, headers={"Retry-After": "0.01"}), FakeResponse(204)]; send; assert exactly 2 POSTs AND no exception raised.
       - test_429GiveUpAfterOne: queue [FakeResponse(429, headers={"Retry-After": "0.01"}), FakeResponse(429, headers={"Retry-After": "0.01"})]; send; assert exactly 2 POSTs AND no exception AND writeLog called with "giving up" substring.
       - test_disabledIfEnvMissing: delenv; sub_config.enabled=True; init; assert instance.enabled is False AND writeLog WARNING fires.
       - test_disabledIfConfigOff: setenv; sub_config.enabled=False; init; assert instance.enabled is False AND NO warning log (quiet).
       - test_webhookUrlNotLogged: AST grep — parse the source file, walk for writeLog Calls, assert none of their f-string components reference `self._webhook_url` directly.
       - test_purchasedColor: send with action="purchased"; assert payload embed color == 0x3498DB.

    4. Run `rtk pytest -q tests/test_notifiers_discord.py`. All GREEN.

    5. Run `rtk pytest -x -q --ignore=tests/test_notifiers_email.py --ignore=tests/test_notifiers_sms.py --ignore=tests/test_notification_writer.py`. Pre-existing + this plan + 05-02 (if landed first) all green; other Wave 1 RED files remain RED for their plans.
  </action>
  <verify>
    <automated>python -c "from notifiers.shopbot_notifier_discord import DiscordNotifier; from notifier_base import Notifier; assert issubclass(DiscordNotifier, Notifier)"</automated>
    <automated>rtk grep -n "os.environ.get.*SHOPBOT_DISCORD_WEBHOOK_URL" notifiers/shopbot_notifier_discord.py</automated>
    <automated>rtk grep -c "os.environ" notifiers/shopbot_notifier_discord.py</automated>
    <automated>rtk pytest -q tests/test_notifiers_discord.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_notifiers_email.py --ignore=tests/test_notifiers_sms.py --ignore=tests/test_notification_writer.py</automated>
  </verify>
  <acceptance_criteria>
    - notifiers/shopbot_notifier_discord.py exists with DiscordNotifier subclass
    - Env var read exactly once at __init__ (rtk grep -c "os.environ" returns 1)
    - 429 retry policy: max one retry, max 30s wait, then logs + returns
    - Webhook URL not referenced in any writeLog argument
    - All tests in tests/test_notifiers_discord.py GREEN
    - Pre-existing suite green; Wave 1 sibling RED files still RED
  </acceptance_criteria>
  <done>NOTIF-04 implemented. Wave 2 notification_writer will pick up DiscordNotifier via discover_notifiers.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Webhook URL (env -> code) | Must enter via env var only; must not be logged or echoed in error messages |
| Discord 429 response | Untrusted external input drives sleep duration; must be bounded |
| notification_writer isolation | DiscordNotifier exceptions must not crash the writer (NOTIF-01) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-03-WEBHOOK-LEAK | Information Disclosure | DiscordNotifier._post_with_one_retry | mitigate | URL kept in `self._webhook_url`; writeLog calls reference only event url (the public link), not the webhook URL; AST grep test enforces |
| T-05-03-RETRY-DOS | Denial of Service (self-inflicted) | _post_with_one_retry | mitigate | Single retry capped at min(Retry-After, 30s); second 429 returns without raising |
| T-05-03-ENV-RUNTIME-CHANGE | Tampering | DiscordNotifier.send | mitigate | Webhook URL captured at __init__; runtime env changes ignored (test enforces) |
| T-05-03-NETWORK-FAILURE | Denial of Service | requests.post timeout | mitigate | 10s timeout per request; total max blocking = 10 + 30 + 10 = 50s under worst-case 429 + retry |
</threat_model>

<verification>
- `python -c "from notifiers.shopbot_notifier_discord import DiscordNotifier; from notifier_base import Notifier; assert issubclass(DiscordNotifier, Notifier)"`
- `rtk grep -n "os.environ.get.*SHOPBOT_DISCORD_WEBHOOK_URL" notifiers/shopbot_notifier_discord.py` matches exactly one line
- `rtk pytest -q tests/test_notifiers_discord.py` shows all GREEN
- `rtk pytest -x -q --ignore=tests/test_notifiers_email.py --ignore=tests/test_notifiers_sms.py --ignore=tests/test_notification_writer.py` green
</verification>

<success_criteria>
- DiscordNotifier subclass of Notifier present in notifiers/
- Webhook URL env-var-only, read once at __init__
- Embed payload matches Discord spec (color by action, ISO 8601 timestamp, fields)
- 429 single-retry policy with 30s cap and clean give-up
- tests/test_notifiers_discord.py fully GREEN
</success_criteria>

<output>
After completion, create `.planning/phases/05-notification-system/05-03-SUMMARY.md`
</output>
