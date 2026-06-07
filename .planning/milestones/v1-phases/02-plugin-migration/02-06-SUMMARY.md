---
phase: 02-plugin-migration
plan: "06"
subsystem: plugin-framework
tags: [nodriver, asyncio, importlib, abc, contributor-tooling]

requires:
  - phase: 02-plugin-migration
    plan: "02"
    provides: "RetailerPlugin v2 ABC (async methods, setup/teardown, domain_patterns)"

provides:
  - "plugins/example_plugin.py: FakeShopPlugin skeleton contributors copy as starting point"
  - "plugins/PLUGIN_DEV.md: complete contributor guide covering naming, ABC contract, domain_patterns, config, credentials, testing"
  - "tests/test_example_plugin.py: ABC compliance test for example_plugin"

affects: [03-contributor-onboarding, docs-phase]

tech-stack:
  added: []
  patterns:
    - "example_plugin.py named outside shopbot_plugin_*.py pattern so registry ignores it as template"
    - "importlib.util.spec_from_file_location used in tests to mirror registry discovery"
    - "TDD: RED commit (failing test) before GREEN commit (implementation)"

key-files:
  created:
    - plugins/example_plugin.py
    - plugins/PLUGIN_DEV.md
    - tests/test_example_plugin.py
  modified: []

key-decisions:
  - "FakeShopPlugin named example_plugin.py (not shopbot_plugin_*.py) so the registry ignores it at runtime"
  - "Test uses importlib.util.spec_from_file_location to mirror actual registry loading path"
  - "PLUGIN_DEV.md section 4 covers D-08 extensibility caveat honestly: community config keys require core edit today"

patterns-established:
  - "Contributor skeleton lives in plugins/ with non-discovery name; PLUGIN_DEV.md cross-references it"
  - "ABC compliance test: spec_from_file_location load + issubclass + config=None instantiation"

requirements-completed: [CORE-08]

duration: 15min
completed: 2026-06-02
---

# Phase 02 Plan 06: Contributor Tooling Summary

**FakeShopPlugin skeleton (example_plugin.py) plus PLUGIN_DEV.md contributor guide covering naming, ABC contract, domain_patterns, credentials, and testing: contributors can build a working plugin without reading core source**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-02
- **Completed:** 2026-06-02
- **Tasks:** 2 (Task 1 TDD, Task 2 doc)
- **Files modified:** 3 created

## Accomplishments

- FakeShopPlugin subclasses RetailerPlugin v2, implements setup/check_availability/auto_buy/teardown with heavy inline comments and a "Replace with real selector" marker
- plugins/PLUGIN_DEV.md covers all 7 required sections: naming convention, ABC contract table, domain_patterns semantics, config access with D-08 caveat, env-vars-only credentials, pytest command, trust note
- Full test suite remains green (45 passed); two new tests verify import and ABC compliance via importlib path

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: failing tests** - `4512c51` (test)
2. **Task 1 GREEN: example_plugin.py** - `ec93dc6` (feat)
3. **Task 2: PLUGIN_DEV.md** - `f042239` (docs)

**Plan metadata:** (this summary commit)

Note: Task 1 followed TDD with separate RED and GREEN commits.

## Files Created/Modified

- `plugins/example_plugin.py`: FakeShopPlugin skeleton with inline comments; named outside shopbot_plugin_*.py so registry skips it
- `plugins/PLUGIN_DEV.md`: Contributor guide: naming, ABC table, domain_patterns, config, credentials (env only), testing, trust note
- `tests/test_example_plugin.py`: test_example_plugin_imports and test_example_plugin_satisfies_abc using spec_from_file_location

## Decisions Made

- Named the example file `example_plugin.py` (not `shopbot_plugin_example.py`) so the live registry ignores it. The file's docstring explains this choice.
- Test file uses `importlib.util.spec_from_file_location` with the same code path the registry uses, proving discovery-compatibility without actually running discovery on the plugins directory.
- PLUGIN_DEV.md section 4 acknowledges the D-08 gap honestly: adding config keys for a new community platform requires editing `core/config_schema.py` today; flexible per-platform sections are deferred.

## Deviations from Plan

None: plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced.
example_plugin.py contains no credentials, no hardcoded secrets. PLUGIN_DEV.md states
the env-vars-only rule (T-02-17) and the plugin-trust note (T-02-16). Both threat model
mitigations confirmed closed.

## Issues Encountered

None.

## Known Stubs

`plugins/example_plugin.py` is intentionally stub-like: `check_availability` uses `"#add-to-cart"` and `auto_buy` navigates to `"https://www.fakeshop.com/checkout"`. These are fictional placeholders with explicit "Replace with real selector" comments. They are the feature, not a gap: the file is a copy-paste template, not a production plugin.

## Next Phase Readiness

- CORE-08 satisfied: contributor tooling is complete
- Phase 2 Wave 2 is now fully committed (plan 06 was the last Wave 2 plan)
- A contributor can copy example_plugin.py, rename it shopbot_plugin_<name>.py, and follow PLUGIN_DEV.md to ship a working plugin without reading core source

## Self-Check

Files exist:
- plugins/example_plugin.py: FOUND
- plugins/PLUGIN_DEV.md: FOUND
- tests/test_example_plugin.py: FOUND

Commits exist:
- 4512c51 (RED test): FOUND
- ec93dc6 (feat example_plugin): FOUND
- f042239 (docs PLUGIN_DEV.md): FOUND

Test suite: 45 passed, 0 failed.

## Self-Check: PASSED

*Phase: 02-plugin-migration*
*Completed: 2026-06-02*
