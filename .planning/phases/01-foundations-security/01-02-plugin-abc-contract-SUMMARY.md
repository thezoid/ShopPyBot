---
phase: 01-foundations-security
plan: 02
subsystem: plugin-architecture
tags:
  - plugin-architecture
  - abc
  - python
  - tdd
requirements:
  - CORE-01
  - CORE-02
dependency-graph:
  requires:
    - pytest-harness
  provides:
    - retailer-plugin-abc
    - plugin-api-version-1
  affects:
    - phase-02-plugin-migration
    - all-future-retailer-plugins
tech-stack:
  added: []
  patterns:
    - abstract-base-class
    - no-op-default-method
    - api-version-constant
key-files:
  created:
    - plugin_base.py
    - tests/test_plugin_base.py
  modified: []
decisions:
  - "Followed D-01: ABC methods drop driver parameter; driver lives on self.driver"
  - "Only check_availability and auto_buy are abstract; login and detect_captcha have no-op defaults"
  - "__init__ stores platform_config (no NotImplementedError) so subclasses can super().__init__()"
  - "Pure stdlib: only abc is imported; no third-party deps in plugin_base.py"
metrics:
  duration: ~3min
  completed: 2026-05-12
  tasks-completed: 2
  files-touched: 2
---

# Phase 1 Plan 02: Plugin ABC Contract Summary

Locked the `RetailerPlugin` ABC contract and `PLUGIN_API_VERSION = 1` at the repo root. Followed the TDD RED then GREEN gate sequence: failing tests committed first, implementation second. All five contract tests pass on Python 3.14 with stdlib-only imports. Phase 2 plugin migration is now unblocked (CORE-01, CORE-02).

## What Shipped

- `plugin_base.py` (44 lines): `RetailerPlugin(ABC)` plus `PLUGIN_API_VERSION: int = 1`. Two `@abstractmethod` decorators on `check_availability` and `auto_buy`. `login` and `detect_captcha` ship as concrete no-op defaults. `__init__(self, platform_config)` stores the config slice so subclasses can call `super().__init__()`. Only stdlib import: `from abc import ABC, abstractmethod`. Per D-01, no method signature includes a `driver` parameter.
- `tests/test_plugin_base.py` (38 lines): five contract tests exercising the API version, abstract instantiation rejection, minimal subclass instantiation, and the two no-op defaults.

## Tasks Completed

| # | Name                                          | Commit  | Files                          |
|---|-----------------------------------------------|---------|--------------------------------|
| 1 | Write failing ABC contract tests (RED)        | 93e7349 | tests/test_plugin_base.py      |
| 2 | Implement plugin_base.py (GREEN)              | 3746039 | plugin_base.py                 |

## Verification Results

- `pytest -x -q tests/test_plugin_base.py`: 5 passed
- `python -c "from plugin_base import RetailerPlugin, PLUGIN_API_VERSION; assert PLUGIN_API_VERSION == 1"`: OK
- AST import scan: only `abc` is imported (no yaml, selenium, pydantic)
- `grep -c "@abstractmethod" plugin_base.py`: 2
- `plugin_base.py` line count: 44 (under 60-line ceiling)

## Must-Have Truths Validation

- `from plugin_base import RetailerPlugin, PLUGIN_API_VERSION` succeeds: VERIFIED
- `PLUGIN_API_VERSION == 1` (integer): VERIFIED (test_api_version_is_one)
- `RetailerPlugin({})` raises TypeError due to unimplemented abstract methods: VERIFIED (test_cannot_instantiate_abstract)
- Subclass implementing only `check_availability` and `auto_buy` instantiates: VERIFIED (test_subclass_with_required_methods_works)
- `login()` default returns None; `detect_captcha()` default returns False: VERIFIED (test_login_default_is_noop, test_detect_captcha_default_returns_false)

## Deviations from Plan

None. Plan executed exactly as written.

## TDD Gate Compliance

Plan tasks were tagged `tdd="true"`. Commit sequence: `test(01-02): ...` (RED, 93e7349) then `feat(01-02): ...` (GREEN, 3746039). RED gate verified by observing `ModuleNotFoundError: No module named 'plugin_base'` before implementation. GREEN gate verified by `5 passed` after implementation. No refactor commit needed: the 44-line module is at minimum complexity.

## Self-Check: PASSED

Verified after writing this SUMMARY:
- FOUND: plugin_base.py
- FOUND: tests/test_plugin_base.py
- FOUND: commit 93e7349
- FOUND: commit 3746039
