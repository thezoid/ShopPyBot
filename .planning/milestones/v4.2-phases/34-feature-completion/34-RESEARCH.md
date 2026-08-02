# Phase 34: Feature Completion - Research

**Researched:** 2026-07-02
**Domain:** Structured logging (contextvars tag injection), read-only web API + analytics, existing v4.1 dashboard design system
**Confidence:** HIGH (all findings verified against the real code in this session)

## Summary

Two load-bearing questions were resolved directly against the source. **FC-01:** `logger.py:writeLog` writes lines as `[{TYPE}][{timestamp}] {message}` and **auto-injects NO plugin tag** — any plugin identity present today is a hand-written prefix in the *message* (e.g. `[BestBuyPlugin]`), and it is **inconsistent** (dozens of call sites emit no plugin prefix at all: `writeLog("Item is available on BestBuy", "SUCCESS")`) and uses the **class name**, not the `platform_key`. This confirms the v4.1 OBS-08 deferral flag: a plugin filter built on today's lines would be unreliable. The clean guarantee is a module-level `contextvars.ContextVar` set once per plugin task in the orchestrator, read by `writeLog`, defaulting to a `core` sentinel. **FC-02:** confirmed-order records live in the single `items` table (`order_id`, `confirmed_at`, `place_order_attempted_at`, `checkout_attempts`, `purchased`). There is **no plugin/platform column** — plugin identity must be derived from the item `link` hostname via the registry's `domain_patterns`. Both durable buy-flow timestamps needed for time-to-checkout (`place_order_attempted_at` and `confirmed_at`) exist and are written as aware UTC ISO-8601.

**Primary recommendation:** FC-01 — inject `[plugin]` via a `ContextVar` set in `supervise()`/`run_plugin()`, format `[{TYPE}][{plugin}][{ts}] {message}` (level stays first bracket so every existing filter and the JS level-color regex keep working); add an optional `plugin` param to `read_logs_filtered()` and `/api/logs`. FC-02 — add one read-only `get_order_analytics_rows_sync()` accessor + a **pure** `compute_analytics(rows, platform_of)` function + `GET /api/analytics`; render **stat cards (`.health-card`/`.health-grid`) + a per-plugin `<table>`** reusing existing components, **no chart**.

## User Constraints (from CONTEXT.md)

### Locked Decisions
**FC-01 [plugin] log tag + /api/logs filter**
- Verify current tagging state (done: absent/inconsistent — see FC-01 below). Guarantee consistency by injecting a `[plugin]` tag from the currently-active plugin context (a `contextvars.ContextVar` set by the orchestrator per plugin iteration) rather than auditing every call site. Lines with no active plugin (startup/global) get a sentinel tag (`[core]`).
- **Tag format:** `[plugin]` where plugin = the plugin's `platform_key` (amazon, bestbuy, walmart, ... squareenix no-underscore). Must be machine-parseable so the filter can match exactly.
- **/api/logs filter:** add an optional `plugin` query parameter to the existing `/api/logs` endpoint (already supports level + search). Reuse the existing `read_logs_filtered()` path. Empty/absent param = all plugins (no behavior change).
- **Log-filter UI:** a plugin dropdown in the existing dashboard log panel, populated from the known plugin list, wired to the `plugin` query param. Reuse the existing log-level/search control styling (components.css).

**FC-02 outcome analytics**
- **Metrics:** (1) success-rate and (2) time-to-checkout, computed from existing confirmed-order (BUY-04) records. BOTH overall and per-plugin breakdowns. Confirm exact schema; define success-rate from available fields; define time-to-checkout as a duration between two existing timestamps. Do NOT invent new columns — if a needed timestamp is missing, scope to what the data supports.
- **Endpoint:** a read-only analytics endpoint (e.g. `GET /api/analytics`) returning computed metrics as JSON. Follow the read-only API pattern (phase 26) — no writes, no credential exposure.
- **View:** operator-facing surface on the existing dashboard. Stat cards for headline numbers + a compact per-plugin table. Only add a uPlot chart if the data is genuinely time-series; default to cards+table. Reuse existing card/table components + tokens.css.
- **Fixture verification:** build a deterministic fixture (known orders with known timestamps) and assert the computed success-rate + time-to-checkout exactly.

**Design-system reuse (hard):** all new UI reuses `web/static/tokens.css`, `components.css`, `dashboard.css` verbatim. Zero-Node holds — no package.json, no CDN, all assets vendored. FOUC-prevention + theme conventions preserved. No new external fonts/URLs.

### Claude's Discretion
- Choice of tag-injection mechanism (contextvars vs threading platform_key vs logging filter) — recommendation below.
- Exact success-rate / time-to-checkout field selection where multiple valid definitions exist — recommendation below with the alternatives documented.
- Whether a chart adds value (default cards+table).

### Deferred Ideas (OUT OF SCOPE)
- Retroactive tagging of historical log FILES (only newly-written lines are guaranteed).
- Advanced analytics (trends over time, funnels) beyond success-rate + time-to-checkout.
- New charting beyond the vendored uPlot.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FC-01 | Log lines carry a `[plugin]` tag and `/api/logs` supports filtering by plugin (completes v4.1-deferred OBS-08) | ContextVar mechanism in `logger.py`, set in `core/orchestrator.py`; `plugin` param in `web/log_reader.py:read_logs_filtered` + `web/routes/api.py:/logs`; dropdown in `web/templates/dashboard.html` |
| FC-02 | Operator views outcome analytics (success-rate, time-to-checkout) computed from existing confirmed-order (BUY-04) records | `items` table columns (`order_id`, `confirmed_at`, `place_order_attempted_at`); new `get_order_analytics_rows_sync()`; pure `compute_analytics()`; `GET /api/analytics`; cards+table in dashboard |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `[plugin]` tag injection | Logging module (`logger.py`) | Orchestrator (sets context) | The single write point (`writeLog`) is the only place that can guarantee every line; the orchestrator is the only place that knows which plugin is active |
| Plugin context propagation | Orchestrator (async tasks) | — | Each `supervise` task owns an isolated `ContextVar` copy; the bot event loop is where plugin `writeLog` calls originate |
| Log filtering (level/search/plugin) | Web read layer (`web/log_reader.py`) | API route | Pure string filtering over the day's file; no bot state needed |
| Analytics computation | Pure function (`core/analytics.py`) | Models accessor (rows), registry (link→platform) | Purity makes the fixture assertion exact and DB-free |
| Analytics data read | Models (`models.py`) | BotService accessor | Single SQL read of `items`; MOD-02 routes web through BotService |
| Analytics + log UI | Dashboard template + inline JS | Static CSS (reuse) | Render tier; reuses existing card/table/control components |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `contextvars` | stdlib (Py 3.11+) | Per-task plugin context for the log tag | Native asyncio support: `asyncio.create_task` copies the context at creation, giving per-plugin isolation with zero locking [CITED: docs.python.org/3/library/contextvars.html] |
| `fastapi` | 0.115.8 | `/api/analytics` + `/api/logs` routes | Already the web dependency (pyproject `[project.optional-dependencies].web`) |
| `sqlite3` | stdlib | Analytics read from `items` | Already the datastore (`models.py`) |
| `pytest` | (installed) | Fixture-verified analytics + tag tests | `[tool.pytest.ini_options]` in pyproject, `asyncio_mode=auto` |

**No new external packages.** `contextvars` is stdlib; everything else is already vendored/declared. Package Legitimacy Audit is therefore N/A for this phase.

### Alternatives Considered (tag mechanism)
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ContextVar` set by orchestrator | Thread `platform_key` through every `writeLog(...)` call | Requires editing ~150 call sites (the exact call-site sweep CONTEXT wants to avoid); easy to miss new lines → guarantee not preserved |
| `ContextVar` | `logging.Filter` on a stdlib logger | `writeLog` is a custom `print`+file-append function, NOT a `logging.Logger` (setup_logger's Logger is unused by writeLog) — a `logging.Filter` would not intercept these lines without a full rewrite of the logging path |

**Recommendation:** `ContextVar`. It guarantees "every newly-written line carries a `[plugin]` tag" from the single write point, with no call-site sweep, and its default value provides the `core` sentinel for free.

## Architecture Patterns

### System Architecture Diagram

```
FC-01 tag flow:
  orchestrator.supervise(plugin)                     web tier (uvicorn loop / startup thread)
     |  set _current_plugin = plugin.platform_key       |  (no ContextVar set)
     v  [per-task ContextVar copy — isolated]           v
  run_plugin -> _check_and_buy -> writeLog(msg,type)  writeLog(msg,type)  main.py / service init
                       |                                        |                  |
                       v  reads _current_plugin.get()           v get()="core"     v get()="core"
                logger.writeLog  --------> line: [TYPE][plugin][ts] msg  --> logs/YYYYMonthDD.log
                                                                                    |
  /api/logs?level=&search=&plugin= --> read_logs_filtered(n,level,search,plugin) --+
     (filter: startswith[TYPE] AND "[plugin]" in line AND search substring) --> {"logs":[...]}

FC-02 analytics flow:
  items table (SQLite)
     | get_order_analytics_rows_sync()  SELECT name,link,order_id,confirmed_at,
     |                                         checkout_attempts,place_order_attempted_at,purchased
     v
  BotService.get_analytics()
     |  resolve link -> platform_key via registry.domain_patterns (hostname match)
     v
  compute_analytics(rows, platform_of)   [PURE: attempted / confirmed / durations]
     |
     v
  GET /api/analytics  -->  {"overall":{...},"per_plugin":[{plugin,attempted,confirmed,success_rate,avg_time_to_checkout_secs,sample_size},...]}
     |
     v
  dashboard.html:  .health-grid of .health-card (headline stats) + <table id="analytics-table"> (per-plugin)
```

### Recommended Project Structure (new/changed files)
```
logger.py                         # + ContextVar + set_log_plugin() + tag in line format
core/orchestrator.py              # set the ContextVar at top of supervise()/run_plugin()
core/analytics.py                 # NEW: pure compute_analytics(rows, platform_of)
models.py                         # + get_order_analytics_rows_sync()
core/service.py                   # + BotService.get_analytics() (registry link->platform)
web/log_reader.py                 # + plugin param on read_logs_filtered()
web/routes/api.py                 # + plugin param on /logs; + GET /analytics
web/templates/dashboard.html      # + analytics section (cards+table) + log-plugin <select>
tests/test_analytics.py           # NEW: pure fixture assertions
tests/test_logger.py              # + tag-injection tests
tests/test_log_reader.py          # + plugin-filter tests
tests/test_api_observability.py   # UPDATE arity asserts; + analytics endpoint test
```

### Pattern 1: ContextVar-injected log tag (FC-01)
**What:** A module-level `ContextVar` with a `core` default; `writeLog` reads it and injects `[plugin]` as the second bracket (after level).
**When to use:** Every `writeLog` call, automatically.
```python
# logger.py
from contextvars import ContextVar
_current_plugin: ContextVar[str] = ContextVar("current_plugin", default="core")

def set_log_plugin(platform_key: str):
    """Set the active plugin tag for all writeLog calls in the current context/task.
    Returns the token (callers may reset, but per-task isolation makes reset optional)."""
    return _current_plugin.set(platform_key or "core")

def writeLog(message: str, type: str, writeTofile: bool = True) -> None:
    loggingLevel = _LOGGING_LEVEL
    # ...log_levels unchanged...
    color, level = log_levels.get(type.upper(), (Fore.LIGHTBLACK_EX, 0))
    if loggingLevel >= level:
        plugin = _current_plugin.get()                       # "core" when no plugin active
        ts = datetime.now().strftime('%Y%B%d@%H:%M:%S')
        head = f"[{type.upper()}][{plugin}][{ts}]"           # LEVEL stays first bracket
        print(f"{color}{head} {message}{Style.RESET_ALL}")
        if writeTofile:
            # ...log_dir resolution unchanged...
            with open(log_file_path, "a", encoding="utf-8") as logFile:
                logFile.write(f"{head} {message}\n")
```
```python
# core/orchestrator.py  — set once per plugin task (isolated by tg.create_task context copy)
from logger import writeLog, set_log_plugin

async def supervise(plugin, write_queue, poll_interval, dispatcher, cfg, registry=None, health=None):
    set_log_plugin(getattr(plugin, "platform_key", None) or plugin.__class__.__name__.lower())
    # ...rest unchanged; every writeLog in this task + its awaited callees is now tagged...
```
**Why `supervise` (not `run_plugin`):** `async_main` creates one `tg.create_task(supervise(...))` per active plugin (orchestrator.py:800-804). Each task starts with a **copy** of the parent context, and `.set()` inside the task mutates only that copy — so tasks never cross-contaminate, and park/restart/backoff logs emitted in `supervise` (not just `run_plugin`) are tagged. [CITED: docs.python.org/3/library/contextvars.html — "When a Task is created the context is copied from the current context."]

### Pattern 2: plugin filter composes with level+search (FC-01)
```python
# web/log_reader.py
def read_logs_filtered(n=50, level=None, search=None, plugin=None):
    lines = _read_today_lines()
    if level is not None:
        lines = [l for l in lines if l.startswith(f"[{level.upper()}]")]   # level still first bracket
    if plugin is not None:
        tag = f"[{plugin}]"
        lines = [l for l in lines if tag in l]                             # e.g. "[amazon]"
    if search is not None:
        needle = search.lower()
        lines = [l for l in lines if needle in l.lower()]
    return lines[-n:]                                                       # filter-then-limit preserved
```
```python
# web/routes/api.py
@router.get("/logs")
async def get_logs(request: Request, level: str | None = None, search: str | None = None,
                   plugin: str | None = None, n: int = 50):
    n = min(max(n, 1), 500)
    logs = await asyncio.to_thread(read_logs_filtered, n, level, search, plugin)
    return JSONResponse({"logs": logs})
```
Absent `plugin` → `None` → no filtering → byte-identical behavior for existing callers. AND-composed with level+search.

### Pattern 3: pure analytics function (FC-02)
```python
# core/analytics.py
from datetime import datetime

_SENTINEL_PREFIX = "CONFIRMED-"   # core/confirmation.py sentinel: URL matched, no real id

def _is_confirmed(order_id):
    return bool(order_id) and not str(order_id).startswith(_SENTINEL_PREFIX)

def compute_analytics(rows, platform_of):
    """rows: iterable of dicts with keys name, link, order_id, confirmed_at,
       checkout_attempts, place_order_attempted_at, purchased.
       platform_of: Callable[[str], str] mapping link -> platform_key ('core' if unknown).
       Returns {'overall': {...}, 'per_plugin': [ {plugin, attempted, confirmed,
       success_rate, avg_time_to_checkout_secs, sample_size}, ... ]}."""
    buckets = {}   # platform_key -> {attempted, confirmed, durations[]}
    for r in rows:
        attempted = (r["place_order_attempted_at"] is not None) or (r["order_id"] is not None)
        if not attempted:
            continue
        key = platform_of(r["link"])
        b = buckets.setdefault(key, {"attempted": 0, "confirmed": 0, "durations": []})
        b["attempted"] += 1
        if _is_confirmed(r["order_id"]):
            b["confirmed"] += 1
            ca, pa = r["confirmed_at"], r["place_order_attempted_at"]
            if ca and pa:
                d = (datetime.fromisoformat(ca) - datetime.fromisoformat(pa)).total_seconds()
                if d >= 0:
                    b["durations"].append(d)
    return {"overall": _summarize(_merge(buckets.values())),
            "per_plugin": [{"plugin": k, **_summarize(v)} for k, v in sorted(buckets.items())]}

def _summarize(b):
    att, conf, dur = b["attempted"], b["confirmed"], b["durations"]
    return {
        "attempted": att, "confirmed": conf,
        "success_rate": (conf / att) if att else None,        # divide-by-zero guard
        "avg_time_to_checkout_secs": (sum(dur) / len(dur)) if dur else None,
        "sample_size": len(dur),                              # #orders with BOTH timestamps
    }
```

### Anti-Patterns to Avoid
- **Putting `[plugin]` before `[LEVEL]`.** Breaks `read_logs_filtered`'s `startswith(f"[{level.upper()}]")` and the dashboard JS regex `/^\[(\w+)\]/` (dashboard.html:495) that colors lines by level. Keep level first.
- **Counting the `CONFIRMED-<ts>` sentinel as a clean success.** It means "URL matched but no real order id" (possibly a payment-failure page) — exclude from `confirmed`.
- **Emitting `link` (URLs) in the analytics JSON.** URLs can carry tokens; output `platform_key` + aggregate numbers only.
- **Using the class name in the tag/filter.** The decision requires `platform_key` (`squareenix`, not `SquareEnixPlugin`). The ContextVar is set from `plugin.platform_key`, so this is automatic — but the UI dropdown must also use platform_key values.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-plugin log context | Manual `platform_key=` kwarg on 150 `writeLog` calls | `contextvars.ContextVar` | Native asyncio task-copy semantics guarantee isolation + coverage; a manual sweep will miss new/future call sites |
| link → plugin mapping | New regex/hostname parser | `registry.route()` / `domain_patterns` (registry.py:102-112) | The routing logic (urlparse hostname substring) already exists and is the single source of truth |
| Duration math | Manual string timestamp parsing | `datetime.fromisoformat` | Both timestamps are aware UTC ISO from `datetime.now(timezone.utc).isoformat()`; `fromisoformat` round-trips them tz-aware |
| Card / table / dropdown styling | New CSS classes | `.health-card`, `.health-grid`, bare `table`/`th`/`td`, `.log-controls`+`select` | All already defined and theme-aware; `test_design_system` forbids new hardcoded hex |

**Key insight:** every hard part of this phase already exists in the codebase — the single log write point, the hostname router, the aware-UTC timestamps, and a full card/table/control component set. The work is wiring, not building.

## Runtime State Inventory

> Rename/refactor categories — this phase is **additive** (new tag, new endpoint, new UI), not a rename. Included for completeness.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Historical `logs/*.log` lines have NO `[plugin]` tag; existing `items` rows may have `place_order_attempted_at=NULL` (pre-Phase 30) or naive/absent `confirmed_at` | None — retroactive log tagging is explicitly deferred; analytics skips rows lacking a needed timestamp (scoped, not migrated) |
| Live service config | None | None — verified: no external service holds a plugin tag |
| OS-registered state | None | None |
| Secrets/env vars | None touched | None — analytics output is aggregate-only; no credential surface added |
| Build artifacts | None | None — no new package/entry-point |

## Common Pitfalls

### Pitfall 1: Log-format change breaks two existing API tests
**What goes wrong:** `tests/test_api_observability.py::test_logs_filtered_level_and_search` asserts `read_logs_filtered` was called as `(50, "ERROR", "captcha")` and `test_logs_no_params_default_behavior` asserts `(50, None, None)`. Adding the `plugin` param makes the route call `(50, level, search, plugin)`.
**Why it happens:** The tests pin the exact positional arity of the mocked function.
**How to avoid:** The plan MUST update both asserts to `assert_called_once_with(50, "ERROR", "captcha", None)` and `(50, None, None, None)` respectively, in the same commit as the route change (TDD: update test first).
**Warning signs:** `AssertionError: expected call not found` on those two tests.

### Pitfall 2: ContextVar does not cross the executor / thread boundary
**What goes wrong:** `loop.run_in_executor(None, fn)` runs `fn` in a worker thread with an **empty** context — a `writeLog` inside such a callback would read the `core` default, not the plugin. The bot also runs in a **daemon thread** with its own event loop (`core/service.py:_run_loop`), separate from the uvicorn loop.
**Why it happens:** `run_in_executor` (unlike `asyncio.to_thread`) does not `copy_context`. [VERIFIED: bugs.python.org/issue34014; GitHub cpython#136157 — `to_thread` copies context, `run_in_executor` does not]
**How to avoid:** Set the ContextVar **inside the plugin coroutine** (`supervise`/`run_plugin`), where every plugin-attributable `writeLog` actually runs. The sync functions dispatched via `run_in_executor` are the `models.py` DB accessors, which contain **no `writeLog` calls** (verified) — so the executor gap is not exercised. Web-server (uvicorn loop) and startup-thread lines correctly fall through to the `core` sentinel. This is the intended behavior, not a bug.
**Warning signs:** A plugin line tagged `[core]`; a `[core]` line that clearly came from inside a plugin poll.

### Pitfall 3: Divide-by-zero / empty dataset
**What goes wrong:** Fresh install, no confirmed orders, or `test_mode` runs (where `place_order_guarded` suppresses the click and writes no marker — plugin_base.py:182-184) yield `attempted == 0`.
**How to avoid:** `_summarize` returns `success_rate=None` and `avg_time_to_checkout_secs=None` when the denominator is 0; the endpoint returns valid JSON with empty `per_plugin`. Add an explicit empty-DB test.
**Warning signs:** `ZeroDivisionError` in the endpoint; NaN in the UI.

### Pitfall 4: Timezone / naive-datetime in duration math
**What goes wrong:** Subtracting a naive from an aware datetime raises `TypeError`.
**Why it happens:** Both `confirmed_at` and `place_order_attempted_at` are written aware-UTC (`datetime.now(timezone.utc).isoformat()` — verified in orchestrator.py:436 and plugin_base.py:187), but a legacy/hand-inserted row could be naive.
**How to avoid:** Only include an order in the time-to-checkout sample when BOTH timestamps parse and the delta is `>= 0`; skip otherwise (already guarded in `compute_analytics`). Report `sample_size` so the operator sees the actual N.

### Pitfall 5: Credential leakage in the new endpoints
**What goes wrong:** Echoing `link` (URLs can embed tokens) or `last_error` in analytics; leaking raw exception strings in logs.
**How to avoid:** Analytics JSON contains only `platform_key` + integer/float aggregates — never `link`, never credentials. `/api/logs` returns raw file lines that are already scrubbed at write time (the codebase convention is `exc.__class__.__name__`, never `str(exc)` — verified across plugins and `core/health.py:record_last_error`). The plugin filter adds no new surface. Mirror the `CRED_PATTERN` assertion from `test_api_observability.py` for the analytics response.

### Pitfall 6: SquareEnix no-underscore platform_key
**What goes wrong:** Tagging/filtering with `square_enix` or `SquareEnixPlugin` instead of `squareenix`.
**How to avoid:** Verified `platform_key = "squareenix"` in `plugins/shopbot_plugin_squareenix.py`. The ContextVar is set from `plugin.platform_key`, so the tag is `[squareenix]` automatically; the UI dropdown must list platform_key values (`amazon, bestbuy, gamestop, newegg, squareenix, target, walmart`), sourced from `svc.list_plugins()` or the registry, not hardcoded class names.

## Code Examples

### FC-02 models accessor (read-only, mirrors get_confirmed_orders_sync)
```python
# models.py
def get_order_analytics_rows_sync():
    """Return rows needed for outcome analytics (FC-02). Read-only.
    Selects every item that was attempted (marker set) OR has an order_id, plus the
    two durable buy-flow timestamps. Link is included for platform resolution ONLY."""
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT name, link, order_id, confirmed_at, checkout_attempts,"
            " place_order_attempted_at, purchased"
            " FROM items"
            " WHERE place_order_attempted_at IS NOT NULL OR order_id IS NOT NULL"
        ).fetchall()
```

### FC-02 BotService accessor (MOD-02 seam; resolves platform via registry)
```python
# core/service.py
def get_analytics(self) -> dict:
    """Compute outcome analytics from existing order records (read-only, no bot start)."""
    from core.analytics import compute_analytics
    from core.registry import PluginRegistry
    from models import get_order_analytics_rows_sync
    from urllib.parse import urlparse
    plugins_dir = Path(__file__).parent.parent / "plugins"
    registry = PluginRegistry(self._cfg, plugins_dir)
    domain_map = [(getattr(p, "platform_key", type(p).__name__.lower()),
                   list(getattr(p, "domain_patterns", []))) for p in registry._all_plugins]
    def platform_of(link: str) -> str:
        host = urlparse(link or "").hostname or ""
        for key, patterns in domain_map:
            if any(pat in host for pat in patterns):
                return key
        return "core"
    rows = [dict(zip(
        ("name","link","order_id","confirmed_at","checkout_attempts",
         "place_order_attempted_at","purchased"), r)) for r in get_order_analytics_rows_sync()]
    return compute_analytics(rows, platform_of)
```

### FC-02 endpoint (read-only, async-safe, no CSRF dep — matches /status, /history)
```python
# web/routes/api.py
@router.get("/analytics")
async def get_analytics(request: Request):
    """Return outcome analytics (FC-02). Read is async-safe via asyncio.to_thread (SSE-03)."""
    data = await asyncio.to_thread(request.app.state.svc.get_analytics)
    return JSONResponse(data)
```

### FC-02 pure fixture test (exact assertions — the load-bearing test)
```python
# tests/test_analytics.py
from core.analytics import compute_analytics

def _row(link, order_id=None, confirmed_at=None, attempted_at=None):
    return {"name": "x", "link": link, "order_id": order_id, "confirmed_at": confirmed_at,
            "checkout_attempts": 0, "place_order_attempted_at": attempted_at, "purchased": 1}

def test_success_rate_and_time_to_checkout_exact():
    platform_of = lambda l: "amazon" if "amazon" in l else "bestbuy"
    rows = [
        _row("amazon.com/a1", "ORD-A1", "2026-01-01T00:00:30+00:00", "2026-01-01T00:00:00+00:00"),  # +30s
        _row("amazon.com/a2", "ORD-A2", "2026-01-01T00:00:50+00:00", "2026-01-01T00:00:00+00:00"),  # +50s
        _row("bestbuy.com/b1","ORD-B1", "2026-01-01T00:01:00+00:00", "2026-01-01T00:00:00+00:00"),  # +60s
        _row("bestbuy.com/b2","CONFIRMED-2026...", None,             "2026-01-01T00:00:00+00:00"),  # sentinel -> not confirmed
    ]
    out = compute_analytics(rows, platform_of)
    assert out["overall"]  == {"attempted": 4, "confirmed": 3, "success_rate": 0.75,
                               "avg_time_to_checkout_secs": (30+50+60)/3, "sample_size": 3}
    amazon = next(p for p in out["per_plugin"] if p["plugin"] == "amazon")
    assert amazon == {"plugin": "amazon", "attempted": 2, "confirmed": 2, "success_rate": 1.0,
                      "avg_time_to_checkout_secs": 40.0, "sample_size": 2}
    bestbuy = next(p for p in out["per_plugin"] if p["plugin"] == "bestbuy")
    assert bestbuy["success_rate"] == 0.5 and bestbuy["sample_size"] == 1

def test_empty_dataset_no_divide_by_zero():
    out = compute_analytics([], lambda l: "core")
    assert out == {"overall": {"attempted": 0, "confirmed": 0, "success_rate": None,
                               "avg_time_to_checkout_secs": None, "sample_size": 0}, "per_plugin": []}
```

### FC-02 confirmed-order schema (the `items` table — VERIFIED in models.py:38-85)
| Column | Type | Set by | Role in analytics |
|--------|------|--------|-------------------|
| `link` | TEXT UNIQUE | `add_items_sync` | Plugin identity via hostname → `domain_patterns` (no plugin column exists) |
| `order_id` | TEXT | `update_item_confirmed_sync` (BUY-04) | Confirmed marker; `CONFIRMED-<ts>` sentinel = unverified |
| `confirmed_at` | TEXT (ISO UTC) | `update_item_confirmed_sync` | End timestamp for time-to-checkout |
| `place_order_attempted_at` | TEXT (ISO UTC) | `mark_place_order_attempted_sync` (Phase 30, written by `place_order_guarded` right before the click) | Start timestamp for time-to-checkout; **attempted** denominator |
| `checkout_attempts` | INTEGER | `increment_checkout_attempts_sync` | Secondary/context only (increments even in test_mode — see below) |
| `purchased` | BOOLEAN | `update_item_purchased_sync` / `update_item_confirmed_sync` | Legacy success flag (may be 1 with `order_id=NULL`) |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Plugin identity as hand-written `[ClassName]` prefix in some messages | ContextVar-injected `[platform_key]` on every line | This phase (FC-01) | Reliable machine-parseable filter; existing manual prefixes become redundant (harmless; cleanup deferred) |
| `checkout_attempts` as the only attempt counter | `place_order_attempted_at` durable write-ahead marker (Phase 30/BF-02) | Phase 30 | Gives a real "a genuine non-suppressed buy click fired" signal — the correct success-rate denominator |

**Metric-definition detail (Claude's discretion resolved):**
- **success_rate = confirmed / attempted**, where **attempted** = rows with `place_order_attempted_at IS NOT NULL OR order_id IS NOT NULL`, and **confirmed** = rows with a non-sentinel `order_id`. Rationale for the union denominator: `place_order_attempted_at` is the truest "we tried a real buy" signal (it is written only on a non-suppressed click — plugin_base.py:182-191, so it is 0 in the documented-default `test_mode=true`), but `update_item_confirmed_sync` does not touch the marker, so a confirmed order could theoretically lack it; the union keeps `confirmed <= attempted` and avoids `checkout_attempts` (which increments even in test_mode via `_pre_attempt_check` → `increment_checkout_attempts_sync`, orchestrator.py:477, and would deflate the rate).
- **time_to_checkout = confirmed_at − place_order_attempted_at** per confirmed order having BOTH timestamps; averaged overall and per plugin. **Missing-timestamp scope:** there is **no stored "availability-detected" timestamp** suitable as an earlier anchor — `last_notified` (models.py) is availability-notification dedup state, updated/cleared on stock edges, not a buy-attempt time. So the metric is scoped to the two durable buy-flow timestamps; `sample_size` reports how many orders qualified.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `place_order_attempted_at` is the preferred success-rate denominator over `checkout_attempts` | State of the Art / Pitfall 3 | If the operator wants "attempts" to mean cart-attempts (incl. test_mode), the denominator differs — surface in discuss-phase; both definitions are one-line swaps in `compute_analytics` |
| A2 | Time-to-checkout should be attempt→confirmation (no earlier detection anchor exists) | State of the Art | If a detection timestamp is later added, the metric can be re-anchored; today it is scoped to available fields |
| A3 | Setting the ContextVar in `supervise()` (not per-item in `run_plugin`) is sufficient granularity | Pattern 1 | Lines from `_staggered_setup`/`restore_session` (run in `async_main`'s context, before tasks) will be `[core]` even when about a plugin — acceptable per the sentinel decision, but note it |

**All other claims are VERIFIED against the code in this session or CITED to Python docs.**

## Open Questions

1. **Should the `CONFIRMED-<ts>` sentinel appear as a distinct "unverified" count in the UI?**
   - What we know: sentinels mean "URL matched, no real order id" (possibly a payment-failure page reaching the thankyou URL — core/confirmation.py:140-151).
   - What's unclear: whether the operator wants them shown separately vs. simply excluded from `confirmed`.
   - Recommendation: exclude from `success_rate` (done); optionally add an `unverified` count later (deferred — not required by FC-02).

2. **Populate the log-plugin dropdown server-side or client-side?**
   - What we know: `svc.list_plugins()` returns discovered plugins (class name + domain_patterns) but NOT `platform_key`. The template is Jinja2-rendered.
   - Recommendation: extend `list_plugins()` to include `platform_key` (one line: `getattr(plugin, "platform_key", None)`), render `<option>`s from it. Low-risk, keeps the dropdown authoritative.

## Environment Availability

> Skip-eligible: this phase is code + template + CSS only. No new external tools/services.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `contextvars` | FC-01 tag | ✓ (stdlib, Py>=3.11) | stdlib | — |
| `fastapi`/`uvicorn`/`jinja2` | endpoints + template | ✓ (declared `[web]`) | 0.115.8 / 0.30.6 / 3.1.6 | — |
| Vendored uPlot | (only if a chart were added) | ✓ | 1.6.32 | Not used — cards+table |

No missing dependencies.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (installed), `asyncio_mode=auto` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"]) |
| Quick run command | `pytest tests/test_analytics.py tests/test_logger.py tests/test_log_reader.py -x` |
| Full suite command | `pytest` |

> Note: full web/API tests need `pip install -e .[web]` and `pip install httpx` (httpx undeclared — per project memory).

### Phase Requirements → Test Map
| Req ID | Behavior (testable truth) | Test Type | Automated Command | File Exists? |
|--------|---------------------------|-----------|-------------------|-------------|
| FC-01 | Every newly-written line carries a `[plugin]` tag (set context → `[amazon]`; no context → `[core]`) | unit | `pytest tests/test_logger.py -x` | ❌ Wave 0 (extend) |
| FC-01 | `read_logs_filtered(plugin=...)` returns only matching lines; composes with level+search; absent=all | unit | `pytest tests/test_log_reader.py -x` | ❌ Wave 0 (extend) |
| FC-01 | `/api/logs?plugin=` passes through to `read_logs_filtered`; existing arity tests updated | integration | `pytest tests/test_api_observability.py -x` | ✅ (UPDATE 2 asserts) |
| FC-02 | `compute_analytics` yields exact success-rate + time-to-checkout on a fixture order set | unit | `pytest tests/test_analytics.py -x` | ❌ Wave 0 (new) |
| FC-02 | Empty dataset → no divide-by-zero, valid JSON | unit | `pytest tests/test_analytics.py -x` | ❌ Wave 0 (new) |
| FC-02 | `/api/analytics` returns computed JSON, no credential pattern | integration | `pytest tests/test_api_observability.py -x` | ✅ (extend) |
| FC-01/02 | Existing log + design-system tests stay green | regression | `pytest tests/test_logger.py tests/test_log_reader.py tests/test_design_system.py -x` | ✅ |

### Sampling Rate
- **Per task commit:** `pytest tests/test_analytics.py tests/test_logger.py tests/test_log_reader.py -x`
- **Per wave merge:** `pytest tests/test_api_observability.py tests/test_web_dashboard.py tests/test_design_system.py tests/test_orchestrator.py -x`
- **Phase gate:** full `pytest` green before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_analytics.py` — covers FC-02 (pure exact assertions + empty case)
- [ ] `tests/test_logger.py` — add tag-injection tests (with/without context) covering FC-01
- [ ] `tests/test_log_reader.py` — add plugin-filter tests covering FC-01
- [ ] `tests/test_api_observability.py` — UPDATE `test_logs_filtered_level_and_search` and `test_logs_no_params_default_behavior` arity asserts; ADD analytics endpoint test
- [ ] New source: `core/analytics.py`; `models.get_order_analytics_rows_sync`; `logger` ContextVar + `set_log_plugin`; `read_logs_filtered` plugin param; `/api/analytics` route
- Framework install: none new (pytest present; web extras per memory)

## Security Domain

> `security_enforcement` not present in `.planning/config.json` → treated as enabled. Light surface (local read-only dashboard).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Local-only dashboard; no auth in scope |
| V3 Session Management | no | — |
| V4 Access Control | partial | State-changing routes carry `check_origin`; new routes are read-only GET → no CSRF dep needed (matches `/status`, `/history`, `/logs`) |
| V5 Input Validation | yes | `plugin` query param is untrusted; treat as a substring filter only. Defense-in-depth: optionally whitelist against known `platform_key` values before matching |
| V6 Cryptography | no | No new crypto |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential leak via analytics/log response | Information Disclosure | Aggregate-only output (platform_key + numbers); never emit `link`; log lines already scrubbed to `exc.__class__.__name__` at write time; assert with `CRED_PATTERN` |
| Log-injection via crafted item name reaching a log line | Tampering | Tag is injected by the trusted logging path (not user-controlled); filter is read-only substring; no eval/render of log content beyond `textContent` (dashboard.html uses `textContent`, not innerHTML, for log lines) |
| Arbitrary `plugin` substring probing the log file | Information Disclosure | Optional whitelist to known platform_keys; the file is already fully readable via existing `search` param, so no new exposure |

## Sources

### Primary (HIGH confidence)
- Codebase (verified this session): `logger.py`, `web/log_reader.py`, `web/routes/api.py`, `models.py`, `core/orchestrator.py`, `core/service.py`, `core/registry.py`, `core/plugin_base.py`, `core/confirmation.py`, `core/health.py`, `web/templates/dashboard.html`, `web/static/{tokens,components,dashboard}.css`, `tests/test_api_observability.py`, `tests/test_models.py`, `tests/test_logger.py`, `tests/test_log_reader.py`, `tests/test_design_system.py`, `plugins/shopbot_plugin_squareenix.py`, `.planning/{REQUIREMENTS,STATE}.md`
- [docs.python.org/3/library/contextvars.html] — Task context copy semantics, `ContextVar` defaults

### Secondary (MEDIUM confidence)
- [bugs.python.org/issue34014] — `loop.run_in_executor` does NOT propagate contextvars
- [github.com/python/cpython/issues/136157] — `asyncio.to_thread` copies context (contrast with executor)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib/already-declared; no new packages
- Architecture (tag + analytics wiring): HIGH — verified against exact call sites, schema, and task structure
- Pitfalls: HIGH — the two breaking tests, the executor context gap, the sentinel, and the test_mode marker behavior were each confirmed in source

**Research date:** 2026-07-02
**Valid until:** 2026-08-01 (stable internal codebase; re-verify if orchestrator task structure or `items` schema changes)
