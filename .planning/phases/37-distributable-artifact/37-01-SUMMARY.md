---
phase: 37-distributable-artifact
plan: 01
subsystem: infra
tags: [packaging, setuptools, wheel, importlib-resources, package-data, pyproject]

# Dependency graph
requires:
  - phase: 36-mainline-reconciliation
    provides: "master carrying the full v4.1+v4.2 surface with green CI, so packaging changes land on the real codebase"
provides:
  - "core/sounds/ as a real importable package carrying the three bundled alert WAVs"
  - "utils.SOUNDS_DIR resolved through importlib.resources.files('core.sounds') instead of a module-relative path"
  - "[tool.setuptools.package-data] declarations that put all 9 data files into the built wheel"
  - "scripts/ as the out-of-package home for dev tooling"
  - "tests/test_packaging.py as the in-tree data-file guard"
affects: [37-02 dependency declaration, 37-04 CI wheel job, 43 plugin roots]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "package-data resolution via importlib.resources rather than os.path.dirname(__file__)"
    - "dev tooling lives in scripts/, outside every packages.find include pattern"

key-files:
  created:
    - core/sounds/__init__.py
    - core/sounds/notification.wav
    - core/sounds/available.wav
    - core/sounds/buy.wav
    - scripts/generate_alert_sounds.py
    - tests/test_packaging.py
  modified:
    - utils.py
    - pyproject.toml
    - README.md
    - CLAUDE.md

key-decisions:
  - "Sounds relocated to core/sounds/ as a real package, not a bare data directory, so packages.find discovers it deterministically regardless of the namespaces default"
  - "No try/except fallback around the resolution: a broken install must fail loudly at import rather than silently resolve to a repo-relative path"
  - "static/vendor/* declared as its own glob because static/* does not descend"
  - "MANIFEST.in was NOT needed; the package-data globs alone shipped all 9 files"

patterns-established:
  - "Packaging claims are proven by inspecting a built wheel's zip entry list, never by reading pyproject.toml back"
  - "Wheel builds go to the session scratchpad; build/ and *.egg-info/ byproducts are removed from the repo root after each build"

requirements-completed: [PKG-01]

# Metrics
duration: 12min
completed: 2026-08-03
---

# Phase 37 Plan 01: Data Files in the Wheel Summary

**The built wheel grew from 61 entries to 71, now carrying the 3 bundled alert WAVs under `core/sounds/` and all 6 `web/static` and `web/templates` files, proven by inspecting a real build's zip entry list.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-03T21:43Z
- **Completed:** 2026-08-03T21:55Z
- **Tasks:** 2 of 2
- **Files modified:** 11 (6 created, 4 modified, 4 of the creations being `git mv` renames)

## Accomplishments

- **Made the sounds structurally shippable.** They were not merely unshipped: `utils` is a top-level module, so `SOUNDS_DIR = os.path.join(os.path.dirname(__file__), 'sounds')` resolved to `site-packages/sounds`, which could not be package data of anything because `sounds` was not a package. Relocating to `core/sounds/` and resolving through `importlib.resources.files("core.sounds")` fixes the class of defect, not just the symptom.
- **Proved the fix against a real artifact.** Two independent builds (one after the `pyproject.toml` edit, one from the fully committed tree) produced identical, asserted entry counts.
- **Kept dev tooling out of the shipped tree.** `generate_alert_sounds.py` moved to `scripts/`, outside every `packages.find` include pattern, and its absence from the wheel is asserted.

## Observed Wheel Contents

Exact counts from `zipfile.ZipFile(whl).namelist()` on `shoppybot-2.0.0-py3-none-any.whl`, both builds identical:

| Measurement | Before (37-SCOUT.md) | After | Asserted |
|-------------|----------------------|-------|----------|
| Total entries | 61 | **71** | `> 61` |
| `core/sounds/*.wav` | 0 | **3** | `== 3` |
| `web/static/*` | 0 | **5** | `== 5` |
| `web/templates/*` | 0 | **1** | `== 1` |
| Web data total | 0 | **6** | `== 6` |
| Top-level `sounds/*` | 0 | **0** | `== 0` |
| `generate_alert_sounds.py` anywhere | 1 (source tree only) | **0** | `== 0` |

The 10-entry growth is exactly the 3 WAVs, the 6 web data files, and `core/sounds/__init__.py`.

Entries observed:

```
core/sounds/__init__.py
core/sounds/available.wav
core/sounds/buy.wav
core/sounds/notification.wav
web/static/components.css
web/static/dashboard.css
web/static/tokens.css
web/static/vendor/uplot.iife.min.js
web/static/vendor/uplot.min.css
web/templates/dashboard.html
```

## Task Commits

1. **Task 1: Relocate sounds into the core package and resolve them through it** - `8a350fa` (refactor)
2. **Task 2: Declare package-data and prove the wheel carries it** - `48327ab` (build)

**Plan metadata:** see the closing `docs(37-01)` commit.

## Files Created/Modified

- `core/sounds/__init__.py` - one-line docstring, no imports; makes `core.sounds` a real package so `importlib.resources.files` can locate it
- `core/sounds/notification.wav`, `available.wav`, `buy.wav` - the three bundled cues, moved with `git mv` so history follows (all four moves recorded as `R` in `git status --porcelain`)
- `scripts/generate_alert_sounds.py` - the CC0 tone generator, moved out of the runtime package; its `_DIR` now targets `core/sounds/` via the repo root, and its docstring usage line reads `python scripts/generate_alert_sounds.py`
- `utils.py` - added `import importlib.resources`; added `_resolve_sounds_dir()` (a 1-statement function plus docstring); `SOUNDS_DIR` remains a module-level `str` constant, now assigned from it
- `pyproject.toml` - added `include-package-data = true` and `[tool.setuptools.package-data]` with `"core.sounds" = ["*.wav", "*.mp3"]` and `web = ["static/*", "static/vendor/*", "templates/*"]`
- `README.md` - the three sound paths and the regeneration command updated; CC0 and provenance wording untouched
- `CLAUDE.md` - the two stale `sounds/` architecture references updated (see Deviations)
- `tests/test_packaging.py` - 4 tests: `SOUNDS_DIR` is a directory, its last two path segments are `core`/`sounds`, it holds all three cue names with a `.wav` or `.mp3` suffix, and the six web data files exist under `Path(web.__file__).parent`

## Decisions Made

- **No `MANIFEST.in`.** The plan allowed one as a fallback if any expected entry was missing. Nothing was missing, so none was added. `include-package-data = true` is declared as the locked decision required, but the `package-data` globs are what actually do the work.
- **`version = "2.0.0"` left byte-identical.** release-please owns versioning and has PR #23 open proposing 2.1.0. `grep -c 'version = "2.0.0"' pyproject.toml` returns 1, unchanged.
- **`dependencies` and `[project.optional-dependencies]` untouched.** Those belong to plan 37-02; editing them here would collide.
- **The generator's output directory changed, not just its docstring.** Leaving `_DIR = os.path.dirname(os.path.abspath(__file__))` after the move would have made a regeneration silently write three WAVs into `scripts/` where nothing reads them, and leave the real ones stale. This was explicitly instructed by the plan and is called out here because it is the one behavioral change inside the moved file.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Doc drift] `CLAUDE.md` still described the old `sounds/` directory**

- **Found during:** Task 1 (relocate sounds)
- **Issue:** `CLAUDE.md` line 38 said `utils.py` "looks for `sounds/{name}.mp3`" and line 57 documented a `sounds/` directory. Both became false the moment the files moved. The plan listed `README.md` but not `CLAUDE.md` in `files_modified`. Leaving them would point a future contributor (or agent, since `CLAUDE.md` is loaded as hard constraints) at a path that no longer exists.
- **Fix:** Updated both lines to name `core/sounds/`, mention the `importlib.resources` resolution, and reference `python scripts/generate_alert_sounds.py`. No other `CLAUDE.md` content touched.
- **Files modified:** `CLAUDE.md`
- **Verification:** `grep -n sounds CLAUDE.md` shows only the two corrected lines; no remaining reference to a bare `sounds/` path.
- **Committed in:** `8a350fa` (part of the Task 1 commit)

**2. [Rule 3 - Blocking] Removed `build/` and `shoppybot.egg-info/` byproducts from the repo root**

- **Found during:** Task 2 (wheel build)
- **Issue:** `python -m build` writes `build/` and `shoppybot.egg-info/` into the repo root even when `--outdir` points elsewhere. Both are gitignored so `git status --porcelain` stayed clean, but the plan explicitly requires keeping them out of the tree rather than trusting `.gitignore`.
- **Fix:** `rm -rf build shoppybot.egg-info` after each of the two builds, targeting those two paths by name. `git clean` was not used at any point.
- **Files modified:** none tracked
- **Verification:** `git status --porcelain` after the final build shows only the pre-existing `.planning/STATE.md` modification.
- **Committed in:** n/a, no tracked files involved

**Total deviations:** 2 auto-fixed (1 Rule 1 doc drift, 1 Rule 3 blocking hygiene)
**Impact on plan:** Both are direct consequences of this plan's own changes. No scope creep; no production code touched beyond what the plan specified.

## Issues Encountered

**`sounds/` survived the four `git mv` calls as an empty directory.** Git tracks files, not directories, so the four renames left an empty `sounds/` on disk while `git status` already showed a clean move. Resolved with `rmdir sounds` (safe: the directory was provably empty, having just had its only four entries moved). The plan's `test -d sounds` acceptance criterion is what caught it.

**No fallback was needed for the vendor subdirectory.** The plan anticipated that `static/*` would not descend into `web/static/vendor/`, and it did not: the separate `static/vendor/*` glob is load-bearing. Both vendor files appear in the wheel.

## Verification Evidence

- Wheel built twice, second time from the fully committed tree: both produced 71 entries with identical data-file counts. Assertions ran in-process via `zipfile`, not by eye.
- `utils.SOUNDS_DIR` prints `E:\repos\ShopPyBot\core\sounds` and lists `['__init__.py', '__pycache__', 'available.wav', 'buy.wav', 'notification.wav']`.
- `grep -n "os.path.dirname(__file__)" utils.py` returns nothing. `grep -n "importlib.resources" utils.py` returns 2 lines.
- `tests/test_utils_audio.py` passes **unmodified**: 8 passed, the same count as before this plan. The pygame graceful-degradation path (`_PYGAME_AVAILABLE`, `_initialize_audio`, `_AUDIO_AVAILABLE`, all three `play_*_sound` wrappers) was not touched.
- Full suite: **965 passed, 2 skipped** against a 961 passed / 2 skipped baseline. The delta is exactly the 4 new tests in `tests/test_packaging.py`; zero regressions.
- All four file moves recorded by git as renames (`R`), not delete-plus-add.

## User Setup Required

None. This is a purely local packaging change: nothing installed, no dependency added, no GitHub state mutated.

## Next Phase Readiness

- **Plan 37-02 is unblocked and is the correct next step.** This plan deliberately did NOT install the wheel into a clean venv, because `import utils` in a bare venv still fails on `colorama` until 37-02 declares the missing runtime dependencies. The clean-venv functional check of `SOUNDS_DIR` belongs there.
- **Plan 37-04's CI wheel job** now has a concrete assertion to encode: at least one entry under each of `web/static/`, `web/templates/`, and `core/sounds/`, with the exact counts 5, 1, and 3 available above if a stricter check is wanted.
- **One thing to watch in 37-02:** `pygame` is slated to become an optional extra. `utils` imports `core.sounds` unconditionally now, but that is a pure-data package with no third-party imports, so the pygame-absent path is unaffected. `tests/test_packaging.py` does not import pygame either.
- No blockers.

## Self-Check: PASSED

All 6 claimed artifacts exist on disk (`core/sounds/__init__.py`, the 3 WAVs, `scripts/generate_alert_sounds.py`, `tests/test_packaging.py`) plus this SUMMARY. Both claimed commits (`8a350fa`, `48327ab`) resolve in `git log --all`. The old `sounds/` directory is confirmed absent.

---
*Phase: 37-distributable-artifact*
*Completed: 2026-08-03*
