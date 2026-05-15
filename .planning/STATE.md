# ShopPyBot — State

## Project Reference

**Core Value**: Drop-in plugin framework — community adds retail platform integrations via a single Python file in `plugins/`; no core changes required.

**Project**: ShopPyBot
**Milestone**: v1 Open Source Launch
**Total Phases**: 6
**Total Requirements**: 44

---

## Current Position

**Phase**: 6 — Platform Expansion (Phase 5 complete)
**Plan**: None started
**Status**: Phase 5 verified PASS 2026-05-15 (6/6 NOTIF reqs; twilio install needed before merge so SMS tests collect)

```
Progress: [ Phase 1 ][ Phase 2 ][ Phase 3 ][ Phase 4 ][ Phase 5 ]
           [  0%    ] [  0%   ] [  0%   ] [  0%   ] [  0%   ]
```

**Overall**: 36/44 requirements complete (82%)

---

## Phase Status

| Phase | Goal Summary | Status | Reqs |
|-------|-------------|--------|------|
| 1 — Foundations + Security | Plugin ABC locked, Pydantic config, all security hardened | Complete (14/14 reqs) | 14 |
| 2 — Plugin Migration | Amazon/BestBuy on ABC, registry operational, contributor tooling | Complete (6/6 reqs) | 6 |
| 3 — Community Documentation | CONTRIBUTING.md, SECURITY.md, issue/PR templates | Complete (5/5 reqs) | 5 |
| 4 — Async Orchestrator | Concurrent plugins, WAL SQLite, no blocking I/O | Complete (5/5 reqs) | 5 |
| 5 — Notification System | Fan-out dispatcher, deduplication, all channels | Complete (6/6 reqs) | 6 |
| 6 — Platform Expansion | 5 new plugins, anti-detection config per platform | Not started | 8 |

---

## Performance Metrics

**Plans completed**: 11
**Requirements completed**: 20
**Phases completed**: 2
**Blockers resolved**: 5 (Phase 1: shared driver, per-call yaml load, plaintext creds, --disable-web-security; Phase 2: missing update_item_purchased in BestBuy auto_buy)

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

**Last action**: Phase 2 executed autonomously: 5 plans across 3 waves, 15 atomic commits, verifier PASS 6/6 reqs, all 4 locked decisions D-01..D-04 verified, 91 Phase-2 tests passing.
**Next action**: `/gsd-plan-phase 3` — plan Phase 3: Community Documentation (CONTRIBUTING.md, SECURITY.md, issue/PR templates).
**Context to carry**: Plugin framework is operational end-to-end. amazon_bot.py and bestbuy_bot.py are deleted; plugins/shopbot_plugin_amazon.py + plugins/shopbot_plugin_bestbuy.py + plugin_registry.py + plugins/PLUGIN_DEV.md are the public surface. Phase 3 should link CONTRIBUTING.md to PLUGIN_DEV.md rather than duplicating contract details. Non-blocking follow-ups (carried from Phase 1+2 VERIFICATION.md): tests/test_utils.py + tests/test_models.py pre-existing collection errors, README "Python 3.8+" line, _deprecated/ folder needs scrubbing pre-OSS launch.

---

*Last updated: 2026-04-19 — initialized by gsd-roadmap*
