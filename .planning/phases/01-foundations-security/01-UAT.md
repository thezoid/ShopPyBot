---
status: partial
phase: 01-foundations-security
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md, 01-05-SUMMARY.md]
started: 2026-06-02T17:20:20Z
updated: 2026-06-02T17:50:00Z
---

## Current Test

[testing paused — 1 item (Test 4) blocked on a live BestBuy stock event + interactive TTY]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running bot. Delete data/shop_py_bot.db. Run `python main.py` with a valid config.yml. App boots clean (no stack trace), config validates, DB is recreated + seeded from config items, ChromeDriver launches, polling loop starts checking the first item.
result: pass
note: "Initially FAILED (blocker): crashed at initialize_db() with sqlite3.OperationalError because data/ dir was absent on fresh checkout. FIXED in this session (models.py: os.makedirs before connect). Re-run confirmed: DB seeded with 5 items, chromedriver downloaded, loop entered 'Starting new iteration of item checks' and checked Amazon items sequentially. No traceback."

### 2. Test Suite Green
expected: Run `pytest` (or `python -m pytest tests/ -q`) from repo root. All tests pass (~15 passed), exit code 0. Only warning is the pre-existing pygame pkg_resources deprecation.
result: pass

### 3. Startup Config Validation
expected: Introduce a bad value in config.yml (e.g. set debug.logging_level to a string like "high"). Run `python main.py`. App exits cleanly with a readable validation error naming the bad field, NOT a raw Python traceback. Restore config after.
result: pass
note: "Initially FAILED (major): debug.logging_level='high' produced a raw TypeError at logger.py:38 because logger read config.yml raw at import with no int coercion. FIXED in this session (logger.py: int() coercion + ValueError in except). Re-run confirmed: logger falls back to 5, AppConfig then rejects the value cleanly -> 'Configuration error -- fix config.yml: debug.logging_level Input should be a valid integer', exit 1, no traceback. AppConfig-routed fields (e.g. quantity) already validated cleanly."

### 4. Missing Credentials Handled Gracefully
expected: With a BestBuy item set auto_buy=true and BB_EMAIL / BB_PASSWORD env vars unset, run the bot until that item is found (or trigger the buy path). The bot logs an actionable ERROR about missing credentials and skips the purchase WITHOUT crashing the loop.
result: blocked
blocked_by: other
reason: "Cannot fully observe in an automated run: the buy branch (main.py:169-178) fires only when check_bestbuy_item returns available=True for a real BestBuy auto_buy item, AND the startup CVV gate must first be satisfied via an interactive TTY (test_mode is false in this scenario). Two compounding requirements: live BestBuy stock event + interactive terminal. Branch code-verified (main.py:173-178): when BB_EMAIL/BB_PASSWORD unset it logs 'ERROR: BB_EMAIL or BB_PASSWORD env var not set. Skipping auto-buy for this item.' and falls through WITHOUT calling auto_buy_bestbuy_item and WITHOUT crashing the loop. MANUAL REPRO: in an interactive terminal, set test_mode: false, add an in-stock bestbuy.com auto_buy item, leave BB_EMAIL/BB_PASSWORD unset, enter a dummy CVV at the prompt, and confirm the ERROR log + loop continues when the item is found available."

### 5. CVV Runtime Prompt
expected: With a BestBuy auto_buy item configured and BB credentials set, on startup the bot shows a hidden CVV prompt (getpass — typed digits do not echo). Check-only runs (no BestBuy auto_buy item) do NOT prompt for CVV.
result: pass
note: "Verified by live behavioral run. Set test_mode: false + first item link to bestbuy.com with auto_buy: true. Bot set up the driver then HALTED before any item check (no 'Starting new iteration of item checks' in log), blocking at collect_cvv()'s hidden getpass prompt (Windows getpass reads the console directly, so a redirected empty stdin did not satisfy it — it waited for keystrokes = the hidden no-echo prompt). Contrast: Test 1 (test_mode true, amazon-only) ran the loop immediately with no prompt. Both gate branches (main.py:125-129) confirmed: prompt fires at startup ONLY when not test_mode AND a bestbuy.com auto_buy item exists. Interactive keystroke entry + no-echo is getpass's library guarantee, not separately keystroke-tested."

### 6. README Disclaimer
expected: Open README.md. Disclaimer section covers personal/non-commercial use, retailer Terms-of-Service responsibility, account suspension/ban risk, and an as-is/no-warranty clause.
result: pass

## Summary

total: 6
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 1

Note: Tests 1 and 3 initially failed (1 blocker, 1 major); both fixed in this UAT session (models.py + logger.py) and re-verified passing. Test 5 (CVV prompt) verified by live behavioral run (gate fires at startup under test_mode false + bestbuy auto_buy). Test 4 (missing-cred skip) remains blocked: needs a live-AVAILABLE BestBuy auto_buy item plus an interactive TTY to pass the CVV gate first; the skip branch is code-verified.

## Gaps

- truth: "Fresh `python main.py` boots, seeds the SQLite DB, and starts the polling loop"
  status: fixed
  reason: "User reported: cold start crashed at initialize_db() with sqlite3.OperationalError: unable to open database file. data/ dir absent on fresh checkout (.gitignore:8 ignores data/*); models.py:9 sqlite3.connect(DB_PATH) does not create the parent directory."
  severity: blocker
  test: 1
  root_cause: "models.py initialize_db() connects to data/shop_py_bot.db without ensuring the data/ directory exists; .gitignore ignores data/* so the dir is absent on any fresh checkout"
  artifacts:
    - path: "models.py"
      issue: "initialize_db() calls sqlite3.connect(DB_PATH) at line 9 with no os.makedirs for the parent dir"
  missing:
    - "Create data/ parent directory before sqlite3.connect (e.g. os.makedirs(os.path.dirname(DB_PATH), exist_ok=True))"
  debug_session: ""

- truth: "Bad debug.logging_level in config.yml produces a clean validation error, not a raw traceback"
  status: fixed
  reason: "User reported: debug.logging_level='high' crashes with raw TypeError at logger.py:38 ('>=' not supported between str and int). logger._load_logging_level reads config.yml raw at import and returns the value uncoerced; AppConfig never validates it because writeLog (main.py:53) runs before AppConfig() (~line 105)."
  severity: major
  test: 3
  root_cause: "logger._load_logging_level() returns settings.get('debug',{}).get('logging_level', 5) with no int() coercion; a present-but-non-int value passes through (only FileNotFoundError/KeyError/TypeError are caught at load, not the deferred comparison-time TypeError), so _LOGGING_LEVEL becomes a str and writeLog's '>=' comparison crashes"
  artifacts:
    - path: "logger.py"
      issue: "_load_logging_level (lines 12-18) does not coerce logging_level to int or validate range; annotated -> int but can return str"
  missing:
    - "Coerce logging_level to int with a safe fallback in _load_logging_level (wrap in int(), add ValueError/TypeError to the except and clamp/fallback to 5)"
  debug_session: ""
