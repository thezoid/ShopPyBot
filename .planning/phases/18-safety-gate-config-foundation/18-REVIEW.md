---
phase: 18-safety-gate-config-foundation
reviewed: 2026-06-11T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - core/cli/__init__.py
  - core/cli/config_cmd.py
  - core/cli/run.py
  - core/config_schema.py
  - core/orchestrator.py
  - core/plugin_base.py
  - plugins/shopbot_plugin_amazon.py
  - plugins/shopbot_plugin_bestbuy.py
  - plugins/shopbot_plugin_gamestop.py
  - plugins/shopbot_plugin_newegg.py
  - plugins/shopbot_plugin_squareenix.py
  - plugins/shopbot_plugin_target.py
  - plugins/shopbot_plugin_walmart.py
  - tests/test_cli_run.py
  - tests/test_config_schema.py
  - tests/test_orchestrator.py
  - tests/test_plugin_base.py
  - tests/test_plugin_bestbuy.py
  - tests/test_safety_gate.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 18: Code Review Report

**Reviewed:** 2026-06-11
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 18 introduces a monitor-only run mode, the `place_order_guarded()` ABC method, a `CheckoutConfig` schema, and reroutes all 7 plugins' final place-order clicks through the guard. The architecture is sound: the ABC's guard method, the orchestrator's pre-buy monitor_only skip, and the CLI flag all compose correctly. The `test_mode` fail-safe default (True = suppress) is correct. Two critical defects remain: (1) the `monitor_only` fail-safe default in `place_order_guarded` is backwards, and (2) Amazon's `auto_buy` contains an unguarded intermediate DOM click (`buy_now.click()`) that executes before `place_order_guarded` is reached, executing real checkout steps even when the guard ultimately suppresses. A test reliability defect and two informational items are also noted.

## Critical Issues

### CR-01: `monitor_only` fail-safe default is inverted in `place_order_guarded`

**File:** `core/plugin_base.py:93`
**Issue:** The docstring states: "Safe-default behavior when config or debug is absent: test_mode defaults to True (suppressed) so a missing/partial config always prevents an order being placed." This is true for `test_mode`, but `monitor_only` uses the opposite default. `getattr(debug, "monitor_only", False)` defaults to `False` = allow. If `debug` is a non-None object that lacks the `monitor_only` attribute (pre-Phase-18 config object, partial mock, deserialized legacy config), the guard passes through and the order is placed. The two flags should both fail-safe to suppress.

**Fix:**
```python
# plugin_base.py:91-94  -- change monitor_only default from False to True
debug = getattr(self.config, "debug", None) if self.config else None
test_mode = getattr(debug, "test_mode", True)
monitor_only = getattr(debug, "monitor_only", True)   # was False; fail-safe must suppress
if test_mode or monitor_only:
```

Note: `DebugConfig.monitor_only` defaults to `False` in the schema, so normal configs behave correctly. Only pathological/legacy configs are affected. But the stated invariant is violated.

### CR-02: Amazon `auto_buy` executes an unguarded `buy_now.click()` before `place_order_guarded`

**File:** `plugins/shopbot_plugin_amazon.py:399-411`
**Issue:** The `place_order_guarded` call on line 411 protects only the final "Place Order" confirm button. Before reaching it, line 403 performs `await buy_now.click()` -- a direct, unguarded DOM click that navigates the browser to the checkout confirmation page. In `test_mode=True`, the `test_pause_event` wait (lines 391-396) pauses execution but does NOT suppress the subsequent `buy_now.click()` -- the click fires after the user presses Enter. If `auto_buy` were ever called directly with `test_mode=True, monitor_only=False` (bypassing the orchestrator's pre-buy skip), the session would advance to the checkout confirmation page before being stopped by `place_order_guarded`. For defense-in-depth, intermediate purchase-path clicks should also be guarded or the method should return False early.

The orchestrator's monitor_only pre-check prevents this in production, but `auto_buy` violates the principle that the method itself should be safe to call in any guarded state without causing unintended checkout navigation.

**Fix:**
```python
# plugins/shopbot_plugin_amazon.py -- add early-return guard at entry of auto_buy
async def auto_buy(self, url: str) -> bool:
    writeLog(f"Entering auto_buy for Amazon: {url}", "DEBUG")
    # Defense-in-depth: refuse at method boundary, not just at final click
    debug = getattr(self.config, "debug", None) if self.config else None
    if getattr(debug, "test_mode", True) or getattr(debug, "monitor_only", True):
        writeLog("[AmazonPlugin] auto_buy suppressed (test_mode/monitor_only)", "INFO")
        return False
    await self.login()
    ...
```
Alternatively, route `buy_now.click()` through `place_order_guarded` as a first-stage guard call, which would cleanly handle test_mode and monitor_only before any checkout navigation occurs.

## Warnings

### WR-01: `test_safety_gate.py:test_monitor_only_gate_via_orchestrator` missing DB patches -- test will fail in CI

**File:** `tests/test_safety_gate.py:152-183`
**Issue:** `_check_and_buy` internally calls `get_item_notification_state_sync` (line 222 in orchestrator.py) and `get_last_price_sync`/`append_price_history_sync` (lines 215-217) via `loop.run_in_executor`. Neither is patched in `test_monitor_only_gate_via_orchestrator`. With no running DB or mocked executor, these calls will raise `OperationalError` (no table) or similar, causing the test to either silently swallow the exception (if the orchestrator catches it) or fail with an unexpected error. In contrast, other orchestrator tests patch `get_item_notification_state_sync` and `writeLog`. This test relies on exception-swallowing behavior to pass, which is a reliability anti-pattern.

**Fix:**
```python
async def test_monitor_only_gate_via_orchestrator(fake_plugin):
    ...
    with (
        patch("core.orchestrator.get_item_notification_state_sync", return_value=(False, None)),
        patch("core.orchestrator.get_last_price_sync", return_value=None),
        patch("core.orchestrator.append_price_history_sync"),
        patch("core.orchestrator.get_item_price_config_sync", return_value=None),
        patch("core.orchestrator.writeLog"),
    ):
        await _check_and_buy(
            plugin, "Test Item", "https://fake.example.com/item", True, write_queue
        )
```

### WR-02: `handle_run` mutates a Pydantic model instance in-place without propagating via service

**File:** `core/cli/run.py:21-23`
**Issue:** `cfg.debug.monitor_only = True` mutates the `DebugConfig` Pydantic model returned by `svc.get_config()`. This works for `svc.run(cvv)` because `BotService.run()` uses `self._cfg` (the same object). However, `svc.get_config()` returns the internal model reference without a defensive copy, so any other concurrent caller that holds a reference to the config also sees the mutation. More critically, if `BotService` were ever changed to return a copy from `get_config()` (a reasonable refactor), the mutation would be silently dropped and monitor_only would no longer be honored. The correct pattern is to pass monitor_only as a parameter to `run()` rather than mutating the config.

**Fix:**
```python
# core/cli/run.py -- pass flag as parameter rather than mutating config
def handle_run(args, svc) -> int:
    cfg = svc.get_config()
    monitor_only = getattr(args, "monitor_only", False) or cfg.debug.monitor_only
    needs_cvv = (
        not cfg.debug.test_mode
        and not monitor_only
        and any(...)
    )
    ...
    svc.run(cvv, monitor_only=monitor_only)   # BotService.run() accepts flag
```

### WR-03: Static test `test_no_raw_place_order_click_in_plugins` has a false-negative gap

**File:** `tests/test_safety_gate.py:87-108`
**Issue:** The test checks whether a file that contains a place-order selector ALSO contains the string `place_order_guarded`. This is file-level, not call-level. A file that calls `place_order_guarded` for one place-order path but has a separate raw `.click()` on a different place-order element would pass the test. The selector list `_PLACE_ORDER_SELECTORS` also uses partial strings (e.g., `"place-order-button"` matches both `data-testid="place-order-button"` and `class="place-order-button"`). The test provides useful CI coverage but should not be considered a guarantee that every place-order path is guarded.

**Fix:** Augment with a per-occurrence check: for each line containing a place-order selector followed by `.click()`, verify that the enclosing function body uses `place_order_guarded`. Alternatively, document the known limitation as a comment in the test so future authors don't rely on it for full coverage.

## Info

### IN-01: Amazon `auto_buy` has a redundant inline `test_mode` check that diverges from `place_order_guarded`

**File:** `plugins/shopbot_plugin_amazon.py:391-396`
**Issue:** Lines 391-396 check `self.config.debug.test_mode` directly to trigger a browser-review pause before clicking buy-now. This is a UX feature (inspect the cart before the guarded final click), but it reads `test_mode` directly instead of going through a shared helper. If the attribute access pattern for test_mode ever changes (e.g., renamed, moved), this inline check would need to be updated separately from `place_order_guarded`. Low risk but creates two code paths for the same flag.

### IN-02: `config set monitor_only` writes to `debug.monitor_only` in YAML but `handle_run` overwrites at runtime

**File:** `core/cli/config_cmd.py:17-21` and `core/cli/run.py:21-23`
**Issue:** `config set monitor_only true` persists `debug.monitor_only=true` in `config.yml`. But `handle_run` also sets `cfg.debug.monitor_only = True` when `--monitor-only` is passed, and does NOT reset it to False when `--monitor-only` is absent. So if `config.yml` has `monitor_only: true` and the user runs `shoppybot run` (no flag), monitor_only is honored from the YAML. If `config.yml` has `monitor_only: false` but the user passes `--monitor-only`, the flag wins. These are both correct. The informational note is that there is no way to override a `config.yml monitor_only: true` at the CLI level for a single run without editing the file. This may surprise users who expect `shoppybot run` (no flag) to mean "not monitor-only." No code change needed unless a `--no-monitor-only` override flag is desired.

---

_Reviewed: 2026-06-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
