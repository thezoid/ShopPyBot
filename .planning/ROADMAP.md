# ShopPyBot — Roadmap

## Project

**Core Value:** A drop-in plugin framework that lets the community add new retail platform integrations by placing a single Python file in `plugins/` — no core changes required.

---

## Milestones

- ✅ **v1 Open Source Launch** — Phases 1-6 (shipped 2026-06-03)
- ✅ **v2.0 Modular Core + Cross-Platform UX** — Phases 7-11 (shipped 2026-06-06)
- ✅ **v3.0 Resilience + Ecosystem** — Phases 12-17 (shipped 2026-06-10)
- **v4.0 Win-the-Drop (Acquisition Core + Reliability)** — Phases 18-24 (in progress)

---

## Phases

<details>
<summary>✅ v1 Open Source Launch (Phases 1-6) — SHIPPED 2026-06-03</summary>

- [x] Phase 1: Foundations + Security (5/5 plans) — 2026-06-02
- [x] Phase 2: Plugin Migration (6/6 plans) — 2026-06-03
- [x] Phase 3: Community Documentation (2/2 plans) — 2026-06-03
- [x] Phase 4: Async Orchestrator (5/5 plans) — 2026-06-03
- [x] Phase 5: Notification System (5/5 plans) — 2026-06-03
- [x] Phase 6: Platform Expansion (5/5 plans) — 2026-06-03

</details>

<details>
<summary>✅ v2.0 Modular Core + Cross-Platform UX (Phases 7-11) — SHIPPED 2026-06-06</summary>

- [x] Phase 7: Modular Core Service (3/3 plans) — 2026-06-04
- [x] Phase 8: Credential Store (4/4 plans) — 2026-06-04
- [x] Phase 9: CLI Front-End (4/4 plans) — 2026-06-04
- [x] Phase 10: Optional Web UI (4/4 plans) — 2026-06-04
- [x] Phase 11: Cross-Platform Verification (5/5 plans) — 2026-06-05

Full phase detail archived at `.planning/milestones/v2.0-ROADMAP.md`.
Audit: `.planning/milestones/v2.0-MILESTONE-AUDIT.md` (status: passed).

</details>

<details>
<summary>✅ v3.0 Resilience + Ecosystem (Phases 12-17) — SHIPPED 2026-06-10</summary>

- [x] **Phase 12: Stability Foundation** — Close v2.0 deferred cross-OS checks and resolve 4 audit tech-debt items (completed 2026-06-09)
- [x] **Phase 13: Anti-Detection Layer 1 — Fingerprint + Proxy** — Apply JS fingerprint stealth patch and implement proxy rotation with ban detection (completed 2026-06-09)
- [x] **Phase 14: Anti-Detection Layer 2 — CAPTCHA Solving** — Integrate 2captcha opt-in solver with CredentialStore key, startup balance check, async executor wrapping, and spend cap (completed 2026-06-09)
- [x] **Phase 15: Plugin Ecosystem Registry** — Add difficulty/proxy/captcha class attrs to ABC, create GitHub wiki registry table, ship `shoppybot plugins list` command (completed 2026-06-09)
- [x] **Phase 16: Price Monitoring** — Per-item target price, append-only price history table, percentage-drop trigger, fan-out price-drop alerts, price-history CLI (completed 2026-06-10)
- [x] **Phase 17: Test Hardening** — Unit and integration coverage for all v3.0 features (completed 2026-06-10)

Full phase detail archived in `.planning/milestones/v3.0-ROADMAP.md`.

</details>

### v4.0 Win-the-Drop (Phases 18-24)

- [x] **Phase 18: Safety Gate + Config Foundation** — Central monitor-only mode, `place_order_guarded()` ABC method closing the 6-of-7 plugin safety hole, and `CheckoutConfig` schema as the foundation every downstream phase depends on (completed 2026-06-11)
- [x] **Phase 19: DB Schema + Confirmation Detection** — Add `order_id`/`confirmed_at`/`checkout_attempts` columns and build `core/confirmation.py` so `purchased` is only written on a real confirmed order number, never on a button click (completed 2026-06-11)
- [x] **Phase 20: Checkout Profile + Form-Fill** — Shipping/billing profile stored in CredentialStore (9 keys, no card data), BestBuy and Amazon form-fill, CVV getpass-only at runtime (completed 2026-06-11)
- [ ] **Phase 21: Per-Step Timeouts + Unified Retry + Cart-Retry** — One `RetryPolicy` in `core/retry.py` shared by both supervisor restart and cart-retry; per-step `asyncio.timeout()` per DOM stage; idempotency guard reads DB before every attempt
- [ ] **Phase 22: Supervisor + Browser Relaunch + Server Safety** — Per-coroutine supervision with failure budget absorbs crashes before the TaskGroup boundary; full relaunch sequence (teardown, proxy, stealth, login); DB read isolation; per-item orchestrator timeout; SIGTERM/SIGINT teardown bridge
- [ ] **Phase 23: Encrypted Session Persistence** — Fernet-encrypted cookie save/restore via `core/session_store.py` (reuses `EncryptedFileBackend` pattern); raw CDP restore path that bypasses the confirmed `set_all()` bug; replaces Phase 22's no-op stub
- [ ] **Phase 24: Health Surface + Server Safety** — `core/health.py` HealthRegistry, expanded `BotService.get_status()` with per-plugin liveness/heartbeat, `health_degraded` notification event, updated FastAPI `/status` endpoint, headless pygame crash guard

---

## Phase Details

### Phase 12: Stability Foundation

**Goal**: The v2.0 deferred debt and audit tech-debt are paid down before new features land, so the test suite is a reliable baseline
**Depends on**: Nothing — do first
**Requirements**: STAB-01, STAB-02
**Success Criteria** (what must be TRUE):

  1. All 4 deferred v2.0 cross-OS/UI manual checks (keyring restart survival, masked-TTY passphrase prompt, web dashboard render on Ubuntu, `0.0.0.0` bind warning) are executed and documented pass or fail, with any failures fixed
  2. Each of the 4 v2.0 audit tech-debt items has a targeted regression test that passes in CI
  3. No broad refactors occur: only the specific items in scope are changed

**Plans**: 4 plans

Plans:

- [x] 12-01-PLAN.md — TD-1: re-anchor logger logging_level read to core.paths.config_path() + regression test
- [x] 12-02-PLAN.md — TD-2/TD-3: harden SC1 secret-read guard (rglob) and separator guard (__file__-anchored)
- [x] 12-03-PLAN.md — TD-4 config write-seam regression test + accepted MOD-02 gap doc; MC-4 0.0.0.0 banner assertion
- [x] 12-04-PLAN.md — Execute and document MC-1..MC-4 deferred manual checks in docs/PLATFORMS.md

### Phase 13: Anti-Detection Layer 1 — Fingerprint + Proxy

**Goal**: Users can enable proxy rotation and the bot applies a JS fingerprint stealth patch at browser startup, measurably reducing Layer 2 bot signals
**Depends on**: Phase 12
**Requirements**: ANTI-08, ANTI-04, ANTI-05
**Success Criteria** (what must be TRUE):

  1. Bot applies `window.chrome`, `navigator.plugins`, `navigator.languages`, and screen-dimension patches via `core/stealth.py` at every browser startup with no plugin ABC version bump
  2. User can enable proxy rotation via an opt-in `proxy:` config section (disabled by default) listing `scheme://host:port` URLs; bot logs "Proxy rotation: enabled, pool_size=N" at startup
  3. Bot detects ban signals (HTTP 403/429/503, challenge-redirect, block-phrase body) and rotates to the next proxy, retiring a proxy after N consecutive failures for a configurable cooldown period
  4. WebRTC Chrome preferences are set at browser launch to prevent real-IP leaks through the proxy tunnel
  5. Each proxy is scoped to its plugin instance (`self._proxy`) and rotated only at browser restart, not mid-session

**Plans**: 3 plans

Plans:

- [x] 13-01-PLAN.md — core/stealth.py: STEALTH_JS + apply_stealth, ProxyPool (round-robin/retire/cooldown), proxy launch args + WebRTC flag, CDP Fetch auth, ban-signal detector (+ unit tests)
- [x] 13-02-PLAN.md — ProxyConfig schema (opt-in, disabled by default) + documented sample.config.yml proxy section
- [x] 13-03-PLAN.md — Wire stealth + proxy into BotService/orchestrator/registry and all 8 plugins; per-instance scoping, exact startup log, fail-loud on pool exhaustion, ban-detect recording

**UI hint**: no

### Phase 14: Anti-Detection Layer 2 — CAPTCHA Solving

**Goal**: Users who encounter reCAPTCHA v2 or Amazon WAF CAPTCHAs can opt into automated solving via 2captcha with full cost visibility and no credential plaintext exposure
**Depends on**: Phase 13 (fingerprint + proxy layer in place before adding CAPTCHA layer)
**Requirements**: ANTI-06, ANTI-07
**Success Criteria** (what must be TRUE):

  1. User can enable CAPTCHA solving via `captcha.enabled: true` in config; the 2captcha API key is stored exclusively in CredentialStore (`TWOCAPTCHA_API_KEY`), never in config.yml
  2. Bot checks 2captcha account balance at startup, logs a WARNING when balance is low, and skips solver use (falling back to manual pause) when balance is zero
  3. CAPTCHA solve calls use `run_in_executor` + `asyncio.timeout(120)` so other plugin poll tasks are not blocked during a solve
  4. A configurable `captcha.max_solves_per_run` limit prevents unbounded API charges; default config disables CAPTCHA solving

**Plans**: 3 plans

Plans:

- [x] 14-01-PLAN.md — Foundation: TWOCAPTCHA_API_KEY in SECRET_KEYS, CaptchaConfig, CaptchaSolver 2captcha v1 client (submit/poll/balance/cap)
- [x] 14-02-PLAN.md — Wiring: solver constructed fresh in async_main + startup balance check + registry.assign_solver (mirrors ProxyPool)
- [x] 14-03-PLAN.md — Plugin solve path: Amazon + BestBuy reCAPTCHA solve under run_in_executor+timeout(120) with manual-pause fallback; WAF deferred

### Phase 15: Plugin Ecosystem Registry

**Goal**: Community contributors have a discoverable registry with clear difficulty ratings, and users can inspect loaded plugins locally without a network call
**Depends on**: Phase 12
**Requirements**: REG-01, REG-02, REG-03, REG-04
**Success Criteria** (what must be TRUE):

  1. Plugin authors can declare `difficulty`, `requires_proxy`, and `requires_captcha` as class attributes on any plugin; existing plugins without these attrs continue to load with sensible defaults (non-breaking)
  2. The GitHub wiki registry table contains required fields for each community plugin: name, platform, domain patterns, maintainer, anti-detection difficulty, methods implemented, last-verified date, proxy-required, captcha-required
  3. Running `shoppybot plugins list` displays all locally loaded plugins with their declared domain patterns, difficulty, and proxy/captcha flags without making a network call
  4. CONTRIBUTING.md and the PR template require contributors to supply `difficulty`, `requires_proxy`, and `requires_captcha` for new plugin submissions

**Plans**: 3 plans

Plans:

- [x] 15-01-PLAN.md — REG-02: add difficulty/requires_proxy/requires_captcha class attrs + __init_subclass__ difficulty validation to RetailerPlugin ABC (non-breaking, PLUGIN_API_VERSION stays 2) + test_plugin_base.py assertions
- [x] 15-02-PLAN.md — REG-03: BotService.list_plugins() over registry._all_plugins + core/cli/plugins.py handler + plugins-list subparser with --json + no-network CLI tests
- [x] 15-03-PLAN.md — REG-01/REG-04: docs/PLUGIN_REGISTRY.md 9-field wiki SPEC + CONTRIBUTING.md/PR-template/PLUGIN_DEV.md attr requirements + tests/test_docs.py

### Phase 16: Price Monitoring

**Goal**: Users can track per-item prices, receive fan-out alerts when prices drop to target or by a configured percentage, and inspect price history from the CLI
**Depends on**: Phase 12
**Requirements**: PRICE-01, PRICE-02, PRICE-03, PRICE-04, PRICE-05, PRICE-06
**Success Criteria** (what must be TRUE):

  1. User can set `target_price` (absolute) and `price_drop_pct` (percentage) per item in config; NULL/absent means price monitoring is off for that item
  2. Bot records scraped prices in an append-only `price_history` SQLite table each poll cycle via an optional `get_price()` plugin ABC hook (default returns `None`); the DB migration is idempotent on existing installs
  3. Price-drop alerts are dispatched through the existing fan-out notification dispatcher using a distinct `price_drop` notification_type with dedup columns separate from stock alert columns
  4. Price alert payloads include the current price, target price, and percentage from target
  5. Running `shoppybot items price-history <name>` displays the last N recorded prices for that item

**Plans**: 4 plans

Plans:

- [x] 16-01-PLAN.md — Data layer: idempotent price_history table + 4 items columns + 8 parameterized price _sync functions + ItemConfig target_price/price_drop_pct (PRICE-01/02/05)
- [x] 16-02-PLAN.md — Plugin + notification contract: NotificationEvent price fields, default-None get_price() ABC hook, real Amazon get_price() + text→cents parser, price_drop notifier branches (PRICE-02/04)
- [x] 16-03-PLAN.md — Orchestrator wiring: _check_and_buy price path, both triggers with separate dedup, single price_drop dispatch, startup config seeding + BotService.get_price_history (PRICE-02/03/04/05)
- [x] 16-04-PLAN.md — CLI: shoppybot items price-history <name> leaf with --limit (default 10), $X.XX table, no network (PRICE-06)

**UI hint**: yes

### Phase 17: Test Hardening

**Goal**: Every new v3.0 feature has unit and integration coverage so regressions are caught by CI before they reach users
**Depends on**: Phases 13, 14, 15, 16 (tests validate the implemented features)
**Requirements**: STAB-03
**Success Criteria** (what must be TRUE):

  1. Unit tests cover proxy config parsing, ban-signal detection logic, per-instance proxy scoping, and cooldown/retire logic
  2. Unit tests cover CAPTCHA config parsing, balance-check behavior, executor wrapping, and spend-cap enforcement
  3. Unit tests cover price comparison threshold logic, `price_history` DB schema (including idempotent migration against a v2.0 DB fixture), and price-drop dedup separation from stock-alert dedup
  4. Integration tests cover the plugin ABC additions (`difficulty`, `requires_proxy`, `requires_captcha` defaults and overrides) and the `get_price()` hook being called alongside `check_availability`

**Plans**: 4 plans

Plans:

- [x] 17-01-PLAN.md — Proxy coverage: PX-01..PX-06 (config validator, fetch-handler tasks, ProxyPool edges, registry routing/lifecycle isolation)
- [x] 17-02-PLAN.md — CAPTCHA coverage: CP-01..CP-05 (poll/timeout errors, balance gate, solve_amazon_waf submit/poll/decode)
- [x] 17-03-PLAN.md — Price + get_price integration: PR-01..PR-04 + AB-01, AB-02 (v2.0-schema migration fixture, trigger guards, get_price-alongside-check_availability)
- [x] 17-04-PLAN.md — Plugin ABC: AB-03, AB-04 (metadata overrides + _handle_ban ban→proxy-cooldown bridge)

---

### Phase 18: Safety Gate + Config Foundation

**Goal**: Every plugin routes its final place-order action through an ABC-enforced gate that honors monitor-only mode, so no plugin — current or future — can place a live order when monitoring is active
**Depends on**: Nothing (do first; all downstream v4.0 phases depend on this config foundation)
**Requirements**: BUY-01, BUY-02
**Success Criteria** (what must be TRUE):

  1. User can start the bot with `--monitor-only` CLI flag or `debug.monitor_only: true` in config; bot performs stock checks and fires alerts but `auto_buy` is never called for any plugin
  2. All 7 bundled plugins route their place-order DOM click through `place_order_guarded()` on the RetailerPlugin ABC; a CI test with all 7 plugins and `monitor_only=True` asserts zero calls to the purchase write-queue
  3. BestBuy's confirmed `test_mode` gap is closed: `place_order.click()` is not called when `monitor_only=True` or `test_mode=True` on any plugin
  4. `CheckoutConfig` sub-model exists in `AppConfig` with `item_timeout_secs`, `step_timeout_secs`, `max_cart_retries`, `backoff_base`, `backoff_jitter`, and `alert_on_errors` fields so downstream phases can use them without schema changes

**Plans**: 4 plans

Plans:

**Wave 1**

- [x] 18-01-PLAN.md — DebugConfig.monitor_only + CheckoutConfig model + AppConfig wiring (BUY-01, BUY-02)
- [x] 18-02-PLAN.md — place_order_guarded() concrete method on RetailerPlugin ABC + unit tests (BUY-02)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 18-03-PLAN.md — orchestrator monitor_only gate + --monitor-only CLI flag + CVV short-circuit + ALLOWLIST (BUY-01)
- [x] 18-04-PLAN.md — reroute all 7 plugins through place_order_guarded + test_safety_gate.py (7-plugin zero-write + grep) (BUY-02)

### Phase 19: DB Schema + Confirmation Detection

**Goal**: Purchases are only recorded when the bot has verified a real order number from the retailer's confirmation page, never on a button click alone
**Depends on**: Phase 18 (monitor-only gate must be live before any live checkout UAT of confirmation selectors)
**Requirements**: BUY-03, BUY-04
**Success Criteria** (what must be TRUE):

  1. The `items` table has `order_id TEXT`, `confirmed_at TEXT`, and `checkout_attempts INTEGER DEFAULT 0` columns added via idempotent `ALTER TABLE` (same pattern as v3.0 price columns); existing DB installs migrate without data loss
  2. After `auto_buy()` returns, the orchestrator calls `detect_order_confirmation(tab, platform)` and only enqueues `("confirmed", link, order_id, ts)` to the write-queue when a non-None order_id is returned; `purchased=1` is set only at that point
  3. When confirmation is not detected, the bot logs a WARNING and falls back to the legacy `purchased` write tag (no silent failure, no double-buy risk from the confirmation path itself)
  4. Each confirmed checkout writes `order_id` and `confirmed_at` to the DB, providing the idempotency anchor for retry (Phase 21) to read before any re-attempt

**Plans**: 4 plans

Plans:

**Wave 1** *(parallel-safe; no file overlap)*

- [x] 19-01-PLAN.md — models.py: 3 idempotent confirmation columns (order_id/confirmed_at/checkout_attempts DEFAULT 0, NOT incremented) + update_item_confirmed_sync (BUY-04)
- [x] 19-02-PLAN.md — core/confirmation.py NEW: detect_order_confirmation (URL-first/DOM-backup map, ~3s settle, Amazon orderID URL-param parse, CONFIRMED-<ts> sentinel) + FakeTab tests (BUY-03)
- [x] 19-03-PLAN.md — core/plugin_base.py: additive sync get_active_tab() ABC default (returns main_tab; PLUGIN_API_VERSION stays 2) (BUY-03)

**Wave 2** *(blocked on Wave 1)*

- [x] 19-04-PLAN.md — orchestrator wiring (_try_auto_buy detect + confirmed/legacy fallback outside any timeout; _dispatch_write confirmed branch) + Amazon/BestBuy _last_tab + get_active_tab override + orchestrator tests (BUY-03, BUY-04)

**Research flag** (RESOLVED via 19-RESEARCH.md): per-retailer confirmation URL patterns (Amazon `/gp/buy/thankyou`, BestBuy `/checkout/r/thank-you`) are HIGH confidence and hardcoded in `core/confirmation.py`; backup DOM selectors (`#confirmedOrderId`, `.thank-you-order-number`) are MEDIUM confidence — live UAT on a test_mode buy is tracked as UAT debt (STATE.md Deferred Items).

### Phase 20: Checkout Profile + Form-Fill

**Goal**: Users can configure a shipping/billing profile that the bot fills during BestBuy and Amazon checkout, with payment using the retailer-saved method plus CVV entered at runtime and no full card data persisted anywhere
**Depends on**: Phase 18 (monitor-only gate required before any form-fill can be tested live); Phase 19 (confirmation detection should precede form-fill so a completed form-fill can be confirmed)
**Requirements**: BUY-07
**Success Criteria** (what must be TRUE):

  1. User can run `shoppybot setup checkout-profile` to interactively populate 9 address keys (`CHECKOUT_FIRST_NAME`, `CHECKOUT_LAST_NAME`, `CHECKOUT_ADDRESS_LINE1`, `CHECKOUT_ADDRESS_LINE2`, `CHECKOUT_CITY`, `CHECKOUT_STATE`, `CHECKOUT_ZIP`, `CHECKOUT_COUNTRY`, `CHECKOUT_PHONE`) in the CredentialStore; no card number or CVV is stored
  2. BestBuy and Amazon plugins fill the shipping form fields from the `CheckoutProfile` loaded at plugin setup time; CVV is provided via `getpass` at runtime only
  3. A CI grep assertion confirms no `_cvv` value appears in any `writeLog()` call argument on checkout code paths
  4. If a shipping form field selector returns None (DOM drift), the plugin logs a WARNING with the selector name and returns False without submitting an incomplete form

**Plans**: 4 plans

Plans:

**Wave 1** *(parallel-safe; no file overlap)*

- [x] 20-01-PLAN.md — core/checkout_profile.py: CHECKOUT_PROFILE_KEYS (9, NOT in SECRET_KEYS) + CheckoutProfile model + load_checkout_profile() incomplete detection + tests (BUY-07)
- [x] 20-02-PLAN.md — `setup checkout-profile` CLI: visible-prompt 9 keys, key-NAME-only output, optional ADDRESS_LINE2, no card/CVV stored (BUY-07)
- [x] 20-03-PLAN.md — CVV threading: Amazon __init__ _cvv=None + orchestrator amz injection (mirrors BestBuy 411-414) + run.py needs_cvv includes amazon.com (BUY-07)

**Wave 2** *(blocked on 20-01 + 20-03)*

- [x] 20-04-PLAN.md — Form-fill: _checkout_profile load at setup() + _fill_field + BestBuy shipping fill before place_order_guarded (missing-selector WARN+False) + Amazon CVV skip-if-absent + CVV-not-in-logs AST test (BUY-07)

### Phase 21: Per-Step Timeouts + Unified Retry + Cart-Retry

**Goal**: Checkout attempts are bounded in time and retries, and all retry/backoff logic flows through one shared `RetryPolicy` so supervisor restarts and cart retries cannot compound into a runaway loop
**Depends on**: Phase 18 (CheckoutConfig fields), Phase 19 (DB `order_id` idempotency anchor must exist before retry reads it)
**Requirements**: BUY-05, BUY-06, REL-08
**Success Criteria** (what must be TRUE):

  1. `core/retry.py` contains a single `RetryPolicy` dataclass and `with_retry()` async helper; both supervisor restart (Phase 22) and cart-retry use this module; a CI grep assertion confirms no standalone `for attempt in range(N)` retry loops exist outside `core/retry.py`
  2. Each checkout DOM step (navigate, add-to-cart, checkout-proceed, CVV entry, place-order click, confirmation wait) runs under its own `asyncio.timeout(step_timeout_secs)` context manager; the entire `auto_buy()` method is NOT wrapped in a single outer timeout
  3. A `checkout_stage` variable tracks progress within `auto_buy()`; on `CancelledError` the stage is logged for post-mortem and the item is not immediately re-submitted
  4. Cart-retry reads the DB `order_id` column before each attempt; if a prior attempt already wrote a confirmed order, the retry loop exits immediately without re-submitting
  5. Cart-retry is bounded by `CheckoutConfig.max_cart_retries` (default 3) with exponential backoff; the retry never re-enters the place-order click stage on an already-attempted order

**Plans**: 4 plans

Plans:

**Wave 1** *(parallel-safe; no file overlap)*

- [x] 21-01-PLAN.md — core/retry.py NEW: RetryPolicy dataclass + pure compute_delay (seedable jitter) + with_retry async helper; tests/test_no_retry_loops.py AST guard (no `for attempt in range(` outside core/retry.py) (REL-08)
- [x] 21-02-PLAN.md — models.py: increment_checkout_attempts_sync (+1 per call) + get_item_order_state_sync (purchased, order_id idempotency anchor); no schema change (BUY-05)
- [ ] 21-03-PLAN.md — per-step asyncio.timeout: self._checkout_stage default on RetailerPlugin ABC + 6 Amazon / 8 BestBuy DOM stages each under their own asyncio.timeout(step_timeout_secs); no outer timeout; per-item ceiling deferred to P22 (BUY-06)

**Wave 2** *(blocked on 21-01 + 21-02 + 21-03)*

- [ ] 21-04-PLAN.md — orchestrator cart-retry: extract _attempt_buy(plugin, link)->(bool, str|None) + with_retry/RetryPolicy from CheckoutConfig; DB re-read + checkout_attempts increment before each attempt; confirmed order_id short-circuit (no double-buy); single enqueue outside loop (BUY-05, REL-08)

**Research flag** (RESOLVED via 21-CONTEXT.md + 21-RESEARCH.md): the `checkout_attempts` increment strategy is resolved — increment once per retry ATTEMPT, BEFORE each attempt (not per-cart-add, not confirmed-only). max_cart_retries semantics documented: it is the number of RETRIES after the first attempt, so total attempts = 1 + max_cart_retries (max_cart_retries=0 → single attempt, no retry).

### Phase 22: Supervisor + Browser Relaunch + Server Safety

**Goal**: A single plugin crash or browser death cannot take down the rest of the bot; plugins restart automatically with backoff and full stealth/proxy/login restoration; the bot shuts down cleanly on SIGTERM
**Depends on**: Phase 18 (CheckoutConfig for alert_on_errors), Phase 21 (RetryPolicy from core/retry.py; supervisor reuses it)
**Requirements**: REL-01, REL-02, REL-03, REL-05, REL-06, SRV-02
**Success Criteria** (what must be TRUE):

  1. An unhandled exception in one plugin's `run_plugin` coroutine is absorbed by the supervisor before the `asyncio.TaskGroup` boundary; all other plugin coroutines keep running (verified by a test that crashes one plugin and asserts others continue)
  2. A plugin that exceeds N failures within a time window is parked (no further restart attempts) and the operator receives a notification through the existing dispatcher
  3. On a dead or disconnected Chrome process, the supervisor calls `plugin.relaunch()` which executes the full sequence: teardown, assign_proxy, setup (new browser + stealth + proxy auth), restore_session (no-op stub until Phase 23), login; `apply_stealth` is verified called on the relaunched browser
  4. Transient `sqlite3.OperationalError` (locked DB) on any `run_in_executor` read path in `run_plugin` is caught and isolated: the poll cycle is skipped, not terminated
  5. Each item's check/buy cycle runs under `asyncio.timeout(item_timeout_secs)`; the `write_queue.put()` calls are placed OUTSIDE the timeout context so a timed-out item cannot orphan a pending DB write
  6. SIGTERM and SIGINT trigger cooperative teardown (write-queue flush + browser teardown) via a platform-appropriate signal bridge (`sys.platform` branch handles Windows `NotImplementedError` on `loop.add_signal_handler`)

**Plans**: TBD
**Research flag**: NEEDS PLAN-PHASE RESEARCH — nodriver relaunch sequence interaction with CDP stealth script state should be validated against installed 0.50.3 before finalizing `plugin.relaunch()`. Specifically: whether `add_script_to_evaluate_on_new_document` persists across a `Browser.stop()` + restart or must be re-injected.

### Phase 23: Encrypted Session Persistence

**Goal**: Users can opt into encrypted cookie persistence so the bot skips re-login and MFA across restarts without storing any auth material in plaintext
**Depends on**: Phase 22 (supervisor calls `restore_session` on relaunch; Phase 22 ships a no-op stub that this phase replaces)
**Requirements**: REL-04
**Success Criteria** (what must be TRUE):

  1. When `platforms.<name>.session_persistence: true`, cookies are saved after successful login via `core/session_store.py` using Fernet encryption (same scrypt KDF as `EncryptedFileBackend`); no plaintext `.json` or `.pickle` file is written to disk
  2. On bot restart or plugin relaunch, cookies are restored via raw CDP `cdp.storage.set_cookies()` (bypassing the confirmed `CookieJar.set_all()` bug); the restore path returns `True` if a session file existed, `False` otherwise (no crash if file is absent)
  3. The `data/sessions/` directory is in `.gitignore`; a CI check confirms no session file pattern matches are committed
  4. The Phase 22 no-op `restore_session` stub in `plugin.relaunch()` is replaced by the live `SessionStore.restore()` call

**Plans**: TBD
**Research flag**: NEEDS PLAN-PHASE RESEARCH — `nodriver cdp.storage.set_cookies()` exact import path and `CookieParam` constructor signature should be verified against the installed `nodriver==0.50.3` package before implementing the restore path. The workaround is confirmed from issues #1816/#2020 but the exact API shape needs local verification.

### Phase 24: Health Surface + Server Safety

**Goal**: Operators can query per-plugin liveness and error state from the CLI or web UI, receive alerts when a plugin degrades, and run the bot headlessly on a server without a pygame import crash
**Depends on**: Phases 22 and 23 (health surface reads from supervisor + session state; SRV-01 is self-contained but grouped here as a low-dependency finish item)
**Requirements**: REL-07, SRV-01
**Success Criteria** (what must be TRUE):

  1. `BotService.get_status()` returns a structured dict including `{"running": bool, "uptime_secs": float, "plugins": {name: {"status": str, "last_heartbeat": float, "consecutive_errors": int, "items_checked": int, "orders_confirmed": int}}}` queryable from CLI (`shoppybot status`) and the FastAPI `/status` endpoint
  2. When a plugin's `consecutive_errors` exceeds the configured `alert_on_errors` threshold, a `health_degraded` event is dispatched through the existing notification fan-out channels
  3. On a headless host with no audio device, the sound notifier degrades to a silent no-op at import time rather than crashing; the bot starts and runs normally without pygame

**Plans**: TBD
**UI hint**: yes

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Foundations + Security | v1 | 5/5 | Complete | 2026-06-02 |
| 2. Plugin Migration | v1 | 6/6 | Complete | 2026-06-03 |
| 3. Community Documentation | v1 | 2/2 | Complete | 2026-06-03 |
| 4. Async Orchestrator | v1 | 5/5 | Complete | 2026-06-03 |
| 5. Notification System | v1 | 5/5 | Complete | 2026-06-03 |
| 6. Platform Expansion | v1 | 5/5 | Complete | 2026-06-03 |
| 7. Modular Core Service | v2.0 | 3/3 | Complete | 2026-06-04 |
| 8. Credential Store | v2.0 | 4/4 | Complete | 2026-06-04 |
| 9. CLI Front-End | v2.0 | 4/4 | Complete | 2026-06-04 |
| 10. Optional Web UI | v2.0 | 4/4 | Complete | 2026-06-04 |
| 11. Cross-Platform Verification | v2.0 | 5/5 | Complete | 2026-06-05 |
| 12. Stability Foundation | v3.0 | 4/4 | Complete | 2026-06-09 |
| 13. Anti-Detection Layer 1 — Fingerprint + Proxy | v3.0 | 3/3 | Complete | 2026-06-09 |
| 14. Anti-Detection Layer 2 — CAPTCHA Solving | v3.0 | 3/3 | Complete | 2026-06-09 |
| 15. Plugin Ecosystem Registry | v3.0 | 3/3 | Complete | 2026-06-09 |
| 16. Price Monitoring | v3.0 | 4/4 | Complete | 2026-06-10 |
| 17. Test Hardening | v3.0 | 4/4 | Complete | 2026-06-10 |
| 18. Safety Gate + Config Foundation | v4.0 | 4/4 | Complete    | 2026-06-11 |
| 19. DB Schema + Confirmation Detection | v4.0 | 4/4 | Complete    | 2026-06-11 |
| 20. Checkout Profile + Form-Fill | v4.0 | 4/4 | Complete    | 2026-06-11 |
| 21. Per-Step Timeouts + Unified Retry + Cart-Retry | v4.0 | 2/4 | In Progress|  |
| 22. Supervisor + Browser Relaunch + Server Safety | v4.0 | 0/TBD | Not started | - |
| 23. Encrypted Session Persistence | v4.0 | 0/TBD | Not started | - |
| 24. Health Surface + Server Safety | v4.0 | 0/TBD | Not started | - |

All 66 v1+v2.0 requirements satisfied. v3.0: 18 requirements mapped across Phases 12-17. v4.0: 17 requirements mapped across Phases 18-24.

---

*Last updated: 2026-06-10 — v4.0 Win-the-Drop roadmap created (Phases 18-24)*
