# Phase 21: Per-Step Timeouts + Unified Retry + Cart-Retry - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Checkout attempts are bounded in time and retries, and all retry/backoff logic flows through one shared `RetryPolicy` so supervisor restarts (Phase 22) and cart retries cannot compound into a runaway loop (BUY-05, BUY-06, REL-08).

Deliverables:
1. `core/retry.py` — a single `RetryPolicy` dataclass + `with_retry()` async helper + pure `compute_delay()`; the one place backoff is defined.
2. Per-step `asyncio.timeout(step_timeout_secs)` around each checkout DOM stage + `self._checkout_stage` tracking (BUY-06).
3. Cart-retry in the orchestrator using `RetryPolicy` from `CheckoutConfig`, reading the DB `order_id`/`purchased` before each attempt (no double-buy) and bounded by `max_cart_retries` (BUY-05).
4. Resolve the P19 carry-forward: `checkout_attempts` increments once per retry attempt.

Out of scope: the supervisor itself + per-item ceiling wiring (Phase 22 owns `item_timeout_secs` and supervisor restart); browser relaunch.
</domain>

<decisions>
## Implementation Decisions

### RetryPolicy & with_retry Contract
- `core/retry.py` exposes a `@dataclass RetryPolicy(max_attempts, backoff_base, backoff_jitter)`, an `async def with_retry(fn, policy, should_retry=..., on_attempt=...)` helper, and a pure `compute_delay(attempt, policy)`.
- Backoff is exponential: `backoff_base ** attempt` plus bounded random jitter up to `backoff_jitter`. The jitter source is injectable (a passable rng / seam) so tests are deterministic.
- Phase 22's supervisor restart reuses the SAME `RetryPolicy` + `compute_delay` (it is generic: max_attempts + backoff). Cart-retry and supervisor both construct a policy from config — single source of truth (REL-08).
- A CI assertion forbids any NEW `for attempt in range(` retry loop outside `core/retry.py`. The existing poll loops (`core/captcha.py` `_MAX_POLLS`, `core/stealth.py` proxy rotation) are polls, not retries, and are explicitly EXEMPT (the assertion targets the `for attempt in range(` retry idiom, not poll loops).

### Per-Step Timeouts & checkout_stage
- Each checkout DOM stage (navigate, add-to-cart, checkout-proceed, form-fill, CVV entry, place-order click, confirmation wait) runs under its OWN `async with asyncio.timeout(step_timeout_secs)`. The whole `auto_buy()` is NOT wrapped in a single outer timeout.
- `self._checkout_stage` (string) is set before each stage; on `CancelledError`/timeout, the stage is logged for post-mortem and the item is NOT immediately re-submitted.
- The hard per-ITEM ceiling (`item_timeout_secs`) is owned by Phase 22 (its success criterion 5 wraps the per-item check/buy cycle). Phase 21 implements per-STEP timeouts + stage tracking only, to avoid duplicating the item-level timeout.
- Integration is minimal: a small `_step(stage_name, coro, timeout)` helper (or inline `async with asyncio.timeout()` per existing step) that sets `self._checkout_stage` first. No broad `auto_buy()` restructure (scope discipline).

### Cart-Retry & checkout_attempts (resolves P19 carry-forward flag)
- `checkout_attempts` increments once per retry ATTEMPT, BEFORE each attempt — an accurate attempt count for bounding and double-buy detection. (NOT per-cart-add, NOT confirmed-only.)
- Cart-retry is a retry wrapper in the orchestrator around the buy attempt, using `with_retry` + a `RetryPolicy` built from `CheckoutConfig` (`max_cart_retries`, `backoff_base`, `backoff_jitter`).
- Before EACH attempt, re-read the item's `purchased`/`order_id` from the DB; if a confirmed `order_id` already exists → exit the loop immediately and do NOT re-submit (BUY-05, no double-buy).
- Retry trigger: `auto_buy` returns False OR confirmation not detected (order_id None) → retry up to `max_cart_retries` with backoff. `auto_buy` True + confirmed order_id → success, stop. The retry never re-enters the place-order click stage on an already-confirmed order.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/config_schema.py` — `CheckoutConfig` (P18) already has `item_timeout_secs`, `step_timeout_secs`, `max_cart_retries=3` (ge=0), `backoff_base=2.0` (ge=0), `backoff_jitter=0.5` (ge=0). RetryPolicy is built from these.
- `core/orchestrator.py` — `_try_auto_buy` (the buy attempt + confirmation enqueue from P19) is where the cart-retry wrapper goes; `_check_and_buy` gates it. The DB re-read uses `get_items_sync`/a targeted read via `run_in_executor`.
- `models.py` — `checkout_attempts` column (P19, DEFAULT 0, currently never incremented); `order_id`/`confirmed_at` (P19) are the idempotency anchor. Add an increment sync helper.
- `plugins/shopbot_plugin_amazon.py` / `shopbot_plugin_bestbuy.py` — `auto_buy` DOM steps are where per-step `asyncio.timeout` + `self._checkout_stage` are applied. Existing `asyncio.timeout(120)` around captcha solve is the timeout idiom to mirror.

### Established Patterns
- `asyncio.timeout()` context managers already used for captcha solves (amazon/bestbuy ~line 117/173).
- Config-driven knobs via `CheckoutConfig`; DB writes serialized through the orchestrator write queue; DB reads via `run_in_executor`.
- Additive helpers; scope discipline (no broad refactors).

### Integration Points
- `core/retry.py` (NEW — RetryPolicy + with_retry + compute_delay).
- `core/orchestrator.py` (cart-retry wrapper around the buy attempt; DB re-read before each attempt).
- `models.py` (increment_checkout_attempts sync helper).
- `plugins/shopbot_plugin_amazon.py` + `shopbot_plugin_bestbuy.py` (per-step timeouts + `self._checkout_stage`).
- `core/plugin_base.py` (maybe a `self._checkout_stage` default attr).

</code_context>

<specifics>
## Specific Ideas

- REL-08 is the architectural keystone: `core/retry.py` is the SINGLE backoff implementation; Phase 22's supervisor MUST import it rather than rolling its own. The CI grep assertion (no `for attempt in range(` outside core/retry.py) enforces this — must be a plan task.
- The cart-retry DB re-read before each attempt is the no-double-buy guard (BUY-05); it pairs with P19's confirmed-order `order_id`. A test must prove: a prior confirmed order_id short-circuits the retry loop with zero further place-order attempts.
- Jitter must be injectable/seedable so backoff tests are deterministic (don't assert on `random` directly).

</specifics>

<deferred>
## Deferred Ideas

- Supervisor / per-coroutine supervision + browser relaunch + per-item `item_timeout_secs` ceiling + SIGTERM → Phase 22.
- Encrypted session persistence → Phase 23.
- Live checkout timing/UAT of the per-step timeouts under a real drop → UAT debt (tracked, not blocking).

</deferred>
