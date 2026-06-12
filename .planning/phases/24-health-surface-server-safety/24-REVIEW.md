---
phase: 24-health-surface-server-safety
reviewed: 2026-06-12T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - core/health.py
  - core/service.py
  - core/orchestrator.py
  - core/cli/status.py
  - core/cli/__init__.py
  - utils.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 24: Code Review Report

**Reviewed:** 2026-06-12T00:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the health surface (REL-07), supervise() invariants, SRV-01 pygame guard, and
status CLI. The architecture is mostly sound: get_snapshot() is a true deep copy, the
health_degraded dedup logic is correct in intent, CancelledError propagates cleanly, and
the status CLI is genuinely network-free.

One blocker was found: `utils.py` does a top-level `import pygame` that will raise
`ModuleNotFoundError` on any deployment where pygame is not installed, crashing every
import of utils.py before the graceful-failure guard even runs. Three warnings surface
a stale-snapshot race in the degraded-threshold check, a data-race window on `_running`
across threads, and a missing `pygame.mixer.music.load` / `.play` guard against
`pygame.error` in `play_sound`. Two info items cover dead initialization code and a
non-fatal missing guard on the `play_sound` file-load path.

## Critical Issues

### CR-01: `import pygame` at module top crashes import when pygame is not installed

**File:** `utils.py:1`

**Issue:** The bare `import pygame` on line 1 executes before any try/except guard.
If pygame is not installed (headless server, Docker image without audio packages, CI
environment) every import of `utils.py` raises `ModuleNotFoundError` and the entire bot
fails at startup. The graceful `_initialize_audio()` catch on line 16 only handles
`pygame.error` (a runtime init failure), it does NOT handle an import-time
`ModuleNotFoundError`. Any module that imports `utils` (e.g. `notifications/sound_notifier.py`)
will also fail. SRV-01 requires that the audio import "never crashes".

**Fix:**
```python
# utils.py -- top of file, replace bare import with a guarded import
try:
    import pygame as _pygame
    _PYGAME_AVAILABLE = True
except ModuleNotFoundError:
    _pygame = None  # type: ignore[assignment]
    _PYGAME_AVAILABLE = False


def _initialize_audio() -> bool:
    if not _PYGAME_AVAILABLE:
        writeLog("pygame not installed -- sound notifications disabled", "INFO")
        return False
    try:
        _pygame.mixer.init()
        return True
    except _pygame.error as exc:
        writeLog(
            f"Audio device unavailable ({exc.__class__.__name__}) -- sound notifications disabled",
            "INFO",
        )
        return False
```
Replace all subsequent `pygame.*` references with `_pygame.*` and guard with
`if _AUDIO_AVAILABLE` (already done for `play_sound`).

## Warnings

### WR-01: Degraded-threshold check reads a snapshot instead of the live counter

**File:** `core/orchestrator.py:143-144`

**Issue:** The health_degraded arm/disarm logic calls `health.get_snapshot()` to read
`consecutive_errors`, then checks the snapshot value. `get_snapshot()` returns a deep
copy -- the value is correct at the moment of the call, but this is an unnecessary
double-read: `record_error()` was just called two lines above (line 138) which
incremented the live counter. Reading back via a full snapshot (which copies every
plugin's entire record dict) just to get one integer is fragile -- it introduces an
extra copy allocation on every crash path and could produce a stale value if the health
registry were ever mutated concurrently between `record_error` and `get_snapshot`.
The existing comment says "lock-free", but reads against a snapshot instead of the
live dict make the code harder to reason about.

A direct accessor is already present on HealthRegistry (`_plugins[name]` is accessible
via `_ensure` semantics). The idiomatic fix is to add a cheap `get_consecutive_errors`
reader or just use the live dict value returned by `record_error`.

**Fix:**
Add a reader to `HealthRegistry`:
```python
# core/health.py
def get_consecutive_errors(self, name: str) -> int:
    self._ensure(name)
    return self._plugins[name]["consecutive_errors"]
```
Then in `supervise()` replace lines 143-144:
```python
# core/orchestrator.py
consecutive = health.get_consecutive_errors(plugin_name)
```
This removes the full-copy snapshot from the hot crash path and makes the intent clear.

### WR-02: `_running` flag has a data-race window between the main thread and the bot thread

**File:** `core/service.py:157,179,188`

**Issue:** `_running` is a plain Python `bool` written by the background thread (lines 179,
188 in `_run_loop`) and read by any caller of `get_status()` or `stop()` from a different
thread. While CPython's GIL makes individual attribute reads/writes atomic at the bytecode
level, there is no memory barrier or lock ordering guarantee here. More concretely:

1. `start()` sets `self._running = True` on the main thread (line 157) BEFORE the daemon
   thread is spawned (line 191). This is deliberate to prevent a concurrent `start()` from
   double-spawning, but the ready-event only fires AFTER `self._task = asyncio.current_task()`
   inside the daemon thread. If the main thread calls `get_status()` between line 157 and
   the ready-event, it sees `running=True` but the bot loop may not yet be processing items.
   This is documented ("_running is set synchronously before the thread starts"), so this
   specific sub-race is intentional and accepted; it is called out here because it means
   `uptime_secs` can be non-zero even before the first poll cycle runs.

2. More importantly: `stop()` checks `if not self._running or self._loop is None` (line 202)
   and returns early if `_running` is False. But `_running` is set to False by the daemon
   thread in its `finally` block (lines 179, 188). There is a TOCTOU window: `_running`
   could flip False between the `stop()` guard check and the `loop.call_soon_threadsafe`
   call, in which case `stop()` would attempt to cancel on a loop that is already finishing.
   This is benign (cancel on a finished task is a no-op), but `stop()` will then still
   call `self._thread.join(timeout=15.0)` which will succeed. The race does not cause data
   loss but could cause a spurious 15-second join stall if the thread exits between the
   guard and the join, because `join()` on an already-finished thread returns immediately.

   The real hazard is `self._loop` being set to None concurrently. `stop()` reads
   `self._loop` on line 202 (guard), stores it in `loop = self._loop` on line 205, then
   uses it on line 209. If the thread sets `self._loop = None` between lines 202 and 209
   the local `loop` variable still holds the old reference (safe), but the guard could
   pass with a non-None loop that becomes None before line 209 -- in that case the local
   `loop` variable is still valid so no crash, but the pattern is fragile without
   documentation.

**Fix:** Document explicitly that the `loop` local captures a reference before the race
window (already partially done). For robustness, snapshot both `_loop` and `_task` at
the top of `stop()` under the guard:
```python
def stop(self) -> None:
    loop = self._loop   # capture before any race
    task = self._task   # capture before any race
    if not self._running or loop is None:
        return
    if task is not None:
        loop.call_soon_threadsafe(task.cancel)
    if self._thread is not None:
        self._thread.join(timeout=15.0)
```
This ensures the captured references are consistent even if the daemon thread NULLs them
out concurrently.

### WR-03: `play_sound` does not guard against `pygame.error` from `load()` or `play()`

**File:** `utils.py:34-40`

**Issue:** `_initialize_audio()` catches `pygame.error` from `mixer.init()`. But
`pygame.mixer.music.load()` (line 34) and `pygame.mixer.music.play()` (line 40) can also
raise `pygame.error` at runtime (e.g., unsupported codec, audio device torn down after
init). These calls are not wrapped in try/except, so a runtime audio error in `play_sound`
will propagate as an unhandled exception to the caller. In the context of this codebase the
callers are `play_notification_sound`, `play_buy_sound`, `play_available_sound`, all of
which are fire-and-forget and do not catch exceptions. Any such error will bubble up to
the orchestrator where it will be absorbed by supervise()'s `except Exception` handler --
so it will not crash the process -- but it will be logged as a plugin crash and increment
the failure budget, which is incorrect behavior (audio failure != plugin failure).

**Fix:**
```python
def play_sound(file_name):
    if not _AUDIO_AVAILABLE:
        return
    writeLog(f"Attempting to play sound: {file_name}", "DEBUG")
    mp3_path = os.path.join(SOUNDS_DIR, f"{file_name}.mp3")
    wav_path = os.path.join(SOUNDS_DIR, f"{file_name}.wav")
    try:
        if os.path.exists(mp3_path):
            pygame.mixer.music.load(mp3_path)
        elif os.path.exists(wav_path):
            pygame.mixer.music.load(wav_path)
        else:
            writeLog(f"Sound file {file_name}.mp3 or {file_name}.wav not found", "ERROR")
            return
        pygame.mixer.music.play()
    except pygame.error as exc:
        writeLog(f"Audio playback error ({exc.__class__.__name__}) -- skipping sound", "WARNING")
```

## Info

### IN-01: `_AUDIO_AVAILABLE` is initialized twice at module scope

**File:** `utils.py:8,24`

**Issue:** `_AUDIO_AVAILABLE` is assigned `False` on line 8 as a module-level type
annotation / default, then immediately overwritten on line 24 by `_initialize_audio()`.
The line 8 assignment is dead code -- it is unconditionally overwritten before any other
code can observe it. This is a minor clarity issue but could mislead a reader into
thinking the variable has a meaningful initial state independent of `_initialize_audio()`.

**Fix:** Remove line 8 and declare only at line 24:
```python
_AUDIO_AVAILABLE: bool = _initialize_audio()
```

### IN-02: `_format_status_table` renders `last_heartbeat` as absolute monotonic seconds

**File:** `core/cli/status.py:34`

**Issue:** `last_heartbeat` is stored as `time.monotonic()` (an epoch-relative float with
no fixed zero point). The table renders it as a raw float with one decimal (e.g.
`"100.0"`). This number is meaningless to a human -- it is not a wall-clock time and has
no intuitive interpretation without knowing the process start monotonic offset. No bug
results, but the field is misleading in the table output. The JSON path is fine since the
raw value is useful programmatically.

**Fix:** Compute age (seconds since heartbeat) in the table formatter:
```python
import time
# Inside _format_status_table, replace the last_heartbeat column:
now = time.monotonic()
hb_raw = rec.get("last_heartbeat", 0.0)
hb_display = f"{now - hb_raw:.1f}s ago" if hb_raw > 0.0 else "never"
```

---

_Reviewed: 2026-06-12T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
