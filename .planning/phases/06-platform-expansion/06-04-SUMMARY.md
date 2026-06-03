---
phase: 06-platform-expansion
plan: "04"
subsystem: plugins
tags: [PLG-07, PLG-08, ANTI-02, ANTI-03, nodriver, plugin]
dependency_graph:
  requires: ["06-01", "06-02"]
  provides: [SquareEnixPlugin, NeweggPlugin]
  affects: [plugins/shopbot_plugin_squareenix.py, plugins/shopbot_plugin_newegg.py]
tech_stack:
  added: []
  patterns: [RetailerPlugin-v2-subclass, nodriver-browser-args-UA, per-platform-headless]
key_files:
  created:
    - plugins/shopbot_plugin_squareenix.py
    - plugins/shopbot_plugin_newegg.py
    - tests/test_plugin_squareenix.py
    - tests/test_plugin_newegg.py
  modified: []
decisions:
  - "Broad domain pattern 'store.square-enix-games.com' covers na.store.* and future regional prefixes via substring match (RESEARCH Pitfall 1)"
  - "Always apply --user-agent= browser_args regardless of whether platform ua_list is empty; fall back to DEFAULT_USER_AGENTS (consistent with Walmart plugin pattern)"
  - "newegg.ca included in domain_patterns for Canadian store coverage at zero cost"
metrics:
  duration: "4 minutes"
  completed: "2026-06-03"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
---

# Phase 06 Plan 04: Square Enix + NewEgg Plugins Summary

**One-liner:** SquareEnixPlugin (PLG-07) and NeweggPlugin (PLG-08) delivered as self-contained RetailerPlugin v2 subclasses with broad domain matching, ANTI-02 UA rotation, and ANTI-03 headless toggle wired in setup().

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Square Enix plugin (PLG-07) | 10e5002 | plugins/shopbot_plugin_squareenix.py, tests/test_plugin_squareenix.py |
| 2 | NewEgg plugin (PLG-08) | f11733b | plugins/shopbot_plugin_newegg.py, tests/test_plugin_newegg.py |

## Verification Results

- tests/test_plugin_squareenix.py: 15 passed
- tests/test_plugin_newegg.py: 15 passed
- Full suite: 205 passed, 1 skipped (pre-existing), 2 warnings (pre-existing)

## Decisions Made

1. **Broad SE domain pattern:** Used `"store.square-enix-games.com"` (not `"na.store.square-enix-games.com"`) so the registry's substring match covers the NA store and any other regional prefix (apac.store.*, etc.). Verified by a dedicated routing test that checks the na.store.* hostname against domain_patterns.

2. **UA always applied:** Both plugins always pass `--user-agent=` in browser_args whether or not the platform config list is non-empty; when empty they fall back to DEFAULT_USER_AGENTS. This matches the Walmart plugin's behavior and ensures ANTI-02 coverage even in default-config deployments.

3. **newegg.ca included:** Added alongside newegg.com at no cost; both patterns are substring-matched by the registry.

## Deviations from Plan

None. Plan executed exactly as written. Both plugins mirror the Walmart template structure from Plan 06-03.

## Known Stubs

All selectors in both plugins carry explicit `# TODO: verify selectors against live <site>` markers. These are intentional per plan spec; live selector verification requires access to the retail sites and is out of scope for this phase.

| File | Location | Reason |
|------|----------|--------|
| plugins/shopbot_plugin_squareenix.py | check_availability, auto_buy, login | Selectors unverifiable without live na.store.square-enix-games.com access |
| plugins/shopbot_plugin_newegg.py | check_availability, auto_buy, login | Selectors unverifiable without live newegg.com access |

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model (T-06-10 through T-06-12). Both plugins follow the established credential-env-var-only pattern (SEC-01) and do not introduce new network endpoints or auth paths beyond the plugin's own browser session.

## Self-Check: PASSED
