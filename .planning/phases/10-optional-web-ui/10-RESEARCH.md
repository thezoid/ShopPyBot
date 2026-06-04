# Phase 10: Optional Web UI - Research

**Researched:** 2026-06-04
**Domain:** FastAPI + Jinja2 server-rendered dashboard, optional [web] extra, CSRF defense, credential-safe HTTP
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Server-rendered Jinja2 templates + minimal hand-written vanilla JS (no frontend build step).
- `[web]` optional extra pins: `fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart` — exact-pinned, added to `pyproject.toml [project.optional-dependencies] web`.
- Live status/logs via polling: JS `fetch` to `/api/status` and `/api/logs` every ~2s (no websocket/SSE).
- Code layout: lazy-imported `web/` package exposing `create_app(svc)`, plus `templates/` and `static/`. `core/cli/web.py:handle_web` imports it inside the function body only — never at module top (CLI-04).
- Credential form lists each known key by NAME with set/unset status only — NEVER renders the current value. POST stores via `CredentialStore.set()`; HTTP response is success/failure status only.
- `--host` flag defaults to `127.0.0.1`. Binding to any non-localhost address prints a prominent security warning to stderr BEFORE the server starts.
- No authentication for the default localhost bind.
- Validate `Origin`/`Host` header on all state-changing POSTs to mitigate local-malware CSRF against `127.0.0.1`.
- Single dashboard page with four sections: Controls/Status, Items, Credentials, Config.
- Items: table + add form + per-row remove — routed through `BotService.add_item/remove_item/list_items`.
- Controls: Start/Stop buttons calling `BotService.start()/stop()`; status from `BotService.get_status()`; recent-logs panel updated by polling.
- Styling: small vendored CSS under `static/` — no CDN.
- All UI actions route through `BotService` — never `models.py`/orchestrator/registry directly (MOD-02).
- Config editing mirrors the CLI `config set` allowlist (`test_mode`, `logging_level`) plus per-notifier enable toggles.
- Tests use FastAPI's `TestClient`; the whole web test module is skipped when fastapi is not installed.
- CLI-04: fastapi imported only inside the `web/` package, which itself is imported only lazily.

### Claude's Discretion
- Exact route paths and template partials, the precise polling interval (2s confirmed), the vendored CSS contents, how `create_app` obtains/holds the BotService instance, the Origin-check implementation detail, and uvicorn invocation specifics.

### Deferred Ideas (OUT OF SCOPE)
- Authentication / multi-user / remote hosting.
- Websocket/SSE live streaming.
- Full AppConfig editor in the UI (limited to CLI allowlist + notifier enables).
- Cross-platform verification matrix / CI (Phase 11).
- CVV entry in the web UI.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GUI-01 | Optional local web UI (FastAPI) launched via `shoppybot web`, served on localhost; provides nothing the CLI cannot do | create_app factory + app.state.svc; MOD-02 AST guard; TestClient SC2 parity tests |
| GUI-02 | Manage tracked items (list/add/remove) via BotService | `/api/items` GET/POST/DELETE routes; SC2 parity test asserting same DB state as CLI |
| GUI-03 | Manage credentials + per-platform config via CredentialStore (never plaintext to browser) | JSON-only POST body; `{"status":"ok"}` response only; SC3 assertion secret absent from all responses |
| GUI-04 | Start/stop the bot and view live status + recent logs | `/api/bot/start|stop`, `/api/status`, `/api/logs`; BotService.start()/stop()/get_status(); log file read pattern |
| GUI-05 | Web UI is optional extra (`pip install .[web]`); core + CLI run without FastAPI | `pytest.importorskip('fastapi')` skip guard; CLI-04 preserved; existing test_cli_no_fastapi.py stays green |
| GUI-06 | Binds to 127.0.0.1 by default; non-localhost bind requires explicit opt-in + clear security warning | `is_localhost()` using `ipaddress.ip_address.is_loopback`; stderr warning before uvicorn.run; in-page banner |
</phase_requirements>

## Summary

Phase 10 adds an optional FastAPI dashboard as a thin adapter over the existing `BotService` and `CredentialStore` APIs. The stack is fully verified on this machine: FastAPI 0.115.8, Pydantic 2.13.3, Jinja2 3.1.4, uvicorn 0.30.6, and starlette 0.45.3 are all installed and interoperable. The app-factory pattern `create_app(svc)` stores the service on `app.state.svc` and accesses it via `request.app.state.svc` in route handlers — verified working with TestClient. The lazy-import seam in `core/cli/web.py` is already in place from Phase 9; Phase 10 fills in the function body.

Security is the highest-risk dimension. Three controls defend it: (1) credential values never appear in any HTTP response or template — JSON routes return only `{"status": "ok/error"}`; (2) `Origin`/`Host` header validation via a FastAPI `Depends` dependency on all state-changing routes rejects cross-origin requests with 403; (3) non-localhost bind detection using `ipaddress.ip_address.is_loopback` prints a warning to stderr before `uvicorn.run` and injects a `is_non_local` flag into every Jinja2 template for the in-page banner. All three controls have been verified by live Python execution in this session.

The test architecture mirrors existing Phase 9 patterns: `pytest.importorskip('fastapi')` at the top of `tests/test_web.py` skips the entire module on a bare `pip install .`, preserving the 282-test baseline. SC2 parity, SC3 credential-leak, SC6 host-warning, and MOD-02 AST-guard tests are all feasible with `TestClient` and the existing `ast.parse` approach already used in `test_cli_mod02.py`.

**Primary recommendation:** Implement in four waves — (1) package skeleton + pyproject.toml update + CLI handle_web body; (2) API routes (status, items, bot control, logs, config, credentials) with CSRF dep; (3) Jinja2 template + vendored CSS + JS polling; (4) full test suite.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Bot start/stop/status | API (BotService) | Frontend Server (SSR for initial render) | BotService owns lifecycle; web routes are thin adapters |
| Item list/add/remove | API (BotService -> models) | Frontend Server (page render) | BotService.add_item/remove_item/list_items are the single seam |
| Credential set/status | API (CredentialStore) | Frontend Server (renders key names + status) | Secrets never travel to browser; CredentialStore.set() is the write path |
| Config read/write | API (yaml read + _atomic_yaml_write) | Frontend Server (renders current values) | Mirrors CLI config_cmd pattern exactly |
| Recent logs | Frontend Server (reads log file) | Browser (updates pre block every 2s) | Log files are server-side; browser polls /api/logs |
| CSRF defense | API (Depends on all state-changing routes) | — | Must be server-side; browser cannot validate itself |
| Non-localhost warning | CLI layer (before uvicorn.run) + Frontend Server | Browser (renders banner) | Warning must precede server startup; template injects flag |
| Static assets / CSS | CDN/Static (StaticFiles mount) | — | Vendored CSS served by FastAPI StaticFiles |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.115.8 | ASGI web framework, route declarations | Locked decision; installed on this machine [VERIFIED: pip registry] |
| uvicorn | 0.30.6 | ASGI server; `uvicorn.run(app, host=, port=)` | Locked decision; installed on this machine [VERIFIED: pip registry] |
| jinja2 | 3.1.4 | Server-side HTML templating | Locked decision; installed on this machine [VERIFIED: pip registry] |
| python-multipart | 0.0.32 | Form body parsing (FastAPI Form() support) | Locked decision; latest version on PyPI; NOT currently installed [VERIFIED: pip index versions] |
| starlette | 0.45.3 | FastAPI dependency; TestClient lives here | Installed as fastapi transitive dep [VERIFIED: pip registry] |

### Supporting (already installed — no new deps)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.13.3 | FastAPI model validation | Already installed; confirmed compatible with fastapi 0.115.8 [VERIFIED: pip registry] |
| ipaddress | stdlib | Localhost detection via `ip_address.is_loopback` | stdlib; no install required |
| pathlib | stdlib | Log file path construction | stdlib; already used throughout project |
| yaml | installed | Config read/write for web config section | Already in requirements.txt |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Jinja2 server-render | SPA (React/Vue) | SPA requires a build step and secrets could be passed to client; locked out |
| polling fetch | WebSocket/SSE | Simpler, no extra protocol; locked out by CONTEXT.md |
| `app.state.svc` | Closure / global | `app.state` is the idiomatic FastAPI way to inject application-wide objects into routes; closures work but are less readable; globals are unsafe in testing |

**Installation (adds to `pyproject.toml [project.optional-dependencies] web`):**
```bash
pip install ".[web]"
```

Which installs: `fastapi==0.115.8 uvicorn[standard]==0.30.6 jinja2==3.1.4 python-multipart==0.0.32`

Note: `uvicorn[standard]` installs optional extras `httptools`, `watchfiles`, `websockets`; `httptools` and `uvloop` are not available on Windows (uvloop is Unix-only). On Windows, uvicorn falls back to `h11` (already installed at 0.16.0). This is safe: `uvicorn[standard]` gracefully omits platform-incompatible extras. [VERIFIED: tested; h11 present; httptools/uvloop absent, no error]

## Package Legitimacy Audit

slopcheck could not be installed (permission denied by auto-mode classifier). All packages below are cross-referenced against PyPI registry + official project pages. Packages are well-established with multi-year histories.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| fastapi | PyPI | 6+ yrs | 100M+/mo | github.com/fastapi/fastapi | [ASSUMED] | Approved — canonical ASGI framework, installed on machine |
| uvicorn | PyPI | 7+ yrs | 80M+/mo | github.com/encode/uvicorn | [ASSUMED] | Approved — standard ASGI server, installed on machine |
| jinja2 | PyPI | 16+ yrs | 200M+/mo | github.com/pallets/jinja | [ASSUMED] | Approved — installed on machine as pytest-html dep |
| python-multipart | PyPI | 12+ yrs | 50M+/mo | github.com/andrew-d/python-multipart | [ASSUMED] | Approved — standard FastAPI form dep, latest 0.0.32 confirmed |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was unavailable at research time (install blocked). All packages above are tagged `[ASSUMED]` and the planner must gate each `pip install` behind a `checkpoint:human-verify` task.*

## Architecture Patterns

### System Architecture Diagram

```
shoppybot web [--host H] [--port P]
        |
        v
core/cli/web.py: handle_web(args, svc)
  -- lazy import: from web import create_app
  -- is_localhost(args.host) check
  -- stderr warning if non-local
  -- svc = svc or BotService()
  -- app = create_app(svc)
  -- uvicorn.run(app, host=args.host, port=args.port)
        |
        v
web/__init__.py: create_app(svc) -> FastAPI
  app.state.svc = svc
  app.state.is_non_local = not is_localhost(host)  [set by handle_web via lifespan or app kwarg]
  -- mount StaticFiles("/static", web/static/)
  -- Jinja2Templates(web/templates/)
  -- include_router(api_router)   [/api/...]
  -- GET / -> dashboard.html template
        |
        +----> GET /api/status      -> svc.get_status()
        +----> GET /api/logs        -> read last 50 lines from logs/YYYYMMMDD.log
        +----> GET /api/items       -> svc.list_items()
        +----> POST /api/items      [CSRF dep] -> svc.add_item(name, link, auto_buy, qty)
        +----> DELETE /api/items/{url_b64} [CSRF dep] -> svc.remove_item(link)
        +----> POST /api/bot/start  [CSRF dep] -> svc.start()    (no CVV -- web scope)
        +----> POST /api/bot/stop   [CSRF dep] -> svc.stop()
        +----> GET /api/config      -> svc.get_config().model_dump() (safe fields only)
        +----> POST /api/config     [CSRF dep] -> _atomic_yaml_write (ALLOWLIST gated)
        +----> GET /api/credentials -> SECRET_KEYS + set/unset status (values NEVER returned)
        +----> POST /api/credentials [CSRF dep] -> get_store().set(key, value)
                                                   response: {"status":"ok"} only

Browser (dashboard.html)
  -- inline <script> polls /api/status + /api/logs every 2000ms
  -- fetch-based form submission (no page reload)
  -- non-local warning banner rendered server-side via Jinja2 flag
```

### Recommended Project Structure

```
web/                         # lazy-imported package (fastapi only imported here)
  __init__.py                # create_app(svc) factory; mounts static + templates
  routes/
    __init__.py
    api.py                   # APIRouter with all /api/* routes
    pages.py                 # GET / -> TemplateResponse
  security.py                # check_origin Depends + is_localhost helper
  log_reader.py              # read_last_n_lines(n=50) -> list[str]
  config_web.py              # web config read/write (mirrors config_cmd ALLOWLIST)
  templates/
    dashboard.html           # single Jinja2 template; inline <script> polling
  static/
    dashboard.css            # vendored minimal CSS per UI-SPEC
```

Files stay under 300 lines by splitting routes into `api.py` (data/action endpoints) and `pages.py` (HTML page route). `security.py` is short (~30 lines). `log_reader.py` is ~20 lines.

### Pattern 1: App Factory with Service Injection

**What:** `create_app(svc)` creates a fresh FastAPI instance, stores `svc` on `app.state`, returns the app. Routes access the service via `request.app.state.svc`.

**When to use:** Any time you need to inject a service into FastAPI routes without a global.

**Example:**
```python
# Source: verified via live Python execution 2026-06-04
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

def create_app(svc) -> FastAPI:
    app = FastAPI(title="ShopPyBot Dashboard")
    app.state.svc = svc
    return app

# In a route:
@router.get("/api/status")
async def get_status(request: Request):
    return JSONResponse(request.app.state.svc.get_status())
```

### Pattern 2: CSRF Origin Check as Depends

**What:** A `Depends` function reads `Origin` and `Host` headers; raises `HTTPException(403)` if the origin is cross-site. Applied as `dependencies=[Depends(check_origin)]` on all state-changing routes.

**When to use:** Every POST/DELETE route (items, credentials, config, bot start/stop).

**Example:**
```python
# Source: verified via live Python execution 2026-06-04
from fastapi import Depends, HTTPException, Request
from urllib.parse import urlparse

_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}

def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        return  # same-origin browser requests may omit Origin header
    parsed = urlparse(origin)
    host = parsed.hostname or ""
    if host not in _ALLOWED_HOSTS:
        raise HTTPException(status_code=403, detail="CSRF: origin rejected")
```

Note: the allowed hosts set must be expanded dynamically when `--host` is non-localhost (the server is intentionally exposed). When `is_non_local=True`, the check must still validate that the Origin matches the *server's own* host, not that it's localhost.

### Pattern 3: Non-Localhost Warning Before Server Start

**What:** `handle_web` calls `is_localhost(args.host)` before `uvicorn.run`. If false, prints warning to stderr and sets a flag on `app.state` so the Jinja2 template renders the banner.

**When to use:** Always, inside `handle_web` before uvicorn.run.

**Example:**
```python
# Source: verified via live Python execution 2026-06-04
import ipaddress, sys

def is_localhost(host: str) -> bool:
    h = host
    if h.startswith("["):
        h = h[1:].split("]")[0]   # strip IPv6 brackets
    elif ":" in h:
        try:
            ipaddress.ip_address(h)  # pure IPv6 -- don't strip
        except ValueError:
            h = h.rsplit(":", 1)[0]  # strip port from IPv4:port
    if h in ("localhost", "127.0.0.1"):
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False

# In handle_web:
if not is_localhost(args.host):
    print(
        "WARNING: ShopPyBot dashboard is binding to a non-local interface. "
        "Credential management will be exposed. Use only on a trusted private network.",
        file=sys.stderr,
    )
app.state.is_non_local = not is_localhost(args.host)
```

### Pattern 4: Safe Recent-Logs Read

**What:** `/api/logs` reads the last N lines of today's log file. The file is never held open between requests. Secrets are never written to logs (CRED-06 established), so no redaction is needed at read time.

**When to use:** `/api/logs` endpoint.

**Example:**
```python
# Source: verified via live Python execution 2026-06-04
import datetime, pathlib

_LOG_DIR = pathlib.Path(__file__).parent.parent / "logs"

def read_recent_logs(n: int = 50) -> list[str]:
    today = datetime.date.today()
    fname = datetime.datetime.now().strftime("%Y%B%d") + ".log"
    log_path = _LOG_DIR / fname
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return text.splitlines()[-n:]
```

Note: `logger.py` uses `datetime.now().strftime('%Y%B%d')` which produces title-case month (e.g. `2026June04`). The log reader must use the same format string.

### Pattern 5: Config Web Section (mirroring CLI ALLOWLIST)

**What:** The web config endpoint reads/writes only ALLOWLIST keys from `config_cmd.py` plus notifier enable toggles (`notifications.discord.enabled`, `notifications.email.enabled`, `notifications.sms.enabled`, `notifications.sound`). It reuses `_atomic_yaml_write` from `core/cli/config_cmd.py` directly (import inside web package is allowed — `config_cmd` is not in the forbidden list).

**Key finding:** Platforms (`amazon`, `bestbuy`, etc.) have NO `enabled` field in the current `AppConfig` schema. The CONTEXT.md phrase "per-platform/notifier enable toggles" in practice means notifier toggles only. The planner should scope Config section to: `test_mode`, `logging_level`, and the four notifier toggles (`sound`, `discord.enabled`, `email.enabled`, `sms.enabled`).

### Anti-Patterns to Avoid

- **Importing fastapi at module top in web.py:** The CLI-04 invariant requires the lazy-import pattern already established. Any `import fastapi` outside `web/` or outside a function body in `core/cli/web.py` breaks it.
- **Echoing the credential value in any response:** Even as a confirmation echo. The SC3 assertion tests for the literal value in the response body.
- **Using `asyncio.run()` inside a FastAPI async route:** Routes are already running in an asyncio event loop. `asyncio.run()` will raise. Use `await` or call sync BotService methods directly (they are safe from async context).
- **BotService.start() CVV parameter in the web UI:** The locked decision is that CVV stays a CLI/runtime concern. `POST /api/bot/start` calls `svc.start()` with no CVV argument (or `cvv=None`).
- **Mutable global for the service:** Use `app.state.svc`; do not use a module-level global. TestClient creates a new app per test; app.state scopes correctly.
- **Template variables with secret values:** Never pass a credential value to `TemplateResponse` context. Pass only key names and `is_set` booleans.
- **Full page reload on form submit:** All forms submit via `fetch`; full-page reloads are rejected by the UI-SPEC.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ASGI server | Custom socket server | `uvicorn.run(app, host=, port=)` | Thread management, signal handling, HTTP/1.1 compliance |
| Template rendering | String f-format HTML | `Jinja2Templates.TemplateResponse` | Escaping, context injection, file-based templates |
| Origin parsing | Regex on header string | `urllib.parse.urlparse(origin).hostname` | stdlib; handles schemes, ports, IPv6 correctly |
| Localhost detection | String prefix check | `ipaddress.ip_address(h).is_loopback` | Handles IPv6, loopback range (127.x.x.x), not just 127.0.0.1 |
| Atomic config write | `open(path, 'w')` direct write | `_atomic_yaml_write` from `core/cli/config_cmd.py` | Already exists; same tempfile+os.replace pattern as EncryptedFileBackend |

**Key insight:** The entire web layer is a thin adapter. Every "business logic" problem is already solved by BotService, CredentialStore, or existing CLI helpers. Hand-rolling any of them in the web layer violates MOD-02 and DRY simultaneously.

## Common Pitfalls

### Pitfall 1: CLI-04 Top-Level Import Leak
**What goes wrong:** Adding `from web import create_app` or `import fastapi` at the top of `core/cli/web.py` or any other file on the CLI import path causes the existing `test_cli_no_fastapi.py` test to fail.
**Why it happens:** Python resolves top-level imports eagerly; `sys.modules['fastapi'] = None` in the test simulates absence, causing ImportError on any eager import.
**How to avoid:** All fastapi imports live only inside `web/` package files. `handle_web` does `from web import create_app` inside the function body. The `test_cli_mod02.py`-style AST scan for `core/cli/` already guards this; extend it to scan for top-level fastapi imports.
**Warning signs:** `test_cli_no_fastapi.py::test_run_works_without_fastapi` fails; `test_web_no_fastapi` fails.

### Pitfall 2: asyncio Conflict Between uvicorn and BotService
**What goes wrong:** uvicorn runs its own asyncio event loop. BotService.start() creates a *separate* daemon thread with its own event loop. Calling `asyncio.run()` or `asyncio.get_event_loop()` from inside a FastAPI route will touch uvicorn's loop, not BotService's loop.
**Why it happens:** asyncio event loops are thread-local; route handlers run on uvicorn's loop.
**How to avoid:** BotService.start() and .stop() are synchronous methods (they use threading internally, not asyncio). Calling them from async route handlers is safe: sync methods called from async context are fine as long as they don't block for a long time. start() returns quickly (waits up to 5s for ready signal but is non-blocking in practice). stop() calls thread.join(15s) — run in a thread pool executor if blocking is a concern: `await asyncio.get_event_loop().run_in_executor(None, svc.stop)`.
**Warning signs:** `RuntimeError: This event loop is already running` in route handlers.

### Pitfall 3: Log File Format String Mismatch
**What goes wrong:** `/api/logs` opens the wrong file (empty result) because the filename uses a different date format than `logger.py`.
**Why it happens:** `logger.py` uses `datetime.now().strftime('%Y%B%d')` which gives title-case month (`2026June04`), not `JUNE` or `06`.
**How to avoid:** Use the exact same format string `'%Y%B%d'` in `log_reader.py`. Verified by live execution: `datetime.datetime.now().strftime('%Y%B%d')` = `2026June04`.
**Warning signs:** `/api/logs` always returns empty list even when bot has been running.

### Pitfall 4: Python-multipart Not Installed, Form() Used
**What goes wrong:** If a route uses `Form()` for field parsing (HTML form encoding), FastAPI raises a 422 at runtime because `python-multipart` is not installed on this machine currently.
**Why it happens:** `python-multipart` is in the locked `[web]` extra but not yet installed.
**How to avoid:** All form submissions use JSON (`Content-Type: application/json`) from the JS `fetch` calls. Routes read `await request.json()` instead of `Form()` fields. This makes `python-multipart` present in the deps list for completeness (some edge paths) but not strictly required.
**Warning signs:** `422 Unprocessable Entity` on form POST routes.

### Pitfall 5: Credential Value in Template Context
**What goes wrong:** A developer passes `{"key": key, "value": store.get(key)}` to the template to pre-fill the input. This sends the secret to the browser.
**Why it happens:** Convenience / copy-paste from other CRUD views.
**How to avoid:** Template context for credentials contains only `key_name` (str) and `is_set` (bool). The SC3 test does `assert secret_value not in response.text` for every credential endpoint.
**Warning signs:** SC3 test fails; `"is_set"` replaced by actual value in template.

### Pitfall 6: CSRF Origin Check Breaks localhost 127.0.0.1:PORT
**What goes wrong:** Origin header sent by Chrome for same-origin fetch is `http://127.0.0.1:8000`. The check compares hostname only (via `urlparse`), so `parsed.hostname = '127.0.0.1'` — this is in `_ALLOWED_HOSTS` and passes. No problem.
**Why it happens:** Not a pitfall if `urlparse` is used. The pitfall is using a raw `startswith` check that would fail on `http://127.0.0.1:8000` (it starts with `http://`, not `127.0.0.1`).
**How to avoid:** Always use `urllib.parse.urlparse(origin).hostname` for the comparison. Verified working: `urlparse('http://127.0.0.1:8000').hostname == '127.0.0.1'`.
**Warning signs:** All state-changing POSTs return 403 even from the dashboard itself.

### Pitfall 7: uvicorn[standard] Fails on Windows Due to uvloop
**What goes wrong:** `pip install uvicorn[standard]` on Windows attempts to install `uvloop`, which only compiles on Unix. This would cause an install error.
**Why it happens:** uvloop is a Unix-only C extension.
**How to avoid:** Current behavior (verified): `uvicorn[standard]` on Windows gracefully skips uvloop. The installed version (0.30.6) has `h11==0.16.0` already present, which is sufficient. Latest uvicorn (0.49.0) is available; the plan should pin to the version tested in this environment (`0.30.6`) unless upgrading is explicitly desired. Pin to `uvicorn[standard]==0.30.6`.
**Warning signs:** `pip install .[web]` fails on Windows with a compile error for uvloop.

### Pitfall 8: MOD-02 Guard Missing for web/ Package
**What goes wrong:** `test_cli_mod02.py` only scans `core/cli/*.py`. The web/ package could import `models` or `orchestrator` directly and the existing guard would miss it.
**Why it happens:** The test was written before the web/ package existed.
**How to avoid:** Extend `test_cli_mod02.py` (or add `test_web_mod02.py`) to scan `web/**/*.py` with the same forbidden-names set. The AST scan pattern is already proven and reusable.
**Warning signs:** `test_web_mod02` not present; web routes bypass BotService.

## Code Examples

### create_app Factory (complete skeleton)
```python
# Source: verified pattern via live Python execution 2026-06-04
# web/__init__.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

_HERE = Path(__file__).parent

def create_app(svc, is_non_local: bool = False) -> "FastAPI":
    app = FastAPI(title="ShopPyBot Dashboard", docs_url=None, redoc_url=None)
    app.state.svc = svc
    app.state.is_non_local = is_non_local

    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")

    from web.routes.api import router as api_router
    from web.routes.pages import router as pages_router
    app.include_router(api_router, prefix="/api")
    app.include_router(pages_router)

    return app
```

### handle_web (complete body)
```python
# Source: verified pattern via live Python execution 2026-06-04
# core/cli/web.py (body only -- keep existing module-level imports as-is)
def handle_web(args, svc=None) -> int:
    try:
        from web import create_app          # lazy -- only inside function
    except ImportError:
        print("FastAPI is not installed. Run: pip install .[web]", file=sys.stderr)
        return 1

    import uvicorn                          # also lazy -- only if fastapi present
    from core.service import BotService
    from web.security import is_localhost

    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8000)
    is_non_local = not is_localhost(host)

    if is_non_local:
        print(
            "WARNING: ShopPyBot dashboard is binding to a non-local interface. "
            "Credential management is exposed on a non-local interface. "
            "Use only on a trusted private network.",
            file=sys.stderr,
        )

    resolved_svc = svc if svc is not None else BotService()
    app = create_app(resolved_svc, is_non_local=is_non_local)
    uvicorn.run(app, host=host, port=port)
    return 0
```

### CSRF check_origin Depends
```python
# Source: verified pattern via live Python execution 2026-06-04
# web/security.py
import ipaddress
from urllib.parse import urlparse
from fastapi import HTTPException, Request

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

def is_localhost(host: str) -> bool:
    h = host
    if h.startswith("["):
        h = h[1:].split("]")[0]
    elif ":" in h:
        try:
            ipaddress.ip_address(h)
        except ValueError:
            h = h.rsplit(":", 1)[0]
    if h in _LOCAL_HOSTS:
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False

def check_origin(request: Request) -> None:
    """FastAPI Depends -- rejects cross-origin state-changing requests (CSRF)."""
    origin = request.headers.get("origin")
    if origin is None:
        return
    hostname = urlparse(origin).hostname or ""
    server_host = request.url.hostname or "127.0.0.1"
    # Allow if origin matches server host or is a known local host
    if hostname != server_host and hostname not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="CSRF: origin rejected")
```

### TestClient skip guard pattern
```python
# Source: verified pattern via live Python execution 2026-06-04
# tests/test_web.py (top of file)
import pytest
pytest.importorskip("fastapi")   # skips entire module if fastapi absent

from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from web import create_app

@pytest.fixture
def client(tmp_data_dir):
    svc = MagicMock()
    svc.get_status.return_value = {"running": False}
    svc.list_items.return_value = []
    return TestClient(create_app(svc))

def test_status_route(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert "running" in resp.json()
```

### SC3 credential-leak assertion
```python
# Source: derived from CONTEXT.md SC3 requirement + verified JSON-only approach
def test_credential_set_no_value_in_response(client):
    secret_value = "super-secret-password-12345"
    resp = client.post(
        "/api/credentials",
        json={"key": "AMZ_EMAIL", "value": secret_value},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert resp.status_code == 200
    assert secret_value not in resp.text          # SC3: not in JSON body
    assert resp.json()["status"] == "ok"

def test_credential_page_no_value_rendered(client):
    # Verify GET /api/credentials returns only key names + is_set booleans
    resp = client.get("/api/credentials")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["credentials"]:
        assert "value" not in item               # SC3: no value field exposed
        assert "name" in item
        assert "is_set" in item
```

### SC2 parity assertion (web add == CLI DB state)
```python
# Source: derived from CONTEXT.md SC2 requirement
def test_web_add_item_parity(tmp_data_dir):
    """Web add produces identical DB state to CLI add."""
    from core.service import BotService
    from fastapi.testclient import TestClient
    from web import create_app

    svc = BotService()
    client = TestClient(create_app(svc))
    client.post(
        "/api/items",
        json={"name": "Widget", "link": "https://example.com/w", "auto_buy": False, "quantity": 1},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    rows = svc.list_items()
    assert any(r[1] == "https://example.com/w" for r in rows)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global `app` variable | `create_app(svc)` factory | FastAPI 0.63+ | Enables per-test app instances with TestClient |
| `from fastapi import Form` for all form fields | `await request.json()` for JSON fetch | FastAPI always supported both | JSON approach avoids python-multipart dependency for body parsing |
| Starlette middleware for CSRF | FastAPI `Depends` on individual routes | FastAPI 0.95+ (Depends cleaner) | Per-route control; more explicit; easier to test |
| `uvicorn.Config` + `Server().serve()` coroutine | `uvicorn.run(app, ...)` synchronous | uvicorn stable | `uvicorn.run` is blocking sync; correct for handle_web which is called from sync CLI |

**Deprecated / outdated:**
- `app.add_middleware(CORSMiddleware, ...)` for CSRF: CORS is about browser policy, not server-side origin validation. Local-malware CSRF defense requires server-side Origin header checking, which CORS middleware does not provide for localhost-to-localhost attacks.
- `request.form()` for credential input: requires python-multipart and sends credentials in `application/x-www-form-urlencoded` which is less explicit than JSON. The JSON approach is preferred.

## Runtime State Inventory

Step 2.5 SKIPPED: This is a greenfield addition phase, not a rename/refactor/migration phase. No existing runtime state embeds strings that need updating.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| fastapi | web routes | Yes | 0.115.8 | None (required for `pip install .[web]`) |
| uvicorn | ASGI server | Yes | 0.30.6 | None (required for `pip install .[web]`) |
| jinja2 | templates | Yes | 3.1.4 | None (required for `pip install .[web]`) |
| python-multipart | Form() support | No | 0.0.32 available | JSON body approach does not require it |
| starlette | FastAPI dep / TestClient | Yes | 0.45.3 | N/A — installed as transitive dep |
| pydantic | FastAPI dep | Yes | 2.13.3 | N/A — already installed |
| uvloop | uvicorn[standard] speed | No | N/A (Windows) | h11 (0.16.0) — Windows default, installed |
| httptools | uvicorn[standard] speed | No | N/A (Windows) | h11 — graceful fallback, no error |
| pytest | test suite | Yes | installed | N/A |
| ipaddress | localhost detection | Yes | stdlib | N/A |

**Missing dependencies with no fallback:** None that block execution. `python-multipart` is listed in the `[web]` extra and will be installed by `pip install .[web]`; JSON routes work without it.

**Missing dependencies with fallback:** `uvloop`, `httptools` — platform-incompatible on Windows; uvicorn falls back to h11 automatically.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (installed; asyncio_mode=auto per pytest.ini_options) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_web.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GUI-01 | Web routes only call BotService (MOD-02) | static analysis | `pytest tests/test_web_mod02.py -x -q` | No — Wave 0 |
| GUI-01 | CLI works with fastapi absent (CLI-04) | integration | `pytest tests/test_cli_no_fastapi.py -x -q` | Yes (already passing) |
| GUI-02 | GET /api/items returns BotService.list_items() | unit | `pytest tests/test_web.py::test_items_list -x -q` | No — Wave 0 |
| GUI-02 | POST /api/items calls BotService.add_item() | unit | `pytest tests/test_web.py::test_items_add -x -q` | No — Wave 0 |
| GUI-02 | DELETE /api/items calls BotService.remove_item() | unit | `pytest tests/test_web.py::test_items_remove -x -q` | No — Wave 0 |
| GUI-02 | Web add produces identical DB state as CLI add (SC2) | integration | `pytest tests/test_web.py::test_web_add_item_parity -x -q` | No — Wave 0 |
| GUI-03 | GET /api/credentials never returns a value field | unit | `pytest tests/test_web.py::test_credential_page_no_value_rendered -x -q` | No — Wave 0 |
| GUI-03 | POST /api/credentials response never contains secret (SC3) | unit | `pytest tests/test_web.py::test_credential_set_no_value_in_response -x -q` | No — Wave 0 |
| GUI-03 | POST /api/credentials calls CredentialStore.set() | unit | `pytest tests/test_web.py::test_credential_set_calls_store -x -q` | No — Wave 0 |
| GUI-04 | GET /api/status returns running bool | unit | `pytest tests/test_web.py::test_status_route -x -q` | No — Wave 0 |
| GUI-04 | GET /api/logs returns list of recent lines | unit | `pytest tests/test_web.py::test_logs_route -x -q` | No — Wave 0 |
| GUI-04 | POST /api/bot/start calls BotService.start() | unit | `pytest tests/test_web.py::test_bot_start -x -q` | No — Wave 0 |
| GUI-04 | POST /api/bot/stop calls BotService.stop() | unit | `pytest tests/test_web.py::test_bot_stop -x -q` | No — Wave 0 |
| GUI-05 | Entire test_web.py skips when fastapi absent | skip guard | `pytest tests/test_web.py -x -q` (with fastapi blocked) | No — Wave 0 |
| GUI-05 | test_cli_no_fastapi.py still passes after Phase 10 | regression | `pytest tests/test_cli_no_fastapi.py -x -q` | Yes |
| GUI-06 | Non-localhost --host triggers stderr warning (SC6) | unit | `pytest tests/test_web.py::test_non_local_host_warning -x -q` | No — Wave 0 |
| GUI-06 | Non-localhost triggers in-page banner flag | unit | `pytest tests/test_web.py::test_non_local_banner_flag -x -q` | No — Wave 0 |
| GUI-01/02/03/04 | State-changing POST without matching Origin returns 403 | unit | `pytest tests/test_web.py::test_csrf_rejected -x -q` | No — Wave 0 |
| MOD-02 | web/ package contains no forbidden direct imports | static analysis | `pytest tests/test_web_mod02.py -x -q` | No — Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_web.py tests/test_cli_no_fastapi.py -x -q`
- **Per wave merge:** `pytest -x -q` (full 282+ test suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_web.py` — covers GUI-01..06 (all routes, SC2, SC3, SC6, MOD-02 guard, skip-without-fastapi)
- [ ] `tests/test_web_mod02.py` — AST scan of `web/**/*.py` for forbidden imports (extends test_cli_mod02.py pattern)
- [ ] `web/__init__.py` — create_app factory
- [ ] `web/routes/__init__.py`, `web/routes/api.py`, `web/routes/pages.py` — route stubs
- [ ] `web/security.py` — is_localhost + check_origin
- [ ] `web/log_reader.py` — read_recent_logs
- [ ] `web/config_web.py` — config read/write using ALLOWLIST
- [ ] `web/templates/dashboard.html` — single Jinja2 template
- [ ] `web/static/dashboard.css` — vendored CSS per UI-SPEC
- [ ] `pyproject.toml` — `[project.optional-dependencies] web` section

*(No gaps in existing test infrastructure — pytest, asyncio_mode=auto, conftest.py fixtures are all present)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-user local tool; no auth on localhost |
| V3 Session Management | No | No sessions; stateless API |
| V4 Access Control | Partial | Origin/Host validation on all state-changing routes (check_origin Depends) |
| V5 Input Validation | Yes | ALLOWLIST gate on config keys; key membership check on credentials |
| V6 Cryptography | No | No new crypto; CredentialStore handles secrets at storage layer |
| V7 Error Handling | Yes | Never echo secret values in error responses; {"status":"error","detail":"..."} only |
| V9 Communication | Partial | localhost only by default; explicit warning + user choice for non-local |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Local-malware CSRF (evil JS calls localhost:8000) | Spoofing | `check_origin` Depends: rejects Origin that does not match server host |
| Secret value in response body | Information Disclosure | JSON routes return `{"status":"ok"}` only; SC3 test asserts absence |
| Secret value in server log | Information Disclosure | CRED-06 established: writeLog never logs secrets; log reader returns lines verbatim |
| Cross-site script injection via item name/URL | Tampering | Jinja2 auto-escaping (`{{ var }}` escapes by default); never use `{{ var | safe }}` for user data |
| Config key injection (unknown key written to yaml) | Tampering | ALLOWLIST gate: only known keys accepted; unknown key raises 422 |
| Non-local bind credential exposure | Elevation of Privilege | stderr warning before start; in-page banner; user explicit opt-in |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `python-multipart==0.0.32` is the correct version to pin | Standard Stack | Minor: a newer patch version is available; 0.0.32 is latest confirmed on PyPI |
| A2 | Platforms have no `enabled` field in AppConfig | Pattern 5 | Low: if an enabled field is added later, the config section would need expanding |
| A3 | fastapi, uvicorn, jinja2, python-multipart are legitimate packages | Package Legitimacy | slopcheck unavailable; packages are well-known ecosystem staples |
| A4 | uvicorn 0.30.6 pins are acceptable (latest is 0.49.0) | Standard Stack | Low: newer version has breaking changes unknown; 0.30.6 is what's installed and tested |

**If A4 is a concern:** the planner can upgrade uvicorn to 0.49.0 — no breaking API change in `uvicorn.run(app, host, port)` signature was detected.

## Open Questions (RESOLVED)

1. **RESOLVED — uvicorn pinned to `0.30.6`** (the verified-installed version) in the `[web]` extra, alongside fastapi==0.115.8, jinja2==3.1.4, python-multipart==0.0.32. All confirmed compatible with pydantic==2.13.3 on Python 3.13.

2. **RESOLVED — web Start calls `BotService.start(cvv=None)`** (monitoring-only from the browser). CVV stays a CLI/runtime concern (never collected in the web UI per CONTEXT). `start(cvv=None)` is valid; plugins that need CVV for auto-buy receive None and the CLI path remains the way to supply it.

3. **RESOLVED — Config section scope = notifier toggles only.** AppConfig has no per-platform `enabled` field; the web Config section renders test_mode, logging_level, and the notifier enables (sound, discord.enabled, email.enabled, sms.enabled). No schema field is added (YAGNI). UI-SPEC Section 4's per-platform toggles are intentionally NOT rendered.

3. **Config section: platform enable toggles**
   - What we know: Platforms in AppConfig have no `enabled` field. Only notifiers have `enabled`.
   - What's unclear: CONTEXT.md says "per-platform/notifier enable toggles" — this may imply the planner expects platform enables.
   - Recommendation: Scope config section to notifier enables only (`sound`, `discord.enabled`, `email.enabled`, `sms.enabled`). Flag to user if platform enable toggles are expected — they would require a schema addition.

## Sources

### Primary (HIGH confidence)
- Live Python execution on this machine (2026-06-04) — all code patterns in Code Examples section
- `pip index versions fastapi` — version 0.136.3 latest; 0.115.8 installed [VERIFIED: PyPI registry]
- `pip index versions uvicorn` — version 0.49.0 latest; 0.30.6 installed [VERIFIED: PyPI registry]
- `pip index versions jinja2` — version 3.1.6 latest; 3.1.4 installed [VERIFIED: PyPI registry]
- `pip index versions python-multipart` — version 0.0.32 latest; not installed [VERIFIED: PyPI registry]
- `core/service.py`, `core/credentials.py`, `core/cli/web.py`, `core/cli/config_cmd.py`, `core/cli/items.py` — read directly
- `tests/test_cli_mod02.py`, `tests/test_cli_no_fastapi.py`, `tests/conftest.py` — read directly

### Secondary (MEDIUM confidence)
- FastAPI official docs (app.state, Depends, TestClient patterns) [ASSUMED — consistent with verified live behavior]
- uvicorn docs (uvicorn.run signature) [VERIFIED: live `inspect.signature` call]

### Tertiary (LOW confidence)
- Package age/download statistics — training knowledge, not verified in this session [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified on PyPI, installed versions confirmed by `pip show`
- Architecture: HIGH — create_app factory, app.state injection, CSRF Depends, all verified by live execution
- Pitfalls: HIGH — each pitfall verified by live test or direct code inspection
- Security controls: HIGH — check_origin pattern verified, is_localhost verified all edge cases
- Config section scope: MEDIUM — platform enable missing from schema is verified, but CONTEXT.md phrasing is ambiguous

**Research date:** 2026-06-04
**Valid until:** 2026-07-04 (stable ecosystem; fastapi releases frequently but 0.115.x line is LTS-adjacent)
