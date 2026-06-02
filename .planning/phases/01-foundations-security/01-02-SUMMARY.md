---
phase: 01-foundations-security
plan: "02"
subsystem: core-abc
tags: [abc, plugin-interface, tdd, stdlib-only]
dependency_graph:
  requires: [01-01]
  provides: [RetailerPlugin-ABC, PLUGIN_API_VERSION, core-package]
  affects: [phase-2-plugin-migration, all-retailer-plugins]
tech_stack:
  added: []
  patterns: [ABC-abstractmethod, module-level-constant, concrete-noop-defaults]
key_files:
  created:
    - core/__init__.py
    - core/plugin_base.py
    - tests/test_plugin_base.py
  modified: []
decisions:
  - "PLUGIN_API_VERSION defined as module-level constant before class body so it is importable without instantiating untrusted subclass code (T-01-VER mitigation)"
  - "driver parameter left untyped in Phase 1 to avoid importing nodriver into the ABC; type annotation deferred to Phase 2"
  - "login and detect_captcha are concrete no-ops so check-only plugins need not override them"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-02"
  tasks: 2
  files_changed: 3
---

# Phase 01 Plan 02: RetailerPlugin ABC Summary

RetailerPlugin ABC locked with PLUGIN_API_VERSION=1 and verified by 5 passing tests; Phase 2 plugins can now subclass against a fixed interface.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create core package and RetailerPlugin ABC | 4425ecb | core/__init__.py, core/plugin_base.py |
| 2 | Write test_plugin_base.py covering ABC enforcement and no-op defaults | 69a913d | tests/test_plugin_base.py |

## What Was Built

`core/__init__.py` (empty package marker) and `core/plugin_base.py` defining `PLUGIN_API_VERSION = 1` as a module-level constant and `class RetailerPlugin(ABC)` with: `check_availability` and `auto_buy` as abstract methods (enforced by `@abstractmethod`); `login` and `detect_captcha` as concrete no-ops returning `None` and `False` respectively. Five tests in `tests/test_plugin_base.py` cover version constant, ABC TypeError enforcement (both missing and partially-missing), and no-op default return values.

## Verification Results

```
5 passed in 0.02s
```

Full suite: 9 passed, 1 warning (pre-existing pygame deprecation).

ABC contract verified:
- `PLUGIN_API_VERSION == 1`
- `RetailerPlugin.__abstractmethods__ == {'check_availability', 'auto_buy'}` (exactly two)
- No imports beyond `abc` stdlib in `core/plugin_base.py`

## Deviations from Plan

None - plan executed exactly as written. TDD gate sequence followed: tests written first (RED: ModuleNotFoundError confirmed), then implementation (GREEN: 5 tests pass).

## TDD Gate Compliance

- RED gate: `tests/test_plugin_base.py` written before implementation; confirmed `ModuleNotFoundError` on collection
- GREEN gate: `core/__init__.py` and `core/plugin_base.py` implemented; all 5 tests pass
- REFACTOR gate: not needed; implementation is clean and under 30 lines

## Known Stubs

None.

## Threat Flags

None -- no new network endpoints, auth paths, file access patterns, or schema changes. T-01-ABC and T-01-VER mitigations applied as specified in threat model: `@abstractmethod` enforces contract at instantiation, `PLUGIN_API_VERSION` is a module-level constant not shadeable by subclasses.

## Self-Check: PASSED

- core/__init__.py: EXISTS
- core/plugin_base.py: EXISTS
- tests/test_plugin_base.py: EXISTS
- Commit 4425ecb: EXISTS
- Commit 69a913d: EXISTS
- `python -m pytest tests/test_plugin_base.py -x -q` exits 0: CONFIRMED (5 passed)
