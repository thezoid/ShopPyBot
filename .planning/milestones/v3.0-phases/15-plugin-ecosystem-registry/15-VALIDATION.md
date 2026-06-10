---
phase: 15
slug: plugin-ecosystem-registry
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-09
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (+ pytest-asyncio, installed) |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `python -m pytest -q <touched test file>` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task's targeted `pytest -q <file>`
- **After every plan wave:** Run `python -m pytest`
- **Before `/gsd:verify-work`:** Full suite green (no new failures vs Phase 14 baseline of 479 passed, 2 skipped)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 1 | REG-02 | — | additive ABC attrs; existing plugins load | unit | `python -m pytest tests/test_plugin_base.py -q` | ✅ | ⬜ pending |
| 15-01-02 | 01 | 1 | REG-02 | — | difficulty validated via __init_subclass__ | unit | `python -m pytest tests/test_plugin_base.py -q` | ✅ | ⬜ pending |
| 15-03-01 | 03 | 1 | REG-01, REG-04 | — | wiki SPEC doc has all 9 fields | doc-check | `python -c "...docs/PLUGIN_REGISTRY.md field check..."` | ✅ | ⬜ pending |
| 15-03-02 | 03 | 1 | REG-01, REG-04 | — | CONTRIBUTING/PR/PLUGIN_DEV require new fields | doc-check | `python -c "...token check in 3 docs..."` | ✅ | ⬜ pending |
| 15-03-03 | 03 | 1 | REG-01, REG-04 | — | docs presence asserted | unit | `python -m pytest tests/test_docs.py -q` | ✅ | ⬜ pending |
| 15-02-01 | 02 | 2 | REG-03 | — | RED stub (CLI tests) | unit | `python -m pytest tests/test_cli_plugins.py -q \|\| true` | ✅ | ⬜ pending |
| 15-02-02 | 02 | 2 | REG-03 | — | list_plugins() reads _all_plugins, no network | unit | `python -c "...BotService().list_plugins() assertions..."` | ✅ | ⬜ pending |
| 15-02-03 | 02 | 2 | REG-03 | — | plugins list table + --json, no network | unit | `python -m pytest tests/test_cli_plugins.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Test files (`test_plugin_base.py`, `test_cli_plugins.py`, `test_docs.py`) created as each plan's first task; `tests/test_cli_items.py` is the CLI mirror. No new deps; pytest-asyncio installed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GitHub wiki registry table populated | REG-01 | The wiki is an external GitHub surface, not in-repo | After merge, create/populate the wiki table per docs/PLUGIN_REGISTRY.md spec |

*The in-repo SPEC doc, CLI, ABC attrs, CONTRIBUTING.md, PR template, and PLUGIN_DEV.md are all automated; only the live wiki population is manual/external.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-09
