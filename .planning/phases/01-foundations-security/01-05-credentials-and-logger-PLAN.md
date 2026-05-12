---
phase: 01-foundations-security
plan: 05
type: execute
wave: 2
depends_on: ["01", "03"]
files_modified:
  - credentials.py
  - logger.py
  - tests/test_credentials.py
  - tests/test_logger.py
autonomous: true
requirements:
  - SEC-02
  - INFRA-02
tags:
  - getpass
  - cvv
  - logger
  - infra

must_haves:
  truths:
    - "collect_cvvs(app_config) prompts via getpass.getpass once per enabled platform with at least one auto_buy item"
    - "collect_cvvs returns a dict mapping platform name to CVV string held only in memory"
    - "When stdin is not a TTY and SHOPBOT_ALLOW_CVV_ENV is not 'true', collect_cvvs writes a clear error to stderr and exits 1"
    - "When stdin is not a TTY and SHOPBOT_ALLOW_CVV_ENV='true', collect_cvvs reads SHOPBOT_<PLATFORM>_CVV env vars instead of prompting"
    - "writeLog() does NOT call open('config.yml') on every invocation"
    - "logger.configure(level) sets a module-level int that subsequent writeLog calls respect"
    - "writeLog signature, type strings (ALWAYS/ERROR/WARNING/SUCCESS/INFO/DEBUG/TRACE), and timestamped color print format are preserved verbatim"
  artifacts:
    - path: "credentials.py"
      provides: "collect_cvvs(app_config) -> dict[str, str]"
      contains: "def collect_cvvs"
      min_lines: 40
    - path: "logger.py"
      provides: "configure(level) + writeLog(message, type, writeTofile=True) without per-call yaml load"
      contains: "def configure"
      min_lines: 30
    - path: "tests/test_credentials.py"
      provides: "Tests for TTY, env opt-in, hard-fail paths"
      min_lines: 50
    - path: "tests/test_logger.py"
      provides: "Test that writeLog never opens config.yml"
      min_lines: 20
  key_links:
    - from: "credentials.collect_cvvs"
      to: "getpass.getpass"
      via: "loop over enabled+auto_buy platforms"
      pattern: "getpass\\.getpass"
    - from: "logger.writeLog"
      to: "_logging_level module global"
      via: "configure(level)"
      pattern: "_logging_level"
---

<objective>
Land two cross-cutting infrastructure modules that Plan 06 will wire into main.py: `credentials.py` (SEC-02 — runtime CVV prompt with non-TTY policy from D-04/D-05) and the `logger.py` refactor (INFRA-02 — drop the per-call `yaml.safe_load`).

Purpose: Both are independent of each other and of the driver work, so they parallelize within Wave 2 and ship as one focused plan. Plan 06 then has only wiring left.

Output: `credentials.py` (new), `logger.py` (refactored), `tests/test_credentials.py` (new), `tests/test_logger.py` (new). Does NOT touch main.py or the bot modules — that integration is Plan 06.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundations-security/01-CONTEXT.md
@.planning/phases/01-foundations-security/01-PATTERNS.md
@.planning/phases/01-foundations-security/01-RESEARCH.md
@logger.py
@config_schema.py
</context>

<interfaces>
<!-- credentials.py — RESEARCH.md Pattern 3, lines 427-474, used VERBATIM. -->
```python
import getpass
import os
import sys


def collect_cvvs(app_config) -> dict[str, str]:
    needed = [
        name for name, plat in app_config.platforms.items()
        if plat.enabled and any(item.auto_buy for item in app_config.available.items)
    ]
    if not needed:
        return {}

    if not sys.stdin.isatty():
        if os.environ.get("SHOPBOT_ALLOW_CVV_ENV", "").lower() == "true":
            cvvs = {}
            for name in needed:
                env_key = f"SHOPBOT_{name.upper()}_CVV"
                val = os.environ.get(env_key)
                if not val:
                    sys.stderr.write(
                        f"ERROR: {env_key} is required because SHOPBOT_ALLOW_CVV_ENV=true and "
                        f"stdin is not a TTY. Set the env var or remove auto_buy from "
                        f"{name} items.\n"
                    )
                    sys.exit(1)
                cvvs[name] = val
            return cvvs
        sys.stderr.write(
            "ERROR: auto_buy is enabled but stdin is not a TTY (this happens when running "
            "from an IDE Run button or under cron/systemd). Either run interactively, or set "
            "SHOPBOT_ALLOW_CVV_ENV=true and supply SHOPBOT_<PLATFORM>_CVV env vars (visible "
            "in /proc/<pid>/environ — trusted infrastructure only).\n"
        )
        sys.exit(1)

    cvvs = {}
    for name in needed:
        cvvs[name] = getpass.getpass(f"Enter CVV for {name}: ")
        if not cvvs[name]:
            sys.stderr.write(f"ERROR: empty CVV for {name}; aborting.\n")
            sys.exit(1)
    return cvvs
```

<!-- logger.py — RESEARCH.md Pattern 5, lines 521-569, used VERBATIM. -->
Replaces current logger.py entirely. Drops `import yaml`, `load_settings()`, `setup_logger()`. Adds module-level `_logging_level` and `configure(level)`. Preserves `writeLog` name, `LOG_LEVELS` dict, color/timestamp format, and file-write block.
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Credentials module — write tests + implement (RED → GREEN)</name>
  <files>credentials.py, tests/test_credentials.py</files>
  <read_first>
    - .planning/phases/01-foundations-security/01-CONTEXT.md (D-04, D-05)
    - .planning/phases/01-foundations-security/01-RESEARCH.md lines 427-476 (Pattern 3 + getpass cite)
    - .planning/phases/01-foundations-security/01-PATTERNS.md (sections "credentials.py" and "tests/test_credentials.py")
    - tests/conftest.py (Plan 01 — clean_env fixture)
    - config_schema.py (Plan 03 — for AppConfig shape used in tests)
  </read_first>
  <behavior>
    - test_no_platforms_returns_empty: app_config with no auto_buy items returns {}
    - test_cvv_prompt_once_per_platform: monkeypatched getpass.getpass returns fixed value; called exactly once per enabled+auto_buy platform
    - test_non_tty_without_optin_hard_fails: stdin.isatty=False, no SHOPBOT_ALLOW_CVV_ENV → SystemExit(1) with stderr containing "TTY" and "SHOPBOT_ALLOW_CVV_ENV"
    - test_non_tty_with_optin_reads_env: stdin.isatty=False, SHOPBOT_ALLOW_CVV_ENV=true, SHOPBOT_AMAZON_CVV=999 → returns {"amazon": "999"}
    - test_non_tty_with_optin_missing_env_exits: opt-in true but env var unset → SystemExit(1) with stderr containing the env var name
    - test_empty_getpass_response_exits: getpass returns "" → SystemExit(1)
  </behavior>
  <action>
    1. Create `tests/test_credentials.py`:
       ```python
       import sys
       import pytest
       from types import SimpleNamespace


       def _make_config(platforms_with_auto_buy):
           # platforms_with_auto_buy: list of platform names that should be enabled with auto_buy items
           items = [SimpleNamespace(auto_buy=True)] if platforms_with_auto_buy else []
           platforms = {
               name: SimpleNamespace(enabled=True)
               for name in platforms_with_auto_buy
           }
           return SimpleNamespace(
               platforms=platforms,
               available=SimpleNamespace(items=items),
           )


       def test_no_platforms_returns_empty(clean_env):
           from credentials import collect_cvvs
           cfg = _make_config([])
           assert collect_cvvs(cfg) == {}


       def test_cvv_prompt_once_per_platform(clean_env, monkeypatch):
           calls = []
           monkeypatch.setattr("sys.stdin.isatty", lambda: True)
           monkeypatch.setattr("getpass.getpass", lambda prompt="": (calls.append(prompt) or "111"))
           from credentials import collect_cvvs
           cfg = _make_config(["amazon", "bestbuy"])
           result = collect_cvvs(cfg)
           assert result == {"amazon": "111", "bestbuy": "111"}
           assert len(calls) == 2


       def test_non_tty_without_optin_hard_fails(clean_env, monkeypatch, capsys):
           monkeypatch.setattr("sys.stdin.isatty", lambda: False)
           from credentials import collect_cvvs
           cfg = _make_config(["amazon"])
           with pytest.raises(SystemExit) as exc:
               collect_cvvs(cfg)
           assert exc.value.code == 1
           err = capsys.readouterr().err
           assert "TTY" in err
           assert "SHOPBOT_ALLOW_CVV_ENV" in err


       def test_non_tty_with_optin_reads_env(clean_env, monkeypatch):
           monkeypatch.setattr("sys.stdin.isatty", lambda: False)
           monkeypatch.setenv("SHOPBOT_ALLOW_CVV_ENV", "true")
           monkeypatch.setenv("SHOPBOT_AMAZON_CVV", "999")
           from credentials import collect_cvvs
           cfg = _make_config(["amazon"])
           assert collect_cvvs(cfg) == {"amazon": "999"}


       def test_non_tty_with_optin_missing_env_exits(clean_env, monkeypatch, capsys):
           monkeypatch.setattr("sys.stdin.isatty", lambda: False)
           monkeypatch.setenv("SHOPBOT_ALLOW_CVV_ENV", "true")
           # SHOPBOT_AMAZON_CVV intentionally NOT set
           from credentials import collect_cvvs
           cfg = _make_config(["amazon"])
           with pytest.raises(SystemExit) as exc:
               collect_cvvs(cfg)
           assert exc.value.code == 1
           assert "SHOPBOT_AMAZON_CVV" in capsys.readouterr().err


       def test_empty_getpass_response_exits(clean_env, monkeypatch, capsys):
           monkeypatch.setattr("sys.stdin.isatty", lambda: True)
           monkeypatch.setattr("getpass.getpass", lambda prompt="": "")
           from credentials import collect_cvvs
           cfg = _make_config(["amazon"])
           with pytest.raises(SystemExit) as exc:
               collect_cvvs(cfg)
           assert exc.value.code == 1
           assert "empty CVV" in capsys.readouterr().err
       ```
    2. Run `pytest -x tests/test_credentials.py` — must fail with `ModuleNotFoundError: No module named 'credentials'` (RED).
    3. Create `credentials.py` at repo root using the contents in <interfaces> above. Use VERBATIM from RESEARCH Pattern 3 with one tweak: in the non-TTY-without-optin branch, expand the message to include the IDE-button warning from Pitfall 4 (RESEARCH lines 631-635).
    4. Run `pytest -x -q tests/test_credentials.py` — all 6 tests must pass (GREEN).
  </action>
  <verify>
    <automated>pytest -x -q tests/test_credentials.py</automated>
    <automated>python -c "import pathlib; src = pathlib.Path('credentials.py').read_text(); assert 'getpass.getpass' in src; assert 'isatty' in src; assert 'SHOPBOT_ALLOW_CVV_ENV' in src; assert 'sys.exit(1)' in src; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `credentials.py` exists, exports `collect_cvvs(app_config)`
    - All 6 tests in `tests/test_credentials.py` pass
    - `grep "getpass.getpass" credentials.py` matches
    - `grep "isatty" credentials.py` matches
    - `grep "SHOPBOT_ALLOW_CVV_ENV" credentials.py` matches (D-05)
    - `grep "writeLog\|logger" credentials.py` returns nothing (SEC-02 — CVV must never go through logging)
    - File under 80 lines
  </acceptance_criteria>
  <done>credentials.py implemented, all 6 tests green, no logging of CVV anywhere</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Refactor logger.py — remove per-call yaml load (RED → GREEN)</name>
  <files>logger.py, tests/test_logger.py</files>
  <read_first>
    - logger.py (current — full content; will be replaced)
    - .planning/phases/01-foundations-security/01-RESEARCH.md lines 521-571 (Pattern 5)
    - .planning/phases/01-foundations-security/01-PATTERNS.md (sections "logger.py" and "tests/test_logger.py")
    - tests/test_utils.py (analog for minimal logger-style test)
  </read_first>
  <behavior>
    - test_writelog_does_not_open_config_yml: monkeypatching `builtins.open` to record paths shows zero opens of `config.yml` during a writeLog call
    - test_configure_sets_threshold: after `configure(2)`, writeLog("x", "DEBUG") (level 4) does not print, but writeLog("x", "ERROR") (level 1) does
    - test_writelog_preserves_format: a printed line for type "INFO" contains the substring `[INFO]` and the message
    - test_no_yaml_import: `logger.py` source contains no `import yaml` line
  </behavior>
  <action>
    1. Create `tests/test_logger.py`:
       ```python
       import builtins
       import importlib
       import pathlib
       import pytest


       def test_no_yaml_import_in_source():
           src = pathlib.Path("logger.py").read_text()
           assert "import yaml" not in src, "INFRA-02: logger must not import yaml"
           assert "load_settings" not in src, "INFRA-02: per-call config load removed"


       def test_writelog_does_not_open_config_yml(monkeypatch, capsys):
           import logger
           importlib.reload(logger)
           opened = []
           real_open = builtins.open

           def spy_open(path, *a, **kw):
               opened.append(str(path))
               return real_open(path, *a, **kw)

           monkeypatch.setattr("builtins.open", spy_open)
           logger.configure(5)
           logger.writeLog("hello", "INFO", writeTofile=False)
           assert not any("config.yml" in p for p in opened), f"opened files: {opened}"


       def test_configure_sets_threshold(monkeypatch, capsys):
           import logger
           importlib.reload(logger)
           logger.configure(2)  # only ALWAYS, ERROR, WARNING, SUCCESS print
           logger.writeLog("debug-msg", "DEBUG", writeTofile=False)
           logger.writeLog("err-msg", "ERROR", writeTofile=False)
           out = capsys.readouterr().out
           assert "debug-msg" not in out
           assert "err-msg" in out


       def test_writelog_preserves_format(monkeypatch, capsys):
           import logger
           importlib.reload(logger)
           logger.configure(5)
           logger.writeLog("hello-world", "INFO", writeTofile=False)
           out = capsys.readouterr().out
           assert "[INFO]" in out
           assert "hello-world" in out
       ```
    2. Run `pytest -x tests/test_logger.py` — must fail (RED — current logger.py imports yaml).
    3. Replace `logger.py` entirely with RESEARCH.md Pattern 5 (lines 521-569). Verbatim. Specifically:
       - Drop `import yaml`, `load_settings()`, `setup_logger()`
       - Keep imports: `os`, `functools`, `from datetime import datetime`, `from colorama import Fore, Style`
       - Define `LOG_LEVELS` dict (same 7 levels in same order)
       - Module-level `_logging_level: int | None = None`
       - `configure(level: int) -> None` sets the global
       - `writeLog(message: str, type: str, writeTofile: bool = True) -> None` reads `_logging_level` (defaults to 5 if `configure` was not called)
       - `_log_dir()` cached with `@functools.cache` for the logs directory creation
       - `_write_to_file(type, ts, message)` for the file append
    4. Run `pytest -x -q tests/test_logger.py` — all 4 tests pass.
    5. Run `pytest -x -q` (full suite) — Plans 01 + 02 + 03 + 04 + 05 tests must all pass.
  </action>
  <verify>
    <automated>pytest -x -q tests/test_logger.py</automated>
    <automated>python -c "import pathlib; src = pathlib.Path('logger.py').read_text(); assert 'import yaml' not in src; assert 'load_settings' not in src; assert 'def configure' in src; assert 'def writeLog' in src; print('OK')"</automated>
    <automated>pytest -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `logger.py` exists, exports `configure(level)` and `writeLog(message, type, writeTofile=True)`
    - All 4 tests in `tests/test_logger.py` pass
    - `grep "import yaml" logger.py` returns nothing (INFRA-02)
    - `grep "load_settings" logger.py` returns nothing (INFRA-02)
    - LOG_LEVELS dict still contains all 7 type strings: ALWAYS, ERROR, WARNING, SUCCESS, INFO, DEBUG, TRACE
    - Full test suite (`pytest -x -q`) passes
  </acceptance_criteria>
  <done>logger.py refactored, no yaml import, configure() works, all tests green</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| user (terminal) -> credentials.py | CVV typed at TTY; must not be echoed, logged, or persisted |
| environment -> credentials.py | Opt-in env-var path for headless deployments; visible in /proc/<pid>/environ |
| logger.py -> filesystem | Append-only log file per day; must not embed credentials |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-1-SEC-02 | Information Disclosure | CVV in process | mitigate | `getpass.getpass` (no echo); CVV held in dict in process memory only; no logger import in credentials.py; `grep writeLog credentials.py` enforces no logging |
| T-1-SEC-02b | Information Disclosure | CVV via env var on shared host | accept | D-05 path is opt-in; error message warns about /proc/<pid>/environ visibility; documented as "trusted infrastructure only" in Plan 06 README |
| T-1-INFRA-02 | Denial of Service | per-call yaml.safe_load on every log line | mitigate | Module-level `_logging_level` + `configure()`; `test_writelog_does_not_open_config_yml` proves zero config.yml opens per call |
| T-1-NONTTY-FAIL | Denial of Service | bot launched headless without opt-in silently hangs | mitigate | `test_non_tty_without_optin_hard_fails` enforces SystemExit(1) within 1s instead of an indefinite getpass block |
| T-1-EMPTY-CVV | Tampering | user hits Enter at prompt | mitigate | Empty-string check raises SystemExit(1); `test_empty_getpass_response_exits` enforces |
</threat_model>

<verification>
- `pytest -x -q tests/test_credentials.py` passes (6 tests)
- `pytest -x -q tests/test_logger.py` passes (4 tests)
- `grep -E "writeLog|logger" credentials.py` returns nothing
- `grep "import yaml" logger.py` returns nothing
- `pytest -x -q` (full suite) exits 0
</verification>

<success_criteria>
- SEC-02 satisfied: CVV via getpass at runtime, never persisted, never logged
- INFRA-02 satisfied: logger no longer reads config.yml on every call
- D-04 + D-05 honored: TTY check, opt-in env path, fail-fast otherwise
- Plan 06 can integrate via `from credentials import collect_cvvs` and `from logger import configure as configure_logger, writeLog`
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundations-security/01-05-SUMMARY.md`
</output>
