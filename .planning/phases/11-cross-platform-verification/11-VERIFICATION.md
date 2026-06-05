---
phase: 11-cross-platform-verification
verified: 2026-06-05T06:00:00Z
status: human_needed
score: 4/4
overrides_applied: 0
human_verification:
  - test: "Run shoppybot --help, items list, config show, and setup on Ubuntu desktop (GNOME/KDE with Secret Service active). Confirm each exits 0 and the keyring backend is selected."
    expected: "All four commands exit 0; log or terminal output shows 'KeyringBackend' selected; no D-Bus errors."
    why_human: "CI matrix uses PYTHON_KEYRING_BACKEND=null to suppress D-Bus; a real desktop session with an active Secret Service cannot be replicated by grep."
  - test: "Run the same four commands on Ubuntu headless (no active D-Bus/Secret Service, e.g. a plain SSH session or a headless runner without PYTHON_KEYRING_BACKEND override). Set SHOPBOT_STORE_PASSPHRASE to a throwaway value."
    expected: "Commands exit 0; 'EncryptedFileBackend' selected; no hang waiting for D-Bus."
    why_human: "Real headless Ubuntu environment cannot be simulated locally on Windows; the mocked backend-selection test proves logic, not the live _has_real_keyring() probe on a real headless system."
  - test: "Confirm keyring secret survives process restart on Windows (Phase 8 deferred): run shoppybot setup, exit completely, unset any credential env vars, then run shoppybot config show or items list and confirm no credential re-prompt."
    expected: "Credentials retrieved from Windows Credential Manager without prompting again."
    why_human: "Requires a real Windows session with Credential Manager; cannot be automated without a live keyring."
  - test: "Confirm encrypted-file secret survives process restart on Ubuntu headless (Phase 8 deferred): set SHOPBOT_STORE_PASSPHRASE, run setup, exit, reopen, confirm retrieval."
    expected: "Credentials retrieved from creds.bin after process restart without re-prompt."
    why_human: "Requires a real persistent filesystem session; cannot be reliably automated in CI without a persistent state fixture."
  - test: "Run shoppybot setup on Ubuntu terminal and Windows PowerShell and confirm credential prompts show no echo (masked TTY), no characters appear in terminal history, and the name-only confirm prompt shows the item name only (Phase 9 deferred)."
    expected: "Silent input (getpass.getpass behavior), history-clean, name-only confirm."
    why_human: "TTY echo behavior and terminal history require interactive human verification; subprocess.run capture_output does not replicate an interactive TTY."
  - test: "Run shoppybot web on Ubuntu and Windows, open http://localhost:8000 in a browser, verify items/config sections render, Start/Stop updates live state, log panel polls without full reload, and --host 0.0.0.0 shows the non-local warning banner (Phase 10 deferred)."
    expected: "Dashboard fully functional; all UI sections visible and interactive; warning banner appears for non-local binding."
    why_human: "Browser rendering, WebSocket live polling, and visual banner presence require a human with a browser; cannot be grep-verified."
---

# Phase 11: Cross-Platform Verification — Verification Report

**Phase Goal:** Every front-end command and all three credential backends are verified to work correctly on both Ubuntu (desktop and headless) and Windows; OS-specific path handling is correct; a verification matrix documents the results.
**Verified:** 2026-06-05T06:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Data/config/log paths resolve to OS-appropriate locations on both Ubuntu and Windows; no hardcoded path separators appear in codebase. | VERIFIED | `core/paths.py` uses `platformdirs.PlatformDirs("shoppybot", appauthor=False)`. Live output on Windows: `data_dir()=C:\Users\brand\AppData\Local\shoppybot`, `log_dir()=C:\Users\brand\AppData\Local\shoppybot\Logs`. Linux paths documented in `docs/PLATFORMS.md` (`~/.local/share/shoppybot`, `~/.local/state/shoppybot/log`). `test_no_hardcoded_separators` passes (scan of core/ + logger.py + models.py + utils.py). |
| 2 | Import, --help, and safe CLI commands complete without errors on Ubuntu desktop, Ubuntu headless, and Windows. | VERIFIED (automated half) | `tests/test_smoke.py` (4 tests, all green): `test_import_smoke` proves clean import; `test_help_smoke` proves `python -m core.service --help` exits 0; `test_items_list_smoke` and `test_config_show_smoke` prove CLI dispatch exits 0 under headless env vars. CI matrix in `ci.yml` runs these on ubuntu-latest + windows-latest. Live-environment runs on real Ubuntu desktop/headless require human check (see Human Verification section). |
| 3 | Credential-backend auto-selection chooses keyring on Windows/desktop-Ubuntu and encrypted-file on headless Ubuntu. | VERIFIED (automated logic) | `tests/test_backend_selection.py` (3 tests, all green): `test_auto_selects_keyring_when_available` (mock True -> KeyringBackend), `test_auto_selects_file_when_no_keyring` (mock False + passphrase -> EncryptedFileBackend), `test_auto_falls_back_to_env` (mock False + no passphrase -> EnvVarBackend). The selection logic in `core/credentials._build_store` is fully covered. Confirmation on live Ubuntu desktop/headless hardware is deferred to the manual matrix. |
| 4 | `docs/PLATFORMS.md` documents verified data/config/log paths per OS, expected credential backend per environment, and steps to reproduce the verification matrix. | VERIFIED | `docs/PLATFORMS.md` exists (commit bf73266). Contains: (1) "Resolved Paths per OS" table with Windows `%LOCALAPPDATA%\shoppybot` and Ubuntu `~/.local/share/shoppybot` values for data/config/log/DB/creds; (2) "Expected Credential Backend per Environment" table for Windows/Ubuntu-desktop/Ubuntu-headless/env-var-fallback; (3) "Reproduce the Verification Matrix" with install steps, CI matrix description, and local repro shell commands for both Linux and Windows; (4) "Manual Verification Checklist" matrix with deferred Phase 8/9/10 live checks folded in. |

**Score:** 4/4 truths verified (automated components confirmed; live cross-OS human runs deferred to the documented manual matrix)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/paths.py` | platformdirs-backed data_dir/config_path/log_dir + migrate_legacy_paths + SHOPBOT_DATA_DIR override | VERIFIED | All six public symbols present and substantive. `PlatformDirs(_APP_NAME, appauthor=False)` at module level. `_env_override()` reads env on every call. `migrate_legacy_paths()` copy2+unlink with idempotency guard. `_REPO_ROOT_OVERRIDE` test seam present. |
| `tests/test_paths.py` | 6 tests: resolution, env-override, separator guard | VERIFIED | All 6 functions present. Passes (6/6 green). `test_no_hardcoded_separators` scans core/ + logger.py + models.py + utils.py. |
| `requirements.txt` | platformdirs==4.10.0 pin | VERIFIED | Line 6: `platformdirs==4.10.0` confirmed by grep. |
| `pyproject.toml` | platformdirs==4.10.0 in project.dependencies | VERIFIED | `tomllib` parse confirms `dependencies = ["platformdirs==4.10.0"]`. |
| `models.py` | DB_PATH anchored to data_dir() | VERIFIED | Line 5: `from core.paths import data_dir as _paths_data_dir`; line 7: `DB_PATH = str(_paths_data_dir() / "shop_py_bot.db")`. Live output confirms absolute OS-standard path. No `os.path.join('data', ...)` remains. |
| `core/config_schema.py` | _DEFAULT_YAML_PATH via config_path() | VERIFIED | Line 16: `from core.paths import config_path as _paths_config_path`; line 19: `_DEFAULT_YAML_PATH: Path = _paths_config_path()`. |
| `core/credentials.py` | _DEFAULT_STORE_PATH via data_dir() | VERIFIED | Line 37: `from core.paths import data_dir as _paths_data_dir`; line 42: `_DEFAULT_STORE_PATH: Path = _paths_data_dir() / "creds.bin"`. |
| `logger.py` | log_dir via lazy import inside writeLog | VERIFIED | Line 41 (inside writeLog, inside the writeTofile branch): `from core.paths import log_dir as _paths_log_dir`. No module-top import. Circular import risk fully avoided. |
| `tests/conftest.py` | tmp_data_dir sets both SHOPBOT_DATA_DIR and models.DB_PATH | VERIFIED | Lines 61-63: `monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))` then `monkeypatch.setattr(models, "DB_PATH", ...)`. Both seams consistent. |
| `tests/test_migration.py` | 5 migration tests (move, idempotency, verbatim, skip-on-dst, no-leak) | VERIFIED | All 5 functions present and passing. Covers T-11-06 through T-11-08 threat mitigations. |
| `core/service.py` | migrate_legacy_paths() called before build_parser() in main() | VERIFIED | Lines 166+171: `from core.paths import migrate_legacy_paths` then `migrate_legacy_paths()` called immediately before `parser = build_parser()`. Confirmed via `inspect.getsource`. |
| `tests/test_smoke.py` | 4 smoke tests (import, --help, items list, config show) | VERIFIED | All 4 functions present, all green. Uses SHOPBOT_DATA_DIR, PYTHON_KEYRING_BACKEND=null, SDL_AUDIODRIVER=dummy. Never invokes `run` subcommand. |
| `tests/test_backend_selection.py` | 3 backend-selection tests via mocked _has_real_keyring | VERIFIED | All 3 functions present, all green. Covers keyring/file/env auto-selection logic. |
| `.github/workflows/ci.yml` | matrix over ubuntu-latest + windows-latest, Python 3.13, headless env, pip install .[web], pytest | VERIFIED | Parsed and confirmed: `matrix.os = [ubuntu-latest, windows-latest]`, `python-version = "3.13"`, all 4 headless env vars present at job level, `pip install -e .[web]` install step, `pytest --tb=short` test step, `actions/checkout@v4` + `actions/setup-python@v5`. |
| `docs/PLATFORMS.md` | Path table + backend map + repro steps + manual matrix with Phase 8/9/10 deferred rows | VERIFIED | All four required sections present. Manual matrix includes deferred Phase 8 (keyring restart, headless auto-select), Phase 9 (setup TTY no-echo), and Phase 10 (dashboard + 0.0.0.0 banner) rows. |
| `.github/workflows/app_linuxBuild.yml` | Deleted (EOL) | VERIFIED | File absent from disk (commit 16fb8c4). |
| `.github/workflows/app_macBuild.yml` | Deleted (EOL) | VERIFIED | File absent from disk (commit 16fb8c4). |
| `.github/workflows/app_windowsBuild.yml` | Deleted (EOL) | VERIFIED | File absent from disk (commit 16fb8c4). |
| `.github/workflows/codeql-analysis.yml` | Preserved | VERIFIED | File present on disk; untouched by this phase. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `core/paths.py` | `platformdirs.PlatformDirs` | `_DIRS = PlatformDirs(_APP_NAME, appauthor=False)` | WIRED | Import `from platformdirs import PlatformDirs` at module top; `_DIRS` instantiated at module level. |
| `core/paths.py:data_dir` | `os.environ SHOPBOT_DATA_DIR` | `_env_override()` called on every invocation | WIRED | `_env_override()` calls `os.environ.get("SHOPBOT_DATA_DIR", "").strip()` every call; no caching. |
| `core/paths.py:migrate_legacy_paths` | `shutil.copy2` + `Path.unlink` | copy-then-unlink guarded by `src.exists() and not dst.exists()` | WIRED | `import shutil` + `shutil.copy2(src, dst)` + `src.unlink()` pattern present in function body. `_migrate_logs` helper handles logs dir via `copytree` + `rmtree`. |
| `core/service.py:main` | `core.paths.migrate_legacy_paths` | called before first BotService() construction | WIRED | `migrate_legacy_paths()` call at line 171, before `parser = build_parser()` at line 173. BotService() first constructed at line 178. |
| `models.py` | `core.paths.data_dir` | `DB_PATH = str(data_dir() / "shop_py_bot.db")` | WIRED | Import and usage confirmed. `models.DB_PATH` resolves to absolute OS-standard path at import time. |
| `logger.py:writeLog` | `core.paths.log_dir` | lazy import inside writeTofile branch | WIRED | `from core.paths import log_dir as _paths_log_dir` at line 41, inside the `if writeTofile:` block. No module-top import. |
| `.github/workflows/ci.yml` | `pytest` | `pip install -e .[web]` then `pytest --tb=short` on both OS | WIRED | Install step runs `pip install -e .[web]`; test step runs `pytest --tb=short`; both run on each matrix OS. |
| `tests/test_backend_selection.py` | `core.credentials._has_real_keyring` | `patch("core.credentials._has_real_keyring", return_value=...)` | WIRED | All three tests patch `_has_real_keyring` and then call `_build_store("auto", cfg)`. Backend class name assertions prove selection logic fires. |
| `tests/test_smoke.py` | `SHOPBOT_DATA_DIR` | env var set in `_headless_env()` helper, injected into subprocess env | WIRED | `_headless_env()` includes `SHOPBOT_DATA_DIR` key; all subprocess invocations pass this env dict. |
| `docs/PLATFORMS.md` | deferred Phase 8/9/10 live checks | manual matrix rows for keyring-restart / setup-TTY / dashboard | WIRED | Sections "Phase 8 Deferred Live Checks", "Phase 9 Deferred Live Checks", "Phase 10 Deferred Live Checks" all present with checklist rows and repro steps. |

### Data-Flow Trace (Level 4)

`core/paths.py` and the test files do not render dynamic data to a UI — they are utility/service modules and tests. Level 4 (data-flow to UI rendering) is not applicable to these artifacts. The CI workflow is a configuration file, not a data-rendering component. PLATFORMS.md is a static documentation file. Level 4 is SKIPPED for this phase as appropriate.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| data_dir() returns absolute OS path | `python -c "from core.paths import data_dir; print(data_dir())"` | `C:\Users\brand\AppData\Local\shoppybot` | PASS |
| models.DB_PATH is absolute (not CWD-relative) | `python -c "import models; print(models.DB_PATH)"` | `C:\Users\brand\AppData\Local\shoppybot\shop_py_bot.db` | PASS |
| migrate_legacy_paths() call verified in main() | `python -c "import core.service, inspect; assert 'migrate_legacy_paths()' in inspect.getsource(core.service.main); print('OK')"` | `OK` | PASS |
| ci.yml YAML valid and matrix+env correct | `python -c "import yaml; d=yaml.safe_load(...); assert matrix + env assertions; print('OK')"` | `OK` | PASS |
| docs/PLATFORMS.md contains all required content | `python -c "t=open(...).read(); assert shoppybot/keyring/encrypted-file/Ubuntu headless/0.0.0.0; print('ALL OK')"` | `ALL OK` | PASS |
| Full pytest suite passes | `python -m pytest -q --tb=short` | `352 passed, 2 skipped, 2 warnings` | PASS |
| Phase-11 specific tests (18 tests) | `python -m pytest tests/test_paths.py tests/test_migration.py tests/test_smoke.py tests/test_backend_selection.py -q` | `18 passed` | PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes declared or discovered for this phase. The phase uses pytest-based verification throughout. SKIPPED (no probe scripts).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| XPLAT-01 | 11-01, 11-02, 11-03, 11-05 | Runs on Ubuntu (desktop + headless) and Windows; data dir + paths resolved per-OS (no hardcoded separators); data/config/log locations documented per OS. | SATISFIED | `core/paths.py` backed by platformdirs; `test_no_hardcoded_separators` passes; `docs/PLATFORMS.md` documents all three path types per OS; first-run migration implemented. |
| XPLAT-02 | 11-04, 11-05 | A documented verification matrix (and/or automated smoke) confirms import + CLI + credential-store backend selection on both Ubuntu and Windows. | SATISFIED | `tests/test_smoke.py` + `tests/test_backend_selection.py` constitute the automated smoke; `.github/workflows/ci.yml` runs them on both ubuntu-latest and windows-latest; `docs/PLATFORMS.md` section 4 is the documented manual matrix. |

Both XPLAT-01 and XPLAT-02 appear in all plan `requirements:` fields and are cross-referenced in REQUIREMENTS.md as "Complete". No orphaned requirements found for Phase 11.

### Anti-Patterns Found

No TBD, FIXME, or XXX markers found in any file modified by this phase. No stub return patterns (`return null`, `return []`, empty handlers) found in production code. The `test_migration.py` docstring contains "TDD RED phase:" as a historical comment from the RED phase of TDD — this is documentation, not a debt marker, and the file is fully implemented (GREEN).

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

### Human Verification Required

The automated components of phase 11 are fully verified. The following items require live hardware that cannot be replicated programmatically. These are exactly the items documented in `docs/PLATFORMS.md` manual verification checklist and are the intended deferred live checks from Phases 8, 9, and 10 folded into the milestone sign-off.

**1. Live CLI Smoke on Ubuntu Desktop (Real Secret Service)**

**Test:** On a machine running GNOME or KDE with an active D-Bus session, install `pip install -e .[web]` and run `shoppybot --help`, `shoppybot items list`, `shoppybot config show`, and `shoppybot setup` (with a test credential).
**Expected:** All commands exit 0; setup selects KeyringBackend and stores/retrieves the credential via the OS Secret Service (GNOME Keyring or KWallet).
**Why human:** The CI matrix forces `PYTHON_KEYRING_BACKEND=null` to prevent D-Bus hangs. Only a real desktop session with an active Secret Service exercises the live `_has_real_keyring()` probe returning True and the actual keyring read/write path.

**2. Live CLI Smoke on Ubuntu Headless (No Secret Service)**

**Test:** On an Ubuntu system without an active D-Bus session (plain SSH or headless runner with no `PYTHON_KEYRING_BACKEND` override set), set `SHOPBOT_STORE_PASSPHRASE=test` and run `shoppybot --help`, `shoppybot items list`, `shoppybot config show`, and `shoppybot setup`.
**Expected:** All commands exit 0; setup selects EncryptedFileBackend (no keyring hang); creds.bin written to the OS-standard path.
**Why human:** Real headless Ubuntu without D-Bus is not available on the Windows dev machine; the backend-selection test mocks the probe but cannot confirm the live D-Bus detection path on actual headless Linux.

**3. Keyring Secret Persistence Across Restart — Windows (Phase 8 deferred)**

**Test:** Run `shoppybot setup` and store a test credential. Exit the process completely. Unset any credential env vars. Run `shoppybot config show` or `shoppybot items list`. Confirm no credential re-prompt.
**Expected:** Credential retrieved transparently from Windows Credential Manager.
**Why human:** Requires a real Windows Credential Manager session with stored credentials persisted across process boundaries; not automatable without a live keyring state.

**4. Keyring Secret Persistence Across Restart — Ubuntu Headless / Encrypted File (Phase 8 deferred)**

**Test:** Set `SHOPBOT_STORE_PASSPHRASE=test`, run `shoppybot setup`, exit. Reopen with the same passphrase set. Confirm credential retrieval without re-prompt.
**Expected:** creds.bin present and correctly decrypted on restart.
**Why human:** Requires a persistent filesystem session where the same creds.bin is present between process runs; difficult to automate as a stateless CI check.

**5. Setup Masked TTY Input (Phase 9 deferred)**

**Test:** Open a fresh terminal (PowerShell on Windows; bash/zsh on Ubuntu). Run `shoppybot setup`. At each credential prompt, type a value and verify no characters are echoed. At the confirmation prompt, verify only the item name is shown.
**Expected:** Silent (masked) input; no echo; history-clean; name-only confirm.
**Why human:** TTY echo suppression and terminal history behavior require an interactive terminal with a human observer; `subprocess.run capture_output` does not replicate an interactive TTY.

**6. Web Dashboard Live Verification (Phase 10 deferred)**

**Test:** Run `shoppybot web`. Open `http://localhost:8000` in a browser. Verify: items list section renders; config section renders; Start/Stop bot button triggers a live state change; the log panel updates via live polling without a full page reload; running `shoppybot web --host 0.0.0.0` shows a non-local binding warning banner.
**Expected:** Full dashboard functional; all sections visible; live behavior confirmed; 0.0.0.0 warning banner visible.
**Why human:** Browser rendering, WebSocket live polling, and visual UI elements require a human with a browser; cannot be verified by grep or subprocess return codes.

### Gaps Summary

No gaps. All four roadmap success criteria are verified against actual codebase artifacts. All must-haves across all five plan frontmatter sections are confirmed substantive and wired. The full pytest suite (352 passed) is green on Windows.

The only outstanding items are the six human verification items above, all of which are live cross-OS runtime checks that are explicitly documented in the manual verification checklist in `docs/PLATFORMS.md`. These are not gaps in the implementation — they are the intentional deferred live-environment portion of the XPLAT-02 verification matrix that the phase design designated as manual-matrix work.

---

_Verified: 2026-06-05T06:00:00Z_
_Verifier: Claude (gsd-verifier)_
