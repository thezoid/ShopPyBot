---
phase: 01-foundations-security
plan: 05
subsystem: infra-and-security
tags:
  - getpass
  - cvv
  - logger
  - infra
  - security
dependency_graph:
  requires:
    - 01-01 (pinned colorama + pytest infra, conftest clean_env fixture)
    - 01-03 (AppConfig.platforms + available.items shape consumed by collect_cvvs)
  provides:
    - credentials.collect_cvvs(app_config) -> dict[str, str]
    - logger.configure(level) + logger.writeLog (no per-call yaml load)
  affects:
    - main.py (Plan 06 will call configure() once and collect_cvvs() once)
    - amazon_bot.py / bestbuy_bot.py (continue to use writeLog unchanged)
tech_stack:
  added: []
  patterns:
    - getpass.getpass for non-echoing CVV prompt (stdlib)
    - sys.stdin.isatty + opt-in env-var fallback (D-04 / D-05)
    - module-level state set once via configure() (replaces per-call config reload)
    - functools.cache for log directory resolution
key_files:
  created:
    - credentials.py
    - tests/test_credentials.py
    - tests/test_logger.py
  modified:
    - logger.py
decisions:
  - "collect_cvvs hard-fails (SystemExit 1) on non-TTY by default; SHOPBOT_ALLOW_CVV_ENV=true opt-in is required for headless flow per D-05. Default-deny posture eliminates the 'IDE Run button silently hangs' failure mode (T-1-NONTTY-FAIL)."
  - "credentials.py imports zero logging functions and never calls writeLog; the CVV exists only in the cvvs dict in process memory (SEC-02 / T-1-SEC-02)."
  - "logger.py preserves the public writeLog(message, type, writeTofile=True) signature, all seven LOG_LEVELS strings, and the timestamp+color print format verbatim because downstream callers (amazon_bot, bestbuy_bot, main) depend on them. Only the internal yaml.safe_load call was removed."
  - "configure() defaults to threshold 5 (TRACE) if never called, so test imports and any pre-Plan-06 callers continue to print everything they did before."
metrics:
  duration_minutes: 5
  tasks_completed: 2
  files_touched: 4
  completed: 2026-05-12
requirements_addressed:
  - SEC-02
  - INFRA-02
---

# Phase 1 Plan 05: Credentials and Logger Summary

Two cross-cutting infra modules landed: `credentials.collect_cvvs` (SEC-02 runtime CVV prompt with TTY check and opt-in env fallback) and a `logger.py` refactor that drops the per-call `yaml.safe_load` (INFRA-02). Plan 06 will wire both into `main.py`.

## What Was Built

- `credentials.py` (63 lines) exports `collect_cvvs(app_config) -> dict[str, str]`. It builds the `needed` list from `app_config.platforms.items()` filtered by `plat.enabled and any(item.auto_buy for item in app_config.available.items)`, returns `{}` if nothing is needed, then branches on `sys.stdin.isatty()`:
  - TTY: loops `getpass.getpass(f"Enter CVV for {name}: ")` once per needed platform; empty response triggers `SystemExit(1)` with a clear stderr message.
  - Non-TTY without `SHOPBOT_ALLOW_CVV_ENV=true`: writes the IDE-Run-button warning to stderr and `sys.exit(1)`.
  - Non-TTY with opt-in: reads `SHOPBOT_<PLATFORM>_CVV` env vars; missing env var triggers `SystemExit(1)` naming the exact env var.
- `logger.py` rewritten (46 added, 29 removed). Drops `import yaml`, `load_settings()`, `setup_logger()`. Adds module-level `_logging_level: int | None = None` and `configure(level: int)` that sets the global once at startup. `writeLog` reads the global directly (defaults to 5 if `configure` was never called) and emits the same `[TYPE][YYYYMonthDD@HH:MM:SS] message` color line plus optional file append. `functools.cache` memoizes the log directory creation.
- `tests/test_credentials.py` (79 lines) covers six paths: empty needed, TTY prompt once per platform, non-TTY hard-fail without opt-in, non-TTY env-var read with opt-in, non-TTY missing env var with opt-in, and empty-CVV exit. All use `SimpleNamespace` fakes for `AppConfig` so the test does not transitively pull in pydantic-settings YAML loading.
- `tests/test_logger.py` (52 lines) covers four contracts: no `import yaml` in source, no `config.yml` open during writeLog (via `monkeypatch` on `builtins.open`), `configure(2)` suppresses DEBUG but emits ERROR, and the `[INFO]` format string is preserved.

## Tasks Executed

| Task | Name                                                | Commits          | Status |
| ---- | --------------------------------------------------- | ---------------- | ------ |
| 1    | credentials.py + tests (RED -> GREEN)               | 8ca67bb, 060a667 | done   |
| 2    | logger.py refactor + tests (RED -> GREEN)           | a7aea6f, b9f011e | done   |

## Verification

- `rtk pytest -x -q tests/test_credentials.py` -> 6 passed
- `rtk pytest -x -q tests/test_logger.py` -> 4 passed
- `rtk pytest -q tests/test_credentials.py tests/test_logger.py tests/test_config_schema.py tests/test_plugin_base.py tests/test_python_version.py tests/test_requirements.py` -> 25 passed
- `grep "writeLog|logger" credentials.py` -> no matches (CVV never goes through logging; T-1-SEC-02 mitigation enforced)
- `grep "import yaml" logger.py` -> no matches (INFRA-02 satisfied)
- `grep "load_settings" logger.py` -> no matches
- `credentials.py` contains `getpass.getpass`, `sys.stdin.isatty`, `SHOPBOT_ALLOW_CVV_ENV`, `sys.exit(1)` as required by acceptance criteria.
- `logger.py` LOG_LEVELS dict contains all seven keys: ALWAYS, ERROR, WARNING, SUCCESS, INFO, DEBUG, TRACE.

## Deviations from Plan

None functional. Two cosmetic adjustments per project CLAUDE.md style:

1. **camelCase internal helpers in credentials.py.** Public name `collect_cvvs` is preserved verbatim (the plan's <interfaces> block exports it under that name and Plan 06 imports it). Internal helpers extracted as `_envOptInEnabled`, `_collectFromEnv`, `_exitNonTty` to keep `collect_cvvs` itself under 30 lines per project CLAUDE.md function-length rule. The RESEARCH Pattern 3 logic is preserved branch-for-branch and message-for-message.
2. **camelCase internal helpers in logger.py.** Public names `configure`, `writeLog`, `LOG_LEVELS` preserved verbatim. The plan's suggested `_log_dir` and `_write_to_file` private helpers were renamed `_logDir` and `_writeToFile` for camelCase consistency. No call site outside `logger.py` references them.

Both adjustments are name-only and do not change behavior, signature, or test surface.

## TDD Gate Compliance

- RED gates: `test(01-05): add failing tests for credentials.collect_cvvs (RED)` at 8ca67bb (ModuleNotFoundError) and `test(01-05): add failing logger refactor tests (RED)` at a7aea6f (`import yaml` still in source).
- GREEN gates: `feat(01-05): implement collect_cvvs with TTY + env-opt-in fallback` at 060a667 (6 passed) and `refactor(01-05): drop per-call yaml load; configure() sets level once` at b9f011e (4 passed).
- REFACTOR: not needed; both implementations followed RESEARCH.md Patterns 3 and 5 directly.

## Threat Flags

None. Threat register from the plan is mitigated as designed:

- T-1-SEC-02 (CVV disclosure): `grep writeLog credentials.py` returns nothing; CVV held in local `cvvs` dict only.
- T-1-SEC-02b (env-var visibility on shared host): accepted by D-05, opt-in only, warning text references `/proc/<pid>/environ`.
- T-1-INFRA-02 (per-call yaml DoS): `test_writelog_does_not_open_config_yml` enforces zero `config.yml` opens per call.
- T-1-NONTTY-FAIL (silent hang under IDE/cron): `test_non_tty_without_optin_hard_fails` enforces SystemExit(1) with stderr message instead of indefinite getpass block.
- T-1-EMPTY-CVV (Enter key at prompt): `test_empty_getpass_response_exits` enforces SystemExit(1).

No new network endpoints, auth surfaces, or trust boundaries introduced beyond what the plan's threat model already enumerates.

## Known Stubs

None. `collect_cvvs` and the logger refactor are complete. Plan 06 will add the two import-and-call lines in `main.py` (`configure(app_config.debug.logging_level)` once at startup, `cvvs = collect_cvvs(app_config)` once before the polling loop).

## Out-of-Scope Pre-existing Issues (not introduced by this plan)

- `tests/test_utils.py` fails to collect because `pygame` is not installed in this env (pre-existing; documented in Plan 03 SUMMARY).
- `tests/test_driver_setup.py` 4 failures because `selenium` is not installed in this env (pre-existing; Plan 04 ships with the same constraint and its summary tracks it).
- `tests/test_models.py` 2 errors with sqlite path resolution (pre-existing; unrelated to credentials/logger work).

None were introduced or worsened by this plan. Tests touched by this plan (test_credentials.py, test_logger.py) and the Plan-01/02/03 baseline tests all pass (25/25).

## Follow-ups

- Plan 06 imports: `from credentials import collect_cvvs` and `from logger import configure as configure_logger, writeLog`. Call `configure_logger(app_config.debug.logging_level)` immediately after loading AppConfig, then `cvvs = collect_cvvs(app_config)` before the polling loop. Pass the per-platform CVV from `cvvs` into the auto-buy paths in `amazon_bot` / `bestbuy_bot`.
- README guidance for headless runs: document `SHOPBOT_ALLOW_CVV_ENV=true` plus `SHOPBOT_AMAZON_CVV` / `SHOPBOT_BESTBUY_CVV` env vars, with the `/proc/<pid>/environ` warning.

## Self-Check: PASSED

- FOUND: credentials.py
- FOUND: logger.py (modified)
- FOUND: tests/test_credentials.py
- FOUND: tests/test_logger.py
- FOUND commit: 8ca67bb (Task 1 RED)
- FOUND commit: 060a667 (Task 1 GREEN)
- FOUND commit: a7aea6f (Task 2 RED)
- FOUND commit: b9f011e (Task 2 GREEN)
