---
phase: 37-distributable-artifact
plan: 03
subsystem: core
tags: [packaging, plugin-discovery, path-resolution, refactor, seam, wheel, pkg-06]

# Dependency graph
requires:
  - phase: 37-distributable-artifact
    plan: 02
    provides: "a wheel that installs and imports, so the accessor could be exercised from a real clean-venv install rather than only from the dev tree"
provides:
  - "core.paths.bundled_plugins_dir(), the single named accessor for the bundled plugin root"
  - "proof the refactor is behavior-preserving, asserted against the real prior source files"
  - "a guard that _REPO_ROOT_OVERRIDE cannot redirect executable-plugin discovery (T-37-10)"
  - "a seam guard asserting no production module outside core/paths.py computes a plugin path, which pre-satisfies Phase 43 criterion 5"
  - "the PKG-06 answer recorded in ROADMAP.md where Phase 43 reads it, with the namespace caveat retained"
affects: [37-04 CI wheel job assertion 4, 43 multi-root discovery, 44 provenance, 47 plugins install]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "distribution content resolves from __file__ directly; only user-data paths are allowed to honour a test override"
    - "a refactor is proven by reconstructing the removed expression from the real prior source file, not by asserting a hardcoded path"
    - "an extracted seam ships with a source-scanning guard so it cannot be silently re-inlined"

key-files:
  created: []
  modified:
    - core/paths.py
    - core/orchestrator.py
    - core/service.py
    - tests/test_paths.py
    - .planning/ROADMAP.md

key-decisions:
  - "bundled_plugins_dir() computes from __file__ directly and never via _repo_root(), because _repo_root() honours the monkeypatchable _REPO_ROOT_OVERRIDE and every .py file under the returned directory is exec_module'd (T-37-10)"
  - "core/service.py's two inline sites were refactored alongside core/orchestrator.py:814; the plan named only the orchestrator, but must-have truth 4 and Phase 43 criterion 5 cover every production module"
  - "the now-unused pathlib.Path import was removed from both callers, since the plan's condition (nothing else in the file uses it) held in both"
  - "PKG-06 verified against a bare wheel install with no extras, which is stricter than the [web] install 37-02 used: the accessor needs only platformdirs"

requirements-completed: [PKG-06]

# Metrics
duration: 7min
completed: 2026-08-03
---

# Phase 37 Plan 03: Bundled Plugin Root Seam Summary

**PKG-06 named a function that did not exist; it exists now, it is computed from `__file__` rather than from the monkeypatchable repo-root override, and calling it from a clean-venv wheel install returns `site-packages/plugins` holding all 7 bundled plugins.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-08-03T22:13Z
- **Completed:** 2026-08-03T22:20Z
- **Tasks:** 2 of 2
- **Files modified:** 5

## Accomplishments

- **Created the seam workstream H depends on.** `core.paths.bundled_plugins_dir()` is now the one place a bundled plugin path is computed. Phase 43's multi-root discovery extends a named function instead of hunting inline expressions.
- **Kept the executable-code root off the mutable override.** `_repo_root()` honours a module global that the suite monkeypatches. Routing the plugin root through it would have made a monkeypatchable global able to redirect `spec.loader.exec_module`, and would have silently changed behavior under exactly the conditions the tests create. The accessor computes from `__file__`, and a test asserts the override cannot move it.
- **Found and fixed a second pair of inline sites the plan did not name.** `core/service.py:133` and `:159` carried the same bare expression as `core/orchestrator.py:814`. Without them the plan's own must-have truth 4 would have been false and its seam guard would have failed. Three sites collapsed into one accessor, not one.
- **Answered PKG-06 durably.** The scout observed the result once in a scratch venv. It is now a repo test, a roadmap entry, and a re-runnable clean-install probe. 37-04's CI job turns it into a fourth, permanent form.
- **Proved the refactor rather than asserting it.** The behavior-preservation test reconstructs the removed expression from `core.orchestrator.__file__` and `core.service.__file__`, so it compares against the real prior source anchors instead of a hardcoded path that could drift with them.

## PKG-06: Observed Output From a Clean Wheel Install

Environment: `py -3.13 -m venv`, `pip list` showing only `pip==26.0.1` immediately after creation, then a single `pip install "<abs path>/shoppybot-2.0.0-py3-none-any.whl"`. **No extras, no `requirements.txt`, no editable install.** The probe ran with `python -I` from a cwd outside the repo, so `core` could only resolve from `site-packages`.

```
interpreter          : ...\scratchpad\pluginenv\Scripts\python.exe
core package dir     : ...\scratchpad\pluginenv\Lib\site-packages\core
resolved plugins_dir : ...\scratchpad\pluginenv\Lib\site-packages\plugins
exists               : True
is_dir               : True
under site-packages  : True
bundled plugin files : 7
     shopbot_plugin_amazon.py
     shopbot_plugin_bestbuy.py
     shopbot_plugin_gamestop.py
     shopbot_plugin_newegg.py
     shopbot_plugin_squareenix.py
     shopbot_plugin_target.py
     shopbot_plugin_walmart.py
venv prefix          : ...\scratchpad\pluginenv
PKG-06 PROBE: PASS
```

Every line above is an assertion, not a print: the probe exits non-zero if the path does not exist, is not a directory, is not under a `site-packages` segment, is not inside `sys.prefix`, is not a sibling of the installed `core` package, or if the sorted `shopbot_plugin_*.py` list is not exactly those 7 names. It exited 0. The 7 names match `37-SCOUT.md` exactly.

The installed copy is the post-refactor tree, not a stale build: `grep -c "def bundled_plugins_dir" <venv>/Lib/site-packages/core/paths.py` returns 1.

## Behavior Preservation

The removed expression appeared three times, all anchored on a module inside `core/`:

| Site | Before | After |
|------|--------|-------|
| `core/orchestrator.py:814` | `plugins_dir = Path(__file__).parent.parent / "plugins"` | `plugins_dir = bundled_plugins_dir()` |
| `core/service.py:133` | `plugins_dir = Path(__file__).parent.parent / "plugins"` | `plugins_dir = bundled_plugins_dir()` |
| `core/service.py:159` | `plugins_dir = Path(__file__).parent.parent / "plugins"` | `plugins_dir = bundled_plugins_dir()` |

Proof is a direct path equality against the real prior anchors, not an argument that the anchors are equivalent:

```
identical: E:\repos\ShopPyBot\plugins
plugins: 7
```

`test_bundled_plugins_dir_preserves_inline_expression` asserts the accessor equals both `Path(core.orchestrator.__file__).parent.parent / "plugins"` and `Path(core.service.__file__).parent.parent / "plugins"`, so if either module ever moves relative to `core/paths.py` the test fails rather than the discovery path silently breaking.

`core/registry.py` is unchanged. `git diff` on it is empty. Its `_discover_plugins(plugins_dir: Path)` signature already took the directory as a parameter, which is the whole reason this refactor cost 4 production lines.

## Tests Added

Four tests in `tests/test_paths.py`, taking the file from 6 to 10:

| Test | Asserts |
|------|---------|
| `test_bundled_plugins_dir_preserves_inline_expression` | equality against the expression reconstructed from `core.orchestrator.__file__` and `core.service.__file__` |
| `test_bundled_plugins_dir_ignores_repo_root_override` | with `_REPO_ROOT_OVERRIDE` monkeypatched to `tmp_path`, the accessor is unchanged and `tmp_path` is not among its parents; `data_dir()` is also undisturbed |
| `test_bundled_plugins_dir_contains_seven_plugins` | the directory exists and its sorted `shopbot_plugin_*.py` listing equals the 7 expected names |
| `test_no_production_module_computes_a_plugin_path` | no line in `core/**`, `web/**`, `logger.py`, `models.py`, `utils.py`, `main.py` (excluding `core/paths.py`) contains both `parent.parent` and a `plugins` literal |

The override test asserts `core.paths._repo_root() == tmp_path` first, so it fails loudly if the monkeypatch stops taking effect rather than passing vacuously. The seam guard mirrors `test_no_hardcoded_separators`: it asserts the scanned set is non-empty, asserts both `core/orchestrator.py` and `core/service.py` are in it so a wrong `rglob` anchor cannot pass silently, asserts `core/paths.py` is excluded, and reports every violation with file and line number rather than a bare boolean.

## Roadmap Change

`.planning/ROADMAP.md` Phase 43's `**Research flag**:` line said:

> Blocked on PKG-06's factual answer. If `bundled_plugins_dir()` does not resolve from an installed wheel, the `importlib.resources` fix is Phase 37 work, not this phase's.

It now states the answer, names the accessor, records the observed `site-packages/plugins` result with the 7 plugin names, states that no `importlib.resources` rewrite is needed, and points at the guarding test. The scout's namespace caveat is retained verbatim in intent as a separate `**Caveat carried forward**` line: the bundled root lands as a top-level `site-packages/plugins` entry that another distribution shipping a top-level `plugins` package would collide with, and Phase 43's multi-root design should own the location rather than inherit it.

`git diff --stat` reports `1 file changed, 2 insertions(+), 1 deletion(-)` in a single hunk confined to the Phase 43 entry. `grep -c "Blocked on PKG-06" .planning/ROADMAP.md` returns 0. No other phase entry, requirement, dependency, or checkbox was touched by that task.

## Task Commits

1. **Task 1: Create the accessor, call it from the orchestrator, and prove the refactor changes nothing** - `e33efa8` (refactor)
2. **Task 2: Prove the accessor resolves from an installed wheel and record the PKG-06 answer** - `cc3b4b8` (docs)

**Plan metadata:** see the closing `docs(37-03)` commit.

## Files Created/Modified

- `core/paths.py` - `bundled_plugins_dir()` added between `log_dir()` and `_migrate_logs()`. 19 lines including a docstring that states it is distribution content rather than user data, that it must not move when a test relocates the data root, and why it deliberately does not consult `_REPO_ROOT_OVERRIDE`. `_repo_root()` is referenced by exactly two lines in the file: its own definition and `migrate_legacy_paths()`. Nothing else in the module changed.
- `core/orchestrator.py` - line 814 now calls the accessor; `from core.paths import bundled_plugins_dir` added to the `core.*` import block in alphabetical position; the `from pathlib import Path` import removed, since line 814 was its only consumer.
- `core/service.py` - lines 133 and 159 now call the accessor; same import addition and same `Path` removal, for the same reason. `PluginRegistry(self._cfg, plugins_dir)` construction unchanged at both sites.
- `tests/test_paths.py` - 4 tests added plus an updated module docstring. The existing 6 tests are untouched.
- `.planning/ROADMAP.md` - Phase 43 research flag rewritten from question to answer, plus the retained caveat line.

## Decisions Made

- **`__file__`, never `_repo_root()`.** This is the plan's central constraint and the reason the wave exists alone. `_repo_root()` returns `_REPO_ROOT_OVERRIDE` when set, and the suite sets it. Two consequences, either of which is disqualifying: the accessor would return a different path than the inline expression under exactly the conditions the tests create, turning a pure refactor into a behavior change; and the root of a directory whose every `.py` file gets `exec_module`'d would become settable from a module global. `T-37-10` records the second as an elevation-of-privilege disposition and the override test is its mitigation.
- **Three sites, not one.** See the deviation below. The plan's `files_modified` list and Task 1 `<files>` named only `core/orchestrator.py`, but its `must_haves.truths` entry 4 is "No production module outside core/paths.py computes a bundled plugin path" and its seam guard enforces exactly that. Leaving `core/service.py` inline would have made the plan self-contradictory and its own acceptance test red.
- **`Path` import removed from both callers.** The plan's condition was explicit: remove it unless something else in the file uses it. `grep -n Path` on each file showed the import line and the plugin-path line only. Verified by a green full suite, and no test patches `core.orchestrator.Path` or `core.service.Path`.
- **Bare wheel install, no extras.** The plan called for it and it is the stricter test. `core.paths` imports only `os`, `pathlib`, and `platformdirs`, so the accessor is reachable before any extra resolves. That matters for 37-04: the CI wheel job can assert the plugin root before it installs `[web]`.
- **`version = "2.0.0"` left byte-identical**, as in 37-01 and 37-02. release-please owns versioning and has PR #23 open proposing 2.1.0.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Refactored `core/service.py`'s two inline plugin-path sites**

- **Found during:** Task 1, `read_first` reconnaissance. A repo-wide `parent.parent` grep surfaced `core/service.py:133` and `core/service.py:159` alongside the `core/orchestrator.py:814` the plan and scout both named.
- **Issue:** The plan's `must_haves.truths` entry 4 and its own Task 1 seam guard require that no production module outside `core/paths.py` computes a bundled plugin path. `BotService.get_analytics()` and `BotService.list_plugins()` each computed one. Implementing the plan exactly as written would have left the stated truth false and made the plan's own new test fail, since the guard scans all of `core/**` and cannot be narrowed to the orchestrator without gutting the point of it. It would also have left Phase 43's criterion 5 half-satisfied while the summary claimed otherwise.
- **Fix:** Both sites now call `bundled_plugins_dir()`. Same import addition and same unused-`Path` removal as the orchestrator. The `PluginRegistry(self._cfg, plugins_dir)` construction below each is unchanged, and both call sites keep the local variable name `plugins_dir` and its type.
- **Files modified:** `core/service.py`
- **Commit:** `e33efa8`

**Total deviations:** 1 auto-fixed, 0 architectural, 0 blocked.
**Impact on plan:** Strictly additive. Every acceptance criterion the plan wrote still passes as written; one file was added to the change set so that criteria the plan wrote against `core/**` could pass at all.

## Verification Evidence

- Acceptance criteria, verbatim results: `grep -c "def bundled_plugins_dir" core/paths.py` = 1. `grep -n '_repo_root' core/paths.py` = 2 lines, its own definition and `migrate_legacy_paths()`, never inside the new accessor. `grep -c 'parent.parent / "plugins"' core/orchestrator.py core/service.py` = 0. `bundled_plugins_dir` appears 6 times across `core/`: the definition, two imports, and three call sites.
- The two one-liner probes exited 0 and printed `identical: E:\repos\ShopPyBot\plugins` and `plugins: 7`.
- `tests/test_paths.py`: **10 passed**, up from 6, exactly the 4 new tests.
- `tests/test_orchestrator.py tests/test_service.py tests/test_main_wiring.py tests/test_registry.py`: **72 passed**, zero failures. These are the suites that exercise the discovery path and the two refactored modules. (`tests/test_cli_plugins.py` named in the plan does not exist in the tree; `tests/test_registry.py` and `tests/test_service.py` cover that surface and were run instead.)
- Full suite: **969 passed, 2 skipped**, against the 37-02 baseline of 965 passed / 2 skipped. The delta is exactly the 4 new tests. No regressions.
- Wheel built from the tree at `e33efa8` with `--outdir` into the session scratchpad. `build/` and `shoppybot.egg-info/` were removed from the repo root **by name** afterwards. `git clean` was not used at any point in this plan. `git status --porcelain` verified empty after the build and after each commit, and no `build/`, `dist/`, or `*.egg-info/` path exists in the repo root.
- Both per-task commits checked with `git diff --diff-filter=D --name-only HEAD~1 HEAD`: no file deletions in either.
- `grep -n '^version' pyproject.toml` = `version = "2.0.0"`, untouched.
- Every venv, wheel, and probe artifact lives under the session scratchpad. Nothing was created inside the repo.

## User Setup Required

None. Purely local refactor plus a planning-doc edit: no push, no PR, no GitHub state mutated, no dependency added, and no new distribution installed beyond the locally built wheel from an absolute path (T-37-SC).

## Next Phase Readiness

- **37-04 is unblocked and its assertion 4 is now a one-liner.** `from core.paths import bundled_plugins_dir` plus a 7-file glob count. It needs only `platformdirs`, so it can run in the wheel job before `[web]` is installed and it will name a plugin-root regression precisely rather than surfacing as a mystery discovery failure.
- **Phase 43 (EXT-03) reads a fact, not a maybe.** Its research flag records the answer, the accessor exists, and its criterion 5 ("no production code computes a plugin path outside `core/paths.py`") is already true and already guarded by a test. Phase 43 extends `bundled_plugins_dir()` with a user root rather than building the seam first.
- **One thing Phase 43 must decide, not inherit:** the bundled root's location. It resolves today only because `plugins` lands as a top-level `site-packages` entry. That is namespace pollution and a distribution collision surface (T-37-11, accepted here, recorded in the roadmap).
- **Caution for Phase 43's multi-root work:** the user root under `data_dir()` legitimately follows `SHOPBOT_DATA_DIR` and the test override; the bundled root must not. Do not unify them behind one override-honouring helper. That distinction is the entire content of T-37-10.
- No blockers.

## Known Stubs

None. No placeholder value, empty collection, or "coming soon" string was introduced. The accessor returns a real computed path with no fallback and no sentinel, and every consumer of it is wired to a live `PluginRegistry` construction.

## Threat Flags

None. No network endpoint, auth path, or schema at a trust boundary was created or changed. The one trust boundary this plan touches, the bundled plugin root feeding `spec.loader.exec_module`, is `T-37-10` in the plan's own register, dispositioned `mitigate`, and mitigated exactly as specified: the path is computed from `__file__` and a test asserts the monkeypatchable override cannot move it. The file-access surface narrowed rather than widened, from three independently computed roots to one.

## Self-Check: PASSED

- `core/paths.py`, `core/orchestrator.py`, `core/service.py`, `tests/test_paths.py`, `.planning/ROADMAP.md` all exist.
- Commit `e33efa8` resolves in `git log`.
- Commit `cc3b4b8` resolves in `git log`.
- `git status --porcelain` clean before this SUMMARY was written.

---
*Phase: 37-distributable-artifact*
*Completed: 2026-08-03*
