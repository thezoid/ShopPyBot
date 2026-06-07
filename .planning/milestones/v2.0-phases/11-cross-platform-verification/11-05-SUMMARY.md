---
phase: 11
plan: "05"
subsystem: ci
tags: [ci-matrix, github-actions, headless, platforms-doc, xplat-01, xplat-02, milestone-closing]
dependency_graph:
  requires: [11-02, 11-03, 11-04]
  provides: [.github/workflows/ci.yml, docs/PLATFORMS.md]
  affects: [milestone-v2.0-close]
tech_stack:
  added: []
  patterns: [matrix-job-single, job-level-env-headless-guards, actions-v4-v5]
key_files:
  created:
    - .github/workflows/ci.yml
    - docs/PLATFORMS.md
  deleted:
    - .github/workflows/app_linuxBuild.yml
    - .github/workflows/app_macBuild.yml
    - .github/workflows/app_windowsBuild.yml
  modified: []
decisions:
  - "Single matrix job (os=[ubuntu-latest, windows-latest], Python 3.13), not one job per OS, per RESEARCH Pattern 5"
  - "Headless guards set at JOB-level env (active during pytest collection): SDL_AUDIODRIVER=dummy, SDL_VIDEODRIVER=dummy, PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring, SHOPBOT_DATA_DIR=${{ runner.temp }}/shopbot"
  - "SHOPBOT_DATA_DIR only in env block, never a run: command, to avoid Windows path-with-spaces word-splitting (RESEARCH Pitfall 6)"
  - "actions/checkout@v4 + setup-python@v5 (Node 20) replace the EOL @v2 (Node 12) legacy files"
  - "codeql-analysis.yml explicitly preserved; only the 3 Python-3.9 per-OS build files deleted"
  - "EOL-file deletion executed only after explicit human 'approved' at the blocking checkpoint (Task 3)"
metrics:
  completed: "2026-06-05T00:00:00Z"
  tasks_completed: 3
  files_created: 2
  files_deleted: 3
  closeout: "SUMMARY authored via safe_resume_gate close-out — all task commits pre-existed (0e0e43f, bf73266, 16fb8c4); only this SUMMARY + tracking were missing"
---

# Phase 11 Plan 05: CI Matrix Workflow + PLATFORMS.md + EOL Cleanup Summary

One-liner: adds `.github/workflows/ci.yml` (ubuntu+windows matrix on Python 3.13 with headless guards and `.[web]` install) and `docs/PLATFORMS.md` (per-OS path table, backend-per-env map, repro steps, and the manual matrix folding deferred Phase 8/9/10 live checks), then removes the three EOL Python-3.9 per-OS workflows after human confirmation. This is the milestone-closing plan for v2.0.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create .github/workflows/ci.yml matrix workflow | 0e0e43f | .github/workflows/ci.yml |
| 2 | Author docs/PLATFORMS.md | bf73266 | docs/PLATFORMS.md |
| 3 | Delete 3 EOL legacy workflow files (human-approved) | 16fb8c4 | app_linuxBuild.yml, app_macBuild.yml, app_windowsBuild.yml (deleted) |

## What Was Built

`.github/workflows/ci.yml` — single `test` job, `runs-on: ${{ matrix.os }}`, `strategy.fail-fast: false`, `matrix.os: [ubuntu-latest, windows-latest]`. Job-level `env` carries the four headless guards so they are live during pytest collection. Steps: `actions/checkout@v4`, `actions/setup-python@v5` (python-version "3.13"), `pip install -e .[web]`, `pytest --tb=short`. Triggers on push + pull_request to [master, dev].

`docs/PLATFORMS.md` — four sections: (1) Resolved Paths per OS table (Windows `%LOCALAPPDATA%\shoppybot` + `\Logs`; Ubuntu `~/.local/share/shoppybot`, `.../config.yml`, `~/.local/state/shoppybot/log`); (2) Expected Credential Backend per Environment (Windows → keyring, Ubuntu desktop → keyring, Ubuntu headless → encrypted-file); (3) Reproduce the Verification Matrix (install, pytest, what the CI matrix covers, SHOPBOT_DATA_DIR redirect); (4) Manual Verification Checklist matrix folding the deferred Phase 8 (keyring restart / headless auto-select), Phase 9 (setup masked TTY), and Phase 10 (dashboard + non-local 0.0.0.0 warning) live checks.

Deleted (EOL, Python 3.9, actions @v2): `app_linuxBuild.yml`, `app_macBuild.yml`, `app_windowsBuild.yml`. Preserved: `codeql-analysis.yml`, new `ci.yml`.

## Deviations from Plan

None functional. Procedural note: this SUMMARY was authored after the fact via the execute-phase `safe_resume_gate` close-out path. All three task commits already existed on `master` (0e0e43f, bf73266, 16fb8c4) from an interrupted run; only the SUMMARY and the STATE/ROADMAP tracking writes were missing. No code was re-executed; re-execution would have attempted to re-delete already-absent files.

## Test Results

- `python -c "import yaml; ...ci.yml..."` matrix + env assertions: OK
- `python -c "...docs/PLATFORMS.md..."` content assertions (shoppybot, keyring, encrypted-file, Ubuntu headless, 0.0.0.0): OK
- codeql-analysis.yml present (preserved); 3 EOL files confirmed absent

## Known Stubs

None.

## Threat Flags

None. ci.yml references NO `${{ secrets.* }}` — only public env redirects (T-11-12 mitigated). Deletion was gated behind the blocking human-verify checkpoint with codeql excluded (T-11-13 mitigated). Headless guards prevent pygame/keyring CI hangs (T-11-14 mitigated).

## Self-Check: PASSED
