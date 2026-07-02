---
phase: 30-breakfix-hardening
verified: 2026-07-02T00:00:00Z
status: human_needed
score: 19/20 must-haves verified (1 partial, non-blocking)
overrides_applied: 0
human_verification:
  - test: "Amazon WAF auto-solve against a real AWS-WAF challenge"
    expected: "solve_amazon_waf returns a valid captcha_voucher/existing_token pair within the ~30s gokuProps freshness window, and the document.cookie injection (aws-waf-token / aws-waf-voucher) actually passes Amazon's live WAF check"
    why_human: "2captcha's AmazonTask injection payload shape is undocumented (RESEARCH.md Assumption A1, LOW confidence) and can only be confirmed against a live Amazon WAF challenge with a funded 2captcha balance -- not reproducible in CI (REQUIREMENTS.md Out-of-Scope)"
  - test: "Inject a real network/browser timeout at the live place-order click on a real retail drop (Amazon and/or BestBuy)"
    expected: "The place_order_attempted_at marker is already committed when the timeout fires; the next monitoring cycle raises _PossiblyPlaced, fires one possibly_placed alert, and never re-clicks place-order"
    why_human: "The final live edge-close of the double-buy guard needs a live slow-drop scenario; the idempotency guard itself is code-complete, unit/integration-tested with mocked timeouts (REQUIREMENTS.md Out-of-Scope: 'BF-02 place-order double-buy live proof')"
  - test: "Live login-selector accuracy for Walmart, Target, GameStop, NewEgg, SquareEnix"
    expected: "email/password/submit selectors match the current live DOM of each retailer's sign-in page so login() can actually reach the post-submit verification step"
    why_human: "All 5 community plugins carry pre-existing TODO markers noting selectors are unverified against live storefronts (~37 community-plugin selector-TODO debt bucket, explicitly Out-of-Scope for this milestone); the generic _verify_login_generic mechanism still guarantees ambiguous == not-success regardless of live selector accuracy"
  - test: "BestBuy post-login landing-page signal"
    expected: "Confirm whether a tighter DOM signal (beyond the current URL-only 'redirect off /identity/signin' check) is available on BestBuy's live post-login page"
    why_human: "BestBuy's post-login landing-page selector was never live-verified (RESEARCH.md); the URL-only check is the honest available signal today and is not a code gap, just an opportunity for a tighter check if a human confirms a stable selector"
---

# Phase 30: Breakfix Hardening Verification Report

**Phase Goal:** An unattended run cannot double-buy on a place-order-stage timeout (BF-02), Amazon WAF challenges are attempted via the existing 2captcha solver before falling back to manual pause (BF-01), and plugin logins are only reported successful when real post-login signals confirm it (BF-03).
**Verified:** 2026-07-02
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria — the binding contract)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An idempotency latch/guard proves no duplicate order is placed on retry after a place-order-stage timeout (BF-02, HIGH) | VERIFIED | `models.py` adds `place_order_attempted_at` column + `mark_place_order_attempted_sync`/`get_place_order_marker_sync` accessors (lines 82-85, 166-192). `plugins/shopbot_plugin_amazon.py:543-557` and `plugins/shopbot_plugin_bestbuy.py:408-427` durably `await` the marker write via `run_in_executor` **immediately before** `place_order_guarded(place_order.click)` — proven by `test_amazon_marks_place_order_before_click` and `test_bestbuy_place_order_latched` (`call_order == ["marker", "click_dispatch"]`). `core/orchestrator.py:410-441` (`_pre_attempt_check`) reads the marker on every retry attempt and raises `_PossiblyPlaced` (lines 383-389, 433-440) when set with no confirmed `order_id`, aborting the `with_retry` loop before `plugin.auto_buy()` is ever re-invoked — proven by `test_possibly_placed_aborts_retry` (`plugin.auto_buy.assert_not_awaited()`). No test literally wraps `place_order_guarded` itself in a raised `asyncio.TimeoutError` in one end-to-end scenario, but the ordering guarantee (marker always durably written before the click line executes, regardless of what happens after) plus the retry-abort guarantee together prove the truth as strongly as a single scenario test would. |
| 2 | Amazon WAF path calls the existing 2captcha solver when a challenge is detected, manual-pause fallback preserved when unavailable/fails; tests mock 2captcha and assert both paths (BF-01) | VERIFIED | `plugins/shopbot_plugin_amazon.py:156-226` (`_solve_or_pause`) detects `window.gokuProps` (line 179) and calls `solver.solve_amazon_waf(...)` via `run_in_executor` under `asyncio.timeout(120)` (lines 196-207), single attempt only (no retry loop — AST guard `test_no_retry_loops.py` passes). `test_amazon_waf_detected_falls_to_manual_pause` proves the solve-success path (solver called once, voucher/token injected via `_inject_waf_token`, `_wait_user_action` NOT called). `test_amazon_waf_solver_unavailable_falls_to_manual_pause`, `test_amazon_waf_solve_raises_falls_to_manual_pause`, `test_amazon_waf_gokuprops_decode_failure_falls_to_manual_pause`, `test_amazon_waf_injection_failure_falls_to_manual_pause` each prove a distinct fallback path degrades to the existing manual pause (`_wait_user_action`), never hard-failing the item. |
| 3 | Plugin login verifies success via expected post-login DOM/URL signals instead of assuming success; a test simulating a failed/ambiguous login asserts login is NOT reported successful (BF-03) | VERIFIED | `core/plugin_base.py:172-198`: ABC `login(self) -> bool` (was `-> None`), no-op default `True`; concrete `_verify_login_generic(tab, signin_url_fragment, form_selector) -> bool` returns `False` if the URL still contains the sign-in fragment, `False` if the form selector is still present, `False` on any exception (never raises) — D-13 "ambiguous == not-success" is structurally enforced by the `try/except Exception: return False` wrapper. All 7 plugins (`amazon`, `bestbuy`, `walmart`, `target`, `gamestop`, `newegg`, `squareenix`) convert `login()` to call this helper and return `False` on every early-return path (missing creds, missing DOM field, unverified signal, exception). `relaunch()` (`plugin_base.py:235-245`) captures `login_ok` and logs ERROR instead of silently treating a failed re-login as authenticated. `core/orchestrator.py:459-463,480-484` short-circuits cart-retry and fires a `login_failed` alert when `plugin._checkout_stage == "login"` on a failed attempt — proven by `test_login_failure_short_circuits_retry_and_alerts_once` (call-counter assertion: `login`/`auto_buy` invoked exactly once despite `max_attempts=4` configured, not merely a post-hoc alert). Per-plugin ambiguous-login tests exist in all 7 plugin test files (verified `_verify_login_generic` return-False cases + `auto_buy` never reaching `place_order_guarded`). |
| 4 | Full test suite is green with new/updated tests covering all three breakfixes | VERIFIED | Ran `pytest -q` independently in this verification session: **878 passed, 2 skipped, 46.23s** — matches the SUMMARY.md-claimed baseline exactly (30-05's "Next Phase Readiness": "Full test suite: 878 passed, 2 skipped"). All 20 task commit hashes cited across the 6 SUMMARY.md files were independently confirmed present in `git log` (ea9f414 through 3681f9b). |

**Score (ROADMAP contract):** 4/4 truths verified

### Plan-Level Truths (additive detail from PLAN.md frontmatter, merged/deduped across 30-01..30-06)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 5 | Marker set + no `order_id` → retry aborts, no re-click (30-01) | VERIFIED | See truth #1 above |
| 6 | Attempted-but-unconfirmed order fires **exactly one** operator alert and is **skipped on future cycles** (30-01) | PARTIAL (non-blocking) | The "no re-click" half is fully verified (see #1/#5). The "exactly one alert, ever" half is only proven within a single `_try_auto_buy` invocation — `test_possibly_placed_alert_fires_once` (`tests/test_orchestrator.py:1236-1261`) calls `_try_auto_buy` once and asserts one alert within that call. Traced `core/orchestrator.py` end-to-end: `_check_and_buy` (lines 492-540) has no marker check before calling `_try_auto_buy`, so on every subsequent polling cycle where the item remains `available=True` and `auto_buy=True`, `_try_auto_buy` is invoked again, `_pre_attempt_check` raises `_PossiblyPlaced` again, and `dispatcher.notify(..., "possibly_placed")` fires again. In a long-running unattended bot this means the operator receives a repeat alert every poll cycle for an unresolved item, not exactly one alert ever. **This does not create a double-buy risk** (the click-abort guarantee is unconditional and independently verified) — it is an alert-cadence/UX nuance, not a safety regression. See "Notable Finding" below. |
| 7 | Verified-failed login short-circuits cart-retry + fires one `login_failed` alert (30-01) | VERIFIED | `test_login_failure_short_circuits_retry_and_alerts_once` proves loop suppression via call-counter (not merely alert count). D-15 explicitly intends "a fresh attempt is allowed on the next monitoring cycle" (unlike BF-02's permanent latch), so a `login_failed` alert re-firing on a subsequent cycle is by design, not a gap. |
| 8 | WAF detection triggers single 2captcha solve attempt when solver available (30-02) | VERIFIED | See truth #2 |
| 9 | WAF falls back to manual pause on decode failure/unavailable/solve failure/timeout/injection failure (30-02) | VERIFIED | See truth #2 |
| 10 | WAF voucher/token is `json.dumps()`-escaped and rejected on quote/backslash/newline before injection (30-02) | VERIFIED | `plugins/shopbot_plugin_amazon.py:129-154` (`_inject_waf_token`): rejects `'`, `\`, `\n` (lines 142-144) before `json.dumps()` escaping (lines 146-147); `test_amazon_waf_inject_rejects_quote_backslash_newline` + `test_amazon_waf_inject_uses_json_dumps` (per SUMMARY 30-02) exercise this — same invariant already covered by CR-02 regression tests for the reCAPTCHA path. |
| 11 | `login()` ABC returns bool; no-op default returns True (30-03) | VERIFIED | `core/plugin_base.py:172-175` |
| 12 | `_verify_login_generic` returns False on ambiguous/exception (30-03) | VERIFIED | `core/plugin_base.py:177-198` |
| 13 | `relaunch()` does not treat a failed re-login as authenticated (30-03) | VERIFIED | `core/plugin_base.py:235-245` |
| 14 | Amazon `auto_buy` durably records marker before click (30-04) | VERIFIED | `plugins/shopbot_plugin_amazon.py:543-557`; `test_amazon_marks_place_order_before_click` |
| 15 | BestBuy `auto_buy` durably records marker before click (30-04) | VERIFIED | `plugins/shopbot_plugin_bestbuy.py:408-427`; `test_bestbuy_place_order_latched` |
| 16 | Amazon login True only after verify; `save_session` only after confirmed (30-05) | VERIFIED | `plugins/shopbot_plugin_amazon.py:389-443` (login method) — verified call ordering places `_verify_login_generic` before `save_session()` |
| 17 | BestBuy login True only after redirect off `/identity/signin` (30-05) | VERIFIED | `plugins/shopbot_plugin_bestbuy.py:225-268` |
| 18 | Amazon + BestBuy set `_checkout_stage='login'` before `login()`, abort `auto_buy` on False (30-05) | VERIFIED | `plugins/shopbot_plugin_amazon.py:468-472`; `plugins/shopbot_plugin_bestbuy.py:364-368` |
| 19 | All 5 community plugins `login()` → bool, False on missing creds/ambiguous/exception (30-06) | VERIFIED | Confirmed directly in `plugins/shopbot_plugin_{walmart,target,gamestop,newegg,squareenix}.py` — each has `async def login(self) -> bool`, `_verify_login_generic` call, `return False` on every early-exit and exception path |
| 20 | Each community `auto_buy` sets `_checkout_stage='login'` before `login()`, aborts on failed login (30-06) | VERIFIED | Confirmed in all 5 files: `self._checkout_stage = "login"` immediately before `login_ok = await self.login()`, `return False` when `not login_ok` |

**Score (all merged truths):** 19/20 fully verified, 1 partial (non-blocking, does not affect ROADMAP-level goal achievement)

### Notable Finding (non-blocking)

**`possibly_placed` alert re-fires every polling cycle, not exactly once.** Truth #6's "fires exactly one operator alert" is only true within a single `_try_auto_buy` call. `_check_and_buy` has no guard that checks `place_order_attempted_at` before entering `_try_auto_buy` again on the next poll, so an unattended run with an unresolved possibly-placed item will re-notify the operator every cycle (e.g. every poll interval) until the operator manually resolves it. The double-buy prevention itself is unaffected — `plugin.auto_buy()` is never re-invoked once the marker is set, verified independently at truth #1/#5. This is an alert-cadence/notification-spam nuance, not a safety defect.

**This looks like a minor, acceptable deviation** given D-04's fail-safe framing ("miss-a-buy over risk-a-double-buy") — repeated alerting arguably keeps the unresolved item more visible to the operator, not less. To formally accept this as-is, add to VERIFICATION.md frontmatter:

```yaml
overrides:
  - must_have: "An attempted-but-unconfirmed order fires exactly one operator alert and is skipped on future cycles"
    reason: "Alert re-fires every poll cycle for an unresolved possibly-placed item (no cross-cycle dedup) — the double-buy prevention itself (no re-click) is unconditional and independently verified; repeat alerting is a UX nuance, not a safety gap"
    accepted_by: "{your name}"
    accepted_at: "{ISO timestamp}"
```

Alternatively, a lightweight follow-up (e.g., a `possibly_placed_alerted` boolean or checking the marker before entering `_try_auto_buy` at all) would close this precisely — small, isolated change, does not require touching the core guard logic verified above.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `models.py` | `place_order_attempted_at` column + `get_place_order_marker_sync`/`mark_place_order_attempted_sync` | VERIFIED | Lines 82-85 (idempotent ALTER), 166-192 (accessors); round-trip + idempotent-migration tests in `tests/test_models.py:236-289` |
| `core/orchestrator.py` | `_PossiblyPlaced` abort exception + `_pre_attempt_check` marker branch + `_try_auto_buy` alert clauses | VERIFIED | Lines 383-389 (exception), 433-440 (guard branch), 469-484 (except clauses + `possibly_placed`/`login_failed` alerts) |
| `plugins/shopbot_plugin_amazon.py` | `_solve_or_pause` WAF branch + `_inject_waf_token` + marker write + `login()->bool` | VERIFIED | Lines 129-226 (WAF), 543-557 (marker), 389-443 (login) |
| `plugins/shopbot_plugin_bestbuy.py` | Marker write + `login()->bool` | VERIFIED | Lines 225-268 (login), 408-427 (marker) |
| `core/plugin_base.py` | `login(self) -> bool` ABC + `_verify_login_generic` + `relaunch()` return-check | VERIFIED | Lines 172-198 (login/_verify_login_generic), 235-245 (relaunch) |
| `plugins/shopbot_plugin_{walmart,target,gamestop,newegg,squareenix}.py` | `login()->bool` via generic verification + `auto_buy` abort-on-False | VERIFIED (all 5) | Each confirmed with `async def login(self) -> bool`, `_verify_login_generic` call, `_checkout_stage="login"` + abort pattern |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `core/orchestrator.py:_pre_attempt_check` | `models.get_place_order_marker_sync` | `loop.run_in_executor` DB read | WIRED | Line 433 |
| `core/orchestrator.py:_try_auto_buy` | `dispatcher.notify` | `_build_event` action=`possibly_placed`/`login_failed` | WIRED | Lines 476, 483 |
| `plugins/shopbot_plugin_amazon.py:_solve_or_pause` | `CaptchaSolver.solve_amazon_waf` | `run_in_executor` under `asyncio.timeout(120)` | WIRED | Lines 196-207 |
| `plugins/shopbot_plugin_amazon.py:_inject_waf_token` | tab (Chromium) | escaped `document.cookie` injection | WIRED | Lines 129-154 |
| `core/plugin_base.py:relaunch` | `self.login()` return value | `login_ok = await self.login(); if not login_ok → ERROR` | WIRED | Lines 238-243 |
| `plugins/shopbot_plugin_amazon.py:auto_buy` | `models.mark_place_order_attempted_sync` | `run_in_executor` before `place_order_guarded` | WIRED | Lines 552-557 |
| `plugins/shopbot_plugin_bestbuy.py:auto_buy` | `models.mark_place_order_attempted_sync` | `run_in_executor` before `place_order_guarded` | WIRED | Lines 422-427 |
| All 7 plugins `:login` | `core/plugin_base._verify_login_generic` | `_verify_login_generic(tab, fragment, selector)` before `return True` | WIRED | Confirmed in all 7 files |
| All 7 plugins `:auto_buy` | `self._checkout_stage`/`login()` return | `_checkout_stage='login'` then abort on False | WIRED | Confirmed in all 7 files |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite green | `pytest -q` | 878 passed, 2 skipped, 46.23s | PASS |
| AST retry-loop guard | `pytest tests/test_no_retry_loops.py -q` | 1 passed | PASS |
| All claimed task commits exist | `git log --oneline -1 <hash>` × 20 | All 20 found | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| BF-01 | 30-02 | Amazon WAF auto-solve wired via 2captcha, manual-pause fallback preserved | SATISFIED | Truths #2, #8, #9, #10 |
| BF-02 (HIGH) | 30-01, 30-04 | Place-order-timeout double-buy idempotency guard | SATISFIED (with non-blocking alert-cadence caveat) | Truths #1, #5, #6, #14, #15 |
| BF-03 | 30-01, 30-03, 30-05, 30-06 | Plugin login verified via real post-login signals | SATISFIED | Truths #3, #7, #11-13, #16-20 |

No orphaned requirements — REQUIREMENTS.md traceability table maps BF-01/BF-02/BF-03 all to Phase 30, and all three appear in at least one plan's `requirements:` frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `plugins/shopbot_plugin_{walmart,target,gamestop,newegg,squareenix}.py` | multiple | `# TODO: verify selectors against live ...` | INFO | Pre-existing (dated to Phase 6, predates Phase 30), explicitly documented as operator debt in REQUIREMENTS.md Out-of-Scope ("~37 community-plugin selector TODOs"). Not introduced or worsened by this phase; the BF-03 verification mechanism itself does not depend on selector accuracy (ambiguous signal still returns False regardless). |
| `plugins/shopbot_plugin_bestbuy.py` | 330 | `# TODO: verify ".a-dropdown-prompt" is correct for BestBuy cart` | INFO | Pre-existing, documented as "suspect BestBuy `.a-dropdown-prompt`" in REQUIREMENTS.md Out-of-Scope. Unrelated to Phase 30's changes. |

No `TBD`/`FIXME`/`XXX` debt markers found in any file modified by this phase (checked: `models.py`, `core/orchestrator.py`, `core/plugin_base.py`, all 7 plugin files).

### Human Verification Required

See frontmatter `human_verification:` block. Summary:

1. **Amazon WAF live-challenge acceptance** — 2captcha's exact injection payload shape is undocumented (RESEARCH.md Assumption A1); only confirmable against a real AWS-WAF challenge with a funded balance.
2. **BF-02 live double-buy edge proof** — the guard mechanism is code-complete and unit/integration-tested with mocked timeouts; final proof against a real slow-drop scenario is operator debt per REQUIREMENTS.md.
3. **Community-plugin live login-selector accuracy** (Walmart/Target/GameStop/NewEgg/SquareEnix) — pre-existing, explicitly out-of-scope debt; the verification mechanism itself is sound regardless of selector accuracy.
4. **BestBuy post-login landing-page signal** — currently URL-only (no live-verified DOM selector); opportunity for a tighter signal if a human confirms one, not a code defect.

All four are explicitly listed in REQUIREMENTS.md's "Out of Scope" table for this milestone (live-environment verification is tracked operator debt, not milestone work) — they are UAT debt items, not code gaps.

### Gaps Summary

No BLOCKER-level gaps found. All 4 ROADMAP success criteria are fully verified against live source code and an independently-run test suite (878 passed, 2 skipped). All 20 merged plan-level truths were checked; 19 fully verify, 1 (`possibly_placed` alert cadence) partially verifies — the safety-critical half (no re-click, ever) is unconditionally proven, while the "exactly one alert" half only holds within a single call and would repeat across polling cycles in a live unattended run. This is flagged as a non-blocking Notable Finding with a suggested override, not a phase-goal blocker. Four items remain legitimate live-environment UAT debt, all pre-declared as out-of-scope in REQUIREMENTS.md.

---

*Verified: 2026-07-02*
*Verifier: Claude (gsd-verifier)*
