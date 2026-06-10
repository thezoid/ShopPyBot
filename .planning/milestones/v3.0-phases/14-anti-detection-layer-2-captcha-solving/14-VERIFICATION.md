---
phase: 14-anti-detection-layer-2-captcha-solving
verified: 2026-06-09T00:00:00Z
status: human_needed
score: 14/14 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Enable captcha solving in config (captcha.enabled: true) with a funded 2captcha account, point the bot at a page showing a reCAPTCHA v2 widget, and confirm the solve completes end-to-end without manual intervention."
    expected: "The CAPTCHA is solved automatically; the bot proceeds past the challenge without displaying the manual-pause prompt."
    why_human: "Requires a live 2captcha account with balance and a real reCAPTCHA v2 page. No way to exercise the full HTTP submit/poll/inject chain in CI."
  - test: "Set TWOCAPTCHA_API_KEY to a zero-balance account and start the bot with captcha.enabled: true. Observe startup logs."
    expected: "Startup log warns 'balance is zero'; bot falls back to manual pause when a CAPTCHA is encountered; no paid request is made."
    why_human: "Requires a real 2captcha account at zero balance; cannot be replicated with mock HTTP in CI."
  - test: "Set TWOCAPTCHA_API_KEY to an account with balance below low_balance_threshold (e.g., $0.50 with threshold at $1.00) and start the bot."
    expected: "Startup log emits a WARNING about low balance but still allows solving; balance_ok remains True."
    why_human: "Requires a funded 2captcha account at a specific low-balance state."
---

# Phase 14: Anti-Detection Layer 2 — CAPTCHA Solving Verification Report

**Phase Goal:** Users can opt into automated CAPTCHA solving via 2captcha with full cost visibility and no credential plaintext exposure.
**Verified:** 2026-06-09T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | TWOCAPTCHA_API_KEY is a registered secret key (in SECRET_KEYS), read only via the credential store | VERIFIED | `core/credentials.py:76` — "TWOCAPTCHA_API_KEY" is the 20th entry in SECRET_KEYS under a `# 2captcha` comment; `python -c "from core.credentials import SECRET_KEYS; assert 'TWOCAPTCHA_API_KEY' in SECRET_KEYS"` exits 0 |
| 2 | captcha config section parses from YAML; enabled defaults to False | VERIFIED | `core/config_schema.py:219-228` — CaptchaConfig(enabled=False, max_solves_per_run=10, low_balance_threshold=1.00); AppConfig.captcha field at line 278; YAML override confirmed by test_captcha_config.py::test_captcha_config_yaml_override passing |
| 3 | CaptchaSolver.from_config returns None when disabled or when the API key is missing | VERIFIED | `core/captcha.py:115-125` — returns None when `enabled=False` or when store.get("TWOCAPTCHA_API_KEY") is falsy; covered by test_solver_disabled and test_solver_no_key, both passing |
| 4 | solve_recaptcha submits to in.php and polls res.php; raises on ERROR_ responses | VERIFIED | `core/captcha.py:36-73` — _submit_recaptcha POSTs to _SUBMIT_URL, _poll_result GETs _RESULT_URL; raises RuntimeError when submit status != 1; test_solve_recaptcha_submit_error passes |
| 5 | Startup balance check sets balance_ok False when zero; logs WARNING when below threshold | VERIFIED | `core/captcha.py:127-149` — check_balance_at_startup sets balance_ok=False for 0.0 and ERROR_ZERO_BALANCE; logs WARNING when balance < low_threshold; tests test_zero_balance_disables_solver, test_low_balance_warning, test_balance_error_zero all pass |
| 6 | can_solve returns False once solve_count reaches max_solves_per_run | VERIFIED | `core/captcha.py:151-153` — `return self.balance_ok and self._solve_count < self._max_solves`; test_cap_enforced passes |
| 7 | The API key never appears in any log line or exception message | VERIFIED | test_key_not_logged and test_exception_logs_class_name_only pass; grep for `str(exc)` in captcha.py returns only the docstring comment, not actual usage; exception handlers log only `exc.__class__.__name__` |
| 8 | A CaptchaSolver is constructed fresh inside async_main from cfg.captcha + get_store() (not in BotService.__init__) so solve_count resets each run | VERIFIED | `core/orchestrator.py:235-239` — `_build_captcha_solver` helper calls `CaptchaSolver.from_config(cfg.captcha, get_store())`; BotService.__init__ has no solver construction; test_returns_none_when_disabled confirms |
| 9 | When captcha.enabled is true, the startup balance check runs via run_in_executor (never blocking the loop) | VERIFIED | `core/orchestrator.py:251-252` — `await loop.run_in_executor(None, captcha_solver.check_balance_at_startup)`; test_balance_check_uses_run_in_executor confirms executor dispatch |
| 10 | registry.assign_solver injects the solver onto each plugin as self._captcha_solver, mirroring assign_proxy | VERIFIED | `core/registry.py:93-100` — assign_solver(plugin) sets plugin._captcha_solver = self._captcha_solver; tests test_assign_solver_sets_attribute_to_solver and test_assign_solver_sets_none_when_no_solver pass |
| 11 | When a CAPTCHA is detected and a usable solver is present, the plugin attempts automated reCAPTCHA v2 solve before pausing | VERIFIED | `plugins/shopbot_plugin_amazon.py:89-156` — _solve_or_pause checks solver presence + can_solve() before attempting; check_availability calls _solve_or_pause when captcha_present; test_amazon_successful_solve_injects_token_no_manual_pause passes |
| 12 | The solve call is wrapped in run_in_executor + asyncio.timeout(120) so other plugin poll tasks are not blocked | VERIFIED | `plugins/shopbot_plugin_amazon.py:135-138` and `plugins/shopbot_plugin_bestbuy.py:117-120` — both contain `async with asyncio.timeout(120): token = await loop.run_in_executor(None, solver.solve_recaptcha, ...)`; source-scan tests confirm presence |
| 13 | On empty sitekey, solve failure, timeout, zero balance, or cap-hit, the plugin falls back to the EXISTING manual-pause path (_wait_user_action) — never a silent skip | VERIFIED | All fallback branches in _solve_or_pause call `await self._wait_user_action(...)`; tests cover: solver=None, can_solve() False, empty sitekey, solve exception, TimeoutError, invalid token — all 10 relevant tests pass |
| 14 | Amazon WAF (window.gokuProps present) gracefully falls back to manual pause (automated WAF injection is deferred) | VERIFIED | `plugins/shopbot_plugin_amazon.py:109-119` — evaluates _WAF_PROBE_JS; if truthy, logs INFO "Amazon WAF CAPTCHA detected -- auto-solve deferred" and calls _wait_user_action; test_amazon_waf_detected_falls_to_manual_pause passes; solve_amazon_waf() not called from plugin (test_amazon_source_does_not_call_solve_amazon_waf passes) |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/captcha.py` | CaptchaSolver class with from_config, check_balance_at_startup, can_solve, solve_recaptcha, solve_amazon_waf | VERIFIED | 203 lines, contains class CaptchaSolver; all methods present; min_lines 120 satisfied |
| `core/config_schema.py` | CaptchaConfig model + AppConfig.captcha field (no api_key field) | VERIFIED | CaptchaConfig at line 219; AppConfig.captcha at line 278; `'api_key' not in CaptchaConfig.model_fields` confirmed |
| `core/credentials.py` | TWOCAPTCHA_API_KEY in SECRET_KEYS | VERIFIED | Line 76 of credentials.py; runtime assertion passes |
| `core/orchestrator.py` | CaptchaSolver construction in async_main + balance check + pass to PluginRegistry | VERIFIED | _build_captcha_solver at line 235; run_in_executor balance check at line 252; captcha_solver= passed to PluginRegistry at line 254 |
| `core/registry.py` | assign_solver(plugin) method mirroring assign_proxy | VERIFIED | Lines 93-100; method exists, callable, injects _captcha_solver |
| `core/service.py` | Startup INFO log when captcha solving is enabled (no key logged) | VERIFIED | Lines 50-58; logs max_solves_per_run and low_balance_threshold; never reads API key here |
| `plugins/shopbot_plugin_amazon.py` | reCAPTCHA solve path with manual-pause fallback + WAF graceful fallback | VERIFIED | _solve_or_pause at line 89; all fallback paths present; asyncio.timeout(120) present |
| `plugins/shopbot_plugin_bestbuy.py` | best-effort reCAPTCHA solve path with manual-pause fallback | VERIFIED | _solve_or_pause at line 89; captcha_event in __init__ at line 48; asyncio.timeout(120) present |
| `tests/test_captcha.py` | CaptchaSolver unit tests (mocked requests) | VERIFIED | 21 test functions including CR-01/WR-02 regression tests; all pass |
| `tests/test_captcha_config.py` | CaptchaConfig defaults + YAML parsing + AppConfig.captcha presence | VERIFIED | 4 tests; all pass |
| `tests/test_captcha_wiring.py` | wiring tests: assign_solver, disabled->None, balance check call | VERIFIED | TestAssignSolver, TestBuildCaptchaSolver, TestOrchestratorBalanceCheck, TestStaggeredSetupAssignSolver, TestBotServiceStartupLog; all pass |
| `tests/test_captcha_plugin.py` | plugin solve-path + fallback unit tests (mocked solver + tab) | VERIFIED | 21 tests covering all behavioral branches including CR-02 regression; all pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `core/captcha.py CaptchaSolver.from_config` | `core/credentials.py get_store().get('TWOCAPTCHA_API_KEY')` | credential store lookup at construction | WIRED | `core/captcha.py:119` — `api_key = store.get("TWOCAPTCHA_API_KEY")` |
| `core/config_schema.py AppConfig` | `CaptchaConfig` | captcha field default-instance | WIRED | `core/config_schema.py:278` — `captcha: CaptchaConfig = CaptchaConfig()` |
| `core/orchestrator.py async_main` | `CaptchaSolver.from_config(cfg.captcha, get_store())` | fresh solver per run via _build_captcha_solver | WIRED | `core/orchestrator.py:239` — `return CaptchaSolver.from_config(cfg.captcha, get_store())` |
| `core/registry.py PluginRegistry` | `plugin._captcha_solver` | assign_solver injection | WIRED | `core/registry.py:100` — `plugin._captcha_solver = self._captcha_solver` |
| `core/orchestrator.py _staggered_setup` | `registry.assign_solver(plugin)` | per-plugin injection before setup | WIRED | `core/orchestrator.py:189` — `registry.assign_solver(plugin)` called alongside assign_proxy |
| `plugins/shopbot_plugin_amazon.py check_availability` | `self._captcha_solver.solve_recaptcha` | run_in_executor under asyncio.timeout(120) | WIRED | Lines 135-138 in _solve_or_pause; called from check_availability line 206 |
| `plugins/shopbot_plugin_amazon.py solve failure` | `self._wait_user_action(self.captcha_event, ...)` | existing manual-pause fallback | WIRED | Lines 102-106, 115-119, 123-127, 141-145, 150-154 — all failure branches call _wait_user_action |

### Data-Flow Trace (Level 4)

Not applicable. Phase 14 adds a service integration (HTTP-based solver) rather than a data-rendering component. The CaptchaSolver constructs data (tokens) consumed internally; there is no UI or dashboard component rendering dynamic DB data.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| TWOCAPTCHA_API_KEY registered in SECRET_KEYS | `python -c "from core.credentials import SECRET_KEYS; assert 'TWOCAPTCHA_API_KEY' in SECRET_KEYS"` | exit 0 | PASS |
| CaptchaConfig defaults correct; no api_key field | `python -c "from core.config_schema import AppConfig, CaptchaConfig; c=AppConfig(); assert c.captcha.enabled is False and c.captcha.max_solves_per_run==10; assert 'api_key' not in CaptchaConfig.model_fields"` | exit 0 | PASS |
| BestBuyPlugin has captcha_event | `python -c "... p=BestBuyPlugin(None); assert hasattr(p,'captcha_event')"` | exit 0 | PASS |
| PLUGIN_API_VERSION unchanged | `python -c "from core.plugin_base import PLUGIN_API_VERSION; assert PLUGIN_API_VERSION == 2"` | exit 0, value = 2 | PASS |
| Full test suite — no regressions | `python -m pytest -q` | 479 passed, 2 skipped | PASS |
| Phase 14 tests | `python -m pytest tests/test_captcha*.py -q` | 60 passed, 0 failed | PASS |

### Probe Execution

Step 7c: No `probe-*.sh` files declared in PLAN.md or SUMMARY.md; no conventional scripts/*/tests/ probes exist for this phase. SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ANTI-06 | 14-01, 14-02, 14-03 | User can enable CAPTCHA solving (reCAPTCHA v2) via opt-in captcha: flag with API key in CredentialStore, never in config.yml. Phase 14 scope: reCAPTCHA v2 end-to-end; Amazon WAF deferred. | SATISFIED | CaptchaConfig.enabled gate; TWOCAPTCHA_API_KEY in SECRET_KEYS only; reCAPTCHA v2 solve path wired in both plugins with manual-pause fallback; WAF deferred with documented followup at .planning/todos/pending/waf-auto-solve-followup.md |
| ANTI-07 | 14-01, 14-02, 14-03 | Bot checks CAPTCHA-solver account balance at startup, warns when balance is low, skips solver use when balance is zero. | SATISFIED | check_balance_at_startup sets balance_ok=False at 0.0 / ERROR_ZERO_BALANCE; WARNING logged below low_balance_threshold; can_solve() gates on balance_ok; run via run_in_executor in async_main |

STAB-03 is mapped to Phase 17 in the traceability table — not a Phase 14 gap.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `plugins/shopbot_plugin_bestbuy.py` | 269 | `TODO: verify ".a-dropdown-prompt" is correct for BestBuy cart` | Info | Pre-existing TODO from Phase auto_buy path; not introduced by Phase 14; references Open Question 2 from Phase 1 UAT validation. Not a debt marker for Phase 14 work. |

No TBD, FIXME, or XXX markers found in any Phase 14 modified files. The one TODO in bestbuy.py (line 269) is pre-existing from before Phase 14 and is in the auto_buy path, not the captcha path. No new debt markers introduced by Phase 14.

### Human Verification Required

#### 1. End-to-End reCAPTCHA v2 Auto-Solve

**Test:** Enable `captcha.enabled: true` in config.yml, set TWOCAPTCHA_API_KEY to a funded account, point the bot at a page showing a reCAPTCHA v2 widget, and run.
**Expected:** The CAPTCHA is solved automatically by 2captcha. The bot proceeds past the challenge page without displaying the manual-pause prompt. Solve count increments. No API key appears in log output.
**Why human:** Requires a live funded 2captcha account and a real reCAPTCHA v2 challenge page. The full HTTP submit/poll/JS-inject chain cannot be exercised in CI.

#### 2. Zero-Balance Guard (Live Account)

**Test:** Set TWOCAPTCHA_API_KEY to a zero-balance account and start the bot with captcha.enabled: true.
**Expected:** Startup log emits WARNING "2captcha balance is zero -- captcha solving disabled for this run". On a CAPTCHA encounter the bot shows the manual-pause prompt, not an error. No paid HTTP requests submitted.
**Why human:** Requires a real 2captcha account at exactly zero balance.

#### 3. Low-Balance Warning (Live Account)

**Test:** Set up an account with balance below low_balance_threshold (e.g., $0.50 when threshold is $1.00) and start the bot.
**Expected:** Startup log emits WARNING about low balance, but balance_ok remains True and the solver is still used. Manual check of startup log output.
**Why human:** Requires a funded 2captcha account at a controlled low-balance state.

### Gaps Summary

No gaps. All 14 must-haves are VERIFIED. All artifacts exist, are substantive, and are correctly wired. The 2 critical review findings (CR-01 CAPTCHA_NOT_READY typo, CR-02 JS injection escaping) and 3 warnings (WR-01 thread comment, WR-02 solve_amazon_waf guard, WR-03 json import location) are all resolved: core/captcha.py line 71 has the correct "CAPTCHA_NOT_READY" spelling; both plugins use `json.dumps(token)` for injection; solve_amazon_waf has a can_solve() guard; json is imported at module top-level.

Regression tests for CR-01 (test_captcha_not_ready_continues_polling, test_captcha_not_ready_no_runtime_error) and WR-02 (test_solve_amazon_waf_blocked_when_cannot_solve, test_solve_amazon_waf_blocked_when_balance_not_ok) all pass.

The WAF deferral is an approved, documented scope decision — .planning/todos/pending/waf-auto-solve-followup.md exists and the REQUIREMENTS.md ANTI-06 annotation explicitly records the user decision. This is not a gap.

Status is `human_needed` because live 2captcha integration tests cannot be automated: the end-to-end reCAPTCHA v2 solve, zero-balance behavior against a real account, and low-balance warning require real HTTP traffic to 2captcha's API which is outside CI scope.

---

_Verified: 2026-06-09T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
