# Plan 06-03 SUMMARY (target-plugin)

**Status:** Complete
**Date:** 2026-05-15
**Requirement:** PLG-05 (Target plugin with Akamai-bypass-resistant defaults; auto-buy labeled experimental)

## What shipped

- `plugins/shopbot_plugin_target.py` (117 lines): TargetPlugin(RetailerPlugin) using nodriver
  - `name = "target"`, `domain_pattern = ["target.com"]`, `login_at_startup = False`
  - `__init__` reads `SHOPBOT_ENABLE_RISKY_AUTOBUY` env once (env-at-init pattern), stores on `self._riskyAutoBuyEnabled`
  - `__init__` logs a WARNING via writeLog if `platform_config.headless` is True (Akamai consistently blocks headless on Target)
  - Module docstring labels auto-buy EXPERIMENTAL with Akamai context
  - `async def open(self)` awaits `uc.start(headless=..., browser_args=[--user-agent=...])` with random.choice from self._userAgents
  - `async def shutdown(self)` uses `inspect.isawaitable()` fallback to handle the O-3 sync-stop surprise discovered in 06-02
  - `async def check_availability(url)` uses nodriver Tab API
  - `async def auto_buy(url, config)` short-circuits with WARNING when env gate is off
- `tests/test_plugins_target.py` (23 GREEN tests): ABC contract, env gate matrix, Akamai headless warning, AST hygiene (no selenium imports), uc.start mock, shutdown sync/async/raises paths

## Locked decisions honored

- D-01: nodriver-based plugin; no selenium imports (AST verified)
- D-02: SHOPBOT_ENABLE_RISKY_AUTOBUY env-at-init gate (single os.environ.get read)
- D-04: respects platform_config.headless; warns about Akamai when True

## Test results

- `tests/test_plugins_target.py`: 23 GREEN
- Regression suite: 339 passed, 1 skipped (Walmart O-1 opt-in), 0 new failures

## Notable findings

**Environment quirk (non-blocking):** nodriver 0.50.3 is incompatible with Python 3.14 (`cdp/network.py` line 1345 has non-UTF-8 byte without PEP 263 declaration). All Wave 1 nodriver plugin tests must run under Python 3.13. Test environment must use the project venv (Python 3.13), not the system Python 3.14. Pinning Python 3.13 in pyproject.toml is already in place from Phase 1.

## Deviation log

None. Plan executed as specified, with the O-3 `inspect.isawaitable()` shutdown pattern carried forward from 06-02 (Walmart smoke test discovered nodriver's `Browser.stop()` is sync).

## Files

- Created: `plugins/shopbot_plugin_target.py`
- Modified: `tests/test_plugins_target.py` (RED skeleton → GREEN)
- Created: this SUMMARY.md
