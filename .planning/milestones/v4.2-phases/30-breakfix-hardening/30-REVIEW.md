---
phase: 30-breakfix-hardening
reviewed: 2026-07-02T18:17:49Z
depth: deep
files_reviewed: 10
files_reviewed_list:
  - models.py
  - core/orchestrator.py
  - core/plugin_base.py
  - plugins/shopbot_plugin_amazon.py
  - plugins/shopbot_plugin_bestbuy.py
  - plugins/shopbot_plugin_walmart.py
  - plugins/shopbot_plugin_target.py
  - plugins/shopbot_plugin_gamestop.py
  - plugins/shopbot_plugin_newegg.py
  - plugins/shopbot_plugin_squareenix.py
findings:
  critical: 1
  high: 0
  medium: 2
  low: 3
  total: 6
status: resolved
gap_closure:
  resolved: 2026-07-02
  resolved_findings: [CR-01, MED-02, LOW-03, LOW-01]
  deferred_findings: [MED-01, LOW-02]
  deferred_reason: >
    MED-01 (community-plugin marker write) is pre-declared deferred debt
    (30-CONTEXT.md); LOW-02 (_checkout_stage structural invariant) is a
    convention documented as acceptable without a regression test. Neither
    is a phase-30 regression; both remain open backlog items, not blockers.
  full_suite: "887 passed, 2 skipped -- pre-fix baseline 878 passed, 2 skipped"
---

# Phase 30: Breakfix Hardening — Code Review Report

**Reviewed:** 2026-07-02T18:17:49Z
**Depth:** deep (cross-file trace: models.py ↔ core/orchestrator.py ↔ core/plugin_base.py ↔ 7 plugins; diff base `7f4740b..HEAD`)
**Files Reviewed:** 10 source files (all phase-30 non-test churn)
**Status:** findings

## Summary

BF-01 (WAF auto-solve wiring) and BF-03 (login verification / auto-buy abort) are implemented correctly and consistently across all 7 plugins. The `_inject_waf_token` escaping path was traced end-to-end (char-blacklist + `json.dumps(ensure_ascii=True)`) and is safe against JS-injection from a malicious/malformed 2captcha response.

BF-02 (the HIGH double-buy guard) has one **critical, provable functional regression**: the durable place-order marker is written unconditionally in Amazon and BestBuy `auto_buy()`, even when `place_order_guarded` is about to suppress the click for `debug.test_mode` (the project's own documented "safe for testing" default — `sample.config.yml` ships `test_mode: true`). This permanently disables future auto-buy for any item that reaches the place-order stage under test_mode, with no code path to reset the marker, and fires a false `possibly_placed` operator alert claiming an order may have been placed when no click ever fired. This was not exercised by any test (all marker-ordering tests pin `test_mode=False`) and was not caught by the phase verifier.

The known finding supplied in the task (possibly_placed alert re-firing every poll cycle) is **confirmed accurate** — see MED-02. The BF-02 marker-write guard is also confirmed **not extended** to the 5 community plugins (Walmart/Target/GameStop/NewEgg/SquareEnix) — this is pre-declared, deliberate deferred debt in `30-CONTEXT.md` (not a phase-30 regression), but is re-surfaced here at MEDIUM severity because it is a live residual double-buy exposure regardless of provenance.

## Critical Issues

### CR-01: BF-02 place-order marker is written even when the click is suppressed (test_mode), permanently poisoning the item and firing a false "possibly placed" alert

**File:** `plugins/shopbot_plugin_amazon.py:543-557`, `plugins/shopbot_plugin_bestbuy.py:408-427`

**Issue:**

Both plugins write the durable `place_order_attempted_at` marker unconditionally, *before* calling the guard that decides whether the click actually fires:

```python
# shopbot_plugin_amazon.py:543-557 (bestbuy:408-427 is byte-identical in shape)
self._checkout_stage = "place-order"
async with asyncio.timeout(step_timeout_secs):
    self._last_tab = tab
    from models import mark_place_order_attempted_sync
    now_iso = datetime.now(timezone.utc).isoformat()
    await asyncio.get_running_loop().run_in_executor(
        None, mark_place_order_attempted_sync, url, now_iso
    )
    return await self.place_order_guarded(place_order.click)
```

`place_order_guarded` (`core/plugin_base.py:148-170`, pre-existing, unmodified this phase) suppresses the actual `click_fn()` call and returns `False` whenever `debug.test_mode` **or** `debug.monitor_only` is true — and `test_mode` defaults to `True` in both `core/config_schema.py:63` and the shipped `sample.config.yml:45`. The Amazon docstring even documents this deliberately: *"test_mode is intentionally NOT suppressed here -- it navigates through to the final place_order_guarded call ... enabling cart inspection before the guarded click."*

So on the **very first** run against a real available item with the documented-default `test_mode: true`:
1. `auto_buy()` reaches the place-order stage, writes the marker to SQLite (durably, unconditionally), then `place_order_guarded` suppresses the click and returns `False`.
2. `success=False`, `plugin._checkout_stage == "place-order"` (not `"login"`) → `should_retry` (`core/orchestrator.py:461`) returns `True` → the retry loop (or the very next poll cycle if `max_cart_retries=0`) calls `_pre_attempt_check` again, which now finds `place_order_attempted_at` set → raises `_PossiblyPlaced` → `_try_auto_buy` fires a `possibly_placed` operator alert (`core/orchestrator.py:469-477`) claiming a click **may have been dispatched with no confirmed order** — even though no click occurred at all.
3. **No code path ever clears `place_order_attempted_at`** (grep confirms `mark_place_order_attempted_sync` is the only writer; there is no `clear_place_order_marker_sync`). Every subsequent poll cycle for that item, forever, short-circuits at `_pre_attempt_check` before `plugin.auto_buy()` is even invoked again — the item's auto-buy capability is permanently disabled unless an operator manually runs `UPDATE items SET place_order_attempted_at=NULL WHERE link=...` against the SQLite file.

**Concrete failure scenario:** An operator follows `sample.config.yml` (or simply never touches `debug.test_mode`, which defaults to `true`), runs the bot to "safely" watch an item reach checkout without buying (exactly the documented purpose of test_mode). The moment the item is in stock and reaches the place-order stage once, the item is silently and permanently blacklisted from ever being auto-bought again — and the operator receives a spurious "possibly placed, may need manual review" alert implying a real purchase might have gone through, when in fact test_mode correctly prevented it. Turning `test_mode` off afterward does not fix it; the marker persists in the SQLite file across restarts.

**Why this was missed:** every phase-30 marker-ordering test (`test_amazon_marks_place_order_before_click`, `test_bestbuy_place_order_latched`) explicitly sets `test_mode=False` to let the click reach `place_order_guarded`, so the test_mode-suppressed path was never exercised together with the new marker write.

**Fix:** Fold the marker write into the click closure passed to `place_order_guarded`, so it only executes when a real click is actually about to fire — this also tightens the D-01 "write immediately before click" contract instead of merely approximating it:

```python
async def _place_order_click():
    from models import mark_place_order_attempted_sync
    now_iso = datetime.now(timezone.utc).isoformat()
    await asyncio.get_running_loop().run_in_executor(
        None, mark_place_order_attempted_sync, url, now_iso
    )
    await place_order.click()

self._checkout_stage = "place-order"
async with asyncio.timeout(step_timeout_secs):
    self._last_tab = tab
    return await self.place_order_guarded(_place_order_click)
```

Apply identically to BestBuy. This removes the false-positive `possibly_placed` alert and the permanent-poison side effect entirely, with no change to the real (test_mode=False) crash-durability guarantee — the write and the click remain back-to-back inside the same awaited call.

## Warnings

### MED-01: BF-02 write-ahead marker is not implemented for the 5 community plugins — live double-buy exposure remains open

**File:** `plugins/shopbot_plugin_walmart.py:208`, `plugins/shopbot_plugin_target.py:212`, `plugins/shopbot_plugin_gamestop.py:211`, `plugins/shopbot_plugin_newegg.py:229`, `plugins/shopbot_plugin_squareenix.py:218`

**Issue:** Each of these plugins calls `return await self.place_order_guarded(place_order.click)` with no preceding `mark_place_order_attempted_sync` write. Since `_pre_attempt_check` (`core/orchestrator.py:410-441`) is platform-agnostic and reads the same DB marker for every plugin, and none of these 5 plugins ever write it, `get_place_order_marker_sync` always returns `None` for their items — `_PossiblyPlaced` can never fire for them, and a swallowed `TimeoutError`/exception at their place-order click (identical shape to the pre-fix Amazon bug: broad `except Exception: ... return False` at the bottom of each `auto_buy`) is fully retryable, i.e. a second real click can be dispatched.

**Concrete failure scenario:** With `test_mode=False`, `monitor_only=False`, and a working session on e.g. GameStop: `place_order.click()` fires and the retailer accepts the order server-side, but the confirmation page is slow to load and the outer `asyncio.timeout(step_timeout_secs)` (or the orchestrator's `item_timeout`) fires before `auto_buy` returns. The broad `except Exception` returns `False`; `should_retry` sees `stage="place-order" != "login"` → retries; `_pre_attempt_check` finds no marker (unlike Amazon/BestBuy) → does **not** raise `_PossiblyPlaced` → `auto_buy()` is invoked again → cart/checkout/login/place-order repeats → a second click can be dispatched against an order that was already accepted.

**Note:** This is documented, deliberate deferred scope in `30-CONTEXT.md` ("Extending the persisted place-order latch to non-Amazon plugins' timeout sites ... any plugin-local timeout wrapping mirroring amazon:460-469 should be audited in a later cleanup if found") and each of these 5 plugins is independently labeled EXPERIMENTAL / likely blocked by anti-bot protection before reaching place-order in practice, which lowers real-world likelihood. It is surfaced here at MEDIUM (not CRITICAL) because it is pre-declared debt with mitigating context, not a silent phase-30 regression — but the residual risk is real and identical in mechanism/severity to the pre-fix Amazon bug BF-02 was created to close.

**Fix:** Port the same `mark_place_order_attempted_sync` write (or the corrected click-closure form from CR-01) into each of the 5 plugins' place-order stage, or — better long-term — move the marker write into `place_order_guarded` itself in `core/plugin_base.py` so all 7 (and any future) plugins get it for free instead of relying on per-plugin copy-paste.

### MED-02: `possibly_placed` alert re-fires every polling cycle instead of exactly once (confirmed)

**File:** `core/orchestrator.py:492-540` (`_check_and_buy`)

**Confirmation of supplied finding:** Verified accurate. `_check_and_buy` has no marker pre-check before calling `_try_auto_buy` (`core/orchestrator.py:540`); `_pre_attempt_check` is only consulted from inside `with_retry`'s `on_attempt`, which runs again from scratch on every fresh `_try_auto_buy` invocation. For an item that remains `available=True`/`auto_buy=True` with an unresolved marker set, every poll cycle (`run_plugin`'s `while True` loop, `core/orchestrator.py:308-342`) re-enters `_try_auto_buy` → `on_attempt(0)` → `_pre_attempt_check` → `_PossiblyPlaced` → a fresh `dispatcher.notify(..., "possibly_placed")` (`core/orchestrator.py:475-476`). `plugin.auto_buy()` is correctly never re-invoked (the double-buy guarantee itself is sound and unconditional), but the alert repeats indefinitely.

**Severity rationale (MEDIUM, not just cosmetic):** for a long unattended run with a short `poll_interval` (default 30s per `app.poll_interval`), an unresolved possibly-placed item generates on the order of ~2,880 duplicate alerts per day until manually resolved. Depending on the notification channel (SMS/webhook), this risks rate-limiting/throttling or unnecessary cost, and buries the one meaningful alert in noise (alert fatigue), which is a genuine operational risk for a system whose entire premise is "notify the operator so they can act."

**Fix:** Either (a) check the marker in `_check_and_buy` before calling `_try_auto_buy` and skip silently after the first alert, or (b) track a `possibly_placed_alerted` boolean (in-memory per-plugin set of links, or a DB column) and only notify on the first observation, as the verifier's own suggested override describes. Given CR-01's fix removes the primary false-positive source, this becomes purely about cadence for genuine unconfirmed-order cases.

## Info

### LOW-01: Redundant `(asyncio.TimeoutError, Exception)` tuple in solve-timeout handlers

**File:** `plugins/shopbot_plugin_amazon.py:208, 246`, `plugins/shopbot_plugin_bestbuy.py:123`

**Issue:** `except (asyncio.TimeoutError, Exception) as exc:` — on Python 3.11+ (this repo targets 3.13 per the venv), `asyncio.TimeoutError` is an alias for the builtin `TimeoutError`, itself a subclass of `OSError` → `Exception`. The explicit `asyncio.TimeoutError` member is always already covered by `Exception` in the same tuple; it's dead weight, not a bug (functionally identical to `except Exception:`).

**Fix:** Simplify to `except Exception as exc:` at all three sites for clarity, or leave as-is if defending against a future Python downgrade — non-blocking either way.

### LOW-02: `_checkout_stage` doubles as informal state + retry-control signal with no reset-on-entry guarantee

**File:** `core/orchestrator.py:461` (`should_retry=lambda r: not r[0] and plugin._checkout_stage != "login"`)

**Issue:** The login-abort short-circuit depends on `plugin._checkout_stage` still reading `"login"` at the moment `should_retry` is evaluated. This works today because every plugin's `auto_buy()` unconditionally sets `self._checkout_stage = "login"` as its first stage transition before any early-return branch that could leave it stale — but this is an implicit cross-file invariant (7 plugins + the orchestrator) enforced only by convention, not by a type or an assertion. A future plugin (or a future edit to an existing one) that returns `False` before reaching the `self._checkout_stage = "login"` line (e.g. a new guard clause inserted above it) would silently inherit whatever `_checkout_stage` was left over from a *previous* `auto_buy()` invocation on the same instance, changing retry behavior in a way that's easy to miss in review.

**Fix:** No change required for correctness today; consider a lightweight regression test (already partially covered by `test_non_login_stage_failure_still_retries`) that asserts every plugin's `auto_buy()` sets `_checkout_stage` before its first `return False`, or reset `_checkout_stage = ""` at the top of `auto_buy()` before the config/monitor_only guard clauses so a stale value can never leak across invocations.

### LOW-03: No accessor exists to clear `place_order_attempted_at` after manual operator review

**File:** `models.py` (whole file — `mark_place_order_attempted_sync`/`get_place_order_marker_sync` only)

**Issue:** Once a genuine (non-test_mode) unconfirmed order sets the marker, D-04's design intent is "skip on future cycles until manually reviewed" — but there is no `clear_place_order_marker_sync` function anywhere, meaning the only recovery path after a legitimate manual review is direct SQLite surgery (`UPDATE items SET place_order_attempted_at=NULL WHERE link=?`), undocumented anywhere in `CLAUDE.md` or the plugin docstrings. This compounds CR-01's impact (no in-app recovery for the false-positive case either) and is a minor operability gap for the true-positive case.

**Fix:** Add a `clear_place_order_marker_sync(link)` accessor (mirrors the existing `clear_item_available_sync` / `clear_price_alert_armed_sync` pattern already in the file) and document the manual-review recovery step, even if no caller wires it up yet.

---

## Gap Closure (2026-07-02)

TDD gap-closure applied on the BF-02 double-buy path. RED test written before each
fix, GREEN confirmed, full suite green before/after each commit.

- **CR-01 (critical) — resolved.** `place_order_guarded` (`core/plugin_base.py`) now
  owns the durable place-order marker write via an optional `order_marker_link`
  kwarg, written immediately before `click_fn()` and ONLY on the non-suppressed
  path. Amazon and BestBuy `auto_buy()` no longer write the marker unconditionally
  before the guard runs — they pass `order_marker_link=url` instead. A test_mode
  run can no longer permanently latch an item or fire a false `possibly_placed`
  alert. Commit: `ba16879`.
- **MED-02 (warning) — resolved.** `_check_and_buy` (`core/orchestrator.py`) now
  pre-checks the place-order marker before entering the cart-retry loop and
  dedupes the `possibly_placed` alert via an `alerted_links` set threaded from
  `supervise()` through `run_plugin()`. The alert fires exactly once per latch
  (per process run); `_pre_attempt_check`'s `_PossiblyPlaced` raise stays as
  defense-in-depth inside the retry loop. Commit: `22ec887`.
- **LOW-03 (info) — resolved.** Added `clear_place_order_marker_sync(link)` to
  `models.py`, mirroring `clear_item_available_sync`/`clear_price_alert_armed_sync`.
  No caller wired up yet (recovery accessor for future operator tooling / manual
  invocation). Commit: `861fc79`.
- **LOW-01 (info) — resolved.** Simplified `except (asyncio.TimeoutError, Exception)`
  to `except Exception` at the three confirmed-redundant solve-timeout sites
  (amazon:208,246; bestbuy:123). No catch-semantics change. Commit: `dbe1345`.
- **MED-01 (warning) — deferred, unchanged.** Community-plugin marker write stays
  out of scope per `30-CONTEXT.md`'s pre-declared deferral; the 5 plugins
  (walmart/target/gamestop/newegg/squareenix) are unchanged.
- **LOW-02 (info) — deferred, unchanged.** `_checkout_stage` structural invariant
  is unchanged; no regression test added in this pass.

Full suite after all four fixes: 887 passed, 2 skipped (pre-fix baseline: 878
passed, 2 skipped).

---

_Reviewed: 2026-07-02T18:17:49Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
