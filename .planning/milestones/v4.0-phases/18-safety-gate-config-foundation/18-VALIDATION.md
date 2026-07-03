---
phase: 18
slug: safety-gate-config-foundation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-11
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (asyncio_mode=auto) |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `pytest tests/test_plugin_base.py tests/test_config_schema.py tests/test_orchestrator.py` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~30-60 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command (touched test files)
- **After every plan wave:** Run `pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|--------|
| 18-cfg | config | 1 | BUY-01 | CheckoutConfig defaults + ge bounds reject negatives; monitor_only defaults False | unit | `pytest tests/test_config_schema.py` | ⬜ pending |
| 18-abc | abc | 1 | BUY-02 | place_order_guarded suppresses click_fn (returns False, no call) when monitor_only OR test_mode | unit | `pytest tests/test_plugin_base.py` | ⬜ pending |
| 18-orch | orchestrator | 2 | BUY-01 | _check_and_buy never calls _try_auto_buy when monitor_only; alert still dispatched | unit | `pytest tests/test_orchestrator.py` | ⬜ pending |
| 18-plugins | plugins | 2 | BUY-02 | all 7 plugins route place-order via place_order_guarded; zero purchase-queue writes under monitor_only=True | integration | `pytest tests/test_safety_gate.py` | ⬜ pending |
| 18-grep | plugins | 2 | BUY-02 | AST/grep assertion: no plugin clicks the place-order element outside place_order_guarded | unit | `pytest tests/test_safety_gate.py` | ⬜ pending |
| 18-cli | cli | 2 | BUY-01 | --monitor-only sets cfg.debug.monitor_only=True; config ALLOWLIST accepts monitor_only | unit | `pytest tests/test_cli_run.py` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_safety_gate.py` — new file: 7-plugin monitor_only zero-write assertion + AST/grep guard-usage assertion
- [ ] Existing `tests/conftest.py` — reuse `fake_browser` / `fake_plugin` fixtures (confirmed present)

*Existing infrastructure (pytest, asyncio_mode=auto, fake_browser/fake_plugin) covers all other phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `--monitor-only` run fires real stock alerts but places no order on a real retailer | BUY-01 | Requires live retailer + browser session; cannot run on CI/Windows dev box autonomously | Deferred as UAT debt: run `python main.py --monitor-only` against a real in-stock item, confirm alert fires and no order placed |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
