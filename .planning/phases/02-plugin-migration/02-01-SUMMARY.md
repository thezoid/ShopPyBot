---
phase: 02-plugin-migration
plan: 01
subsystem: tests
tags: [tdd, pytest-asyncio, plugin-base, wave-0]
dependency_graph:
  requires: []
  provides: [abc-v2-contract-tests, async-test-fixtures]
  affects: [tests/test_plugin_base.py, tests/conftest.py]
tech_stack:
  added: []
  patterns: [pytest-asyncio asyncio_mode=auto, AsyncMock fake_browser, module-level test in conftest]
key_files:
  created: []
  modified:
    - tests/conftest.py
    - tests/test_plugin_base.py
decisions:
  - "No @pytest.mark.asyncio decorators: asyncio_mode=auto in pyproject.toml handles plain async def test_*"
  - "test_minimal_plugin_instantiates added (7th test) to explicitly assert complete subclass CAN instantiate"
  - "Smoke test placed as module-level function in conftest.py (not in a test_* file) per plan action"
metrics:
  duration: "3m 27s"
  completed_date: "2026-06-03"
  tasks: 2
  files: 2
---

# Phase 2 Plan 1: ABC v2 Contract Tests (Wave 0) Summary

Wave 0 test rewrite: plugin-base tests for ABC v2 async contract written BEFORE revising the ABC, establishing the executable contract that Plan 02 will satisfy.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add asyncio smoke test + shared fixtures to conftest.py | 49843f7 | tests/conftest.py |
| 2 | Rewrite tests/test_plugin_base.py for ABC v2 | 895a7e3 | tests/test_plugin_base.py |

## What Was Built

tests/conftest.py now provides:
- `test_asyncio_smoke`: plain `async def` test confirming pytest-asyncio 1.3.0 + asyncio_mode=auto works
- `fake_browser` fixture: MagicMock Browser with AsyncMock `get()` returning a fake Tab; Tab has AsyncMock `select`, `select_all`, `find`; fake Element has AsyncMock `click` and `send_keys`; `Browser.stop` is a plain MagicMock (sync, matching nodriver semantics)
- `tmp_plugins_dir` fixture: writes `shopbot_plugin_fake.py` to `tmp_path` defining `FakePlugin(RetailerPlugin)` with async stubs; returns the dir Path for Wave 2 registry tests
- Preserved `tmp_config_yml` and `tmp_data_dir` verbatim

tests/test_plugin_base.py rewrites to v2 contract (7 tests):
- `test_version_constant`: asserts `PLUGIN_API_VERSION == 2`
- `test_incomplete_plugin_raises`: empty subclass cannot instantiate (TypeError)
- `test_abstract_methods_enforced`: subclass missing `auto_buy` cannot instantiate (TypeError)
- `test_minimal_plugin_instantiates`: complete subclass with both abstract methods CAN instantiate
- `test_login_noop` (async): `await login()` returns None
- `test_detect_captcha_noop` (async): `await detect_captcha()` returns False
- `test_init_sets_driver_none`: `instance.driver is None` after construction (D-06)

## Verification Results

- `pytest tests/test_plugin_base.py --co`: 7 tests collected, zero collection errors
- `pytest tests/conftest.py::test_asyncio_smoke -v`: PASSED (asyncio_mode=auto confirmed working)
- `pytest tests/test_logger.py tests/test_models.py tests/test_config_schema.py tests/test_config.py tests/test_utils.py -q`: 12 passed (baseline green, unaffected)
- `pytest tests/test_plugin_base.py -v`: 5 FAILED, 2 passed (expected RED against v1 ABC)

The 5 failures are the correct RED signal: `PLUGIN_API_VERSION == 2` fails (v1 has 1), and `MinimalPlugin(config=None)` fails (v1 ABC has no `__init__`). These turn green when Plan 02 revises the ABC.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Functionality] Added test_minimal_plugin_instantiates as 7th test**
- Found during: Task 2 verification (only 6 collected initially)
- Issue: Plan acceptance criteria specifies 7 tests; plan behavior section lists MinimalPlugin CAN be instantiated as a distinct behavior point
- Fix: Added `test_minimal_plugin_instantiates` asserting `isinstance(p, RetailerPlugin)` after construction
- Files modified: tests/test_plugin_base.py
- Commit: 895a7e3

None other - plan executed as written.

## Known Stubs

None. Both files are test infrastructure, not production features. The v2 tests are intentionally failing (RED) against the v1 ABC; they are not stubs.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced. The `tmp_plugins_dir` fixture writes a static `.py` file to pytest's ephemeral `tmp_path`; content is in-repo authored code, not user-supplied.
