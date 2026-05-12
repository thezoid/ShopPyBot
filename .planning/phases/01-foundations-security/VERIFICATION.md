---
phase: 01-foundations-security
verified: 2026-05-12
status: PASS
score: 14/14 requirements verified; 5/5 ROADMAP success criteria met; 4/4 anti-patterns resolved
verifier: gsd-verifier
test_run:
  command: "py -3.13 -m pytest tests/test_requirements.py tests/test_python_version.py tests/test_plugin_base.py tests/test_config_schema.py tests/test_driver_setup.py tests/test_credentials.py tests/test_logger.py tests/test_main_smoke.py tests/test_docs.py"
  result: "39 passed in 0.64s"
  python: "3.13.13"
  notes: "system rtk pytest invokes Python 3.14 without selenium installed; venv interpreter required per Phase 1 SUMMARY note. 39/39 confirmed under Python 3.13 which has all pinned deps."
follow_ups:
  - "tests/test_utils.py imports make_tiny from utils, but make_tiny relocated to main.py during Plan 01-06. Test fails at collection. Documented in deferred-items.md as pre-existing; recommend deletion or relocation in Phase 2 entry tasks."
  - "tests/test_models.py fails when data/ directory absent (sqlite3 cannot open db). Pre-existing, unrelated to Phase 1."
  - "_deprecated/ folder remains git-tracked and contains settings.json with placeholder credential strings ('your bestbuy account password' etc). Not a leak but worth scrubbing before public release."
  - "README.md Prerequisites still states 'Python 3.8+' on line 57 — contradicts the requires-python>=3.11 declaration. Cosmetic only; main.py enforces the real floor."
---

# Phase 1: Foundations + Security — Verification Report

**Phase Goal:** Plugin interface contract locked and versioned, config validated at startup, all credential/driver security issues resolved — codebase safe to publish as open source.

**Verdict:** PASS — All 14 in-scope requirements satisfied with code-level evidence and 39/39 Phase 1 tests green. All 5 ROADMAP success criteria met. All 4 critical anti-patterns from `.continue-here.md` are resolved.

## ROADMAP Success Criteria

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | RetailerPlugin ABC: only `check_availability` + `auto_buy` abstract; `login`/`detect_captcha` no-op defaults; `PLUGIN_API_VERSION = 1` importable | PASS | `plugin_base.py:12` `PLUGIN_API_VERSION: int = 1`; lines 28-44 confirm two abstract + two default methods; D-01 followed (no `driver` arg). `tests/test_plugin_base.py` 5 passing. |
| 2 | Missing field produces actionable error + clean exit (no traceback) | PASS | `main.py:93-97` wraps `AppConfig()` in try/except, writes message to stderr, `sys.exit(1)`. `tests/test_config_schema.py::test_missing_field_message` passes. |
| 3 | No credentials/CVV/passwords in `config.yml` or logs; CVV via getpass; env-var-only creds | PASS | `sample.config.yml:14-32` has empty placeholders + env-var documentation; `config_schema.py:18` notes "cvv intentionally absent"; `credentials.py:29` `getpass.getpass`. |
| 4 | ChromeDriver: no `--disable-web-security`, real UA, `navigator.webdriver` hidden via CDP | PASS | `driver.py:14-17` real Chrome 131 UA; `driver.py:52-55` `execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", ...)`; grep confirms `--disable-web-security` absent from all `.py` source files (only present in tests/docs as negative assertions). |
| 5 | `requirements.txt` exact-pinned, no dupes, `python_requires >= 3.11`; CD output via Service log_path, no stdout monkey-patch | PASS | `requirements.txt` 8 lines all `==X.Y.Z` (verified by `tests/test_requirements.py`); `pyproject.toml:4` `requires-python = ">=3.11"`; `driver.py:49` `Service(executable_path=..., log_path=...)`; no `sys.stdout =` in any source `.py`. |

## Per-Requirement Verdict

| Req | Verdict | Evidence |
|-----|---------|----------|
| **CORE-01** | PASS | `plugin_base.py:15-44` defines `RetailerPlugin(ABC)` with `check_availability(self, url) -> bool`, `auto_buy(self, url, config) -> bool` abstract; `login(self, config) -> None` and `detect_captcha(self) -> bool` no-op default; `__init__` takes `platform_config` only, plugin owns `self.driver` per D-01. |
| **CORE-02** | PASS | `plugin_base.py:12` `PLUGIN_API_VERSION: int = 1` importable. `tests/test_plugin_base.py::test_api_version_is_one` passes. |
| **CORE-05** | PASS | `config_schema.py` Pydantic `AppConfig(BaseSettings)` validates on instantiation; `main.py:93-97` catches `Exception` and exits 1 with the formatted message. `extra="forbid"` (line 49) yields actionable errors on unknown keys. |
| **CORE-06** | PASS | `config_schema.py:16-25` defines `PlatformCredentials` + `PlatformConfig`; `AppConfig.platforms: dict[str, PlatformConfig]` (line 58) supports per-platform sections (amazon, bestbuy). `tests/test_config_schema.py::test_per_platform_credentials` passes. |
| **CORE-07** | PASS | `config_schema.py:73-100` `reject_deprecated_keys` model_validator hard-fails on `app.amz_email`, `app.amz_pwd`, `app.bb_email`, `app.bb_password`, `app.bb_cvv` with structured migration block pointing to env var or new schema key. `tests/test_config_schema.py::test_deprecated_amz_email_hard_fails` + `test_deprecated_bb_cvv_hard_fails` pass. |
| **SEC-01** | PASS | `config_schema.py:16-19` schema requires `email` + `password` strings but `sample.config.yml:14-32` ships empty placeholders and inline comments instructing use of `SHOPBOT_PLATFORMS__<NAME>__CREDENTIALS__EMAIL/PASSWORD`. `settings_customise_sources` (line 62-71) orders env > YAML so env wins. CVV intentionally absent from schema. |
| **SEC-02** | PASS | `credentials.py:29` `getpass.getpass(f"Enter CVV for {name}: ")`. Non-TTY path: `:24-25` calls `_exitNonTty()` unless `SHOPBOT_ALLOW_CVV_ENV=true` opt-in (line 36-38). Empty-CVV abort on line 30-32. 6 passing tests in `tests/test_credentials.py`. |
| **SEC-03** | PASS | `driver.py` does NOT add `--disable-web-security`. Grep across `*.py`: only present in test assertions (`tests/test_driver_setup.py:18`) and documentation. `tests/test_driver_setup.py::test_no_disable_web_security` passes. |
| **SEC-04** | PASS | `driver.py:52-55` `driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": WEBDRIVER_HIDE_JS})` where the source redefines `Navigator.prototype.webdriver` to `undefined`. Runs before any page script. `tests/test_driver_setup.py::test_cdp_webdriver_hide_called` passes. |
| **SEC-05** | PASS | `driver.py:14-17` `CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/131.0.0.0 Safari/537.36"` — no "Selenium" or "HeadlessChrome" substring. `tests/test_driver_setup.py::test_real_user_agent_set` asserts this. |
| **SEC-06** | PASS | `README.md:16-28` "Disclaimer" section contains "personal use", "TOS", "account". `README.md:30-43` "Credentials and Environment" section documents the four env vars and the runtime CVV prompt + `SHOPBOT_ALLOW_CVV_ENV` opt-in for trusted infra. `tests/test_docs.py` passes. |
| **INFRA-01** | PASS | `requirements.txt`: all 8 lines match `==X.Y.Z` regex; no duplicates (verified by `tests/test_requirements.py`). `pyproject.toml:4` `requires-python = ">=3.11"`. `tests/test_python_version.py` passes. |
| **INFRA-02** | PASS | `logger.py` has zero `yaml.safe_load` or `open("config.yml")` calls. Verbosity is module-level `_logging_level` set once via `configure(level)` (lines 24-30) called from `main.py:99`. `tests/test_logger.py::test_no_yaml_import_in_source` + `test_writelog_does_not_open_config_yml` pass. |
| **INFRA-03** | PASS | `driver.py:48-49` `Service(executable_path=driver_path, log_path=log_path)` routes ChromeDriver output to file. No `sys.stdout = open(...)` or `sys.stderr = open(...)` anywhere in source `.py`. `tests/test_driver_setup.py::test_service_uses_log_path` + `test_no_stdout_monkey_patch_in_source` pass. |

## Anti-Pattern Resolution (from `.planning/.continue-here.md`)

| # | Anti-Pattern | Verdict | Evidence |
|---|--------------|---------|----------|
| 1 | Shared global WebDriver | RESOLVED | `driver.py:26` is a `build_driver()` factory; no `driver = webdriver.Chrome(...)` at module scope in any active source file. `main.py:105` constructs once and owns lifecycle locally. (Global driver lines in `_deprecated/bot.py:206`, `_deprecated/bot-availCheck.py:161` are archived legacy.) |
| 2 | Logger re-reads `config.yml` per call | RESOLVED | `logger.py` has no yaml import and no `config.yml` open. Threshold cached in `_logging_level` module global. |
| 3 | Credentials in `config.yml` | RESOLVED | Schema has no plaintext credential fields besides `email`/`password` containers that are normally populated from env vars (env > YAML priority). `sample.config.yml` ships empties + comments. Old `app.*_email/_pwd/_cvv` keys hard-fail. |
| 4 | `--disable-web-security` Chrome flag | RESOLVED | Absent from `driver.py` and all source files. |

## Integration Verification

- `py -3.13 -c "import main"` → exit 0 (main module compiles and imports cleanly).
- `main.py` wires all four new modules: `AppConfig`, `build_driver`, `collect_cvvs`, `configure_logger` (verified by `tests/test_main_smoke.py` 8 passing assertions).
- `amazon_bot.py:58-59` reads credentials via `config.platforms['amazon'].credentials.email/.password` (new schema, no `app.amz_*`).
- `bestbuy_bot.py:40` accepts email/password/cvv as args from main.py; no shared config reads.
- `config.py` is an `ImportError` tripwire (line 9-12), so any stale `from config import config` fails loudly.

## Test Results

Phase 1 targeted test set (per Plan 01-06 SUMMARY): **39 passed / 0 failed** under Python 3.13.13.

```
tests/test_requirements.py     2 passed
tests/test_python_version.py   1 passed
tests/test_plugin_base.py      5 passed
tests/test_config_schema.py    7 passed
tests/test_driver_setup.py     5 passed
tests/test_credentials.py      6 passed
tests/test_logger.py           4 passed
tests/test_main_smoke.py       8 passed
tests/test_docs.py             1 passed
                              ---
TOTAL                          39 passed in 0.64s
```

Environment note: the system `rtk pytest` resolves to a Python 3.14 interpreter without selenium/pygame installed, which causes collection failures unrelated to Phase 1 code. Using `py -3.13` (the interpreter with pinned deps installed) gives the canonical green result. Plan 01-06 SUMMARY documented this same observation.

## Gaps / Follow-Ups (Non-Blocking)

These do not block Phase 1 sign-off but should be tracked:

1. **`tests/test_utils.py` is stale.** It imports `make_tiny` from `utils`, but Plan 01-06 moved `make_tiny` to `main.py`. The test now errors at collection. Documented in `deferred-items.md` as pre-existing. **Phase 2 entry task:** delete the test or relocate the import.
2. **`tests/test_models.py` collection error.** Pre-existing; requires `data/` directory. Unrelated to Phase 1. Track for Phase 4 (SQLite hardening) or fix opportunistically.
3. **`_deprecated/` folder still git-tracked.** Contains `settings.json` with placeholder credential strings (no real secrets, but the literal strings `bb_email`, `bb_cvv` etc. live there). Before the open-source publish, recommend `git rm -r _deprecated/` or move outside the repo. Not a security blocker — values are placeholder text — but reduces signal noise for new contributors.
4. **README.md `Prerequisites` still says "Python 3.8+".** Line 57 contradicts `pyproject.toml requires-python>=3.11` and `main.py` runtime guard. Cosmetic; runtime enforcement is correct. Fix in Phase 3 docs pass.
5. **`amazon_bot.py:1`, `bestbuy_bot.py:1` import `from selenium import webdriver` but never reference the alias.** Pre-existing; not a Phase 1 regression. Will be cleaned up in Phase 2 plugin migration.

## Recommended Next Action

Phase 1 is complete. Update `.planning/ROADMAP.md` Progress table to mark Phase 1 as Complete and proceed to Phase 2 (Plugin Migration) planning. Carry the four follow-up items above into the Phase 2 plan kickoff so they get scheduled rather than forgotten.

---

*Verified: 2026-05-12 — gsd-verifier under Python 3.13.13*
