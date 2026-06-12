# Phase 24: Health Surface + Server Safety - Research

**Researched:** 2026-06-12
**Domain:** Python async health registry, CLI subcommand, pygame headless guard, notification dedup
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- `core/health.py` `HealthRegistry`: per-plugin record with `status`, `last_heartbeat`,
  `consecutive_errors`, `items_checked`, `orders_confirmed`. Updated by `run_plugin`
  (heartbeat + items_checked per cycle), `supervise` (consecutive_errors, status
  transitions: park/relaunch/degraded), and the confirmation path (orders_confirmed).
- `get_status()` returns `{"running": bool, "uptime_secs": float, "plugins": {name: {"status": str, "last_heartbeat": float, "consecutive_errors": int, "items_checked": int, "orders_confirmed": int}}}`.
- `status` enum values: `running` | `degraded` | `parked` | `relaunching` | `idle`.
- Single `HealthRegistry` instance created in `async_main`, passed to `supervise`/`run_plugin`;
  `BotService` holds a reference so `get_status()` can read it.
- `health_degraded` fires when `consecutive_errors > alert_on_errors`; armed/disarmed per-plugin
  dedup (in-memory on HealthRegistry); distinct from `plugin_parked`.
- New `shoppybot status` CLI: per-plugin table; `--json` flag; no network call.
- Existing `/status` FastAPI endpoint unchanged; richer dict flows through.
- SRV-01: wrap `pygame.mixer.init()` in `utils.py` (line 38) in try/except; set `_AUDIO_AVAILABLE = False` on failure; play functions become no-ops; one-time INFO log.
- `BotService` records start timestamp in `run()`; `uptime_secs = now - start`; `running` reflects service state.

### Claude's Discretion

None noted.

### Deferred Ideas (OUT OF SCOPE)

- Web-dashboard health panel / visual redesign.
- Historical health metrics / time-series.
- Live headless-server run verification (pygame no-op on a real no-audio host; SIGTERM on deploy OS) -> UAT debt.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REL-07 | `BotService.get_status()` returns structured per-plugin health surface (liveness, last-activity, last-error) queryable from CLI and web UI; sustained degradation signaled through notification dispatcher. | HealthRegistry + get_status expansion + supervise hook points + health_degraded dispatcher wiring documented below. |
| SRV-01 | Sound notifier degrades to silent no-op on headless host with no audio device instead of crashing at import. | Exact pygame crash surface, guard pattern, and no-op play function pattern documented below. |

</phase_requirements>

---

## Summary

Phase 24 adds a thin read-only health surface on top of the already-built P22 supervisor.
The core work is three coordinated additions: (1) `core/health.py` holding a simple dict
of per-plugin counters that the supervisor and poll loop write to, (2) `BotService.get_status()`
expanded to project that dict into the locked JSON shape, and (3) a `health_degraded`
notification dispatched through the existing fan-out using the established armed/disarmed
dedup already present for price alerts. The pygame guard is self-contained and touches
only `utils.py`.

The key insight is that P22 already tracks `consecutive_errors` and `failure_times` inside
`supervise()` as local variables. Phase 24 does not replace that tracking: it wires a
`HealthRegistry` reference through the same call chain so the supervisor can write a
parallel observable copy. The `health_degraded` alert fires at a crossing point inside
supervise's existing exception handler, before the park threshold triggers.

**Primary recommendation:** Wire `HealthRegistry` as an optional kwarg through
`supervise` and `run_plugin` using the same `registry=None` pattern already established
in Phase 22; default to None so no existing call site breaks.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HealthRegistry state management | Async orchestrator (`core/orchestrator.py`) | `core/health.py` (storage) | Supervisor and run_plugin own writes; health.py owns the data structure |
| get_status() read path | BotService (`core/service.py`) | None | BotService is the stable API seam; web + CLI both read through it |
| health_degraded alert | Async orchestrator (`supervise`) | Notification dispatcher | Threshold crossing happens in supervise; dispatcher owns fan-out |
| CLI status subcommand | CLI handler (`core/cli/status.py`) | BotService | Handler calls `svc.get_status()`; no direct health import |
| /status web endpoint | Existing FastAPI route (unchanged) | BotService | Already returns `svc.get_status()`; no route change needed |
| pygame headless guard | `utils.py` module level | None | Import-time guard; self-contained |

---

## Standard Stack

No new external packages. All work is pure Python stdlib + project-internal modules.

### Core (existing, no new deps)
| Module | Role | Notes |
|--------|------|-------|
| `time` stdlib | `time.monotonic()` for `last_heartbeat` float | Already used in orchestrator |
| `pygame` (pinned in requirements.txt) | Audio; guarded by `_AUDIO_AVAILABLE` | No version change |
| `asyncio` stdlib | Async safety of HealthRegistry reads | Same-loop access, no locks needed |

### No new packages required

The Package Legitimacy Audit section is omitted: this phase installs zero external packages.

---

## Architecture Patterns

### System Architecture Diagram

```
async_main()
    |
    +-- creates HealthRegistry()
    |       |
    |       +-- passed to supervise(health=registry) per plugin
    |       +-- passed to run_plugin(health=registry) per plugin
    |       +-- stored on BotService._health_registry
    |
    +-- supervise(plugin, ..., health=registry)
    |       |
    |       +-- on each run_plugin return: registry.set_status(name, "running")
    |       +-- on each Exception: registry.record_error(name)
    |       |       |
    |       |       +-- if consecutive_errors > alert_on_errors AND NOT armed:
    |       |               dispatcher.notify(health_degraded event)
    |       |               registry.arm(name)
    |       +-- on park: registry.set_status(name, "parked")
    |       +-- on relaunch attempt: registry.set_status(name, "relaunching")
    |       +-- on recovery (consecutive_errors < threshold): registry.disarm(name)
    |
    +-- run_plugin(plugin, ..., health=registry)
            |
            +-- per cycle start: registry.heartbeat(name)
            +-- per item checked: registry.inc_items_checked(name)
            +-- (orders_confirmed incremented by _enqueue_buy_result path)
```

### Recommended Project Structure

```
core/
    health.py          # NEW: HealthRegistry class
    service.py         # EDIT: get_status() expansion + start_time + _health_registry ref
    orchestrator.py    # EDIT: async_main wiring + supervise hooks + run_plugin hooks
    cli/
        status.py      # NEW: handle_status + _format_status_table
        __init__.py    # EDIT: register 'status' subcommand
utils.py               # EDIT: pygame import-time guard
tests/
    test_health.py     # NEW: HealthRegistry unit tests
    test_cli_status.py # NEW: CLI status handler tests
    test_utils.py      # EDIT: pygame guard tests (currently a placeholder)
```

### Pattern 1: HealthRegistry Data Model

**What:** A plain dict-of-dicts wrapped in a class with named mutator methods. No locks
needed because all writes happen on the single asyncio event loop; reads from `get_status()`
on the web handler run on the same loop (via `await asyncio.to_thread` or directly from
the FastAPI request handler which is also on the same loop as `BotService`).

**Thread-safety note:** The web UI runs in a separate uvicorn thread via
`BotService.start()` -> daemon thread -> own event loop. `svc.get_status()` is called
from the FastAPI handler on uvicorn's event loop, NOT from the bot's event loop. The
health registry is written by the bot loop's tasks. This means reads and writes CAN occur
from different threads.

**Resolution:** HealthRegistry only holds primitive Python types (int, float, str). CPython
GIL makes individual attribute reads/writes atomic for primitive types. The read returns a
snapshot copy (dict-of-dicts) via `get_snapshot()`, so the web caller sees a consistent-at-point-in-time view even under concurrent writes. No asyncio.Lock needed for this use case.
[VERIFIED: CPython GIL atomicity for primitive attribute access -- standard Python threading model]

```python
# Source: project pattern (verified from core/orchestrator.py Phase 22 structure)
import time

class HealthRegistry:
    """Per-plugin health counters. Written by orchestrator tasks, read by BotService."""

    _IDLE_STATUS = "idle"

    def __init__(self) -> None:
        self._plugins: dict[str, dict] = {}

    def _ensure(self, name: str) -> None:
        if name not in self._plugins:
            self._plugins[name] = {
                "status": self._IDLE_STATUS,
                "last_heartbeat": 0.0,
                "consecutive_errors": 0,
                "items_checked": 0,
                "orders_confirmed": 0,
                "_degraded_armed": False,  # private dedup flag
            }

    def heartbeat(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["last_heartbeat"] = time.monotonic()

    def set_status(self, name: str, status: str) -> None:
        self._ensure(name)
        self._plugins[name]["status"] = status

    def record_error(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["consecutive_errors"] += 1

    def reset_errors(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["consecutive_errors"] = 0

    def inc_items_checked(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["items_checked"] += 1

    def inc_orders_confirmed(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["orders_confirmed"] += 1

    def is_degraded_armed(self, name: str) -> bool:
        self._ensure(name)
        return self._plugins[name]["_degraded_armed"]

    def arm_degraded(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["_degraded_armed"] = True

    def disarm_degraded(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["_degraded_armed"] = False

    def get_snapshot(self) -> dict[str, dict]:
        """Return a shallow copy of the per-plugin state, stripping private keys."""
        return {
            name: {k: v for k, v in rec.items() if not k.startswith("_")}
            for name, rec in self._plugins.items()
        }
```

[ASSUMED: specific method names and snapshot-copy pattern -- these are implementation recommendations, not verified from an external authoritative source. The threading model analysis is standard CPython behavior.]

### Pattern 2: supervise() Hook Points

The existing `supervise()` in `core/orchestrator.py` (L90-L153) has these exact hook sites:

```python
# EXISTING code structure (verified from orchestrator.py L114-L153):
while True:
    try:
        await run_plugin(plugin, write_queue, poll_interval, dispatcher=dispatcher, cfg=cfg)
        attempt = 0  # Line 117 -- healthy run reset
        # HOOK: set status "running", reset_errors, disarm_degraded here

    except asyncio.CancelledError:
        raise

    except Exception as exc:
        now = time.monotonic()
        failure_times.append(now)
        # window eviction (L124)
        # HOOK: record_error(name) here
        # HOOK: if consecutive_errors > alert_on_errors AND NOT armed: fire health_degraded, arm

        if len(failure_times) >= n_budget:
            await _park_plugin(plugin, n_budget, dispatcher)
            # HOOK: set_status("parked") here
            return

        if _is_browser_dead_exc(exc):
            # HOOK: set_status("relaunching") here
            ...
            try:
                await plugin.relaunch()
            except Exception:
                ...

        await asyncio.sleep(delay)
        attempt += 1
```

**Critical ordering for `health_degraded` vs `plugin_parked`:**
- `health_degraded` fires when `consecutive_errors > alert_on_errors` AND `len(failure_times) < n_budget`
- `plugin_parked` fires when `len(failure_times) >= n_budget`
- These are SEPARATE checks. `health_degraded` fires BEFORE park.
- Since `consecutive_errors` and `len(failure_times)` both increment per crash, they will both
  be equal at the crossing point -- but the alert_on_errors config threshold is the same value
  (`n_budget`). This means `health_degraded` fires on the same crash as `plugin_parked` unless
  the thresholds differ. The CONTEXT.md decision says `health_degraded` fires before park:
  the planner must decide whether to fire `health_degraded` at `>= alert_on_errors` and
  `plugin_parked` at `>= n_budget + 1`, or at different thresholds. [ASSUMED: threshold
  separation strategy -- needs explicit decision in planning.]

**Simplest correct wiring approach:** Use `len(failure_times)` (already maintained by
`supervise`) as the proxy for `consecutive_errors` rather than maintaining a separate counter
in HealthRegistry. This avoids duplicating the failure-window logic. The HealthRegistry
`consecutive_errors` field is then `len(failure_times)` at the time of each update, not a
separate independent counter.

[VERIFIED: exact supervise() code structure from core/orchestrator.py lines 90-153]

### Pattern 3: run_plugin() Hook Points

```python
# EXISTING run_plugin structure (verified from orchestrator.py L278-L310):
async def run_plugin(plugin, write_queue, poll_interval, dispatcher=None, cfg=None) -> None:
    loop = asyncio.get_running_loop()
    item_timeout = ...
    while True:
        try:
            items = await loop.run_in_executor(None, get_items_sync)
        except sqlite3.OperationalError:
            # skip cycle
            await asyncio.sleep(...)
            continue
        # HOOK: heartbeat(name) + set_status("running") here (once per cycle top)
        for name, link, auto_buy, quantity, purchased in items:
            if purchased:
                continue
            if not any(p in (link or "") for p in plugin.domain_patterns):
                continue
            # HOOK: inc_items_checked(name) here (per matched item, before _check_and_buy)
            try:
                async with asyncio.timeout(item_timeout):
                    await _check_and_buy(...)
            except TimeoutError:
                ...
        await asyncio.sleep(...)
```

[VERIFIED: exact run_plugin() structure from core/orchestrator.py lines 278-310]

### Pattern 4: orders_confirmed Hook Point

The confirmation enqueue path is in `_enqueue_buy_result()` (orchestrator.py L351-L366):

```python
async def _enqueue_buy_result(name, link, platform, order_id, write_queue, dispatcher) -> None:
    if dispatcher is not None:
        await dispatcher.notify(...)
    if order_id is not None:
        ts = datetime.now(timezone.utc).isoformat()
        await write_queue.put(("confirmed", link, order_id, ts))
        # HOOK: health_registry.inc_orders_confirmed(platform) here
    else:
        await write_queue.put(("purchased", link))
        # HOOK: inc_orders_confirmed here too (legacy confirmed path)
```

**Problem:** `_enqueue_buy_result` does not currently receive a `health_registry` argument.
It receives `name, link, platform, order_id, write_queue, dispatcher`. The registry must be
threaded in as an additional kwarg, OR `inc_orders_confirmed` can be called one level up in
`_try_auto_buy` after `_enqueue_buy_result` returns. The latter avoids touching `_enqueue_buy_result`'s signature.
[ASSUMED: preferred wiring site -- either approach is valid; planner decides]

[VERIFIED: _enqueue_buy_result signature from core/orchestrator.py lines 351-366]

### Pattern 5: health_degraded Notification

The existing notification pattern (verified from `_build_event` in orchestrator.py L155-L164
and price alert dedup in `_evaluate_price_triggers` L229-L252):

```python
# Dispatch a new notification_type by adding a new action string to _build_event call.
# NotificationEvent.action is a free-form str field (verified from notifications/base.py L44):
#     action: str  # "detected" | "purchased" | "price_drop"
# Adding "health_degraded" requires NO dataclass change -- it is just a new action value.

# The dedup pattern (from _evaluate_price_triggers, verified from orchestrator.py L229-L252):
#   1. Check trigger condition
#   2. Read armed state
#   3. If armed: return (no-op)
#   4. If not armed: dispatch + arm
#   5. On recovery (trigger clears): disarm
#
# For health_degraded, the armed state lives in HealthRegistry._plugins[name]["_degraded_armed"]
# (in-memory per-plugin, not DB). This matches the CONTEXT.md decision.
```

**Notifier behavior for `health_degraded` action:** All existing notifiers (SoundNotifier,
DiscordNotifier, EmailNotifier, SmsNotifier) fall through to their default/"other" branch
when they receive an unknown action string. Specifically:
- `SoundNotifier.send()`: action not "detected" or "purchased" -> `play_notification_sound()`
  (verified from notifications/sound_notifier.py L20-L27)
- Discord/Email/SMS notifiers: likely render the action field in the message body or subject.
  No special health_degraded formatting required; the item_name field can be the plugin name.

**NotificationEvent fields for health_degraded:**
```python
NotificationEvent(
    item_name=plugin.__class__.__name__,  # plugin name as the "item"
    item_url="",                          # no URL for a health event
    platform=plugin.__class__.__name__,
    timestamp=datetime.now(timezone.utc),
    action="health_degraded",
    # price_cents, target_price_cents, pct_from_target all None (default)
)
```

[VERIFIED: NotificationEvent dataclass fields and SoundNotifier dispatch from project source]
[ASSUMED: empty string for item_url is acceptable -- no official constraint found, but consistent with plugin_parked usage in _build_event L87]

### Pattern 6: BotService.get_status() Expansion

**Current shape** (verified from core/service.py L68-L70):
```python
def get_status(self) -> dict:
    """Return plain running-state dict. Safe to call before start()."""
    return {"running": self._running}
```

**Target shape** (from CONTEXT.md):
```python
{
    "running": bool,
    "uptime_secs": float,
    "plugins": {
        plugin_name: {
            "status": str,
            "last_heartbeat": float,
            "consecutive_errors": int,
            "items_checked": int,
            "orders_confirmed": int,
        }
    }
}
```

**start_time placement:** `run()` calls `asyncio.run(async_main(cfg, cvv))` directly.
`start()` sets `self._running = True` before the thread starts (L139). The start_time
should be set at the same point where `_running` is set True -- inside `_run_loop._main()`
before the `await async_main(...)` call, or at the top of `run()` before `asyncio.run(...)`.

**Concrete change:** Add `self._start_time: Optional[float] = None` to `__init__`; set
`self._start_time = time.monotonic()` at the moment the bot starts (both `start()` and
`run()` paths); clear it in the `finally` block. `uptime_secs` = `time.monotonic() - self._start_time` when `_start_time is not None`.

**HealthRegistry reference on BotService:** `async_main` creates the registry. `BotService.start()` calls `async_main` indirectly via the daemon thread. The registry must be surfaced back to `BotService`. Two options:
1. Pass `BotService` self into `async_main` and let it set `self._health_registry` from inside the loop.
2. Create the registry BEFORE calling `async_main` and pass it in; BotService holds the
   pre-created instance.

Option 2 is cleaner (BotService owns the registry, passes it to async_main):
```python
# In BotService.__init__ or start():
self._health_registry = HealthRegistry()
# async_main receives it as a param: async_main(cfg, cvv, health_registry=self._health_registry)
```

For `run()` (blocking path), same approach: create registry before `asyncio.run()`.

[VERIFIED: BotService.get_status() current shape, start/run lifecycle from core/service.py]
[ASSUMED: Option 2 (BotService creates HealthRegistry) is the cleanest approach -- planner confirms]

### Pattern 7: pygame Headless Guard (SRV-01)

**Current utils.py structure** (verified from utils.py lines 1-38):
- Line 1: `import pygame` -- module-level import
- Line 8: `def initialize_pygame(): pygame.mixer.init()`
- Lines 11-23: `play_sound()` calls `pygame.mixer.init()` again each call
- Line 38: `initialize_pygame()` -- module-level call, executes on import

**Exact exception:** `pygame.mixer.init()` raises `pygame.error` when no audio device
is available. `pygame.error` is a subclass of `Exception` (stdlib RuntimeError-compatible).
[VERIFIED: pygame.error is the documented mixer init failure exception per pygame docs]
[ASSUMED: cannot simulate no-audio device in this environment to produce a live trace]

**Guard pattern:**
```python
import pygame
import os
from logger import writeLog

SOUNDS_DIR = os.path.join(os.path.dirname(__file__), 'sounds')

_AUDIO_AVAILABLE: bool = False

def _initialize_audio() -> bool:
    """Attempt pygame mixer init. Return True on success, False on failure."""
    try:
        pygame.mixer.init()
        return True
    except pygame.error as exc:
        writeLog(
            f"Audio unavailable (pygame.error: {exc.__class__.__name__}) -- sound disabled",
            "INFO",
        )
        return False

_AUDIO_AVAILABLE = _initialize_audio()
```

**play_sound() guard:**
```python
def play_sound(file_name):
    if not _AUDIO_AVAILABLE:
        return  # silent no-op
    writeLog(f"Attempting to play sound: {file_name}", "DEBUG")
    # pygame.mixer.init() call inside play_sound ALSO needs removal or guarding:
    # current code calls pygame.mixer.init() redundantly on every play.
    # With the guard in place, this second call is unreachable when _AUDIO_AVAILABLE=False.
    # When _AUDIO_AVAILABLE=True the second init() is a no-op (pygame is idempotent on
    # double-init when already initialized).
    ...
```

**SoundNotifier import:** `notifications/sound_notifier.py` imports `play_available_sound`,
`play_buy_sound`, `play_notification_sound` from `utils`. The `import pygame` at line 1 of
utils.py does NOT raise even without an audio device -- `import pygame` itself always
succeeds. Only `pygame.mixer.init()` raises. This means `sound_notifier.py` can import
`utils` safely; the guard only needs to wrap the `init()` call.

[VERIFIED: utils.py exact line numbers and structure from source read]
[ASSUMED: pygame import itself succeeds without audio device -- this is standard pygame behavior but unverified in a no-audio environment in this session]

### Pattern 8: CLI status subcommand

**Exact pattern from plugins list handler** (verified from core/cli/plugins.py and core/cli/__init__.py):

Registration in `build_parser()`:
```python
# Analog to plugins list (L152-L165 of core/cli/__init__.py):
status_p = sub.add_parser("status", help="Show per-plugin health status.")
status_p.add_argument(
    "--json",
    action="store_true",
    default=False,
    help="Emit output as JSON instead of a text table.",
)
status_p.set_defaults(func=handle_status)
```

Handler in `core/cli/status.py`:
```python
import json
import time
from core.service import BotService

def handle_status(args, svc: BotService) -> int:
    status = svc.get_status()
    if getattr(args, "json", False):
        print(json.dumps(status, indent=2))
    else:
        print(_format_status_table(status))
    return 0
```

**Table format:** One row per plugin with columns: Name, Status, Last Heartbeat,
Consecutive Errors, Items Checked, Orders Confirmed. Plus a header line showing
running=True/False and uptime.

**No network call:** `svc.get_status()` reads `self._running`, `self._start_time`,
and `self._health_registry.get_snapshot()` -- all in-memory, no I/O.

**svc availability in CLI handlers:** In `main()` (core/service.py L246), every
subcommand handler receives a fresh `BotService()` instance. For `status`, this
BotService is NOT the running instance (if the bot is running in another process).
The `status` command reads the BotService created in this process invocation --
which means `_running` will be False if called from a separate CLI invocation.
This is by design per CONTEXT.md ("no network call") -- the status command shows
the in-process state only. [VERIFIED: main() dispatch pattern from core/service.py L242-L246]

**Important implication:** `shoppybot status` called from a terminal while the bot
is running in another process will always show `running=False` and empty plugins dict,
because each process has its own BotService. This is acceptable per CONTEXT.md
("no network call" constraint means no IPC). The web `/status` endpoint (which calls
svc on the live running BotService held by the web server) is the correct path for
live status. The CLI `status` command is primarily useful from within the same process
context (e.g., when bot is run embedded) or as a quick JSON shape validator.
[ASSUMED: this limitation is acceptable per "no network call" constraint in CONTEXT.md]

### Anti-Patterns to Avoid

- **Separate consecutive_errors counter independent of failure_times deque:** P22's
  `failure_times` is a rolling-window deque that evicts old failures. A simple
  increment-only counter in HealthRegistry would diverge from the windowed count.
  Use `len(failure_times)` as the source for `consecutive_errors` in HealthRegistry
  updates.

- **Acquiring an asyncio.Lock in HealthRegistry for web reads:** The web handler is on
  a different thread than the bot event loop. Calling `asyncio.Lock.acquire()` from a
  non-async context (web request) will deadlock. Use the GIL-atomicity of primitive
  Python types + snapshot copy instead.

- **Calling `pygame.mixer.init()` on every `play_sound()` call in the guarded path:**
  The current utils.py calls `pygame.mixer.init()` inside `play_sound()` as well as at
  module level. The guard must also cover or remove this redundant call, or the first
  `play_sound()` call will re-raise `pygame.error` even when `_AUDIO_AVAILABLE=False`
  would have short-circuited it... but the guard does short-circuit it because the
  `if not _AUDIO_AVAILABLE: return` check comes first.

- **health_degraded firing on every poll cycle once threshold crossed:** Must arm on
  first crossing and only re-fire after explicit disarm (when consecutive_errors drops
  back below threshold). Mirror the `price_alert_armed` DB pattern but in-memory.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Notification fan-out for health_degraded | New dispatcher | Existing `NotificationDispatcher.notify()` | Already handles per-channel isolation + error logging |
| Thread-safe async state machine | asyncio.Lock + state machine | Plain dict + GIL atomicity | Over-engineering; primitive types are GIL-atomic in CPython |
| CLI table formatter | Custom formatter | Mirror `_format_plugins_table()` pattern | Consistent column alignment pattern already in codebase |

---

## Common Pitfalls

### Pitfall 1: health_degraded and plugin_parked fire on the same crash

**What goes wrong:** Both thresholds use `alert_on_errors` as `n_budget`. When
`len(failure_times) >= n_budget`, supervise parks the plugin. The health_degraded
check (consecutive_errors > alert_on_errors) would also be true at the same moment,
so both notifications fire on the same crash.

**Why it happens:** `consecutive_errors` is `len(failure_times)` at update time;
`n_budget` is `alert_on_errors`. They're the same value.

**How to avoid:** Fire `health_degraded` at `len(failure_times) == n_budget - 1`
(one crash before park) OR fire it unconditionally when threshold is first crossed
and then let park suppress further activity. The simplest approach: fire `health_degraded`
at `>= 1` failure (any degradation above zero), arm, and let park be the escalation.
Planner must make this threshold explicit.

**Warning signs:** Test shows both `health_degraded` and `plugin_parked` in the same
`dispatcher.notify` call list for the same plugin run.

### Pitfall 2: HealthRegistry thread-safety for web reads

**What goes wrong:** `get_status()` is called from the FastAPI handler on uvicorn's
thread. The bot event loop writes to `_health_registry` from its own thread. A dict
read while a dict is being mutated in another thread can see partial state in CPython.

**Why it happens:** `get_snapshot()` iterates over `self._plugins` while supervise
or run_plugin may be updating `self._plugins[name]` sub-dicts simultaneously.

**How to avoid:** The snapshot copy must be a full deep copy at the dict-of-dicts
level, not a shallow copy that could have inner dicts mutated mid-iteration. Use
`{name: dict(rec) for name, rec in self._plugins.items()}` (copy each inner dict).
Strip private keys in the same pass. The outer dict iteration and inner dict copy
are both protected by the GIL in CPython.

**Warning signs:** Intermittent KeyError or partial dict output in `/status` response
under concurrent load.

### Pitfall 3: pygame.mixer.init() called twice (redundant call in play_sound)

**What goes wrong:** Current `play_sound()` calls `pygame.mixer.init()` at line 13.
Even with the module-level guard setting `_AUDIO_AVAILABLE = False` and the early
return in `play_sound()`, if someone removes the early return guard later, the raw
`pygame.mixer.init()` call inside `play_sound()` will crash on a headless host.

**How to avoid:** Remove the redundant `pygame.mixer.init()` call inside `play_sound()`.
The module-level call in `_initialize_audio()` is sufficient; double-init when audio IS
available is a no-op but the redundant call is confusing.

### Pitfall 4: async_main signature change breaks BotService.run() and BotService.start()

**What goes wrong:** If `async_main` signature changes to accept `health_registry` as a
required positional argument, the call sites in `BotService.run()` (L203) and inside
`_run_loop._main()` (L154) must both be updated.

**How to avoid:** Use `health_registry=None` keyword argument with a default. The
`run_plugin` and `supervise` kwargs already use this pattern (`registry=None` from P22).
Apply the same convention consistently.

### Pitfall 5: get_status() called from web before bot has started (no HealthRegistry)

**What goes wrong:** If `_health_registry` is None before `start()` or `run()` is
called, `get_status()` will raise AttributeError.

**How to avoid:** Initialize `self._health_registry = HealthRegistry()` in
`BotService.__init__()`, not in `start()`/`run()`. This means the registry exists
but is empty (no plugins registered) until the bot starts -- which correctly
represents the pre-start state. `get_status()` returns `{"running": False, "uptime_secs": 0.0, "plugins": {}}` before start.

---

## Code Examples

### HealthRegistry snapshot for get_status()

```python
# In BotService.get_status() (core/service.py)
import time

def get_status(self) -> dict:
    uptime = 0.0
    if self._start_time is not None and self._running:
        uptime = time.monotonic() - self._start_time
    return {
        "running": self._running,
        "uptime_secs": uptime,
        "plugins": self._health_registry.get_snapshot(),
    }
```

### supervise() health_degraded hook (conceptual, not full rewrite)

```python
# Inside the except Exception block in supervise(), after failure_times update:
plugin_name = plugin.__class__.__name__
if health is not None:
    health.record_error(plugin_name)  # mirrors len(failure_times) increment
    consecutive = len(failure_times)  # use windowed count as source of truth
    if (consecutive >= n_budget - 1
            and not health.is_degraded_armed(plugin_name)
            and dispatcher is not None):
        await dispatcher.notify(_build_event("", "", plugin_name, "health_degraded"))
        health.arm_degraded(plugin_name)

if len(failure_times) >= n_budget:
    if health is not None:
        health.set_status(plugin_name, "parked")
    await _park_plugin(plugin, n_budget, dispatcher)
    return
```

### utils.py pygame guard

```python
import pygame
import os
from logger import writeLog

SOUNDS_DIR = os.path.join(os.path.dirname(__file__), 'sounds')

_AUDIO_AVAILABLE: bool = False


def _initialize_audio() -> bool:
    try:
        pygame.mixer.init()
        return True
    except pygame.error as exc:
        writeLog(
            f"Audio device unavailable ({exc.__class__.__name__}) -- sound notifications disabled",
            "INFO",
        )
        return False


_AUDIO_AVAILABLE = _initialize_audio()


def play_sound(file_name):
    if not _AUDIO_AVAILABLE:
        return
    writeLog(f"Attempting to play sound: {file_name}", "DEBUG")
    # Note: removed redundant pygame.mixer.init() call that was here originally
    mp3_path = os.path.join(SOUNDS_DIR, f"{file_name}.mp3")
    wav_path = os.path.join(SOUNDS_DIR, f"{file_name}.wav")
    if os.path.exists(mp3_path):
        pygame.mixer.music.load(mp3_path)
    elif os.path.exists(wav_path):
        pygame.mixer.music.load(wav_path)
    else:
        writeLog(f"Sound file {file_name}.mp3 or {file_name}.wav not found", "ERROR")
        return
    pygame.mixer.music.play()
```

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | health_degraded threshold should fire at `n_budget - 1` failures (one before park) | Pattern 2, Pitfall 1 | Both alerts fire simultaneously if threshold is same as park; spams on recovery if too low |
| A2 | Option 2 (BotService creates HealthRegistry before calling async_main) is cleaner | Pattern 6 | Minor: Option 1 also works; just a code organization choice |
| A3 | orders_confirmed increment best placed in `_try_auto_buy` after `_enqueue_buy_result` | Pattern 4 | If placed wrong, counter may not increment on legacy (non-order_id) confirmation path |
| A4 | `shoppybot status` CLI shows in-process state only (not live running bot in another process) | Pattern 8 | If user expects live status from a separate terminal, command is confusing; may need doc note |
| A5 | pygame import itself never raises without audio device; only mixer.init() raises pygame.error | Pattern 7 | If import also raises, guard must wrap the import too -- test in no-audio environment to confirm |
| A6 | _AUDIO_AVAILABLE = False disarm condition: consecutive_errors drops back below threshold on healthy run | Pattern 2 | If disarm is not triggered on healthy run, re-arm never fires after recovery; alert fires once then never again |

---

## Open Questions (RESOLVED)

> RESOLVED (per CONTEXT decision + plan-check): **Q1** — fire `health_degraded` at `max(1, alert_on_errors - 1)` consecutive errors (one crash BEFORE the park/windowed-budget threshold) so degraded is a distinct early-warning that precedes park; armed-once, re-arm on recovery. **Q2** — `HealthRegistry.consecutive_errors` mirrors `len(failure_times)` (windowed), reset on window eviction / healthy run. **Q3** — `orders_confirmed` increments on BOTH the confirmed and legacy (`"purchased"`) paths (yes).

1. **health_degraded threshold: exactly when relative to park?**
   - What we know: CONTEXT.md says "fires BEFORE park" and "distinct from plugin_parked"
   - What's unclear: whether "before" means N-1 failures (one early warning) or same N as park (fires simultaneously before park fires)
   - Recommendation: Fire at `>= 1` failure on first crossing (armed), re-arm on recovery; park remains the hard stop at `n_budget`. This gives maximum warning time.

2. **consecutive_errors counter: windowed deque or simple increment?**
   - What we know: P22 uses a rolling-window deque; HealthRegistry should expose a single integer
   - What's unclear: should HealthRegistry track the raw windowed value (mirroring len(failure_times)) or a simple ever-increasing increment?
   - Recommendation: Mirror `len(failure_times)` from the deque so the counter reflects recoverable state accurately. Reset to 0 when window eviction drops all failures.

3. **orders_confirmed increment for legacy (non-confirmed) path?**
   - What we know: `_enqueue_buy_result` has two branches: `("confirmed", ...)` and `("purchased", ...)` legacy
   - What's unclear: should `orders_confirmed` increment on the legacy `("purchased", ...)` path too?
   - Recommendation: Yes -- a purchase happened; the absence of an order_id is a detection failure, not an absence of purchase.

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies -- all work is internal Python modules and existing pinned packages).

---

## Validation Architecture

nyquist_validation is enabled (config.json `workflow.nyquist_validation` absent, treated as true).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with asyncio_mode=auto (confirmed from existing tests) |
| Config file | `pytest.ini` or `pyproject.toml` (existing, not changed) |
| Quick run command | `pytest tests/test_health.py tests/test_cli_status.py tests/test_utils.py -x` |
| Full suite command | `pytest` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| REL-07 | HealthRegistry records per-plugin status/heartbeat/errors/items/orders | unit | `pytest tests/test_health.py -x` | No -- Wave 0 |
| REL-07 | get_status() returns correct shape before bot starts (no registry entries) | unit | `pytest tests/test_service.py::test_get_status_shape_before_start -x` | No -- Wave 0 |
| REL-07 | get_status() returns correct shape with populated registry | unit | `pytest tests/test_service.py::test_get_status_shape_with_registry -x` | No -- Wave 0 |
| REL-07 | health_degraded fires ONCE when consecutive_errors crosses threshold | unit | `pytest tests/test_supervisor.py::test_health_degraded_fires_once -x` | No -- Wave 0 |
| REL-07 | health_degraded does NOT re-fire before recovery (armed dedup) | unit | `pytest tests/test_supervisor.py::test_health_degraded_dedup -x` | No -- Wave 0 |
| REL-07 | health_degraded re-arms after recovery (errors drop below threshold) | unit | `pytest tests/test_supervisor.py::test_health_degraded_rearms -x` | No -- Wave 0 |
| REL-07 | shoppybot status CLI prints table without crashing | unit | `pytest tests/test_cli_status.py::test_status_table -x` | No -- Wave 0 |
| REL-07 | shoppybot status --json emits valid JSON matching get_status() shape | unit | `pytest tests/test_cli_status.py::test_status_json -x` | No -- Wave 0 |
| REL-07 | /status endpoint returns JSON-serializable dict with richer shape | unit | `pytest tests/test_web_controls.py::test_status_endpoint_shape -x` | No -- Wave 0 |
| SRV-01 | utils.py import succeeds even when pygame.mixer.init raises pygame.error | unit | `pytest tests/test_utils.py::test_audio_unavailable_import_succeeds -x` | No -- Wave 0 |
| SRV-01 | play_sound() is a no-op when _AUDIO_AVAILABLE=False (no exception raised) | unit | `pytest tests/test_utils.py::test_play_sound_noop_when_audio_unavailable -x` | No -- Wave 0 |
| SRV-01 | SoundNotifier.send() does not raise when audio unavailable | unit | `pytest tests/test_notifications.py::test_sound_notifier_no_audio -x` | No -- Wave 0 (add to existing file) |

### Sampling Rate

- Per task commit: `pytest tests/test_health.py tests/test_cli_status.py tests/test_utils.py -x`
- Per wave merge: `pytest`
- Phase gate: Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_health.py` -- HealthRegistry unit tests (REL-07)
- [ ] `tests/test_cli_status.py` -- CLI status subcommand handler tests (REL-07)
- [ ] `tests/test_utils.py` -- pygame guard tests (SRV-01) -- file exists as placeholder, needs real test body
- [ ] `core/health.py` -- HealthRegistry implementation (create before tests)

---

## Security Domain

> This phase has no authentication, session management, access control, cryptography,
> or external input validation concerns. The health surface is read-only, internal,
> and contains no secrets. The pygame guard is a local audio subsystem operation.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | -- |
| V3 Session Management | no | -- |
| V4 Access Control | no | -- |
| V5 Input Validation | no | get_status() reads internal state only; no external input |
| V6 Cryptography | no | -- |

**No new security controls required for this phase.**

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Module-level `initialize_pygame()` with no guard | `_initialize_audio()` wrapped in try/except returning bool | This phase (SRV-01) | Bot imports on headless servers without crash |
| `get_status()` returns `{"running": bool}` only | Returns full health surface dict | This phase (REL-07) | CLI + web can query per-plugin liveness |

**No deprecated patterns to remove beyond the redundant `pygame.mixer.init()` call inside `play_sound()`.**

---

## Sources

### Primary (HIGH confidence -- verified from project source)

- `core/orchestrator.py` lines 90-153 (supervise), 278-310 (run_plugin), 351-366 (_enqueue_buy_result), 629-679 (async_main)
- `core/service.py` lines 36-70 (BotService.__init__, get_status, start, run)
- `core/cli/__init__.py` lines 18-184 (build_parser, subparser registration pattern)
- `core/cli/plugins.py` lines 1-54 (handle_plugins_list pattern)
- `utils.py` lines 1-38 (pygame import, initialize_pygame, play_sound, module-level call)
- `notifications/base.py` lines 20-63 (NotificationEvent dataclass, Notifier ABC)
- `notifications/dispatcher.py` (NotificationDispatcher.notify fan-out)
- `notifications/sound_notifier.py` (action dispatch pattern)
- `web/routes/api.py` lines 24-28 (/status endpoint shape)
- `core/config_schema.py` lines 271-279 (CheckoutConfig.alert_on_errors field)

### Secondary (MEDIUM confidence -- documentation/stdlib knowledge)

- pygame.error exception type: standard pygame mixer documentation
- CPython GIL atomicity for primitive dict operations: Python threading documentation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all modules verified from source
- Architecture: HIGH -- exact hook points verified from source; threshold strategy is ASSUMED
- Pitfalls: HIGH -- derived directly from verified source code structure

**Research date:** 2026-06-12
**Valid until:** 2026-07-12 (stable codebase; no external dependencies)
