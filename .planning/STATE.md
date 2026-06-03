---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Phase complete — ready for verification
last_updated: "2026-06-03T00:32:54.891Z"
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 11
  completed_plans: 9
  percent: 17
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

Phase: 01 (foundations-security) — EXECUTING
Plan: 5 of 5
**Phase**: 1 — Foundations + Security
**Plan**: 0 of 5 executed
**Status**: Planned — ready to execute

```
Progress: [ Phase 1 ][ Phase 2 ][ Phase 3 ][ Phase 4 ][ Phase 5 ]
           [  0%    ] [  0%   ] [  0%   ] [  0%   ] [  0%   ]
```

**Overall**: 0/39 requirements complete (0%)

---

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

**Last action**: Completed plan 01-04 — requirements.txt pinned/deduped (INFRA-01) and logger.py caches level at import (INFRA-02); 15 tests passing
**Next action**: Execute plan 01-05 (security hardening patches to main.py: AppConfig instantiation with ValidationError catch, selenium Service log_output)
**Context to carry**: requirements.txt now exact-pinned; nodriver==0.50.3 and pydantic-settings[yaml]==2.14.0 locked and human-verified. logger._LOGGING_LEVEL caches the level at import; do not re-add per-call config reads. AppConfig uses yaml_file= kwarg for injection (not _yaml_file=). core/config_schema.py is complete; main.py (plan 05) should instantiate AppConfig() with ValidationError catch. selenium pinned at 4.43.0 for Service log_output in plan 05.

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
