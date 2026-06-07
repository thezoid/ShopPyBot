# Phase 2: Plugin Migration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-02
**Phase:** 2-plugin-migration
**Areas discussed:** Driver tech & concurrency, ABC interface revision, Driver lifecycle / instantiation, domain_pattern routing format

---

## Driver tech & concurrency

### Q1 — Which driver does each plugin own?

| Option | Description | Selected |
|--------|-------------|----------|
| Selenium now, nodriver later | Sync Selenium per plugin, reuse DOM code, defer nodriver | |
| nodriver now (async migration) | Port both platforms to nodriver async; remove CDP patch | ✓ |
| You decide | Claude locks choice | |

**User's choice:** nodriver now (async migration)
**Notes:** Accepts the larger blast radius (rewrite check/buy as async + convert main loop). Honors the locked `nodriver==0.50.3` dep and the Phase-1 note that nodriver replaces Selenium in Phase 2.

### Q2 — Concurrent or sequential execution?

| Option | Description | Selected |
|--------|-------------|----------|
| Async plumbing, sequential execution | Async interface/loop, await one item at a time | ✓ |
| Async + concurrent now | asyncio.gather across plugins/items this phase | |
| You decide | Claude locks choice | |

**User's choice:** Async plumbing, sequential execution
**Notes:** Concurrency deferred to its own roadmap phase; keeps Phase 2 a clean migration.

### Q3 — nodriver isolation granularity?

| Option | Description | Selected |
|--------|-------------|----------|
| One Browser process per plugin | Separate Chrome process + profile per plugin | ✓ |
| Shared Browser, one tab per plugin | Lighter, shares cookies/fingerprint | |
| You decide | Claude locks choice | |

**User's choice:** One Browser process per plugin
**Notes:** Matches PLG-03 "no shared global driver"; accepts one Chrome process per active plugin.

---

## ABC interface revision

### Q1 — Revised RetailerPlugin shape?

| Option | Description | Selected |
|--------|-------------|----------|
| Async, self.driver, async setup() + version 2 | Drop driver param, async methods, setup()/teardown(), bump API version | ✓ |
| Async, driver built in __init__ (sync stub) | asyncio.run inside __init__ (nested-loop risk) | |
| You decide | Claude locks interface | |

**User's choice:** Async, self.driver, async setup() + version 2
**Notes:** `async setup()` reconciles PLG-03's "driver in __init__" with nodriver's async start. PLUGIN_API_VERSION 1 → 2 supersedes the Phase-1 "locked" v1 ABC.

### Q2 — Config object passed to plugins?

| Option | Description | Selected |
|--------|-------------|----------|
| Typed AppConfig now, defer extensibility | Whole typed AppConfig; community-config gap deferred | ✓ |
| Raw dict per platform section | Extensible for community plugins, loses pydantic validation | |
| You decide | Claude locks choice | |

**User's choice:** Typed AppConfig now, defer extensibility
**Notes:** Reuses Phase-1 typing. AppConfig's fixed amazon/bestbuy fields mean new community platforms need a core edit until the per-platform-config phase — explicitly deferred.

---

## Driver lifecycle / instantiation

### Q1 — When does each plugin's browser launch?

| Option | Description | Selected |
|--------|-------------|----------|
| Eager discovery, lazy browser launch | Instantiate all; setup() only for plugins with matching items | ✓ |
| Eager everything at startup | setup() every plugin at startup (all browsers open) | |
| You decide | Claude locks choice | |

**User's choice:** Eager discovery, lazy browser launch
**Notes:** Only pay for browsers in use; teardown() launched plugins at shutdown.

---

## domain_pattern routing format

### Q1 — How does a plugin declare URLs it handles?

| Option | Description | Selected |
|--------|-------------|----------|
| List of substring domains, matched on host | domain_patterns: list[str]; urlparse host substring match | ✓ |
| Single substring string | domain_pattern: str, one domain | |
| Regex pattern | Most flexible, higher contributor bar | |

**User's choice:** List of substring domains, matched on host
**Notes:** Handles multi-TLD retailers; matching `urlparse(url).hostname` avoids path/query false hits; simplest contributor ergonomics short of a single string.

---

## Claude's Discretion

- Registry file location and internal structure.
- `example_plugin.py` demo platform choice and `PLUGIN_DEV.md` outline (must satisfy criterion 4).
- Exact warning text/log level for non-matching `.py` files; handling of plugins that fail import / `setup()` (recommend log + skip, don't crash).

## Deferred Ideas

- Real concurrent / parallel item checking (asyncio.gather) — own phase.
- Per-platform flexible config sections for community plugins — own phase.
- New platforms (Walmart, Target, GameStop, Square Enix, NewEgg) — later phases.
