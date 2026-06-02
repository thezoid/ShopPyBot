---
phase: 01-foundations-security
plan: "01"
subsystem: test-infrastructure
tags: [pytest, fixtures, test-repair, asyncio]
dependency_graph:
  requires: []
  provides: [pytest-config, shared-fixtures, green-test-suite]
  affects: [all-phase-1-plans]
tech_stack:
  added: [pyproject.toml]
  patterns: [tmp_path-fixture, monkeypatch-chdir, importlib-reload, monkeypatch-setattr]
key_files:
  created:
    - pyproject.toml
    - tests/conftest.py
  modified:
    - tests/test_utils.py
    - tests/test_models.py
    - tests/test_config.py
decisions:
  - "Used importlib.reload + monkeypatch.chdir in tests to satisfy config.py module-level load_config() without modifying production code"
  - "Monkeypatched main.requests.get in test_make_tiny for offline deterministic execution (T-01-01 mitigated)"
  - "tmp_data_dir fixture uses monkeypatch.setattr on models.DB_PATH so each test gets an isolated tmp_path DB"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-02"
  tasks: 3
  files_changed: 5
---

# Phase 01 Plan 01: Test Infrastructure Repair Summary

Repaired three broken test files and added pytest configuration so every subsequent Phase 1 plan can attach automated verification.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add pyproject.toml | 1e542bf | pyproject.toml |
| 2 | Add shared fixtures in tests/conftest.py | 50bb376 | tests/conftest.py |
| 3 | Repair broken existing tests | 69471d7 | tests/test_utils.py, tests/test_models.py, tests/test_config.py |

## What Was Built

pytest + asyncio config file (pyproject.toml) with `asyncio_mode=auto` and `requires-python>=3.11`. Shared test fixtures (`tmp_config_yml`, `tmp_data_dir`) in `tests/conftest.py`. Three previously-broken test files repaired to collect and run green without touching production code.

## Verification Results

```
4 passed, 1 warning in 0.83s
```

The single warning is a pre-existing `pygame` pkg_resources deprecation unrelated to this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] main.py module-level import chain blocks test_utils collection**
- **Found during:** Task 3
- **Issue:** `import main` at module level in test_utils triggered `from config import config` at collection time, which called `open('config.yml')` before any fixture could set up CWD. Collection failed with `FileNotFoundError`.
- **Fix:** Moved `import main` inside the test function body; used `monkeypatch.chdir(tmp_config_yml.parent)` + `importlib.reload` to satisfy the CWD-relative load before the import runs. Production code untouched.
- **Files modified:** tests/test_utils.py
- **Commit:** 69471d7

**2. [Rule 1 - Bug] test_config.py called load_config(sample_config) but function signature takes no args**
- **Found during:** Task 3
- **Issue:** The existing `test_config.py` passed a `Path` argument to `config.load_config()`, but the production function signature is `def load_config():` with no parameters. Would raise `TypeError` at runtime.
- **Fix:** Rewrote the test to use `monkeypatch.chdir` + `importlib.reload(config_module)` + `config_module.load_config()` (no args) so the test exercises the real function signature.
- **Files modified:** tests/test_config.py
- **Commit:** 69471d7

## Known Stubs

None -- this plan adds infrastructure only; no data stubs present.

## Threat Flags

None -- no new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- pyproject.toml: EXISTS
- tests/conftest.py: EXISTS
- Commit 1e542bf: EXISTS
- Commit 50bb376: EXISTS
- Commit 69471d7: EXISTS
- `python -m pytest tests/ -q` exits 0: CONFIRMED (4 passed)
