# Milestones

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
