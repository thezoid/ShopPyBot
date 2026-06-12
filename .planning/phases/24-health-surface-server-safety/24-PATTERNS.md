# Phase 24: Health Surface + Server Safety - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 8 (5 new, 3 modified)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `core/health.py` | service / data store | event-driven | `core/orchestrator.py` failure-deque state (L111-L125) + `core/stealth.ProxyPool` | role-match |
| `core/service.py` | service | request-response | `core/service.py` itself (expand get_status L68-70, add start_time to start L132-174) | self-edit |
| `core/orchestrator.py` | orchestrator | event-driven | `core/orchestrator.py` supervise (L90-153), run_plugin (L278-310), _enqueue_buy_result (L351-366), async_main (L629-679) | self-edit |
| `core/cli/status.py` | CLI handler | request-response | `core/cli/plugins.py` handle_plugins_list (L1-54) + _format_plugins_table (L11-44) | exact |
| `core/cli/__init__.py` | config | request-response | `core/cli/__init__.py` plugins subparser block (L151-165) | self-edit |
| `utils.py` | utility | event-driven | `utils.py` itself initialize_pygame (L8-9) + module-level call (L38) | self-edit |
| `tests/test_health.py` | test | — | `tests/test_supervisor.py` (async mock pattern L1-91) | role-match |
| `tests/test_cli_status.py` | test | — | `tests/test_cli_plugins.py` (main dispatch + capsys pattern L1-114) | exact |

## Pattern Assignments

### `core/health.py` (service, event-driven)

**Analog:** `core/orchestrator.py` failure-deque local state (lines 111-112); structure mirrors a dict-of-dicts class wrapping primitives.

**Imports pattern:**
```python
import time
```

**Core pattern** (modeled on orchestrator's per-plugin local state, lifted into a class):
```python
class HealthRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, dict] = {}

    def _ensure(self, name: str) -> None:
        if name not in self._plugins:
            self._plugins[name] = {
                "status": "idle",
                "last_heartbeat": 0.0,
                "consecutive_errors": 0,
                "items_checked": 0,
                "orders_confirmed": 0,
                "_degraded_armed": False,
            }
```

**Mutator naming convention:** mirror camelCase-free verb names already in the codebase (`record_error`, `set_status`, `inc_items_checked`, `arm_degraded`, `disarm_degraded`, `is_degraded_armed`).

**Snapshot pattern** (strip private keys, copy inner dicts for thread safety -- GIL atomicity on primitives):
```python
def get_snapshot(self) -> dict[str, dict]:
    return {
        name: {k: v for k, v in rec.items() if not k.startswith("_")}
        for name, rec in self._plugins.items()
    }
```

**Error handling:** No try/except inside the registry itself; callers (orchestrator) own exception handling.

---

### `core/service.py` (expand get_status + add _start_time + hold HealthRegistry ref)

**Analog:** `core/service.py` lines 36-70 (self-edit); follow the `_running` init pattern for `_start_time` and `_health_registry`.

**`__init__` additions pattern** (after `self._task` on line 41, mirroring existing Optional fields):
```python
# core/service.py __init__ additions (after existing _task field):
self._start_time: float | None = None
# HealthRegistry created here so get_status() is always safe before start():
from core.health import HealthRegistry
self._health_registry: HealthRegistry = HealthRegistry()
```

**`start()` addition** (set start_time at same point _running is set True, line 141):
```python
self._running = True
self._start_time = time.monotonic()  # ADD HERE (after existing line 141)
```

**`run()` addition** (blocking path, before asyncio.run, line 203):
```python
import time
self._start_time = time.monotonic()
asyncio.run(async_main(self._cfg, cvv, health_registry=self._health_registry))
self._start_time = None
```

**`get_status()` expansion** (replace lines 68-70):
```python
def get_status(self) -> dict:
    """Return structured health surface. Safe to call before start()."""
    import time
    uptime = 0.0
    if self._start_time is not None and self._running:
        uptime = time.monotonic() - self._start_time
    return {
        "running": self._running,
        "uptime_secs": uptime,
        "plugins": self._health_registry.get_snapshot(),
    }
```

**`finally` block** inside `_run_loop._main()` (line 163, mirror `self._running = False`):
```python
finally:
    self._running = False
    self._start_time = None   # ADD alongside existing _running = False
    self._task = None
```

**async_main call** inside `_run_loop._main()` (line 154 -- pass registry as kwarg):
```python
await async_main(self._cfg, cvv, health_registry=self._health_registry)
```

---

### `core/orchestrator.py` (hook supervise + run_plugin + async_main + _enqueue_buy_result)

**Analog:** `core/orchestrator.py` itself (self-edit). All hook points verified.

**`async_main` signature change** (line 629 -- keyword-only, default None avoids breaking callers):
```python
async def async_main(cfg, cvv, health_registry=None) -> None:
```

**`async_main` supervise call** (line 668 -- add health kwarg):
```python
tg.create_task(
    supervise(plugin, write_queue, poll_interval,
              dispatcher=dispatcher, cfg=cfg,
              registry=registry, health=health_registry),
    name=f"poll-{plugin.__class__.__name__}",
)
```

**`supervise` signature** (line 90 -- add `health=None` after `registry=None`):
```python
async def supervise(plugin, write_queue, poll_interval, dispatcher, cfg,
                    registry=None, health=None) -> None:
```

**`supervise` healthy-run hook** (after `attempt = 0`, line 117):
```python
attempt = 0
if health is not None:
    plugin_name = plugin.__class__.__name__
    health.set_status(plugin_name, "running")
    health.reset_errors(plugin_name)
    health.disarm_degraded(plugin_name)
```

**`supervise` exception hook** (inside `except Exception`, after `failure_times.append`, lines 122-130):
```python
# After existing failure_times eviction block:
plugin_name = plugin.__class__.__name__
if health is not None:
    health.record_error(plugin_name)
    n_errors = len(failure_times)
    if (n_errors >= 1
            and not health.is_degraded_armed(plugin_name)
            and dispatcher is not None):
        await dispatcher.notify(
            _build_event("", "", plugin_name, "health_degraded")
        )
        health.arm_degraded(plugin_name)
```

**`supervise` park hook** (before `return` at line 133):
```python
if len(failure_times) >= n_budget:
    if health is not None:
        health.set_status(plugin.__class__.__name__, "parked")
    await _park_plugin(plugin, n_budget, dispatcher)
    return
```

**`supervise` relaunch hook** (inside `if _is_browser_dead_exc(exc):`, line 135):
```python
if _is_browser_dead_exc(exc):
    if health is not None:
        health.set_status(plugin.__class__.__name__, "relaunching")
    if registry is not None:
        registry.assign_proxy(plugin)
    ...
```

**`run_plugin` signature** (line 278 -- add `health=None`):
```python
async def run_plugin(plugin, write_queue, poll_interval,
                     dispatcher=None, cfg=None, health=None) -> None:
```

**`run_plugin` heartbeat hook** (after items fetch, before for-loop, line 292):
```python
if health is not None:
    plugin_name = plugin.__class__.__name__
    health.heartbeat(plugin_name)
    health.set_status(plugin_name, "running")
for name, link, auto_buy, quantity, purchased in items:
```

**`run_plugin` items_checked hook** (inside inner for-loop, after domain filter passes, line 295):
```python
if not any(p in (link or "") for p in plugin.domain_patterns):
    continue
if health is not None:
    health.inc_items_checked(plugin.__class__.__name__)
```

**`supervise` call to `run_plugin`** (line 116 -- thread health kwarg through):
```python
await run_plugin(plugin, write_queue, poll_interval,
                 dispatcher=dispatcher, cfg=cfg, health=health)
```

**orders_confirmed hook** -- placed in `_try_auto_buy` after `_enqueue_buy_result` returns (avoids touching `_enqueue_buy_result` signature). Pass `health` down through `_check_and_buy` -> `_try_auto_buy`. Pattern mirrors how `dispatcher` is already threaded:
```python
# In _try_auto_buy, after _enqueue_buy_result call:
await _enqueue_buy_result(name, link, platform, order_id, write_queue, dispatcher)
if health is not None:
    health.inc_orders_confirmed(platform)
```

---

### `core/cli/status.py` (CLI handler, request-response) NEW

**Analog:** `core/cli/plugins.py` lines 1-54 -- exact structural copy.

**Imports pattern** (copy from plugins.py lines 1-8):
```python
"""handle_status: CLI status subcommand handler."""

import json
import time

from core.service import BotService
```

**Table formatter pattern** (mirror `_format_plugins_table` from `core/cli/plugins.py` lines 11-44):
```python
def _format_status_table(status: dict) -> str:
    running = status.get("running", False)
    uptime = status.get("uptime_secs", 0.0)
    plugins = status.get("plugins", {})
    header = f"running={running}  uptime={uptime:.1f}s"
    if not plugins:
        return f"{header}\nNo plugin data yet."
    col_headers = ("Name", "Status", "Last Heartbeat", "Errors", "Checked", "Orders")
    # Same left-justified aligned table as _format_plugins_table:
    data = [
        (
            name,
            rec.get("status", "idle"),
            f"{rec.get('last_heartbeat', 0.0):.1f}",
            str(rec.get("consecutive_errors", 0)),
            str(rec.get("items_checked", 0)),
            str(rec.get("orders_confirmed", 0)),
        )
        for name, rec in plugins.items()
    ]
    widths = [max(len(h), max(len(row[i]) for row in data)) for i, h in enumerate(col_headers)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [header, fmt.format(*col_headers), "  ".join("-" * w for w in widths)]
    for row in data:
        lines.append(fmt.format(*row))
    return "\n".join(lines)
```

**Handler pattern** (mirror `handle_plugins_list` from `core/cli/plugins.py` lines 47-54):
```python
def handle_status(args, svc: BotService) -> int:
    """Print per-plugin health status as table or JSON."""
    status = svc.get_status()
    if getattr(args, "json", False):
        print(json.dumps(status, indent=2))
    else:
        print(_format_status_table(status))
    return 0
```

**Error handling:** No try/except -- follows the plugins.py precedent; all reads are in-memory and cannot raise.

---

### `core/cli/__init__.py` (add `status` subparser)

**Analog:** `core/cli/__init__.py` plugins subparser block, lines 151-165 -- copy the exact flat-subcommand (not nested) pattern; `status` has no sub-subcommands.

**Import addition** (after line 16 `from core.cli.plugins import handle_plugins_list`):
```python
from core.cli.status import handle_status
```

**Subparser registration** (add before the `# --- web ---` block, line 168, mirroring plugins_list_p block lines 155-162):
```python
# --- status ---
status_p = sub.add_parser("status", help="Show per-plugin health status.")
status_p.add_argument(
    "--json",
    action="store_true",
    default=False,
    help="Emit output as JSON instead of a text table.",
)
status_p.set_defaults(func=handle_status)
```

Note: no `_require_subcommand` needed -- `status` is a leaf command, not a group.

---

### `utils.py` (pygame headless guard) SRV-01

**Analog:** `utils.py` itself, lines 1-38.

**Current state to replace:**
- Line 8-9: `def initialize_pygame(): pygame.mixer.init()` -- replace with guarded version
- Line 13: `pygame.mixer.init()` inside `play_sound()` -- remove (redundant; guard short-circuits)
- Line 38: `initialize_pygame()` -- replace with `_AUDIO_AVAILABLE = _initialize_audio()`

**Module-level guard pattern** (replaces lines 1-38 partially):
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
            f"Audio device unavailable ({exc.__class__.__name__}) -- sound notifications disabled",
            "INFO",
        )
        return False


_AUDIO_AVAILABLE = _initialize_audio()
```

**play_sound guard pattern** (add early return at line 12; remove redundant `pygame.mixer.init()` at line 13):
```python
def play_sound(file_name):
    if not _AUDIO_AVAILABLE:
        return                             # silent no-op on headless host
    writeLog(f"Attempting to play sound: {file_name}", "DEBUG")
    # REMOVED: pygame.mixer.init()        # was line 13, now redundant
    mp3_path = os.path.join(SOUNDS_DIR, f"{file_name}.mp3")
    ...
```

The three public wrappers (`play_notification_sound`, `play_buy_sound`, `play_available_sound`) are unchanged -- they call `play_sound()` which carries the guard.

---

## Shared Patterns

### Notification Dispatch (health_degraded event)

**Source:** `core/orchestrator.py` `_build_event` (lines 155-164) + `_evaluate_price_triggers` dedup logic (lines 238-252)

**Apply to:** `supervise()` health_degraded hook in `core/orchestrator.py`

```python
# _build_event is the existing factory -- reuse with action="health_degraded":
_build_event("", "", plugin.__class__.__name__, "health_degraded")
# item_name="" and item_url="" mirror _park_plugin usage at line 87
```

Dedup pattern (in-memory armed/disarmed on HealthRegistry -- mirrors DB armed/disarmed for price alerts):
```python
# Check: trigger condition
if n_errors >= 1 and not health.is_degraded_armed(name) and dispatcher is not None:
    await dispatcher.notify(...)      # fire ONCE
    health.arm_degraded(name)         # arm

# Recovery path (healthy run in supervise):
health.disarm_degraded(name)          # disarm on recovery
```

### kwargs=None default for optional args

**Source:** `core/orchestrator.py` supervise line 90 (`registry=None`) and run_plugin line 278 (`dispatcher=None`, `cfg=None`)

**Apply to:** All new `health=None` parameters on `supervise`, `run_plugin`, `async_main`, `_check_and_buy`, `_try_auto_buy`

Pattern: always use keyword-only default=None; callers pass by name; never break existing call sites.

### CLI handler: no network, --json flag, return int

**Source:** `core/cli/plugins.py` lines 47-54

**Apply to:** `core/cli/status.py` handle_status

Pattern: read from `svc` only, `getattr(args, "json", False)` for flag, `return 0` always.

---

## Test Pattern Assignments

### `tests/test_health.py` (NEW)

**Analog:** `tests/test_supervisor.py` lines 1-91 (helper factories, MagicMock pattern, async tests)

Key patterns to copy:
- `_make_cfg()` factory returning MagicMock with nested attrs -- use same approach for HealthRegistry (no mocking needed; test the real class)
- `async def test_*()` with `pytest.mark.asyncio` implicit via asyncio_mode=auto
- Assert on dict values returned by `get_snapshot()`

Structure:
```python
from core.health import HealthRegistry

def test_registry_idle_before_use():
    reg = HealthRegistry()
    assert reg.get_snapshot() == {}

def test_heartbeat_sets_last_heartbeat():
    reg = HealthRegistry()
    reg.heartbeat("PluginA")
    snap = reg.get_snapshot()
    assert snap["PluginA"]["last_heartbeat"] > 0.0

def test_record_error_increments():
    ...

def test_arm_disarm_degraded():
    ...

def test_snapshot_strips_private_keys():
    reg = HealthRegistry()
    reg._ensure("PluginA")
    snap = reg.get_snapshot()
    assert "_degraded_armed" not in snap["PluginA"]
```

### `tests/test_cli_status.py` (NEW)

**Analog:** `tests/test_cli_plugins.py` lines 1-114 -- exact structural copy.

Key patterns:
```python
from core.service import main
from unittest.mock import MagicMock, patch

_STATUS_PAYLOAD = {
    "running": True,
    "uptime_secs": 42.0,
    "plugins": {
        "AmazonPlugin": {
            "status": "running",
            "last_heartbeat": 100.0,
            "consecutive_errors": 0,
            "items_checked": 5,
            "orders_confirmed": 1,
        }
    }
}

def test_status_table(capsys, tmp_data_dir):
    mock_svc = MagicMock()
    mock_svc.get_status.return_value = _STATUS_PAYLOAD
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["status"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "AmazonPlugin" in out

def test_status_json(capsys, tmp_data_dir):
    ...
    assert json.loads(out)["running"] is True
```

### `tests/test_utils.py` (EDIT -- add real test body)

**Analog:** `tests/test_supervisor.py` mock patching style; `tests/test_service.py` fixture approach.

Key patterns:
```python
import pytest
from unittest.mock import patch, MagicMock

def test_audio_unavailable_import_succeeds(monkeypatch):
    """utils imports cleanly even when pygame.mixer.init raises pygame.error."""
    import importlib
    import utils
    # Patch _initialize_audio to simulate failure:
    with patch("utils._initialize_audio", return_value=False):
        # _AUDIO_AVAILABLE is already set; test the guard directly:
        with patch.object(utils, "_AUDIO_AVAILABLE", False):
            utils.play_sound("notification")  # must not raise

def test_play_sound_noop_when_audio_unavailable(monkeypatch):
    import utils
    monkeypatch.setattr(utils, "_AUDIO_AVAILABLE", False)
    utils.play_sound("notification")  # no exception, no pygame call
```

### `tests/test_service.py` (EDIT -- add get_status shape tests)

**Analog:** `tests/test_service.py` existing `test_get_status_before_start_reports_not_running` (line 65-70).

Pattern:
```python
def test_get_status_shape_before_start(service):
    status = service.get_status()
    assert "running" in status
    assert "uptime_secs" in status
    assert "plugins" in status
    assert isinstance(status["plugins"], dict)
    assert status["uptime_secs"] == 0.0

def test_get_status_shape_with_registry(service):
    service._health_registry.heartbeat("FakePlugin")
    status = service.get_status()
    assert "FakePlugin" in status["plugins"]
```

### `tests/test_web_controls.py` (EDIT -- add richer /status shape test)

**Analog:** `tests/test_web_controls.py` `test_get_status_returns_running_bool` (lines 45-51).

Pattern:
```python
def test_status_endpoint_richer_shape(mock_svc, client):
    mock_svc.get_status.return_value = {
        "running": True,
        "uptime_secs": 10.5,
        "plugins": {"AmazonPlugin": {"status": "running", ...}}
    }
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "uptime_secs" in data
    assert "plugins" in data
```

### `tests/test_supervisor.py` (EDIT -- add health_degraded tests)

**Analog:** `tests/test_supervisor.py` `test_failure_budget_parks_plugin` (lines 196-214) -- same dispatcher mock + actions assertion pattern.

Pattern:
```python
async def test_health_degraded_fires_once():
    from core.orchestrator import supervise
    from core.health import HealthRegistry

    cfg = _make_cfg(alert_on_errors=3)
    dispatcher = _make_dispatcher()
    health = HealthRegistry()
    plugin = _make_plugin("PluginDegraded")
    registry = _make_registry_with_plugins(plugin)

    # Crash once, block after:
    ...

    actions = [c.args[0].action for c in dispatcher.notify.call_args_list]
    assert actions.count("health_degraded") == 1

async def test_health_degraded_dedup():
    # Crash twice -- health_degraded fires ONCE (armed after first)
    ...
    assert actions.count("health_degraded") == 1

async def test_health_degraded_rearms():
    # Crash, recover, crash again -- health_degraded fires twice total
    ...
    assert actions.count("health_degraded") == 2
```

---

## No Analog Found

All files have analogs. No entries in this section.

---

## Metadata

**Analog search scope:** `core/`, `core/cli/`, `tests/`, `utils.py`, `notifications/`
**Files scanned:** 12 source files read, 75+ test files globbed
**Pattern extraction date:** 2026-06-12
