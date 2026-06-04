# ShopPyBot — Roadmap

## Project

**Core Value:** A drop-in plugin framework that lets the community add new retail platform integrations by placing a single Python file in `plugins/` — no core changes required.

**Milestone:** v1 Open Source Launch

---

## Phases

- [x] **Phase 1: Foundations + Security** — Plugin ABC contract locked, Pydantic config validation, all credential security hardening complete; safe to open source (completed 2026-06-02)
- [x] **Phase 2: Plugin Migration** — Amazon and BestBuy refactored to ABC, plugin registry operational, contributor tooling published (completed 2026-06-03)
- [x] **Phase 3: Community Documentation** — CONTRIBUTING.md, SECURITY.md, issue templates, and PR template in place so the project is ready for external contributors (completed 2026-06-03)
- [x] **Phase 4: Async Orchestrator** — All platforms run concurrently, SQLite safe under parallel writes, no blocking I/O in async loop (completed 2026-06-03)
- [x] **Phase 5: Notification System** — Fan-out dispatcher delivers alerts across all configured channels with per-item deduplication (completed 2026-06-03)
- [x] **Phase 6: Platform Expansion** — Five new platform plugins operational with anti-detection configuration (completed 2026-06-03)

---

## Phase Details

### Phase 1: Foundations + Security

**Goal**: The plugin interface contract is locked and versioned, config is validated at startup, and all credential/driver security issues are resolved — making the codebase safe to publish as open source.
**Depends on**: Nothing (first phase)
**Requirements**: CORE-01, CORE-02, CORE-05, CORE-06, CORE-07, SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, INFRA-01, INFRA-02, INFRA-03
**Success Criteria** (what must be TRUE):

  1. A developer can implement `RetailerPlugin` ABC with only `check_availability` and `auto_buy` as required methods; `login` and `detect_captcha` have working no-op defaults and `PLUGIN_API_VERSION = 1` is importable
  2. Starting the bot with a `config.yml` missing a required field prints an actionable error message describing exactly which field is missing and where to set it, then exits — it does not crash with a stack trace
  3. No credentials, CVV, or passwords exist in `config.yml` or any log output; the bot prompts for CVV at runtime via `getpass` and reads credentials from environment variables only
  4. ChromeDriver launches without `--disable-web-security`, reports a real Chrome user agent string, and has `navigator.webdriver` hidden via CDP patch
  5. `requirements.txt` specifies exact pinned versions, contains no duplicates, and declares `python_requires >= 3.11`; ChromeDriver output is suppressed without `sys.stdout` monkey-patching

**Plans**: 5 plans
Plans:

- [x] 01-01-PLAN.md — Wave 0: repair broken test suite, add pyproject.toml + shared fixtures
- [x] 01-02-PLAN.md — RetailerPlugin ABC + PLUGIN_API_VERSION (CORE-01, CORE-02)
- [x] 01-03-PLAN.md — AppConfig pydantic-settings validation (CORE-05, CORE-06, CORE-07, SEC-01)
- [x] 01-04-PLAN.md — requirements.txt pin/dedupe + logger singleton (INFRA-01, INFRA-02)
- [x] 01-05-PLAN.md — main.py security hardening + sample config + .env.example + README disclaimer (SEC-01..06, INFRA-03)

### Phase 2: Plugin Migration

**Goal**: Amazon and BestBuy are fully migrated to the plugin ABC with isolated WebDriver instances, the plugin registry auto-discovers and routes plugins at startup, and contributor tooling is in place so the framework is immediately usable by external developers.
**Depends on**: Phase 1
**Requirements**: CORE-03, CORE-04, CORE-08, PLG-01, PLG-02, PLG-03
**Success Criteria** (what must be TRUE):

  1. Dropping `plugins/shopbot_plugin_amazon.py` and `plugins/shopbot_plugin_bestbuy.py` into the `plugins/` directory causes the registry to discover and load both plugins at startup with no manual registration required
  2. Placing a `.py` file in `plugins/` that does not match the `shopbot_plugin_*.py` naming convention produces a logged warning and is ignored — it does not crash the bot
  3. Each plugin owns its own `self.driver` WebDriver instance; neither plugin references a global driver; BestBuy calls `update_item_purchased()` after a successful purchase
  4. A new contributor can read `plugins/PLUGIN_DEV.md` and `plugins/example_plugin.py`, copy the example, implement `check_availability` and `auto_buy`, and have a working skeleton plugin without reading any core source code

**Plans**: 6 plans
Plans:

- [x] 02-01-PLAN.md — Wave 0: rewrite plugin-base tests for ABC v2 + async fixtures/smoke test
- [x] 02-02-PLAN.md — Revise RetailerPlugin ABC v1 to v2 (async, self.driver, setup/teardown, version 2)
- [x] 02-03-PLAN.md — Plugin registry: importlib discovery + domain routing + lazy lifecycle (CORE-03, CORE-04)
- [x] 02-04-PLAN.md — Amazon + BestBuy nodriver plugins; PLG-02 update_item_purchased fix (PLG-01, PLG-02, PLG-03)
- [x] 02-05-PLAN.md — main.py async conversion: registry-driven loop, Selenium/CDP removal, CVV threading
- [x] 02-06-PLAN.md — Contributor tooling: example_plugin.py + PLUGIN_DEV.md (CORE-08)

**UI hint**: no

### Phase 3: Community Documentation

**Goal**: CONTRIBUTING.md, SECURITY.md, issue templates, and a PR template are in place so external contributors know how to submit plugins, report security issues, and engage with the project safely.
**Depends on**: Phase 2
**Requirements**: DOCS-01, DOCS-02, DOCS-03, DOCS-04, DOCS-05
**Success Criteria** (what must be TRUE):

  1. A first-time contributor can open CONTRIBUTING.md and find the full plugin submission workflow — naming convention, required ABC methods, test expectations, and anti-detection risk declaration — without reading any source code
  2. SECURITY.md explicitly lists known TOS/legal risks per platform and includes a responsible disclosure process with a contact method
  3. Submitting a bug report or plugin request via GitHub Issues presents a pre-filled template with the required fields
  4. Opening a pull request presents a checklist covering ABC compliance, naming convention, test presence, and risk documentation

**Plans**: 2 plans
Plans:

- [x] 03-01-PLAN.md — Governance prose docs: SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md (DOCS-01, DOCS-02, DOCS-03)
- [x] 03-02-PLAN.md — GitHub templates: PR template + bug/plugin issue forms + ISSUE_TEMPLATE config (DOCS-04, DOCS-05)

**UI hint**: no

### Phase 4: Async Orchestrator

**Goal**: All active platform plugins run concurrently in a single async event loop, SQLite handles parallel writes without locking errors, and no blocking `input()` calls stall the async loop.
**Depends on**: Phase 3
**Requirements**: ASYNC-01, ASYNC-02, ASYNC-03, ASYNC-04, ASYNC-05
**Success Criteria** (what must be TRUE):

  1. Running the bot with Amazon and BestBuy both configured shows both platforms polling concurrently — log timestamps confirm overlapping execution, not sequential
  2. Starting the bot with three or more plugins does not produce ChromeDriver port conflicts; startup logs show each plugin's driver initializing at least 1.5 seconds apart
  3. No `input()` calls exist anywhere in the async code path; user intervention (e.g., manual CAPTCHA solve) is communicated via `asyncio.Event` notification
  4. Sustained parallel operation for 60+ minutes on two platforms produces zero `database is locked` SQLite errors; all `update_item_purchased()` calls succeed

**Plans**: 5 plans
Plans:

- [x] 04-01-PLAN.md — Wave 0: poll_interval config field + fake_plugin/Event test fixtures (ASYNC-01, ASYNC-02, ASYNC-03, ASYNC-05)
- [x] 04-02-PLAN.md — SQLite WAL context manager + *_sync functions + concurrent-write stress proxy (ASYNC-04, ASYNC-05)
- [x] 04-03-PLAN.md — Orchestrator: TaskGroup + 1.5s stagger + write-queue drain + stdin listener (ASYNC-01, ASYNC-02, ASYNC-05)
- [x] 04-04-PLAN.md — Replace 5 Amazon input() with asyncio.Event; remove direct DB writes (ASYNC-03, ASYNC-05)
- [x] 04-05-PLAN.md — main.py wiring to orchestrator + live concurrency/zero-lock human-verify (ASYNC-01..05)

### Phase 5: Notification System

**Goal**: A fan-out notification dispatcher delivers stock alerts across all configured channels; a single channel failure does not prevent other channels from firing; each item triggers at most one notification per restock event.
**Depends on**: Phase 4
**Requirements**: NOTIF-01, NOTIF-02, NOTIF-03, NOTIF-04, NOTIF-05, NOTIF-06
**Success Criteria** (what must be TRUE):

  1. When Discord is misconfigured (bad webhook URL), the bot continues running and delivers notifications to email and sound — the error is logged but does not crash or block other channels
  2. An item going in and out of stock multiple times within one poll cycle produces exactly one notification per restock event, not one per poll tick
  3. A Discord notification includes item name, URL, platform, timestamp, and action taken (detected / purchased), formatted as an embed
  4. SMS via Twilio is disabled by default; enabling it requires explicit opt-in configuration; accidental activation without credentials produces a clear config error, not a silent no-op

**Plans**: 5 plans
Plans:

- [x] 05-01-PLAN.md — Wave 0: NotificationsConfig + SMS startup gate + dedup columns/state functions + Notifier ABC + 14-test scaffold (NOTIF-02, NOTIF-06)
- [x] 05-02-PLAN.md — SoundNotifier (wraps utils) + DiscordNotifier embed POST (NOTIF-03, NOTIF-04)
- [x] 05-03-PLAN.md — EmailNotifier (smtplib STARTTLS) + SmsNotifier (Twilio REST) (NOTIF-05, NOTIF-06)
- [x] 05-04-PLAN.md — NotificationDispatcher fan-out with per-channel isolation + secret scrub (NOTIF-01)
- [x] 05-05-PLAN.md — Orchestrator wiring: build_dispatcher + dedup edge-trigger + typed write queue + live Discord human-verify (NOTIF-01, NOTIF-02, NOTIF-04)

**UI hint**: no

### Phase 6: Platform Expansion

**Goal**: Five new platform plugins (Walmart, Target, GameStop, Square Enix, NewEgg) are operational, each with documented anti-detection risk levels, and per-platform delay/jitter/headless configuration is available across all plugins.
**Depends on**: Phase 5
**Requirements**: PLG-04, PLG-05, PLG-06, PLG-07, PLG-08, ANTI-01, ANTI-02, ANTI-03
**Success Criteria** (what must be TRUE):

  1. All five new platform plugins load via the plugin registry without modifying any core code; each plugin file is self-contained
  2. Setting `platforms.walmart.min_delay: 8` and `platforms.walmart.max_delay: 15` in `config.yml` causes Walmart polling intervals to vary randomly between 8 and 15 seconds with no code changes
  3. Setting `platforms.amazon.headless: false` launches an Amazon browser session in visible mode while other platforms run headless, all in the same bot process
  4. The Walmart plugin README section documents PerimeterX/HUMAN Security detection risk; the Target plugin documents that auto-buy is experimental due to Akamai headless blocking

**Plans**: 5 plans
Plans:

- [x] 06-01-PLAN.md — Wave 0: config_schema 5 platform submodels + UA pool constant + mock-nodriver fixture + 7 test scaffolds (ANTI-01, ANTI-02, ANTI-03)
- [x] 06-02-PLAN.md — Orchestrator per-platform jitter: _get_plugin_sleep + run_plugin wiring + jitter tests (ANTI-01)
- [x] 06-03-PLAN.md — Walmart + Target + GameStop plugins; ANTI-02/03 setup; SC4 risk docstrings (PLG-04, PLG-05, PLG-06, ANTI-02, ANTI-03)
- [x] 06-04-PLAN.md — Square Enix + NewEgg plugins; ANTI-02/03 setup; risk docstrings (PLG-07, PLG-08, ANTI-02, ANTI-03)
- [x] 06-05-PLAN.md — SECURITY.md 5 risk rows + SC4 phrase tests + SC1 7-plugin discovery gate (PLG-04, PLG-05, PLG-06, PLG-07, PLG-08)

**UI hint**: no

---

## Milestone v2.0 — Modular Core + Cross-Platform UX

**Goal:** Refactor the v1 code into a clean reusable core library, add a dynamic cross-platform secure credential store, and add an optional local web UI, while keeping the CLI the default, running on Ubuntu (desktop + headless) and Windows.

### v2.0 Phase Checklist

- [ ] **Phase 7: Modular Core Service** — `BotService` wraps all bot logic behind a stable API; installable package with `shoppybot` entry point; `main.py` becomes a thin shim
- [ ] **Phase 8: Credential Store** — `CredentialStore` interface with OS-keyring/encrypted-file/env-var backends; all secret reads routed through it; no scattered `os.environ` reads remain
- [ ] **Phase 9: CLI Front-End** — `shoppybot` CLI commands (run/setup/items/config) over `BotService`; setup command stores/manages credentials cross-platform; fully functional without any web UI
- [ ] **Phase 10: Optional Web UI** — FastAPI local dashboard (localhost-bound) for items/config/credentials/bot control; optional install extra; credential secrets never leave the server
- [ ] **Phase 11: Cross-Platform Verification** — Documented and automated verification that import, CLI, and credential-backend selection work correctly on both Ubuntu and Windows

---

## Phase Details (v2.0)

### Phase 7: Modular Core Service

**Goal**: All bot logic lives in a single importable `BotService` API; the CLI, web UI, and `python main.py` shim all call the same service; no logic is duplicated in front-ends; the package is installable via pip.
**Depends on**: Phase 6
**Requirements**: MOD-01, MOD-02, MOD-03
**Success Criteria** (what must be TRUE):

  1. `from core.service import BotService` succeeds after `pip install -e .`; calling `BotService.start()`, `BotService.stop()`, `BotService.list_items()`, `BotService.add_item()`, `BotService.remove_item()`, `BotService.get_status()`, and `BotService.get_config()` covers every operation the bot exposes to front-ends.
  2. A grep for `PluginRegistry`, `async_main`, direct SQLite model calls, and `AppConfig()` across the `cli/` and any future `web/` directories returns zero matches — all such calls are inside `core/service.py` or below.
  3. `pip install -e .` succeeds on both Ubuntu and Windows; running `shoppybot --help` shows the entry point; running `python main.py` continues to work and delegates immediately to `BotService`.
  4. The existing test suite passes without modification after the refactor (no behavior regressions in v1 capabilities).

**Plans**: 3 plans
Plans:

- [ ] 07-01-PLAN.md — BotService API (start/stop/run/list/add/remove/get_status/get_config) + remove_item_sync + new service tests (MOD-01)
- [ ] 07-02-PLAN.md — pyproject.toml packages + shoppybot console entry point (core.service:main); pip install -e . (MOD-03)
- [ ] 07-03-PLAN.md — main.py thin shim routes through BotService.run; update test_main_wiring delegation seam (MOD-02, MOD-03)

**UI hint**: no

### Phase 8: Credential Store

**Goal**: A `CredentialStore` abstraction with three runtime-selectable backends (OS keyring, encrypted file, env-var) centralizes all secret access; no plaintext secrets exist anywhere on disk; every plugin and notifier reads credentials through the store.
**Depends on**: Phase 7
**Requirements**: CRED-01, CRED-02, CRED-03, CRED-04, CRED-05, CRED-06, CRED-07
**Success Criteria** (what must be TRUE):

  1. A grep for `os.environ.get` and `os.environ[` across `plugins/`, `notifications/`, and `core/` returns zero matches for secret keys (`DISCORD_WEBHOOK_URL`, `SMTP_PASSWORD`, `TWILIO_*`, `AMZ_*`, `BB_*`) — every such read is replaced by a `CredentialStore.get(key)` call.
  2. On a machine with a functioning OS keyring (Windows Credential Manager or Linux Secret Service), secrets stored via `CredentialStore.set(key, value)` survive a process restart and are retrieved correctly without any env-var set.
  3. On a headless Ubuntu machine with no keyring daemon, the encrypted-file backend activates automatically; the data-dir file is binary (not readable as plaintext); a test asserts that no secret value appears as plaintext in `config.yml`, any log file, or the SQLite database.
  4. When no store is configured and no keyring is available, the env-var fallback activates; startup logs the active backend name (e.g., `CredentialStore: env-var backend active`) without logging any secret value.
  5. Running `shoppybot setup --migrate` imports all secrets currently set as environment variables into the selected backend and confirms each key imported by name (not value).

**Plans**: TBD
**UI hint**: no

### Phase 9: CLI Front-End

**Goal**: The `shoppybot` command-line tool provides all bot operations (run, setup, item management, config) through `BotService` and `CredentialStore`; it is fully functional with no web UI installed; setup works interactively on both Ubuntu and Windows.
**Depends on**: Phase 8
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04
**Success Criteria** (what must be TRUE):

  1. `shoppybot run` starts the bot (and `python main.py` still works identically); both paths call `BotService.start()` with no duplicated orchestrator logic.
  2. `shoppybot setup` prompts for each known credential key by name, stores each value via `CredentialStore.set()` without echoing it to the terminal, and confirms storage by key name only — the flow completes correctly on both Ubuntu (interactive terminal) and Windows (PowerShell).
  3. `shoppybot items list` prints the current tracked items; `shoppybot items add --name "..." --url "..."` adds an item; `shoppybot items remove --url "..."` removes it; all three call `BotService` and not the DB directly.
  4. Uninstalling FastAPI (`pip uninstall fastapi`) leaves `shoppybot run`, `shoppybot setup`, and `shoppybot items` fully functional — no import errors, no degraded behavior.

**Plans**: TBD
**UI hint**: no

### Phase 10: Optional Web UI

**Goal**: An optional FastAPI dashboard reachable at `http://127.0.0.1:PORT` lets users manage items, credentials, and bot state through a browser; it installs as an optional extra; credential secrets never leave the server side; binding to any non-localhost address requires explicit opt-in and prints a security warning.
**Depends on**: Phase 9
**Requirements**: GUI-01, GUI-02, GUI-03, GUI-04, GUI-05, GUI-06
**Success Criteria** (what must be TRUE):

  1. `pip install .[web]` installs FastAPI and its dependencies; `shoppybot web` starts the server on `127.0.0.1` at the configured port; visiting the URL in a browser renders the dashboard without errors.
  2. Adding, removing, and listing tracked items through the dashboard UI produces the same DB state as the equivalent `shoppybot items` CLI commands — both call `BotService` and the results are identical.
  3. Submitting a credential update through the dashboard POSTs the value to the server, stores it via `CredentialStore.set()`, and returns only a success/failure status to the browser — the secret value is never included in any HTTP response body, HTML page source, browser localStorage, or server log.
  4. Clicking Start/Stop in the dashboard calls `BotService.start()` / `BotService.stop()`; the status indicator reflects the current `BotService.get_status()` state; recent log lines are visible without a page refresh.
  5. With FastAPI not installed (`pip install .` without `[web]`), `shoppybot run`, `shoppybot setup`, and `shoppybot items` all work without errors; `shoppybot web` prints a clear message that the web extra is not installed.
  6. Launching with a non-localhost bind address (e.g., `--host 0.0.0.0`) prints a prominently visible security warning to stdout before the server starts, stating that credential management is exposed on a non-local interface.

**Plans**: TBD
**UI hint**: yes

### Phase 11: Cross-Platform Verification

**Goal**: Every front-end command and all three credential backends are verified to work correctly on both Ubuntu (desktop and headless) and Windows; OS-specific path handling is correct; a verification matrix documents the results.
**Depends on**: Phase 10
**Requirements**: XPLAT-01, XPLAT-02
**Success Criteria** (what must be TRUE):

  1. Data directory, config path, and log path resolve to OS-appropriate locations on both Ubuntu and Windows (e.g., `~/.local/share/shoppybot` on Ubuntu, `%APPDATA%\shoppybot` on Windows or equivalent); no hardcoded path separators appear in the codebase.
  2. `shoppybot --help`, `shoppybot setup`, and `shoppybot run --dry-run` (or equivalent smoke) complete without errors on Ubuntu desktop, Ubuntu headless (no display), and Windows — confirmed by manual run or CI matrix job.
  3. The credential-backend auto-selection logic chooses the OS keyring backend on Windows and desktop Ubuntu, and the encrypted-file backend on headless Ubuntu with no active Secret Service — verified on each target environment.
  4. A `docs/PLATFORMS.md` file (or equivalent section in README) documents the verified data/config/log paths per OS, the expected credential backend per environment, and the steps to reproduce the verification matrix.

**Plans**: TBD
**UI hint**: no

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundations + Security | 5/5 | Complete   | 2026-06-02 |
| 2. Plugin Migration | 6/6 | Complete   | 2026-06-03 |
| 3. Community Documentation | 2/2 | Complete   | 2026-06-03 |
| 4. Async Orchestrator | 5/5 | Complete   | 2026-06-03 |
| 5. Notification System | 5/5 | Complete   | 2026-06-03 |
| 6. Platform Expansion | 5/5 | Complete   | 2026-06-03 |
| 7. Modular Core Service | 0/TBD | Not started | - |
| 8. Credential Store | 0/TBD | Not started | - |
| 9. CLI Front-End | 0/TBD | Not started | - |
| 10. Optional Web UI | 0/TBD | Not started | - |
| 11. Cross-Platform Verification | 0/TBD | Not started | - |

---

## Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 | Pending |
| CORE-02 | Phase 1 | Pending |
| CORE-03 | Phase 2 | Pending |
| CORE-04 | Phase 2 | Pending |
| CORE-05 | Phase 1 | Pending |
| CORE-06 | Phase 1 | Pending |
| CORE-07 | Phase 1 | Pending |
| CORE-08 | Phase 2 | Pending |
| SEC-01 | Phase 1 | Pending |
| SEC-02 | Phase 1 | Pending |
| SEC-03 | Phase 1 | Pending |
| SEC-04 | Phase 1 | Pending |
| SEC-05 | Phase 1 | Pending |
| SEC-06 | Phase 1 | Pending |
| PLG-01 | Phase 2 | Pending |
| PLG-02 | Phase 2 | Pending |
| PLG-03 | Phase 2 | Pending |
| PLG-04 | Phase 6 | Pending |
| PLG-05 | Phase 6 | Pending |
| PLG-06 | Phase 6 | Pending |
| PLG-07 | Phase 6 | Pending |
| PLG-08 | Phase 6 | Pending |
| ASYNC-01 | Phase 4 | Pending |
| ASYNC-02 | Phase 4 | Pending |
| ASYNC-03 | Phase 4 | Pending |
| ASYNC-04 | Phase 4 | Pending |
| ASYNC-05 | Phase 4 | Pending |
| ANTI-01 | Phase 6 | Pending |
| ANTI-02 | Phase 6 | Pending |
| ANTI-03 | Phase 6 | Pending |
| NOTIF-01 | Phase 5 | Pending |
| NOTIF-02 | Phase 5 | Pending |
| NOTIF-03 | Phase 5 | Pending |
| NOTIF-04 | Phase 5 | Pending |
| NOTIF-05 | Phase 5 | Pending |
| NOTIF-06 | Phase 5 | Pending |
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| DOCS-01 | Phase 3 | Pending |
| DOCS-02 | Phase 3 | Pending |
| DOCS-03 | Phase 3 | Pending |
| DOCS-04 | Phase 3 | Pending |
| DOCS-05 | Phase 3 | Pending |
| MOD-01 | Phase 7 | Pending |
| MOD-02 | Phase 7 | Pending |
| MOD-03 | Phase 7 | Pending |
| CRED-01 | Phase 8 | Pending |
| CRED-02 | Phase 8 | Pending |
| CRED-03 | Phase 8 | Pending |
| CRED-04 | Phase 8 | Pending |
| CRED-05 | Phase 8 | Pending |
| CRED-06 | Phase 8 | Pending |
| CRED-07 | Phase 8 | Pending |
| CLI-01 | Phase 9 | Pending |
| CLI-02 | Phase 9 | Pending |
| CLI-03 | Phase 9 | Pending |
| CLI-04 | Phase 9 | Pending |
| GUI-01 | Phase 10 | Pending |
| GUI-02 | Phase 10 | Pending |
| GUI-03 | Phase 10 | Pending |
| GUI-04 | Phase 10 | Pending |
| GUI-05 | Phase 10 | Pending |
| GUI-06 | Phase 10 | Pending |
| XPLAT-01 | Phase 11 | Pending |
| XPLAT-02 | Phase 11 | Pending |

**Total: 66/66 requirements mapped**

---

*Last updated: 2026-06-03 — v2.0 phases 7-11 added*
