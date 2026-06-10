---
phase: 15-plugin-ecosystem-registry
plan: 01
subsystem: testing
tags: [plugin-base, abc, typing, literal, registry, tdd]

# Dependency graph
requires:
  - phase: 14-anti-detection-layer-2-captcha-solving
    provides: stable plugin ABC with _captcha_solver injection; PLUGIN_API_VERSION=2 baseline

provides:
  - RetailerPlugin ABC exposes difficulty/requires_proxy/requires_captcha class attrs with defaults
  - __init_subclass__ validates difficulty against {"easy","medium","hard"} at class-definition time
  - 4 new tests proving defaults, override, invalid-difficulty rejection, and existing-plugin smoke

affects: [15-02, 15-03, plugins-list-cli, plugin-dev-docs]

# Tech tracking
tech-stack:
  added: ["typing.Literal (stdlib, no new dep)"]
  patterns:
    - "__init_subclass__ for fail-fast import-time attribute validation"
    - "Additive class attributes with defaults (non-breaking ABC extension)"

key-files:
  created: []
  modified:
    - core/plugin_base.py
    - tests/test_plugin_base.py

key-decisions:
  - "__init_subclass__ chosen as difficulty validation enforcement point: fails at class-definition time, not at runtime or CLI time; plugins omitting difficulty inherit medium and are never invalidated"
  - "PLUGIN_API_VERSION stays 2: additive class attributes are non-breaking per RESEARCH Pattern 1"
  - "frozenset used for O(1) membership test in __init_subclass__"

patterns-established:
  - "Pattern: Non-breaking ABC extension via class attributes with defaults + __init_subclass__ validation"

requirements-completed: [REG-02]

# Metrics
duration: 8min
completed: 2026-06-09
---

# Phase 15 Plan 01: Plugin Registry Metadata Attributes Summary

**Three additive class attrs (difficulty/requires_proxy/requires_captcha) on RetailerPlugin ABC with __init_subclass__ import-time difficulty validation; all 7 existing plugins load unchanged with defaults**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-09T21:32:43Z
- **Completed:** 2026-06-09T21:40:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `difficulty: Literal["easy","medium","hard"] = "medium"`, `requires_proxy: bool = False`, `requires_captcha: bool = False` to `RetailerPlugin` ABC
- Added `__init_subclass__` hook that raises `ValueError` for any `difficulty` value outside the allowed frozenset at class-definition time (import-time fail-fast, T-15-01 mitigation)
- `PLUGIN_API_VERSION` stays 2; no new dependencies added (stdlib `typing.Literal` only)
- 4 new tests: defaults, override, invalid-difficulty raises, existing-plugin smoke (>= 7 classes load with valid defaults)
- Full suite: 483 passed, 2 skipped (baseline 479 + 4 new)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add 3 registry attrs + __init_subclass__ to RetailerPlugin** - `384ce91` (feat)
2. **Task 2: Extend test_plugin_base with 3 additional assertions** - `0d563e3` (test)

**Plan metadata:** (docs commit follows)

_Note: Both tasks used TDD (RED: failing test written first; GREEN: impl added; suite verified)_

## Files Created/Modified

- `core/plugin_base.py` - Added `from typing import Literal`, `_VALID_DIFFICULTY` frozenset, 3 class attrs with defaults, `__init_subclass__` validation hook
- `tests/test_plugin_base.py` - Added `from pathlib import Path` import; added `test_defaults`, `test_override`, `test_invalid_difficulty_raises`, `test_existing_plugins_load`

## Decisions Made

- `__init_subclass__` chosen as the difficulty validation enforcement point: import-time fail-fast is the cleanest approach; a plugin author typo fails loudly at discovery rather than silently at runtime. Plugins that omit `difficulty` inherit "medium" and are never invalidated by this hook.
- `PLUGIN_API_VERSION` stays 2: additive class attributes with defaults do not change `__abstractmethods__` and have no compatibility implications (RESEARCH Pattern 1 / Anti-Patterns confirm).
- `frozenset` used for the allow-list to provide O(1) membership test and immutability.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 (plugins list CLI) can read `difficulty`, `requires_proxy`, `requires_captcha` off any plugin instance via plain attribute access
- Plan 03 (wiki registry docs) can reference the three attrs as the machine-readable contract
- All 7 existing plugins confirmed loading with defaults; no breaking changes introduced

## Threat Surface Scan

T-15-01 (Tampering via `difficulty` string) mitigated as planned: `__init_subclass__` validates against the 3-value allow-list at class-definition time. No new threat surface introduced beyond what was in the threat model.

---
*Phase: 15-plugin-ecosystem-registry*
*Completed: 2026-06-09*

## Self-Check: PASSED

- `core/plugin_base.py` contains `difficulty`, `requires_proxy`, `requires_captcha`, `__init_subclass__`: FOUND
- `tests/test_plugin_base.py` contains `requires_proxy`: FOUND
- Commit `384ce91` exists: FOUND
- Commit `0d563e3` exists: FOUND
- `PLUGIN_API_VERSION == 2`: VERIFIED (python -c "import core.plugin_base; print(core.plugin_base.PLUGIN_API_VERSION)")
- Full suite 483 passed, 2 skipped: VERIFIED
