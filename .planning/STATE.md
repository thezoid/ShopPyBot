# ShopPyBot — State

## Project Reference

**Core Value**: Drop-in plugin framework — community adds retail platform integrations via a single Python file in `plugins/`; no core changes required.

**Project**: ShopPyBot
**Milestone**: v1 Open Source Launch
**Total Phases**: 5
**Total Requirements**: 39

---

## Current Position

**Phase**: 2 — Plugin Migration (Phase 1 complete)
**Plan**: None started
**Status**: Phase 1 verified PASS 2026-05-12; ready for Phase 2 planning

```
Progress: [ Phase 1 ][ Phase 2 ][ Phase 3 ][ Phase 4 ][ Phase 5 ]
           [  0%    ] [  0%   ] [  0%   ] [  0%   ] [  0%   ]
```

**Overall**: 14/39 requirements complete (36%)

---

## Phase Status

| Phase | Goal Summary | Status | Reqs |
|-------|-------------|--------|------|
| 1 — Foundations + Security | Plugin ABC locked, Pydantic config, all security hardened | Complete (14/14 reqs) | 14 |
| 2 — Plugin Migration | Amazon/BestBuy on ABC, registry operational, contributor docs | Not started | 6 |
| 3 — Async Orchestrator | Concurrent plugins, WAL SQLite, no blocking I/O | Not started | 5 |
| 4 — Notification System | Fan-out dispatcher, deduplication, all channels | Not started | 6 |
| 5 — Platform Expansion | 5 new plugins, anti-detection config per platform | Not started | 8 |

---

## Performance Metrics

**Plans completed**: 6
**Requirements completed**: 14
**Phases completed**: 1
**Blockers resolved**: 4 (shared driver, per-call yaml load, plaintext creds, --disable-web-security)

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

**Last action**: Phase 1 executed autonomously: 6 plans across 4 waves, 18 atomic commits, verifier PASS 14/14 reqs
**Next action**: `/gsd-plan-phase 2` — plan Phase 2: Plugin Migration
**Context to carry**: Plugin ABC contract is locked (`plugin_base.py`, `PLUGIN_API_VERSION = 1`, D-01 driver-arg drop). Phase 2 migrates `amazon_bot.py` and `bestbuy_bot.py` to the ABC and wires the plugin registry. Non-blocking Phase 1 follow-ups noted in VERIFICATION.md (tests/test_utils.py stale, README "Python 3.8+" line, _deprecated/ folder needs scrubbing pre-OSS).

---

*Last updated: 2026-04-19 — initialized by gsd-roadmap*
