---
phase: 1
slug: foundations-security
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-02
updated: 2026-05-02
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 |
| Config file | `pyproject.toml` ([tool.pytest.ini_options]) — installed in Plan 01 (Wave 0) |
| Quick run command | `pytest -x -q` |
| Full suite command | `pytest -v` |
| Estimated runtime | ~10 seconds |

## Sampling Rate

- After every task commit: `pytest -x -q`
- After every plan wave: `pytest -v`
- Before `/gsd-verify-work`: full suite must be green
- Max feedback latency: 10 seconds

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | INFRA-01 | T-1-INFRA-01 | requirements.txt has exact pins, no duplicates | smoke | `pytest -x -q tests/test_requirements.py` | created in Plan 01 | pending |
| 1-01-02 | 01 | 0 | INFRA-01 | T-1-PYVER-01 | pyproject.toml declares requires-python >= 3.11 | smoke | `pytest -x -q tests/test_python_version.py` | created in Plan 01 | pending |
| 1-02-01 | 02 | 1 | CORE-01, CORE-02 | T-1-CORE-01 | RED: ABC tests fail because plugin_base.py absent | unit | `pytest -x tests/test_plugin_base.py` (must FAIL) | created in Plan 02 | pending |
| 1-02-02 | 02 | 1 | CORE-01, CORE-02 | T-1-CORE-01, T-1-CORE-02 | GREEN: ABC contract enforced; PLUGIN_API_VERSION=1; defaults work | unit | `pytest -x -q tests/test_plugin_base.py` | created in Plan 02 | pending |
| 1-03-01 | 03 | 1 | CORE-05, CORE-06, CORE-07, SEC-01 | T-1-SEC-01, T-1-CORE-05/06/07 | RED: schema tests fail because config_schema.py absent | unit | `pytest -x tests/test_config_schema.py` (must FAIL) | created in Plan 03 | pending |
| 1-03-02 | 03 | 1 | CORE-05, CORE-06, CORE-07, SEC-01 | T-1-SEC-01, T-1-CORE-05/06/07, T-1-EXTRA-FORBID | GREEN: AppConfig validates, deprecated keys hard-fail, env wins over yaml | unit | `pytest -x -q tests/test_config_schema.py` | created in Plan 03 | pending |
| 1-04-01 | 04 | 1 | SEC-03, SEC-04, SEC-05, INFRA-03 | T-1-SEC-03/04/05, T-1-INFRA-03 | RED: driver tests fail because driver.py absent | unit | `pytest -x tests/test_driver_setup.py` (must FAIL) | created in Plan 04 | pending |
| 1-04-02 | 04 | 1 | SEC-03, SEC-04, SEC-05, INFRA-03 | T-1-SEC-03/04/05, T-1-INFRA-03, T-1-CDP-ORDER | GREEN: build_driver omits --disable-web-security, sets real UA, calls CDP, uses Service log_path | unit | `pytest -x -q tests/test_driver_setup.py` | created in Plan 04 | pending |
| 1-05-01 | 05 | 2 | SEC-02 | T-1-SEC-02, T-1-NONTTY-FAIL, T-1-EMPTY-CVV | collect_cvvs prompts via getpass once per platform; non-TTY policy enforced | unit | `pytest -x -q tests/test_credentials.py` | created in Plan 05 | pending |
| 1-05-02 | 05 | 2 | INFRA-02 | T-1-INFRA-02 | writeLog never opens config.yml; configure() sets threshold | unit | `pytest -x -q tests/test_logger.py` | created in Plan 05 | pending |
| 1-06-01 | 06 | 3 | SEC-06, INFRA-03 | T-1-SEC-06, T-1-INFRA-03b, T-1-PYVER-01b, T-1-INTEGRATION | RED: smoke + docs tests fail before main.py rewrite | smoke | `pytest -x tests/test_main_smoke.py tests/test_docs.py` (must FAIL) | created in Plan 06 | pending |
| 1-06-02 | 06 | 3 | SEC-06, INFRA-03, all integration | T-1-SEC-06, T-1-INFRA-03b, T-1-PYVER-01b, T-1-INTEGRATION, T-1-CONFIG-IMPORT | GREEN: main.py wired (AppConfig+driver+credentials+logger); README disclosed; full suite passes | integration | `pytest -x -q && python -c "import main"` | created in Plan 06 | pending |

*Status: pending / green / red / flaky*

## Wave 0 Requirements (Plan 01)

- [ ] `tests/conftest.py` — shared fixtures (`clean_env`, `tmp_config_yml`)
- [ ] `tests/test_requirements.py` — INFRA-01 enforcement (every line pinned, no duplicates)
- [ ] `tests/test_python_version.py` — INFRA-01 enforcement (requires-python >= 3.11)
- [ ] `pyproject.toml` — pytest config (`testpaths = ["tests"]`) + requires-python
- [ ] `requirements.txt` — pin pytest==8.3.4 along with all other deps

Note: Plan 01 creates only the framework + INFRA-01 smoke tests. The per-feature test stubs (test_config_schema, test_plugin_base, test_driver_setup, test_credentials, test_logger, test_main_smoke, test_docs) are written by the plan that implements the feature, in RED-first style. This is the agreed deviation from the original VALIDATION.md draft, which assumed a single Wave 0 stub for every feature; under the per-plan TDD model, each plan owns its own RED test.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Chrome stealth not flagged by bot.sannysoft.com | SEC-04, SEC-05 | DOM-level navigator.webdriver evasion requires a real browser instance | After Plan 04 ships: `python -c "from driver import build_driver; d = build_driver('./chromedriver.exe'); d.get('https://bot.sannysoft.com'); input('press enter to close')"` — visually confirm "WebDriver" row is green and User-Agent row does not say HeadlessChrome |
| Non-TTY hard-fail in a real terminal pipe | SEC-02, D-05 | `pytest` capture buffers stdin in a way that simulates but is not identical to a true non-TTY pipe | After Plan 05 + Plan 06 ship: `echo "" \| python main.py` — confirm exit code 1 and stderr message contains "TTY" and "SHOPBOT_ALLOW_CVV_ENV" |
| Pydantic ValidationError formatting on malformed config | CORE-05 | Pydantic message string is generated at runtime; spot-check that field paths are human-readable | `python -c "import pathlib; pathlib.Path('config.yml').write_text('selenium: {}\n'); from config_schema import AppConfig; AppConfig()"` — confirm error names `selenium.driver_path` |

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or are explicit RED-state precursors
- [x] Sampling continuity: every plan ends with `pytest -x -q` (Plan 03/05/06 also run full suite)
- [x] Wave 0 (Plan 01) covers framework + INFRA-01 only; per-feature RED tests live in their owning plans
- [x] No watch-mode flags
- [x] Feedback latency < 10s (estimated suite ~10s)
- [x] `nyquist_compliant: true`

Approval: planner-signed
