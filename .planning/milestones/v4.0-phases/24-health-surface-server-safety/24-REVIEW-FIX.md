---
phase: 24-health-surface-server-safety
fixed_at: 2026-06-12T00:00:00Z
review_path: .planning/phases/24-health-surface-server-safety/24-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 24: Code Review Fix Report

**Fixed at:** 2026-06-12
**Source review:** .planning/phases/24-health-surface-server-safety/24-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (CR-01, WR-01, WR-02, WR-03, IN-02; IN-01 subsumed by CR-01 rewrite)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01 + WR-03: Guard pygame import; wrap play_sound audio errors

**Files modified:** `utils.py`, `tests/test_utils_audio.py`
**Commit:** 8284735
**Applied fix:**
- Replaced bare `import pygame` with `try/except (ModuleNotFoundError, ImportError)` block; sets `_PYGAME_AVAILABLE` and `_pygame` alias.
- `_initialize_audio()` short-circuits to False when `_PYGAME_AVAILABLE` is False (before calling mixer.init).
- All `pygame.*` references in the module now use `_pygame.*`.
- `play_sound` wraps `mixer.music.load/play` in `try/except _pygame.error` to swallow runtime audio errors (WR-03).
- Dead `_AUDIO_AVAILABLE: bool = False` pre-declaration (IN-01) eliminated as part of the rewrite.
- Updated `tests/test_utils_audio.py`: patches retargeted to `utils._pygame`, added non-vacuous import-failure simulation test (blocks pygame via `sys.modules["pygame"] = None`, reloads utils, asserts `_AUDIO_AVAILABLE=False` and `play_sound` no-ops), added WR-03 load/play error tests.

**Suite result:** 755 passed, 2 skipped, 0 failures (baseline 752 passed; 3 new tests added)

### WR-01: Add get_consecutive_errors reader; use in supervise() crash path

**Files modified:** `core/health.py`, `core/orchestrator.py`
**Commit:** d11bf2c
**Applied fix:**
- Added `HealthRegistry.get_consecutive_errors(name: str) -> int` that reads the live counter directly via `_ensure` + dict lookup.
- Replaced `snap = health.get_snapshot(); consecutive = snap.get(plugin_name, {}).get("consecutive_errors", 0)` in `supervise()` with `consecutive = health.get_consecutive_errors(plugin_name)`. Removes the full deep-copy allocation on the hot crash path.

### WR-02: Snapshot loop/task before guard in stop() to close TOCTOU

**Files modified:** `core/service.py`
**Commit:** 79e5419
**Applied fix:**
- Moved `loop = self._loop` and `task = self._task` captures to the top of `stop()`, before the `if not self._running or loop is None` guard. Guard and `call_soon_threadsafe` now operate on the same consistent local references even if the daemon thread nulls the instance attributes concurrently.

### IN-02: Display heartbeat age instead of raw monotonic seconds

**Files modified:** `core/cli/status.py`
**Commit:** 3007ba1
**Applied fix:**
- Added `import time` and `now = time.monotonic()` in `_format_status_table`.
- Replaced `f"{rec.get('last_heartbeat', 0.0):.1f}"` with `f"{now - rec['last_heartbeat']:.1f}s ago"` (or `"never"` when heartbeat is 0.0).

### IN-01: Dead _AUDIO_AVAILABLE pre-declaration

Subsumed by CR-01 fix. The line 8 `_AUDIO_AVAILABLE: bool = False` pre-declaration was not present in the rewritten utils.py; no separate commit required.

---

_Fixed: 2026-06-12_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
