---
phase: 12-stability-foundation
plan: "02"
subsystem: test-guards
tags: [tech-debt, test-hardening, SC1, separator-guard, TD-2, TD-3]
dependency_graph:
  requires: []
  provides: [TD-2-closed, TD-3-closed]
  affects: [tests/test_no_env_secret_reads.py, tests/test_paths.py]
tech_stack:
  added: []
  patterns: [rglob-recursive-scan, __file__-anchored-paths, non-empty-scan-assertion]
key_files:
  created: []
  modified:
    - tests/test_no_env_secret_reads.py
    - tests/test_paths.py
decisions:
  - "Switch all three dirs_to_scan entries to rglob (not just core/) for future-proofing; safe per RESEARCH Pitfall 2 (rglob never matches .pyc)"
  - "Companion assertion checks Path('core/cli/config_cmd.py') in scanned_rels using relative_to(repo_root) -- cross-platform path comparison"
  - "Added both len > 0 guard AND core/paths.py presence check to test_paths; belt-and-suspenders per RESEARCH Pitfall 3"
metrics:
  duration: "237s"
  completed: "2026-06-09"
  tasks: 2
  files_modified: 2
---

# Phase 12 Plan 02: SC1 and Separator Guard Hardening Summary

TD-2 and TD-3 both resolved: the SC1 secret-read guard now uses `rglob` to recurse into `core/cli/*.py` with a companion proof assertion, and the separator guard is anchored to `Path(__file__).parent.parent` with a non-empty scan assertion -- both turning silent coverage holes into reliable guards.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Harden SC1 secret-read guard to recurse into core/cli (TD-2) | 98fa051 | tests/test_no_env_secret_reads.py |
| 2 | Anchor separator guard to __file__ and forbid silent empty scan (TD-3) | 40abbfc | tests/test_paths.py |

## What Was Built

### Task 1 (TD-2): SC1 rglob fix

`tests/test_no_env_secret_reads.py` changed from `scan_dir.glob("*.py")` to `scan_dir.rglob("*.py")` for all three scan directories (plugins/, notifications/, core/). The core/ entry is the critical fix -- `core/cli/*.py` (6 files: `__init__.py`, `config_cmd.py`, `items.py`, `run.py`, `setup.py`, `web.py`) were previously invisible to the guard.

A `scanned_files` accumulator collects every path across all dirs. After the scan loop, a companion assertion confirms `Path("core/cli/config_cmd.py")` is in the relative-path set. If a future commit reverts to non-recursive `glob`, the companion assertion fails explicitly rather than silently passing.

### Task 2 (TD-3): Separator guard anchor fix

`tests/test_paths.py:test_no_hardcoded_separators` replaced `Path("core")` with `Path(__file__).parent.parent / "core"` (absolute, repo-root-anchored). All three top-level files (`logger.py`, `models.py`, `utils.py`) are similarly anchored via `repo_root / "name"`.

First assertion in the function: `assert len(src_files) > 0, "separator guard scanned zero files"`. A second assertion confirms `repo_root / "core" / "paths.py"` is in the scanned set. These ensure that a misconfigured anchor (empty list) triggers a loud failure rather than silently passing.

## Verification

- `pytest -q tests/test_no_env_secret_reads.py` -- 1 passed
- `pytest -q tests/test_paths.py` -- 6 passed
- `pytest --tb=short -q` (full suite) -- 356 passed, 2 skipped, 0 failed

## Deviations from Plan

None. Plan executed exactly as written.

The plan specified applying rglob "at least" to the core scan; the implementation applied it to all three dirs (plugins/, notifications/, core/) as the plan also explicitly noted is "safe and future-proof." This is within plan scope (the plan text states "switching all three dirs to rglob is safe and future-proofs them").

## Threat Flags

None. Test-only guard changes; no new production surface introduced.

## Self-Check: PASSED

- tests/test_no_env_secret_reads.py: FOUND
- tests/test_paths.py: FOUND
- Commit 98fa051: FOUND
- Commit 40abbfc: FOUND
- Full suite: 356 passed, 2 skipped (matches expected baseline)
