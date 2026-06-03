# ShopPyBot — Roadmap

## Project

**Core Value:** A drop-in plugin framework that lets the community add new retail platform integrations by placing a single Python file in `plugins/` — no core changes required.

**Milestone:** v1 Open Source Launch

---

## Phases

- [x] **Phase 1: Foundations + Security** — Plugin ABC contract locked, Pydantic config validation, all credential security hardening complete; safe to open source (completed 2026-06-02)
- [x] **Phase 2: Plugin Migration** — Amazon and BestBuy refactored to ABC, plugin registry operational, contributor tooling published (completed 2026-06-03)
- [x] **Phase 3: Community Documentation** — CONTRIBUTING.md, SECURITY.md, issue templates, and PR template in place so the project is ready for external contributors (completed 2026-06-03)
- [ ] **Phase 4: Async Orchestrator** — All platforms run concurrently, SQLite safe under parallel writes, no blocking I/O in async loop
- [ ] **Phase 5: Notification System** — Fan-out dispatcher delivers alerts across all configured channels with per-item deduplication
- [ ] **Phase 6: Platform Expansion** — Five new platform plugins operational with anti-detection configuration

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
- [ ] 04-05-PLAN.md — main.py wiring to orchestrator + live concurrency/zero-lock human-verify (ASYNC-01..05)

### Phase 5: Notification System

**Goal**: A fan-out notification dispatcher delivers stock alerts across all configured channels; a single channel failure does not prevent other channels from firing; each item triggers at most one notification per restock event.
**Depends on**: Phase 4
**Requirements**: NOTIF-01, NOTIF-02, NOTIF-03, NOTIF-04, NOTIF-05, NOTIF-06
**Success Criteria** (what must be TRUE):

  1. When Discord is misconfigured (bad webhook URL), the bot continues running and delivers notifications to email and sound — the error is logged but does not crash or block other channels
  2. An item going in and out of stock multiple times within one poll cycle produces exactly one notification per restock event, not one per poll tick
  3. A Discord notification includes item name, URL, platform, timestamp, and action taken (detected / purchased), formatted as an embed
  4. SMS via Twilio is disabled by default; enabling it requires explicit opt-in configuration; accidental activation without credentials produces a clear config error, not a silent no-op

**Plans**: TBD
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

**Plans**: TBD
**UI hint**: no

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundations + Security | 5/5 | Complete   | 2026-06-02 |
| 2. Plugin Migration | 6/6 | Complete   | 2026-06-03 |
| 3. Community Documentation | 2/2 | Complete   | 2026-06-03 |
| 4. Async Orchestrator | 4/5 | In Progress|  |
| 5. Notification System | 0/? | Not started | - |
| 6. Platform Expansion | 0/? | Not started | - |

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

**Total: 44/44 requirements mapped**

---

*Last updated: 2026-06-03 — Phase 4 planned (5 plans)*
