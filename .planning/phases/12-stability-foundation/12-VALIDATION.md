---
phase: 12
slug: stability-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-09
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini / pyproject.toml (existing) |
| **Quick run command** | `pytest -q` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~30 seconds (baseline: 354 passed, 2 skipped) |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q <touched test file>`
- **After every plan wave:** Run `pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | STAB-02 | — | N/A | unit | `pytest -q tests/` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — planner refines this map per task.*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements — regression tests are additions to existing test files.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Keyring restart survival (MC-1) | STAB-01 | Requires OS keyring + process restart | See docs/PLATFORMS.md repro steps |
| Masked-TTY passphrase prompt (MC-2) | STAB-01 | Requires real interactive TTY | See docs/PLATFORMS.md repro steps |
| Web dashboard live render on Ubuntu (MC-3) | STAB-01 | Requires real browser + Ubuntu host | See docs/PLATFORMS.md repro steps |

*MC-4 (`0.0.0.0` bind banner) has an automatable TestClient assertion — not manual-only.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
