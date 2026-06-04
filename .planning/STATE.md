---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: — Modular Core + Cross-Platform UX
status: executing
last_updated: "2026-06-04T15:08:26.715Z"
last_activity: 2026-06-04
progress:
  total_phases: 11
  completed_phases: 7
  total_plans: 35
  completed_plans: 34
  percent: 64
---

# ShopPyBot — State

## Project Reference

**Core Value**: Drop-in plugin framework — community adds retail platform integrations via a single Python file in `plugins/`; no core changes required.

**Project**: ShopPyBot
**Milestone**: v1 Open Source Launch
**Total Phases**: 6
**Total Requirements**: 44

---

## Current Position

Phase: 08 (credential-store) — EXECUTING
Plan: 4 of 4
Status: Ready to execute
Last activity: 2026-06-04

## Phase Status

| Phase | Goal Summary | Status | Reqs |
|-------|-------------|--------|------|
| 1 — Foundations + Security | Plugin ABC locked, Pydantic config, all security hardened | Not started | 14 |
| 2 — Plugin Migration | Amazon/BestBuy on ABC, registry operational, contributor docs | Not started | 6 |
| 3 — Async Orchestrator | Concurrent plugins, WAL SQLite, no blocking I/O | Not started | 5 |
| 4 — Notification System | Fan-out dispatcher, deduplication, all channels | Not started | 6 |
| 5 — Platform Expansion | 5 new plugins, anti-detection config per platform | Not started | 8 |

---

## Performance Metrics

**Plans completed**: 0
**Requirements completed**: 0
**Phases completed**: 0
**Blockers resolved**: 0

---

## Accumulated Context

### Key Decisions Logged

- Plugin interface: only `check_availability` and `auto_buy` are abstract; `login` and `detect_captcha` get no-op defaults — preserves contributor-friendliness
- Plugin naming convention enforced: `shopbot_plugin_*.py`; non-matching files get a warning log, not a crash
- One WebDriver instance per plugin (`self.driver` in `__init__`); no shared global driver — required for async safety
- CVV via `getpass` at runtime; credentials via env vars only — must be complete before open source launch
- SMS/Twilio is opt-in disabled by default to prevent accidental charges
- nodriver preferred over Selenium for new plugins (async-native, bot-detection resistant); Selenium retained for Phase 1/2 refactor continuity

### Research Flags (carry into planning)

- Phase 3: nodriver async session lifecycle needs validation against plugin interface before Phase 3 planning
- Phase 5 (Walmart): PerimeterX/HUMAN bypass viability with nodriver needs targeted research before committing to auto-buy

### Active Todos

- None yet — roadmap just initialized

### Blockers

- None

---

## Session Continuity

**Last action**: Completed plan 07-03 — main.py slimmed to BotService-delegating shim; test_main_wiring.py updated for new delegation seam; 227 tests passing
**Next action**: Phase 07 plan 04 or next phase
**Context to carry**: main.py is now a thin shim routing through BotService(cfg).run(cvv). getpass CVV collection stays in main.py front-end. BotService.run() is the blocking convenience wrapping asyncio.run(async_main). test_main_wiring.py has 6 passing tests asserting BotService delegation + CVV gate + ValidationError->SystemExit(1).

---

*Last updated: 2026-06-02 — Phase 1 planned by gsd-plan-phase*

## Performance Metrics

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 01-foundations-security P01 | 8m | 3 tasks | 5 files |
| Phase 01 P02 | 5m | - tasks | - files |
| Phase 01 P03 | 5m | 2 tasks | 2 files |
| Phase 01 P04 | 8min | 3 tasks | 3 files |
| Phase 01 P05 | 11min | 3 tasks | 4 files |
| Phase 02-plugin-migration P01 | 207 | 2 tasks | 2 files |
| Phase 02-plugin-migration P03 | 20m | 2 tasks | 2 files |
| Phase 02-plugin-migration P04 | 20min | 2 tasks | 4 files |
| Phase 02-plugin-migration P06 | 15 | 2 tasks | 3 files |
| Phase 02-plugin-migration P05 | 10 | 1 tasks | 1 files |
| Phase 03-community-documentation P01 | 8m | 2 tasks | 3 files |
| Phase 03-community-documentation P02 | 5min | 2 tasks | 5 files |
| Phase 04-async-orchestrator P01 | 15 | 2 tasks | 3 files |
| Phase 04-async-orchestrator P04 | 15m | 2 tasks | 5 files |
| Phase 04-async-orchestrator P05 | 15 | 1 tasks | 3 files |
| Phase 05-notification-system P02 | 12m | 2 tasks | 3 files |
| Phase 05-notification-system P03 | 4m | 2 tasks | 3 files |
| Phase 05-notification-system P04 | 3 | 1 tasks | 3 files |
| Phase 05-notification-system P05 | 25 | 2 tasks | 4 files |
| Phase 06-platform-expansion P01 | 15 | 2 tasks | 9 files |
| Phase 06-platform-expansion P06-02 | 5 minutes | - tasks | - files |
| Phase 06 P03 | 12 | 3 tasks | 9 files |
| Phase 06-platform-expansion P04 | 4m | 2 tasks | 4 files |
| Phase 06-platform-expansion P05 | 5m | 2 tasks | 2 files |
| Phase 07-modular-core-service P01 | 375s | 2 tasks | 3 files |
| Phase 07-modular-core-service P02 | 4min | 1 tasks | 3 files |
| Phase 07-modular-core-service P03 | 5m | 2 tasks | 2 files |
| Phase 08-credential-store P01 | 8min | 3 tasks | 4 files |
| Phase 08-credential-store P02 | 7min | 2 tasks | 3 files |
| Phase 08 P03 | 12min | 3 tasks | 4 files |

## Decisions

- [Phase ?]: Used importlib.reload + monkeypatch.chdir in tests to isolate config.py module-level load without touching production code
- [Phase ?]: PLUGIN_API_VERSION defined module-level before class body; importable without instantiation (T-01-VER)
- [Phase 01-03]: yaml_file= constructor kwarg (not _yaml_file=) used for test injection; _active_yaml_file class sentinel bridges __init__ to classmethod settings_customise_sources
- [Phase 01-03]: No env_prefix on AppConfig; single-user tool keeps DEBUG__LOGGING_LEVEL format simpler than SHOPBOT_DEBUG__LOGGING_LEVEL
- [Phase ?]: [Phase 01-04]: Pinned all deps to exact installed versions; added nodriver==0.50.3 and pydantic-settings[yaml]==2.14.0 after human package-legitimacy approval; logger caches level at import (_LOGGING_LEVEL), eliminating per-loop config.yml reads
- [Phase ?]: Phase-1 SEC-04: navigator.webdriver hidden on the existing Selenium driver via CDP injection; nodriver replaces it in Phase 2
- [Phase ?]: Credentials sourced from env vars (BB_EMAIL/BB_PASSWORD); CVV via runtime getpass, never persisted or logged
- [Phase ?]: open_browser hardcoded False pending AppConfig relocation (app block removed for SEC-01)
- [Phase ?]: pytest-asyncio 1.3.0 with asyncio_mode=auto: no decorators needed on plain async def test_ functions
- [Phase ?]: _route_all routes against _all_plugins to enable lazy-launch before active list is populated
- [Phase ?]: D-02 closed: nodriver handles stealth architecturally; Selenium imports gone
- [Phase ?]: Placeholder email SECURITY_CONTACT_PLACEHOLDER@example.com in SECURITY.md and CODE_OF_CONDUCT.md; maintainer must replace before launch
- [Phase ?]: Anchored /config.yml in .gitignore to repo root to prevent ISSUE_TEMPLATE/config.yml exclusion
- [Phase ?]: config.yml contact_links url points to SECURITY.md blob on master branch for private vulnerability reporting
- [Phase ?]: TaskGroup of per-plugin coroutines with 1.5s stagger and single write-queue drain via asyncio.Queue
- [Phase ?]: stdin listener thread uses loop.call_soon_threadsafe as the only thread-safe Event bridge; no direct event.set() from non-loop threads (ASYNC-03)
- [Phase ?]: run_in_executor used only for sqlite3 calls and stdin readline; nodriver browser work stays on the event loop (ASYNC-01 primary model)
- [Phase ?]: SoundNotifier: synchronous pygame calls (no executor, thread-safety unconfirmed)
- [Phase ?]: DiscordNotifier: secret-safe error logging (class+status only, never webhook URL or str(exc))
- [Phase ?]: Discord 429: raises RuntimeError with Retry-After; no retry loop in Phase 5 scope
- [Phase ?]: build_dispatcher factory selects notifiers from config flags; dedup edge-trigger notifies once per restock via get_item_notification_state_sync
- [Phase ?]: squareenix (no underscore) chosen for config key
- [Phase ?]: Naming difference is intentional and documented
- [Phase ?]: No separate helper module; Option A from RESEARCH Pattern 4
- [Phase ?]: getattr-chain platform_key lookup: no hardcoded class-name string munging for jitter config
- [Phase ?]: ANTI-02 UA always active -- falls back to DEFAULT_USER_AGENTS when platform user_agents empty
- [Phase ?]: SC1 registry gate
- [Phase 07-01]: BotService uses daemon thread with its own asyncio event loop for non-blocking start/stop from any sync caller
- [Phase 07-01]: stop() cancels task via loop.call_soon_threadsafe so async_main's finally block runs teardown_all (no orphaned Chrome)
- [Phase 07-01]: run() = asyncio.run(async_main(cfg, cvv)) identical to v1 behavior; CVV is a parameter only (never logged)
- [Phase ?]: parse_known_args() in core.service:main() avoids sys.argv contamination when test calls main() directly
- [Phase ?]: plugins/__init__.py added to make plugins/ a proper setuptools package; Phase 07-02 shoppybot entry point = core.service:main via pyproject.toml [project.scripts]
- [Phase 07-03]: main.py is now a thin shim: validate+seed+getpass CVV gate then BotService(cfg).run(cvv); asyncio.run and async_main imports removed from main.py (now internal to core/service.py)
- [Phase ?]: get_store lazy-fallback to EnvVarBackend keeps monkeypatch.setenv tests green (CRED-04)
- [Phase ?]: _build_store stub returns EnvVarBackend in plan 08-01; auto-detection keyring->file->env deferred to plan 08-03
- [Phase ?]: KeyringBackend uses SERVICE=shopbot hardcoded; keyring has no enumerate API so list() probes each SECRET_KEY individually (CRED-02)
- [Phase ?]: EncryptedFileBackend: scrypt n=2**14 + fresh 16B salt per write; fdopen-in-with + os.replace-outside for Windows-safe atomic write; InvalidToken -> ValueError(SHOPBOT_STORE_PASSPHRASE) (CRED-03)
- [Phase ?]: _build_store: explicit config > real keyring > encrypted-file (passphrase in env) > env-var; getpass deferred to explicit 'file' backend path only
