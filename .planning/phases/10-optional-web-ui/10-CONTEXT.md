# Phase 10: Optional Web UI - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

An OPTIONAL local FastAPI dashboard at `http://127.0.0.1:PORT`, launched via `shoppybot web`, that manages tracked items, credentials, and bot start/stop/status through a browser — as a thin adapter over `BotService` and `CredentialStore` (GUI-01: provides nothing the CLI cannot do). Installs as an optional extra (`pip install .[web]`); core + CLI run with FastAPI absent (GUI-05, already guaranteed by the Phase 9 lazy-import seam in `core/cli/web.py`). Credential secrets never leave the server side (GUI-03). Non-localhost bind requires explicit opt-in and prints a security warning (GUI-06). Covers GUI-01..GUI-06.

NOT in scope: auth/multi-user (single-user local tool), remote hosting, cross-platform CI matrix (Phase 11). The CVV stays a CLI/runtime concern, never managed in the web UI.
</domain>

<decisions>
## Implementation Decisions

### Web Stack & Architecture (GUI-01, GUI-05)
- Server-rendered Jinja2 templates + minimal hand-written vanilla JS (no frontend build step; keeps secrets server-side).
- `[web]` optional extra pins: `fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart` (form posts) — exact-pinned per INFRA-01, added to `pyproject.toml [project.optional-dependencies] web`.
- Live status/logs via polling: JS `fetch` to `/api/status` and `/api/logs` every ~2s (KISS — no websocket/SSE).
- Code layout: a lazy-imported `web/` package exposing `create_app(svc)` (app factory taking a BotService), plus `templates/` and `static/`. `core/cli/web.py:handle_web` imports it inside the function body only — never at module top (preserves CLI-04). uvicorn serves `create_app(get-or-build BotService)`.

### Security — Credential Management over HTTP (GUI-03, GUI-06)
- The credential form lists each known key by NAME with a set/unset status only; it NEVER renders the current value. POST stores via `CredentialStore.set()`; the HTTP response is a success/failure status only — no secret value in any response body, HTML source, localStorage, or server log.
- `--host` flag defaults to `127.0.0.1`. Binding to any non-localhost address prints a prominent, clearly-worded security warning to stderr BEFORE the server starts (stating credential management is exposed on a non-local interface). Warning only — not a hard block (per SC6).
- No authentication for the default localhost bind (single-user local tool; matches the project's "CLI + config sufficient" ethos). The non-local warning makes exposure the user's explicit choice.
- Defense-in-depth: validate the `Origin`/`Host` header on all state-changing POSTs (credentials, items add/remove, config, start/stop) to mitigate local-malware CSRF against `127.0.0.1`. Reject mismatched origins with an error status.

### UI Scope & Layout (GUI-02, GUI-04)
- Single dashboard page with four sections: Controls/Status, Items, Credentials, Config.
- Items: a table of tracked items + an add form (name, url, auto_buy, quantity) + a per-row remove control — all routed through `BotService.add_item/remove_item/list_items`.
- Controls: Start / Stop buttons calling `BotService.start()` / `BotService.stop()`; a status indicator reflecting `BotService.get_status()`; a recent-logs panel updated by polling (no full page refresh).
- Styling: a small vendored minimal CSS file under `static/` — no CDN (works offline, no external dependency).

### Parity & Testing (GUI-01, GUI-02)
- All UI actions route through `BotService` (and the config layer) — never `models.py`/orchestrator/registry directly (mirrors the CLI MOD-02 rule).
- Config editing in the UI mirrors the CLI `config set` allowlist (test_mode, logging_level) plus per-platform/notifier enable toggles.
- Tests use FastAPI's `TestClient`: route-level tests for items/credentials/config/controls; explicit assertions that no secret value appears in any response body or rendered HTML; the whole web test module is skipped when fastapi is not installed (so the default `pip install .` test run stays green).
- GUI-01 parity: the UI is a thin adapter; it exposes nothing the CLI cannot already do.

### Claude's Discretion
- Exact route paths and template partials, the precise polling interval, the vendored CSS contents, how `create_app` obtains/holds the BotService instance, the Origin-check implementation detail, and uvicorn invocation specifics — provided the locked decisions hold, secrets never reach the browser/logs, CLI-04 stays intact (no top-level fastapi import outside the `web/` package, which is itself only imported lazily), and the existing 282-test suite stays green with fastapi absent.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/service.py` `BotService`: `get_config()`, `get_status()`, `list_items()`, `add_item(name, link, auto_buy, quantity)`, `remove_item(link)`, `start(cvv)`, `stop()` — the complete seam the web routes adapt over (same as the CLI).
- `core/credentials.py`: `get_store()`, `SECRET_KEYS`, `get_store().set(key, value)` — credential POST handler target; `list()`/known-keys drive the name+status form.
- `core/cli/web.py:handle_web`: Phase-9 stub with the lazy fastapi import seam + `pip install .[web]` message already in place — Phase 10 fills the body to build + serve `create_app`.
- `core/cli/config_cmd.py`: the `config set` allowlist + `_atomic_yaml_write` pattern to mirror for the web config section.
- `core/cli/items.py`: the CLI items handlers — the web item routes should produce identical BotService calls / DB state (SC2 parity).
- `logger.py`: writeLog + log files under `logs/` — source for the recent-logs panel (read recent lines; never log secrets).

### Established Patterns
- Lazy-import seam + `sys.modules['fastapi']=None` test idiom (Phase 9) — web tests skip when fastapi absent.
- Secrets never logged/echoed/persisted plaintext (Phase 1/8) — extends to: never in an HTTP response or HTML.
- Front-ends are thin adapters over BotService (MOD-02) — web UI is bound by the same rule; an AST/route guard can assert it.

### Integration Points
- `shoppybot web [--host H] [--port P]` → `handle_web` → lazy import `web.create_app(svc)` → uvicorn serve.
- `pyproject.toml` gains `[project.optional-dependencies] web = [...]`.
- Credential POST → `get_store().set`; item routes → BotService; controls → BotService.start/stop/get_status.
</code_context>

<specifics>
## Specific Ideas

- SC3 guardrail: a test that POSTs a credential then asserts the value is absent from the response body, the rendered credentials page HTML, and the server logs.
- SC2 parity: a test asserting a web item add/remove yields the same DB state as the CLI equivalent.
- SC6: a test/asserting that a non-localhost `--host` triggers the stderr security warning before serving.
- MOD-02 web guard: no direct models/orchestrator/registry access from the web package.
- CLI-04 must remain green: fastapi stays out of every module imported by the core CLI path; only the `web/` package (lazily imported) may import fastapi.
</specifics>

<deferred>
## Deferred Ideas

- Authentication / multi-user / remote hosting — out of scope (single-user local tool).
- Websocket/SSE live streaming — polling is sufficient this milestone.
- Full AppConfig editor in the UI — limited to the CLI allowlist + platform/notifier enables.
- Cross-platform verification matrix / CI (Phase 11).
- CVV entry in the web UI — stays a CLI/runtime concern.
</deferred>

---

*Phase: 10-optional-web-ui*
*Context gathered: 2026-06-04 via smart discuss (autonomous)*
