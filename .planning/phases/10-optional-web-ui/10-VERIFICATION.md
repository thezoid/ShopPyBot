---
phase: 10-optional-web-ui
verified: 2026-06-04T22:30:00Z
status: human_needed
score: 6/6 must-haves verified (all roadmap SCs pass automated checks)
overrides_applied: 0
human_verification:
  - test: "Open http://127.0.0.1:8000 in a real browser after running `shoppybot web`"
    expected: "All four sections render (Controls/Status, Items, Credentials, Config); CSS loads correctly; no browser JS console errors"
    why_human: "TestClient verifies HTTP/HTML structure but not live browser rendering, CSS paint, or JS execution context"
  - test: "Click Start Bot in the dashboard; observe status and log panel behavior"
    expected: "Status dot flips to green Running label; Start button disables; Recent Logs panel updates within ~2s without a page refresh"
    why_human: "Live JS polling behavior and BotService state transitions cannot be asserted headlessly via TestClient"
  - test: "Run `shoppybot web --host 0.0.0.0` and visit in a browser"
    expected: "Red warning banner renders at the top of the page with the exact text from UI-SPEC; security warning already printed to stderr before serving"
    why_human: "In-page CSS rendering of the banner (color, layout, prominence) cannot be verified without a real browser"
  - test: "Verify on Ubuntu (desktop and headless)"
    expected: "pip install .[web] succeeds; shoppybot web binds and serves; all four dashboard sections render in browser; credential management works"
    why_human: "Cross-platform verification is deferred to Phase 11; current environment is Windows only"
---

# Phase 10: Optional Web UI Verification Report

**Phase Goal:** An optional FastAPI dashboard reachable at `http://127.0.0.1:PORT` lets users manage items, credentials, and bot state through a browser; it installs as an optional extra; credential secrets never leave the server side; binding to any non-localhost address requires explicit opt-in and prints a security warning.
**Verified:** 2026-06-04T22:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | pip install .[web] pins fastapi/uvicorn/jinja2/python-multipart; shoppybot web serves create_app on 127.0.0.1:PORT; dashboard route GET / renders 4 sections | VERIFIED | pyproject.toml `web = ["fastapi==0.115.8", "uvicorn[standard]==0.30.6", "jinja2==3.1.4", "python-multipart==0.0.32"]`; web* in packages.find include; create_app constructs app with StaticFiles + 4 routers; GET / 200 with Controls/Items/Credentials/Config sections confirmed via TestClient |
| 2 | Web items add/remove/list == CLI DB state — both via BotService (SC2 parity) | VERIFIED | `test_web_add_item_parity` passes with real BotService + tmp_data_dir; POST /api/items routes through `request.app.state.svc.add_item`; no direct model imports (MOD-02 AST guard green) |
| 3 | Credential POST stores via CredentialStore.set; secret value NEVER in any response body, rendered HTML, or log | VERIFIED | SC3 confirmed: `SUPER_SECRET_TOKEN_12345` absent from GET / HTML and GET /api/credentials response; no `value` key in credential entries; `test_dashboard_no_credential_value_in_html` passes; NOTE: api.py duplicate route has no SECRET_KEYS gate (see warnings) |
| 4 | Start/Stop call BotService.start()/stop(); status reflects get_status(); /api/logs returns recent lines | VERIFIED | `svc.start()` called with zero positional+keyword args confirmed; `stop` dispatched via `asyncio.get_event_loop().run_in_executor(None, svc.stop)`; GET /api/status returns `{"running": bool}`; GET /api/logs returns `{"logs": [...]}` |
| 5 | fastapi absent: run/setup/items still work; shoppybot web prints "Web UI is not installed. Run: pip install .[web]"; CLI-04 stays green | VERIFIED | `test_cli_no_fastapi.py` passes (2/2); `handle_web` top-level imports only `sys`; ImportError guard prints exact string; `web.py` confirmed no module-level fastapi import |
| 6 | Non-localhost bind prints security warning to stderr before serving; is_localhost loopback detection correct; Origin/Host check returns 403 on state-changing POSTs | VERIFIED | `is_localhost` matrix passes all 8 parametrized cases (127.0.0.1/localhost/::1/[::1]:8000/127.0.0.1:8000 True; 0.0.0.0/192.168.1.5/10.0.0.1 False); warning text confirmed: "WARNING: ShopPyBot dashboard is binding to a non-local interface..."; POST /api/items with origin http://evil.com returns 403 |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | [web] extra with exact-pinned deps; web* in packages.find | VERIFIED | All 4 packages pinned; `"web*"` in include list |
| `web/__init__.py` | `create_app(svc, is_non_local=False)` factory | VERIFIED | Constructs FastAPI app, sets app.state.svc + is_non_local, mounts StaticFiles, includes 4 routers |
| `web/security.py` | `is_localhost` + `check_origin` Depends | VERIFIED | Both functions present; is_localhost handles IPv4/IPv6/port forms; check_origin raises HTTP 403 on cross-origin |
| `web/log_reader.py` | `read_recent_logs(n=50)` with `%Y%B%d` format | VERIFIED | Uses `datetime.datetime.now().strftime("%Y%B%d") + ".log"`; returns [] if absent |
| `web/config_web.py` | WEB_ALLOWLIST + read/write reusing config_cmd | VERIFIED | `from core.cli.config_cmd import ALLOWLIST, _atomic_yaml_write`; no duplication |
| `web/routes/api.py` | Items + bot-control + status + logs routes | VERIFIED | All 7 endpoints present; all mutating routes have `Depends(check_origin)`; NOTE: also contains duplicate credential routes (see warnings) |
| `web/routes/credentials.py` | GET + POST credential routes; status-only | VERIFIED | Implements SECRET_KEYS gate and is_set-only response; however api.py routes are registered first and win (see warnings) |
| `web/routes/config.py` | GET + POST /config; WEB_ALLOWLIST gate | VERIFIED | Imports from web.config_web; unknown key returns 422 |
| `web/routes/pages.py` | GET / renders dashboard.html via Jinja2Templates | VERIFIED | TemplateResponse passes is_non_local, status, items context; no credential values in context |
| `web/templates/dashboard.html` | 4 sections; banner; polling; forms; no \| safe | VERIFIED | All 4 sections render; setInterval polls /api/status and /api/logs at 2000ms; banner conditional on is_non_local; no `\| safe` filter for user data |
| `web/static/dashboard.css` | UI-SPEC tokens; no CDN/external fonts | VERIFIED | #2563eb/#dc2626/#fee2e2 present; max-width: 900px; min-height: 36px; comment confirms no @import url(); no external font sources |
| `core/cli/web.py` | handle_web body; lazy import; --host/--port | VERIFIED | Only `sys` at module level; lazy `from web import create_app` inside function body; --host/--port args confirmed |
| `tests/test_web_mod02.py` | AST guard scanning web/**/*.py via rglob | VERIFIED | Uses rglob("*.py"); checks for orchestrator/registry/models/sync functions; passes |
| All 8 test_web_*.py | importorskip("fastapi") guard at top | VERIFIED | All 8 files begin with `import pytest` then `pytest.importorskip("fastapi")` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `core/cli/web.py:handle_web` | `web.create_app` | lazy import inside function body | VERIFIED | `from web import create_app` inside function body only; no module-level import |
| `web/__init__.py:create_app` | `web.routes.api/credentials/config/pages routers` | `include_router` inside factory | VERIFIED | All 4 routers included; api/credentials/config under `/api` prefix; pages with no prefix |
| `web/config_web.py` | `core.cli.config_cmd` | `from core.cli.config_cmd import ALLOWLIST, _atomic_yaml_write` | VERIFIED | Import confirmed; no duplicate ALLOWLIST or atomic writer |
| `web/routes/api.py` | `BotService via request.app.state.svc` | `request.app.state.svc` accessor | VERIFIED | All routes access svc only via app.state |
| `web/routes/api.py mutating routes` | `web.security.check_origin` | `dependencies=[Depends(check_origin)]` | VERIFIED | POST /items, DELETE /items/{b64}, POST /bot/start, POST /bot/stop all have the dependency |
| `web/routes/api.py GET /logs` | `web.log_reader.read_recent_logs` | import + call | VERIFIED | `from web.log_reader import read_recent_logs` at top of api.py; called with n=50 |
| `web/routes/pages.py` | `dashboard.html via Jinja2Templates` | TemplateResponse | VERIFIED | `templates.TemplateResponse(request, "dashboard.html", {...})` |
| `dashboard.html` | `/api/status + /api/logs` | inline fetch + setInterval | VERIFIED | `setInterval(pollStatus, POLL_MS)` and `setInterval(pollLogs, POLL_MS)` at 2000ms |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `dashboard.html` | `items` (SSR) | `svc.list_items()` in pages.py | Yes (BotService delegates to DB) | FLOWING |
| `dashboard.html` | `status` (SSR) | `svc.get_status()` in pages.py | Yes (BotService.get_status returns live state) | FLOWING |
| `dashboard.html` | credentials section | JS fetches `/api/credentials` on load | Yes (get_store().get per key) | FLOWING |
| `dashboard.html` | config section | JS fetches `/api/config` on load | Yes (svc.get_config() via read_web_config) | FLOWING |
| `dashboard.html` | log panel | JS polls `/api/logs` every 2000ms | Yes (read_recent_logs reads today's log file) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| create_app returns FastAPI instance | `from web import create_app; from unittest.mock import MagicMock; create_app(MagicMock())` | FastAPI instance returned | PASS |
| is_localhost loopback detection | 8-case parametrized test | All 8 cases correct | PASS |
| Non-local warning text on stderr | handle_web with host=0.0.0.0 (uvicorn mocked) | "WARNING: ShopPyBot dashboard is binding to a non-local interface..." | PASS |
| CSRF 403 on cross-origin POST | POST /api/items with origin http://evil.com | 403 | PASS |
| Secret absent from GET / HTML | GET / with store returning SUPER_SECRET_TOKEN_12345 | Secret absent from response.text | PASS |
| SC2 parity: web add == CLI list | real BotService + tmp_data_dir | Row visible in svc.list_items() after web POST | PASS |
| BotService.start called with zero args | POST /api/bot/start with mock svc | `svc.start.assert_called_once_with()` passes | PASS |
| shoppybot web prints correct no-fastapi message | sys.modules['fastapi'] = None, call handle_web | "Web UI is not installed. Run: pip install .[web]" on stderr, return 1 | PASS |
| Full test suite | `python -m pytest -q` | 322 passed, 1 xpassed, 0 failed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| GUI-01 | 10-04 | Optional local web UI via `shoppybot web`, served on localhost; nothing CLI cannot do | SATISFIED | create_app + handle_web + pages route confirmed; config scope limited to CLI ALLOWLIST + notifier toggles |
| GUI-02 | 10-02 | Manage tracked items through UI via BotService | SATISFIED | /api/items GET/POST/DELETE all delegate to request.app.state.svc; SC2 parity test green |
| GUI-03 | 10-03 | Manage credentials via UI; secrets never plaintext to browser/localStorage/disk | SATISFIED | GET returns name+is_set only; POST returns status only; SC3 tests green (with caveat on api.py duplicate route — see warnings) |
| GUI-04 | 10-02 | Start/stop bot and view live status + logs from UI | SATISFIED | /api/bot/start, /api/bot/stop, /api/status, /api/logs all implemented and tested |
| GUI-05 | 10-01 | Web UI is an optional extra (pip install .[web]); core + CLI work without FastAPI | SATISFIED | test_cli_no_fastapi.py passes; module-level fastapi import absent from core/cli/web.py; importorskip guard in all 8 web test files |
| GUI-06 | 10-01 | Binds to localhost by default; non-localhost requires explicit opt-in + security warning | SATISFIED | Default host=127.0.0.1; is_localhost detection correct; stderr warning fires for non-local; in-page banner renders when is_non_local=True |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `web/routes/api.py` lines 106-124 | Duplicate GET+POST /credentials routes registered before credentials.py router; api.py POST has no SECRET_KEYS validation gate | WARNING | T-10-11 mitigation (key injection gate) bypassed at runtime — any string key can be written to CredentialStore via the winning api.py route; however SC3 output guarantee (no secret value in response) is unaffected |

**Debt markers:** None found (no TBD/FIXME/XXX in modified files).

### Human Verification Required

#### 1. Live Dashboard Browser Render

**Test:** Run `pip install .[web]` then `shoppybot web`. Open http://127.0.0.1:8000 in a real browser.
**Expected:** All four sections render (Controls/Status, Items, Credentials, Config); CSS loads (cards, accent blue buttons, spacing match UI-SPEC); no JS console errors.
**Why human:** TestClient verifies HTTP and HTML structure but not live browser rendering, CSS paint, or JS execution in a real browser context.

#### 2. Live Start/Stop + Log Polling

**Test:** With the dashboard open in a browser, click "Start Bot"; observe the status indicator and log panel.
**Expected:** Status dot flips to green "Running"; Start button disables; Stop button enables; Recent Logs panel updates within approximately 2 seconds without a page refresh. Click "Stop Bot" and confirm status returns to "Stopped".
**Why human:** JS polling behavior and live BotService state transitions cannot be verified headlessly via TestClient — setInterval is present in the template but actual DOM updates require a real browser runtime.

#### 3. Non-Localhost In-Page Banner Visual Check

**Test:** Run `shoppybot web --host 0.0.0.0`. Confirm stderr warning prints before the server starts. Open the dashboard in a browser.
**Expected:** The red warning banner renders prominently at the top of the page with the exact UI-SPEC copy: "Warning: this dashboard is reachable beyond localhost. Credential management is exposed on a non-local interface. Use only on a trusted private network." Background #fee2e2 with #dc2626 text is visually prominent.
**Why human:** CSS rendering (color, layout prominence) cannot be verified without a real browser.

#### 4. Ubuntu Verification (Deferred to Phase 11)

**Test:** On Ubuntu (desktop and headless), run `pip install .[web]`, then `shoppybot web`. Open dashboard.
**Expected:** Server binds, dashboard renders, all four sections work, credentials section shows Set/Not set status.
**Why human:** Current environment is Windows only. Phase 11 is the designated cross-platform verification phase.

### Warnings Summary

**Duplicate Credential Routes (api.py + credentials.py):** `web/__init__.py` includes both `api_router` and `credentials_router` under the `/api` prefix. `api.py` defines GET and POST `/credentials` routes and is included first — these win over `credentials.py`'s equivalents. The `api.py` POST route has no `SECRET_KEYS` membership check, meaning any string key (including non-canonical keys) can be written to the CredentialStore via POST /api/credentials. The `credentials.py` route's validation gate is dead code. SC3's output guarantee (secret value never in response body) is unaffected — both implementations return `{"status":"ok"}` with no value. The risk is key injection: an attacker with localhost access who can bypass the CSRF Origin check could write to arbitrary CredentialStore keys.

This is a WARNING, not a BLOCKER, because:
- SC3 (no secret in response) is fully satisfied
- The CSRF Origin check (check_origin) still applies to the winning route
- All tests pass including the SC3 leak assertions
- The exploit requires localhost access (attacker must already be on the machine)

---

_Verified: 2026-06-04T22:30:00Z_
_Verifier: Claude (gsd-verifier)_
