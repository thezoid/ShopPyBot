---
phase: 11
slug: cross-platform-verification
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-04
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (existing) + a new env-independent smoke module |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `pytest tests/test_paths.py tests/test_smoke.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_paths.py tests/test_smoke.py -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd:verify-work`:** Full suite green (335 baseline + new path/smoke tests; must stay green after the path re-anchor + migration)
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|----------|-----------|-------------------|-------------|--------|
| 11-01 | 01 | 1 | XPLAT-01 | core/paths.py (platformdirs) resolves data/config/log to OS-standard dirs; SHOPBOT_DATA_DIR override; no hardcoded separators | unit | `pytest tests/test_paths.py -q` | ❌ W0 | ⬜ pending |
| 11-02 | 02 | 2 | XPLAT-01 | models/config_schema/credentials/logger anchor through core/paths.py; models.py CWD bug fixed; existing suite stays green | unit | `pytest tests/test_paths.py tests/test_models.py tests/test_credentials.py -q` | ❌ W0 | ⬜ pending |
| 11-03 | 03 | 2 | XPLAT-01 | idempotent first-run migration of legacy DB/creds.bin/config.yml/logs (copy2→unlink); logs paths only, never secrets | unit | `pytest tests/test_migration.py -q` | ❌ W0 | ⬜ pending |
| 11-04 | 04 | 3 | XPLAT-02 | env-independent smoke (import + --help/items/config show + path resolution); backend-per-OS via mocked _has_real_keyring | unit | `pytest tests/test_smoke.py tests/test_backend_selection.py -q` | ❌ W0 | ⬜ pending |
| 11-05 | 05 | 3 | XPLAT-02 | .github/workflows/ci.yml matrix (ubuntu+windows, py3.13, pip install .[web], pytest); docs/PLATFORMS.md path table + backend-per-env + repro + manual matrix | doc/ci | `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"` + `test -f docs/PLATFORMS.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs indicative — planner finalizes exact plan/task numbering.*

---

## Wave 0 Requirements

- [ ] `tests/test_paths.py` — paths.py resolution + override + no-separator grep guard
- [ ] `tests/test_migration.py` — idempotent legacy migration; no plaintext secret relocation
- [ ] `tests/test_smoke.py` — env-independent import + CLI smoke
- [ ] `tests/test_backend_selection.py` — mocked _has_real_keyring → keyring vs file
- [ ] `tests/conftest.py` — extend tmp_data_dir fixture to monkeypatch core/paths.py resolution

*Existing pytest infrastructure covers framework; new test files + platformdirs dep needed.*

---

## Manual-Only Verifications (the milestone-closing matrix)

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full CLI + backends on Ubuntu desktop | XPLAT-02 | Requires real Linux desktop w/ Secret Service | Run the docs/PLATFORMS.md matrix: --help, setup, run smoke, items, config, web; confirm keyring backend |
| Full CLI + backends on Ubuntu headless | XPLAT-02, CRED-03 | Requires real headless Linux (no Secret Service) | Same matrix; confirm encrypted-file backend auto-selected; data/log under ~/.local/share & ~/.local/state |
| Full CLI + backends on Windows | XPLAT-02 | Requires Windows (this dev box covers it) | Same matrix; confirm keyring (Credential Manager); data under %LOCALAPPDATA%\shoppybot |
| OS keyring secret survives process restart (deferred Phase 8) | CRED-02 | Live OS keyring | setup a secret, restart, confirm retrieval with no env var |
| setup masked TTY entry (deferred Phase 9) | CLI-02 | Live terminal | shoppybot setup in PowerShell + Ubuntu terminal; no echo; name-only confirm |
| Dashboard renders + live polling + non-local banner (deferred Phase 10) | GUI-01/04/06 | Live browser | pip install .[web]; shoppybot web; verify sections, polling, --host 0.0.0.0 banner |

*The CI matrix (ci.yml) covers the automated half on ubuntu-latest + windows-latest; the table above is the human half on real desktop/headless hardware.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 35s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-04
