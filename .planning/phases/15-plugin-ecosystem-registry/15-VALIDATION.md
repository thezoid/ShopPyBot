---
phase: 15
slug: plugin-ecosystem-registry
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| 15-01-01 | 01 | 1 | REG-02 | — | additive ABC attrs; existing plugins still load | unit | `python -m pytest tests/test_plugin_attrs.py -q` | ❌ W0 | ⬜ pending |

*Planner refines this map. The ABC default attributes, difficulty validation, and the `plugins list` CLI (stdout capture, table + --json, no network) are all unit-testable. Docs tasks verify via file-presence/content grep.*

---

## Wave 0 Requirements

- [ ] `tests/test_plugin_attrs.py` / `tests/test_cli_plugins.py` — ABC default + CLI stdout tests (mirror `tests/test_cli_items.py`)

*No new deps; pytest-asyncio already installed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GitHub wiki registry table populated | REG-01 | The wiki is an external GitHub surface, not in-repo | After merge, create/populate the wiki table per docs/PLUGIN_REGISTRY.md spec |

*The in-repo registry SPEC doc, CLI, ABC attrs, CONTRIBUTING.md, and PR template are all automatable; only the live wiki population is manual/external.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
