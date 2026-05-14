---
phase: 05-notification-system
plan: 02
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - notifier_registry.py
  - notifiers/__init__.py
  - notifiers/shopbot_notifier_sound.py
  - tests/test_notifier_registry.py
  - tests/test_notifiers_sound.py
autonomous: true
requirements:
  - NOTIF-03
tags:
  - python
  - notifications
  - registry
  - sound
  - pygame
  - wave-1

must_haves:
  truths:
    - "notifier_registry.py exports `async def discover_notifiers(notifiers_dir, *, app_config) -> list[Notifier]` mirroring plugin_registry.discover_async (D-01 consistency)"
    - "notifier_registry uses `NOTIFIER_PREFIX = 'shopbot_notifier_'` and `importlib.util.spec_from_file_location` to load modules (same shape as plugin_registry)"
    - "notifier_registry has NO domain_pattern check and NO verify_coverage helper — notifiers do not route URLs (RESEARCH Pattern 2)"
    - "discover_notifiers stagger is 0 seconds (no chromedriver port race for notifiers); each instantiation runs via asyncio.to_thread for symmetry with plugin discovery"
    - "Per-notifier instantiation failures log a WARNING via writeLog and are skipped (mirrors plugin_registry D-04 Phase A lenient load)"
    - "discover_notifiers files that do not start with NOTIFIER_PREFIX log a WARNING and are skipped (same convention as plugin_registry)"
    - "notifiers/__init__.py exists (may be empty) so the directory is a valid namespace; the actual modules are loaded via importlib.spec_from_file_location, not as a package import"
    - "notifiers/shopbot_notifier_sound.py defines `class SoundNotifier(Notifier)` with `name = 'sound'` and `_lock = threading.Lock()` as a class attribute (CONTEXT pitfall #5; mandatory)"
    - "SoundNotifier.__init__ accepts a `sound_config: SoundNotifierConfig` argument and reads `self.enabled = sound_config.enabled` once (no env vars; sound has no secrets to read)"
    - "SoundNotifier.send body uses `await asyncio.to_thread(self._play_locked, fn)` where `fn` is `play_buy_sound` for action=='purchased' else `play_available_sound` (RESEARCH Q5 action-to-sound mapping)"
    - "SoundNotifier._play_locked is a classmethod or method that holds `cls._lock` (or `self._lock`) for the duration of the `fn()` call — verified by AST grep on the file"
    - "SoundNotifier file imports `play_available_sound`, `play_buy_sound` from `utils` and does NOT call `play_notification_sound` (unused post-Phase-4)"
    - "SoundNotifier.send does NOT raise on play_*_sound failure — it logs via writeLog and continues (a missing sound file should not cancel notification_writer)"
    - "All RED tests in tests/test_notifier_registry.py and tests/test_notifiers_sound.py from Plan 05-01 now PASS"
    - "Full pytest suite remains green across Phase 1/2/3/4/5"
  artifacts:
    - path: "notifier_registry.py"
      provides: "discover_notifiers async discovery of shopbot_notifier_*.py"
      contains: "async def discover_notifiers"
      min_lines: 60
    - path: "notifiers/__init__.py"
      provides: "Namespace marker for notifiers directory"
      min_lines: 0
    - path: "notifiers/shopbot_notifier_sound.py"
      provides: "SoundNotifier (NOTIF-03) with class-level threading.Lock"
      contains: "class SoundNotifier"
      min_lines: 30
    - path: "tests/test_notifier_registry.py"
      provides: "GREEN tests for discover_notifiers"
    - path: "tests/test_notifiers_sound.py"
      provides: "GREEN tests for NOTIF-03 (to_thread wrap + threading.Lock)"
  key_links:
    - from: "notifier_registry.discover_notifiers"
      to: "notifier_base.Notifier"
      via: "instances filtered by issubclass(cls, Notifier)"
      pattern: "issubclass\\(.*Notifier\\)"
    - from: "notifiers/shopbot_notifier_sound.py"
      to: "utils.play_available_sound"
      via: "imported and wrapped in to_thread inside send"
      pattern: "play_(available|buy)_sound"
    - from: "notifiers/shopbot_notifier_sound.py"
      to: "threading.Lock"
      via: "class-level _lock attribute serializes pygame.mixer access"
      pattern: "_lock\\s*=\\s*threading\\.Lock"
---

<objective>
Wave 1 (parallel-safe): ship `notifier_registry.py` and the first notifier — sound. The registry mirrors `plugin_registry.discover_async` minus URL routing. The sound notifier wraps the existing `play_available_sound` / `play_buy_sound` helpers in `asyncio.to_thread` and serializes pygame.mixer.music access via a class-level `threading.Lock`. Flip RED tests in `tests/test_notifier_registry.py` and `tests/test_notifiers_sound.py` to GREEN.

Purpose: This is the lowest-risk Wave 1 plan — no network, no external SDKs, no env-var secrets. The sound notifier is the canonical reference implementation other Wave 1 plans mirror. Building the registry here (rather than in Plan 05-01) keeps Plan 05-01 focused on shapes and tests; the registry's only dependency is the Notifier ABC, which Plan 05-01 ships.

Output: notifier_registry.py + notifiers/__init__.py + notifiers/shopbot_notifier_sound.py + two GREEN test files.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/05-notification-system/05-CONTEXT.md
@.planning/phases/05-notification-system/05-RESEARCH.md
@.planning/phases/05-notification-system/05-01-foundation-and-red-skeletons-PLAN.md
@notifier_base.py
@plugin_registry.py
@utils.py
@logger.py
@config_schema.py
@tests/conftest.py
@tests/test_notifier_registry.py
@tests/test_notifiers_sound.py
</context>

<interfaces>
Target `notifier_registry.py` (new file, full contents — mirrors plugin_registry.discover_async with URL-routing parts deleted):

```python
"""Notifier discovery for ShopPyBot (Phase 5).

Mirrors plugin_registry.discover_async. Loads every shopbot_notifier_*.py
under notifiers/ via importlib, finds the single Notifier subclass per file,
and instantiates it with the app_config slice it needs. Per-notifier failures
log WARNING and are skipped (lenient load; consistent with plugin_registry
Phase A semantics from Phase 2 D-04).
"""
import asyncio
import importlib.util
import inspect
import sys
from pathlib import Path

from logger import writeLog
from notifier_base import Notifier

NOTIFIER_PREFIX = "shopbot_notifier_"


def _load_module(path: Path):
    mod_name = f"shoppybot_notifiers.{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not build spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def _find_notifier_class(module) -> type[Notifier]:
    candidates = [
        cls for _, cls in inspect.getmembers(module, inspect.isclass)
        if issubclass(cls, Notifier)
        and cls is not Notifier
        and cls.__module__ == module.__name__
    ]
    if len(candidates) == 0:
        raise ImportError(f"{module.__name__}: no Notifier subclass found")
    if len(candidates) > 1:
        names = ", ".join(c.__name__ for c in candidates)
        raise ImportError(
            f"{module.__name__}: expected one notifier class, found {len(candidates)}: {names}"
        )
    return candidates[0]


def _instantiate(cls, name: str, app_config) -> Notifier:
    """Pass per-channel config slice + full app_config (SMS needs test_mode)."""
    sub = getattr(app_config.notifications, name, None)
    return cls(sub_config=sub, app_config=app_config)


def _iter_notifier_paths(notifiers_dir: Path):
    for path in sorted(Path(notifiers_dir).glob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        if not path.stem.startswith(NOTIFIER_PREFIX):
            writeLog(
                f"Skipped {path.name} (not auto-loaded; copy to "
                f"{NOTIFIER_PREFIX}<name>.py to enable)",
                "INFO",
            )
            continue
        yield path


def _load_and_instantiate(path: Path, app_config):
    try:
        cls = _find_notifier_class(_load_module(path))
    except Exception as e:
        writeLog(f"Failed to load {path.name}: {e}", "WARNING")
        return None
    name = getattr(cls, "name", "") or path.stem.removeprefix(NOTIFIER_PREFIX)
    try:
        inst = _instantiate(cls, name, app_config)
    except Exception as e:
        writeLog(
            f"Failed to instantiate {cls.__name__} from {path.name}: {e}",
            "WARNING",
        )
        return None
    inst.name = name
    return inst


async def discover_notifiers(
    notifiers_dir: Path,
    *,
    app_config,
) -> list[Notifier]:
    """Walk notifiers_dir for shopbot_notifier_*.py files and return instances.

    Mirrors plugin_registry.discover_async but with stagger=0 (no port race for
    notifiers) and no URL-routing coverage check.
    """
    instances: list[Notifier] = []
    for path in _iter_notifier_paths(notifiers_dir):
        inst = await asyncio.to_thread(_load_and_instantiate, path, app_config)
        if inst is not None:
            instances.append(inst)
    return instances
```

Target `notifiers/__init__.py` (empty file or single comment):

```python
# Notifier namespace. Files are loaded via importlib.spec_from_file_location.
```

Target `notifiers/shopbot_notifier_sound.py`:

```python
"""Sound notifier (NOTIF-03).

Wraps existing utils.play_available_sound / play_buy_sound in asyncio.to_thread
and serializes pygame.mixer.music access via a class-level threading.Lock
(RESEARCH Q5: pygame.mixer.music is single-channel; concurrent .load+.play from
worker threads can interleave and truncate).
"""
import asyncio
import threading

from logger import writeLog
from notifier_base import Notifier, NotificationEvent
from utils import play_available_sound, play_buy_sound


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
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement notifier_registry.discover_notifiers</name>
  <files>notifier_registry.py, notifiers/__init__.py, tests/test_notifier_registry.py</files>
  <read_first>
    - plugin_registry.py (full file; mirror discover_async shape line-by-line minus domain_pattern + verify_coverage)
    - notifier_base.py (Notifier ABC + NOTIFIER_API_VERSION)
    - tests/test_notifier_registry.py (RED tests from Plan 05-01)
    - .planning/phases/05-notification-system/05-RESEARCH.md Pattern 2 (Discovery)
  </read_first>
  <behavior>
    - `from notifier_registry import discover_notifiers; assert inspect.iscoroutinefunction(discover_notifiers)` succeeds.
    - Stub two valid notifier files under `tmp_path/notifiers/shopbot_notifier_a.py` and `shopbot_notifier_b.py` each containing a minimal Notifier subclass; `await discover_notifiers(tmp_path/'notifiers', app_config=stub)` returns two instances. Order is sorted by filename.
    - A file `tmp_path/notifiers/not_a_notifier.py` is logged as WARNING-INFO and skipped (no exception).
    - A file `tmp_path/notifiers/shopbot_notifier_broken.py` whose module raises ImportError at exec_module time is logged WARNING and skipped (no exception propagates).
    - Each instantiation runs via asyncio.to_thread (mirrors plugin_registry).
    - The function does NOT touch URL routing and does NOT have a verify_coverage helper.
    - Each instantiated notifier has its `.name` attribute set to the filename suffix (e.g. `shopbot_notifier_sound.py` -> `name = "sound"` if class attribute is empty; otherwise the class attribute wins per `getattr(cls, "name", "")`).
    - All RED tests in tests/test_notifier_registry.py flip to GREEN.
  </behavior>
  <action>
    1. Create `notifier_registry.py` with the full contents from <interfaces>. Match plugin_registry.py's docstring + private helper style. Each helper function < 30 lines.

    2. Create `notifiers/__init__.py` with the single comment line shown in <interfaces>. The file may be empty; what matters is the directory exists.

    3. Flip `tests/test_notifier_registry.py` to GREEN: confirm the two RED tests from Plan 05-01 now run. If the RED tests reference `tmp_path/notifiers` stub modules, create those stubs via `textwrap.dedent` inside the test (use the plugin_registry test style as a reference). Each stub module defines a unique Notifier subclass overriding `send` to record calls. The test passes an `appConfigStub` that has a `notifications` attribute exposing whatever sub-configs the stub notifiers expect (use SimpleNamespace).

    4. If the RED tests in Plan 05-01 are missing edge-case coverage, ADD tests for:
       - test_nonPrefixFileSkipped: drop a `not_a_notifier.py` in tmp dir; assert it is skipped without exception and a WARNING/INFO log fires (capture via caplog if logger is configured for it; otherwise assert the notifier list excludes it).
       - test_brokenModuleLogged: drop `shopbot_notifier_broken.py` that raises at import time; assert discover returns the other notifiers without raising.

    5. Run `rtk pytest -q tests/test_notifier_registry.py`. All tests GREEN.

    6. Run `rtk pytest -x -q` over the full suite. Pre-existing tests still pass; Plan 05-01 RED suite remains RED for files NOT touched by this plan (notifier writer, three other notifiers).
  </action>
  <verify>
    <automated>python -c "import inspect; from notifier_registry import discover_notifiers; assert inspect.iscoroutinefunction(discover_notifiers)"</automated>
    <automated>rtk grep -n "NOTIFIER_PREFIX\s*=\s*\"shopbot_notifier_\"" notifier_registry.py</automated>
    <automated>rtk pytest -q tests/test_notifier_registry.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_notifiers_discord.py --ignore=tests/test_notifiers_email.py --ignore=tests/test_notifiers_sms.py --ignore=tests/test_notification_writer.py</automated>
  </verify>
  <acceptance_criteria>
    - notifier_registry.py exists with discover_notifiers (async) + private helpers
    - notifiers/__init__.py exists
    - tests/test_notifier_registry.py is fully GREEN
    - No verify_coverage / domain_pattern code in notifier_registry.py
    - Pre-existing suite green; other RED files remain RED for their respective downstream plans
  </acceptance_criteria>
  <done>Notifier discovery operational. Wave 1 sibling plans (Discord/Email/SMS) can rely on `notifiers/shopbot_notifier_*.py` being auto-loaded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement SoundNotifier (NOTIF-03)</name>
  <files>notifiers/shopbot_notifier_sound.py, tests/test_notifiers_sound.py</files>
  <read_first>
    - notifier_base.py (Notifier ABC; ensure send signature matches)
    - utils.py (existing play_available_sound, play_buy_sound; note play_notification_sound is unused post-Phase-4)
    - notifier_registry.py (just-created; confirm _instantiate kwargs are `sub_config` and `app_config`)
    - tests/test_notifiers_sound.py (RED tests from Plan 05-01)
    - .planning/phases/05-notification-system/05-RESEARCH.md Pattern Q5 (pygame thread safety)
  </read_first>
  <behavior>
    - `from notifiers.shopbot_notifier_sound import SoundNotifier` succeeds (test imports via the package-style path AND via discover_notifiers path; both work because discover loads by file path).
    - `SoundNotifier(sub_config=SoundNotifierConfig(enabled=True), app_config=stub).enabled is True`.
    - `SoundNotifier(sub_config=SoundNotifierConfig(enabled=False), app_config=stub).enabled is False`.
    - `SoundNotifier._lock` is an instance of `threading.Lock` AND is a class attribute (shared across instances).
    - AST inspection of `notifiers/shopbot_notifier_sound.py` finds `asyncio.to_thread` inside the `send` function body.
    - AST inspection finds `play_buy_sound` referenced when event.action == "purchased", `play_available_sound` otherwise.
    - When `play_available_sound` raises (monkeypatch to raise RuntimeError), `await SoundNotifier(...).send(event)` returns without raising and a WARNING is logged.
    - Concurrent invocation: schedule 4 send() coroutines for the same instance via asyncio.gather; assert play_*_sound was called 4 times AND the lock was held during each call (verify via a fake play_* that records lock state via `cls._lock.locked()` at call time — should be True throughout).
    - All RED tests in tests/test_notifiers_sound.py flip to GREEN.
  </behavior>
  <action>
    1. Create `notifiers/shopbot_notifier_sound.py` with the full contents from <interfaces>. Single class < 30 lines per method. Keep `_lock` as a class attribute (not instance) so it serializes pygame access across ALL SoundNotifier instances (defensive — there should only ever be one anyway).

    2. Flip `tests/test_notifiers_sound.py` to GREEN. Tests should:
       - Import via package path: `from notifiers.shopbot_notifier_sound import SoundNotifier`.
       - Build a SoundNotifierConfig stub or use the real class from config_schema.
       - Use `monkeypatch.setattr("notifiers.shopbot_notifier_sound.play_available_sound", recorder)` to record calls.
       - Verify lock is class-level: `assert SoundNotifier._lock is SoundNotifier._lock` AND `assert isinstance(SoundNotifier._lock, type(threading.Lock()))`.
       - AST test: parse the file, walk for `Call` nodes where `func.attr == "to_thread"`, assert at least one is inside the `send` async function body.
       - Resilience test: monkeypatch play_available_sound to raise; await send; assert no exception propagated AND writeLog was called with a "playback failed" message (capture writeLog via monkeypatch).

    3. Run `rtk pytest -q tests/test_notifiers_sound.py`. All GREEN.

    4. Run `rtk pytest -x -q` over the full suite. Pre-existing green; other RED files untouched.
  </action>
  <verify>
    <automated>python -c "from notifiers.shopbot_notifier_sound import SoundNotifier; import threading; assert isinstance(SoundNotifier._lock, type(threading.Lock()))"</automated>
    <automated>rtk grep -n "asyncio.to_thread" notifiers/shopbot_notifier_sound.py</automated>
    <automated>rtk grep -n "play_buy_sound\|play_available_sound" notifiers/shopbot_notifier_sound.py</automated>
    <automated>rtk pytest -q tests/test_notifiers_sound.py</automated>
    <automated>rtk pytest -x -q --ignore=tests/test_notifiers_discord.py --ignore=tests/test_notifiers_email.py --ignore=tests/test_notifiers_sms.py --ignore=tests/test_notification_writer.py</automated>
  </verify>
  <acceptance_criteria>
    - notifiers/shopbot_notifier_sound.py exists with SoundNotifier subclass
    - Class-level threading.Lock present
    - send() wraps utils.play_*_sound in asyncio.to_thread
    - Playback exceptions logged + swallowed
    - tests/test_notifiers_sound.py fully GREEN
    - Pre-existing suite green
  </acceptance_criteria>
  <done>NOTIF-03 implemented. The sound notifier is the canonical reference for Wave 1 sibling notifiers (Discord, Email, SMS).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| notifier_registry module loading | Importing arbitrary `shopbot_notifier_*.py` from disk; broken modules must not crash discovery |
| pygame.mixer process-global state | Concurrent worker threads can interleave .load/.play |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-02-BROKEN-MODULE | Denial of Service | notifier_registry._load_and_instantiate | mitigate | Per-module exceptions caught and logged WARNING; other notifiers continue to load (mirrors Phase 2 D-04 Phase A lenient load) |
| T-05-02-PYGAME-INTERLEAVE | Denial of Service (silent UX) | SoundNotifier | mitigate | Class-level threading.Lock serializes pygame.mixer.music.load + .play (RESEARCH Q5) |
| T-05-02-SOUND-MISSING-FILE | Denial of Service | SoundNotifier.send | accept | utils.play_sound already handles missing files via writeLog; notifier wraps in try/except and continues |
</threat_model>

<verification>
- `python -c "import inspect; from notifier_registry import discover_notifiers; assert inspect.iscoroutinefunction(discover_notifiers)"`
- `python -c "from notifiers.shopbot_notifier_sound import SoundNotifier; import threading; assert isinstance(SoundNotifier._lock, type(threading.Lock()))"`
- `rtk pytest -q tests/test_notifier_registry.py tests/test_notifiers_sound.py` shows all GREEN
- `rtk pytest -x -q --ignore=tests/test_notifiers_discord.py --ignore=tests/test_notifiers_email.py --ignore=tests/test_notifiers_sms.py --ignore=tests/test_notification_writer.py` green
</verification>

<success_criteria>
- notifier_registry.py operational with async discovery
- notifiers/ directory established with __init__.py + shopbot_notifier_sound.py
- SoundNotifier implements NOTIF-03 with to_thread + threading.Lock
- Two RED files from Plan 05-01 flipped to GREEN
</success_criteria>

<output>
After completion, create `.planning/phases/05-notification-system/05-02-SUMMARY.md`
</output>
