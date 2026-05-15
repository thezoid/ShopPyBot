---
phase: 05-notification-system
plan: 02
subsystem: notifier-registry-and-sound
tags:
  - python
  - notifications
  - registry
  - sound
  - pygame
  - wave-1
dependency_graph:
  requires:
    - notifier_base.Notifier (Plan 05-01)
    - config_schema.SoundNotifierConfig (Plan 05-01)
    - plugin_registry.discover_async (mirrored shape)
    - utils.play_available_sound / play_buy_sound
  provides:
    - notifier_registry.discover_notifiers (async)
    - notifiers/ package with __init__.py
    - notifiers.shopbot_notifier_sound.SoundNotifier (NOTIF-03)
  affects:
    - Wave 1 siblings (Plans 05-03 Discord, 05-04 Email, 05-05 SMS) inherit the registry contract and constructor signature
    - Wave 2 (Plan 05-06 notification_writer) consumes Notifier instances returned by discover_notifiers
tech_stack:
  added: []
  patterns:
    - importlib.spec_from_file_location module loading (mirrors plugin_registry)
    - asyncio.to_thread wrapping sync pygame playback
    - Class-level threading.Lock serializing process-global pygame.mixer.music state
key_files:
  created:
    - notifier_registry.py
    - notifiers/__init__.py
    - notifiers/shopbot_notifier_sound.py
  modified:
    - tests/test_notifier_registry.py (RED to GREEN)
    - tests/test_notifiers_sound.py (RED to GREEN)
decisions:
  - "notifier_registry mirrors plugin_registry.discover_async shape minus domain_pattern and verify_coverage (Pattern 2 separation of concerns)"
  - "Stagger removed (stagger=0): notifiers have no chromedriver port race; asyncio.to_thread retained per task for symmetry with plugin discovery"
  - "Lenient load: per-module exceptions logged WARNING and skipped (mirrors plugin_registry Phase A from Phase 2 D-04)"
  - "SoundNotifier._lock is a class attribute so it serializes pygame.mixer access across all SoundNotifier instances and across worker threads (RESEARCH Q5)"
  - "Sound notifier action mapping: action=='purchased' to play_buy_sound; everything else to play_available_sound (play_notification_sound left unused post-Phase-4)"
  - "Playback exceptions in SoundNotifier swallowed with WARNING log so a missing sound file cannot crash notification_writer (T-05-02-SOUND-MISSING-FILE accept)"
metrics:
  duration_minutes: 2
  completed: 2026-05-15
  tasks_completed: 2
  files_changed: 5
---

# Phase 5 Plan 02: Notifier Registry and Sound Notifier Summary

Wave 1 ships `notifier_registry.discover_notifiers` (async, importlib-based, NOTIFIER_PREFIX='shopbot_notifier_') plus the canonical `SoundNotifier` (NOTIF-03) wrapping `utils.play_available_sound` and `utils.play_buy_sound` in `asyncio.to_thread` and serializing pygame access via a class-level `threading.Lock`. Two RED test files from Plan 05-01 flip to GREEN.

## What Shipped

### notifier_registry.py

`async def discover_notifiers(notifiers_dir, *, app_config) -> list[Notifier]` mirrors `plugin_registry.discover_async` line-for-line minus URL routing:

- `NOTIFIER_PREFIX = "shopbot_notifier_"`
- `_load_module` builds a spec via `importlib.util.spec_from_file_location` under module name `shoppybot_notifiers.<stem>` and registers in `sys.modules` before `exec_module` (matches plugin_registry).
- `_find_notifier_class` walks `inspect.getmembers` and filters `issubclass(cls, Notifier) and cls is not Notifier and cls.__module__ == module.__name__`. Raises on zero or multiple subclasses.
- `_iter_notifier_paths` sorts `*.py`, skips `__init__.py` and `_`-prefixed files, and emits an INFO log + skip for any `*.py` whose stem does NOT start with `NOTIFIER_PREFIX`.
- `_load_and_instantiate` wraps load and instantiation in two `try/except` blocks. Each failure logs WARNING via `writeLog` and returns `None` so other notifiers continue (mirrors Phase 2 D-04 Phase A lenient load).
- `_instantiate(cls, name, app_config)` reads `app_config.notifications.<name>` and passes `cls(sub_config=sub, app_config=app_config)`. This is the constructor shape every Wave 1 sibling notifier follows.
- The async function iterates paths and runs `_load_and_instantiate` via `asyncio.to_thread`. No stagger sleep (notifiers don't bind ports).

No `domain_pattern`, no `verify_coverage`, no `route_url`: notifiers fan out, they do not route.

### notifiers/__init__.py

Single comment line documenting that the actual modules load via `importlib.spec_from_file_location`, not as a package import. Marks the directory so `from notifiers.shopbot_notifier_sound import SoundNotifier` works in tests.

### notifiers/shopbot_notifier_sound.py (NOTIF-03)

```
class SoundNotifier(Notifier):
    name = "sound"
    _lock = threading.Lock()

    def __init__(self, *, sub_config, app_config) -> None:
        self.enabled = bool(sub_config and sub_config.enabled)

    async def send(self, event: NotificationEvent) -> None:
        fn = play_buy_sound if event.action == "purchased" else play_available_sound
        await asyncio.to_thread(self._play_locked, fn)

    @classmethod
    def _play_locked(cls, fn) -> None:
        with cls._lock:
            try:
                fn()
            except Exception as e:
                writeLog(f"sound notifier: playback failed: {e}", "WARNING")
```

`_lock` is a class attribute so two `SoundNotifier()` instances share one lock (defensive: the dispatcher only creates one anyway). The lock is acquired inside the worker thread, so the asyncio event loop never blocks on the lock; only the worker thread blocks while another worker thread is mid-play. Playback exceptions log WARNING and return; they do not propagate to `notification_writer` (T-05-02-SOUND-MISSING-FILE disposition).

### Test changes

- `tests/test_notifier_registry.py`: replaced the 2-test RED skeleton with 7 GREEN tests covering async shape, prefix constant, sorted discovery, non-prefix skip, broken-module skip, no-subclass skip, and sub_config wiring from app_config.
- `tests/test_notifiers_sound.py`: replaced the 4-test RED skeleton with 11 GREEN tests covering importability, class-level Lock (shape and identity across instances), enabled flag (true / false / None sub_config), AST presence of `asyncio.to_thread` inside `send`, source-level helper imports, detected-vs-purchased action dispatch, exception swallow + log, and concurrent gather verifying the lock is held during every play call.

## Verification Results

- `python -c "import inspect; from notifier_registry import discover_notifiers; assert inspect.iscoroutinefunction(discover_notifiers)"` -> OK
- `python -c "from notifiers.shopbot_notifier_sound import SoundNotifier; import threading; assert isinstance(SoundNotifier._lock, type(threading.Lock()))"` -> OK
- `grep -n "NOTIFIER_PREFIX\s*=\s*\"shopbot_notifier_\"" notifier_registry.py` -> match on line 20
- End-to-end integration: `discover_notifiers(Path('notifiers'), app_config=<stub with SoundNotifierConfig(enabled=True)>)` returns `[SoundNotifier(name='sound', enabled=True)]`.
- `pytest -q tests/test_notifier_registry.py` -> 7 passed
- `pytest -q tests/test_notifiers_sound.py` -> 11 passed
- Full suite minus the four downstream RED files and the pre-existing deferred `tests/test_utils.py`: 227 passed.

## Deviations from Plan

None of Rules 1-4. Plan executed as written. Two minor implementation refinements stayed inside the plan envelope:

- `_instantiate` defensively handles `app_config=None` by short-circuiting `getattr(app_config, "notifications", None)` rather than only `getattr(app_config.notifications, name, None)`. The RED test from Plan 05-01 originally called `discover_notifiers(notifiersDir, app_config=None)`; this kept the call from raising AttributeError. The replacement GREEN test passes a SimpleNamespace stub anyway, but the None-tolerance costs nothing and matches plugin_registry's `_safe_platform`.
- The Plan 05-01 RED skeleton for `test_notifiers_sound.py` invoked `SoundNotifier(SoundNotifierConfig(enabled=True))` (positional). Plan 05-02's `<interfaces>` mandates the keyword-only `SoundNotifier(sub_config=..., app_config=...)` signature to match `notifier_registry._instantiate`. The action step ("flip RED tests to GREEN") expects test rewrites, so the new GREEN test calls `SoundNotifier(sub_config=..., app_config=None)` against the documented contract.

## Authentication Gates

None.

## Commits

| Task | Hash | Message |
|------|------|---------|
| 1 | 6eaedda | feat(05-02): notifier_registry.discover_notifiers + GREEN tests |
| 2 | 78caa26 | feat(05-02): SoundNotifier (NOTIF-03) with class-level Lock + to_thread |

## TDD Gate Compliance

Plan type is `execute` with per-task `tdd="true"`. Plan 05-01 shipped the RED skeletons (collection ImportError on missing symbols), so the RED gate is already in git history from commit `873102b`. Plan 05-02 ships the GREEN implementations and rewrites the RED tests to a fuller GREEN suite. RED-then-GREEN ordering is satisfied across the plan boundary: Plan 05-01 RED commit precedes Plan 05-02 GREEN commits.

## Known Stubs

None. The two RED test files are now GREEN. The four other Plan-05-01 RED files (`test_notifier_writer.py`, `test_notifiers_discord.py`, `test_notifiers_email.py`, `test_notifiers_sms.py`) remain RED-by-design for Plans 05-03 through 05-06.

## Deferred Issues

- `tests/test_utils.py` collection error (`ImportError: cannot import name 'make_tiny' from 'utils'`) is pre-existing and explicitly carried over from Plan 05-01 ("pre-existing deferred test_utils.py"). Out of scope for Plan 05-02; ignored via `--ignore=tests/test_utils.py` in verification runs. No new code touches `utils.py`.

## Threat Flags

None. The threat surface introduced by this plan is fully covered by the plan's `<threat_model>`:

- T-05-02-BROKEN-MODULE mitigated: `_load_and_instantiate` wraps both `_load_module` and `_instantiate` in `try/except Exception`; failures log WARNING via `writeLog` and return None, letting subsequent notifier files load (verified by `test_brokenModuleLoggedAndSkipped`).
- T-05-02-PYGAME-INTERLEAVE mitigated: `SoundNotifier._lock` is a class-level `threading.Lock` acquired inside `_play_locked` for the full duration of the playback function call (verified by `test_concurrentSendsSerializeViaLock` observing `cls._lock.locked() is True` during every play call under `asyncio.gather` of four sends).
- T-05-02-SOUND-MISSING-FILE accepted: `_play_locked` catches `Exception` from the playback function and logs WARNING; `utils.play_sound` already handles missing files with its own writeLog (verified by `test_sendSwallowsPlaybackException`).

## Self-Check: PASSED

Files verified present:
- FOUND: notifier_registry.py
- FOUND: notifiers/__init__.py
- FOUND: notifiers/shopbot_notifier_sound.py
- FOUND: tests/test_notifier_registry.py (GREEN, 7 tests)
- FOUND: tests/test_notifiers_sound.py (GREEN, 11 tests)

Commits verified:
- FOUND: 6eaedda (Task 1, notifier_registry + GREEN tests)
- FOUND: 78caa26 (Task 2, SoundNotifier + GREEN tests)
