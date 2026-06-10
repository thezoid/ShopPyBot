# Feature Research — v4.0 Win-the-Drop (Checkout Automation + Reliability)

**Domain:** Verified-checkout + reliability features for a community-extensible retail stock-checkout bot (Python / nodriver)
**Researched:** 2026-06-10
**Milestone scope:** NEW v4.0 features only. Existing v3.0 and earlier features are not re-researched.
**Confidence:** HIGH (checkout flow patterns, retry/idempotency), MEDIUM (per-retailer confirmation signals), HIGH (supervisor/backoff patterns), MEDIUM (nodriver cookie persistence — known bugs)

---

## Context: What Already Exists (Do Not Re-Research)

| System | Key facts relevant to v4.0 |
|--------|---------------------------|
| Plugin ABC (`RetailerPlugin`) | `async auto_buy(url) -> bool`; orchestrator marks purchased only on `True` return; `test_mode` skips final click on 6 of 7 plugins |
| `auto_buy` gap | Returns `True` after `place_order.click()` with no confirmation check; button-click = "purchased" is wrong |
| Orchestrator (`core/orchestrator.py`) | `asyncio.TaskGroup` with one long-lived `run_plugin` coroutine per plugin; write-queue serializes DB writes; `_try_auto_buy` wraps auto_buy with a bare try/except but no retry |
| `_write_queue_drain` | Sole write path; already serialized; enqueues `("purchased", link)` tuples |
| `models.py` | `update_item_purchased_sync` with `purchased` flag; already prevents re-buy on next poll loop |
| Login pattern | Called inside `auto_buy` on every invocation; no session reuse; MFA/passkey gates require manual user action |
| BestBuy CVV | Threaded via `plugin._cvv`; set by `main.py` via `getpass`; never logged |
| Config | `debug.test_mode: bool`; `app.poll_interval: float`; per-platform `min_delay`/`max_delay` |

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features whose absence makes the bot functionally incomplete for v4.0's stated goal of "verified orders."

| Feature | Why Expected | Complexity | Existing Hook / Dependency | ToS-sensitive? |
|---------|--------------|------------|---------------------------|----------------|
| **Order-confirmation detection** | Without it, a bot that reports "purchased" on a click, then discovers the order failed (session expired, payment declined, CAPTCHA injected mid-checkout), will suppress re-attempts forever via the `purchased` flag. Every real checkout bot verifies a real order. | MEDIUM | Extends `auto_buy`; must return `True` only on confirmed signal; write-queue path unchanged | No |
| **Monitor-only / alert-without-buy mode** | Users routinely want to watch a drop without having the bot place an order — either for manual review or because `auto_buy` is not safe for that item. Currently, `auto_buy=False` per-item skips buying, but there is no global "never buy" CLI flag. Also closes the `test_mode` hole: 6 of 7 plugins skip the final click under `test_mode` but still call all preceding checkout steps. | LOW | `--monitor-only` CLI flag passed into `async_main`; orchestrator skips `_try_auto_buy` globally; orthogonal to per-item `auto_buy` flag | No |
| **Checkout profile (shipping/billing form-fill)** | On limited drops, a new-device checkout or address-change challenge fires the full shipping/billing form. Bots that only handle pre-saved accounts stall silently. Profile data must be stored encrypted, never in config.yml or logs. | MEDIUM | New `CheckoutProfile` model in `CredentialStore`; per-plugin form-fill helper; PCI constraint: CVV at runtime only, never persisted | **Opt-in** (payment data in credential store) |
| **Bounded retry-on-cart with backoff and double-buy guard** | Transient failures (add-to-cart 429, session blip, checkout button briefly absent) are common on drop day. Without retry, the bot abandons valid opportunities. Without double-buy guard, retrying a POST-equivalent checkout click risks duplicate orders. | MEDIUM | New `_try_auto_buy_with_retry` wrapping `_try_auto_buy`; idempotency guard reads `purchased` flag from DB before each attempt; max attempts + exponential backoff cap | No |
| **Per-step / per-item checkout time budget** | A stalled checkout step (form-fill waiting forever, checkout page not loading) can block the entire plugin coroutine, preventing future poll cycles. `asyncio.wait_for` wrapping each step is standard practice. | LOW | `asyncio.wait_for` wrapping `auto_buy` call in orchestrator; configurable `checkout_timeout_secs` per platform | No |

### Differentiators (Competitive Advantage)

Features that distinguish ShopPyBot from single-script bots and advance the plugin-framework value proposition.

| Feature | Value Proposition | Complexity | Existing Hook / Dependency | ToS-sensitive? |
|---------|-------------------|------------|---------------------------|----------------|
| **Encrypted session/cookie persistence** | Login + MFA is the slowest and most fragile part of checkout. Reusing a live authenticated session eliminates the passkey-dismiss and OTP pauses on every `auto_buy` call. Commercially sold bots (Refract, etc.) call this "prelogin." | MEDIUM | nodriver `browser.cookies.get_all()` / `set_all()` via CDP — known `set_all` bugs in issues #1816, #2020, #2232; workaround: direct `cdp.storage.set_cookies` call; encrypt with `cryptography.fernet` or reuse existing `EncryptedFileStore`; store path under per-platform key | **Opt-in** (persists auth tokens to disk) |
| **Structured health / heartbeat surface** | Long-running unattended runs silently stall. A per-plugin liveness timestamp + periodic heartbeat log line lets operators know the bot is alive without polling logs manually. Also enables future monitoring integrations (Discord webhook, Prometheus). | LOW | New `_heartbeat` coroutine in orchestrator TaskGroup; writes `last_alive_at` dict keyed by plugin name; emits a log line at configurable interval | No |
| **Per-coroutine supervisor with backoff restart** | Currently, if a plugin coroutine raises an unhandled exception, `asyncio.TaskGroup` propagates it and tears down all tasks. A supervisor wrapper catches the exception, sleeps with exponential backoff, and relaunches the coroutine — keeping other plugins alive. Failure budget (e.g., 5 crashes in 5 minutes) triggers a clean exit rather than an infinite restart loop. | MEDIUM | Replaces bare `tg.create_task(run_plugin(...))` with `tg.create_task(supervised(run_plugin, plugin, ...))` wrapper; failure counter per plugin with rolling window | No |
| **Browser-crash detection and relaunch** | nodriver's Chrome subprocess can die silently (OOM, renderer crash, orphan after proxy disconnect). No built-in crash detection exists in nodriver (confirmed by docs + issue #2130). Detection via `plugin.driver._process.returncode` or a CDP ping; relaunch calls `plugin.teardown()` then `plugin.setup()` then re-adds to active pool. | MEDIUM | New `_is_browser_alive(plugin)` helper; called at top of each `run_plugin` iteration; relaunch via `registry.relaunch_plugin(plugin)` | No |
| **DB read-path error isolation** | A SQLite read failure in `get_items_sync` raises into `run_plugin`, which — without the supervisor above — kills the plugin coroutine. Wrapping DB reads with a retry (3x with 1s sleep) and logging the error without re-raising prevents a DB hiccup from stopping the bot. | LOW | Narrow try/except around `loop.run_in_executor(None, get_items_sync)` in `run_plugin`; log error, skip iteration, continue loop | No |
| **Per-item orchestrator timeout** | If `_check_and_buy` hangs (browser frozen mid-checkout), all items for that plugin are blocked. `asyncio.wait_for` around the entire `_check_and_buy` call with a `per_item_timeout_secs` config value prevents one stuck item from starving others. | LOW | `asyncio.wait_for(_check_and_buy(...), timeout=cfg.app.per_item_timeout_secs)` in `run_plugin` | No |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Full card-data persistence** | Avoid re-entering payment info on each run | PCI-DSS: storing full card number + CVV anywhere on disk is a serious violation; most retailers require CVV at time of transaction specifically to prevent stored re-use | Store only last-4 + expiry for display; collect CVV at runtime via `getpass`; use retailer-saved payment methods; the v4.0 design already does this correctly |
| **Immediate retry on every checkout failure** | Maximize acquisition chances | POST-equivalent checkout is not idempotent; an immediate retry after an ambiguous "connection reset" can produce a duplicate order; Amazon and BestBuy do not expose an idempotency key | Check `purchased` flag in DB before each retry attempt; use exponential backoff with a small max-attempts cap (3-5); add a mandatory post-click settle delay before reading confirmation |
| **Parallel multi-account checkout** | Higher acquisition probability per drop | Most ToS-hostile feature category; direct CFAA risk when accounts are fictitious; high detection/ban rate; requires N sets of credentials and N billing profiles; complex state machine for coordinating successes | Single-account, single-attempt with fast retry; this is deferred in PROJECT.md and should stay deferred |
| **Request/API-mode checkout (bypass browser)** | 10-100x faster than DOM automation | Arms-race: retailers detect and block API-mode checkout constantly; maintenance burden is very high; defeats the stealth investment in v3.0; also more ToS-hostile than browser automation | Stick with the nodriver browser stack; optimize checkout speed through session persistence and per-step timeouts |
| **Amazon WAF CAPTCHA auto-solve** | Unblock auto-buy when WAF fires | Amazon WAF CAPTCHA (`window.gokuProps`) is a distinct challenge from reCAPTCHA v2; 2captcha does not support it; any "solve" service for it changes frequently and is fragile; deferred in PROJECT.md | Manual pause on WAF detection (already implemented); defer until a reliable solve path exists |
| **Unlimited retry loops on cart failure** | Never miss a drop due to transient errors | Drop-day 429s can turn a "retry forever" loop into a ban trigger; cart-state can become inconsistent across unlimited retries; logs become unreadable | Bounded retry (max 3-5 attempts) with jitter backoff; log each attempt; abort and re-arm on next poll cycle |

---

## Order-Confirmation Detection: Per-Retailer Signal Inventory

This is the most research-intensive area. Signals are listed from most to least reliable.

### Amazon

| Signal | Reliability | Implementation |
|--------|------------|----------------|
| URL contains `/gp/buy/thankyou/handlers` | HIGH | Amazon's standard post-order landing URL; check `tab.url` after `place_order.click()` with a short settle delay | 
| Page contains order-number element `#orderDetails` or `span.order-id-number` | HIGH (backup) | `tab.select("#orderDetails", timeout=10)` or text search for pattern `\d{3}-\d{7}-\d{7}`; Amazon order numbers always match this format |
| Page title contains "Thank you" | MEDIUM | JavaScript `document.title` evaluation; fragile to i18n and A/B tests |
| Account order history contains new entry (API call to `/gp/css/order-history`) | LOW (too slow) | Requires a second navigation; only use as a last-resort verification pass |

**Recommended composite check for Amazon:** URL prefix match (`/gp/buy/thankyou`) AND either `#orderDetails` element present OR order-number regex match in page text. Any one of URL or DOM match is sufficient; require at least one.

### BestBuy

| Signal | Reliability | Implementation |
|--------|------------|----------------|
| URL contains `/checkout/r/thank-you` or `/checkout/r/confirmation` | HIGH | BestBuy's post-order redirect; check `tab.url` after place-order click |
| Page contains order-number element `.thank-you-order-number` or `[data-testid="order-number"]` | HIGH (backup) | `tab.select(".thank-you-order-number", timeout=10)` — confirmed by ScrapingBee article pattern; BestBuy's selector may drift on redesign |
| Page contains text "Order confirmed" or "Thank you for your order" | MEDIUM | `tab.find("Order confirmed", timeout=5)` — confirmed by BestBuy UX review and community reports |

**Important BestBuy caveat:** Refract's docs note "BestBuy's site does not surface failures clearly — it may show 'invited' or 'requested' states that are NOT confirmed purchases." The URL redirect to `/checkout/r/thank-you` is the most reliable signal. Absence of redirect after place-order click = failure (not confirmed).

**Recommended composite check for BestBuy:** URL must contain `/thank-you` AND `.thank-you-order-number` element OR "Order confirmed" text. Do not rely on text alone.

### Other Plugins (Walmart, Target, GameStop, SquareEnix, NewEgg)

These plugins currently have no `auto_buy` confirmation check and v4.0 does not extend form-fill to them. The correct v4.0 approach: wrap their existing `place_order.click()` with a URL-based check (any redirect away from the order-review page) and a generic "order number" regex scan. No per-plugin DOM surgery needed for v4.0 — that is deferred.

---

## Retry-on-Cart Semantics

### When to Retry

| Condition | Retry? | Rationale |
|-----------|--------|-----------|
| `add-to-cart` button not found (stock gone) | NO | Item sold out; re-arm on next poll cycle |
| `add-to-cart` click returns 429 / challenge page | YES (with backoff) | Transient rate-limit; back off and retry |
| Cart page loads but checkout button absent | YES (1 retry) | Intermittent cart load failure |
| `place_order.click()` completes but NO confirmation URL observed | YES (1 retry, max 2 total) | Possible click miss or navigation delay |
| `place_order.click()` completes AND confirmation URL observed | NO | Success; enqueue DB write immediately |
| `purchased` flag already set in DB | NO (hard guard) | Idempotency: DB is the authoritative state |
| Any attempt after 5 consecutive failures | ABORT | Failure budget exceeded; log and exit checkout |

### Backoff Values (Recommended)

- Base delay: 2 seconds
- Multiplier: 2x per attempt
- Max delay: 30 seconds
- Jitter: `random.uniform(0, base_delay)` added to each sleep
- Max attempts: 3 for cart-add; 2 for place-order (lower because place-order is less idempotent)

### Double-Buy Guard (Idempotency)

The `purchased` flag in SQLite is the idempotency anchor. Before each retry attempt in `_try_auto_buy_with_retry`, read the flag synchronously. If already `True`, abort silently. This is safe because `_write_queue_drain` is the only writer and runs serially.

**Critical:** Do NOT retry immediately after `place_order.click()`. Insert a settle delay (3-5 seconds) before reading the confirmation URL. The browser navigation after a successful order has measurable latency.

---

## Checkout Time Budgets (Recommended Values)

| Step | Recommended Timeout | Rationale |
|------|--------------------|-----------| 
| `add-to-cart` click + cart page load | 15 seconds | Fast on good sessions; generous for slow pages |
| Full checkout flow (`auto_buy` end-to-end) | 90 seconds | Covers form-fill + CVV + confirmation wait |
| Per-item `_check_and_buy` (orchestrator level) | 120 seconds | Adds 30s buffer above `auto_buy` for pre/post work |
| Post-place-order settle (before confirmation check) | 5 seconds | Navigation latency after successful order |
| Session/cookie load at login | 10 seconds | CDP `set_cookies` call |

These map directly to `asyncio.wait_for` timeout arguments. They should be config-overridable under `platforms.<name>.checkout_timeout_secs`.

---

## Session / Cookie Persistence Implementation Notes

### nodriver-Specific Concerns (HIGH confidence — from GitHub issues #1816, #2020, #2232)

- `browser.cookies.set_all(cookies)` has a confirmed bug: the `cookies` parameter is silently overwritten by `cdp.storage.get_cookies()` before use. The result is that set_all does nothing.
- **Workaround confirmed working:** Use `await tab.send(cdp.storage.set_cookies(cookies=cookie_list))` directly — bypasses the broken helper.
- `browser.cookies.get_all()` works correctly for reading.
- HttpOnly cookies are accessible via CDP `Network.getAllCookies` but not via `document.cookie` JavaScript.

### Storage Approach

1. After successful login, call `await plugin.driver.cookies.get_all()` to capture the full cookie jar as a list of `cdp.network.Cookie` objects.
2. Serialize to JSON (not pickle — avoids class version issues on upgrade).
3. Encrypt with `cryptography.fernet` using a key from `CredentialStore` (reuse existing infrastructure).
4. Write to a platform-scoped file: `.shopbot_sessions/<platform>_cookies.enc` under the app data directory.
5. On next `login()` call, check if a valid session file exists. If yes, restore cookies via direct CDP call (workaround above), navigate to account page, verify logged-in state by checking for account-nav element. If verification fails, fall back to full login.

### Security Constraints (Non-Negotiable)

- Session files must be encrypted at rest (no plaintext JSON cookies on disk).
- Session files must be scoped to a platform and never shared across plugins.
- Session file path must never appear in logs.
- This feature is **opt-in** (`platforms.<name>.session_persistence: true`) because it persists authentication tokens that could be misused if the machine is compromised.

---

## Supervisor and Health Patterns

### Per-Coroutine Supervisor (Recommended Pattern)

Replace the current bare `tg.create_task(run_plugin(...))` in `async_main` with a supervised wrapper:

```
supervised(coroutine_factory, *args, max_failures=5, window_secs=300, base_backoff=2.0, max_backoff=60.0)
```

- Runs `coroutine_factory(*args)` in a loop.
- On exception: increments per-plugin failure counter, logs the error, sleeps with exponential backoff + jitter.
- If failure counter exceeds `max_failures` within `window_secs`: logs a critical error and returns (does NOT re-raise into TaskGroup, allowing other plugins to continue).
- On success (clean return from the coroutine): resets failure counter.
- Respects `asyncio.CancelledError` — never catches it; propagates cleanly for shutdown.

### Browser-Crash Detection

nodriver does not provide a built-in health check. The recommended detection approach:

1. Check `plugin.driver._process.returncode is not None` — if the subprocess has exited, the browser is dead.
2. Alternatively: wrap every `tab.select(...)` call in a try/except; if a `ConnectionError` or `websockets` disconnect fires, treat as crash.
3. On crash detection: call `plugin.teardown()`, sleep 5 seconds, call `plugin.setup()`. If setup fails, increment the failure budget.

### Health / Heartbeat Surface

A lightweight `_heartbeat` coroutine runs in the TaskGroup alongside plugin coroutines:

- Writes `{"plugin": ..., "last_alive": ISO-timestamp, "items_checked": N}` to a per-plugin in-memory dict every `heartbeat_interval_secs` (default: 60).
- Emits one log line per plugin at INFO level: `[HEARTBEAT] AmazonPlugin alive, checked 42 items`.
- Optionally serializes the dict to a JSON file (`.shopbot_health.json`) for external monitoring. This is opt-in.

---

## Feature Dependencies

```
Order-confirmation detection
    requires --> auto_buy returns True ONLY on confirmed signal
    requires --> settle delay before confirmation read

Bounded retry-on-cart
    requires --> Order-confirmation detection (to distinguish "click failed" from "click succeeded")
    requires --> DB purchased flag read before each attempt (idempotency guard)
    conflicts --> Unlimited retry (anti-feature)

Checkout profile form-fill
    requires --> CheckoutProfile in CredentialStore (encrypted; never plaintext)
    enhances --> Retry-on-cart (profile re-fill on session expiry retry)

Session/cookie persistence
    requires --> CredentialStore Fernet key
    requires --> nodriver CDP workaround (set_cookies direct call)
    enhances --> Checkout profile form-fill (fewer form-fills needed when session is live)
    conflicts --> Unencrypted cookie storage (anti-feature)

Per-coroutine supervisor
    requires --> asyncio.CancelledError propagation (must not be caught)
    enhances --> Browser-crash detection + relaunch (supervisor drives the relaunch loop)

Browser-crash detection
    requires --> plugin.driver._process or CDP ping
    requires --> plugin.teardown() + plugin.setup() idempotency

Per-item orchestrator timeout
    requires --> asyncio.wait_for (stdlib, no new dependency)
    enhances --> Per-coroutine supervisor (timeout fires before supervisor failure budget)

Monitor-only mode
    requires --> --monitor-only CLI flag wired into async_main
    conflicts --> auto_buy per-item flag (orthogonal; monitor-only overrides all)

Health / heartbeat
    enhances --> Per-coroutine supervisor (heartbeat absence = implicit crash signal)
```

---

## v4.0 Feature Prioritization

| Feature | User Value | Implementation Cost | Priority | Phase Recommendation |
|---------|------------|---------------------|----------|---------------------|
| Order-confirmation detection (Amazon + BestBuy) | HIGH | MEDIUM | P1 | Phase 18 (Acquisition Core A) |
| Monitor-only mode + close test_mode hole | HIGH | LOW | P1 | Phase 18 |
| Bounded retry-on-cart + double-buy guard | HIGH | MEDIUM | P1 | Phase 19 (Acquisition Core B) |
| Per-step / per-item checkout time budget | HIGH | LOW | P1 | Phase 19 |
| Per-coroutine supervisor + backoff restart | HIGH | MEDIUM | P1 | Phase 20 (Always-On Reliability A) |
| Browser-crash detection + relaunch | HIGH | MEDIUM | P1 | Phase 20 |
| DB read-path error isolation | MEDIUM | LOW | P2 | Phase 20 |
| Encrypted session/cookie persistence | HIGH | MEDIUM | P2 | Phase 21 (Always-On Reliability B) |
| Checkout profile form-fill (BestBuy, Amazon) | MEDIUM | MEDIUM | P2 | Phase 21 |
| Structured health / heartbeat surface | MEDIUM | LOW | P2 | Phase 21 |
| SIGTERM/SIGINT teardown bridge | MEDIUM | LOW | P2 | Phase 20 or 21 |
| Headless pygame import-crash guard | LOW | LOW | P3 | Phase 20 (opportunistic) |

**Priority key:**
- P1: Required for v4.0 milestone goal ("verified orders + unattended survival")
- P2: Should ship in v4.0; user-visible reliability improvement
- P3: Opportunistic; include if low-risk, otherwise defer

---

## ToS and Safety Summary

| Feature | ToS Risk | Required Treatment |
|---------|----------|--------------------|
| Checkout profile form-fill (shipping/billing) | Moderate: automated form-fill on retail sites violates most ToS | **Opt-in** via `platforms.<name>.checkout_profile: enabled: true`; document risk clearly |
| Session/cookie persistence | Moderate: persists auth tokens; also violates most retailer ToS for automation | **Opt-in** via `platforms.<name>.session_persistence: true`; encrypted at rest; document risk |
| Bounded retry-on-cart | Low: retry is common in legitimate clients | Safe by default; bounded to prevent abuse |
| Monitor-only mode | None: no purchasing | Safe; explicitly reduces ToS risk |
| Order-confirmation detection | None: improves accuracy | Safe; prevents false "purchased" flags |
| All others (supervisor, crash relaunch, heartbeat, timeouts) | None: internal reliability | Safe by default |

---

## Sources

- nodriver cookie bug issues: github.com/ultrafunkamsterdam/undetected-chromedriver issues #1816, #2020, #2232
- BestBuy bot checkout selectors: github.com/TreborNamor/Agressive-Store-Bots/blob/main/bestbuy.py (`.button--place-order`, `#credit-card-cvv`)
- Order confirmation DOM pattern (ScrapingBee article): blog.adnansiddiqi.me — `.thank-you-order-number` CSS selector confirmed as order confirmation signal
- BestBuy confirmation behavior: help.refractbot.com/modules/bestbuy-us — "site does not surface failures; only returns invited/requested"
- Asyncio supervisor + failure budget pattern: medium.com/@skyler.lewis asyncio-patterns-part-2-managing-failures
- Retry idempotency for POST: scrapeops.io/python-web-scraping-playbook/python-requests-retry-failed-requests — "POST is not idempotent; retry only on connection errors"
- BOTS Act / ToS consequences: ftc.gov/business-guidance/blog/2025/04/bots-act-compliance-time-refresher
- nodriver browser crash issue: github.com/ultrafunkamsterdam/undetected-chromedriver/issues/2130

---

*Feature research for: v4.0 Win-the-Drop — Acquisition Core + Reliability*
*Researched: 2026-06-10*
