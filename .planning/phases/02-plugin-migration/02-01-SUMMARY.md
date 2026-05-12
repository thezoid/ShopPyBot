---
phase: 02-plugin-migration
plan: 01
subsystem: plugin-framework
tags:
  - plugin-architecture
  - registry
  - importlib
  - python
dependency_graph:
  requires:
    - plugin_base.py (Phase 1)
    - logger.py (Phase 1)
  provides:
    - "plugin_registry.discover(plugins_dir, app_config, cvvs) -> list[RetailerPlugin]"
    - "plugin_registry.route_url(url, registry) -> RetailerPlugin | None"
    - "plugin_registry.verify_coverage(registry, items) -> None (raises ValueError)"
    - "RetailerPlugin.domain_pattern: list[str] = []"
    - "RetailerPlugin.login_at_startup: bool = False"
    - "RetailerPlugin.name: str = '' (optional override)"
  affects:
    - Wave 1 (plans 02, 03, 05): can now subclass amended ABC
    - Plan 04 (main.py refactor): can integrate discover/verify_coverage/route_url
tech_stack:
  added: []
  patterns:
    - "importlib.util.spec_from_file_location + module_from_spec + exec_module"
    - "inspect.getmembers with three-filter subclass detection"
    - "urllib.parse.urlparse netloc normalization (lowercase + strip port + strip trailing dot)"
    - "Dotted-subdomain anchor (netloc == p or netloc.endswith('.' + p))"
    - "Two-phase load: lenient discover + strict verify_coverage (D-04)"
key_files:
  created:
    - plugin_registry.py
    - tests/test_plugin_registry.py
  modified:
    - plugin_base.py
    - tests/conftest.py
    - tests/test_plugin_base.py
decisions:
  - "D-01 locked: domain_pattern is list[str] with default []"
  - "D-03 locked: login_at_startup is False by default; plugins opt in"
  - "Plugin name resolution: optional `name` class attribute, defaults to filename stem with shopbot_plugin_ prefix removed"
  - "Empty domain_pattern raises ImportError, caught by D-04 Phase A warn-and-skip"
  - "Module namespace: shoppybot_plugins.<stem> to avoid sys.modules collisions"
metrics:
  duration_minutes: 12
  completed_date: 2026-05-12
  task_count: 2
  file_count: 5
requirements:
  - CORE-03
  - CORE-04
---

# Phase 2 Plan 01: Registry and ABC Amendment Summary

Amended the `RetailerPlugin` ABC contract to lock D-01 (`domain_pattern: list[str]`) and D-03 (`login_at_startup: bool`), and shipped `plugin_registry.py` implementing two-phase discovery, URL routing with subdomain-anchored matching, and a strict coverage check. This is the Wave 0 gating work that unblocks every downstream Phase 2 plan (02 Amazon, 03 BestBuy, 04 main.py refactor, 05 example_plugin + docs).

## What Shipped

**`plugin_base.py` (48 lines, under 60 cap):**
- `domain_pattern: list[str] = []` (was `str = ""`)
- `login_at_startup: bool = False`
- `name: str = ""` (optional override)
- Updated class docstring to explain the list type and the startup-login opt-in
- ABC method signatures (`check_availability`, `auto_buy`, `login`, `detect_captcha`) unchanged per Phase 1 D-01 lock

**`plugin_registry.py` (158 lines, under 300 cap):**
- Public API: `discover`, `route_url`, `verify_coverage`
- Private helpers: `_normalize_netloc`, `_matches`, `_load_module`, `_find_plugin_class`, `_load_plugin_class`, `_safe_platform`, `_safe_driver_path`, `_instantiate`
- Module namespace `shoppybot_plugins.<stem>` registered in `sys.modules` to prevent collisions with PyPI packages
- Three-filter subclass detection: `issubclass` + identity check against `RetailerPlugin` + `__module__ == module.__name__`
- One-class-per-file rule: ImportError raised when a module contains two or more `RetailerPlugin` subclasses
- Empty `domain_pattern` raises ImportError, caught by Phase A warn-and-skip
- D-04 Phase A: lenient discovery, per-plugin failures logged via `writeLog(..., "WARNING")` and skipped
- D-04 Phase B: `verify_coverage` raises `ValueError` naming the offending URL and expected plugin filename
- Subdomain anchor in `_matches` rejects `evilamazon.com` vs `amazon.com`
- Zero third-party imports (stdlib only + `logger` + `plugin_base`)
- Zero `print` calls, zero `import logging`, zero `sys.path` mutation

**Test additions:**
- `tests/conftest.py`: added `tmp_plugins_dir` fixture
- `tests/test_plugin_base.py`: 3 new tests (typing, default value, login_at_startup) for total of 8
- `tests/test_plugin_registry.py`: 15 test functions (18 with parametrize rows) covering normalization, subdomain matching, lenient discovery, dunder-skip, INFO log on non-prefixed files, one-class-per-file enforcement, name resolution, empty domain_pattern, routing, and coverage

**Filesystem precursor:** `plugins/` directory created at repo root (empty). Wave 1 plans (02, 03, 05) will populate it without racing.

## Verification

- `rtk pytest tests/test_plugin_base.py tests/test_plugin_registry.py` exits 0 with 26 passed
- ABC smoke: `from plugin_base import RetailerPlugin; assert RetailerPlugin.domain_pattern == [] and RetailerPlugin.login_at_startup is False`
- Registry smoke: `_normalize_netloc('https://Amazon.Com:443/') == 'amazon.com'`, `_matches('www.amazon.com', 'amazon.com') is True`, `_matches('evilamazon.com', 'amazon.com') is False`
- `rtk grep -n "@abstractmethod" plugin_base.py` reports 2 matches
- `rtk grep "import logging|sys\.path|print\(" plugin_registry.py` reports 0 matches

## Commits

| Hash    | Type | Description                                                |
| ------- | ---- | ---------------------------------------------------------- |
| ab9e642 | test | RED tests for amended ABC and plugin registry              |
| e5a7571 | feat | amend ABC contract and ship plugin registry (GREEN)        |

## Deviations from Plan

**1. Updated `_MinimalPlugin.domain_pattern` literal in existing test from `"example.com"` to `["example.com"]`.**
- **Found during:** Task 1 (RED test authoring)
- **Issue:** The pre-existing `tests/test_plugin_base.py` set `domain_pattern = "example.com"` on its test subclass. After D-01 locks `list[str]`, a string value is contract-invalid even though Python does not enforce the annotation at runtime.
- **Fix:** Changed the literal to `["example.com"]`. No existing assertion depends on the value.
- **Files modified:** tests/test_plugin_base.py
- **Commit:** ab9e642
- **Rule:** Rule 2 (correctness, matches locked D-01)

**2. Decomposed `discover()` to keep helpers under the 30-line cap.**
- **Found during:** Task 2 (GREEN implementation)
- **Issue:** The plan's reference implementation of `discover()` runs about 38 lines including the inner instantiation block. CLAUDE.md caps functions at 30 lines.
- **Fix:** Extracted `_load_plugin_class(path)` (combines load, find-class, and empty-domain check) and `_instantiate(cls, name, app_config, cvvs)` from `discover()`. `discover()` itself is now 27 lines.
- **Files modified:** plugin_registry.py
- **Rule:** CLAUDE.md hard constraint (function length)

## Threat Model Coverage

All threat IDs flagged for mitigation in the plan are implemented:

| Threat ID            | Mitigation Implemented                                                                                                |
| -------------------- | --------------------------------------------------------------------------------------------------------------------- |
| T-2-CORE-03-IMPORT   | Module namespaced under `shoppybot_plugins.<stem>` in `_load_module`; no `sys.path` mutation                          |
| T-2-CORE-03-FAIL     | Per-plugin import failure caught in `discover()` and logged WARNING; coverage check surfaces actionable errors only   |
| T-2-CORE-03-MULTI    | `_find_plugin_class` raises ImportError on more than one subclass; caught by D-04 Phase A                             |
| T-2-CORE-04-SUBDOMAIN| `_matches` dotted-subdomain anchor; `_normalize_netloc` lowercases + strips port + strips trailing dot                |
| T-2-CORE-04-EMPTY    | `_load_plugin_class` raises ImportError on empty `domain_pattern`; plugin omitted from registry, surfaced via WARNING |
| T-2-IDN              | Accepted (out of scope); contributors must use ASCII hostnames (PLUGIN_DEV.md will document in Plan 05)               |

## Out-of-Scope Failures Observed (Not Fixed)

Full `rtk pytest` (entire suite) surfaces pre-existing environmental issues unrelated to this plan:
- `tests/test_utils.py` fails to collect: `pygame` not installed (called out in 02-CONTEXT.md as known tech debt)
- `tests/test_driver_setup.py` 4 failures: `selenium` not installed in the worktree's Python environment
- `tests/test_models.py` 2 errors: `sqlite3.OperationalError: unable to open database file` (missing `data/` dir)

These are environment-setup gaps from the worktree, not regressions from this plan. The plan-scoped suite (`tests/test_plugin_base.py tests/test_plugin_registry.py`) is fully green.

## TDD Gate Compliance

- RED gate satisfied: commit ab9e642 (`test(02-01)`) introduces failing tests before any implementation exists
- GREEN gate satisfied: commit e5a7571 (`feat(02-01)`) makes all 26 plan-scoped tests pass
- REFACTOR gate: no separate refactor commit; the helper decomposition (see Deviation 2) was applied inline during GREEN

## Self-Check: PASSED

Created files verified:
- plugin_registry.py: FOUND
- tests/test_plugin_registry.py: FOUND

Modified files verified:
- plugin_base.py: FOUND (48 lines)
- tests/conftest.py: FOUND (tmp_plugins_dir present)
- tests/test_plugin_base.py: FOUND (8 tests)

Commits verified:
- ab9e642: FOUND
- e5a7571: FOUND
