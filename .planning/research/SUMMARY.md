# Project Research Summary

**Project:** ShopPyBot v4.0 -- Win-the-Drop (Acquisition Core + Reliability)
**Domain:** Async nodriver/asyncio retail checkout bot -- verified-purchase execution + unattended survival
**Researched:** 2026-06-10
**Confidence:** HIGH (stack, architecture, pitfalls derived from direct in-repo source reads; MEDIUM on per-retailer confirmation selectors requiring live UAT)

## Executive Summary

ShopPyBot v4.0 closes the gap between "item detected" and "verified order placed" by adding confirmed-checkout detection, idempotent retry-on-cart, a central monitor-only safety gate, and a per-coroutine supervisor to the shipped v3.0 async plugin framework. The milestone goal is "bot survives unattended overnight and produces a real order number, not just a button-click confirmation." Every v4.0 capability maps to existing pinned dependencies or Python 3.13 stdlib -- zero new runtime packages are required. Two new internal modules are anticipated (core/session_store.py, core/health.py) plus two for shared logic (core/retry.py, core/confirmation.py), and selective additions to core/orchestrator.py and core/plugin_base.py.

The most important architectural decision in v4.0 is where confirmation detection runs: it belongs in the orchestrator AFTER auto_buy() returns, not inside the plugin. This keeps the plugin scope to DOM interaction and makes the confirmation check the idempotency gate -- the purchased flag is only written when a confirmed order_id is returned. The monitor-only safety gate is equally critical: BestBuy currently has no test_mode guard at all, and five other plugins lack one too. A concrete place_order_guarded() method on the RetailerPlugin ABC enforces the gate for all 7 plugins including any future community additions, without requiring per-plugin edits to enforce the invariant.

The primary risk in v4.0 is double-buy -- placing a second order because the first succeeded but confirmation was not detected before a retry. Prevention requires three layers: URL-redirect confirmation check before any True return from auto_buy(), a 3-5 second settle delay before reading the confirmation URL, and a DB purchased flag read at the top of every retry attempt. Session/cookie persistence adds a meaningful security surface (encrypted auth tokens on disk) and must use Fernet via the existing CredentialStore machinery rather than plaintext JSON. The nodriver CookieJar.set_all() method is buggy across multiple versions; cookie restore must use raw CDP cdp.storage.set_cookies() directly.

## Key Findings

### Recommended Stack

v4.0 adds zero new runtime dependencies. All capabilities are covered by the existing pinned stack: nodriver 0.50.3 (CDP API for cookie restore, browser.stopped for crash detection), asyncio stdlib (TaskGroup, asyncio.timeout, asyncio.Event), cryptography 44.0.2 (Fernet for session encryption), pydantic 2.13.3 (CheckoutConfig and CheckoutProfile models), and the existing CredentialStore/EncryptedFileBackend pattern in core/credentials.py. The full requirements.txt is unchanged from v3.0.

**Core technologies and their v4.0 roles:**
- nodriver 0.50.3: browser.stopped property detects crash; cdp.storage.set_cookies() restores sessions (bypasses buggy CookieJar.set_all); tab.select/find for confirmation detection
- asyncio.timeout (stdlib 3.11+): per-step and per-item checkout time budgets; already used in _solve_or_pause() -- extend the pattern
- cryptography.fernet (existing): session cookie encryption in core/session_store.py; reuses same Fernet + scrypt KDF as EncryptedFileBackend
- pydantic 2.13.3 (existing): new CheckoutConfig sub-model (item_timeout_secs, step_timeout_secs, max_cart_retries, backoff_base); new CheckoutProfile dataclass
- random + asyncio.sleep (stdlib): unified RetryPolicy backoff in core/retry.py; explicit loop preferred over tenacity for this bounded stateful case
- dataclasses + time.monotonic (stdlib): HealthState / HealthRegistry in core/health.py
- signal (stdlib): SIGTERM bridge with sys.platform branch for Windows NotImplementedError on add_signal_handler

**What NOT to add:**
- tenacity/backoff: bounded 3-attempt checkout retry is a 10-line loop; decorator indirection obscures stateful relaunch logic
- aiohttp/httpx: no new HTTP calls in v4.0
- structlog: second logging system alongside writeLog() would diverge
- async-healthcheck: FastAPI already present for /health; no second HTTP server

### Expected Features

**Must have (table stakes -- P1):**
- Order-confirmation detection (Amazon + BestBuy): URL-redirect check primary, DOM order-number regex backup; orchestrator calls detect_order_confirmation() after auto_buy() returns; purchased flag only written on confirmed signal
- Monitor-only mode + close test_mode hole: --monitor-only CLI flag sets cfg.app.monitor_only; orchestrator gate prevents _try_auto_buy() from running; closes BestBuy missing test_mode guard via place_order_guarded() ABC method
- Bounded retry-on-cart + double-buy guard: max 3 cart-add attempts, max 2 place-order attempts; DB purchased flag read before EVERY attempt; 3-5 second settle delay before confirmation read; exponential backoff with jitter
- Per-step / per-item checkout time budget: asyncio.timeout() as context manager per DOM step (not wrapping entire auto_buy); checkout_stage tracking so cancellation never leaves ambiguous order state

**Should have (competitive -- P2):**
- Per-coroutine supervisor + backoff restart: coro-factory pattern (~15 lines); absorbs exceptions before TaskGroup boundary; exponential backoff with failure budget (max 5 per plugin); CancelledError always re-raised
- Browser-crash detection + relaunch: browser.stopped property check at top of run_plugin loop; full relaunch sequence (teardown, assign_proxy, setup, restore_session, login) via plugin.relaunch() ABC method
- Encrypted session/cookie persistence: core/session_store.py reusing EncryptedFileBackend pattern; save after login, restore before first navigation; opt-in per platform; raw CDP cookie restore (bypasses set_all bug)
- Checkout profile form-fill (BestBuy + Amazon first): CheckoutProfile from CredentialStore; 9 address keys, no card data; CVV remains getpass-only at runtime
- Structured health/heartbeat surface: HealthRegistry with per-plugin status + last_heartbeat; BotService.get_status() expands to return plugin health dict; health_degraded notification event
- DB read-path error isolation: try/except around get_items_sync and all other run_in_executor reads in run_plugin; write-queue drain already isolated; read path is not

**Defer to v5+:**
- Parallel multi-account checkout (CFAA risk, high detection rate)
- Amazon WAF CAPTCHA auto-solve (unreliable solve path)
- Request/API-mode checkout (arms-race maintenance burden)
- Unlimited retry loops (ban trigger on drop-day 429s)
- Full card number persistence (PCI violation)

**ToS-sensitive features (opt-in, documented):**
- Session/cookie persistence: platforms.<name>.session_persistence: true required
- Checkout profile form-fill: platforms.<name>.checkout_profile.enabled: true required

### Architecture Approach

v4.0 integrates two feature clusters into the shipped v3.0 layered architecture without structural changes. The write-queue remains the sole SQLite write path; confirmation detection adds a new "confirmed" tuple tag handled by _dispatch_write. The supervisor replaces bare tg.create_task() calls in async_main with supervised wrappers that absorb exceptions before the TaskGroup boundary, preventing one plugin crash from cancelling all siblings. The ABC gains one concrete method (place_order_guarded) that all 7 plugins call instead of direct DOM clicks, making the monitor-only gate architectural rather than convention-based.

**Major new components:**
1. core/confirmation.py: detect_order_confirmation(tab, platform) -> str | None; per-platform selector map; called from orchestrator _try_auto_buy, not from plugin; URL-redirect check primary
2. core/retry.py: RetryPolicy dataclass + with_retry() async helper; ONE unified backoff implementation shared by both supervisor restart and cart-retry paths
3. core/session_store.py: Fernet-encrypted JSON cookie save/restore; reuses EncryptedFileBackend pattern; raw CDP restore path
4. core/health.py: HealthRegistry with HealthEntry per plugin; thread-safe via threading.Lock; queryable via BotService.get_status()
5. core/supervisor.py (or inline in orchestrator): supervise(coro_factory, name, policy) async wrapper; coro-factory pattern for re-creatable coroutines on restart
6. core/plugin_base.py (modified): place_order_guarded() concrete method; plugin.relaunch() concrete method

**Modified components:**
- core/orchestrator.py: supervisor wrapping, DB read isolation, per-item asyncio.timeout, confirmation detection wiring, heartbeat updates
- core/config_schema.py: DebugConfig.monitor_only, new CheckoutConfig sub-model (5 fields)
- core/credentials.py: 9 checkout profile keys added to SECRET_KEYS
- models.py: 3 new columns (order_id, confirmed_at, checkout_attempts); new "confirmed" write-queue tag
- All 7 plugins: replace direct place_order.click() with place_order_guarded()

### Critical Pitfalls

1. **Double-buy via non-idempotent checkout retry**: Return True from auto_buy() ONLY after confirmation element detected; read DB purchased flag before EVERY retry; insert 3-5 second settle delay before confirmation URL check. Financial risk: $400-700+ duplicate order on a limited-release item cannot be undone after shipment.

2. **Monitor-only gate that fails to block all 7 plugins**: BestBuy has NO test_mode guard today; 5 others will have none when checkout is added. Use place_order_guarded() on the ABC as the single enforcement point. Add CI test: 7 plugins, monitor_only=True, assert zero auto_buy() calls.

3. **Per-step timeout orphaning a half-submitted order**: Never wrap entire auto_buy() in a single asyncio.timeout; wrap each DOM step individually; track checkout_stage so CancelledError at "placed" stage sets in_progress=True rather than leaving purchased=False for re-submission.

4. **Two divergent retry implementations**: If supervisor restart and cart-retry are implemented independently they can multiply: max_supervisor_retries x max_cart_retries = excessive attempts. Use one RetryPolicy in core/retry.py for both paths.

5. **Session cookie persistence as plaintext**: nodriver browser.cookies.save() writes a plaintext file; never use it. core/session_store.py must use the same Fernet + scrypt path as EncryptedFileBackend. CookieJar.set_all() is confirmed buggy (issues #1816, #2020, #2232) -- use raw CDP cdp.storage.set_cookies() for restore.

6. **Browser relaunch that forgets stealth, proxy, and login**: A relaunch calling only plugin.setup() without assign_proxy + apply_stealth + login hits the site without protection and triggers an instant ban-loop. The plugin.relaunch() ABC method must encode the full sequence: teardown, assign_proxy, setup, restore_session, login.

7. **DB read-path has no error handling while write-path does**: _dispatch_write is wrapped in except Exception; get_items_sync and all run_in_executor reads in run_plugin are not. A SQLite lock on read raises into the TaskGroup and kills everything. Wrap reads in try/except sqlite3.OperationalError (transient) vs sqlite3.DatabaseError (fatal, propagate after CRITICAL log).

8. **CVV in logs or CredentialStore**: Never log self._cvv; use exc.__class__.__name__ not str(exc) on checkout exception paths; never add CVV/CARD_NUMBER to SECRET_KEYS. Add CI grep assertion blocking _cvv in any writeLog argument.

## Implications for Roadmap

All four researchers converged on the same dependency-ordered build sequence. The phase structure below follows those dependencies directly.

### Phase 18: Safety Gate + Config Foundation

**Rationale:** No other v4.0 work can proceed without the monitor-only gate and the CheckoutConfig schema. This is the lowest-risk change: it adds behavior (gate), does not remove any, and closes the 6-of-7 plugin safety hole that exists today. No downstream dependencies on this phase -- everything else depends on it.

**Delivers:** DebugConfig.monitor_only field; CheckoutConfig sub-model in AppConfig; place_order_guarded() concrete method on RetailerPlugin ABC; all 7 plugins updated to call place_order_guarded(); BestBuy test_mode gap closed; --monitor-only CLI flag wired into async_main

**Addresses:** Monitor-only mode (FEATURES P1); closes BestBuy test_mode hole (PITFALLS #6)

**Avoids:** The 6-of-7 safety hole (PITFALLS #6); need to re-audit plugins on future community additions (ABC enforcement)

**Research flag:** Standard patterns -- no plan-phase research needed

### Phase 19: DB Schema + Confirmation Detection

**Rationale:** Confirmation detection is the keystone feature. It must come before retry logic because the confirmed order_id is the idempotency check that prevents double-buy on retry. The DB schema changes (order_id, confirmed_at, checkout_attempts columns; "confirmed" write-queue tag) must land before confirmation detection can persist anything.

**Delivers:** items table gains order_id, confirmed_at, checkout_attempts columns (idempotent ALTER TABLE); _dispatch_write handles "confirmed" tag; core/confirmation.py with detect_order_confirmation(tab, platform) -> str | None; orchestrator _try_auto_buy wired to call confirmation after auto_buy() returns; unconfirmed fallback logs WARNING and writes legacy "purchased" tag

**Addresses:** Order-confirmation detection (FEATURES P1); double-buy prevention (PITFALLS #1, #2)

**Avoids:** False-positive "purchased" on click-without-confirmation (PITFALLS #2); retry before confirmation gate exists (PITFALLS #1)

**Research flag:** NEEDS PLAN-PHASE RESEARCH -- per-retailer confirmation URL patterns and DOM selector IDs require live UAT. Amazon /gp/buy/thankyou and BestBuy /checkout/r/thank-you are HIGH confidence; backup DOM selectors (#confirmedOrderId, .thank-you-order-number) are MEDIUM confidence and may have drifted.

### Phase 20: Checkout Profile + Form-Fill

**Rationale:** Form-fill has no external dependencies and placing it before retry lets the retry logic re-fill forms on session-expiry retries. BestBuy first (most reliable selector history), Amazon second.

**Delivers:** 9 checkout address keys added to SECRET_KEYS; core/checkout_profile.py with CheckoutProfile dataclass and fill_shipping_form(tab) method; shoppybot setup checkout-profile CLI command; BestBuy and Amazon plugins wired for form-fill; CVV getpass-only, no card number storage

**Addresses:** Checkout profile form-fill (FEATURES P2); PCI handling (PITFALLS #4)

**Avoids:** CVV in logs or CredentialStore (PITFALLS #4)

**Research flag:** Standard patterns -- selector verification for shipping form fields needs live UAT but a missing selector fails gracefully, it does not double-buy.

### Phase 21: Per-Step Timeouts + Unified Retry + Cart-Retry

**Rationale:** Timeouts and retry must be built together to avoid the "two divergent retry implementations" pitfall. Building core/retry.py first and wiring both supervisor restart (Phase 22) and cart-retry (this phase) to the same RetryPolicy prevents the multiplicative retry problem.

**Delivers:** core/retry.py with RetryPolicy dataclass and with_retry() async helper; per-step asyncio.timeout() context managers in auto_buy() (not wrapping entire method); checkout_stage tracking variable in auto_buy(); orchestrator _try_auto_buy replaced with _try_auto_buy_with_retry using RetryPolicy(max_attempts=3); idempotency guard reads purchased flag before each retry attempt

**Addresses:** Bounded retry-on-cart (FEATURES P1); per-step time budget (FEATURES P1)

**Avoids:** Half-submitted order on timeout (PITFALLS #5); two divergent retry implementations (PITFALLS #12); double-buy on retry (PITFALLS #1)

**Research flag:** Standard patterns -- asyncio.timeout and RetryPolicy are well-documented stdlib patterns. No plan-phase research needed.

### Phase 22: Supervisor + Browser Relaunch

**Rationale:** Supervisor can be built with a stub restore_session (no-op if no session file exists) and wired properly once session_store ships in Phase 23. DB read isolation and per-item timeout belong here because they protect the same poll loop the supervisor protects.

**Delivers:** core/supervisor.py (supervise(coro_factory, name, policy) async wrapper; coro-factory pattern; CancelledError always re-raised; failure budget + backoff); plugin.relaunch() concrete ABC method (full sequence: teardown, assign_proxy, setup, restore_session stub, login); bare tg.create_task() replaced with supervised wrappers in orchestrator; DB read isolation (try/except around all run_in_executor reads); per-item asyncio.timeout wrapping check_availability + auto_buy portion of _check_and_buy (write_queue.put calls OUTSIDE timeout context); SIGTERM bridge with sys.platform branch for Windows

**Addresses:** Per-coroutine supervision (FEATURES P2); browser-crash detection + relaunch (FEATURES P2); DB read-path isolation (FEATURES P2)

**Avoids:** TaskGroup tear-down on single plugin crash (PITFALLS #7); relaunch forgetting stealth/proxy/login (PITFALLS #8); timeout cancelling mid-DB-write (PITFALLS #10); Windows NotImplementedError on add_signal_handler

**Research flag:** NEEDS PLAN-PHASE RESEARCH -- nodriver relaunch sequence interaction with CDP stealth script state should be validated against installed 0.50.3 before finalizing plugin.relaunch() implementation.

### Phase 23: Encrypted Session Persistence

**Rationale:** Session persistence is last in the reliability cluster because the supervisor (Phase 22) calls restore_session on relaunch. Phase 22 ships a no-op stub; Phase 23 replaces it. This avoids circular dependency.

**Delivers:** core/session_store.py (~60 lines); reuses EncryptedFileBackend Fernet + scrypt KDF; atomic write via mkstemp + os.replace; save after successful login; restore before first navigation (replaces stub from Phase 22); raw CDP cdp.storage.set_cookies() for restore (bypasses buggy CookieJar.set_all()); data/sessions/ added to .gitignore; opt-in per platform

**Addresses:** Encrypted session/cookie persistence (FEATURES P2)

**Avoids:** Plaintext auth tokens on disk (PITFALLS #9); nodriver set_all() bug; git history leaking session files

**Research flag:** NEEDS PLAN-PHASE RESEARCH -- nodriver cdp.storage.set_cookies() argument shape and CookieParam constructor should be verified against installed 0.50.3 before implementation.

### Phase 24: Health Surface

**Rationale:** Health is the final phase because it reads from all other systems (supervisor status, confirmation counts, DB state). Nothing else depends on it. It is the observability layer, not a functional prerequisite.

**Delivers:** core/health.py with HealthRegistry and HealthEntry (status, last_heartbeat, consecutive_errors, items_checked, orders_confirmed); BotService.get_status() expanded to return plugin health dict + uptime_secs; health_degraded notification event type added to dispatcher; FastAPI /status endpoint updated; optional .shopbot_health.json write (opt-in)

**Addresses:** Structured health/heartbeat surface (FEATURES P2)

**Avoids:** Silent stalls on unattended overnight runs; degraded plugin going undetected

**Research flag:** Standard patterns -- dataclasses, threading.Lock, FastAPI route addition are all standard. No plan-phase research needed.

### Phase Ordering Rationale

The dependency chain is clear and all four researchers converged on the same sequence:

- Safety gate first: monitor_only is a prerequisite for trustworthy UAT of every subsequent phase. Any live testing of checkout features without it risks a real order.
- Confirmation before retry: cart-retry idempotency guard reads the order_id column, which confirmation detection writes. Retry without confirmation first has no idempotency anchor.
- Retry before supervisor: the supervisor uses RetryPolicy from core/retry.py. Building supervisor without the shared retry module first recreates the two-divergent-implementations problem.
- Session persistence after supervisor shell: the relaunch path calls restore_session; Phase 22 ships a no-op stub replaced in Phase 23. Avoids circular dependency.
- Health last: purely additive observability; no functional feature depends on it.

### Research Flags

Needs plan-phase research (--research-phase flag during planning):
- Phase 19: per-retailer confirmation selectors require live UAT before hardcoding in core/confirmation.py
- Phase 22: nodriver relaunch sequence interaction with CDP stealth state needs validation against installed 0.50.3
- Phase 23: cdp.storage.set_cookies() argument shape and CookieParam constructor need verification against installed 0.50.3

Standard patterns (skip plan-phase research):
- Phase 18: ABC concrete method, Pydantic bool field, CLI flag wiring
- Phase 20: CredentialStore key addition, Pydantic dataclass, form-fill via send_keys (same as existing login)
- Phase 21: asyncio.timeout context manager, RetryPolicy dataclass
- Phase 24: dataclasses, threading.Lock, FastAPI route

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All v4.0 features mapped to existing pinned deps or stdlib; verified from nodriver source and in-repo code reads; zero new packages confirmed |
| Features | HIGH | P1/P2/defer split derived from direct analysis of existing code gaps; feature dependencies traced through existing call graph |
| Architecture | HIGH | All integration points from direct source reads of orchestrator.py, plugin_base.py, credentials.py, models.py; no inference from training data |
| Pitfalls | HIGH (acquisition) / MEDIUM (browser relaunch) | Double-buy, PCI, asyncio cancellation pitfalls traceable to existing code; nodriver relaunch inferred from CDP behavior + Phase 13 ship experience |

**Overall confidence:** HIGH with three targeted LOW-confidence open questions requiring live validation

### Gaps to Address (Open Questions for Plan-Phase)

These three items are explicitly LOW confidence and must be validated during plan-phase:

1. **Per-retailer confirmation selectors (Phase 19):** URL-redirect signal is HIGH confidence. Backup DOM selectors (#confirmedOrderId, #widget-purchaseConfirmationStatus for Amazon; .thank-you-order-number, [data-testid="order-number"] for BestBuy) are MEDIUM confidence. Must be verified via live UAT (test_mode buy on a low-cost item) before hardcoding in core/confirmation.py.

2. **nodriver cookie CDP API against installed 0.50.3 (Phase 23):** The cdp.storage.set_cookies() workaround is confirmed from issues #1816/#2020 but the exact import path and CookieParam constructor signature should be verified against the installed package before committing the implementation.

3. **checkout_attempts increment strategy (Phases 19/21):** The schema adds checkout_attempts INTEGER DEFAULT 0, but the research files do not fully resolve when to increment it (on every auto_buy() call? on every cart-add attempt? only on confirmed orders?). This needs an explicit decision in Phase 21 planning to avoid ambiguous semantics that could mislead double-buy detection.

## Sources

### Primary (HIGH confidence -- direct source reads)
- core/orchestrator.py: existing TaskGroup structure, _try_auto_buy, write-queue drain, asyncio.timeout usage confirmed
- core/plugin_base.py: RetailerPlugin ABC contract, setup/teardown, existing method signatures
- core/credentials.py: EncryptedFileBackend Fernet + scrypt KDF pattern, SECRET_KEYS list, _resolve_passphrase()
- core/stealth.py: apply_stealth, ProxyPool, setup_proxy_auth; confirmed from nodriver import cdp import
- plugins/shopbot_plugin_amazon.py: test_mode check pattern (lines 391-428); place-order without confirmation
- plugins/shopbot_plugin_bestbuy.py: missing test_mode guard confirmed (lines 303-309)
- models.py: existing schema, WAL mode, PRAGMA table_info idempotent ALTER pattern
- nodriver source nodriver/core/browser.py: browser.stopped property, _process_pid (verified 2026-06-10)
- Python 3.13 stdlib docs: asyncio.timeout, TaskGroup exception propagation, signal module Windows limitations

### Secondary (MEDIUM confidence -- verified PyPI/GitHub, community sources)
- nodriver CookieJar.set_all() bug: issues #1816, #2020, #2232 confirmed; cdp.storage.set_cookies workaround confirmed working
- Amazon confirmation URL /gp/buy/thankyou/handlers: documented in community bot references; HIGH for URL, MEDIUM for DOM selector IDs
- BestBuy confirmation URL /checkout/r/thank-you: Refract bot docs confirm; DOM selector .thank-you-order-number confirmed by ScrapingBee article
- Asyncio supervisor coro-factory pattern: Python docs (coroutine cannot be re-awaited after consumption)

### Tertiary (LOW confidence -- needs live validation)
- Amazon DOM confirmation selectors (#widget-purchaseConfirmationStatus, #orderConfirmations, #confirmedOrderId): may have drifted; require live UAT
- BestBuy DOM confirmation selectors (.thank-you-enhancement__order-number, [data-testid="order-number"]): same caveat
- nodriver cdp.storage.set_cookies() exact argument shape against installed 0.50.3: verify against installed package before Phase 23

---
*Research completed: 2026-06-10*
*Ready for roadmap: yes*
