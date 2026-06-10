---
phase: 12
slug: stability-foundation
status: approved
nyquist_compliant: true
wave_0_complete: true
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
| **Quick run command** | `pytest -q <touched test file>` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~30 seconds (baseline: 354 passed, 2 skipped) |

---

## Sampling Rate

- **After every task commit:** Run the task's targeted `pytest -q <file>`
- **After every plan wave:** Run `pytest`
- **Before `/gsd:verify-work`:** Full suite must be green (≥ 354 passed, no new failures)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | STAB-02 | — | N/A | unit | `pytest -q tests/test_logger.py` | ✅ | ⬜ pending |
| 12-01-02 | 01 | 1 | STAB-02 | — | N/A | unit | `pytest -q tests/test_logger_config_path.py` | ✅ | ⬜ pending |
| 12-02-01 | 02 | 1 | STAB-02 | — | N/A | unit | `pytest -q tests/test_no_env_secret_reads.py` | ✅ | ⬜ pending |
| 12-02-02 | 02 | 1 | STAB-02 | — | N/A | unit | `pytest -q tests/test_paths.py` | ✅ | ⬜ pending |
| 12-03-01 | 03 | 1 | STAB-01, STAB-02 | — | N/A | unit | `pytest -q tests/test_web_config.py tests/test_web_credentials.py` | ✅ | ⬜ pending |
| 12-03-02 | 03 | 1 | STAB-01 | — | N/A | unit | `pytest -q tests/test_web_dashboard.py` | ✅ | ⬜ pending |
| 12-04-01 | 04 | 2 | STAB-01 | — | N/A | checkpoint:human-verify | — (manual MC-1..MC-4 execution) | n/a | ⬜ pending |
| 12-04-02 | 04 | 2 | STAB-01 | — | N/A | checkpoint:human-verify | — (manual-result transcription to docs/PLATFORMS.md) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements — all regression tests are additions to existing test files. No Wave 0 scaffolding needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Keyring restart survival (MC-1) | STAB-01 | Requires OS keyring + process restart | See docs/PLATFORMS.md repro steps |
| Masked-TTY passphrase prompt (MC-2) | STAB-01 | Requires real interactive TTY | See docs/PLATFORMS.md repro steps |
| Web dashboard live render on Ubuntu (MC-3) | STAB-01 | Requires real browser + Ubuntu host | See docs/PLATFORMS.md repro steps (mark "pending Ubuntu access" if no host) |
| `0.0.0.0` bind banner live render (MC-4 manual half) | STAB-01 | Live render confirmation on real host | See docs/PLATFORMS.md (automated TestClient assertion in 12-03-02 covers the HTML) |

*MC-4 has an automatable TestClient assertion (task 12-03-02) plus a manual live-render confirmation.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or are checkpoint:human-verify (12-04 manual checks)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (Wave 1 all automated)
- [x] Wave 0 covers all MISSING references (none needed — existing infra)
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-09
