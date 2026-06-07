---
phase: 01-foundations-security
plan: 05
subsystem: security
tags: [selenium, cdp, credentials, getpass, env-vars, fingerprint, hardening, disclaimer]

# Dependency graph
requires:
  - phase: 01-foundations-security
    provides: "AppConfig pydantic-settings schema (plan 03)"
  - phase: 01-foundations-security
    provides: "Cached logger / requirements pinning (plan 04)"
provides:
  - "Hardened main.py: no --disable-web-security, real UA, navigator.webdriver hidden via CDP"
  - "ChromeDriver subprocess output suppressed via Service(log_output=DEVNULL); Python exceptions remain visible"
  - "Credentials sourced from env vars (BB_EMAIL/BB_PASSWORD); CVV via runtime getpass, never on disk"
  - "AppConfig startup validation with clean SystemExit on ValidationError"
  - "Credential-free sample.config.yml, .env.example, SEC-06 README disclaimer"
affects: [phase-02-browser-automation, security, configuration, entrypoint]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Selenium navigator.webdriver suppression via CDP Page.addScriptToEvaluateOnNewDocument (Phase-1 bridge; nodriver replaces in Phase 2)"
    - "Runtime secret collection via getpass with non-interactive SystemExit guard (no input() echo fallback)"
    - "Credentials from os.environ only; never config.yml or logs"

key-files:
  created: [.env.example, .planning/phases/01-foundations-security/01-05-SUMMARY.md]
  modified: [main.py, core/config_schema.py, sample.config.yml, README.md]

key-decisions:
  - "SEC-04 satisfied on the existing Selenium driver in Phase 1 via CDP injection (per plan objective); removed when nodriver lands in Phase 2"
  - "open_browser defaulted to constant False since the schema's app block was removed; relocation to AppConfig deferred as follow-up (did not invent a new schema field)"
  - "Added SeleniumConfig to AppConfig so main.py can read cfg.selenium.driver_path (the plan-03 schema omitted it)"
  - "Expanded the existing README disclaimer rather than replacing it; added personal-use, TOS, and no-warranty language for SEC-06"
  - "CVV prompt fires only when a BestBuy item has auto_buy=True, avoiding an unnecessary prompt for check-only runs"

patterns-established:
  - "Driver-launch hardening lives in main() startup, surgical and pref-preserving"
  - "Secrets enter only at runtime (env + getpass), never persisted, never logged"

requirements-completed: [SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, INFRA-03]

# Metrics
duration: 11min
completed: 2026-06-02
---

# Phase 01 Plan 05: Driver and Credential Hardening Summary

**Hardened main.py to remove the --disable-web-security fingerprint, hide navigator.webdriver via a Selenium CDP injection, set a real Chrome UA, suppress ChromeDriver output without masking Python exceptions, and source all credentials from env vars + a runtime getpass CVV; stripped credentials from sample.config.yml, added .env.example, and added a personal-use/TOS/account-risk README disclaimer.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-06-02T13:20:00Z
- **Completed:** 2026-06-02T13:31:00Z
- **Tasks:** 3 (plus 1 approved blocking auto-fix)
- **Files modified:** 4 (1 created)

## Accomplishments
- SEC-03: `--disable-web-security` removed from Chrome options
- SEC-04: `navigator.webdriver` set to undefined via `driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", ...)` immediately after driver creation, before any navigation, with the Phase-1 decision recorded in a code comment
- SEC-05: real desktop Chrome UA string set (no HeadlessChrome / Selenium marker)
- INFRA-03: `sys.stdout/sys.stderr = devnull` hack replaced with `Service(driver_path, log_output=subprocess.DEVNULL)`; Python exceptions now surface normally
- SEC-01: BestBuy email/password read from `os.environ`; missing env vars log an actionable ERROR and skip the buy without crashing the loop
- SEC-02: CVV collected via `getpass.getpass` only when a BestBuy auto_buy item exists; `GetPassWarning` and empty/non-interactive cases `SystemExit` rather than echo
- CORE-05 wiring: `AppConfig()` instantiated in a try/except `ValidationError` with `SystemExit(1)`; all dict-form config reads converted to typed `cfg.*` access
- SEC-06: sample.config.yml credential block removed and replaced with a `platforms` section; `.env.example` documents the env var names; README disclaimer expanded

## Task Commits

Each task was committed atomically:

1. **Auto-fix: SeleniumConfig in AppConfig schema** - `e9f0f8d` (fix)
2. **Tasks 1+2: Harden driver setup and wire env-var credentials** - `22ab18a` (feat)
3. **Task 3: Strip sample credentials, add .env.example and disclaimer** - `fe62a42` (docs)

_Tasks 1 and 2 both patch main.py and were committed together as a single coherent main.py rewrite (driver setup + config/credential flow are interleaved in the same function)._

## Files Created/Modified
- `main.py` - Driver hardening (SEC-03/04/05, INFRA-03), AppConfig startup validation, env-var credentials + getpass CVV (SEC-01/02), typed config reads
- `core/config_schema.py` - Added `SeleniumConfig` model and `selenium` field on AppConfig
- `sample.config.yml` - Removed `app` credential block; added `platforms.amazon`/`platforms.bestbuy`; validates cleanly against AppConfig
- `.env.example` - Documents AMZ_EMAIL/AMZ_PWD/BB_EMAIL/BB_PASSWORD; notes CVV is runtime-only
- `README.md` - Expanded Disclaimer (personal use, retailer TOS, account suspension/ban risk, no warranty)

## Decisions Made
- SEC-04 was satisfied on the existing Selenium driver per the plan objective, not deferred to Phase 2. A code comment records that the CDP call is removed when nodriver replaces Selenium.
- `open_browser` was defaulted to a constant `False` because the schema no longer carries an `app` block; relocation into AppConfig is a documented follow-up (no new schema field invented, per plan instruction).
- The CVV prompt is conditional on a BestBuy auto_buy item existing, so check-only runs are not interrupted.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing SeleniumConfig in AppConfig schema**
- **Found during:** Task 1 (driver setup patch)
- **Issue:** Task 1 routes `get_chromedriver_path(cfg)` to read `cfg.selenium.driver_path`, but the plan-03 AppConfig schema had no `selenium` section, so the attribute access would fail at runtime.
- **Fix:** Added a `SeleniumConfig(BaseModel)` with `driver_path: str = "chromedriver"` and wired a `selenium: SeleniumConfig` field onto AppConfig.
- **Files modified:** core/config_schema.py
- **Verification:** `AppConfig(yaml_file='sample.config.yml').selenium.driver_path` resolves; full suite 15 passed
- **Committed in:** e9f0f8d (human-approved before commit)

**2. [Rule 2 - Missing critical functionality] README disclaimer lacked TOS/personal-use language**
- **Found during:** Task 3 (README disclaimer)
- **Issue:** The existing `### Disclaimer` covered only Amazon account-restriction risk; SEC-06 requires personal-use, Terms-of-Service, and no-warranty coverage.
- **Fix:** Expanded the disclaimer in place (preserving the original account-restriction text) to add personal/non-commercial use, retailer TOS compliance responsibility, account suspension/ban risk, and an as-is/no-warranty clause.
- **Files modified:** README.md
- **Verification:** README contains "disclaimer" and "terms of service"; Task 3 verify passed
- **Committed in:** fe62a42

---

**Total deviations:** 2 (1 blocking schema fix, 1 SEC-06 disclaimer expansion)
**Impact on plan:** None on deliverables; both deviations were required to satisfy the plan's own acceptance criteria.

## Known Stubs
- `open_browser` is hardcoded to `False` in main.py. This is intentional and documented: the schema's `app` block was removed for SEC-01, and the plan explicitly forbade inventing a new schema field. Relocation of `open_browser` into AppConfig is a tracked follow-up. It does not block the plan goal (credential/driver hardening).

## Threat Flags
None. All security-relevant surface in the changed files maps to dispositions already in the plan's threat register (T-01-WD, T-01-DWS, T-01-CVV, T-01-ENV, T-01-STDERR, T-01-LOGLEAK), all dispositioned `mitigate` and implemented.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## User Setup Required
- Before running with BestBuy auto-buy, export `BB_EMAIL` and `BB_PASSWORD` (and `AMZ_EMAIL`/`AMZ_PWD` for Amazon) as environment variables or place them in a gitignored `.env`. See `.env.example`.
- The BestBuy CVV is entered at a hidden runtime prompt; it is never stored.

## Next Phase Readiness
- Phase 2 (nodriver migration) will remove the Phase-1 CDP `navigator.webdriver` patch; nodriver handles this architecturally.
- The `open_browser` schema relocation remains an open follow-up for a future plan.
- Entry point now validates config at startup and fails fast with a readable message on bad config.

## Self-Check: PASSED

All created/modified files exist (main.py, core/config_schema.py, sample.config.yml, .env.example, README.md, 01-05-SUMMARY.md) and all task commits (e9f0f8d, 22ab18a, fe62a42) are present in git history.

---
*Phase: 01-foundations-security*
*Completed: 2026-06-02*
