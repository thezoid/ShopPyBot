---
phase: 24-health-surface-server-safety
plan: "02"
subsystem: utils
tags: [pygame, headless, server-safety, SRV-01, audio-guard]
dependency_graph:
  requires: []
  provides: [headless-pygame-guard]
  affects: [utils.py, notifications/sound_notifier.py]
tech_stack:
  added: []
  patterns: [try/except import-time guard, module-level flag, early-return no-op]
key_files:
  created:
    - tests/test_utils_audio.py
  modified:
    - utils.py
decisions:
  - "Log audio init failure using exc.__class__.__name__ (not str(exc)) to avoid leaking device info"
  - "Removed redundant pygame.mixer.init() inside play_sound (Pitfall 3 from RESEARCH)"
  - "_AUDIO_AVAILABLE flag set at module level so play_sound guard is a single early return"
metrics:
  duration_secs: 217
  completed: "2026-06-12"
  tasks_completed: 2
  files_modified: 2
---

# Phase 24 Plan 02: Pygame Headless Guard Summary

Import-time pygame.mixer.init() wrapped in _initialize_audio() -> bool; _AUDIO_AVAILABLE flag controls all play_* paths; headless hosts import utils and call play_sound without crashing.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for pygame headless guard | 5a2f2be | tests/test_utils_audio.py |
| 1+2 (GREEN) | pygame headless guard in utils.py | dc9eb71 | utils.py |

## What Was Built

utils.py now:
- Defines `_initialize_audio() -> bool` that wraps `pygame.mixer.init()` in `try/except pygame.error`
- On failure, logs one INFO line with `exc.__class__.__name__` and returns False
- Sets `_AUDIO_AVAILABLE: bool = _initialize_audio()` at module level (replaces bare `initialize_pygame()`)
- `play_sound()` has `if not _AUDIO_AVAILABLE: return` as its first line (silent no-op)
- Removed the redundant `pygame.mixer.init()` call inside `play_sound` (was line 13)
- Three public wrappers (`play_notification_sound`, `play_buy_sound`, `play_available_sound`) unchanged

tests/test_utils_audio.py covers:
- `test_initialize_audio_returns_false_on_pygame_error`
- `test_initialize_audio_returns_true_on_success`
- `test_play_sound_noop_when_audio_unavailable` (asserts music.load NOT called)
- `test_play_sound_noop_does_not_raise`
- `test_sound_notifier_no_audio` (async; all three actions: detected, purchased, health_degraded)

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

- RED gate: commit 5a2f2be (`test(24-02): ...`) - 5 failing tests confirmed
- GREEN gate: commit dc9eb71 (`feat(24-02): ...`) - 5 passing tests confirmed
- REFACTOR gate: not needed (implementation was clean on first pass)

## Verification

Full test suite: 738 passed, 2 skipped, 0 failures (was 733 passed, 2 skipped before this plan; +5 new tests).

`python -c "import utils; utils.play_sound('notification')"` runs without raising.

## Known Stubs

None.

## Threat Flags

None. utils.py is a local sound utility with no network surface, file I/O beyond sounds/ directory reads, or auth paths.

## Self-Check: PASSED

- utils.py exists and contains `_AUDIO_AVAILABLE` and `_initialize_audio`
- tests/test_utils_audio.py exists with 5 tests
- Commits 5a2f2be and dc9eb71 present in git log
- Full suite: 738 passed, 0 failures
