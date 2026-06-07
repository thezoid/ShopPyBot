---
phase: 04-async-orchestrator
plan: "04"
subsystem: plugins
tags: [asyncio, event-driven, plugin, security, async-03, async-05]
dependency_graph:
  requires: ["04-01", "04-03"]
  provides: ["asyncio.Event intervention pattern on AmazonPlugin", "sole write path via orchestrator queue"]
  affects: ["plugins/shopbot_plugin_amazon.py", "plugins/shopbot_plugin_bestbuy.py"]
tech_stack:
  added: []
  patterns: ["asyncio.Event notify-wait-clear", "write-queue sole ownership", "AST-based static analysis test"]
key_files:
  created:
    - tests/test_no_input.py
  modified:
    - plugins/shopbot_plugin_amazon.py
    - plugins/shopbot_plugin_bestbuy.py
    - tests/test_plugin_amazon.py
    - tests/test_plugin_bestbuy.py
decisions:
  - "asyncio.Event attrs live on AmazonPlugin only (not on RetailerPlugin ABC); BestBuy has no input() sites and needs no events. The stdin listener uses getattr(..., None) so plugins lacking the attrs are skipped safely."
  - "test_no_input.py uses Python AST parsing (not text grep) to find input() call nodes, correctly excluding docstring and comment occurrences (e.g., orchestrator.py module docstring mentions the word input() for documentation purposes)."
  - "test_wait_user_action_timeout_does_not_raise uses patch.object on the importlib-loaded module object (not a string import path) and closes the unawaited coroutine to avoid ResourceWarning -- keeps CI fast."
metrics:
  duration: "~15 minutes (excluding 300s initial test hang on first run)"
  completed: "2026-06-03"
  tasks_completed: 2
  files_changed: 5
---

# Phase 4 Plan 4: Input() Removal and Write-Queue Sole Path Summary

asyncio.Event pattern replaces all 5 Amazon input() blocking calls; both plugins' direct DB writes removed so the orchestrator queue is the sole write path.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Replace 5 Amazon input() calls with asyncio.Event pattern | 22b0a6d | plugins/shopbot_plugin_amazon.py, tests/test_plugin_amazon.py |
| 2 | Remove direct DB writes from plugins; add static no-input() test | d34ee6b | plugins/shopbot_plugin_bestbuy.py, tests/test_plugin_bestbuy.py, tests/test_no_input.py |

## What Was Built

### Task 1: asyncio.Event Intervention Pattern (ASYNC-03)

AmazonPlugin now has four `asyncio.Event` attributes in `__init__`:
- `captcha_event` -- CAPTCHA intervention in `check_availability`
- `passkey_event` -- passkey dismiss in `login`
- `otp_event` -- MFA/OTP entry in `login`
- `test_pause_event` -- test mode pauses in `auto_buy` (reused for both sites)

The helper `_wait_user_action(event, message)`:
1. Calls `play_notification_sound()` to alert the user
2. Logs the actionable message at WARNING level
3. `await asyncio.wait_for(event.wait(), timeout=300)` -- 5-min unattended guard (T-04-14)
4. On `asyncio.TimeoutError`: logs "timed out -- continuing" and continues (T-04-14)
5. `event.clear()` in `finally` -- ensures next poll cycle genuinely re-waits (Pitfall 7, T-04-15)

All 5 `input()` sites replaced:
- `check_availability`: captcha_event + "CAPTCHA detected on Amazon. Solve it in the browser, then press Enter."
- `login` (passkey): passkey_event + "Amazon passkey prompt visible. Dismiss it in the browser, then press Enter."
- `login` (OTP): otp_event + "MFA/OTP prompt detected. Enter your code in the browser, then press Enter."
- `auto_buy` (test pre-buy): test_pause_event + "TEST MODE: review the browser, then press Enter to continue."
- `auto_buy` (test post-order): test_pause_event + "TEST MODE: order review complete. Press Enter to continue."

Security: `_wait_user_action` never reads, echoes, or stores typed text (T-04-13). The user interacts with the browser; the bot only observes an asyncio.Event set by the stdin listener thread.

### Task 2: Remove Direct DB Writes (ASYNC-05)

Both plugins no longer import or call `update_item_purchased` directly:
- `shopbot_plugin_amazon.py`: `from models import update_item_purchased` removed; `update_item_purchased(url)` call in `auto_buy` removed
- `shopbot_plugin_bestbuy.py`: same removal

`auto_buy` in both plugins returns `True` on success. The orchestrator's `run_plugin` (Plan 03) calls `await write_queue.put(url)` after a successful `auto_buy`, driving the sole write path through `_write_queue_drain` (T-04-16).

Static test `tests/test_no_input.py` scans `plugins/`, `core/`, `main.py` using Python AST (`ast.walk`) to find actual `Call` nodes for `input`. This correctly excludes docstrings and comments (the orchestrator module docstring says "No input() anywhere in this module" -- text grep would false-positive, AST does not).

## Decisions Made

1. Event attributes on AmazonPlugin only (not on RetailerPlugin ABC). BestBuy has no input() sites. The stdin listener uses `getattr(plugin, attr, None)` so plugins without those attrs are skipped without any change to BestBuy.

2. AST-based static analysis for test_no_input.py. Text-grep false-positived on `orchestrator.py` line 10 (docstring: "No input() anywhere in this module"). The AST approach is the correct tool: only actual call expression nodes trigger the assertion.

3. `test_wait_user_action_timeout_does_not_raise` patches `asyncio.wait_for` via `patch.object` on the importlib-loaded module object. The coroutine created by `event.wait()` is explicitly closed in the mock to prevent `RuntimeWarning: coroutine was never awaited`. Tests run fast (< 2s vs 301s for the naive unpatched version).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Timeout test caused 300s hang in initial run**
- Found during: Task 1 test development
- Issue: `test_wait_user_action_timeout_does_not_raise` initially did not mock `asyncio.wait_for`, causing the real 300-second `asyncio.wait_for(event.wait(), timeout=300)` to execute in CI. The test passed (correctly), but took 301 seconds.
- Fix: Replaced `patch("plugins.shopbot_plugin_amazon.asyncio")` (string import, wrong module registry key) with `patch.object(_amazon_module.asyncio, "wait_for", _fast_timeout)` where `_fast_timeout` closes the coroutine and raises `TimeoutError` immediately.
- Files modified: tests/test_plugin_amazon.py
- Commit: 22b0a6d

**2. [Rule 1 - Bug] Static test false-positive on orchestrator.py docstring**
- Found during: Task 2 test development
- Issue: First implementation of `test_no_input.py` used line-text scanning; it matched `orchestrator.py:10: - No input() anywhere in this module` (inside a module docstring, not a Python call).
- Fix: Rewrote scanner to use `ast.parse` and `ast.walk` to find actual `ast.Call` nodes where `func.id == 'input'`. Docstrings and comments are never call nodes in the AST.
- Files modified: tests/test_no_input.py
- Commit: 38b1fe3

## Known Stubs

None. All intervention sites are wired to real `asyncio.Event` objects. The write-queue path is wired end-to-end (Plan 03 orchestrator owns `write_queue.put`).

## Threat Flags

None. All T-04-13 through T-04-16 threats are mitigated as specified in the plan's threat register.

## Verification Results

```
# Full suite
.venv/Scripts/python.exe -m pytest tests/ -q
67 passed, 1 warning in 3.10s

# Warning is pre-existing: test_check_availability_never_raises (out of scope)
```

```
# No input() calls in async paths
AST scan: input() calls found: NONE

# asyncio.Event() instantiations in non-comment lines
grep -v '^[ \t]*#' plugins/shopbot_plugin_amazon.py | grep -c 'asyncio.Event()' -> 4

# No update_item_purchased import/call in plugins (AST verified)
No import/call violations found
```

## Self-Check: PASSED

- plugins/shopbot_plugin_amazon.py: FOUND
- plugins/shopbot_plugin_bestbuy.py: FOUND
- tests/test_plugin_amazon.py: FOUND
- tests/test_plugin_bestbuy.py: FOUND
- tests/test_no_input.py: FOUND
- Commits 0435ac3, 22b0a6d, 38b1fe3, d34ee6b: all present in git log
