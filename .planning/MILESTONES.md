# Milestones

## v4.1 Dashboard & Observability (Shipped: 2026-06-30)

**Phases completed:** 6 phases (25-29 + inserted 29.1), 20 plans

**Delivered:** The optional FastAPI dashboard is redesigned on a zero-Node vendored design system and surfaces live operational observability over SSE, without breaking the CLI-default, localhost-bound, no-CDN posture.

**Key accomplishments:**

- **Design system (P25):** Zero-Node vendored CSS split (`tokens.css` / `components.css` / `dashboard.css`), light/dark theme with FOUC-safe inline `<head>` script, uPlot 1.6.32 vendored (no CDN), and the `loadItems()`/`loadCredentials()` XSS vector replaced with `createElement`/`textContent`; MC-4 non-local banner + CSRF gate preserved.
- **Read-only API (P26):** `GET /api/history`, `GET /api/price-history/{link_b64}`, and a filterable `GET /api/logs` (level/search/n) — every sync DB/log read wrapped in `asyncio.to_thread`; `last_error` scrubbed to `exc.__class__.__name__`; CI assertion guards the read path against credential-pattern leaks.
- **SSE infrastructure (P27):** Single `/api/events` stream over a clean cross-thread bridge where uvicorn's `_poll_loop` is the sole producer (bot daemon never touches `asyncio.Queue`); keepalive comments, disconnect cleanup (no generator leak), `retry: 3000`, and a cursor-based log tail.
- **Observability surfaces (P28):** Per-plugin health cards (status badge, monotonic heartbeat-age color bands, error/items counters, confirmed-orders counter), confirmed-buys table, per-item uPlot price charts with explicit empty-state, color-coded filterable log viewer (Follow/pause-on-scroll, 500-line DOM cap), and a uptime status bar.
- **SSE client wiring (P29):** Replaced the 2s `setInterval` polling with a single feature-detected `EventSource('/api/events')` (named status/log listeners, one-shot backfill), a polling fallback for environments without `EventSource`, and a Live/Reconnecting indicator.
- **Tech-debt cleanup (P29.1, inserted):** Closed 3 audit warnings — uPlot loader relocated to `<head>` (cold-load `ReferenceError` race removed), blanket consecutive-line log drop replaced with a one-shot backfill-boundary dedup, and an SSE idle watchdog + REST polling fallback so a stalled-but-open stream flips to Reconnecting and recovers to Live.

**Audit:** `.planning/milestones/v4.1-MILESTONE-AUDIT.md` (refresh 2026-06-30) — 16/16 requirements satisfied, 6/6 phases, 6/6 integration boundaries WIRED, 5/5 E2E flows complete. Full suite 807 passed / 2 skipped. Status `tech_debt` (no blockers): 2 low-sev warnings (UI-03 SSR remove-button dead handler; `last_heartbeat` cosmetic field in status payload).

**Known deferred items at close: 8** (see STATE.md → Deferred Items) — 4 `human_needed` verifications (P27/28/29/29.1, live-browser/socket) + 1 partial HUMAN-UAT (29.1, 3 scenarios), all deferred per the autonomous live-UAT policy; 1 todo (Amazon WAF auto-solve, manual-pause fallback in place); 2 dormant seeds (SEED-001 repo scrub, SEED-002 release-please) — release-milestone items.

---

## v4.0 Win-the-Drop (Shipped: 2026-06-25)

**Phases completed:** 7 phases, 29 plans

**Delivered:** ShopPyBot now completes *verified* orders on limited-release drops and survives multi-hour unattended runs without one fault taking down the rest.

**Key accomplishments:**

- **Safety gate (P18):** Central monitor-only mode + concrete `place_order_guarded()` on the `RetailerPlugin` ABC routes all 7 bundled plugins' place-order clicks through one guard, closing the confirmed 6-of-7 `test_mode` hole (CI grep + zero-write integration test). `CheckoutConfig` schema foundation for downstream phases.
- **Verified checkout (P19):** URL-first order-confirmation detector (`core/confirmation.py`) plus idempotent `order_id`/`confirmed_at`/`checkout_attempts` columns — `purchased` is written only on a real order number, never a button click.
- **Checkout profile + form-fill (P20):** 9-key CredentialStore shipping/billing profile, BestBuy + Amazon form-fill, CVV via `getpass` at runtime only, AST CI assertion proving no CVV leaks to logs; no full card data persisted.
- **Bounded retry (P21):** Single `RetryPolicy` in `core/retry.py` shared by supervisor restart and cart-retry; per-step `asyncio.timeout()` per DOM stage; DB idempotency re-read before each attempt (no double-buy).
- **Supervisor + relaunch (P22):** Per-coroutine supervision with failure budget absorbs crashes before the TaskGroup boundary; full browser relaunch (teardown→stealth→proxy→login); `sqlite3.OperationalError` read isolation; per-item timeout; cross-platform SIGTERM/SIGINT teardown bridge.
- **Encrypted sessions (P23):** Fernet-encrypted per-platform cookie persistence (`core/session_store.py`) via raw CDP restore that bypasses the nodriver `set_all()` bug; skips re-login/MFA across restarts, no plaintext on disk.
- **Health surface + server safety (P24):** `HealthRegistry`, expanded `BotService.get_status()` (per-plugin liveness/heartbeat), `health_degraded` fan-out alert, `shoppybot status` CLI, headless pygame import-crash guard.

**Audit:** `.planning/milestones/v4.0-MILESTONE-AUDIT.md` — 17/17 requirements, 7/7 phases verified, 6/6 integration seams clean, suite 755 passed / 2 skipped. Status `tech_debt` (no blockers).

**Known deferred items at close: 17** (see STATE.md → Deferred Items) — 7 live-environment UAT scenarios + 7 `human_needed` verifications (deferred per autonomous live-UAT policy), 1 todo (Amazon WAF auto-solve), 2 dormant seeds (SEED-001 repo scrub, SEED-002 release-please) — all explicitly Out of Scope for v4.0.

---

## v3.0 v3.0 (Shipped: 2026-06-10)

**Phases completed:** 6 phases, 21 plans, 32 tasks

**Key accomplishments:**

- logger._load_logging_level() re-anchored to core.paths.config_path() with a dedicated reload-based regression test that guards the migrated-config logging_level behavior
- ProxyConfig Pydantic model nested under AppConfig providing opt-in, disabled-by-default proxy rotation config surface for ANTI-04
- 1. [Rule 1 - Bug] conftest mock_nodriver_start main_tab.send not AsyncMock
- 2captcha v1 client (hand-rolled requests submit/poll/balance) with per-run solve cap, zero-balance gate, and API key exclusively in the credential store.
- CaptchaSolver injected into plugins via PluginRegistry.assign_solver, built fresh per run in async_main with startup balance check off the event loop, and operator-visible INFO log in BotService (no key logged).
- reCAPTCHA v2 automated solve path wired into Amazon and BestBuy plugins via run_in_executor under asyncio.timeout(120); every failure mode degrades gracefully to the existing manual-pause path; Amazon WAF deferred and documented.
- Three additive class attrs (difficulty/requires_proxy/requires_captcha) on RetailerPlugin ABC with __init_subclass__ import-time difficulty validation; all 7 existing plugins load unchanged with defaults
- BotService.list_plugins() + core/cli/plugins.py + shoppybot plugins list [--json]; bare plugins exits 2; no network call; 5 new tests, 492 total passing
- 9-field wiki registry table SPEC in docs/PLUGIN_REGISTRY.md plus structured difficulty/requires_proxy/requires_captcha metadata required in CONTRIBUTING.md, PR template, and PLUGIN_DEV.md; 4 doc-presence tests added
- Idempotent SQLite migration adding price_history table, four items columns, eight parameterized _sync functions, and Optional ItemConfig price fields for per-item price monitoring
- 1. [Rule 1 - Bug] Test spy patches targeted wrong module binding
- Six deterministic proxy-surface tests covering URL validation, CDP fetch-handler task lifecycle, ProxyPool empty-pool edges, and registry routing/lifecycle isolation -- bringing stealth.py to 99% and config_schema.py to 96% coverage on the new lines
- Six deterministic tests cover the v2.0-DB in-place migration fixture, denominator guards, trigger early-returns, row-None sentinels, and get_price error isolation + sequencing -- models.py:48-81/198/246 and orchestrator.py:70/77/123/126/209-210 now CI-covered.

---

## v2.0 Modular Core + Cross-Platform UX (Shipped: 2026-06-06)

**Phases completed:** 5 phases, 20 plans, 17 tasks

**Key accomplishments:**

- BotService wraps registry+orchestrator+config+models behind a single importable class using a daemon-thread-with-own-loop for non-blocking start/stop from any sync caller.
- setuptools pyproject.toml with shoppybot console entry point (core.service:main), explicit package discovery for core/plugins/notifications, and argparse --help guard so shoppybot --help exits cleanly
- Task 1: Slim main.py into BotService-delegating shim (f51ccf1)
- 1. [Rule 2 - Missing critical functionality] Added os.unlink cleanup guard in EncryptedFileBackend._save
- 1. [Rule 3 - Blocking] keyring and cryptography not installed in venv
- 1. [Rule 1 - Bug] test_run_subcommand_calls_botservice_run expected no SystemExit
- Interactive credential setup via grouped getpass prompts with key-name-only confirmation, and config show/set with ALLOWLIST gate + atomic YAML write
- Items subcommand fully wired over BotService with aligned table, name-on-remove, exit-1-on-miss, and MOD-02 AST guard enforcing no CLI module bypasses BotService
- 1. [Rule 1 - Bug] test_run_works_without_fastapi raised SystemExit instead of asserting mock call
- `pyproject.toml` now carries `[project.optional-dependencies] web` with exact-pinned fastapi==0.115.8, uvicorn[standard]==0.30.6, jinja2==3.1.4, python-multipart==0.0.32. The `web*` package is added to setuptools `packages.find include`.
- Seven FastAPI route handlers in web/routes/api.py thin-adapting BotService with CSRF origin-checks, running-state guards, and event-loop-safe async stop via run_in_executor
- Returns `{"credentials": [{"name": k, "is_set": store.get(k) is not None}]}` for every key in `SECRET_KEYS`. No `value` field present on any entry (SC3 / T-10-08).
- Four legacy path anchors (models DB, creds.bin, config.yml, log dir) re-routed through core/paths.py; CWD-relative DB bug fixed; logger lazy-imports log_dir inside writeLog to avoid circular import; full 341-test suite stays green.
- 1. [Rule 1 - Bug] items list requires initialize_db() before first query

---
