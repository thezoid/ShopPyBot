# Phase 21: Per-Step Timeouts + Unified Retry + Cart-Retry — Research

**Researched:** 2026-06-11
**Domain:** Python asyncio retry/backoff, DOM checkout automation, SQLite idempotency
**Confidence:** HIGH (all findings verified from in-repo source; no external packages required)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- `core/retry.py` exposes `@dataclass RetryPolicy(max_attempts, backoff_base, backoff_jitter)`, `async def with_retry(fn, policy, should_retry=..., on_attempt=...)`, and pure `compute_delay(attempt, policy)`.
- Backoff: `backoff_base ** attempt` plus bounded random jitter up to `backoff_jitter`. Jitter source is injectable (passable rng seam) so tests are deterministic.
- Phase 22 supervisor reuses the SAME `RetryPolicy` + `compute_delay` — single source of truth (REL-08).
- CI assertion forbids any NEW `for attempt in range(` retry loop outside `core/retry.py`. Existing poll loops (`core/captcha.py` `_MAX_POLLS`, `core/stealth.py` proxy rotation) are EXEMPT.
- Each checkout DOM stage runs under its OWN `async with asyncio.timeout(step_timeout_secs)`. `auto_buy()` is NOT wrapped in a single outer timeout.
- `self._checkout_stage` (string) set before each stage; on `CancelledError`/timeout, stage is logged and item is NOT immediately re-submitted.
- Per-item ceiling (`item_timeout_secs`) owned by Phase 22.
- `checkout_attempts` increments once per retry attempt, BEFORE each attempt.
- Cart-retry is a wrapper in the orchestrator around the buy attempt, using `with_retry` + `RetryPolicy` built from `CheckoutConfig` (`max_cart_retries`, `backoff_base`, `backoff_jitter`).
- Before EACH attempt, re-read `purchased`/`order_id` from DB; confirmed `order_id` exits immediately (BUY-05).
- Retry trigger: `auto_buy` returns False OR `order_id` None after confirmation detection.

### Claude's Discretion

- `_step(stage_name, coro, timeout)` helper or inline `async with asyncio.timeout()` per step — planner chooses the minimal approach.
- Targeted `get_item_order_state_sync(link)` read helper vs. filtering `get_items_sync()` — planner picks based on simplicity.
- Exact grep/AST assertion shape for the CI no-retry-loop check.

### Deferred Ideas (OUT OF SCOPE)

- Supervisor / per-coroutine supervision + browser relaunch + per-item `item_timeout_secs` ceiling — Phase 22.
- Encrypted session persistence — Phase 23.
- Live checkout timing/UAT of per-step timeouts — UAT debt.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUY-05 | Cart-retry up to configurable max with backoff; re-reads DB state before each attempt; no double-buy on succeeded-but-misdetected order | `CheckoutConfig.max_cart_retries/backoff_base/backoff_jitter` exist; `order_id` column is the idempotency anchor; `_try_auto_buy` is the wrap point in orchestrator |
| BUY-06 | Per-step time budget with checkout-stage tracking; clean abort on slow step | `asyncio.timeout()` already used at lines 173/117 in both plugins; `_checkout_stage` attr on plugin instance; `CancelledError` propagation documented |
| REL-08 | Supervisor restart and cart-retry share one `RetryPolicy`; backoff defined in single place | `core/retry.py` does not yet exist; Phase 22 is the supervisor consumer; `CheckoutConfig` already has all needed fields |
</phase_requirements>

## Summary

Phase 21 introduces three coordinated changes. First, `core/retry.py` becomes the single home for exponential backoff — a pure dataclass + async helper + deterministic delay calculator. Second, each DOM stage in `auto_buy()` for both Amazon and BestBuy gets wrapped in its own `asyncio.timeout(step_timeout_secs)` with a `self._checkout_stage` string updated before each stage so aborted checkouts leave a breadcrumb. Third, the orchestrator's `_try_auto_buy` is wrapped in a cart-retry loop that re-reads `purchased`/`order_id` from the DB before each attempt, using `RetryPolicy` built from the already-present `CheckoutConfig` fields.

All required config knobs (`step_timeout_secs`, `max_cart_retries`, `backoff_base`, `backoff_jitter`) exist in `core/config_schema.py:CheckoutConfig` with correct bounds. The DB already has `checkout_attempts`, `order_id`, and `confirmed_at` columns from Phase 19, but no increment helper exists yet. The existing `asyncio.timeout(120)` captcha solve idiom in both plugins (amazon line 173, bestbuy line 117) is the exact pattern to mirror for per-step timeouts — including the WR-01 caveat that it cancels the await but not any executor thread.

The CI assertion is scoped to the `for attempt in range(` idiom (not `for _ in range(`). The captcha `_MAX_POLLS` loop uses `for _ in range(_MAX_POLLS)` (line 59 of `core/captcha.py`) and the proxy advance loop uses `for _ in range(len(self._entries))` (line 244 of `core/stealth.py`) — both are exempt because they use `_` not `attempt` as the loop variable. The grep/AST assertion can target the literal identifier `attempt` inside a `for` statement's target.

**Primary recommendation:** Add `core/retry.py` (3 exports), add `increment_checkout_attempts_sync` + `get_item_order_state_sync` to `models.py`, wrap `_try_auto_buy` in orchestrator with `with_retry`, add `self._checkout_stage = ""` default to `plugin_base.py`, inline `async with asyncio.timeout(step_timeout_secs)` per DOM stage in both plugins.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Backoff delay math | Core utility (retry.py) | None | Pure function; must be testable without browser or DB |
| Retry loop execution | Orchestrator | None | Orchestrator owns the buy-attempt lifecycle; plugins return True/False only |
| Per-step timeout enforcement | Plugin (auto_buy) | None | DOM stage structure lives in each plugin's auto_buy method |
| Checkout stage tracking | Plugin (self._checkout_stage) | Orchestrator (reads on error) | Plugin sets it; orchestrator logs it on CancelledError |
| Idempotency anchor read | Models (get_item_order_state_sync) | Orchestrator (calls it) | DB read belongs in models.py; orchestrator calls via run_in_executor |
| attempt counter increment | Models (increment_checkout_attempts_sync) | Orchestrator (calls it) | Same pattern as all other DB writes in the project |

## Standard Stack

No new packages. All implementation uses:

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| asyncio (stdlib) | 3.11+ | `asyncio.timeout()`, `asyncio.sleep()`, `CancelledError` | Already used; `asyncio.timeout` is Python 3.11+ stdlib |
| dataclasses (stdlib) | 3.7+ | `@dataclass RetryPolicy` | Already used in `core/stealth.py` |
| random (stdlib) | stdlib | Jitter RNG with injectable seam | Already used in orchestrator (`random.uniform`) |
| sqlite3 (stdlib) | stdlib | `increment_checkout_attempts_sync` + `get_item_order_state_sync` | Established pattern in `models.py` |

[VERIFIED: codebase grep] All imports above are already present in this codebase.

**Installation:** No new dependencies.

## Package Legitimacy Audit

No external packages added in this phase. Section not applicable.

## Architecture Patterns

### System Architecture Diagram

```
orchestrator._check_and_buy
  |
  v
orchestrator._cart_retry_wrapper (NEW)     <--- with_retry(fn, RetryPolicy)
  |                                              reads DB order_id before each attempt
  |-- attempt N:
  |     increment_checkout_attempts_sync(link)    <--- models.py (NEW)
  |     get_item_order_state_sync(link)            <--- models.py (NEW)
  |     if order_id already confirmed: EXIT
  |     _try_auto_buy(plugin, name, link, ...)     <--- existing
  |          |
  |          v
  |        plugin.auto_buy(link)
  |             |
  |             Stage 1: self._checkout_stage = "navigate"
  |             async with asyncio.timeout(step_timeout_secs): tab = driver.get(url)
  |             Stage 2: self._checkout_stage = "add-to-cart"
  |             async with asyncio.timeout(step_timeout_secs): [add to cart click]
  |             Stage 3: ...
  |             CancelledError -> log self._checkout_stage, propagate
  |
  |-- backoff: compute_delay(attempt, policy) + asyncio.sleep
  |
  v
confirmation stays OUTSIDE retry loop (P19 unchanged)
write_queue.put() stays OUTSIDE retry loop
```

### Recommended Project Structure

```
core/
  retry.py          # NEW: RetryPolicy, with_retry, compute_delay
models.py           # ADD: increment_checkout_attempts_sync, get_item_order_state_sync
core/orchestrator.py  # MODIFY: _cart_retry_wrapper around _try_auto_buy
core/plugin_base.py  # MODIFY: self._checkout_stage = "" default in __init__
plugins/shopbot_plugin_amazon.py   # MODIFY: per-stage timeout + _checkout_stage
plugins/shopbot_plugin_bestbuy.py  # MODIFY: per-stage timeout + _checkout_stage
tests/
  test_retry.py     # NEW: RetryPolicy compute_delay, with_retry, CI grep assertion
  test_cart_retry.py  # NEW: idempotency guard, attempt increment
```

### Pattern 1: RetryPolicy Dataclass + compute_delay

**What:** Pure dataclass holding retry parameters; `compute_delay` is a free function so it is testable without instantiating the async helper. Jitter is injectable to allow seeded-rng tests.

**When to use:** Anywhere a loop needs bounded exponential backoff.

```python
# [ASSUMED] illustrative — exact implementation for planner
import random
from dataclasses import dataclass

@dataclass
class RetryPolicy:
    max_attempts: int
    backoff_base: float
    backoff_jitter: float

def compute_delay(attempt: int, policy: RetryPolicy, rng=random) -> float:
    """Return delay for attempt N (0-indexed). Deterministic when rng is seeded."""
    base = policy.backoff_base ** attempt
    jitter = rng.uniform(0, policy.backoff_jitter)
    return base + jitter
```

Key points:
- `attempt` is 0-indexed so attempt 0 gives `backoff_base**0 = 1.0` (one second base for default `backoff_base=2.0`).
- `rng` defaults to `random` module; tests pass `random.Random(42)` for determinism.
- `compute_delay` is a module-level function, not a method, so Phase 22 supervisor can import it directly.

### Pattern 2: with_retry Async Helper

**What:** Drives the retry loop; calls `on_attempt(attempt_number)` before each attempt (used to increment `checkout_attempts`); calls `should_retry(result)` to decide if a retry is warranted.

```python
# [ASSUMED] illustrative
import asyncio

async def with_retry(fn, policy: RetryPolicy, should_retry=None, on_attempt=None, rng=random):
    """Call fn() up to policy.max_attempts times with exponential backoff."""
    for attempt in range(policy.max_attempts):
        if on_attempt is not None:
            await on_attempt(attempt)
        result = await fn()
        if should_retry is None or not should_retry(result):
            return result
        if attempt < policy.max_attempts - 1:
            delay = compute_delay(attempt, policy, rng)
            await asyncio.sleep(delay)
    return result
```

Note: `asyncio.sleep` is cancel-safe — if the enclosing task is cancelled during the sleep, `CancelledError` propagates cleanly. No special handling needed.

### Pattern 3: asyncio.timeout Per DOM Step (mirroring existing captcha idiom)

**What:** Inline `async with asyncio.timeout(step_timeout_secs)` around each DOM interaction. Set `self._checkout_stage` BEFORE the context manager so the stage is readable even if the timeout fires.

**Existing model:** `plugins/shopbot_plugin_amazon.py` lines 171-183 and `plugins/shopbot_plugin_bestbuy.py` lines 115-125.

```python
# [ASSUMED] illustrative — mirrors existing captcha pattern
self._checkout_stage = "navigate"
async with asyncio.timeout(step_timeout_secs):
    tab = await self.driver.get(url)

self._checkout_stage = "add-to-cart"
async with asyncio.timeout(step_timeout_secs):
    btn = await tab.select(".add-to-cart-button", timeout=10)
    if not btn:
        return False
    await btn.click()
```

WR-01 caveat applies only to `run_in_executor` calls inside a timeout block: `asyncio.timeout` cancels the `await` (the future) but the thread continues running in the executor. For pure nodriver tab operations (no executor), cancellation is clean. See Pattern 4 below.

### Pattern 4: WR-01 — Executor Calls Inside Timeout

**What:** The existing `asyncio.timeout(120)` wraps `await loop.run_in_executor(None, solver.solve_recaptcha, ...)`. When the timeout fires, the `await` is cancelled but the executor thread keeps running until its blocking call returns (up to `_POLL_INTERVAL_SECS + requests_timeout = 5+10 = 15s` past the gate).

**Impact on Phase 21:** None of the DOM stages in `auto_buy()` use `run_in_executor`. All DOM operations (`tab.select`, `tab.click`, `tab.send_keys`, `tab.evaluate`) are native nodriver async operations that cancel cleanly. The only executor calls in auto_buy are the login helper calls, which are done before the timed stages begin.

**Conclusion:** Per-step timeouts on DOM stages are cancel-safe. No executor-thread leakage risk for the DOM steps being timed. [VERIFIED: codebase grep — no `run_in_executor` inside auto_buy bodies in either plugin]

### Pattern 5: get_item_order_state_sync Targeted Read

**What:** Rather than filtering `get_items_sync()` (which returns 5-tuples without `order_id`), add a targeted single-column read. This avoids loading all items just to check one item's order state.

```python
# [ASSUMED] illustrative — mirrors existing get_item_notification_state_sync pattern
def get_item_order_state_sync(link: str) -> tuple[bool, str | None]:
    """Return (purchased as bool, order_id) for idempotency check (BUY-05)."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT purchased, order_id FROM items WHERE link=?",
            (link,),
        ).fetchone()
    if row is None:
        return False, None
    return bool(row[0]), row[1]
```

### Pattern 6: increment_checkout_attempts_sync

```python
# [ASSUMED] illustrative — mirrors update_item_purchased_sync pattern
def increment_checkout_attempts_sync(link: str) -> None:
    """Increment checkout_attempts by 1 for the item (BUY-05/REL-08)."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET checkout_attempts = checkout_attempts + 1 WHERE link=?",
            (link,),
        )
```

### Anti-Patterns to Avoid

- **Outer single timeout on auto_buy:** Wrapping the entire `auto_buy()` in one timeout means a slow form-fill kills the CVV entry or place-order click mid-flight, leaving a half-submitted order. Per-step timeouts abort cleanly at the DOM boundary of each stage. [VERIFIED: CONTEXT.md locked decision]
- **Retry inside auto_buy:** The retry loop belongs in the orchestrator, not inside the plugin. `auto_buy` returns True/False; the orchestrator decides whether to retry. Mixing retry logic into the plugin couples the DOM work to the backoff policy.
- **Sleeping with time.sleep in retry:** `time.sleep` in an async context blocks the event loop. `asyncio.sleep` is the correct primitive; it is cooperative and cancel-safe.
- **Incrementing checkout_attempts after confirmation:** The CONTEXT.md decision is to increment BEFORE each attempt. This ensures the count reflects attempts made, not successes, and prevents a succeeded-but-misdetected order from being retried (the pre-attempt re-read of `order_id` provides the actual guard).
- **Double-incrementing via write queue:** `increment_checkout_attempts_sync` should be called directly via `run_in_executor` (or via `on_attempt` callback), not through the write queue. The write queue is for purchased/confirmed/available writes. Using it for attempt counts would serialize unnecessarily and complicate the `on_attempt` callback.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff | Custom sleep loop in each retry site | `core/retry.py compute_delay` | Single source of truth for Phase 22 supervisor reuse (REL-08) |
| Jitter randomness | `random.random()` inline | Injectable `rng` parameter | Tests need seeded rng for determinism |
| asyncio cancel safety | Manual try/except around every sleep | `asyncio.sleep()` (already cancel-safe) | stdlib handles cooperative cancellation |

## Per-Plugin DOM Stage Map

This is the core deliverable for the planner: exactly where each `asyncio.timeout` + `self._checkout_stage` assignment goes in each plugin.

### Amazon Plugin (`plugins/shopbot_plugin_amazon.py`) — `auto_buy()` starts at line 364

Current structure (no timeouts):

| Stage Name | Current Code Location | DOM Action | Notes |
|---|---|---|---|
| `"navigate"` | Line 386 | `tab = await self.driver.get(url)` | First await; most likely to hang on slow product page |
| `"quantity-select"` | Lines 397-408 | `.a-button-dropdown` click + `#quantity_{n-1}` click | Two selects, one timeout block covers both |
| `"test-pause"` | Lines 410-415 | `_wait_user_action` (test_mode only) | NOT a timed stage — it awaits user; skip timeout here |
| `"buy-now"` | Lines 418-424 | `#buy-now-button` select + click | One timeout block |
| `"place-order-select"` | Lines 426-430 | `#submitOrderButtonId` select | Pre-CVV; before the guarded click |
| `"cvv-entry"` | Lines 432-439 | `#addCreditCardCvvInput` send_keys | Optional field; timeout still applies (absent field returns None fast) |
| `"place-order"` | Line 442 | `place_order_guarded(place_order.click)` | Final click; stage set before the guarded call |

**Confirmed from codebase read:** `login()` is called before the try block at line 384 — it is NOT part of the timed stages. `login()` has its own internal waits for passkey/OTP which use `asyncio.wait_for(event.wait(), timeout=300)` — a user-action gate, not a DOM timeout. Login should remain un-timed at the auto_buy level.

**Stage count for Amazon:** 6 timed stages (navigate, quantity-select, buy-now, place-order-select, cvv-entry, place-order). The `test-pause` is a user action gate, not a DOM step, so it is excluded from per-step timeouts.

### BestBuy Plugin (`plugins/shopbot_plugin_bestbuy.py`) — `auto_buy()` starts at line 273

Current structure (no timeouts):

| Stage Name | Current Code Location | DOM Action | Notes |
|---|---|---|---|
| `"navigate"` | Line 292 | `tab = await self.driver.get(url)` | Product page load |
| `"add-to-cart"` | Lines 294-299 | `.add-to-cart-button` select + click | Distinct from checkout — cart add is step 1 |
| `"cart-navigate"` | Line 301 | `self.driver.get("https://www.bestbuy.com/cart")` | Navigate to cart page |
| `"quantity-select"` | Lines 303-320 | `.a-dropdown-prompt` + `#quantity_{n}` | Both in one stage |
| `"checkout-proceed"` | Lines 322-327 | `.checkout-buttons__checkout` select + click | Proceed from cart |
| `"login"` | Line 330 | `await self.login()` | Called mid-flow after checkout proceed — NOT a timed stage (user-action gate) |
| `"address-fill"` | Lines 332-358 | `_fill_field` loop for 7 required fields | Form fill; one timeout block covers the loop |
| `"cvv-entry"` | Lines 360-364 | `#credit-card-cvv` send_keys | Optional (guarded by `self._cvv`) |
| `"place-order"` | Lines 366-371 | `.button--place-order` select + `place_order_guarded` | Final click |

**Note on BestBuy login placement:** `login()` is called at line 330, inside the try block, after proceeding to checkout. It is a user-action gate (waits for Enter), not a DOM scrape. Do NOT wrap it in `asyncio.timeout(step_timeout_secs)`. The `_wait_user_action` inside it already has its own 300s guard.

**Stage count for BestBuy:** 8 timed stages (navigate, add-to-cart, cart-navigate, quantity-select, checkout-proceed, address-fill, cvv-entry, place-order). Login is excluded.

### Shared `_checkout_stage` Default

`self._checkout_stage: str = ""` must be added to `RetailerPlugin.__init__` in `core/plugin_base.py` as a default. Both plugins inherit it. Setting it before each stage means the orchestrator's cart-retry error handler can log it on `CancelledError` or `auto_buy` returning False.

## Orchestrator Cart-Retry Seam

### Current `_try_auto_buy` (lines 183-222 of orchestrator.py)

```python
async def _try_auto_buy(plugin, name, link, write_queue, dispatcher) -> None:
    ...
    success = await plugin.auto_buy(link)
    ...
    if order_id is not None:
        await write_queue.put(("confirmed", link, order_id, ts))
    else:
        await write_queue.put(("purchased", link))
```

`_try_auto_buy` currently: calls `plugin.auto_buy`, runs confirmation detection, enqueues the write. It returns `None`.

### Retry Wrapper Placement

The cart-retry loop wraps the `auto_buy` call and confirmation detection. The `write_queue.put()` calls must stay OUTSIDE the retry loop (per STATE.md pitfall note on double-buy). The structure is:

```
_check_and_buy (existing)
  |-- calls _cart_retry_wrapper (NEW) instead of _try_auto_buy directly
        |-- loop up to max_cart_retries:
        |     pre-attempt: increment checkout_attempts
        |     pre-attempt: read order_id -- exit if confirmed
        |     call: success = await plugin.auto_buy(link)
        |     call: order_id = await detect_order_confirmation(tab, platform)
        |     if success and order_id: break (done)
        |     if not success or no order_id: backoff and retry
        |-- after loop: enqueue write (confirmed or legacy purchased)
```

**Key constraint from STATE.md (Phase 22 pitfall):** `write_queue.put()` must be OUTSIDE the timeout/retry scope. This is already respected because confirmation detection + write happen after `auto_buy` returns.

**Refactoring approach:** Rather than restructuring `_try_auto_buy`, the simplest additive change is:

1. Extract the `auto_buy` + confirmation detection block into a new `_attempt_buy(plugin, link) -> tuple[bool, str|None]` that returns `(success, order_id)` — no write, no enqueue.
2. `_cart_retry_wrapper` calls `_attempt_buy` in a `with_retry` loop with the idempotency guard.
3. After the loop, `_try_auto_buy` (or a renamed version) enqueues the write.

Alternatively, stay additive: `_try_auto_buy` gets the retry loop inside it without extracting helpers, and `write_queue.put()` remains at the bottom. Either approach works; the planner chooses based on line-count discipline (30-line max per function).

### DB Re-Read Before Each Attempt

`get_item_order_state_sync(link)` returns `(purchased, order_id)`. Called via `run_in_executor` before each attempt in the retry loop:

```python
loop = asyncio.get_running_loop()
purchased, order_id = await loop.run_in_executor(None, get_item_order_state_sync, link)
if order_id is not None:
    writeLog(f"[{platform}] prior confirmed order_id={order_id} -- skipping retry", "INFO")
    return  # or break from loop
```

This is the no-double-buy guard (BUY-05).

### Confirmation Stays Outside Retry

The confirmation detection (`detect_order_confirmation`) and the `write_queue.put()` remain the same as P19. The retry loop only retries the DOM buy attempt + confirmation. On final success, the existing enqueue logic runs exactly once.

## Common Pitfalls

### Pitfall 1: asyncio.timeout CancelledError Swallowed

**What goes wrong:** A bare `except Exception` around the DOM stage catches `CancelledError` (which inherits from `BaseException` in Python 3.8+ but IS caught by `except Exception` on 3.11+ since it inherits through `BaseException`, not `Exception`).

**Why it happens:** `asyncio.CancelledError` is a subclass of `BaseException` in Python 3.8+, NOT `Exception`. So a `try/except Exception` block does NOT catch it — it propagates correctly.

**Correction:** The existing `except Exception as exc` in `auto_buy` will NOT catch `CancelledError`. The `CancelledError` from an expired `asyncio.timeout` will propagate up to the orchestrator's `_try_auto_buy` caller, which currently catches `Exception`. Since `CancelledError` is `BaseException`, it will propagate past `except Exception` up to the TaskGroup.

**Resolution for Phase 21:** The per-step timeout fires `asyncio.TimeoutError` (a subclass of `TimeoutError`, which IS a subclass of `Exception` since Python 3.11). The outer `except Exception` in `auto_buy` WILL catch it. So `auto_buy` returns `False` on a step timeout. The retry loop then decides whether to retry.

**[VERIFIED: Python 3.11 docs — `asyncio.TimeoutError` is `TimeoutError` which inherits from `Exception`]** [ASSUMED — verifying against installed Python version; behavior consistent with Python 3.11+]

**How to avoid:** Set `self._checkout_stage` BEFORE the `async with asyncio.timeout()` block. On `TimeoutError`, log the stage name in the `except Exception as exc` handler and return `False`.

### Pitfall 2: Double-Incrementing checkout_attempts

**What goes wrong:** If `increment_checkout_attempts_sync` is called both in `on_attempt` callback AND inside `auto_buy` (which would be wrong), the count doubles.

**How to avoid:** Only the orchestrator calls `increment_checkout_attempts_sync`, via `on_attempt` in `with_retry`. No increment inside `auto_buy`.

### Pitfall 3: Jitter Makes Tests Non-Deterministic

**What goes wrong:** `random.uniform(0, backoff_jitter)` produces different delays every test run; assertions on exact sleep durations fail intermittently.

**How to avoid:** `compute_delay(attempt, policy, rng=random)` — tests pass `random.Random(42)` as `rng`. The production path uses the default module-level `random`.

### Pitfall 4: Cart-Retry Retries a Confirmed Order

**What goes wrong:** `auto_buy` returned `True`, `detect_order_confirmation` returned an `order_id`, but a transient exception in the confirmation detection path caused the caller to think it failed — retry loop re-enters `auto_buy` and places a second order.

**How to avoid:** The pre-attempt DB re-read checks `order_id`. If the FIRST attempt wrote the confirmed order (via `write_queue.put` + `_dispatch_write` + `update_item_confirmed_sync`), the second attempt reads a non-None `order_id` and exits immediately.

**Constraint:** The `write_queue.put()` call for the confirmed order must complete (i.e., the drain task must flush it) before the next retry attempt reads the DB. Because the retry uses `asyncio.sleep(compute_delay(...))` between attempts, and the write-queue drain runs concurrently, there is a race window: the drain may not have flushed the write before the re-read.

**Mitigation:** The retry loop re-read is a best-effort guard, not a guarantee. The primary guard is `order_id is not None` returned by `detect_order_confirmation` in the same attempt — if the order was confirmed, the attempt exits successfully and the retry loop does not iterate. The DB re-read catches the case where the bot was restarted mid-retry. The STATE.md note (Phase 22 pitfall #10) confirms: `write_queue.put()` must be outside the retry scope, which is the design here.

### Pitfall 5: `_checkout_stage` Not on Base Class

**What goes wrong:** `self._checkout_stage = "navigate"` is set in `auto_buy` but the attribute does not exist until then. If the orchestrator reads it on an exception before `auto_buy` is called, it gets `AttributeError`.

**How to avoid:** Add `self._checkout_stage: str = ""` to `RetailerPlugin.__init__`.

### Pitfall 6: CancelledError in asyncio.sleep During Backoff

**What goes wrong:** If the TaskGroup cancels the plugin coroutine (e.g., KeyboardInterrupt) while the retry loop is sleeping in `asyncio.sleep(delay)`, the `CancelledError` should propagate up cleanly. If it is caught inside `with_retry`, the plugin task does not exit.

**How to avoid:** `with_retry` should NOT catch `CancelledError`. The `asyncio.sleep` raises it; it propagates through `with_retry` to the TaskGroup's cancellation machinery. This is the correct behavior.

## Code Examples

### Verified: asyncio.timeout Idiom (from codebase)

```python
# Source: plugins/shopbot_plugin_amazon.py lines 171-183
# WR-01: asyncio.timeout cancels the await but not the executor thread.
loop = asyncio.get_running_loop()
try:
    async with asyncio.timeout(120):
        token = await loop.run_in_executor(
            None, solver.solve_recaptcha, sitekey, pageurl
        )
except (asyncio.TimeoutError, Exception) as exc:
    _log.warning("CAPTCHA solve failed: %s", exc.__class__.__name__)
    ...
```

[VERIFIED: codebase] This is the exact pattern to mirror for per-step DOM timeouts, minus the `run_in_executor` (pure nodriver awaits cancel cleanly).

### Verified: CheckoutConfig Fields (from codebase)

```python
# Source: core/config_schema.py lines 264-272
class CheckoutConfig(BaseModel):
    item_timeout_secs: int = Field(default=120, ge=1)
    step_timeout_secs: int = Field(default=30, ge=1)
    max_cart_retries: int = Field(default=3, ge=0)
    backoff_base: float = Field(default=2.0, ge=0.0)
    backoff_jitter: float = Field(default=0.5, ge=0.0)
    alert_on_errors: int = Field(default=3, ge=0)
```

[VERIFIED: codebase] All config fields for `RetryPolicy` construction exist.

### Verified: Existing DB Write Pattern (from codebase)

```python
# Source: models.py lines 101-105 (update_item_purchased_sync)
def update_item_purchased_sync(link):
    with get_db_connection() as conn:
        conn.execute("UPDATE items SET purchased=1 WHERE link=?", (link,))
```

[VERIFIED: codebase] New helpers (`increment_checkout_attempts_sync`, `get_item_order_state_sync`) follow this exact pattern.

### Verified: Captcha Poll Loop (CI Exemption Confirmation)

```python
# Source: core/captcha.py line 59
for _ in range(_MAX_POLLS):
```

[VERIFIED: codebase] The loop variable is `_`, not `attempt`. The CI grep targeting `for attempt in range(` will NOT match this line. Exempt as required by CONTEXT.md.

### Verified: Proxy Rotation Loop (CI Exemption Confirmation)

```python
# Source: core/stealth.py line 244
for _ in range(len(self._entries)):
```

[VERIFIED: codebase] The loop variable is `_`, not `attempt`. CI grep exempt.

## CI Assertion Design

### Grep/AST Shape for No-Retry-Loop Outside core/retry.py

The CI assertion is an AST walk (mirroring `test_no_cvv_in_logs.py`):

1. Scan all `.py` files in `core/`, `plugins/`, `models.py`, `main.py` EXCEPT `core/retry.py`.
2. Walk AST for `ast.For` nodes whose `target` is an `ast.Name` with `id == "attempt"`.
3. Check that the node's `iter` is an `ast.Call` to `range(...)`.
4. Any match is a violation.

**Why `attempt` as the identifier (not `_`):** The locked CONTEXT.md decision says the assertion targets the `for attempt in range(` idiom. The captcha (`_`) and proxy (`_`) loops use `_` as the loop variable, making them structurally exempt without needing a whitelist.

**Alternative simpler form (grep):** `grep -rn "for attempt in range(" core/ plugins/ models.py` excluding `core/retry.py`. Equivalent to the AST walk for this specific pattern.

**Recommendation for test file:** Use `ast` module (not grep subprocess) to stay consistent with `test_no_cvv_in_logs.py` precedent. Fail with per-violation file:line list.

```python
# [ASSUMED] test structure — mirrors test_no_cvv_in_logs.py pattern
# In tests/test_retry.py or tests/test_no_retry_loops.py:
import ast
from pathlib import Path

def test_no_for_attempt_in_range_outside_retry():
    repo_root = Path(__file__).parent.parent
    exclude = {repo_root / "core" / "retry.py"}
    scan_dirs = [repo_root / "core", repo_root / "plugins"]
    scan_files_direct = [repo_root / "models.py", repo_root / "main.py"]
    violations = []
    for path in [...all .py files in scan_dirs...] + scan_files_direct:
        if path in exclude:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                if isinstance(node.target, ast.Name) and node.target.id == "attempt":
                    if isinstance(node.iter, ast.Call):
                        func = node.iter.func
                        fname = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                        if fname == "range":
                            violations.append(f"{path.name}:{node.lineno}")
    assert not violations, "for attempt in range() found outside core/retry.py: " + str(violations)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `asyncio.TimeoutError` as separate class | `asyncio.TimeoutError` is `TimeoutError` (stdlib) | Python 3.11 | `except TimeoutError` and `except asyncio.TimeoutError` are equivalent |
| `asyncio.wait_for` for timeouts | `async with asyncio.timeout()` context manager | Python 3.11 | Cleaner nesting; already used in this codebase |
| Manual retry loops at each call site | Shared `RetryPolicy` + `with_retry` | Phase 21 | Single backoff definition; prevents compounding with Phase 22 supervisor |

**Deprecated/outdated in this phase:**
- Inline `for attempt in range(max_cart_retries)` retry pattern in orchestrator: replaced by `with_retry`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `asyncio.TimeoutError` is `TimeoutError` (caught by `except Exception`) in Python 3.11+ | Pitfall 1 | If running Python < 3.11, `asyncio.TimeoutError` is a distinct class but still subclasses `Exception` via `concurrent.futures.TimeoutError`; behavior is the same in practice |
| A2 | `with_retry` signature with `on_attempt` + `should_retry` callbacks | Architecture Patterns Pattern 2 | Planner may simplify to no callbacks if inline is cleaner |
| A3 | `_cart_retry_wrapper` as a new function in orchestrator | Orchestrator Cart-Retry Seam | Could be inlined into `_check_and_buy` if < 30 lines |
| A4 | CI grep targets `for attempt in range(` identifier | CI Assertion Design | If retry.py itself uses a different loop variable, the assertion is still correct |
| A5 | `attempt` is 0-indexed in `compute_delay` | Pattern 1 | If 1-indexed, `backoff_base**1 = 2.0` as first delay (acceptable either way; planner must be consistent) |

## Open Questions

1. **`_attempt_buy` helper extraction vs. inline retry in `_try_auto_buy`**
   - What we know: `_try_auto_buy` is currently 40 lines (exceeds 30-line max); restructuring is likely required.
   - What's unclear: Whether to split into `_attempt_buy` (returns success+order_id) + retry wrapper, or restructure `_try_auto_buy` to embed the loop.
   - Recommendation: Extract `_attempt_buy(plugin, link) -> tuple[bool, str|None]` — cleaner separation, easier to test.

2. **`asyncio.sleep` in `with_retry` cancel behavior**
   - What we know: `asyncio.sleep` propagates `CancelledError` cleanly (cooperative cancel).
   - What's unclear: Whether Phase 22's per-item timeout wraps the retry loop — if so, the sleep cancellation should bubble up through `with_retry` to the item-level timeout. This is the correct behavior and requires no special handling.
   - Recommendation: No action in Phase 21; Phase 22 wraps at a higher level.

3. **`max_cart_retries=0` edge case**
   - What we know: `max_cart_retries` has `ge=0`, so 0 is valid.
   - What's unclear: Does `max_cart_retries=0` mean zero retries (run once, no retry) or zero attempts total (skip buy)?
   - Recommendation: `max_cart_retries=0` means no retries — buy attempt runs once. `with_retry(..., max_attempts=max_cart_retries + 1)` or document that `max_attempts` equals the number of total attempts. Planner must pick one and document it in a comment.

## Environment Availability

Step 2.6: SKIPPED — no external tools or services beyond the existing project stack. Phase 21 is code-only (new module + model helpers + plugin modifications).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (asyncio_mode=auto) |
| Config file | `pyproject.toml` (asyncio_mode=auto already set) |
| Quick run command | `pytest tests/test_retry.py tests/test_cart_retry.py -x` |
| Full suite command | `pytest` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REL-08 | `RetryPolicy` compute_delay with injected rng returns deterministic values | unit | `pytest tests/test_retry.py::test_compute_delay_deterministic -x` | No — Wave 0 |
| REL-08 | `with_retry` stops after `max_attempts` | unit | `pytest tests/test_retry.py::test_with_retry_max_attempts -x` | No — Wave 0 |
| REL-08 | No `for attempt in range(` outside `core/retry.py` (AST) | CI assertion | `pytest tests/test_no_retry_loops.py -x` | No — Wave 0 |
| BUY-06 | Per-step timeout fires and `_checkout_stage` is logged | unit | `pytest tests/test_retry.py::test_step_timeout_logs_stage -x` | No — Wave 0 |
| BUY-05 | Cart-retry exits immediately when pre-existing `order_id` found | unit | `pytest tests/test_cart_retry.py::test_no_retry_on_confirmed_order -x` | No — Wave 0 |
| BUY-05 | `checkout_attempts` increments once per attempt | unit | `pytest tests/test_cart_retry.py::test_attempt_count_increments -x` | No — Wave 0 |
| BUY-05 | Backoff sleep called with correct delay between retries | unit | `pytest tests/test_retry.py::test_with_retry_backoff_sleep -x` | No — Wave 0 |

### Sampling Rate

- Per task commit: `pytest tests/test_retry.py tests/test_cart_retry.py -x`
- Per wave merge: `pytest`
- Phase gate: Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- `tests/test_retry.py` — covers `compute_delay` determinism, `with_retry` max_attempts, backoff sleep, CI grep
- `tests/test_cart_retry.py` — covers idempotency guard, attempt increment, no double-buy
- `tests/test_no_retry_loops.py` — AST assertion (CI enforcement of REL-08)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Not touched in this phase |
| V3 Session Management | No | Not touched in this phase |
| V4 Access Control | No | Not touched in this phase |
| V5 Input Validation | Yes | Retry count and delay bounds enforced by `CheckoutConfig` Field validators (ge=0) |
| V6 Cryptography | No | No crypto in this phase |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unbounded retry loop | Denial of Service | `max_cart_retries` upper-bounded by config; `with_retry` always terminates |
| Double-buy on retry | Repudiation | `order_id` pre-read guard exits retry loop on confirmed order |
| CVV in retry log on failure | Information Disclosure | Existing `test_no_cvv_in_logs.py` AST guard already covers `writeLog` in both plugins; no new log callsites for CVV |

## Sources

### Primary (HIGH confidence)

- `plugins/shopbot_plugin_amazon.py` — full `auto_buy` DOM stage enumeration verified line by line
- `plugins/shopbot_plugin_bestbuy.py` — full `auto_buy` DOM stage enumeration verified line by line
- `core/orchestrator.py` — `_try_auto_buy` signature and write-queue placement verified
- `models.py` — column names (`checkout_attempts`, `order_id`, `confirmed_at`), DB helper patterns verified
- `core/config_schema.py` — `CheckoutConfig` fields verified (step_timeout_secs=30, max_cart_retries=3, backoff_base=2.0, backoff_jitter=0.5)
- `core/captcha.py` line 59 — `for _ in range(_MAX_POLLS)` verified (CI exemption confirmed)
- `core/stealth.py` line 244 — `for _ in range(len(self._entries))` verified (CI exemption confirmed)
- `core/plugin_base.py` — `RetailerPlugin.__init__` structure verified; `_checkout_stage` not present (must add)
- `tests/test_no_cvv_in_logs.py` — AST assertion pattern verified for CI test design

### Secondary (MEDIUM confidence)

- Python 3.11 docs [ASSUMED] — `asyncio.TimeoutError` == `TimeoutError`; `CancelledError` is `BaseException` not `Exception`

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all stdlib; no new packages
- Architecture: HIGH — verified from codebase; all integration points confirmed
- Per-plugin DOM stage map: HIGH — line-by-line verification from plugin source
- CI exemption (poll loops): HIGH — verified `_` variable names in both exempt loops
- Pitfalls: HIGH — derived from existing codebase patterns and STATE.md accumulated decisions
- Test shape: MEDIUM — mirrors existing test patterns; exact assertions drafted but not implemented

**Research date:** 2026-06-11
**Valid until:** 2026-12-11 (stable; no external dependencies)
