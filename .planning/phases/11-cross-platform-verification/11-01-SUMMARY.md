---
phase: 11
plan: "01"
subsystem: core/paths
tags: [paths, platformdirs, cross-platform, xplat-01]
dependency_graph:
  requires: []
  provides: [core/paths.py, platformdirs-pin]
  affects: [models.py, core/credentials.py, core/config_schema.py, logger.py]
tech_stack:
  added: [platformdirs==4.10.0]
  patterns: [module-level-singleton+function-accessor, SHOPBOT_DATA_DIR-env-seam]
key_files:
  created:
    - core/paths.py
    - tests/test_paths.py
  modified:
    - requirements.txt
    - pyproject.toml
decisions:
  - "appauthor=False suppresses redundant vendor subdir on Windows (%LOCALAPPDATA%\\shoppybot not \\shoppybot\\shoppybot)"
  - "data_dir/config_path/log_dir re-read SHOPBOT_DATA_DIR on every call; no module-level caching that defeats env override"
  - "No migrate_legacy_paths in this plan; migration deferred to Plan 03 per plan scope"
  - "platformdirs==4.10.0 pinned in both requirements.txt and pyproject.toml [project].dependencies"
metrics:
  duration: "5m"
  completed: "2026-06-05T02:53:22Z"
  tasks_completed: 3
  files_modified: 4
---

# Phase 11 Plan 01: core/paths.py + platformdirs Pin Summary

One-liner: `core/paths.py` exposes `data_dir/config_path/log_dir` backed by `platformdirs==4.10.0` with a `SHOPBOT_DATA_DIR` env-override seam that re-reads on every call.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write tests/test_paths.py (RED) | 7c71e09 | tests/test_paths.py |
| 2 | Create core/paths.py (GREEN) | 815b421 | core/paths.py |
| 3 | Pin platformdirs==4.10.0 in both manifests | 72a33ed | requirements.txt, pyproject.toml |

## What Was Built

`core/paths.py` is the single source of truth for OS-standard paths:
- `data_dir()`: returns `SHOPBOT_DATA_DIR` env value or `%LOCALAPPDATA%\shoppybot` on Windows / `~/.local/share/shoppybot` on Linux
- `config_path()`: returns `data_dir() / "config.yml"`
- `log_dir()`: returns `override / "logs"` when env set, else `%LOCALAPPDATA%\shoppybot\Logs` / `~/.local/state/shoppybot/log`
- `_env_override()`: reads `os.environ.get("SHOPBOT_DATA_DIR")` on every call; the monkeypatch seam
- `_DIRS`: module-level `PlatformDirs("shoppybot", appauthor=False)` singleton
- No side effects at import (no mkdir, no migration)

`tests/test_paths.py` covers all six required behaviors including the SC1 separator guard.

## Deviations from Plan

None - plan executed exactly as written.

## Test Results

- `test_paths.py`: 6/6 passed (GREEN after Task 2)
- Full suite after Task 3: 341 passed (335 baseline + 6 new), 1 xpassed, 0 failures

## Known Stubs

None. `core/paths.py` is fully functional. Consumer re-anchoring (models.py, credentials.py, config_schema.py, logger.py) is deferred to Plan 02 per plan scope boundary.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.
T-11-02 (platformdirs supply chain) mitigated: exact pin ==4.10.0; pre-vetted tox-dev org package.

## Self-Check: PASSED
