---
phase: 14-anti-detection-layer-2-captcha-solving
plan: "03"
subsystem: captcha
tags: [captcha, plugin, recaptcha-v2, run_in_executor, asyncio-timeout, tdd, amazon, bestbuy]

requires:
  - phase: 14-anti-detection-layer-2-captcha-solving plan 02
    provides: _captcha_solver injected onto plugins via PluginRegistry.assign_solver

provides:
  - AmazonPlugin._solve_or_pause + _extract_sitekey + _inject_token helpers
  - AmazonPlugin: reCAPTCHA v2 solve path under asyncio.timeout(120); WAF graceful fallback
  - BestBuyPlugin: captcha_event, _wait_user_action, _solve_or_pause; best-effort reCAPTCHA solve
  - tests/test_captcha_plugin.py -- 19 plugin solve-path + fallback unit tests

affects: [phase-15-plugin-ecosystem]

tech-stack:
  added: []
  patterns:
    - _solve_or_pause helper extracts CAPTCHA solve path from check_availability (under 30 lines)
    - asyncio.timeout(120) wraps only the run_in_executor call (Pitfall 3 compliance)
    - V5 token validation: reject empty/quote/newline tokens before JS injection (T-14-inject)
    - WAF detection via window.gokuProps JS probe; INFO log + manual-pause fallback (T-14-waf)
    - Rule 1 fix: BestBuy test_plugin_bestbuy.py tests updated to patch detect_captcha
      (new detect_captcha accesses driver.main_tab.evaluate; fake_browser returns truthy
      sitekey without the patch; mirrors the Amazon test pattern already in use)

key-files:
  created:
    - tests/test_captcha_plugin.py
  modified:
    - plugins/shopbot_plugin_amazon.py
    - plugins/shopbot_plugin_bestbuy.py
    - tests/test_plugin_bestbuy.py

key-decisions:
  - "_solve_or_pause is a private async helper called from check_availability CAPTCHA branch; manual-pause fallback always reuses self._wait_user_action (never duplicated)"
  - "WAF auto-solve deferred per user decision (2026-06-09): window.gokuProps present logs INFO and falls through to manual pause; solve_amazon_waf() is never called from the plugin this phase"
  - "BestBuy detect_captcha override queries data-sitekey presence + challenge phrase; best-effort: empty sitekey falls to manual pause covering non-reCAPTCHA challenges (Open Question 2)"
  - "Rule 1 fix: existing BestBuy check_availability tests updated to patch detect_captcha (consistent with Amazon test pattern); new detect_captcha accesses main_tab.evaluate which returns truthy sitekey in fake_browser, causing false-positive CAPTCHA trigger and 300s test hang without the patch"
  - "PLUGIN_API_VERSION stays at 2; no ABC method added; _captcha_solver injected via attribute assignment (mirrors _proxy pattern)"

requirements-completed: [ANTI-06, ANTI-07]

duration: 18min
completed: "2026-06-09"
---

# Phase 14 Plan 03: Captcha Plugin Integration Summary

**reCAPTCHA v2 automated solve path wired into Amazon and BestBuy plugins via run_in_executor under asyncio.timeout(120); every failure mode degrades gracefully to the existing manual-pause path; Amazon WAF deferred and documented.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-06-09T20:20:00Z
- **Completed:** 2026-06-09T20:38:00Z
- **Tasks:** 2 (Task 1: Amazon; Task 2: BestBuy)
- **Files modified:** 4

## Accomplishments

- AmazonPlugin: `_solve_or_pause(tab, pageurl)` helper added; called from check_availability CAPTCHA branch
  - WAF probe (window.gokuProps): INFO log "auto-solve deferred" + manual pause (T-14-waf)
  - Sitekey extraction via `_extract_sitekey`; empty -> manual pause (no silent skip)
  - Solve via `loop.run_in_executor(None, solver.solve_recaptcha, sitekey, pageurl)` wrapped in `asyncio.timeout(120)` (T-14-block2, Pitfall 3)
  - Catch (asyncio.TimeoutError, Exception): log `exc.__class__.__name__`, manual pause
  - Token validation: reject empty / contains `'` / contains `\n` -> manual pause (T-14-inject)
  - `_inject_token`: sets `#g-recaptcha-response` + fires `___grecaptcha_cfg` callbacks via `tab.evaluate`
- BestBuyPlugin: `captcha_event`, `_wait_user_action`, `_extract_sitekey`, `_inject_token`, `_solve_or_pause`, `detect_captcha` added
  - Same run_in_executor + asyncio.timeout(120) pattern
  - detect_captcha: checks data-sitekey presence then "robot" challenge phrase
  - Empty sitekey (non-reCAPTCHA challenge) -> manual pause (best-effort coverage)
- 19 new tests in tests/test_captcha_plugin.py; all branches covered
- Full suite: 471 passed, 2 skipped (was 452 passed, 2 skipped; +19 new tests)

## Task Commits

Each task was committed atomically:

1. **Task 1+2 RED: failing plugin solve-path tests** - `697102e` (test)
2. **Task 1 GREEN: Amazon plugin** - `a35df25` (feat)
3. **Task 2 GREEN: BestBuy plugin + test regression fix** - `2b54a02` (feat)

## Files Created/Modified

- `tests/test_captcha_plugin.py` - 19 tests: Amazon all-branches (solver None, can_solve False, WAF, empty sitekey, success, exception, TimeoutError, quote token, newline token, source assertions); BestBuy branches (solver None, empty sitekey, success, source assertions)
- `plugins/shopbot_plugin_amazon.py` - Added `_captcha_solver=None` default, module-level JS constants, `_log`, `_extract_sitekey`, `_inject_token`, `_solve_or_pause`; routed check_availability CAPTCHA branch through `_solve_or_pause`
- `plugins/shopbot_plugin_bestbuy.py` - Added `captcha_event`, `_captcha_solver=None`, `_wait_user_action`, `_extract_sitekey`, `_inject_token`, `_solve_or_pause`, `detect_captcha`; added CAPTCHA branch in check_availability
- `tests/test_plugin_bestbuy.py` - Patched `detect_captcha` in 4 existing check_availability tests (Rule 1 fix; mirrors Amazon test pattern)

## Decisions Made

- `_solve_or_pause` is a private helper to keep `check_availability` under 30 lines (CLAUDE.md constraint).
- WAF auto-solve explicitly deferred: `solve_amazon_waf()` is present in `core/captcha.py` as the future API contract but NOT called from plugins this phase. Tests assert this (source regex scan).
- BestBuy's `detect_captcha` is best-effort: if sitekey is empty (Akamai/Cloudflare challenge), `_solve_or_pause` receives an empty sitekey and falls to manual pause without attempting a solve (Open Question 2 resolution).
- `asyncio.timeout(120)` context manager wraps ONLY the `await loop.run_in_executor(...)` line (Pitfall 3 compliance). No unrelated awaits inside the timeout scope.
- PLUGIN_API_VERSION stays 2; no abstract method added to RetailerPlugin ABC.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] BestBuy existing check_availability tests would hang on new detect_captcha**
- **Found during:** Task 2 GREEN (analysis before implementation)
- **Issue:** New `detect_captcha` calls `self.driver.main_tab.evaluate(_SITEKEY_JS)`. The `fake_browser` fixture's `evaluate` returns `"normal page content"` for any JS eval call, which is truthy -- causing `detect_captcha` to return `True`. Without patching, `check_availability` would enter `_solve_or_pause` with `_captcha_solver=None`, call `_wait_user_action`, and block for 300 seconds on `asyncio.wait_for(event.wait(), timeout=300)`.
- **Fix:** Added `patch.object(plugin, "detect_captcha", new=AsyncMock(return_value=False))` to 4 existing check_availability tests in `tests/test_plugin_bestbuy.py`. This is consistent with how `tests/test_plugin_amazon.py` already patches `detect_captcha`.
- **Files modified:** tests/test_plugin_bestbuy.py
- **Commit:** 2b54a02

**Total deviations:** 1 auto-fixed (Rule 1 -- test regression from new detect_captcha accessing fake_browser evaluate)
**Impact on plan:** Test fix only; no implementation scope change. All 19 new captcha tests plus 52 total plugin tests pass.

## TDD Gate Compliance

- RED gate: `697102e` (test commit with 19 failing tests)
- GREEN gate (Amazon): `a35df25` (feat commit; all Amazon captcha tests pass)
- GREEN gate (BestBuy): `2b54a02` (feat commit; all 19 tests pass; Rule 1 fix included)

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes. The two new trust boundaries are covered by the threat model:

| Flag | File | Description |
|------|------|-------------|
| T-14-inject (mitigated) | plugins/shopbot_plugin_amazon.py | Token from 2captcha validated before JS injection; quote/newline rejected |
| T-14-inject (mitigated) | plugins/shopbot_plugin_bestbuy.py | Same token validation applied |
| T-14-block2 (mitigated) | Both plugins | asyncio.timeout(120) wraps only run_in_executor call; non-blocking |
| T-14-silent (mitigated) | Both plugins | All failure branches call _wait_user_action; no silent skip |
| T-14-waf (accepted) | plugins/shopbot_plugin_amazon.py | WAF deferred; graceful fallback to manual pause documented |

## Known Stubs

None. WAF auto-solve is explicitly deferred (not a stub) and documented in `.planning/todos/pending/waf-auto-solve-followup.md`.

## Self-Check: PASSED

Files confirmed present:
- `plugins/shopbot_plugin_amazon.py` -- FOUND
- `plugins/shopbot_plugin_bestbuy.py` -- FOUND
- `tests/test_captcha_plugin.py` -- FOUND
- `tests/test_plugin_bestbuy.py` -- FOUND (modified)

Commits confirmed in git log:
- 697102e (RED) -- FOUND
- a35df25 (GREEN Amazon) -- FOUND
- 2b54a02 (GREEN BestBuy) -- FOUND

Full suite: 471 passed, 2 skipped -- no regressions.

---
*Phase: 14-anti-detection-layer-2-captcha-solving*
*Completed: 2026-06-09*
