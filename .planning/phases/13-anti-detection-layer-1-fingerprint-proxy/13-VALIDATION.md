---
phase: 13
slug: anti-detection-layer-1-fingerprint-proxy
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-09
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio 1.3.0 (`asyncio_mode=auto`, already installed) |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `python -m pytest -q <touched test file>` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task's targeted `pytest -q <file>`
- **After every plan wave:** Run `python -m pytest`
- **Before `/gsd:verify-work`:** Full suite green (no new failures vs baseline 359 passed, 2 skipped)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | ANTI-08, ANTI-04, ANTI-05 | T-13-01/02 | RED stub (test syntax valid) | unit | `python -c "import ast; ast.parse(open('tests/test_stealth.py').read())"` | ✅ W0 | ⬜ pending |
| 13-01-02 | 01 | 1 | ANTI-08, ANTI-04, ANTI-05 | T-13-01/02/09 | creds never logged; WebRTC leak blocked | unit | `python -m pytest tests/test_stealth.py -q` | ✅ | ⬜ pending |
| 13-02-01 | 02 | 1 | ANTI-04 | — | proxy disabled by default | unit | `python -m pytest tests/test_proxy_config.py -q` | ✅ | ⬜ pending |
| 13-02-02 | 02 | 1 | ANTI-04 | — | sample config proxy.enabled=false | unit | `python -c "import yaml; d=yaml.safe_load(open('sample.config.yml')); assert d.get('proxy',{}).get('enabled') is False; print('OK')"` | ✅ | ⬜ pending |
| 13-03-01 | 03 | 2 | ANTI-04, ANTI-05, ANTI-08 | T-13-09 | proxy assigned at setup path | unit | `python -m pytest tests/test_proxy_wiring.py tests/test_service.py tests/test_registry.py tests/test_orchestrator.py -q` | ✅ | ⬜ pending |
| 13-03-02 | 03 | 2 | ANTI-04, ANTI-05, ANTI-08 | — | stealth+proxy in amazon/bestbuy setup | unit | `python -m pytest tests/test_proxy_wiring.py tests/test_plugin_amazon.py tests/test_plugin_bestbuy.py -q` | ✅ | ⬜ pending |
| 13-03-03 | 03 | 2 | ANTI-04, ANTI-05, ANTI-08 | — | stealth+proxy in remaining plugins | unit | `python -m pytest tests/test_proxy_wiring.py tests/test_plugin_walmart.py tests/test_plugin_target.py tests/test_plugin_gamestop.py tests/test_plugin_squareenix.py tests/test_plugin_newegg.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. `pytest-asyncio==1.3.0` is already pinned with `asyncio_mode=auto` — no install task needed. Test files are created as part of each plan's TDD RED task.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fingerprint patches measurably reduce bot signals | ANTI-08 | Requires a real browser hitting a fingerprint probe | Launch bot, load CreepJS / bot.sannysoft, confirm window.chrome/plugins/languages/screen patched and no WebRTC real-IP leak |
| Live proxy rotation on real ban signal | ANTI-04, ANTI-05 | Requires a live banning endpoint + real proxy pool | Enable proxy config, trigger 403/429, observe rotation + retirement after 3 failures + 300s cooldown |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — infra exists)
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-09
