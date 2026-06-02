# ShopPyBot — State

## Project Reference

**Core Value**: Drop-in plugin framework — community adds retail platform integrations via a single Python file in `plugins/`; no core changes required.

**Project**: ShopPyBot
**Milestone**: v1 Open Source Launch
**Total Phases**: 6
**Total Requirements**: 44

---

## Current Position

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

**Last action**: Phase 1 planned — 5 plans across 3 waves, verified by plan-checker (all 14 reqs covered, all 12 dimensions pass)
**Next action**: `/gsd-execute-phase 1` — execute Phase 1: Foundations + Security
**Context to carry**: SEC-04 decided — satisfy navigator.webdriver hiding on existing Selenium driver via CDP patch in Phase 1 (NOT deferred to Phase 2 nodriver). Plan 01-04 has a blocking human-verify checkpoint for nodriver/pydantic-settings package legitimacy. Phase 1 creates core/plugin_base.py + core/config_schema.py; does NOT touch amazon_bot.py/bestbuy_bot.py.

---

*Last updated: 2026-06-02 — Phase 1 planned by gsd-plan-phase*
