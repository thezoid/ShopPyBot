# Phase 30: Breakfix Hardening - Research

**Researched:** 2026-07-02
**Domain:** Python 3.11+ async retail-automation bot (nodriver/Chromium checkout automation, SQLite persistence, 2captcha solving) -- three targeted correctness breakfixes, no new libraries
**Confidence:** HIGH (all touch-points verified directly against live source; the sole LOW-confidence item is the exact AWS-WAF token injection payload shape, flagged explicitly below)

## Summary

This phase is pure wiring/correctness work inside the existing v4.1 modular `core/` + `plugins/` architecture -- no new libraries, no schema redesign, no new architectural layers. All three breakfixes touch code that already exists and is already partially tested; the gap is a missing guard (BF-02), a deferred wire-up of an already-implemented solver method (BF-01), and a missing verification step on an already-called method (BF-03).

Every canonical source location cited in `30-CONTEXT.md` was read directly and confirmed accurate (line numbers match within 1-2 lines). Two important facts emerged from direct code reading that CONTEXT.md's canonical refs did not fully spell out, and both materially affect how the planner should scope tasks:

1. **BF-02's DB marker write cannot live in the orchestrator.** The write must happen inside the plugin's `auto_buy()` immediately before the place-order click -- the orchestrator only awaits `auto_buy()` as one atomic call and has no visibility into the click-dispatch instant. This requires a new (currently absent) direct `models.py` import into `plugins/shopbot_plugin_amazon.py` (and `bestbuy.py` if extended), following the existing `increment_checkout_attempts_sync` direct-write precedent (bypasses `write_queue`, does not violate ASYNC-05 which only governs the *purchased/confirmed* write path).
2. **BestBuy has the byte-for-byte identical swallowed-`TimeoutError` bug at its own place-order stage** (`shopbot_plugin_bestbuy.py:389-396`). CONTEXT.md scoped BF-02's root-cause callout to Amazon only and deferred "extending to non-Amazon plugins" as later cleanup "if found" -- it is found, in this research pass. See Open Questions for the recommendation.

**Primary recommendation:** Implement all three fixes as narrow, additive changes to already-tested modules: add one new SQLite column + one new models.py accessor + one new orchestrator abort exception for BF-02; replace one `if waf_raw:` branch in `_solve_or_pause` for BF-01 (the `CaptchaSolver.solve_amazon_waf` method is already implemented and already has full unit test coverage in `tests/test_captcha.py`); add one shared ABC verification helper + per-plugin `return True/False` conversions for BF-03. Two existing tests currently assert the *old* (pre-fix) behavior and must be rewritten, not just supplemented -- see Common Pitfalls.

## Architectural Responsibility Map

This is a single-process desktop bot, not a web app -- the standard Browser/SSR/API/CDN/DB tiers don't map cleanly. Substituting the closest analogous tiers for this codebase's actual layers (Browser/Client = nodriver-controlled Chromium tab; API/Backend = `core/orchestrator.py` + `core/*.py`; Database/Storage = SQLite via `models.py`; External Service = 2captcha HTTP API):

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Place-order idempotency marker (BF-02) | Database / Storage | API / Backend | Marker must be durably committed to SQLite (WAL, `busy_timeout=5000`) before the click; the retry guard that reads it back (`_pre_attempt_check`) lives in the orchestrator (API/Backend) |
| Place-order click dispatch (BF-02) | Browser / Client | API / Backend | The click fires inside the plugin's nodriver tab; orchestrator only awaits `auto_buy()` as one atomic unit and cannot observe the click instant itself |
| WAF challenge solve (BF-01) | API / Backend | External Service | `CaptchaSolver` is a blocking HTTP client to 2captcha, run via `run_in_executor`; solved token flows back to the Browser/Client tier for injection |
| WAF token injection (BF-01) | Browser / Client | -- | Applied via CDP (`tab.send(...)`) or `tab.evaluate(...)` against the live Chromium tab |
| Post-login verification (BF-03) | Browser / Client | API / Backend | DOM/URL signal is read from the live tab; the resulting `bool` flows back into the plugin's `auto_buy()` control flow (API/Backend-equivalent business logic) |
| Operator alerting (BF-02, BF-03) | API / Backend | -- | `notifications/dispatcher.py` fan-out is only reachable from `core/orchestrator.py` -- plugins have **no** dispatcher reference (see Common Pitfalls) |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**BF-02 -- Double-buy idempotency latch (HIGH)**
- **D-01 (latch durability):** DB-persisted write-ahead marker, not an in-memory flag. Write a "place-order attempted / in-flight" marker to SQLite **immediately before** dispatching the place-order button click, then reconcile after. An in-memory flag dies on relaunch; a relaunch mid-place-order is exactly the double-buy window. A persisted marker survives crash/relaunch and reuses the existing DB-read guard (`_pre_attempt_check` at `core/orchestrator.py:400-423`).
- **D-02 (marker mechanism):** new dedicated timestamp column (e.g. `place_order_attempted_at TEXT`) written just before the click. Do NOT overload `checkout_attempts` (accounting-only) and do NOT use the confirmation sentinel `CONFIRMED-<ts>` as the key (`core/confirmation.py:26-31` explicitly bars this).
- **D-03 (retry semantics):** once the place-order click has been dispatched, the place-order stage is non-retryable. Extend the retry guard: `_pre_attempt_check` raises a new "possibly-placed" abort (sibling to `_AlreadyConfirmed`) when the marker is set but no `order_id` is captured -- so the RetryPolicy loop never re-clicks place-order. Earlier stages remain retryable exactly as today.
- **D-04 (unconfirmed-order handling):** fail-safe = miss-a-buy over risk-a-double-buy. After the click fires (even on `TimeoutError`), run confirmation detection once. If confirmed -> `update_item_confirmed_sync` as today. If NOT confirmed -> leave the item in a "needs manual review / unconfirmed" state (marker set, no order_id), alert the operator via the notifier fan-out, and skip it on future monitoring cycles.
- **D-05 (reuse):** no second retry concept. Continue to use the single unified `RetryPolicy` (`core/retry.py`) -- the latch is a guard inside the existing loop, not a new retry mechanism.

**BF-01 -- Amazon WAF auto-solve wiring**
- **D-06 (wiring):** route the existing WAF branch to `solve_amazon_waf`. Replace the "auto-solve deferred; falling back to manual pause" path in `plugins/shopbot_plugin_amazon.py:147-158` (`_solve_or_pause`) with a call to `CaptchaSolver.solve_amazon_waf(key, iv, context, pageurl)` using the `gokuProps` values already read by `_WAF_PROBE_JS` (amazon:59-63). Run under `run_in_executor` (solver is blocking/sync) and inject the returned voucher/token via the same injection approach as the reCAPTCHA path.
- **D-07 (attempt policy):** single solve attempt, then manual pause -- no solve retry. The ~30s gokuProps freshness window makes a second solve likely to arrive stale and waste a 2captcha spend.
- **D-08 (fallback triggers):** manual-pause fallback preserved on every non-success path -- solver disabled/no balance/spend cap reached, solve API failure, solve timeout, token-injection failure, or missing/stale gokuProps. WAF solving must never hard-fail the item.
- **D-09 (budget):** WAF solves share the same spend cap and balance gate as reCAPTCHA -- one budget: `_solve_count` / `max_solves_per_run` and the startup balance check. No separate WAF cap.
- **D-10 (tests):** mock the 2captcha call; assert both paths -- solve-success (voucher injected, no manual pause) and fallback (solver unavailable/fails -> manual pause invoked). Live-challenge acceptance stays operator debt.

**BF-03 -- Post-login verification**
- **D-11 (scope):** one shared verification mechanism applied uniformly to all 7 plugins. Add the verification step to the ABC / a shared helper so a failed or ambiguous login can never be reported successful on any plugin. Do not special-case only Amazon/BestBuy.
- **D-12 (signal):** generic real signal + platform-specific override. Default success signal = post-submit URL is no longer the sign-in page **and** the login form is gone; Amazon/BestBuy get more specific signals where known. The 5 community plugins use the generic signal (selector tuning stays operator debt).
- **D-13 (ambiguity):** ambiguous == not-success. If the signal cannot be positively confirmed, login is reported failed.
- **D-14 (contract):** `login()` returns `bool`. Change the ABC `login(self) -> None` (`core/plugin_base.py:172-174`) to return `True` only when a post-login signal confirms, `False` on failed/ambiguous. ABC default returns `True` (login-less plugin is trivially "logged in"). Keep `PLUGIN_API_VERSION = 2` (additive contract change, v4.0 `place_order_guarded` precedent).
- **D-15 (behavior on verified-failed login):** abort the buy, don't proceed to checkout, alert the operator. A `False` from `login()` stops the attempt before add-to-cart/checkout and is surfaced as a non-transient failure (not an immediate retry loop; a fresh attempt is allowed on the next monitoring cycle). Also check the return at the `relaunch()` call site (`plugin_base.py:210-216`) so a failed re-login after relaunch is not silently treated as an authenticated session.

### Claude's Discretion

- Exact token/voucher injection JS for the WAF path (mirror the reCAPTCHA `_inject_token` approach) -- implementation detail.
- Precise DOM selectors / URL fragments per platform for the login signal -- Amazon/BestBuy verifiable now; the 5 others use the generic heuristic.
- Exact name/shape of the new "possibly-placed" abort exception and the DB column name -- planner's call, following existing `_AlreadyConfirmed` / `get_item_order_state_sync` patterns.
- Whether the "needs manual review" state is a new DB column vs derived (marker-set AND order_id-NULL) -- planner's call; derived is preferred if it avoids a schema addition.

### Deferred Ideas (OUT OF SCOPE)

- Live AWS-WAF auto-solve acceptance -- needs a real challenge inside the ~30s gokuProps freshness window; tracked operator debt.
- Live place-order-timeout double-buy edge proof -- the idempotency guard is code-actionable now; the final live edge-close is operator debt.
- Per-retailer live login-selector tuning for the 5 community plugins (Walmart/Target/GameStop/NewEgg/SquareEnix) -- generic verification signal ships now; live-verified selectors remain in the ~37 community-plugin selector-TODO debt bucket.
- Extending the persisted place-order latch to non-Amazon plugins' timeout sites -- "if the guard is implemented at the orchestrator/DB layer it covers all plugins uniformly, but any plugin-local timeout wrapping mirroring amazon:460-469 should be audited in a later cleanup if found." **This research found it (BestBuy) -- see Open Questions.**
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BF-01 | Amazon WAF challenge auto-solve wired into the Amazon plugin via the existing 2captcha solver path, with manual-pause fallback preserved (unit/integration-tested with mocked 2captcha; live-challenge proof stays operator debt) | `CaptchaSolver.solve_amazon_waf` (core/captcha.py:169-204) is already implemented and already unit-tested (tests/test_captcha.py CP-04/CP-05/WR-02) -- BF-01 work is wiring only, in `_solve_or_pause` (amazon:128-195). Exact injection payload is genuinely undocumented by 2captcha (LOW confidence) -- see Common Pitfalls / Open Questions for the honest gap and recommended mitigation. |
| BF-02 (HIGH) | A place-order-stage timeout cannot cause a placed-but-unconfirmed double-buy on retry -- an idempotency latch/guard around order placement, verified by injecting a timeout at that stage | Root cause confirmed at amazon:460-469 (swallowed `TimeoutError` -> `return False` -> retry loop re-clicks). Fix requires: 1 new SQLite column, 1 new models.py accessor, 1 new orchestrator abort exception (sibling to `_AlreadyConfirmed`), 1 new direct-write call inside `auto_buy()` immediately before the click. Existing `RetryPolicy`/`with_retry`/`_pre_attempt_check` mechanism is reused unmodified in shape (D-05). |
| BF-03 | Plugin login verifies success via expected post-login DOM/URL signals instead of assuming success (WR-03) | `login()` ABC contract change confirmed at plugin_base.py:172-174; `relaunch()` call site at :210-216 (lines confirmed). All 7 plugin `login()` implementations read and confirmed structurally identical (env-var creds -> navigate -> fill fields -> click submit -> `writeLog("Signed in...")` with zero post-submit verification). One breaking test (`test_login_noop`) and Amazon-only ordering nuance identified -- see Common Pitfalls. |
</phase_requirements>

## Standard Stack

**No new dependencies this phase.** This is 100% wiring/correctness work against already-installed, already-imported modules:

| Module | Role in this phase | Already imported by |
|--------|--------------------|--------------------|
| `core.retry` (`RetryPolicy`, `with_retry`, `compute_delay`) | Reused unmodified (D-05) -- BF-02's guard is an exception raised inside the existing `on_attempt` hook, not a new retry mechanism | `core/orchestrator.py` |
| `core.captcha.CaptchaSolver` | `solve_amazon_waf()` already implemented + already unit-tested; BF-01 only adds a call site | `core/orchestrator.py`, `plugins/shopbot_plugin_amazon.py` (via `self._captcha_solver`) |
| `models` (sqlite3 stdlib) | BF-02 needs one new column + one new accessor function, following the exact idiom already used for `order_id`/`confirmed_at`/`checkout_attempts` | `core/orchestrator.py` only today; **BF-02 requires adding this import to `plugins/shopbot_plugin_amazon.py`** (new dependency edge -- see Architecture Patterns) |
| `notifications.dispatcher.NotificationDispatcher` / `notifications.base.NotificationEvent` | Reused unmodified for operator alerts (D-04, D-15) via the existing `_build_event(...)` + `dispatcher.notify(...)` pattern already used for `"plugin_parked"` / `"health_degraded"` | `core/orchestrator.py` only -- plugins have no dispatcher reference (see Common Pitfalls) |

**Verified via registry/PyPI:** N/A -- no packages to verify. `requests==2.33.1` (already pinned, used by `core/captcha.py`) is the only HTTP client touched, and it is not being upgraded or newly added.

**Version verification:** `pytest 8.3.4` / `pytest-asyncio 1.3.0` confirmed installed in the current dev environment (`asyncio_mode = "auto"` in `pyproject.toml`, no `@pytest.mark.asyncio` decorator required, though existing tests use it inconsistently -- both styles work).

## Package Legitimacy Audit

**Not applicable.** This phase installs zero new external packages. All three breakfixes are wiring/logic changes inside `core/`, `plugins/`, and `models.py` using only stdlib (`sqlite3`, `asyncio`, `json`) and already-vetted, already-imported project dependencies (`requests`, `nodriver`). Skip condition per the Package Legitimacy Gate protocol is met.

## Architecture Patterns

### System Architecture Diagram (BF-02 idempotency guard)

```
 poll cycle (core/orchestrator.py: run_plugin -> _check_and_buy)
        |
        v
 _try_auto_buy(plugin, name, link, write_queue, dispatcher)
        |
        v
 with_retry(fn=_attempt_buy, policy, should_retry, on_attempt=_pre_attempt_check)
        |
        |--- on_attempt(N) --> _pre_attempt_check(loop, link, platform)
        |                         |
        |                         v
        |                    get_item_order_state_sync(link)  -> (purchased, order_id)
        |                    [NEW] get_item_place_order_marker_sync(link) -> attempted_at | None
        |                         |
        |                         |-- order_id present ------------> raise _AlreadyConfirmed  (existing)
        |                         |-- purchased legacy -------------> raise _AlreadyConfirmed  (existing)
        |                         |-- [NEW] marker set, no order_id -> raise _PossiblyPlaced    (NEW -- BF-02)
        |                         `-- else -------------------------> increment_checkout_attempts_sync (existing)
        |
        v
 _attempt_buy(plugin, link)
        |
        v
 plugin.auto_buy(link)  <-- runs INSIDE the plugin (Browser/Client tier)
        |
        |  ... navigate / add-to-cart / buy-now / cvv-entry stages (retryable, unchanged) ...
        |
        v
 [NEW] await loop.run_in_executor(None, mark_place_order_attempted_sync, link, now_iso)
        |    ^-- MUST be a synchronous, awaited, blocking-until-committed write.
        |        Must NOT go through write_queue (queue is deferred/async -- defeats
        |        the crash-durability purpose: the whole point is the marker is
        |        durably on disk before the click fires, even if the process dies
        |        1ms later).
        v
 await self.place_order_guarded(place_order.click)   <-- the click (existing, unmoved)
        |
        v
 (auto_buy returns True/False as today; _attempt_buy runs confirmation detection as today)
```

### Recommended Project Structure (no new files)

```
core/
├── orchestrator.py     # add _PossiblyPlaced exception; extend _pre_attempt_check; new operator-alert call
├── retry.py             # UNCHANGED (D-05)
├── captcha.py            # UNCHANGED -- solve_amazon_waf already exists and is already tested
├── plugin_base.py        # login() ABC -> bool; relaunch() checks login() return value
plugins/
├── shopbot_plugin_amazon.py    # _solve_or_pause WAF branch rewired; auto_buy marker write; login() -> bool + verify
├── shopbot_plugin_bestbuy.py   # login() -> bool + verify (BF-03); optionally marker write (BF-02, see Open Questions)
├── shopbot_plugin_{walmart,target,gamestop,newegg,squareenix}.py  # login() -> bool via generic shared signal (BF-03)
models.py                # +1 column (place_order_attempted_at), +1-2 accessor functions
tests/                   # extend existing files listed in canonical_refs -- no new test files required
```

### Pattern 1: Direct synchronous DB write from inside a plugin (NEW pattern for this codebase)

**What:** Every existing plugin write path (`update_item_purchased_sync`, `update_item_confirmed_sync`, availability writes) is either routed through `write_queue` (deferred, async, orchestrator-owned) or called directly from `core/orchestrator.py` via `run_in_executor` (e.g. `increment_checkout_attempts_sync`). No plugin file currently imports `models.py` at all.

**When to use:** BF-02's marker write is the first case where the write must happen at a precise instant *inside* plugin code (immediately before the click), so it cannot be deferred to the write_queue (async put() does not guarantee the write lands on disk before the click fires) and cannot be hoisted to the orchestrator (which has no hook between "about to click" and "clicked" -- `auto_buy()` is awaited as one atomic call).

**Recommendation:** Add `from models import mark_place_order_attempted_sync` (or equivalent name) to `plugins/shopbot_plugin_amazon.py`, and call it via `await asyncio.get_running_loop().run_in_executor(None, mark_place_order_attempted_sync, link, ts)` directly inside `auto_buy()`, immediately before `return await self.place_order_guarded(place_order.click)`. This does not violate the existing "ASYNC-05: does NOT call update_item_purchased directly" comment -- that comment is specifically about the *outcome* write (purchased/confirmed), which stays owned by `write_queue` unmodified. The marker write is a new, narrow, single-purpose write mirroring the existing `increment_checkout_attempts_sync` direct-write precedent (already called via `run_in_executor` from `core/orchestrator.py`, just now also callable from plugin code). WAL mode + `busy_timeout=5000` (already configured in `models.get_db_connection()`) make this safe under concurrent plugin coroutines.

**Example:**
```python
# Source: plugins/shopbot_plugin_amazon.py:460-463 (existing) + models.py idiom (existing)
self._checkout_stage = "place-order"
async with asyncio.timeout(step_timeout_secs):
    self._last_tab = tab
    # NEW: write-ahead marker -- MUST complete before the click (D-01).
    from models import mark_place_order_attempted_sync
    now_iso = datetime.now(timezone.utc).isoformat()
    await asyncio.get_running_loop().run_in_executor(
        None, mark_place_order_attempted_sync, url, now_iso
    )
    return await self.place_order_guarded(place_order.click)
```

### Pattern 2: New sibling abort exception (BF-02, mirrors existing `_AlreadyConfirmed`)

**What:** `core/orchestrator.py` already has `_AlreadyConfirmed` (an internal `Exception` subclass raised inside `on_attempt` to short-circuit `with_retry`, caught in `_try_auto_buy`). BF-02 needs a second, structurally identical exception for the "marker set, no order_id" case.

**Example:**
```python
# Source: core/orchestrator.py:376-380 (existing _AlreadyConfirmed, pattern to mirror)
class _PossiblyPlaced(Exception):
    """Sentinel: raised inside on_attempt when a place-order click was dispatched
    (marker set) but no order_id was ever confirmed. Aborts retry -- D-03/D-04:
    fail-safe = miss-a-buy over risk-a-double-buy. Caught in _try_auto_buy, which
    must alert the operator (D-04) instead of silently returning."""
    def __init__(self, attempted_at: str) -> None:
        self.attempted_at = attempted_at
```
`_pre_attempt_check` gains a new branch (checked in the same order-of-precedence as the existing checks -- order_id first, purchased-legacy second, then the new marker check, then the existing `increment_checkout_attempts_sync` fallthrough), and `_try_auto_buy` gains a new `except _PossiblyPlaced:` clause parallel to the existing `except _AlreadyConfirmed:` clause -- but unlike `_AlreadyConfirmed` (which logs INFO and returns silently, D-04 requires this new path to **also call `dispatcher.notify(...)`** via the existing `_build_event(name, link, platform, "possibly_placed")` + `NotificationDispatcher.notify()` pattern (same shape already used for `"plugin_parked"`/`"health_degraded"` -- both fire with `name=""`, `link=""`; this new alert should carry the real `name`/`link` since it's item-specific).

### Pattern 3: Shared post-login verification helper on the ABC (BF-03)

**What:** D-11 requires ONE shared mechanism on `RetailerPlugin` (not per-plugin duplication), with D-12's generic signal (URL no longer sign-in page AND login form gone) as default and Amazon/BestBuy overriding with tighter signals.

**Recommendation (Claude's Discretion per CONTEXT.md):** Add a concrete, non-abstract helper to `core/plugin_base.py` (PLUGIN_API_VERSION stays 2, additive -- v4.0 `place_order_guarded` precedent):

```python
# Source: core/plugin_base.py -- new concrete method, mirrors get_active_tab()/place_order_guarded() style
async def _verify_login_generic(
    self, tab, signin_url_fragment: str, form_selector: str
) -> bool:
    """D-12 generic signal: URL no longer contains signin_url_fragment AND
    form_selector is no longer present. D-13: any exception or ambiguity -> False.
    Never raises -- callers treat a raised exception the same as False (fail-safe)."""
    try:
        current_url = tab.target.url
        if signin_url_fragment in current_url:
            return False
        form_present = await tab.select(form_selector, timeout=5)
        return form_present is None
    except Exception as exc:
        writeLog(f"[{self.__class__.__name__}] login verification error: "
                 f"{exc.__class__.__name__}", "WARNING")
        return False
```

Each plugin's `login()` calls this (or a tighter platform-specific check) as the LAST step before `return True`, and every existing early `return` (missing creds, missing DOM elements) becomes `return False`. Concrete per-platform signals, derived directly from the already-read source of each plugin's own sign-in URL + field selectors:

| Plugin | signin_url_fragment | form_selector (generic) | Tighter signal (D-12, "where known") |
|--------|---------------------|--------------------------|----------------------------------------|
| Amazon | `/ap/signin` | `#ap_email` | absence of `#ap_email` (already the generic signal here -- Amazon's own field IS the tightest available marker without live DOM access to an account-landing page selector) |
| BestBuy | `/identity/signin` | `#fld-e` | redirect off `/identity/signin` (URL-only, already tight -- BestBuy's post-login landing page selector is unverified, so URL-only is the honest "tighter" signal available) |
| Walmart | `/account/login` | `#email` | generic only (community plugin, D-12) |
| Target | `/account/signin` | `[data-test="accountNav-signIn"] input[type="email"]` | generic only |
| GameStop | `/login` | `input#login-form-email` | generic only |
| NewEgg | `/identity/signin` | `#labeled-input-signEmail` | generic only |
| SquareEnix | `/account/login` | `[type="email"]` | generic only |

### Pattern 4: WAF solve wiring (BF-01) -- mirrors the already-tested reCAPTCHA branch

**What:** `_solve_or_pause` (amazon:128-195) currently has a hard-coded early-return at the WAF-detection branch (lines 152-158). D-06 replaces it with the same `run_in_executor` + `asyncio.timeout(120)` + try/except shape already used for `solve_recaptcha` two branches later in the same function (lines 172-195) -- this exact pattern is already both implemented and unit-tested for reCAPTCHA, so BF-01 is a structural copy, not a new pattern.

**Example (structure only -- see Common Pitfalls for the injection-payload caveat):**
```python
# Source: plugins/shopbot_plugin_amazon.py:147-158 (current, to be replaced)
# and :172-184 (solve_recaptcha reference pattern, HIGH confidence)
if waf_raw:
    try:
        waf_data = _json.loads(waf_raw)  # {key, iv, context} per _WAF_PROBE_JS
    except Exception:
        await self._wait_user_action(self.captcha_event, "...")
        return
    loop = asyncio.get_running_loop()
    try:
        async with asyncio.timeout(120):
            solution = await loop.run_in_executor(
                None, solver.solve_amazon_waf,
                waf_data["key"], waf_data["iv"], waf_data["context"], pageurl,
            )
    except (asyncio.TimeoutError, Exception) as exc:
        _log.warning("WAF solve failed: %s", exc.__class__.__name__)
        await self._wait_user_action(self.captcha_event, "...")
        return
    # D-07: single attempt only -- no retry loop here, matches solve_recaptcha shape.
    try:
        await self._inject_waf_token(tab, solution)  # NEW method -- see Common Pitfalls
    except Exception as exc:
        _log.warning("WAF token injection failed: %s", exc.__class__.__name__)
        await self._wait_user_action(self.captcha_event, "...")
        return
    return  # success -- no manual pause
```

### Anti-Patterns to Avoid

- **Do not put the BF-02 marker write behind `write_queue.put()`.** The queue is intentionally async/deferred (unbounded, non-blocking put per REL-06) -- routing the marker through it reintroduces exactly the crash-durability gap D-01 exists to close.
- **Do not add a second retry loop or a new `RetryPolicy` instance for BF-02.** D-05 is explicit: reuse `with_retry`/`RetryPolicy` unmodified; the guard is an exception raised from the existing `on_attempt` hook.
- **Do not give plugins a `dispatcher` parameter to satisfy D-04/D-15's "alert the operator" requirement.** No plugin method (`auto_buy`, `login`, `relaunch`) has ever had orchestrator-object access in this codebase; alerting must happen at the orchestrator layer where `dispatcher` is already in scope (`_try_auto_buy`, `supervise`) -- see Common Pitfalls for exactly where.
- **Do not assume `login()` is called at the same point in every plugin's `auto_buy()` flow.** Amazon calls `login()` first (before any DOM interaction); BestBuy and all 5 community plugins call `login()` mid-flow, *after* add-to-cart and checkout-proceed have already run. D-15's phrase "stops the attempt before add-to-cart/checkout" is only literally true for Amazon.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Retry/backoff for the idempotency guard | A second retry policy or a bespoke backoff loop | `core/retry.py` `RetryPolicy` + `with_retry` (already used by `_try_auto_buy`) | D-05 explicit; also enforced by a structural AST test (`tests/test_cart_retry.py::test_no_retry_loop_in_orchestrator` and `tests/test_no_retry_loops.py`) that fails the build if any `for attempt in range(...)` loop appears outside `core/retry.py` |
| 2captcha AmazonTask HTTP client | A new solver call/parser | `core.captcha.CaptchaSolver.solve_amazon_waf` (already implemented, already fully unit-tested: CP-04 success path, CP-05 non-JSON fallback + submit-error, WR-02 `can_solve()` guard) | Building a second client would duplicate an already-correct, already-tested implementation |
| Token validation before JS injection | A new validation routine for the WAF voucher | The exact quote/backslash/newline rejection + `json.dumps()` escaping already used in `_inject_token` (amazon:114-126, covered by `tests/test_captcha_plugin.py` CR-02 regressions) | Same injection-safety invariant applies to any string interpolated into `tab.evaluate()`; reuse, don't reinvent |
| Operator alert delivery | A new notification channel or ad-hoc `writeLog` | `notifications/dispatcher.py` `NotificationDispatcher.notify()` via the existing `_build_event(name, link, plugin_name, action)` helper (`core/orchestrator.py:180-189`) | Fan-out with per-channel isolation already exists; unknown `action` strings degrade gracefully (Discord shows the raw string; `SoundNotifier` falls through to `play_notification_sound()`) -- no notifier code changes needed for new action strings like `"possibly_placed"` or `"login_failed"` |

**Key insight:** every piece of infrastructure this phase needs (retry policy, HTTP solver client, JS-injection sanitization, notification fan-out) already exists and is already tested. The actual work is exclusively: one new DB column + accessor, one new exception class + guard branch, one new ABC helper method, and per-plugin `bool` conversions.

## Common Pitfalls

### Pitfall 1: Two existing tests assert the OLD (pre-fix) WAF behavior and must be rewritten, not supplemented
**What goes wrong:** `tests/test_captcha_plugin.py::test_amazon_waf_detected_falls_to_manual_pause` asserts that `solve_amazon_waf` is **NOT** called on WAF detection, and `test_amazon_source_does_not_call_solve_amazon_waf` is a source-grep guard that asserts the literal string `solve_amazon_waf(` never appears as a call site in `shopbot_plugin_amazon.py`. Both will fail the moment BF-01 is wired correctly -- and that failure is the *correct* outcome, not a regression.
**How to avoid:** The plan must explicitly replace both tests (rename/rewrite them to assert the NEW behavior: WAF detected + solver available -> `solve_amazon_waf` IS called; WAF detected + solver unavailable/fails -> manual pause). Do not leave the old assertions in place expecting them to coexist with the new call site.
**Warning signs:** CI red on `test_captcha_plugin.py` after wiring the WAF branch is expected, not a bug to chase.

### Pitfall 2: `test_plugin_base.py::test_login_noop` asserts `login()` returns `None` -- breaks under D-14
**What goes wrong:** `async def test_login_noop(): result = await p.login(); assert result is None`. Per D-14, the ABC default must become `return True`. This assertion must change to `assert result is True`.
**How to avoid:** Flag this test explicitly in the plan's Wave 0 / test-update list (it's already implicitly covered by canonical_refs' "tests/test_plugin_base.py" entry, but the exact assertion that breaks is worth calling out so it isn't missed in a broad file-level pass).

### Pitfall 3: `login()` is NOT called at the same point in every plugin's `auto_buy()` -- D-15's "before add-to-cart/checkout" phrasing only fits Amazon
**What goes wrong:** Amazon's `auto_buy()` calls `await self.login()` at line 389, *before* navigate/quantity/buy-now (i.e., genuinely before any checkout DOM interaction). BestBuy calls `login()` at line 349, *after* `add-to-cart` (line 302-309) and `checkout-proceed` (line 337-344) have already executed. All 5 community plugins (Walmart/Target/GameStop/NewEgg/SquareEnix) follow BestBuy's ordering: `add_to_cart.click()` -> cart navigate -> `checkout_btn.click()` -> `await self.login()` -> place_order. If the planner writes "stop before add-to-cart/checkout" literally for all 7 plugins, 6 of them cannot satisfy it (checkout has already been initiated by the time `login()` runs).
**How to avoid:** Implement D-15 as "return `False` immediately after `login()` returns `False`, aborting all remaining stages (do not proceed to CVV/place-order)" -- true for all 7 plugins regardless of where in the flow `login()` sits. Do not gate task acceptance criteria on "no add-to-cart occurred" for BestBuy/community plugins.

### Pitfall 4: Plugins have no `dispatcher` reference -- D-04/D-15 operator alerts cannot be fired from inside a plugin
**What goes wrong:** `auto_buy(self, url: str) -> bool` and `login(self) -> bool` are the only signatures available on every plugin; neither receives a dispatcher, notifier, or any orchestrator-owned object. If the plan tries to have a plugin call `dispatcher.notify(...)` directly, there is no reference to call it on.
**How to avoid:** For BF-02 (D-04), fire the alert from `_try_auto_buy`'s new `except _PossiblyPlaced:` clause (orchestrator layer, `dispatcher` already in scope). For BF-03 (D-15), the login-failure alert must similarly be fired from the orchestrator layer -- since a `False` return from `auto_buy()` (due to login failure) is currently indistinguishable from any other stage failure at the `_attempt_buy`/`_try_auto_buy` level, the cleanest signal-passing mechanism is the already-existing `plugin._checkout_stage` instance attribute (BUY-06, already read by the existing `"cart-retry exhausted (stage=...)"` log line). Recommend the planner have each plugin set `self._checkout_stage = "login"` immediately before the `login()` call and check-fail, so the orchestrator can inspect `plugin._checkout_stage == "login"` after a `False` result to (a) fire a distinct `"login_failed"` alert and (b) skip the cart-retry backoff loop per D-15's "not an immediate retry loop" requirement (this needs a new `should_retry`/exception-based short-circuit analogous to Pattern 2 -- flagged as an Open Question below since CONTEXT.md's D-15 does not fully specify the retry-suppression mechanism).

### Pitfall 5: BestBuy has the identical swallowed-`TimeoutError` place-order bug as Amazon
**What goes wrong:** `shopbot_plugin_bestbuy.py:389-396` wraps its place-order click in the exact same `async with asyncio.timeout(step_timeout_secs): ... return await self.place_order_guarded(place_order.click)` shape, inside the same outer `except Exception as exc: ... return False` handler as Amazon. If BF-02 only patches Amazon, BestBuy retains the double-buy exposure with zero mitigation.
**How to avoid / recommendation:** Since the core guard mechanism (DB marker + `_PossiblyPlaced` abort in `_pre_attempt_check`) is platform-agnostic once built, the marginal cost of also adding the marker-write call to BestBuy's `auto_buy()` is small (same 4-line pattern, same place-order stage). See Open Questions for the explicit recommendation and scope tradeoff.

### Pitfall 6: `CONFIRMED-<ts>` sentinel is explicitly NOT an idempotency key (already documented, easy to violate accidentally)
**What goes wrong:** `core/confirmation.py:26-31` already warns that a payment-failure page reaching the Amazon thankyou URL can still produce a `CONFIRMED-<ts>` sentinel `order_id`. If the BF-02 "possibly-placed" check treats *any* non-NULL `order_id` (including a sentinel) as "confirmed, skip the alert," a payment-failure-that-looks-confirmed would silently suppress the D-04 operator alert.
**How to avoid:** `_pre_attempt_check`'s existing `if existing_order_id is not None: raise _AlreadyConfirmed(...)` branch already fires BEFORE the new marker check (order precedence in Pattern 2 above) -- this is actually fine as designed, since a sentinel order_id already existing means confirmation detection *did* run and found a URL match, which is a materially different (better) state than "marker set, no order_id at all." No code change needed here, but the planner should not conflate "sentinel present" with "needs manual review" -- they are different states with different existing handling.

### Pitfall 7: AST guard forbids any new `for attempt in range(` loop outside `core/retry.py`
**What goes wrong:** `tests/test_no_retry_loops.py::test_no_for_attempt_in_range_outside_retry` walks the AST of every `.py` file under `core/`, `plugins/`, plus `models.py` and `main.py`, and fails the build on any `for attempt in range(...)` loop found outside `core/retry.py`. If the planner's BF-02 implementation adds a manual retry loop anywhere (e.g., a bespoke solve-retry for WAF, contradicting D-07 anyway), this guard fails.
**How to avoid:** Confirms D-05/D-07 are structurally enforced, not just documented -- no new loops with a variable literally named `attempt`.

## Code Examples

### `_pre_attempt_check` extension (BF-02) -- order of precedence matters
```python
# Source: core/orchestrator.py:400-423 (existing, to be extended)
async def _pre_attempt_check(loop, link: str, platform: str) -> None:
    purchased, existing_order_id = await loop.run_in_executor(
        None, get_item_order_state_sync, link
    )
    if existing_order_id is not None:
        raise _AlreadyConfirmed(existing_order_id)          # existing -- unchanged
    if purchased:
        raise _AlreadyConfirmed("")                          # existing -- unchanged
    # NEW (BF-02): check BEFORE incrementing checkout_attempts, mirrors the
    # existing early-return-before-increment shape above.
    attempted_at = await loop.run_in_executor(
        None, get_place_order_marker_sync, link
    )
    if attempted_at is not None:
        raise _PossiblyPlaced(attempted_at)
    await loop.run_in_executor(None, increment_checkout_attempts_sync, link)
```

### `models.py` additions (BF-02) -- follows the existing idempotent-ALTER-TABLE idiom exactly
```python
# Source: models.py:61-80 (existing idiom for order_id/confirmed_at/checkout_attempts)
if "place_order_attempted_at" not in existing:
    conn.execute("ALTER TABLE items ADD COLUMN place_order_attempted_at TEXT")

# New accessor, mirrors get_item_order_state_sync (models.py:133-145) exactly:
def get_place_order_marker_sync(link: str) -> str | None:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT place_order_attempted_at FROM items WHERE link=?", (link,)
        ).fetchone()
    return row[0] if row else None

def mark_place_order_attempted_sync(link: str, attempted_at: str) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE items SET place_order_attempted_at=? WHERE link=?",
            (attempted_at, link),
        )
```

### `login()` -> `bool` conversion pattern (BF-03, applies to all 7 plugins)
```python
# Source: plugins/shopbot_plugin_amazon.py:299-364 (existing, every early `return`
# becomes `return False`; final success path calls the new verification helper)
async def login(self) -> bool:
    store = get_store()
    email = store.get("AMZ_EMAIL") or ""
    password = store.get("AMZ_PASSWORD") or ""
    if not email or not password:
        writeLog("AMZ_EMAIL or AMZ_PASSWORD not set -- skipping login", "ERROR")
        return False                                    # was: return
    try:
        tab = await self.driver.get("https://www.amazon.com/ap/signin?...")
        email_field = await tab.select("#ap_email", timeout=10)
        if not email_field:
            writeLog("Email field not found on Amazon sign-in page", "ERROR")
            return False                                # was: return
        # ... unchanged form-fill / passkey / MFA steps ...
        writeLog("Signed in to Amazon", "INFO")
        verified = await self._verify_login_generic(tab, "/ap/signin", "#ap_email")
        if not verified:
            writeLog("Amazon login verification failed", "WARNING")
            return False
        await self.save_session()
        return True
    except Exception as exc:
        writeLog(f"Error during Amazon sign-in: {exc.__class__.__name__}", "ERROR")
        return False                                    # was: implicit None
```

### `relaunch()` return-value check (BF-03, D-15 second half)
```python
# Source: core/plugin_base.py:210-216 (existing)
session_restored = await self.restore_session()
if not session_restored:
    writeLog(f"[{plugin_name}] restore_session=False; re-logging in", "INFO")
    login_ok = await self.login()                       # NEW: capture return value
    if not login_ok:
        writeLog(f"[{plugin_name}] relaunch: re-login failed; NOT authenticated", "ERROR")
else:
    writeLog(f"[{plugin_name}] relaunch: session restored; skipping login", "INFO")
```
No dispatcher plumbing needed here (relaunch() has never had one) -- logging ERROR is sufficient because the plugin's `_checkout_stage`/`auto_buy()` will naturally re-attempt login on the next monitoring cycle and surface the D-15 alert path there.

## State of the Art

Not applicable in the usual "library X deprecated in favor of Y" sense -- this is internal-codebase debt closure, not an ecosystem-currency question. The one relevant "old approach -> current approach" pair is internal to this phase:

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| `login() -> None`, success assumed unconditionally after the submit click | `login() -> bool`, success gated on a real post-submit DOM/URL signal | This phase (BF-03) | `relaunch()` and every plugin's `auto_buy()` gain a real failure signal instead of blind trust |
| WAF CAPTCHA always falls back to 300s manual pause | WAF CAPTCHA attempts one automated 2captcha solve first, falls back to manual pause only on failure | This phase (BF-01) | Reduces unattended-run stalls when running with `captcha.enabled=true` and a funded 2captcha balance |
| Place-order click failure (any reason, including timeout) is retried up to `max_cart_retries` times | Once a place-order click has fired, the item becomes non-retryable within the current monitoring cycle regardless of the failure reason | This phase (BF-02) | Closes the tracked HIGH audit item (v4.0 Phase 21) |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The exact JSON/cookie payload format 2captcha's `solve_amazon_waf` result (`captcha_voucher` + `existing_token`) must be applied to the live Amazon page in is UNDOCUMENTED by 2captcha's own API docs and could not be confirmed from official sources (WebFetch of `2captcha.com/api-docs/amazon-aws-waf-captcha` and `2captcha.com/h/how-to-bypass-amazon-captcha` both explicitly state the injection mechanism is left to the integrator). Cross-vendor research (anti-captcha, a different provider) suggests AWS WAF tokens are typically applied via a cookie (their convention: `amazon-waf-token`), not a JS-callback pattern like reCAPTCHA -- but this is a different vendor's convention, not confirmed to apply to 2captcha's two-value response shape. | Architecture Patterns (Pattern 4), Code Examples | If the planner or a downstream implementer guesses the wrong injection mechanism (cookie name, form field, or header), the WAF solve will silently fail to actually pass the challenge even though the mocked unit tests (which only assert the call site fires and doesn't crash) will pass green. This is explicitly bounded by REQUIREMENTS.md's own scoping ("live-challenge proof stays operator debt") -- the plan should implement a best-effort injection helper (recommend: CDP `tab.send(cdp_storage.set_cookies(...))`, reusing the existing `_dicts_to_cookie_params`-adjacent pattern already in `core/plugin_base.py`, since that's the more robust mechanism already proven in this codebase for cookie injection) and explicitly flag the payload correctness as unverified/operator-debt in the plan's acceptance criteria, exactly as REQUIREMENTS.md already does at the milestone level. |
| A2 | `mark_place_order_attempted_sync` / `get_place_order_marker_sync` and `_PossiblyPlaced` are proposed names, not confirmed against any existing convention document (CONTEXT.md explicitly delegates exact naming to the planner: "planner's call, following existing `_AlreadyConfirmed` / `get_item_order_state_sync` patterns"). | Code Examples | None -- purely cosmetic; any name following the existing `_sync` suffix + `_Xxx` exception-class idiom is equally valid. |
| A3 | Recommendation to also patch BestBuy's identical place-order timeout bug (Pitfall 5 / Open Question 1) is a research-derived suggestion, not a CONTEXT.md-locked decision -- CONTEXT.md's Deferred Ideas section frames non-Amazon extension as "later cleanup." | Common Pitfalls (Pitfall 5), Open Questions | If the planner scopes BF-02 to Amazon-only per the literal CONTEXT.md root-cause callout, BestBuy retains an un-mitigated, now-explicitly-known double-buy exposure of the same severity as the tracked HIGH item. If the planner includes BestBuy and the operator did not want scope expansion, it's a small amount of extra (low-risk, symmetric) code -- asymmetric downside favors inclusion, but this is presented as a recommendation for the discuss-phase/planning gate to confirm, not asserted as settled. |

## Open Questions

1. **Should BF-02's DB marker + guard also cover BestBuy's identical place-order timeout site, or stay Amazon-only this phase?**
   - What we know: `shopbot_plugin_bestbuy.py:389-396` has the byte-for-byte same swallowed-`TimeoutError`-at-place-order shape as Amazon's root-cause site. The underlying guard mechanism (DB column, `_pre_attempt_check` extension, `_PossiblyPlaced` exception) is being built platform-agnostically in `core/orchestrator.py`/`models.py` regardless of which plugins call the marker-write.
   - What's unclear: CONTEXT.md's canonical refs and root-cause narrative are Amazon-specific, and the Deferred Ideas section explicitly frames non-Amazon extension as "later cleanup ... if found" -- suggesting the operator's intent may have been Amazon-only for this phase, with BestBuy intentionally left for a follow-up.
   - Recommendation: Include the ~4-line marker-write addition to BestBuy's `auto_buy()` in the same phase, since the guard mechanism already has to be built and tested platform-agnostically for Amazon, and the marginal implementation/test cost for BestBuy is small relative to closing a known, symmetric double-buy exposure. If the operator prefers strict Amazon-only scope per the literal CONTEXT.md text, defer BestBuy explicitly (not silently) with a dated follow-up note, since leaving it unaddressed after this research surfaces it would be a regression from "not yet investigated" to "known and left open."

2. **What is the precise mechanism for suppressing cart-retry (not just aborting the current attempt) on a verified-failed login (D-15 "not an immediate retry loop")?**
   - What we know: `should_retry=lambda r: not r[0]` in `_try_auto_buy` only sees the `(success, order_id)` 2-tuple from `_attempt_buy`; it cannot currently distinguish "login failed" from any other DOM-stage failure that legitimately benefits from cart-retry (e.g., a transient selector-not-ready). `plugin._checkout_stage` is already set before each stage and already read for logging (`"cart-retry exhausted (stage=...)"`).
   - What's unclear: CONTEXT.md's D-15 states the requirement ("not an immediate retry loop; a fresh attempt is allowed on the next monitoring cycle") but leaves the mechanism to the planner. Two candidate mechanisms: (a) inspect `plugin._checkout_stage == "login"` after a `False` result inside `_try_auto_buy` and short-circuit the retry loop (no new exception needed, reuses existing telemetry); (b) raise a new sibling exception (mirroring `_PossiblyPlaced`) from inside the plugin's `auto_buy()` on login failure, caught the same way. Option (a) is lower-risk/smaller-diff since `_checkout_stage` already exists and crosses the plugin/orchestrator boundary safely (it's a plain instance attribute, not a call-time value).
   - Recommendation: Option (a) -- inspect `plugin._checkout_stage` after `_attempt_buy` returns `(False, None)`, short-circuit cart-retry when it equals the login-failure marker, and fire the D-15 operator alert from that same orchestrator-layer call site (mirrors the D-04 `_PossiblyPlaced` alert pattern in Pattern 2 above -- both are "orchestrator inspects post-attempt state and decides retry-vs-alert" mechanisms, keeping the two breakfixes structurally consistent).

## Environment Availability

Skipped -- this phase has no new external dependencies. The one existing external dependency touched (2captcha HTTP API via `requests`) is already wired, already configured via `CaptchaConfig`/`CredentialStore` (`TWOCAPTCHA_API_KEY`), and its live-network behavior is explicitly out of scope for this phase's automated tests (D-10: mocked only).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 + pytest-asyncio 1.3.0 (`asyncio_mode = "auto"` in `pyproject.toml` -- no decorator required, though most existing async tests use `@pytest.mark.asyncio` anyway; both work) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"]) |
| Quick run command | `pytest tests/test_cart_retry.py tests/test_retry.py tests/test_no_retry_loops.py tests/test_captcha.py tests/test_captcha_plugin.py tests/test_plugin_base.py -q` |
| Full suite command | `pytest -q` (per project CLAUDE.md) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| BF-02 | Timeout at place-order stage -> item marked non-retryable, no second click | unit | `pytest tests/test_cart_retry.py -x` (extend with a new `test_possibly_placed_aborts_retry` case) | New test case in existing file (✓ file exists) |
| BF-02 | `_pre_attempt_check` raises `_PossiblyPlaced` when marker set + no order_id | unit | `pytest tests/test_orchestrator.py -x` (or `test_cart_retry.py`, matching existing `_AlreadyConfirmed` test placement) | ✅ existing |
| BF-02 | DB column + accessors round-trip correctly, idempotent migration on legacy schema | unit | `pytest tests/test_models.py -x` (mirror `test_confirmation_columns_added` / `test_migration_on_legacy_schema`) | ✅ existing |
| BF-02 | Operator alert fires exactly once on unconfirmed-but-attempted state | unit | `pytest tests/test_cart_retry.py -x` or new assertion using `fake_notifier` fixture (conftest.py already provides one) | ✅ fixture exists |
| BF-01 | WAF detected + solver available -> `solve_amazon_waf` called, token injected, no manual pause | unit | `pytest tests/test_captcha_plugin.py -x` (REWRITE `test_amazon_waf_detected_falls_to_manual_pause`, see Pitfall 1) | ✅ existing (needs rewrite) |
| BF-01 | WAF detected + solver unavailable/fails -> manual pause, `solve_amazon_waf` not called or fails gracefully | unit | `pytest tests/test_captcha_plugin.py -x` | ✅ existing (needs rewrite) |
| BF-01 | `solve_amazon_waf` itself (submit/poll/decode/can_solve guard) | unit | `pytest tests/test_captcha.py -x` | ✅ already fully covered (CP-04/CP-05/WR-02) -- no new work needed here |
| BF-03 | `login()` returns `False` on missing creds / missing DOM field / exception, for all 7 plugins | unit | `pytest tests/test_plugin_amazon.py tests/test_plugin_bestbuy.py tests/test_plugin_walmart.py tests/test_plugin_target.py tests/test_plugin_gamestop.py tests/test_plugin_newegg.py tests/test_plugin_squareenix.py -x` | ✅ all exist |
| BF-03 | `login()` returns `True` only when the post-signal verification passes; ambiguous -> `False` | unit | `pytest tests/test_plugin_base.py -x` (new tests for `_verify_login_generic`; REWRITE `test_login_noop`, see Pitfall 2) | ✅ existing (needs one assertion updated) |
| BF-03 | `relaunch()` logs/handles a failed re-login without treating it as authenticated | unit | `pytest tests/test_relaunch.py -x` (extend with a `login()->False` case) | ✅ existing |
| BF-03 | `auto_buy()` aborts before place-order when `login()` returns `False`, for all 7 plugins | unit | same 7 plugin test files as above | ✅ existing |

### Sampling Rate
- **Per task commit:** the relevant quick-run subset for whichever breakfix the task belongs to (see table above)
- **Per wave merge:** `pytest tests/ -q -k "cart_retry or retry or captcha or plugin or relaunch or models or orchestrator"` (broad but still sub-full-suite)
- **Phase gate:** `pytest -q` (full suite) green before `/gsd:verify-work`, matching the project's `## Tests` command in CLAUDE.md

### Wave 0 Gaps
None -- every test file this phase needs already exists (per canonical_refs "Tests to extend"). No new test files, no new fixtures, no framework installs required. `conftest.py` already provides `tmp_data_dir`, `fake_notifier`, `fake_plugin`, `mock_nodriver_start`, `event_shim` -- all sufficient for the new test cases identified above.

## Security Domain

`security_enforcement` is not set in `.planning/config.json` -- treated as enabled per default.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|--------------------|
| V2 Authentication | Yes (BF-03 is literally an authentication-correctness fix) | Real post-login DOM/URL signal instead of blind success assumption; ambiguous = failed (D-13) |
| V3 Session Management | Marginal | `save_session()` already has a weak proxy guard (WR-03: skip save on zero domain-matching cookies) -- BF-03 strengthens the precondition (only call `save_session()` after `login()` verification passes) but does not touch session-store internals (out of scope, Phase 23 already shipped this) |
| V4 Access Control | No | Single-operator local bot, no multi-user access control surface |
| V5 Input Validation | Yes (BF-01) | The WAF solver's returned `captcha_voucher`/`existing_token` strings must go through the SAME quote/backslash/newline rejection + `json.dumps()` escaping already enforced for the reCAPTCHA token before any `tab.evaluate()` interpolation (existing pattern, amazon:186-193; regression-tested via CR-02 in `test_captcha_plugin.py`) |
| V6 Cryptography | No | No crypto added or touched this phase |
| V7 Error Handling / Logging | Yes | Maintain the existing `str(exc)`-ban invariant (enforced by `test_amazon_source_no_str_exc` / `test_bestbuy_source_no_str_exc`) in all new exception-handling branches added for BF-01/02/03; never log the 2captcha API key (already enforced, unchanged) or any credential value |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Untrusted captcha-solver response string interpolated into `tab.evaluate()` JS | Tampering | `json.dumps()` escaping + explicit rejection of quote/backslash/newline characters before injection (already implemented for reCAPTCHA; BF-01 must apply identically to the WAF voucher/token) |
| Business-logic double-submission (place-order click fired twice due to a naive retry-on-any-failure policy) | Repudiation / Integrity (closest STRIDE fit for a non-cryptographic business-logic replay) | BF-02's DB write-ahead marker + non-retryable guard IS the mitigation being built this phase |
| False-positive authentication state (bot proceeds to checkout believing it is logged in when it is not) | Spoofing | BF-03's real post-login DOM/URL signal check, ambiguous-defaults-to-failed (D-13) IS the mitigation being built this phase |
| Credential/API-key leakage via exception messages or log lines | Information Disclosure | Existing `exc.__class__.__name__`-only logging convention, enforced by structural source-grep tests; must be preserved in all new BF-01/02/03 exception handlers |

## Sources

### Primary (HIGH confidence -- direct codebase reads, this session)
- `E:\repos\ShopPyBot\.planning\phases\30-breakfix-hardening\30-CONTEXT.md` -- locked decisions D-01 through D-15, canonical source touch-points
- `E:\repos\ShopPyBot\core\orchestrator.py` -- full file read; `_attempt_buy`, `_pre_attempt_check`, `_AlreadyConfirmed`, `_try_auto_buy`, `run_plugin`, `supervise`, `_build_event`, `_build_captcha_solver` all confirmed against canonical_refs line numbers
- `E:\repos\ShopPyBot\core\retry.py` -- full file read; `RetryPolicy`, `compute_delay`, `with_retry`
- `E:\repos\ShopPyBot\core\confirmation.py` -- full file read; `_CONFIRMED_SENTINEL_PREFIX` warning confirmed
- `E:\repos\ShopPyBot\models.py` -- full file read; schema, idempotent ALTER-TABLE idiom, all `_sync` accessors
- `E:\repos\ShopPyBot\plugins\shopbot_plugin_amazon.py` -- full file read; `_solve_or_pause`, `_WAF_PROBE_JS`, `_inject_token`, `login()`, `auto_buy()` (including the exact place-order swallowed-TimeoutError site)
- `E:\repos\ShopPyBot\plugins\shopbot_plugin_bestbuy.py` -- full file read; confirmed identical place-order timeout pattern to Amazon
- `E:\repos\ShopPyBot\plugins\shopbot_plugin_{walmart,target,gamestop,newegg,squareenix}.py` -- all 5 read in full; confirmed identical `login()` structure and `checkout_btn.click()`-before-`login()` ordering
- `E:\repos\ShopPyBot\core\captcha.py` -- full file read; `CaptchaSolver`, `solve_recaptcha`, `solve_amazon_waf` (already implemented)
- `E:\repos\ShopPyBot\core\plugin_base.py` -- full file read; `login()` ABC, `relaunch()`, `place_order_guarded()`, `restore_session()`, `save_session()`
- `E:\repos\ShopPyBot\core\config_schema.py` -- full file read; `CaptchaConfig`, `CheckoutConfig`, all platform configs
- `E:\repos\ShopPyBot\core\registry.py` -- full file read; `assign_solver`, `assign_proxy`, plugin discovery/routing
- `E:\repos\ShopPyBot\notifications\{base,dispatcher,discord_notifier,sound_notifier}.py` -- confirmed `NotificationEvent`/`NotificationDispatcher` contract and graceful degradation on unknown `action` strings
- `E:\repos\ShopPyBot\tests\{test_cart_retry,test_captcha,test_captcha_plugin,test_plugin_base,test_relaunch,test_amazon_plugin,test_no_retry_loops,test_confirmation,test_models}.py` and `tests/conftest.py` -- all read in full to confirm existing test patterns, fixtures, and the two tests that assert pre-fix behavior (Pitfall 1/2)
- `E:\repos\ShopPyBot\pyproject.toml` -- pytest config, Python 3.11+ requirement, no new deps declared
- `E:\repos\ShopPyBot\.planning\REQUIREMENTS.md`, `.planning\STATE.md` -- milestone scope, "code-complete + CI-green, live proof stays operator debt" rule, traceability

### Secondary (MEDIUM confidence -- web search cross-referenced with official docs)
- [2Captcha Amazon WAF CAPTCHA API docs](https://2captcha.com/api-docs/amazon-aws-waf-captcha) -- confirms response shape (`captcha_voucher`, `existing_token`); does NOT specify injection mechanism (checked directly via WebFetch)
- [2Captcha "How to bypass Amazon captcha" guide](https://2captcha.com/h/how-to-bypass-amazon-captcha) -- confirms 2captcha explicitly defers injection-mechanism discovery to the integrator via DevTools Network-tab inspection

### Tertiary (LOW confidence -- flagged explicitly, not used as a basis for any locked recommendation)
- [Anti-Captcha AmazonTaskProxyless docs](https://anti-captcha.com/apidoc/task-types/AmazonTaskProxyless) -- describes a DIFFERENT vendor's single-token/`amazon-waf-token`-cookie convention; informative context only, not confirmed applicable to 2captcha's two-value response shape (see Assumption A1)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new dependencies, every touched module read directly
- Architecture: HIGH -- all canonical_refs line numbers verified against live source; the plugin->models new-dependency-edge finding (Pattern 1) and the BestBuy-parity finding (Pitfall 5) are both direct-code-read discoveries, not inferences
- Pitfalls: HIGH for the 6 codebase-verified pitfalls; LOW (explicitly flagged as Assumption A1) for the exact WAF token injection payload shape, which is genuinely undocumented by 2captcha and unverifiable without a live challenge

**Research date:** 2026-07-02
**Valid until:** 30 days (stable internal codebase; no fast-moving external dependency in scope) -- re-verify the 2captcha AmazonTask response contract (A1) if BF-01 live-UAT is later scheduled, since vendor API behavior for this specific undocumented-injection case could change without a version bump
