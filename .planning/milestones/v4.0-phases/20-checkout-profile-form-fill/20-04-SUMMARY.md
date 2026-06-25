---
phase: 20-checkout-profile-form-fill
plan: 04
subsystem: plugins
tags: [nodriver, form-fill, checkout, cvv, ast, security, bestbuy, amazon]

requires:
  - phase: 20-01
    provides: CheckoutProfile model + load_checkout_profile() + CHECKOUT_PROFILE_KEYS
  - phase: 20-03
    provides: AmazonPlugin._cvv threading + orchestrator injection + needs_cvv for amazon.com

provides:
  - RetailerPlugin.__init__ sets self._checkout_profile = None (additive safe default)
  - BestBuyPlugin._fill_field helper: tab.select + clear_input + send_keys + SPA event dispatch
  - BestBuy auto_buy fills 7 required shipping fields before CVV/place_order_guarded
  - Missing required shipping selector: WARNING(selector name) + return False, no submit (T-20-09)
  - Optional address_line2 filled only when value present and selector found
  - Amazon auto_buy enters CVV from self._cvv with skip-if-absent (T-20-10)
  - Both plugins load checkout profile at setup() time via load_checkout_profile()
  - tests/test_checkout_form_fill.py: 7 behavior tests covering fill, abort, CVV skip
  - tests/test_no_cvv_in_logs.py: AST CI assertion (BUY-07 criterion 3)

affects:
  - phase-21-per-step-timeouts
  - phase-22-supervisor-browser-relaunch

tech-stack:
  added: []
  patterns:
    - "_fill_field(tab, selector, value) -> bool: clear_input + send_keys with SPA onChange dispatch"
    - "Profile-None guard in auto_buy: WARNING + return False before any place_order_guarded call"
    - "AST walk over ast.Call nodes checking writeLog() args for forbidden token"
    - "monkeypatch writeLog (stdout-only) for log-content assertions in tests"
    - "conftest fake_element.clear_input = AsyncMock() for _fill_field compatibility"

key-files:
  created:
    - tests/test_checkout_form_fill.py
    - tests/test_no_cvv_in_logs.py
  modified:
    - core/plugin_base.py
    - plugins/shopbot_plugin_bestbuy.py
    - plugins/shopbot_plugin_amazon.py
    - tests/conftest.py
    - tests/test_plugin_bestbuy.py

key-decisions:
  - "_fill_field logs selector name only, never field value (T-20-08 mitigated)"
  - "Amazon shipping address form-fill deferred to UAT: Amazon typically uses account default address (Open Question 1 / out of scope this plan)"
  - "SPA onChange dispatch added best-effort inside try/except; non-fatal if apply() unsupported (Pitfall 7)"
  - "conftest fake_element updated with clear_input = AsyncMock() as per reviewer note; additive, non-breaking"
  - "BestBuy shipping selectors #first-name/#last-name/#street/#street2/#city/#state/#zip/#phone are MEDIUM/LOW confidence -- UAT debt recorded"

patterns-established:
  - "_fill_field helper pattern: all required-field selectors routed through single helper returning bool"
  - "writeLog-capturing test pattern: monkeypatch the module-level writeLog (stdout only, not captured by caplog)"
  - "AST scan with non-vacuous file-existence guard for CI security assertions"

requirements-completed: [BUY-07]

duration: 14min
completed: 2026-06-11
---

# Phase 20 Plan 04: Form-Fill Implementation Summary

**BestBuy shipping form-fill and Amazon CVV entry wired from CheckoutProfile + self._cvv, with DOM-drift abort guard, optional-field skip, and AST CI assertion proving no CVV leak to logs.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-06-11T22:35:19Z
- **Completed:** 2026-06-11T22:49:00Z
- **Tasks:** 3 (+ 1 Rule 1 auto-fix)
- **Files modified:** 7

## Accomplishments

- BestBuy and Amazon plugins load `self._checkout_profile` at `setup()` time via `load_checkout_profile()`; `RetailerPlugin.__init__` defaults it to None (no API bump, additive)
- BestBuy `auto_buy` fills 7 required shipping fields via `_fill_field` before CVV/`place_order_guarded`; any absent required selector logs `WARNING(selector)` and returns False without submitting
- Amazon `auto_buy` enters CVV from `self._cvv` using `#addCreditCardCvvInput`; absent CVV field is skipped gracefully (valid state per T-20-10)
- AST CI assertion in `test_no_cvv_in_logs.py` proves no `_cvv` variable appears in any `writeLog()` argument across both plugins and `core/checkout_profile.py` (BUY-07 criterion 3)
- Full suite: 625 passed, 2 skipped (net +8 tests from baseline 617)

## Task Commits

1. **Task 1: _checkout_profile default + BestBuy form-fill + Amazon CVV fill** - `3e798ec` (feat)
2. **Task 2: Form-fill behavior tests** - `c627225` (test)
3. **Task 3: CVV-not-in-logs AST CI assertion** - `574d48b` (test)
4. **Rule 1 fix: conftest clear_input + regression test update** - `f0a9283` (fix)

## Files Created/Modified

- `core/plugin_base.py` - Added `self._checkout_profile = None` in `__init__` (additive; PLUGIN_API_VERSION stays 2)
- `plugins/shopbot_plugin_bestbuy.py` - Added `_fill_field` helper; setup() loads profile; auto_buy fills shipping fields before CVV
- `plugins/shopbot_plugin_amazon.py` - setup() loads profile; auto_buy inserts CVV fill with skip-if-absent
- `tests/test_checkout_form_fill.py` - 7 behavior tests: fill success, missing selector WARN+False, profile-None guard, optional line2 skip, Amazon CVV skip-if-absent
- `tests/test_no_cvv_in_logs.py` - AST CI assertion with non-vacuous file-existence guard
- `tests/conftest.py` - Added `clear_input = AsyncMock()` to fake_element (Rule 1 fix per reviewer note)
- `tests/test_plugin_bestbuy.py` - Updated ASYNC-05 test to set `_checkout_profile` (Rule 1 fix)

## Decisions Made

- Amazon shipping address form-fill explicitly deferred: Amazon checkout typically uses the account's saved default address. No Amazon address form-fill was implemented this plan (matches Open Question 1 scope decision from CONTEXT.md). Noted as UAT debt.
- `_fill_field` uses best-effort SPA `onChange` event dispatch (`el.apply("(e) => e.dispatchEvent(new Event('input', {bubbles: true}))")`) inside a `try/except`; non-fatal if `apply()` is unsupported. UAT required to confirm React form validation clears.
- BestBuy shipping selectors remain MEDIUM/LOW confidence (UAT debt). No selector changes this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] conftest fake_element missing clear_input AsyncMock**
- **Found during:** Task 2 (form-fill behavior tests) -- existing test `test_autobuy_returns_true_without_direct_db_write` failed with TypeError when `_fill_field` awaited `el.clear_input()` on a plain MagicMock
- **Issue:** Conftest `fake_element` had `click` and `send_keys` as AsyncMocks but not `clear_input`, which `_fill_field` now awaits
- **Fix:** Added `fake_element.clear_input = AsyncMock()` in conftest; updated `test_autobuy_returns_true_without_direct_db_write` to set a complete `_checkout_profile` (required for the form-fill guard to pass in a full-flow test)
- **Files modified:** `tests/conftest.py`, `tests/test_plugin_bestbuy.py`
- **Verification:** All 22 BestBuy/Amazon tests green; full suite 625 passed
- **Committed in:** `f0a9283`

---

**Total deviations:** 1 auto-fixed (Rule 1 -- bug)
**Impact on plan:** Fix required for correctness; directly caused by `_fill_field` adding `clear_input` as an awaitable call. No scope creep.

## Known Stubs

None -- form-fill uses real selectors (MEDIUM/LOW confidence, UAT-gated) and the full `_fill_field` logic. No hardcoded empty values or placeholder text in the production code path.

**UAT debt (non-blocking, logged):**
- BestBuy shipping selectors `#first-name`/`#last-name`/`#street`/`#street2`/`#city`/`#state`/`#zip`/`#phone`: MEDIUM/LOW confidence; require live test_mode run to verify DOM match
- Amazon CVV selector `#addCreditCardCvvInput`: MEDIUM confidence; require live verification
- Amazon shipping address form-fill: deferred pending UAT confirmation that address is always pre-populated from account default

## Threat Flags

None beyond those in the plan's threat register. All T-20-07/T-20-08/T-20-09/T-20-10 mitigations implemented as specified.

## Issues Encountered

The `writeLog` function writes directly to stdout (not Python's logging module), so `pytest caplog` does not capture its output. Tests asserting WARNING log content must monkeypatch `writeLog` at the module level rather than using `caplog.at_level()`. Fixed in Task 2.

## Next Phase Readiness

- BUY-07 fully covered: profile-based shipping fill + CVV entry + no-CVV-in-logs CI guard
- Phase 21 (per-step timeouts + cart retry) can build on `_fill_field` for timeout wrapping
- Live form-fill + CVV UAT against real BestBuy/Amazon checkout DOM required before production use

---
*Phase: 20-checkout-profile-form-fill*
*Completed: 2026-06-11*

## Self-Check: PASSED

Files exist:
- tests/test_checkout_form_fill.py: FOUND
- tests/test_no_cvv_in_logs.py: FOUND
- core/plugin_base.py (modified): FOUND
- plugins/shopbot_plugin_bestbuy.py (modified): FOUND
- plugins/shopbot_plugin_amazon.py (modified): FOUND

Commits exist:
- 3e798ec: FOUND
- c627225: FOUND
- 574d48b: FOUND
- f0a9283: FOUND
