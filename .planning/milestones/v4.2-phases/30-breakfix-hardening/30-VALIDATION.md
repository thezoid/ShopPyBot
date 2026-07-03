---
phase: 30
slug: breakfix-hardening
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-02
---

# Phase 30 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `30-RESEARCH.md` §Validation Architecture. Live-environment proof
> (WAF challenge, place-order double-buy edge, per-retailer selectors) is explicit
> operator debt per REQUIREMENTS.md Out-of-Scope — NOT gated here.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.4 + pytest-asyncio 1.3.0 (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"]) |
| **Quick run command** | `pytest tests/test_cart_retry.py tests/test_retry.py tests/test_no_retry_loops.py tests/test_captcha.py tests/test_captcha_plugin.py tests/test_plugin_base.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~30–60 seconds (existing suite) |

---

## Sampling Rate

- **After every task commit:** Run the breakfix's quick-run subset (see per-requirement map)
- **After every plan wave:** `pytest tests/ -q -k "cart_retry or retry or captcha or plugin or relaunch or models or orchestrator"`
- **Before `/gsd:verify-work`:** `pytest -q` (full suite) must be green
- **Max feedback latency:** ~60 seconds

---

## Per-Requirement Verification Map

> Task-ID granularity is reconciled during execution; tasks do not exist at plan-time.
> Every row maps to an existing test file (Wave 0 gaps: none).

| Requirement | Behavior | Threat Ref | Test Type | Automated Command | File Exists |
|-------------|----------|------------|-----------|-------------------|-------------|
| BF-02 | Timeout at place-order → item marked non-retryable, no second click | T-30-02 | unit | `pytest tests/test_cart_retry.py -x` (new `test_possibly_placed_aborts_retry`) | ✅ |
| BF-02 | `_pre_attempt_check` raises possibly-placed abort when marker set + no order_id | T-30-02 | unit | `pytest tests/test_orchestrator.py -x` | ✅ |
| BF-02 | DB marker column + accessors round-trip; idempotent migration on legacy schema | — | unit | `pytest tests/test_models.py -x` | ✅ |
| BF-02 | Operator alert fires exactly once on attempted-but-unconfirmed state | — | unit | `pytest tests/test_cart_retry.py -x` (`fake_notifier` fixture) | ✅ |
| BF-02 | BestBuy place-order timeout also latched (parity, live-tested plugin) | T-30-02 | unit | `pytest tests/test_plugin_bestbuy.py -x` | ✅ |
| BF-01 | WAF detected + solver available → `solve_amazon_waf` called, token injected, no manual pause | T-30-01 | unit | `pytest tests/test_captcha_plugin.py -x` (REWRITE `test_amazon_waf_detected_falls_to_manual_pause`) | ✅ rewrite |
| BF-01 | WAF detected + solver unavailable/fails → manual pause, graceful | T-30-01 | unit | `pytest tests/test_captcha_plugin.py -x` | ✅ rewrite |
| BF-01 | Voucher/token string escaping before `tab.evaluate()` injection (V5) | T-30-01 | unit | `pytest tests/test_captcha_plugin.py -x -k inject` | ✅ |
| BF-03 | `login()` returns `False` on missing creds / missing DOM field / exception (all 7 plugins) | T-30-03 | unit | `pytest tests/test_plugin_amazon.py tests/test_plugin_bestbuy.py tests/test_plugin_walmart.py tests/test_plugin_target.py tests/test_plugin_gamestop.py tests/test_plugin_newegg.py tests/test_plugin_squareenix.py -x` | ✅ |
| BF-03 | `login()` returns `True` only when post-login signal passes; ambiguous → `False` | T-30-03 | unit | `pytest tests/test_plugin_base.py -x` (REWRITE `test_login_noop`) | ✅ rewrite |
| BF-03 | `relaunch()` handles failed re-login without treating as authenticated | T-30-03 | unit | `pytest tests/test_relaunch.py -x` | ✅ |
| BF-03 | `auto_buy()` aborts before place-order when `login()` is `False` (all 7 plugins) | T-30-03 | unit | same 7 plugin test files | ✅ |

*Status column reconciled at execution: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*None — every test file this phase needs already exists (canonical_refs "Tests to extend"). No new test files, no new fixtures, no framework installs. `conftest.py` already provides `tmp_data_dir`, `fake_notifier`, `fake_plugin`, `mock_nodriver_start`, `event_shim`.*

**Note:** three existing tests assert PRE-FIX behavior and must be rewritten (not supplemented):
`test_amazon_waf_detected_falls_to_manual_pause` + `test_amazon_source_does_not_call_solve_amazon_waf` (`tests/test_captcha_plugin.py`), and `test_login_noop` (`tests/test_plugin_base.py`).

---

## Security Domain (ASVS L1)

| ASVS Category | Applies | Control |
|---------------|---------|---------|
| V2 Authentication | Yes (BF-03) | Real post-login DOM/URL signal; ambiguous = failed (D-13) |
| V5 Input Validation | Yes (BF-01) | WAF `captcha_voucher`/`existing_token` go through the same quote/backslash/newline rejection + `json.dumps()` escaping as reCAPTCHA before `tab.evaluate()` interpolation |
| V7 Error Handling / Logging | Yes | Preserve `exc.__class__.__name__`-only logging (no `str(exc)`) in all new BF-01/02/03 handlers; never log the 2captcha key or credentials |

**Threat refs for PLAN `<threat_model>` blocks:**
- **T-30-01** (Tampering): untrusted solver response interpolated into JS → escaping mitigation (BF-01).
- **T-30-02** (Integrity/Repudiation): business-logic double-submission → DB write-ahead marker + non-retryable guard (BF-02, the fix itself).
- **T-30-03** (Spoofing): false-positive auth state → real post-login signal, ambiguous-defaults-failed (BF-03, the fix itself).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live AWS-WAF challenge solved within ~30s gokuProps window | BF-01 | Needs a real challenge; unverifiable in CI | Operator debt (REQUIREMENTS Out-of-Scope) |
| Place-order double-buy edge under real slow-drop | BF-02 | Needs a live slow retail drop | Operator debt (REQUIREMENTS Out-of-Scope) |
| Per-retailer login-selector accuracy (5 community plugins) | BF-03 | Verifiable only against live storefronts | Operator debt (selector-TODO bucket) |

*All in-scope (mocked-external) behaviors have automated verification per the map above.*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (N/A — no gaps)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter (set at execution close)

**Approval:** pending
