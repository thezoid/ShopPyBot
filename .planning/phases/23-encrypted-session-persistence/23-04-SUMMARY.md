---
phase: 23-encrypted-session-persistence
plan: "04"
subsystem: auth
tags: [nodriver, cdp, cookies, fernet, session-persistence, plugin-abc]

requires:
  - phase: 23-01
    provides: SessionStore + build_session_store() factory with Fernet save/restore
  - phase: 23-02
    provides: session_persistence bool on all 7 platform config models
  - phase: 22
    provides: relaunch() sequence on RetailerPlugin ABC (teardown->setup->restore_session->login)

provides:
  - Live restore_session() on RetailerPlugin ABC via raw CDP cdp_storage.set_cookies([CookieParam(...)])
  - save_session() on RetailerPlugin ABC reads live cookies via cdp_storage.get_cookies()
  - _dicts_to_cookie_params module-level helper with expiry filter and SameSite enum mapping
  - platform_key class attrs on AmazonPlugin and BestBuyPlugin
  - save_session() called after login success in AmazonPlugin and BestBuyPlugin
  - Startup restore wired into registry.setup_for_items (mirrors relaunch sequence)
  - 14 integration tests covering round-trip, restore-skips-login, save-after-login, and no-op guards

affects: [24-health-surface, any-phase-using-plugin-abc, any-new-plugin-with-session-persistence]

tech-stack:
  added: []
  patterns:
    - "Raw CDP cookie restore: tab.send(cdp_storage.set_cookies([CookieParam(...)])) never CookieJar.set_all()"
    - "getattr-safe platform config read: getattr(getattr(self.config, 'platforms', None), key, None)"
    - "Module-level CDP helper _dicts_to_cookie_params: expiry filter + SameSite enum + TimeSinceEpoch wrapping"
    - "Startup restore mirrors relaunch sequence in registry loop; login stays lazy in auto_buy"

key-files:
  created:
    - tests/test_session_persistence.py
  modified:
    - core/plugin_base.py
    - core/registry.py
    - plugins/shopbot_plugin_amazon.py
    - plugins/shopbot_plugin_bestbuy.py

key-decisions:
  - "restore_session checks store._passphrase is None directly (fast guard) rather than calling a separate helper; build_session_store() is still used for the actual restore/save ops"
  - "Startup registry loop calls restore_session() but NOT login() -- login stays lazy inside auto_buy() to avoid double-login or MFA block at startup (diverges from relaunch() which owns login explicitly)"
  - "CookieJar.set_all() prohibition documented in a code comment adjacent to the restore path (nodriver bug #1816/#2020 citation)"
  - "save_session() called inside the existing try block in login() -- if save_session raises, it is swallowed internally (save failure must never break login flow)"

patterns-established:
  - "CDP cookie round-trip: serialize to 8-field dict on save, build fresh CookieParam on restore (never pass network.Cookie to set_cookies)"
  - "_dicts_to_cookie_params is module-level so it is directly testable without a plugin instance"
  - "Registry startup restore: after plugin.setup() + _active_plugins.append(), call restore_session() and log skip-vs-lazy-login outcome"

requirements-completed: [REL-04]

duration: 12min
completed: 2026-06-12
---

# Phase 23 Plan 04: Live Session Restore + Save Summary

**RetailerPlugin ABC gets live CDP cookie restore (raw cdp_storage.set_cookies + CookieParam, bypassing the nodriver CookieJar.set_all bug) and a save_session() hook wired into Amazon/BestBuy login(); startup restore added to registry.setup_for_items to close the cold-restart MFA gap.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-12T00:00:00Z
- **Completed:** 2026-06-12T00:12:00Z
- **Tasks:** 3
- **Files modified:** 5 (4 source + 1 test)

## Accomplishments

- Replaced the Phase 22 no-op `restore_session()` stub with a live implementation that decrypts cookies from SessionStore and injects them via raw CDP `tab.send(cdp_storage.set_cookies([CookieParam(...)]))`, correctly filtering expired cookies and mapping SameSite strings to the `CookieSameSite` enum.
- Added `save_session()` to the ABC that reads live browser cookies via `cdp_storage.get_cookies()`, serializes the 8 CookieParam-compatible fields, and persists via `SessionStore.save()` -- wired into `AmazonPlugin.login()` and `BestBuyPlugin.login()` immediately after the success log.
- Wired `restore_session()` into `registry.setup_for_items()` after each `plugin.setup()`, closing the research-flagged startup gap (Pitfall 7) so the first run after a cold restart can skip login when a valid encrypted session exists.
- 14 integration tests passing: CookieParam type/SameSite/TimeSinceEpoch round-trip, past-expiry filtering, restore True + CDP path used + login skipped, restore False on disabled/no-passphrase/no-file, save writes encrypted file, save no-ops when disabled or passphrase absent.
- Full suite: 718 passed, 2 skipped, 0 failures (baseline was 704 passed 2 skipped; delta is the 14 new tests).

## Task Commits

1. **Task 1: Live restore_session + save_session on RetailerPlugin ABC** - `d90cdef` (feat)
2. **Task 2: platform_key, save_session hook in Amazon/BestBuy, startup restore in registry** - `c90a3f2` (feat)
3. **Task 3: Integration tests for session persistence** - `2a188c2` (test)

## Files Created/Modified

- `core/plugin_base.py` - Added `_dicts_to_cookie_params` module-level helper, `_session_platform_key`, `_session_enabled`, live `restore_session()`, and `save_session()`; added CDP + SessionStore imports
- `core/registry.py` - Extended `setup_for_items` loop to call `restore_session()` after `plugin.setup()` with skip-vs-lazy-login logging
- `plugins/shopbot_plugin_amazon.py` - Added `platform_key = "amazon"` class attr; `await self.save_session()` after "Signed in to Amazon" log
- `plugins/shopbot_plugin_bestbuy.py` - Added `platform_key = "bestbuy"` class attr; `await self.save_session()` after "Signed in to BestBuy" log
- `tests/test_session_persistence.py` - 14 integration tests (created)

## Decisions Made

- `restore_session()` fast-guards on `store._passphrase is None` directly: if the passphrase is absent, return False immediately without touching the tab. This is the same pattern used in `SessionStore.save/restore` internally, avoids a redundant restore() call, and makes the disabled-path zero-overhead.
- Startup registry loop does NOT call `login()` unconditionally: Amazon and BestBuy call `login()` lazily inside `auto_buy()`. Adding `login()` to the startup loop would either double-login (if restore returned True and the plugin auto-logged-in anyway) or block startup on MFA. The startup restore path primes the cookie jar; lazy login handles the case where restore returns False.
- `save_session()` is called inside the existing `try` block in each plugin's `login()`, not outside. If `save_session()` itself raises an unhandled exception, it swallows internally (the ABC method has its own try/except). The outer `try` block in `login()` provides an additional safety net, but the intent is the same: save failure must never surface to the caller.
- `CookieJar.set_all()` is prohibited and its prohibition documented in a code comment adjacent to the restore path, citing nodriver issues #1816/#2020. The acceptance criteria grep-counts the comment occurrence as acceptable (prohibition documentation, not executable code).

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered

None. All CDP imports resolved cleanly (`python -c "import core.plugin_base"` clean), existing test suites (test_relaunch.py, test_plugin_base.py, test_registry.py) stayed green, and the 14 new tests passed on first run.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The cookie persistence path (browser -> disk) was already in scope for this plan's threat model (T-23-09 through T-23-13). All threat mitigations implemented as planned:

- T-23-09: Fresh `CookieParam` always built from dicts; `CookieJar.set_all()` prohibited
- T-23-10: `expires < time.time()` filter in `_dicts_to_cookie_params`; test coverage in `test_cookie_param_past_expiry_filtered`
- T-23-11: Only `exc.__class__.__name__` logged on CDP errors in both methods
- T-23-12: Both methods have full try/except; registry restore is inside the existing exception handler
- T-23-13: `_session_enabled()` uses getattr-safe read with default False

## Known Stubs

None -- all session persistence hooks are fully wired. The `restore_session()` Phase 22 no-op stub has been completely replaced.

## User Setup Required

None -- no external service configuration required. Session persistence is opt-in via `session_persistence: true` in `config.yml` under the relevant platform and `SHOPBOT_STORE_PASSPHRASE` env var. Both are documented in sample.config.yml and the Phase 23 CONTEXT.md.

## Next Phase Readiness

Phase 23 (REL-04) is complete across all 4 plans. Phase 24 (Health Surface + Server Safety) can proceed. The plugin ABC is stable at PLUGIN_API_VERSION = 2 with all session persistence hooks additive.

## Self-Check: PASSED

- `core/plugin_base.py` exists with `cdp_storage.set_cookies` (2 occurrences) and `PLUGIN_API_VERSION = 2`
- `core/registry.py` contains `restore_session` in `setup_for_items`
- `plugins/shopbot_plugin_amazon.py` contains `platform_key` and `save_session`
- `plugins/shopbot_plugin_bestbuy.py` contains `platform_key` and `save_session`
- `tests/test_session_persistence.py` exists with 14 passing tests
- Commits: d90cdef, c90a3f2, 2a188c2 all verified in git log
- Full suite: 718 passed, 2 skipped, 0 failures

---
*Phase: 23-encrypted-session-persistence*
*Completed: 2026-06-12*
