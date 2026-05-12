---
phase: 01-foundations-security
plan: 06
subsystem: integration
tags: [integration, main, readme, disclaimer, sec-06]
requires:
  - 01-01-test-infra-and-pinned-deps
  - 01-02-plugin-abc-contract
  - 01-03-pydantic-config-schema
  - 01-04-driver-hardening
  - 01-05-credentials-and-logger
provides:
  - wired-main-entrypoint
  - sec-06-disclaimer
  - config-py-retirement-shim
affects:
  - main.py
  - amazon_bot.py
  - config.py
  - README.md
tech-stack:
  patterns:
    - AppConfig() at startup with try/except + sys.exit on validation error
    - Python version guard at top of main.py before non-sys imports
    - config.py raises ImportError as migration tripwire
key-files:
  created:
    - tests/test_main_smoke.py
    - tests/test_docs.py
  modified:
    - main.py
    - amazon_bot.py
    - config.py
    - README.md
decisions:
  - "config.py retained as ImportError shim rather than deleted (catches stale `from config import config` imports loudly)"
  - "bestbuy_bot.py left untouched: already accepts credential args directly (Option A signature)"
  - "Polling loop split into _handle_amazon and _handle_bestbuy helpers to keep main() under the 30-line guidance"
metrics:
  tasks_completed: 2
  files_created: 2
  files_modified: 4
  duration_minutes: ~10
  completed: 2026-05-12
---

# Phase 01 Plan 06: Main Integration and README Summary

Wired AppConfig, build_driver, collect_cvvs, and logger.configure into main.py; propagated platform-credential reads into amazon_bot.amz_sign_in; retired config.py as an ImportError shim; and added the SEC-06 personal-use/TOS/account-risk disclaimer to README.md. Two source-grep smoke tests now lock the integration invariants.

## Tasks Completed

| Task | Name                                                                  | Commit  |
| ---- | --------------------------------------------------------------------- | ------- |
| 1    | Write smoke tests for main.py invariants and README disclaimer (RED)  | 3dfde83 |
| 2    | Rewrite main.py, edit bot modules, retire config.py, README (GREEN)   | 9a38c1a |

## Integration Points

- main.py imports: `from config_schema import AppConfig`, `from driver import build_driver`, `from credentials import collect_cvvs`, `from logger import configure as configure_logger, writeLog`.
- Python version guard at top of file: `if sys.version_info < (3, 11): sys.exit(...)` with "3.11+" in the message.
- BestBuy auto_buy call now reads `app_config.platforms['bestbuy'].credentials.email/.password` plus `cvvs['bestbuy']`.
- Amazon `amz_sign_in` reads `config.platforms['amazon'].credentials.email/.password` (signature unchanged; caller passes the AppConfig instance).
- Removed: stdout/stderr `open(os.devnull)` monkey patches, the duplicate Options import, `load_config()`, `import yaml`, the inline chromeOptions block (replaced by `build_driver`), and the trailing `setup_logger()` reference.
- config.py raises ImportError with migration text; any surviving `from config import config` fails loudly at import time.

## SEC-06 Disclaimer

README.md now contains a top-level Disclaimer section with the required substrings ("personal use", "TOS", "account") and a follow-on Credentials and Environment section documenting the four SHOPBOT_PLATFORMS__ env vars plus the runtime CVV prompt / SHOPBOT_ALLOW_CVV_ENV opt-in.

## Verification

- `python -c "import main"` exits 0.
- Full Phase 1 test set (`tests/test_requirements.py tests/test_python_version.py tests/test_plugin_base.py tests/test_config_schema.py tests/test_driver_setup.py tests/test_credentials.py tests/test_logger.py tests/test_main_smoke.py tests/test_docs.py`): 39 passed under the project Python 3.13 interpreter (which has selenium installed per requirements.txt).
- `tests/test_main_smoke.py`: 8 passed.
- `tests/test_docs.py`: 1 passed.

### Environment Note

`rtk pytest` on this Windows host invokes Python 3.14 (a system-side interpreter) which does not have selenium installed, so the four `test_driver_setup.py` cases that import `driver.py` fail with `ModuleNotFoundError: No module named 'selenium'`. This is a pre-existing test-runner-environment issue (selenium is pinned in requirements.txt for the project's 3.11+ venv per Plan 01-01), not a regression introduced by this plan. Running `python -m pytest ...` directly uses the venv interpreter and all 39 tests pass.

## Deviations from Plan

None substantive. Two minor adjustments worth noting:

1. `main()` was kept short by extracting two helpers (`_handle_amazon`, `_handle_bestbuy`) instead of inlining the entire polling loop body. This preserves the loop semantics exactly while honoring the CLAUDE.md 30-line function guidance. No behavior change.
2. Git tracked the README as lowercase `readme.md` on the filesystem (Windows case-insensitive). Renamed to canonical `README.md` via `git mv -f` so the path matches the plan / test substring exactly.

## STATE.md / ROADMAP.md

Untouched as instructed.

## Self-Check: PASSED

- main.py exists and contains all four required imports plus the version guard: FOUND
- amazon_bot.py has no `config['app']['amz_*']` substrings: FOUND
- config.py raises ImportError: FOUND
- README.md contains "personal use", "TOS", "account": FOUND
- tests/test_main_smoke.py exists with 8 tests: FOUND
- tests/test_docs.py exists with 1 test: FOUND
- Commit 3dfde83 (RED tests): FOUND
- Commit 9a38c1a (GREEN integration): FOUND
