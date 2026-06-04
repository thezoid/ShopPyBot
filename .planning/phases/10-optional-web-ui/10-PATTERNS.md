# Phase 10: Optional Web UI - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 13 new/modified files
**Analogs found:** 11 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `web/__init__.py` | provider (app factory) | request-response | `core/cli/web.py` (lazy-import stub) | role-match |
| `web/routes/api.py` | controller | request-response | `core/cli/items.py` + `core/cli/config_cmd.py` | role-match |
| `web/routes/pages.py` | controller | request-response | `core/cli/items.py` (handle pattern) | partial |
| `web/routes/__init__.py` | config | — | `core/cli/__init__.py` | structural |
| `web/security.py` | middleware/utility | request-response | `core/cli/web.py` (import guard pattern) | partial |
| `web/log_reader.py` | utility | file-I/O | `logger.py` (log file naming) | partial |
| `web/config_web.py` | service | CRUD | `core/cli/config_cmd.py` | exact |
| `web/templates/dashboard.html` | template | request-response | none (greenfield HTML) | none |
| `web/static/dashboard.css` | config/static | — | none (greenfield CSS) | none |
| `core/cli/web.py` | controller/provider | request-response | itself (Phase 9 stub to fill) | self |
| `pyproject.toml` | config | — | itself (add `[web]` extra) | self |
| `tests/test_web.py` | test | request-response | `tests/test_cli_no_fastapi.py` + `tests/test_cli_mod02.py` | role-match |
| `tests/test_web_mod02.py` | test (static analysis) | — | `tests/test_cli_mod02.py` | exact |

## Pattern Assignments

### `web/__init__.py` (provider, request-response)

**Analog:** `core/cli/web.py` (lazy-import guard), `core/cli/config_cmd.py` (`_atomic_yaml_write` import style)

**Imports pattern** — all fastapi imports live only inside this package; never at module top of any CLI file:
```python
# web/__init__.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

_HERE = Path(__file__).parent
```

**Core factory pattern** (from RESEARCH verified skeleton):
```python
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

**Key constraint:** `docs_url=None, redoc_url=None` disables the auto-generated OpenAPI UI (not needed for a local admin tool; reduces attack surface).

---

### `web/routes/api.py` (controller, request-response)

**Analog:** `core/cli/items.py` (lines 31-57) for BotService call pattern; `core/cli/config_cmd.py` (lines 74-105) for config ALLOWLIST gate

**BotService call pattern** — copy the exact BotService method signatures from `core/cli/items.py`:

From `core/cli/items.py` lines 31-56:
```python
# The three BotService calls that web item routes must mirror exactly:
svc.list_items()                              # returns list of 5-tuples
svc.add_item(name, link, auto_buy, quantity)  # no return value
svc.remove_item(url)                          # no return value
```

**Route handler shape** — modeled on `core/cli/items.py` handle_* functions (each does one BotService call, returns immediately):
```python
# Parallel: handle_items_list -> GET /api/items
# handle_items_add  -> POST /api/items
# handle_items_remove -> DELETE /api/items/{...}

@router.get("/items")
async def list_items(request: Request):
    rows = request.app.state.svc.list_items()
    return JSONResponse({"items": [...]})   # serialize 5-tuples to dicts

@router.post("/items", dependencies=[Depends(check_origin)])
async def add_item(request: Request):
    body = await request.json()
    request.app.state.svc.add_item(
        body["name"], body["link"], body["auto_buy"], body["quantity"]
    )
    return JSONResponse({"status": "ok"})

@router.delete("/items/{link_b64}", dependencies=[Depends(check_origin)])
async def remove_item(link_b64: str, request: Request):
    import base64
    link = base64.urlsafe_b64decode(link_b64.encode()).decode()
    request.app.state.svc.remove_item(link)
    return JSONResponse({"status": "ok"})
```

**Config ALLOWLIST gate** — mirror `core/cli/config_cmd.py` lines 17-20 and 82-88:
```python
# From core/cli/config_cmd.py lines 17-20:
ALLOWLIST: dict[str, tuple[str, type]] = {
    "test_mode": ("debug", bool),
    "logging_level": ("debug", int),
}

# Gate pattern from lines 82-88:
if key not in ALLOWLIST:
    # return 422, not print to stderr
    raise HTTPException(status_code=422, detail=f"Key not in allowlist")
```

**Credential route — secret never in response** — `core/credentials.py` lines 94-99 shows the `set()` API:
```python
# GET /api/credentials: only name + is_set, never the value
store = get_store()
creds = [
    {"name": k, "is_set": store.get(k) is not None}
    for k in SECRET_KEYS
]
return JSONResponse({"credentials": creds})

# POST /api/credentials: call set(), return status only
store.set(body["key"], body["value"])
return JSONResponse({"status": "ok"})   # value NEVER echoed
```

**CSRF dependency** — apply `dependencies=[Depends(check_origin)]` to every state-changing route (POST/DELETE). Pattern from RESEARCH:
```python
from web.security import check_origin
from fastapi import Depends

# Every mutating route declaration:
@router.post("/bot/start", dependencies=[Depends(check_origin)])
@router.post("/bot/stop",  dependencies=[Depends(check_origin)])
@router.post("/items",     dependencies=[Depends(check_origin)])
@router.delete("/items/{link_b64}", dependencies=[Depends(check_origin)])
@router.post("/config",    dependencies=[Depends(check_origin)])
@router.post("/credentials", dependencies=[Depends(check_origin)])
```

---

### `web/routes/pages.py` (controller, request-response)

**Analog:** `core/cli/items.py` handle_items_list (minimal: reads svc, formats output, returns)

**Core pattern** — single GET / route that renders the Jinja2 template with initial data:
```python
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

@router.get("/")
async def dashboard(request: Request):
    svc = request.app.state.svc
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "is_non_local": request.app.state.is_non_local,
        "status": svc.get_status(),
        "items": svc.list_items(),
    })
```

**Key constraint:** never pass credential values or config secrets into template context.

---

### `web/security.py` (middleware/utility, request-response)

**Analog:** `core/cli/web.py` lines 16-23 (lazy ImportError guard as the closest existing boundary-check pattern); RESEARCH verified code

**Full implementation** (short file, ~35 lines — copy from RESEARCH Pattern 2 and 3 verbatim):
```python
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
    if hostname != server_host and hostname not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="CSRF: origin rejected")
```

**No analog in codebase** for the localhost-detection logic itself; uses stdlib `ipaddress` module.

---

### `web/log_reader.py` (utility, file-I/O)

**Analog:** `logger.py` lines 40-47 (the exact log file path construction and format string)

**Critical pattern from `logger.py` line 45** — the strftime format that names log files:
```python
# From logger.py line 45 -- MUST use this exact format string in log_reader.py:
log_file_path = os.path.join(log_dir, f"{datetime.now().strftime('%Y%B%d')}.log")
# Produces e.g. "2026June04.log" (title-case month from %B directive)
```

**Log reader implementation** — mirrors the file path convention:
```python
import datetime
import pathlib

_LOG_DIR = pathlib.Path(__file__).parent.parent / "logs"

def read_recent_logs(n: int = 50) -> list[str]:
    fname = datetime.datetime.now().strftime("%Y%B%d") + ".log"
    log_path = _LOG_DIR / fname
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return text.splitlines()[-n:]
```

**Pitfall:** using `%Y%m%d` or `%Y-%m-%d` produces a different filename than `logger.py` writes. Match `%Y%B%d` exactly.

---

### `web/config_web.py` (service, CRUD)

**Analog:** `core/cli/config_cmd.py` (exact — this file mirrors it)

**Full analog:** `core/cli/config_cmd.py`

**ALLOWLIST + _atomic_yaml_write** — import directly from config_cmd rather than duplicating:
```python
# web/config_web.py -- thin wrapper; re-use the CLI's ALLOWLIST and writer
from core.cli.config_cmd import ALLOWLIST, _atomic_yaml_write
from core.config_schema import _DEFAULT_YAML_PATH
import yaml

# Extended allowlist for notifier enable toggles (RESEARCH Pattern 5):
WEB_ALLOWLIST = {
    **ALLOWLIST,   # test_mode, logging_level
    # Notifier enables -- these are nested paths, need special handling:
    "notifications.sound":           ("notifications", "sound", bool),
    "notifications.discord.enabled": ("notifications", "discord", bool),
    "notifications.email.enabled":   ("notifications", "email", bool),
    "notifications.sms.enabled":     ("notifications", "sms", bool),
}
```

**Atomic write pattern from `core/cli/config_cmd.py` lines 44-63** — call `_atomic_yaml_write` directly:
```python
# From core/cli/config_cmd.py lines 97-104 -- copy the read-modify-write pattern:
try:
    raw = _DEFAULT_YAML_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    raw = ""
data = yaml.safe_load(raw) or {}
data.setdefault(section, {})[key] = value
_atomic_yaml_write(_DEFAULT_YAML_PATH, data)
```

---

### `core/cli/web.py` (controller/provider, request-response)

**Analog:** itself (Phase 9 stub, lines 10-26) + RESEARCH verified handle_web body

**Existing stub to preserve** (`core/cli/web.py` lines 1-8 — module-level imports MUST remain only `sys`):
```python
# Lines 1-8 of core/cli/web.py -- keep exactly as-is:
"""handle_web: Phase 10 stub with lazy fastapi import seam (CLI-04)."""
import sys

def handle_web(args, svc=None) -> int:
    try:
        import fastapi  # noqa: F401 -- lazy; never at module level
    ...
```

**Replacement body** (RESEARCH Pattern — fill in from line 17 forward):
```python
def handle_web(args, svc=None) -> int:
    try:
        from web import create_app          # lazy -- only inside function
    except ImportError:
        print("FastAPI is not installed. Run: pip install .[web]", file=sys.stderr)
        return 1

    import uvicorn
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

**Key constraint:** `uvicorn` and `from web import create_app` must stay inside the function body, never at module top. The existing `test_cli_no_fastapi.py::test_run_works_without_fastapi` (`tests/test_cli_no_fastapi.py` lines 20-36) will catch any top-level leak.

---

### `pyproject.toml` (config)

**Analog:** itself (existing `[project]` section, lines 1-21)

**Addition needed** — insert after line 10 (`requires-python = ">=3.11"`):
```toml
[project.optional-dependencies]
web = [
    "fastapi==0.115.8",
    "uvicorn[standard]==0.30.6",
    "jinja2==3.1.4",
    "python-multipart==0.0.32",
]
```

**Also required in `[tool.setuptools.packages.find]`** — the `web` package must be discoverable. Current line 13:
```toml
include = ["core*", "plugins*", "notifications*"]
```
Must become:
```toml
include = ["core*", "plugins*", "notifications*", "web*"]
```

---

### `tests/test_web.py` (test, request-response)

**Analog:** `tests/test_cli_no_fastapi.py` (importorskip / sys.modules pattern) + `tests/conftest.py` (tmp_data_dir fixture + MagicMock patterns)

**Skip guard pattern** — copy from `tests/test_cli_no_fastapi.py` lines 1-6 adapted:
```python
# tests/test_web.py lines 1-6
import pytest
pytest.importorskip("fastapi")   # skips entire module if fastapi absent

from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from web import create_app
```

**Fixture pattern** — modeled on `tests/conftest.py` lines 53-58 (`tmp_data_dir`) and `tests/test_cli_no_fastapi.py` mock pattern:
```python
@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False}
    svc.list_items.return_value = []
    return svc

@pytest.fixture
def client(mock_svc):
    return TestClient(create_app(mock_svc))
```

**SC3 credential-leak assertion** — use `assert secret_value not in resp.text` (from RESEARCH Code Examples):
```python
def test_credential_set_no_value_in_response(client):
    secret_value = "super-secret-password-12345"
    resp = client.post(
        "/api/credentials",
        json={"key": "AMZ_EMAIL", "value": secret_value},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert resp.status_code == 200
    assert secret_value not in resp.text
    assert resp.json()["status"] == "ok"
```

**SC2 parity assertion** — use real `BotService` + `tmp_data_dir` (from `tests/conftest.py` lines 53-58):
```python
def test_web_add_item_parity(tmp_data_dir):
    from core.service import BotService
    svc = BotService()
    client = TestClient(create_app(svc))
    client.post(
        "/api/items",
        json={"name": "Widget", "link": "https://example.com/w",
              "auto_buy": False, "quantity": 1},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    rows = svc.list_items()
    assert any(r[1] == "https://example.com/w" for r in rows)
```

**SC6 non-localhost warning** — capture stderr, call `handle_web` with a non-local host:
```python
def test_non_local_host_warning(capsys, monkeypatch):
    import uvicorn
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: None)
    from core.cli.web import handle_web
    from unittest.mock import MagicMock
    handle_web(type("args", (), {"host": "0.0.0.0", "port": 8000})(), MagicMock())
    assert "WARNING" in capsys.readouterr().err
```

---

### `tests/test_web_mod02.py` (test, static analysis)

**Analog:** `tests/test_cli_mod02.py` (exact — copy the AST scan, change the directory)

**Full pattern from `tests/test_cli_mod02.py`** lines 1-47 — change `cli_dir` to scan `web/`:
```python
# tests/test_web_mod02.py -- copy of test_cli_mod02.py with web/ path
import ast
from pathlib import Path

def test_web_no_direct_model_imports():
    forbidden_names = {
        "orchestrator",
        "registry",
        "models",
        "add_items_sync",
        "get_items_sync",
        "remove_item_sync",
        "add_items",
    }
    web_dir = Path(__file__).parent.parent / "web"
    violations: list[str] = []
    for py_file in sorted(web_dir.rglob("*.py")):   # rglob covers routes/ subdir
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_names:
                        violations.append(f"{py_file.name}: imports {alias.name!r}")
            elif isinstance(node, ast.ImportFrom):
                if node.module in forbidden_names or (
                    node.names and any(a.name in forbidden_names for a in node.names)
                ):
                    violations.append(
                        f"{py_file.name}: from-imports forbidden name "
                        f"(module={node.module!r})"
                    )
    assert not violations, "\n".join(violations)
```

**Key delta from `test_cli_mod02.py`:** uses `rglob("*.py")` instead of `glob("*.py")` to catch `web/routes/api.py` and `web/routes/pages.py` inside the `routes/` subdirectory.

---

### `web/templates/dashboard.html` (template)

**No analog in codebase** — greenfield Jinja2 template.

**Integration contracts** (from UI-SPEC):
- Renders `{{ is_non_local }}` flag from `app.state` for the non-local warning banner (background `#fee2e2`, border `#dc2626`, text `#dc2626`, padding 12px 16px)
- Four section cards in order: Controls/Status, Items, Credentials, Config
- Inline `<script>` polls `/api/status` and `/api/logs` every 2000ms via `fetch`
- All forms submit via `fetch` (no `action=` / full page reload)
- Credential inputs are `type="password"` with placeholder "Enter new value" — never pre-filled
- Jinja2 auto-escaping is active by default for `.html` files; never use `| safe` for user-controlled values

---

### `web/static/dashboard.css` (static)

**No analog in codebase** — greenfield vendored CSS.

**Design contract** (from UI-SPEC):
- System font stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- Page max-width 900px centered; full-width with 16px padding below 640px
- Spacing tokens: xs=4px sm=8px md=16px lg=24px xl=32px 2xl=48px
- Color palette: bg=`#f5f5f5`, card=`#ffffff`, accent=`#2563eb`, destructive=`#dc2626`, border=`#d1d5db`, text-primary=`#111827`, text-secondary=`#6b7280`
- Section cards: white bg, 1px `#d1d5db` border, 4px border-radius, 24px inner padding
- No CDN references, no `@import url()`, no external font loads

## Shared Patterns

### BotService Access in Routes

**Source:** `core/service.py` lines 46-56 (read-only accessors), `core/cli/items.py` lines 31-56 (caller pattern)
**Apply to:** all route handlers in `web/routes/api.py` and `web/routes/pages.py`

```python
# Canonical access inside any route handler:
svc = request.app.state.svc   # never use a module-level global
result = svc.list_items()     # returns list of 5-tuples (name, link, auto_buy, qty, purchased)
svc.add_item(name, link, auto_buy, quantity)
svc.remove_item(link)
svc.get_status()              # returns {"running": bool}
svc.start(cvv=None)           # web UI passes no CVV -- locked decision
svc.stop()
```

### CSRF Depends on All Mutating Routes

**Source:** `web/security.py` (new file; pattern from RESEARCH Pattern 2, verified live)
**Apply to:** every POST and DELETE route in `web/routes/api.py`

```python
from fastapi import Depends
from web.security import check_origin
# Usage:
@router.post("/items", dependencies=[Depends(check_origin)])
```

### Pytest Skip Guard (fastapi optional)

**Source:** `tests/test_cli_no_fastapi.py` lines 1-6
**Apply to:** first two lines of `tests/test_web.py` and `tests/test_web_mod02.py`

```python
import pytest
pytest.importorskip("fastapi")
```

### Atomic Config Write

**Source:** `core/cli/config_cmd.py` lines 44-63 (`_atomic_yaml_write`)
**Apply to:** `web/config_web.py` POST handler — import and call directly, do not duplicate

```python
from core.cli.config_cmd import _atomic_yaml_write, ALLOWLIST
```

### JSON-Only Responses for State Changes

**Source:** `core/cli/items.py` (returns exit codes, not data) adapted for HTTP
**Apply to:** all POST/DELETE handlers in `web/routes/api.py`

```python
# Success:
return JSONResponse({"status": "ok"})
# Error:
return JSONResponse({"status": "error", "detail": "..."}, status_code=...)
# NEVER include secret values, even in error context
```

### Log File Naming

**Source:** `logger.py` line 45
**Apply to:** `web/log_reader.py`

```python
# MUST match logger.py exactly:
datetime.datetime.now().strftime("%Y%B%d") + ".log"
# Produces e.g. "2026June04.log"
```

### tmp_data_dir Fixture

**Source:** `tests/conftest.py` lines 53-58
**Apply to:** all integration tests in `tests/test_web.py` that instantiate a real `BotService`

```python
# Already in conftest.py -- just use the fixture:
def test_something(tmp_data_dir):
    from core.service import BotService
    svc = BotService()   # DB is redirected to tmp_path
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `web/templates/dashboard.html` | template | request-response | No Jinja2 templates exist in the codebase; use UI-SPEC section contracts directly |
| `web/static/dashboard.css` | static | — | No CSS exists in the codebase; use UI-SPEC color/spacing/typography tables directly |

## Metadata

**Analog search scope:** `core/cli/`, `core/`, `tests/`, `logger.py`, `pyproject.toml`
**Files scanned:** 13 source files read directly
**Pattern extraction date:** 2026-06-04
