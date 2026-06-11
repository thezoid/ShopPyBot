---
phase: 18-safety-gate-config-foundation
plan: "03"
subsystem: orchestrator, cli
tags: [monitor-only, safety-gate, cli-flag, buy-01]
dependency_graph:
  requires: [18-01]
  provides: [monitor_only_gate_enforced, cli_flag_wired, cvv_suppressed]
  affects: [core/orchestrator.py, core/cli/__init__.py, core/cli/run.py, core/cli/config_cmd.py]
tech_stack:
  added: []
  patterns: [getattr-safe config access, argparse store_true flag, pydantic mutation]
key_files:
  created: []
  modified:
    - core/orchestrator.py
    - core/cli/__init__.py
    - core/cli/run.py
    - core/cli/config_cmd.py
    - tests/test_orchestrator.py
    - tests/test_cli_run.py
decisions:
  - "monitor_only gate uses getattr-safe access on plugin.config to avoid AttributeError when config=None in tests"
  - "Gate placed INSIDE if auto_buy: block so stock-availability detected alert always fires first (T-18-08)"
  - "needs_cvv adds not cfg.debug.monitor_only; no checkout will run so CVV collection is pointless (T-18-09)"
metrics:
  duration: "8 minutes"
  completed: "2026-06-11"
  tasks: 2
  files: 6
---

# Phase 18 Plan 03: Monitor-Only Wire-Up Summary

Monitor-only run mode wired end to end: orchestrator gate blocks _try_auto_buy when debug.monitor_only is True; --monitor-only CLI flag mutates cfg.debug.monitor_only; CVV prompt suppressed; ALLOWLIST entry enables `config set monitor_only true`.

## Tasks Completed

| Task | Name | Commit (RED) | Commit (GREEN) | Files |
|------|------|-------------|----------------|-------|
| 1 | monitor_only gate in _check_and_buy | 61973b6 | 8dc5d6c | core/orchestrator.py, tests/test_orchestrator.py |
| 2 | --monitor-only CLI flag + config mutation + CVV + ALLOWLIST | d4f3807 | ae3c6af | core/cli/__init__.py, core/cli/run.py, core/cli/config_cmd.py, tests/test_cli_run.py |

## What Was Built

**Task 1 (orchestrator gate):** Inside `_check_and_buy`, within the `if auto_buy:` block (after the detected alert fires at lines 224-229), a guard reads `plugin.config.debug.monitor_only` getattr-safely. When True, logs an INFO skip message and returns without calling `_try_auto_buy`. The gate is inside `if auto_buy:` so the stock-availability `detected` alert and `set_available` write always execute regardless of monitor_only state.

**Task 2 (CLI):**
- `core/cli/__init__.py`: `--monitor-only` (store_true, dest=monitor_only) added to the `run` subparser, mirroring the `--auto-buy` idiom.
- `core/cli/run.py`: After `cfg = svc.get_config()`, if `args.monitor_only` is True, `cfg.debug.monitor_only = True` is set (CLI override pattern; mutates existing pydantic v2 model instance, does not reconstruct). `needs_cvv` gains `and not cfg.debug.monitor_only` so the getpass prompt is never reached when monitor_only is active.
- `core/cli/config_cmd.py`: `"monitor_only": ("debug", bool)` added to `ALLOWLIST` so `shoppybot config set monitor_only true` is accepted.

## Test Coverage

New tests in `tests/test_orchestrator.py`:
- `test_monitor_only_skips_try_auto_buy`: monitor_only=True, auto_buy=True -> _try_auto_buy NOT awaited; detected fires
- `test_monitor_only_false_calls_try_auto_buy`: monitor_only=False -> _try_auto_buy IS awaited (regression)
- `test_monitor_only_set_available_not_purchased`: set_available enqueued; purchased never enqueued

New tests in `tests/test_cli_run.py`:
- `test_monitor_only_flag_parses_true`: `run --monitor-only` -> args.monitor_only is True
- `test_monitor_only_flag_absent_is_false`: absent flag -> args.monitor_only is False
- `test_handle_run_monitor_only_mutates_config`: handle_run sets cfg.debug.monitor_only=True
- `test_handle_run_monitor_only_skips_cvv_prompt`: bestbuy auto_buy + monitor_only -> getpass not called
- `test_allowlist_contains_monitor_only`: ALLOWLIST["monitor_only"] == ("debug", bool)

Full suite: 567 passed, 2 skipped.

## Deviations from Plan

**1. [Rule 2 - Missing Safety] getattr-safe plugin.config access in orchestrator gate**

- Found during: Task 1 implementation
- Issue: `fake_plugin` fixture creates plugins with `config=None`; accessing `plugin.config.debug.monitor_only` directly would raise AttributeError on existing tests using `config=None`.
- Fix: Used `getattr(plugin.config, "debug", None) if plugin.config is not None else None` then `getattr(debug_cfg, "monitor_only", False)` -- same pattern as `place_order_guarded` in plan 18-02. Defaults to False (fail-open for availability monitoring, not for purchases -- correct disposition).
- Files modified: core/orchestrator.py
- Commit: 8dc5d6c

## TDD Gate Compliance

- Task 1 RED gate: 61973b6 `test(18-03):`
- Task 1 GREEN gate: 8dc5d6c `feat(18-03):`
- Task 2 RED gate: d4f3807 `test(18-03):`
- Task 2 GREEN gate: ae3c6af `feat(18-03):`

Both RED/GREEN gate sequences present. No REFACTOR pass needed (code is already minimal and clear).

## Known Stubs

None.

## Threat Flags

None -- no new trust boundaries introduced. T-18-07, T-18-08, T-18-09 from the plan's threat register are all mitigated as designed.

## Self-Check: PASSED

- core/orchestrator.py: FOUND
- core/cli/__init__.py: FOUND
- core/cli/run.py: FOUND
- core/cli/config_cmd.py: FOUND
- tests/test_orchestrator.py: FOUND
- tests/test_cli_run.py: FOUND
- 61973b6: FOUND
- 8dc5d6c: FOUND
- d4f3807: FOUND
- ae3c6af: FOUND
