---
phase: 6
slug: platform-expansion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-03
---

# Phase 6 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.4 + pytest-asyncio 1.3.0 (asyncio_mode=auto) |
| **Config file** | pyproject.toml |
| **Quick run** | `.venv/Scripts/python.exe -m pytest tests/ -q` |
| **Full suite** | `.venv/Scripts/python.exe -m pytest tests/ -q` |
| **Runtime** | ~3s (registry/config/jitter unit tests; no live browser, no live retail) |

## Sampling Rate

- After every task commit: quick run
- After every wave: full suite
- Before verify-work: full suite green
- Max latency: ~5s

## Per-Requirement Verification Map

| Requirement | Test Type | Approach | Live? |
|-------------|-----------|----------|-------|
| PLG-04..08 (5 plugins load, self-contained) | unit | Registry discovers all 5 shopbot_plugin_*.py; each subclasses RetailerPlugin v2, sets domain_patterns + platform_key, has async check_availability/auto_buy, no module-global driver, no direct update_item_purchased (write queue owns writes) | no |
| SC1 (5 load, no core edits) | unit | Drop the 5 files in a tmp plugins dir; registry loads all 5 with no import error | no |
| ANTI-01 (jitter) | unit | `_get_plugin_sleep` returns a value within [min_delay, max_delay] when platform config sets them; falls back to shared poll_interval otherwise; setting walmart min=8/max=15 yields 8..15 | no |
| ANTI-03 (headless per platform) | unit | Plugin setup() passes its `headless` flag to nodriver.start(headless=...); mock nodriver.start, assert the kwarg per plugin; mixed values across plugins | no (mock) |
| ANTI-02 (rotating UA) | unit | UA selected from the configured list (global pool + per-platform override); applied via browser_args --user-agent; assert selection logic | no (mock) |
| SC2 (config-only jitter) | unit | Changing config min/max changes the sleep range with NO code change | no |
| SC3 (mixed headless in one process) | unit | Two plugins, one headless true one false; assert each setup() gets its own flag | no (mock) |
| SC4 (risk docs) | unit/static | Each plugin docstring contains its risk level + reason; SECURITY.md table has a row per platform; assert exact phrases "PerimeterX/HUMAN Security" (Walmart) and "Akamai"+"headless" (Target) | no |

## Wave 0 Requirements

- [ ] `tests/conftest.py` — a tmp plugins-dir fixture (may already exist from Phase 2) and a mock nodriver.start to assert headless/UA kwargs without launching Chrome.
- [ ] config_schema: per-platform min_delay/max_delay/headless/user_agents fields + global default UA pool constant — covered by a config test before plugins/orchestrator depend on them.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Instructions |
|----------|-------------|------------|--------------|
| Live availability detection per site | PLG-04..08 | Selectors unverifiable here; sites are bot-protected | Run against a real item per site; confirm/adjust selectors (each has a TODO marker) |
| Live auto-buy on each site | PLG-04..08 | Bot-protected; experimental; NOT a success criterion | Out of scope for acceptance; experimental warnings logged |
| Real jitter/headless in a live multi-platform run | SC2/SC3 | Needs live browsers | Set walmart min/max + amazon headless:false; observe varied intervals + one visible browser among headless |

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependency
- [ ] No 3 consecutive tasks without automated verify
- [ ] Wave 0 covers config fields + mock nodriver fixture
- [ ] No watch-mode flags
- [ ] Live retail behavior correctly excluded from acceptance (success criteria are framework/config/docs, not live purchasing)
- [ ] nyquist_compliant: true when complete

**Approval:** pending
