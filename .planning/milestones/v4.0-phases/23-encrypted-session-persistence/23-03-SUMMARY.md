---
phase: 23-encrypted-session-persistence
plan: "03"
subsystem: tests
tags: [ci-guard, security, gitignore, session]
dependency_graph:
  requires: []
  provides: [test_no_committed_sessions.py]
  affects: [data/sessions/]
tech_stack:
  added: []
  patterns: [subprocess-check=False-returncode-guard, pytest-skip-outside-git]
key_files:
  created:
    - tests/test_no_committed_sessions.py
  modified: []
decisions:
  - "check=False + explicit returncode != 0 guard chosen over check=True; empty stdout on failed git call must not silently pass"
  - "Asserts data/* OR data/sessions in .gitignore to survive either rule formulation"
metrics:
  duration: "3min"
  completed: "2026-06-12"
  tasks: 1
  files: 1
---

# Phase 23 Plan 03: No-Committed-Sessions CI Guard Summary

CI guard asserting no `data/sessions/*.bin` is git-tracked and `data/sessions/` is gitignored via the existing `data/*` rule.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | CI guard -- no committed session files + sessions dir gitignored | 2354855 | tests/test_no_committed_sessions.py |

## What Was Built

`tests/test_no_committed_sessions.py` (56 lines) with two tests:

- `test_no_committed_session_files`: runs `git ls-files data/sessions/` with `check=False`; skips on non-zero returncode or `FileNotFoundError`; filters stdout for `.bin` lines and asserts the list is empty. Mitigates T-23-07.
- `test_sessions_dir_gitignored`: reads `.gitignore`; skips if absent; asserts `data/*` or `data/sessions` is present in the file. Mitigates T-23-08.

## Deviations from Plan

None. Plan executed exactly as written, with the reviewer-flagged `check=False` + explicit `returncode != 0` guard applied (the PATTERNS.md draft used `check=True` which would raise on git failure instead of skipping).

## Test Results

- `pytest tests/test_no_committed_sessions.py -x`: 2 passed
- Full suite: 648 passed, 10 skipped

## Known Stubs

None.

## Threat Flags

None. This plan adds a CI guard against committed session files; it does not introduce new network endpoints, auth paths, or file access patterns.

## Self-Check: PASSED

- tests/test_no_committed_sessions.py: FOUND
- Commit 2354855: FOUND
