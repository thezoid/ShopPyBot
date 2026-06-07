---
phase: 2
slug: plugin-migration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-02
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.4 + pytest-asyncio 1.3.0 (asyncio_mode=auto in pyproject.toml) |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/ -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~2 seconds (unit); browser-backed checks excluded from suite |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -q`
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

> Planner refines per task. Requirement→test mapping below is the contract.

| Requirement | Test Type | Approach | Live browser? |
|-------------|-----------|----------|---------------|
| ABC v2 (async, self.driver, setup/teardown, PLUGIN_API_VERSION=2, domain_patterns) | unit | Rewrite tests/test_plugin_base.py: assert version==2, abstract enforcement, async no-op defaults | no |
| CORE-03 (importlib discovery, warn+ignore non-matching) | unit | Drop fixture plugin files in tmp_path; assert registry loads valid, logs warning + ignores bad name / import error without raising | no |
| CORE-04 (domain_patterns routing on urlparse host) | unit | Assert registry.route(url) returns correct plugin by hostname substring; multi-domain + non-match cases | no |
| PLG-03 (per-plugin self.driver, no global) | unit | Assert each plugin instance builds its own driver in setup(); no module-global driver references | no (mock nodriver.start) |
| PLG-01 / PLG-02 (Amazon/BestBuy ported) | unit + manual | Unit: instantiate plugin, mock tab/element to assert check_availability bool + auto_buy flow branches; PLG-02: assert update_item_purchased called after successful buy | partial (mock) |
| PLG-02 fix (update_item_purchased after purchase) | unit | Mock the buy flow to success; assert models.update_item_purchased invoked | no |
| Lifecycle (eager discovery, lazy setup, teardown) | unit | Assert setup() awaited only for plugins with matching items; teardown() on shutdown | no (mock) |
| CORE-08 (example_plugin.py + PLUGIN_DEV.md) | manual + lint | example_plugin imports + instantiates cleanly; PLUGIN_DEV.md covers the 4 contributor steps (criterion 4) | no |
| Full async loop in main.py | manual | Live cold-start run: bot boots async, discovers plugins, checks an item end-to-end | yes |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_plugin_base.py` — REWRITE for ABC v2 (async stubs, PLUGIN_API_VERSION==2). The existing 5 tests assert v1 sync contract and WILL break; rewrite before touching `core/plugin_base.py`.
- [ ] `pytest-asyncio` smoke test — confirm `@pytest.mark.asyncio` / `asyncio_mode=auto` runs an `async def test_` (version 1.3.0 unverified per research).
- [ ] `tests/conftest.py` — add fixtures for a fake nodriver Browser/Tab/Element + tmp_path plugins dir if needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real availability/buy DOM interaction on live retailer pages | PLG-01, PLG-02 | Requires live Amazon/BestBuy pages + a real browser; selectors can drift; auto_buy gated by test_mode | Run `python main.py` with test_mode true and a real item; confirm async plugin checks the item and logs availability |
| End-to-end async cold start | phase goal | Needs a live nodriver Chrome process | Fresh `python main.py`: bot boots async, registry discovers plugins, lazy-launches a browser for the matched plugin, checks first item |
| CVV getpass in async context | PLG-02 | Hidden terminal prompt, interactive | Configure a BestBuy auto_buy item, test_mode false, interactive terminal; confirm CVV prompt fires once at startup before the async loop |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
