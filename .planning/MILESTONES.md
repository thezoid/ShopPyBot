# Milestones

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
