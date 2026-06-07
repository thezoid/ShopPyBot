---
phase: 10-optional-web-ui
plan: "01"
subsystem: web-ui
tags: [fastapi, web, optional-extra, security, cli-04, gui-05, gui-06]
dependency_graph:
  requires: [core/cli/web.py, core/service.py, core/credentials.py, core/cli/config_cmd.py]
  provides: [web/__init__.py, web/security.py, web/log_reader.py, web/config_web.py, web/routes/]
  affects: [pyproject.toml, core/cli/__init__.py, core/cli/web.py]
tech_stack:
  added: [fastapi==0.115.8, uvicorn[standard]==0.30.6, jinja2==3.1.4, python-multipart==0.0.32]
  patterns: [app-factory, lazy-import, csrf-depends, importorskip-skip-guard, atomic-yaml-write]
key_files:
  created:
    - web/__init__.py
    - web/security.py
    - web/log_reader.py
    - web/config_web.py
    - web/routes/__init__.py
    - web/routes/api.py
    - web/routes/pages.py
    - web/routes/credentials.py
    - web/routes/config.py
    - web/templates/dashboard.html
    - web/static/dashboard.css
    - tests/test_web_app.py
    - tests/test_web_security.py
    - tests/test_web_items.py
    - tests/test_web_controls.py
    - tests/test_web_credentials.py
    - tests/test_web_config.py
    - tests/test_web_dashboard.py
    - tests/test_web_mod02.py
  modified:
    - pyproject.toml
    - core/cli/web.py
    - core/cli/__init__.py
decisions:
  - "Route imports (api/credentials/config/pages) are deferred inside create_app() body to avoid circular import; fastapi stays out of module top-level"
  - "All web/ route bodies implemented in api.py rather than 4 separate routers; stub routers for credentials.py and config.py remain empty for future plans"
  - "TemplateResponse uses new Starlette API: TemplateResponse(request, name, context) to avoid DeprecationWarning"
  - "SC2 parity test calls initialize_db() explicitly before BotService() since tmp_data_dir only redirects DB_PATH"
metrics:
  duration: "~15 min"
  completed: "2026-06-04"
  tasks: 3
  files: 21
requirements: [GUI-05, GUI-06]
---

# Phase 10 Plan 01: Web Package Skeleton + [web] Extra + Security/Log/Config + handle_web + Wave 0 Tests Summary

Optional FastAPI web dashboard foundation: pyproject [web] extra, lazy-imported web/ package with create_app factory, is_localhost/check_origin security layer, log reader, config-web helper, filled handle_web CLI body, and 8 Wave 0 skip-guarded test files. 320 tests green (282 baseline + 38 new).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wave 0 skip-guarded test scaffold (8 files) | e1eae9a | tests/test_web_*.py (8 files) |
| 2 | pyproject [web] extra + web/ skeleton + security + log_reader + config_web | 9eab60b | pyproject.toml, web/ (11 files) |
| 3 | Fill handle_web body + --host/--port to web subparser | 1d9752f | core/cli/web.py, core/cli/__init__.py |
| fix | SC2 DB init + config mock + Jinja2 TemplateResponse signature | 20f64ea | 3 files |

## What Was Built

**[web] optional extra:** `pyproject.toml` now carries `[project.optional-dependencies] web` with exact-pinned fastapi==0.115.8, uvicorn[standard]==0.30.6, jinja2==3.1.4, python-multipart==0.0.32. The `web*` package is added to setuptools `packages.find include`.

**web/ package:** `create_app(svc, is_non_local=False)` factory builds a FastAPI app with `app.state.svc`, StaticFiles at /static, and all four routers included. All fastapi imports live inside web/ files only (CLI-04 invariant).

**Security layer:** `web/security.py` provides `is_localhost()` (handles IPv4:port, bare/bracketed IPv6, `ipaddress.ip_address.is_loopback`) and `check_origin()` FastAPI Depends rejecting cross-origin POSTs with 403.

**Log reader:** `web/log_reader.py` reads last N lines from today's log file using `%Y%B%d` format matching `logger.py`.

**Config helper:** `web/config_web.py` extends CLI `ALLOWLIST` with four notifier toggles (sound, discord.enabled, email.enabled, sms.enabled). Reuses `_atomic_yaml_write` and `ALLOWLIST` from `core/cli/config_cmd.py` directly.

**handle_web:** Lazy `from web import create_app` inside function body. ImportError message exactly: "Web UI is not installed. Run: pip install .[web]". Non-local --host prints WARNING to stderr before uvicorn.run. --host/--port args added to web subparser.

**Dashboard:** Single-page Jinja2 template with all 4 sections (Controls, Items, Credentials, Config), inline JS polling (2s), all forms submit via fetch. Vendored CSS (system font, no CDN).

**Wave 0 test scaffold:** All 8 test files open with `pytest.importorskip("fastapi")`. Test fixtures use lazy imports inside functions to allow collection before web/ existed. MOD-02 guard uses rglob to scan web/routes/. SC2 parity, SC3 credential-leak, SC6 non-local warning, CSRF 403 tests all pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SC2 parity test missing initialize_db() call**
- Found during: Task 1 (test), discovered during full suite run
- Issue: `test_web_add_item_parity` used real BotService with tmp_data_dir fixture but did not call `initialize_db()`, causing `sqlite3.OperationalError: no such table: items`
- Fix: Added `initialize_db(delete=True)` before `BotService()` instantiation in the test
- Files modified: tests/test_web_items.py
- Commit: 20f64ea

**2. [Rule 1 - Bug] test_web_config mock_svc missing JSON-serializable config**
- Found during: Full suite run
- Issue: `read_web_config(svc)` called `svc.get_config().debug.test_mode` which returned a MagicMock — not JSON serializable
- Fix: Configured `mock_svc.get_config.return_value` with explicit bool/int values in the fixture
- Files modified: tests/test_web_config.py
- Commit: 20f64ea

**3. [Rule 1 - Bug] Jinja2 TemplateResponse deprecated API**
- Found during: Full suite run (DeprecationWarning emitted)
- Issue: `TemplateResponse(name, {"request": request, ...})` uses old Starlette API
- Fix: Changed to `TemplateResponse(request, name, context)` per current Starlette API
- Files modified: web/routes/pages.py
- Commit: 20f64ea

**4. [Sequencing note] Task 2 verify required Task 3 work**
- `test_non_local_host_warning` in test_web_security.py tests handle_web behavior. Task 2's verify spec included this test but the body was Task 3's work. Resolution: Task 3 was completed before Task 2 was verified as green. Both were committed separately as intended.

**5. [Design choice] Route bodies implemented in api.py rather than deferred**
- Plan said "stub routes with no endpoints". However, test_web_security.py requires POST /api/items to exist for the CSRF 403 test. Since the plan's own verify required those tests to pass, full route bodies were implemented in api.py. credentials.py and config.py stubs remain empty (future plans).

## Known Stubs

- `web/routes/credentials.py` - empty router stub; credential routes are in api.py (Plan 04 will move/extend)
- `web/routes/config.py` - empty router stub; config routes are in api.py (Plan 05 will move/extend)
- Dashboard template credentials and config sections populated by JS fetch on load (not SSR initial data)

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: information-disclosure | web/routes/api.py | GET /api/credentials calls get_store().get(k) to check is_set; value is only tested for None, never included in response |

## Self-Check: PASSED

Files exist:
- web/__init__.py: FOUND
- web/security.py: FOUND
- web/log_reader.py: FOUND
- web/config_web.py: FOUND
- web/routes/api.py: FOUND
- web/templates/dashboard.html: FOUND
- web/static/dashboard.css: FOUND
- core/cli/web.py: FOUND (filled)
- tests/test_web_mod02.py: FOUND

Commits exist:
- e1eae9a: FOUND
- 9eab60b: FOUND
- 1d9752f: FOUND
- 20f64ea: FOUND

Full suite: 320 passed, 0 failed.
