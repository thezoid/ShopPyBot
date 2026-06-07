---
phase: 07-modular-core-service
plan: 02
subsystem: infra
tags: [setuptools, pyproject, console-scripts, argparse, pip-install]

# Dependency graph
requires:
  - phase: 07-modular-core-service/07-01
    provides: core/service.py with BotService and main() entry point
provides:
  - pyproject.toml with build-system, project metadata, packages, and shoppybot console entry point
  - plugins/__init__.py making plugins/ a proper Python package
  - argparse --help guard in core.service:main() for clean shoppybot --help exit
affects:
  - 07-03-main-shim (uses same pyproject install)
  - 09-cli-package (extends the argparse parser added here)
  - 11-cross-platform-ci (validates pip install -e . on Ubuntu)

# Tech tracking
tech-stack:
  added: [setuptools>=61 as build backend]
  patterns: [pyproject.toml package declaration with explicit include/exclude, parse_known_args for entry-point --help guard]

key-files:
  created: [plugins/__init__.py]
  modified: [pyproject.toml, core/service.py]

key-decisions:
  - "parse_known_args() instead of parse_args() in main() so the test calling main() directly with pytest's sys.argv doesn't cause SystemExit(2)"
  - "plugins/__init__.py added (empty) to make plugins/ discoverable by setuptools package find; namespace packages avoided in favor of explicit __init__.py"
  - "find packages with include=[core*, plugins*, notifications*] and exclude=[tests*]; top-level single-file modules declared via py-modules"

patterns-established:
  - "Entry-point --help guard: argparse.ArgumentParser + parse_known_args() at top of main(); Phase 9 extends with real subcommands"
  - "pyproject.toml: [tool.setuptools.packages.find] with include/exclude lists for explicit package control"

requirements-completed: [MOD-03]

# Metrics
duration: 4min
completed: 2026-06-04
---

# Phase 7 Plan 02: pyproject.toml Package Metadata and Entry Point Summary

**setuptools pyproject.toml with shoppybot console entry point (core.service:main), explicit package discovery for core/plugins/notifications, and argparse --help guard so shoppybot --help exits cleanly**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-04T03:14:16Z
- **Completed:** 2026-06-04T03:18:23Z
- **Tasks:** 1
- **Files modified:** 3 (pyproject.toml, core/service.py, plugins/__init__.py created)

## Accomplishments
- Extended pyproject.toml: [build-system] with setuptools>=61, [project.scripts] shoppybot = core.service:main, package discovery (core*, plugins*, notifications*), py-modules for top-level single-file modules, [tool.pytest.ini_options] preserved verbatim
- Added `plugins/__init__.py` to make plugins/ a proper Python package for setuptools discovery
- Added argparse --help guard to core.service:main() using parse_known_args() so shoppybot --help exits 0 without starting the bot
- pip install -e . succeeds; shoppybot --help exits 0 and prints usage; 227 tests pass (no test modified)

## Task Commits

1. **Task 1: Extend pyproject.toml + argparse guard + plugins/__init__.py** - `9b775a1` (feat)

**Plan metadata:** (see final commit below)

## Files Created/Modified
- `E:\repos\ShopPyBot\pyproject.toml` - Added [build-system], [project.scripts], [tool.setuptools.packages.find], [tool.setuptools] py-modules; preserved [tool.pytest.ini_options]
- `E:\repos\ShopPyBot\plugins\__init__.py` - Empty file making plugins/ a proper Python package
- `E:\repos\ShopPyBot\core\service.py` - Added argparse import and --help guard (parse_known_args) in main()

## Decisions Made
- Used `parse_known_args()` instead of `parse_args()` so the existing `test_main_constructs_service_and_runs` test can call `main()` directly without sys.argv contamination causing SystemExit(2).
- Added `plugins/__init__.py` as a Rule 2 auto-fix: without it, setuptools `find_packages` skips plugins/ (no __init__.py = not a package), breaking `from plugins.shopbot_plugin_X import ...` imports after install.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] parse_args() -> parse_known_args() to avoid sys.argv contamination in test**
- **Found during:** Task 1 verification (pytest run)
- **Issue:** Initial implementation used `parser.parse_args()` which reads sys.argv; when the existing test `test_main_constructs_service_and_runs` calls `main()` directly, sys.argv contains `tests/ -q` (pytest args), causing SystemExit(2).
- **Fix:** Changed to `parser.parse_known_args()` which ignores unrecognized arguments; `--help` still exits 0, no bot starts.
- **Files modified:** core/service.py
- **Verification:** 227 tests pass; shoppybot --help still exits 0 and prints usage.
- **Committed in:** 9b775a1 (same task commit)

**2. [Rule 2 - Missing Critical] Added plugins/__init__.py**
- **Found during:** Task 1 (pyproject.toml authoring)
- **Issue:** plugins/ directory had no __init__.py; setuptools find_packages would skip it, making `from plugins.shopbot_plugin_X import ...` fail after pip install -e .
- **Fix:** Created empty plugins/__init__.py
- **Files modified:** plugins/__init__.py (created)
- **Verification:** pip install -e . succeeds; existing plugin import tests still pass (227 green).
- **Committed in:** 9b775a1 (same task commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug, 1 Rule 2 missing critical)
**Impact on plan:** Both fixes required for correctness. No scope creep.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- pip install -e . works; shoppybot --help resolves; full suite green
- Plan 03 (main.py shim wiring through BotService) can proceed immediately
- Phase 9 CLI can extend the argparse parser established in core.service:main()

---
*Phase: 07-modular-core-service*
*Completed: 2026-06-04*
