---
phase: 02-plugin-migration
plan: 05
subsystem: plugin-framework
tags:
  - documentation
  - example
  - contributor
  - python
dependency_graph:
  requires:
    - plugin_base.RetailerPlugin (Phase 2 Plan 01 amended ABC)
    - driver.build_driver (Phase 1)
    - logger.writeLog (Phase 1)
    - plugin_registry.discover (Phase 2 Plan 01) - skip-by-naming behavior for example_plugin.py
  provides:
    - "plugins/example_plugin.py exporting ExamplePlugin(RetailerPlugin) as the starter template"
    - "plugins/PLUGIN_DEV.md as the technical contract reference for contributors"
    - "tests/test_docs.py extended with 16+ source-grep and AST tests guarding both artifacts"
  affects:
    - "Phase 3 CONTRIBUTING.md: PLUGIN_DEV.md forward-links to it; Phase 3 should reciprocate"
tech_stack:
  added: []
  patterns:
    - "AST-based class introspection (ast.ClassDef + ast.AnnAssign walks) for test assertions"
    - "sys.modules stubbing (selenium.webdriver.common.by + driver) for instantiation test without real Chrome"
    - "pytest.parametrize for required-section substring checks in PLUGIN_DEV.md"
    - "Non-prefixed plugin filename (example_plugin.py) intentionally bypasses registry discovery"
key_files:
  created:
    - plugins/example_plugin.py
    - plugins/PLUGIN_DEV.md
  modified:
    - tests/test_docs.py
decisions:
  - "ExamplePlugin uses httpbin.org/html as the example target (RESEARCH Q8 A1): contributors can read the URL and immediately understand the example without credentials"
  - "ExamplePlugin is check-only: login_at_startup=False, login() inherits no-op, auto_buy returns False with informational log. Demonstrates the smallest viable plugin shape"
  - "Filename rule honored: example_plugin.py NOT prefixed with shopbot_plugin_ so registry emits INFO log and skips it (per plugin_registry.discover)"
  - "PLUGIN_DEV.md scoped to technical contract only: meta workflow (fork, branch, PR) explicitly deferred to CONTRIBUTING.md (Phase 3) with forward-link"
  - "Anti-patterns section enumerates 9 rules from RESEARCH Q9 in the order contributors are most likely to hit them"
  - "Style enforcement encoded as tests: no em dashes, no horizontal-rule lines (--- / *** / ___). Catches CLAUDE.md style drift mechanically"
  - "Test selenium stubbing uses monkeypatch.setitem(sys.modules, ...) so stubs are reverted per-test; driver module stubbed wholesale so example_plugin import does not require selenium.webdriver.chrome submodule"
  - "domain_pattern AST check accepts both AnnAssign and Assign nodes to be forgiving of contributor style; the registry-side empty-list check (plugin_registry._load_plugin_class) enforces non-emptiness at runtime"
metrics:
  duration_minutes: 8
  completed_date: 2026-05-12
  task_count: 2
  file_count: 3
requirements:
  - CORE-08
---

# Phase 2 Plan 05: Example Plugin and Developer Docs Summary

Shipped the two contributor-facing artifacts that close CORE-08: a working
ExamplePlugin against httpbin.org (NOT auto-loaded; filename prefix mismatch)
and PLUGIN_DEV.md, the technical contract reference for plugin contributors.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | RED tests for example_plugin.py + PLUGIN_DEV.md | 5f820c6 | tests/test_docs.py |
| 2 | Ship example_plugin.py + PLUGIN_DEV.md (GREEN) | ba92fa6 | plugins/example_plugin.py, plugins/PLUGIN_DEV.md, tests/test_docs.py |

## What Was Built

### plugins/example_plugin.py (88 lines)

Working check-only plugin against httpbin.org/html. Demonstrates every
integration point a new plugin needs:

- `class ExamplePlugin(RetailerPlugin)` with `domain_pattern: list[str] = ["httpbin.org"]`
- `login_at_startup: bool = False` (inherits no-op login)
- `name: str = "example"` (explicit even though registry would derive it)
- `__init__` calls `super().__init__(platform_config)` then `self.driver = build_driver(driver_path or "chromedriver.exe")`
- `check_availability` does a DOM probe via `find_elements(By.TAG_NAME, "h1")` and logs via `writeLog`
- `auto_buy` is an informational no-op returning False

The file lives at `plugins/example_plugin.py`. Because its filename does NOT
start with `shopbot_plugin_`, `plugin_registry.discover` emits an INFO log and
skips it (see `plugin_registry.py:111`). Contributors copy it to
`plugins/shopbot_plugin_<name>.py` to enable discovery.

### plugins/PLUGIN_DEV.md (185 lines)

10-section technical contract reference. Sections:

1. What is a plugin
2. The contract (ABC method table + class attribute table)
3. File naming convention (with literal "one plugin class per file" phrase)
4. domain_pattern matching rules (with literal "list[str]" examples)
5. Driver construction (build_driver in __init__; no module-level driver)
6. Reading config (self.platform_config; legacy singleton retired)
7. Testing your plugin (references tests/test_plugins_amazon.py, tests/test_plugins_bestbuy.py)
8. PLUGIN_API_VERSION (current value 1; bump triggers documented)
9. Submitting (forward-links to CONTRIBUTING.md for Phase 3 process flow)
10. Anti-patterns (9 rules from RESEARCH Q9)

Style constraints enforced by tests:
- Zero em dashes
- Zero horizontal-rule lines (`---`, `***`, `___`)
- Required substrings: `list[str]`, `login_at_startup`, `example_plugin.py`,
  `CONTRIBUTING.md`, `one plugin class per file`

### tests/test_docs.py (extended from 13 -> 230 lines)

Preserved the existing SEC-06 README disclaimer test. Added:

- 7 example_plugin.py guards: file exists, filename not auto-loaded, AST
  finds RetailerPlugin subclass, domain_pattern is a list literal,
  build_driver imported, no `from config import` anti-pattern, instantiation
  via monkeypatched build_driver returns sentinel
- 9 PLUGIN_DEV.md guards: file exists, parametrized required-section
  substrings, anti-patterns section, references example_plugin.py, documents
  list[str] / login_at_startup / one-class-per-file, links CONTRIBUTING.md,
  no em dashes, no horizontal-rule lines

Total: 24 new test cases (some via `pytest.parametrize`). All pass.

## Verification

```
pytest -q tests/test_docs.py                       # 25 passed
pytest -q tests/test_docs.py tests/test_plugin_base.py \
        tests/test_plugin_registry.py \
        tests/test_plugins_amazon.py \
        tests/test_plugins_bestbuy.py              # 74 passed
python -c "import ast; ast.parse(open('plugins/example_plugin.py').read())"  # parses
grep -n "—" plugins/PLUGIN_DEV.md                   # 0 matches
grep -nE "^---$|^\*\*\*$|^___$" plugins/PLUGIN_DEV.md  # 0 matches
```

Pre-existing test failures (NOT introduced by this plan, verified by
`git stash + pytest` rerun):

- `tests/test_utils.py` collection error: `pygame` not installed in dev env
- `tests/test_driver_setup.py` (4 failures): `selenium.webdriver.chrome`
  submodule not installed; out of scope for docs plan
- `tests/test_models.py` (2 errors): sqlite3 unable to open db file on this
  worktree path; environmental, not code defect

These are flagged in 02-CONTEXT.md as pre-existing technical debt.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] example_plugin.py docstring matched anti-pattern grep**

- Found during: Task 2 GREEN run (after writing the example file)
- Issue: The example file's anti-pattern comment literally read
  ``NEVER `from config import config` (Phase 1 retired the singleton)``,
  which tripped the `test_example_plugin_no_config_singleton_import` source
  grep because the test searches for the substring "from config import" in
  the source.
- Fix: Reworded the comment to "NEVER import the legacy config singleton
  (Phase 1 retired it)". The anti-pattern is still documented; the comment
  no longer pattern-matches the grep.
- Files modified: plugins/example_plugin.py
- Commit: ba92fa6

**2. [Rule 3 - Blocking] Selenium chrome submodule absent during test**

- Found during: Task 2 GREEN run
- Issue: `test_example_plugin_constructs_via_mock` attempted to import
  the real `driver` module to monkeypatch `build_driver`. `driver.py`
  imports `selenium.webdriver.chrome.options`, which is not available in
  the dev environment.
- Fix: Refactored the test to stub the `driver` module wholesale via
  `monkeypatch.setitem(sys.modules, "driver", driver_stub)`. The example
  plugin's `from driver import build_driver` now resolves to the stub
  without ever touching the real driver module.
- Files modified: tests/test_docs.py
- Commit: ba92fa6

### Out of Scope (Deferred)

- `tests/test_utils.py` pygame collection failure (Phase 2 cleanup window
  per 02-CONTEXT.md; not in scope for the example-plugin docs plan)
- `tests/test_driver_setup.py` selenium.webdriver.chrome dependency
  (environmental setup; not in scope)
- `tests/test_models.py` sqlite path error on worktree (environmental;
  not in scope)

## Authentication Gates

None. No remote services contacted.

## Known Stubs

None. Both shipped files are complete and tested.

## Self-Check: PASSED

Verification:
- `plugins/example_plugin.py` exists (88 lines, parses, subclasses RetailerPlugin)
- `plugins/PLUGIN_DEV.md` exists (185 lines, all required substrings present)
- `tests/test_docs.py` modified, all 25 tests pass
- Commit `5f820c6` (RED) found in git log
- Commit `ba92fa6` (GREEN) found in git log

## TDD Gate Compliance

- RED gate: `5f820c6 test(02-05): add RED tests for example_plugin.py and PLUGIN_DEV.md`
- GREEN gate: `ba92fa6 feat(02-05): ship example_plugin.py and PLUGIN_DEV.md (CORE-08)`
- REFACTOR: not needed; GREEN code is small and clear.
