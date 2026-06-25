---
phase: 21
slug: per-step-timeouts-unified-retry-cart-retry
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-11
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (asyncio_mode=auto) |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `pytest tests/test_retry.py tests/test_cart_retry.py tests/test_no_retry_loops.py tests/test_orchestrator.py` |
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
| retry-module | REL-08 | RetryPolicy + compute_delay deterministic with injected rng; with_retry stops after max_attempts | unit | `pytest tests/test_retry.py` | ⬜ pending |
| no-retry-loops | REL-08 | AST scan: no `for attempt in range(` retry loop outside core/retry.py (poll loops with `_` not flagged) | unit | `pytest tests/test_no_retry_loops.py` | ⬜ pending |
| models-helpers | BUY-05 | increment_checkout_attempts_sync(+1); get_item_order_state_sync returns (purchased, order_id) | unit | `pytest tests/test_models.py` | ⬜ pending |
| per-step-timeout | BUY-06 | each DOM stage under asyncio.timeout(step_timeout_secs); _checkout_stage set per stage; logged on cancel | unit | `pytest tests/test_amazon_plugin.py tests/test_bestbuy_plugin.py` | ⬜ pending |
| cart-retry | BUY-05 | retry ≤ max_cart_retries w/ backoff; re-reads order_id before each attempt; confirmed order_id → exit, zero re-submit | unit | `pytest tests/test_cart_retry.py` | ⬜ pending |
| attempts-increment | BUY-05 | checkout_attempts increments once per attempt, before each | unit | `pytest tests/test_cart_retry.py` | ⬜ pending |
| enqueue-outside | BUY-05 | confirmation/purchased enqueue stays outside retry+timeout (no double enqueue) | unit | `pytest tests/test_orchestrator.py` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_retry.py` — new: RetryPolicy/compute_delay/with_retry
- [ ] `tests/test_cart_retry.py` — new: orchestrator cart-retry + idempotency + increment
- [ ] `tests/test_no_retry_loops.py` — new: AST guard (model on tests/test_no_cvv_in_logs.py)
- [ ] Existing fake-tab/fake-plugin fixtures (conftest.py)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Per-step timeouts fire cleanly under a real slow drop (no half-submitted order, no orphaned browser) | BUY-06 | Requires live retailer checkout under real latency | Deferred as UAT debt: run a real test_mode buy, induce a slow step, confirm clean abort + stage logged |

*All non-live behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
