---
phase: 07-modular-core-service
status: passed
verified: 2026-06-03
score: 4/4 success criteria, 3/3 requirements
method: unit suite (227 passed) + live editable-install + entry-point + import checks
---

# Phase 7 Verification — Modular Core Service

**Status: PASSED** — 4/4 success criteria, 3/3 requirements (MOD-01/02/03), 227 tests green, no behavior regression.

## Success Criteria (ROADMAP)

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | `from core.service import BotService` + all front-end operations | PASS | BotService imports; `hasattr` check confirms all 8 methods present: start, stop, run, list_items, add_item, remove_item, get_status, get_config. 13 new tests in tests/test_service.py exercise them. |
| 2 | No bot logic in front-ends (grep cli/web returns zero) | PASS (boundary) | No `cli/` or `web/` dir exists yet (Phase 9/10). Phase 7 proves the boundary: `main.py` routes the run through `BotService(cfg).run(cvv)` — it no longer imports `async_main`/`asyncio.run`. The cli/web grep becomes fully testable once those dirs land. |
| 3 | `pip install -e .` works; `shoppybot --help`; `python main.py` still works | PASS (live) | `pip install -e .` exits 0; `shoppybot --help` exits 0 (argparse guard, no bot start) via both the installed console script and the module; `main.py:50` delegates to `BotService(cfg).run(cvv)` with pre-flight (AppConfig validation, DB seed, getpass CVV) preserved. |
| 4 | Existing test suite passes WITHOUT modification (no regression) | PASS | `git diff 7ed220c..HEAD -- tests/` shows the ONLY existing test file changed is the pre-authorized `tests/test_main_wiring.py` (its 5 tests that patched `main.async_main`/`main.asyncio.run` repointed to the new `BotService` seam, CVV-gate + ValidationError intent preserved). All other 200+ existing tests unmodified. Full suite 227 passed. |

## Requirement Coverage

- MOD-01 (BotService API wrapping registry+orchestrator+config): core/service.py BotService, 8 methods. COVERED.
- MOD-02 (no bot logic in front-ends): main.py is a thin shim routing through BotService; getpass stays in the shim (front-end), core/service.py has no getpass/input (test_no_input.py enforces). COVERED.
- MOD-03 (installable package + entry point + main shim): pyproject.toml project metadata + packages (core/plugins/notifications) + `shoppybot = core.service:main`; `pip install -e .` works; `python main.py` still works. COVERED.

## Locked-Decision Checks

- start() runs the orchestrator in a background daemon thread with its own event loop and returns; stop() cancels via `loop.call_soon_threadsafe` so teardown_all runs (no orphaned Chrome). CONFIRMED.
- Core service never calls getpass/input; CVV is a method parameter only, never stored/logged. CONFIRMED (test + test_no_input scan of core/).
- No src/ restructure; core/plugins/notifications stayed in place; pyproject preserved the existing [tool.pytest.ini_options]. CONFIRMED.
- main.py preserves AppConfig validation + DB seed + getpass CVV gate, then delegates. CONFIRMED.
- Phase 7 added no cli/ dir and no new dependencies. CONFIRMED.

## Incidental Fixes (logged, in-scope)

- `plugins/__init__.py` (empty) added so setuptools treats plugins/ as a package after install (registry file-based discovery of shopbot_plugin_*.py is unaffected; 7-plugin discovery test still green).
- `core.service:main()` uses argparse `parse_known_args()` so `shoppybot --help` exits 0 without starting the bot, and pytest's argv does not trigger SystemExit in tests.

## Regression

`.venv/Scripts/python.exe -m pytest tests/ -q` -> 227 passed (1 warning).
