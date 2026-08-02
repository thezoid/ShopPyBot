---
phase: 20
slug: checkout-profile-form-fill
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-11
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (asyncio_mode=auto) |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `pytest tests/test_checkout_profile.py tests/test_setup.py tests/test_amazon_plugin.py tests/test_bestbuy_plugin.py` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~30-60 seconds |

---

## Sampling Rate

- **After every task commit:** Run touched test files
- **After every plan wave:** Run `pytest`
- **Before verify:** Full suite green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task | Requirement | Secure Behavior | Test Type | Command | Status |
|------|-------------|-----------------|-----------|---------|--------|
| profile-keys | BUY-07 | CHECKOUT_PROFILE_KEYS (9) defined, NOT in SECRET_KEYS; round-trip via fake store; migrate_from_env unaffected | unit | `pytest tests/test_credentials.py` | ⬜ pending |
| profile-model | BUY-07 | CheckoutProfile loads 9 keys from store; incomplete detection when a required key missing; ADDRESS_LINE2 optional | unit | `pytest tests/test_checkout_profile.py` | ⬜ pending |
| setup-cmd | BUY-07 | `setup checkout-profile` stores 9 keys (key NAME only in output, never values); no card/CVV stored | unit | `pytest tests/test_setup.py` | ⬜ pending |
| cvv-thread | BUY-07 | Amazon _cvv injected (mirrors BestBuy); needs_cvv includes amazon.com; _cvv never persisted | unit | `pytest tests/test_orchestrator.py tests/test_cli_run.py` | ⬜ pending |
| formfill-bestbuy | BUY-07 | BestBuy fills shipping fields from profile before place_order_guarded; CVV from runtime value | unit | `pytest tests/test_bestbuy_plugin.py` | ⬜ pending |
| formfill-amazon | BUY-07 | Amazon fills shipping fields; CVV field skip-if-absent (context-dependent) | unit | `pytest tests/test_amazon_plugin.py` | ⬜ pending |
| missing-selector | BUY-07 | shipping field selector None → WARNING(selector name) + return False, no submit | unit | `pytest tests/test_bestbuy_plugin.py tests/test_amazon_plugin.py` | ⬜ pending |
| cvv-not-in-logs | BUY-07 | AST scan: no `_cvv` in any writeLog() arg on checkout paths | unit | `pytest tests/test_no_cvv_in_logs.py` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_checkout_profile.py` — new: CheckoutProfile load + incomplete detection
- [ ] `tests/test_no_cvv_in_logs.py` — new: AST-walk no-`_cvv`-in-writeLog (model on tests/test_no_env_secret_reads.py)
- [ ] `tests/test_setup.py` — extend for `setup checkout-profile`
- [ ] Existing fake-store + fake-tab fixtures (conftest.py)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live BestBuy + Amazon shipping form-fill against the real checkout DOM | BUY-07 | Requires live retailer checkout; shipping selectors are MEDIUM/LOW confidence; send_keys may need synthetic input event for SPA fields | Deferred as UAT debt: run a real test_mode buy, confirm each shipping field fills correctly and CVV enters; update selectors in plugin if DOM drifted |
| CVV actually entered into the live CVV field | BUY-07 | Live-only; BestBuy `#credit-card-cvv` HIGH but Amazon CVV field context-dependent | Deferred as UAT debt |

*All non-DOM behaviors have automated verification (incl. the CVV-not-in-logs AST guard).*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
