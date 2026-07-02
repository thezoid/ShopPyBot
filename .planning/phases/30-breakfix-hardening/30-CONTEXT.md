# Phase 30: Breakfix Hardening - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning

> **Note on decision provenance:** The operator was away during discussion. All
> implementation decisions below were made on Claude's best judgment against the
> locked ROADMAP success criteria, the v4.2 "code-actionable + CI-green, live
> proof stays operator debt" milestone rule, and a fail-safe bias appropriate to
> the one HIGH item (BF-02). They are defensible defaults, not operator-confirmed
> preferences — review and revise before `/gsd:plan-phase 30` if any differ from
> intent.

<domain>
## Phase Boundary

Three independent backend breakfixes to the checkout/anti-detection/login paths of the modular v4.1 core. No new capabilities; each fix hardens an existing flow against a known failure mode.

- **BF-02 (HIGH):** A place-order-stage timeout must not cause a placed-but-unconfirmed double-buy on retry — an idempotency latch around order placement.
- **BF-01:** Amazon AWS-WAF challenge auto-solve wired through the existing 2captcha solver, with the manual-pause fallback preserved.
- **BF-03:** Plugin login reports success only when real post-login DOM/URL signals confirm it (WR-03).

**In scope:** the code wiring + unit/integration tests with mocked externals (2captcha, timeout injection, simulated failed login).
**Out of scope (operator debt, per milestone rule):** live AWS-WAF challenge proof within the ~30s gokuProps window; live place-order-timeout double-buy edge proof; per-retailer live selector tuning for the 5 community plugins.

</domain>

<decisions>
## Implementation Decisions

### BF-02 — Double-buy idempotency latch (HIGH)

- **D-01 (latch durability): DB-persisted write-ahead marker, not an in-memory flag.** Write a "place-order attempted / in-flight" marker to SQLite **immediately before** dispatching the place-order button click, then reconcile after. Rationale: v4.0 ships browser relaunch + supervisor restart; an in-memory `self._order_submitted` flag dies on relaunch, and a relaunch mid-place-order is exactly the double-buy window. A persisted marker survives crash/relaunch and reuses the existing DB-read guard (`_pre_attempt_check` at `core/orchestrator.py:400-423` already re-reads DB state per attempt).
- **D-02 (marker mechanism): new dedicated timestamp column** (e.g. `place_order_attempted_at TEXT`) written just before the click. Do NOT overload `checkout_attempts` (that stays accounting-only) and do NOT use the confirmation sentinel `CONFIRMED-<ts>` as the key — `core/confirmation.py:26-31` explicitly bars the sentinel as an idempotency key (a payment-failure page can still hit the thankyou URL).
- **D-03 (retry semantics): once the place-order click has been dispatched, the place-order stage is non-retryable.** Extend the retry guard: `_pre_attempt_check` raises a new "possibly-placed" abort (sibling to the existing `_AlreadyConfirmed`) when the marker is set but no `order_id` is captured — so the RetryPolicy loop (`should_retry=lambda r: not r[0]`, `orchestrator.py:441`) never re-clicks place-order. Earlier stages (navigate, add-to-cart, buy-now, form-fill, CVV) remain retryable exactly as today.
- **D-04 (unconfirmed-order handling): fail-safe = miss-a-buy over risk-a-double-buy.** After the click fires (even on `TimeoutError`), run confirmation detection once. If confirmed → `update_item_confirmed_sync` as today. If NOT confirmed → leave the item in a "needs manual review / unconfirmed" state (marker set, no order_id), **alert the operator via the notifier fan-out**, and skip it on future monitoring cycles (do not silently drop, do not re-attempt place-order).
- **D-05 (reuse): no second retry concept.** Continue to use the single unified `RetryPolicy` (`core/retry.py`) — v4.0 decision holds; the latch is a guard inside the existing loop, not a new retry mechanism.

### BF-01 — Amazon WAF auto-solve wiring

- **D-06 (wiring): route the existing WAF branch to `solve_amazon_waf`.** Replace the "auto-solve deferred; falling back to manual pause" path in `plugins/shopbot_plugin_amazon.py:147-158` (`_solve_or_pause`) with a call to `CaptchaSolver.solve_amazon_waf(key, iv, context, pageurl)` using the `gokuProps` values already read by `_WAF_PROBE_JS` (amazon:59-63). Run under `run_in_executor` (solver is blocking/sync) and inject the returned voucher/token via the same injection approach as the reCAPTCHA path.
- **D-07 (attempt policy): single solve attempt, then manual pause — no solve retry.** The ~30s gokuProps freshness window makes a second solve likely to arrive stale and waste a 2captcha spend. One attempt; on any failure fall back to manual pause.
- **D-08 (fallback triggers): manual-pause fallback preserved on every non-success path** — solver disabled / no balance / spend cap reached (`can_solve()` False), solve API failure, solve timeout, token-injection failure, or missing/stale gokuProps. WAF solving must never hard-fail the item; it degrades to the existing `_wait_user_action` pause (sound + event/stdin listener, not `input()`).
- **D-09 (budget): WAF solves share the same spend cap and balance gate as reCAPTCHA** — one budget: `_solve_count` / `max_solves_per_run` and the startup balance check. No separate WAF cap.
- **D-10 (tests): mock the 2captcha call; assert both paths** — solve-success (voucher injected, no manual pause) and fallback (solver unavailable/fails → manual pause invoked). Live-challenge acceptance stays operator debt.

### BF-03 — Post-login verification

- **D-11 (scope): one shared verification mechanism applied uniformly to all 7 plugins.** Add the verification step to the ABC / a shared helper so a failed or ambiguous login can never be reported successful on any plugin (DRY + consistent safety). Do not special-case only Amazon/BestBuy.
- **D-12 (signal): generic real signal + platform-specific override.** Default success signal = post-submit URL is no longer the sign-in page **and** the login form is gone; Amazon/BestBuy (the live-tested pair) get more specific signals where known (e.g. Amazon: absence of `#ap_email` / account landing; BestBuy: redirect off `/identity/signin`). The 5 community plugins with unverified "TODO" selectors use the generic signal (their live selector tuning stays operator debt) — the mechanism still guarantees ambiguous → not-success.
- **D-13 (ambiguity): ambiguous == not-success.** If the signal cannot be positively confirmed, login is reported failed. (Directly satisfies success criterion 3.)
- **D-14 (contract): `login()` returns `bool`.** Change the ABC `login(self) -> None` (`core/plugin_base.py:172-174`) to return `True` only when a post-login signal confirms, `False` on failed/ambiguous. ABC default returns `True` (a login-less plugin is trivially "logged in") and is documented as such; every real retail plugin overrides and verifies. Keep `PLUGIN_API_VERSION = 2` (treated as an additive contract change, consistent with the v4.0 `place_order_guarded` precedent).
- **D-15 (behavior on verified-failed login): abort the buy, don't proceed to checkout, alert the operator.** In each plugin's `auto_buy`, a `False` from `login()` stops the attempt before add-to-cart/checkout and is surfaced as a non-transient failure (not an immediate retry loop; a fresh attempt is allowed on the next monitoring cycle). Also check the return at the `relaunch()` call site (`plugin_base.py:210-216`, invoked when `restore_session()` is False) so a failed re-login after relaunch is not silently treated as an authenticated session.

### Claude's Discretion (delegated to research/planning)

- Exact token/voucher injection JS for the WAF path (mirror the reCAPTCHA `_inject_token` approach) — implementation detail.
- Precise DOM selectors / URL fragments per platform for the login signal — Amazon/BestBuy verifiable now; the 5 others use the generic heuristic (selector tuning is operator debt).
- Exact name/shape of the new "possibly-placed" abort exception and the DB column name — planner's call, following existing `_AlreadyConfirmed` / `get_item_order_state_sync` patterns.
- Whether the "needs manual review" state is a new DB column vs derived (marker-set AND order_id-NULL) — planner's call; derived is preferred if it avoids a schema addition.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external ADR/spec docs exist for this phase — requirements are fully captured in ROADMAP.md success criteria + REQUIREMENTS.md and the decisions above. The authoritative references are the source touch-points below.

### Phase requirements & criteria
- `.planning/ROADMAP.md` §"Phase 30: Breakfix Hardening" — goal + 4 success criteria (the fixed scope anchor).
- `.planning/REQUIREMENTS.md` — BF-01, BF-02 (HIGH), BF-03 definitions; Out-of-Scope table (live-proof debt).
- `.planning/STATE.md` §"Sequencing Notes (v4.2)" + "Deferred Items" — BF-02 traces the v4.0 audit HIGH item (Phase 21 place-order-timeout double-buy edge); BF-01 traces `waf-auto-solve-followup`.

### BF-02 (place-order idempotency) source
- `core/orchestrator.py:344-373` `_attempt_buy`, `:400-423` `_pre_attempt_check` (the retry guard to extend), `:426-453` `_try_auto_buy` (RetryPolicy loop), `:382-397`/`:507-529` DB write path.
- `plugins/shopbot_plugin_amazon.py:460-469` place-order stage timeout-wrap + swallowed `TimeoutError` (the root-cause site).
- `core/confirmation.py:26-52,113-151` confirmation detection + the sentinel-is-not-an-idempotency-key warning.
- `core/retry.py:20-71` `RetryPolicy` / `with_retry` (reuse; do not fork).
- `models.py:38-80` items schema; `:114-158` order-state writers; `:133-145` `get_item_order_state_sync` (the guard read).

### BF-01 (WAF auto-solve) source
- `core/captcha.py:98-204` `CaptchaSolver` — `can_solve()` (:151-153), `solve_amazon_waf()` (:169-204, currently unwired), `solve_recaptcha()` (:155-167, the wired reference pattern).
- `core/config_schema.py:230-238,300` `CaptchaConfig` (enabled, `max_solves_per_run`, balance threshold).
- `plugins/shopbot_plugin_amazon.py:59-63` `_WAF_PROBE_JS` (gokuProps), `:128-195` `_solve_or_pause` (the branch to wire), `:87-105` `_wait_user_action` (fallback).
- `core/orchestrator.py:635-639,668-674` solver build/balance-check; `core/registry.py:93-100` `assign_solver`.

### BF-03 (login verification) source
- `core/plugin_base.py:172-174` `login()` ABC (contract to change to `-> bool`); `:210-216` `relaunch()` login call site; `:282-339` `save_session()` (notes verification was out of scope).
- Per-plugin `login()` methods to update: amazon `:299-364`, bestbuy `:224-253`, walmart `:118-146`, target `:120-148`, gamestop `:120-148`, newegg `:124-161`, squareenix `:121-152`.

### Tests to extend
- BF-02: `tests/test_cart_retry.py`, `test_retry.py`, `test_confirmation.py`, `test_no_retry_loops.py`, `test_orchestrator.py`, `test_models.py`.
- BF-01: `tests/test_captcha.py`, `test_captcha_plugin.py`, `test_captcha_wiring.py`, `test_captcha_config.py`.
- BF-03: `tests/test_plugin_base.py`, `test_plugin_amazon.py`, `test_plugin_bestbuy.py`, `test_plugin_{walmart,target,gamestop,newegg,squareenix}.py`, `test_relaunch.py`, `test_session_persistence.py`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`RetryPolicy` / `with_retry` (`core/retry.py`)** — the single retry source; the BF-02 latch is a guard inside this loop, not a new mechanism.
- **`_pre_attempt_check` + `_AlreadyConfirmed` (`core/orchestrator.py:400-423`)** — existing per-attempt DB-read guard; extend it with a "possibly-placed" abort for BF-02.
- **`get_item_order_state_sync` / `update_item_confirmed_sync` / `increment_checkout_attempts_sync` (`models.py`)** — order-state read/write accessors; add the place-order marker alongside.
- **`CaptchaSolver.solve_amazon_waf` (`core/captcha.py:169-204`)** — already-written AWS-WAF API contract, just unwired; `solve_recaptcha` wiring (amazon:172-184) is the injection reference pattern.
- **`_wait_user_action` + stdin/event listener (`amazon:87-105`, `orchestrator.py:599-621`)** — the manual-pause fallback to preserve for BF-01.
- **Notifier fan-out dispatcher (`notifications/`)** — the operator-alert channel for BF-02 unconfirmed orders and BF-03 failed logins.

### Established Patterns
- **A button click is not a purchase** (v4.0) — `order_id`/`confirmed_at` is the only true idempotency anchor; the BF-02 marker records *intent to click*, distinct from the confirmed anchor.
- **Blocking externals run under `run_in_executor`** — 2captcha calls are sync; keep them off the event loop (BF-01).
- **Manual-pause via event, not `input()`** — the loop signals pause completion through `captcha_event`/`otp_event`/`passkey_event` set by the stdin listener thread.
- **Additive ABC changes keep `PLUGIN_API_VERSION = 2`** (v4.0 `place_order_guarded` precedent) — BF-03's `login() -> bool` follows this.

### Integration Points
- BF-02: DB schema (`models.py`) + the guard in `orchestrator.py` retry loop + the amazon place-order timeout site.
- BF-01: `CaptchaSolver` ↔ the Amazon plugin `_solve_or_pause` WAF branch.
- BF-03: ABC `login()` contract ↔ all 7 plugin overrides ↔ `relaunch()` call site ↔ notifier.

</code_context>

<specifics>
## Specific Ideas

- **Fail-safe bias is the governing principle for BF-02:** when in doubt, miss a buy rather than risk a double-buy. This resolves every ambiguous BF-02 sub-decision.
- **The BF-02 root cause is a swallowed `TimeoutError`:** `plugins/shopbot_plugin_amazon.py:460-469` wraps the place-order click in `asyncio.timeout(...)` and the broad `except Exception` returns `False`, which the RetryPolicy reads as retryable. The latch must sit at/around the click dispatch, not only in the exception handler.
- **The scouted codebase maps (`.planning/codebase/*.md`) are STALE** (dated 2026-04-19; they describe the pre-v2.0 `main.py`/`amazon_bot.py` monolith). Ignore them for this phase; the source locations in Canonical References reflect the current v4.1 modular layout (`core/` + `plugins/`).

</specifics>

<deferred>
## Deferred Ideas

- **Live AWS-WAF auto-solve acceptance** — needs a real challenge inside the ~30s gokuProps window; tracked operator debt (out of scope per REQUIREMENTS.md).
- **Live place-order-timeout double-buy edge proof** — the idempotency guard is code-actionable now; the final live edge-close is operator debt.
- **Per-retailer live login-selector tuning** for the 5 community plugins (Walmart/Target/GameStop/NewEgg/SquareEnix) — the generic verification signal ships now; live-verified selectors remain in the ~37 community-plugin selector-TODO debt bucket.
- **Extending the persisted place-order latch to non-Amazon plugins' timeout sites** — BF-02's HIGH concern is the Amazon place-order path; if the guard is implemented at the orchestrator/DB layer it covers all plugins uniformly, but any plugin-local timeout wrapping mirroring amazon:460-469 should be audited in a later cleanup if found.

</deferred>

---

*Phase: 30-breakfix-hardening*
*Context gathered: 2026-07-02*
</content>
</invoke>
