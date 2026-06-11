---
phase: 20-checkout-profile-form-fill
plan: "03"
subsystem: checkout-cvv-threading
tags: [cvv, amazon, orchestrator, security, tdd]
dependency_graph:
  requires: []
  provides: [AmazonPlugin._cvv, orchestrator-amz-injection, needs_cvv-amazon]
  affects: [plugins/shopbot_plugin_amazon.py, core/orchestrator.py, core/cli/run.py]
tech_stack:
  added: []
  patterns: [attribute-injection-after-setup, needs_cvv-predicate-extension, ast-scan-never-logged]
key_files:
  created:
    - tests/test_cvv_threading.py
  modified:
    - plugins/shopbot_plugin_amazon.py
    - core/orchestrator.py
    - core/cli/run.py
decisions:
  - "Repeated `if cvv:` guard in orchestrator instead of shared block -- matches existing BestBuy style for independent readability (PATTERNS.md exact analog)"
  - "AST scan flags ast.Name nodes containing _cvv in writeLog/print args; ast.Constant prompt string excluded to avoid false positives"
  - "Python 3.14 env (via rtk) has pre-existing nodriver cdp SyntaxError; tests pass on project Python 3.13 (617 passed, 2 skipped)"
metrics:
  duration: "7 minutes"
  completed_date: "2026-06-11"
  tasks: 2
  files: 4
requirements: [BUY-07]
---

# Phase 20 Plan 03: CVV Threading to Amazon Plugin Summary

Amazon CVV injection path wired end-to-end: `AmazonPlugin.__init__` initializes `self._cvv = None`, the orchestrator injects `amz_plugin._cvv = cvv` after `_staggered_setup`, and `needs_cvv` in `run.py` now fires the getpass prompt for amazon.com auto_buy items.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Init Amazon _cvv, orchestrator injection, extend needs_cvv | f59467c | plugins/shopbot_plugin_amazon.py, core/orchestrator.py, core/cli/run.py |
| 2 | CVV threading tests | 7538805 | tests/test_cvv_threading.py |

## What Was Built

Task 1 made three coordinated edits:

1. `plugins/shopbot_plugin_amazon.py`: `self._cvv = None` added immediately after `super().__init__(config)` with SEC-02 comment (mirrors BestBuy __init__ line 46 exactly).

2. `core/orchestrator.py`: Amazon injection block added immediately after the existing BestBuy block (lines 411-414). Both blocks use a separate `if cvv:` guard per the existing style.

3. `core/cli/run.py`: `needs_cvv` any() predicate extended from `"bestbuy.com" in item.link` to `("bestbuy.com" in item.link or "amazon.com" in item.link)`.

Task 2 created `tests/test_cvv_threading.py` with 10 tests covering: Amazon _cvv default None, needs_cvv true/false matrix (amazon auto_buy, test_mode short-circuit, monitor_only short-circuit), BestBuy regression, orchestrator injection with fake registry, injection skipped when cvv=None, injection no-op when registry returns None, and AST scan confirming cvv never appears as a variable arg to writeLog/print.

## Verification

- `pytest tests/test_cvv_threading.py -x`: 10/10 passed
- `pytest tests/test_cli_run.py tests/test_orchestrator.py -x`: 33/33 passed (no regression)
- Full suite: 617 passed, 2 skipped

## Deviations from Plan

None - plan executed exactly as written. The orchestrator injection block uses repeated `if cvv:` guards (one per retailer) per the documented analog pattern.

## Known Stubs

None. The CVV attribute is initialized to None as a placeholder for orchestrator injection - this is the intended design, not a stub. The form-fill usage of `self._cvv` is Plan 04 (Wave 2) by design.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced. The CVV threading path was already planned in the threat model:

- T-20-05 (cvv in writeLog): mitigated - AST scan test confirms zero violations
- T-20-06 (cvv persisted): mitigated - cvv is parameter only; no store.set calls added

## Self-Check: PASSED

- `plugins/shopbot_plugin_amazon.py`: self._cvv = None present (commit f59467c)
- `core/orchestrator.py`: amz_plugin._cvv = cvv block present (commit f59467c)
- `core/cli/run.py`: amazon.com in needs_cvv predicate present (commit f59467c)
- `tests/test_cvv_threading.py`: file exists (commit 7538805)
- Commits verified: f59467c, 7538805 in git log
