---
phase: 19
slug: db-schema-confirmation-detection
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-11
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (asyncio_mode=auto) |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `pytest tests/test_models.py tests/test_confirmation.py tests/test_orchestrator.py` |
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
| migration | BUY-04 | order_id/confirmed_at/checkout_attempts added idempotently; v3.0-schema DB migrates losslessly; re-run safe; checkout_attempts NOT NULL DEFAULT 0 | unit | `pytest tests/test_models.py` | ⬜ pending |
| confirmation-url | BUY-03 | detect_order_confirmation returns order_id on matching thankyou URL (Amazon orderID query param parsed); None on non-match | unit | `pytest tests/test_confirmation.py` | ⬜ pending |
| confirmation-sentinel | BUY-03 | URL match without extractable id returns CONFIRMED-<ts> sentinel (non-None) + WARNING | unit | `pytest tests/test_confirmation.py` | ⬜ pending |
| write-confirmed | BUY-04 | ("confirmed", link, order_id, ts) sets purchased=1 + order_id + confirmed_at together | unit | `pytest tests/test_models.py` | ⬜ pending |
| orch-confirmed | BUY-03 | after auto_buy True, confirmed order enqueues ("confirmed",...); purchased=1 only then | unit | `pytest tests/test_orchestrator.py` | ⬜ pending |
| orch-fallback | BUY-03 | no detection → WARNING + legacy ("purchased", link) fallback (no silent failure) | unit | `pytest tests/test_orchestrator.py` | ⬜ pending |
| get-active-tab | BUY-03 | get_active_tab() returns _last_tab or main_tab fallback; additive, no API bump | unit | `pytest tests/test_plugin_base.py` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_confirmation.py` — new file: FakeTab (async sleep no-op, target.url / evaluate stubs) per-platform URL/DOM/sentinel cases
- [ ] `tests/test_models.py` — extend: v3.0-schema migration fixture + idempotent re-run + update_item_confirmed_sync
- [ ] Existing `tests/conftest.py` — reuse tmp_data_dir DB isolation fixture

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Amazon/BestBuy confirmation-page URL pattern + DOM order-number selector match a live test_mode buy | BUY-03 | Requires live retailer checkout to the confirmation page; cannot run on CI/Windows dev box. DOM selectors are LOW-confidence/assumed | Deferred as UAT debt: run a real test_mode buy, capture the confirmation URL + order-number element, verify detect_order_confirmation captures the real order_id (not just the sentinel) |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
