---
phase: 09-cli-front-end
verified: 2026-06-04T00:00:00Z
status: human_needed
score: 4/4
overrides_applied: 0
human_verification:
  - test: "On Windows PowerShell: run `shoppybot setup`, enter a value for one credential key, observe the prompt"
    expected: "Input is hidden (not echoed to terminal), confirmation line shows key NAME only (e.g. 'Stored: AMZ_EMAIL'), not the value typed"
    why_human: "getpass no-echo behavior on a live Windows PowerShell TTY cannot be asserted by monkeypatching; piped-stdin path is tested but live terminal masking requires manual observation"
  - test: "On Ubuntu interactive terminal: run `shoppybot setup`, enter a value for one credential key"
    expected: "Input is hidden, confirmation line shows key name only, backend prompt accepts 'auto' default, 'Setup complete. N key(s) stored.' summary printed"
    why_human: "Live TTY getpass masking on Ubuntu requires a real terminal session; CI cannot observe whether the terminal actually suppresses echo"
---

# Phase 9: CLI Front-End Verification Report

**Phase Goal:** The `shoppybot` command-line tool provides all bot operations (run, setup, item management, config) through `BotService` and `CredentialStore`; it is fully functional with no web UI installed; setup works interactively on both Ubuntu and Windows.
**Verified:** 2026-06-04
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `shoppybot run` and `python main.py` both call `BotService.run()` with no duplicated orchestrator logic | VERIFIED | `main(["run"])` dispatches to `handle_run` → `svc.run(cvv)`; `main.py` calls `BotService(cfg).run(cvv)` directly. `test_bare_defaults_to_run`, `test_run_subcommand_calls_botservice_run`, `test_main_delegates_to_botservice_run` all pass. `core/cli/run.py` contains no orchestrator/registry/async_main imports. |
| 2 | `shoppybot setup` prompts each credential key by name via getpass with no echo; stores via `CredentialStore.set()`; confirms by key NAME only | VERIFIED (automated portion) | `core/cli/setup.py` calls `getpass.getpass()` and `store.set(key, val)` with `print(f"  Stored: {key}")` (name only, no value). `test_setup_no_secret_echo` asserts "MY_SECRET" absent from stdout. `test_setup_writes_credentials` asserts `store.set` called. `test_enter_skips_key` confirms skip-on-empty. Live TTY masking requires human check (see below). |
| 3 | `shoppybot items list/add/remove` all call `BotService`; `config show/set` work; MOD-02 guard active | VERIFIED | `core/cli/items.py` imports only `sys` and `core.service.BotService`. `test_items_list_table`, `test_items_add` (verifies `add_item("Widget","https://ex.com",False,1)`), `test_items_remove`, `test_items_remove_not_found` (exit 1) all pass. `test_config_set_test_mode`/`test_config_set_logging_level`/`test_config_set_invalid_key` (exit 2)/`test_config_show` all pass. `test_cli_no_direct_model_imports` (AST scan) passes with zero forbidden-name violations. |
| 4 | Uninstalling FastAPI leaves run/setup/items/config fully functional; no import errors | VERIFIED | `core/cli/web.py` has `import sys` as its only module-level import; `import fastapi` is inside `handle_web()` body only. `test_web_no_fastapi` confirms `handle_web` returns 1 and stderr contains "pip install .[web]" with `sys.modules['fastapi']=None`. `test_run_works_without_fastapi` confirms `main(["run"])` reaches `BotService.run()` with fastapi poisoned. All CLI imports verified clean under poisoned state. |

**Score:** 4/4 truths verified (live TTY test deferred to human verification)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/cli/__init__.py` | `build_parser()` with nested subparsers + `set_defaults(func=...)` dispatch | VERIFIED | 97 lines; `build_parser()` returns parser with run/setup/items/config/web; `parse_known_args(["items","list"]).func is handle_items_list` confirmed; `parse_known_args([]).func is None` confirmed |
| `core/cli/run.py` | `handle_run(args, svc)` calling `svc.run(cvv)` with CVV gate | VERIFIED | 39 lines; CVV gate mirrors `main.py` logic (bestbuy.com + auto_buy + not test_mode); calls `svc.run(cvv)`; returns 0 on success or 1 on non-interactive stdin |
| `core/cli/setup.py` | Getpass prompts, `get_store().set()`, backend write, `--migrate` alias | VERIFIED | 84 lines; uses `getpass.getpass`, `store.set(key, val)`, `_atomic_yaml_write`, `migrate_from_env`; confirms by key name only |
| `core/cli/items.py` | `handle_items_list/add/remove` over BotService; `_format_items_table` | VERIFIED | 57 lines; imports only `sys` and `BotService`; `_format_items_table` renders aligned table; remove exits 1 on unknown URL |
| `core/cli/config_cmd.py` | `ALLOWLIST`, `_coerce`, `_atomic_yaml_write`, `handle_config_show/set` | VERIFIED | 89 lines; `_atomic_yaml_write` uses `tempfile.mkstemp + os.replace`; unknown key raises `SystemExit(2)`; bool/int coercion correct |
| `core/cli/web.py` | `handle_web` with lazy `try/except ImportError` fastapi seam | VERIFIED | 27 lines; only `sys` at module level; `import fastapi` inside function body; prints install hint to stderr on ImportError |
| `core/service.py:main` | Restructured to `build_parser() + parse_known_args(argv)` dispatch | VERIFIED | `main(argv=None)` calls `build_parser()`, `parse_known_args(argv)`, dispatches via `args.func`; `--migrate` back-compat alias preserved; bare invocation defaults to `handle_run` |
| `tests/test_cli_run.py` | CLI-01 run/dispatch/main-shim tests | VERIFIED | 3 active tests; `test_bare_defaults_to_run`, `test_run_subcommand_calls_botservice_run`, `test_help_exits_zero` — all pass |
| `tests/test_cli_setup.py` | CLI-02 credential setup tests | VERIFIED | 5 active tests; all pass including `test_setup_no_secret_echo` |
| `tests/test_cli_items.py` | CLI-03 items list/add/remove tests | VERIFIED | 4 active tests; all pass; `test_items_add` asserts exact `add_item("Widget","https://ex.com",False,1)` call |
| `tests/test_cli_config.py` | CLI-03 config show/set tests | VERIFIED | 4 active tests; all pass |
| `tests/test_cli_no_fastapi.py` | CLI-04 no-fastapi guard tests | VERIFIED | 2 active tests; all pass |
| `tests/test_cli_mod02.py` | MOD-02 AST grep guard | VERIFIED | 1 active test; AST scan of all `core/cli/*.py` for 7 forbidden names returns zero violations |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `core/service.py:main` | `core.cli.build_parser` | `from core.cli import build_parser` + `parse_known_args(argv)` | WIRED | Confirmed in source; `test_bare_defaults_to_run` + `test_help_exits_zero` exercise this path |
| `core/cli/run.py:handle_run` | `BotService.run` | `svc.run(cvv)` | WIRED | Line 38: `svc.run(cvv)`; test verifies `mock_svc.run.assert_called_once()` |
| `core/cli/__init__.py` | All handler functions | `set_defaults(func=...)` on each leaf subparser | WIRED | All 6 handlers wired; `parse_known_args` dispatch verified programmatically |
| `core/cli/setup.py:handle_setup` | `CredentialStore.set` | `get_store().set(key, val)` | WIRED | Line 76: `store.set(key, val)`; `test_setup_writes_credentials` asserts `mock_store.set.assert_called()` |
| `core/cli/setup.py:handle_setup` | `config.yml credentials.backend` | `_write_backend` → `_atomic_yaml_write` | WIRED | `_write_backend` calls `_atomic_yaml_write(path, data)`; `test_setup_writes_backend` verifies YAML written |
| `core/cli/config_cmd.py:handle_config_set` | `config.yml debug.*` | `yaml.safe_load + ALLOWLIST + _atomic_yaml_write` | WIRED | `handle_config_set` reads YAML, updates section, writes atomically; tests verify `test_mode is False` after set |
| `core/cli/items.py:handle_items_add` | `BotService.add_item` | `svc.add_item(name, url, auto_buy, quantity)` | WIRED | Line 39: `svc.add_item(args.name, args.url, args.auto_buy, args.quantity)`; test asserts exact call args |
| `core/cli/items.py:handle_items_remove` | `BotService.list_items + remove_item` | `list_items()` lookup then `remove_item(url)` | WIRED | Lines 49-54: lookup then conditional `remove_item`; not-found path returns 1 without calling remove |
| `core/cli/web.py:handle_web` | `fastapi` (optional) | `try: import fastapi / except ImportError` | WIRED | Lazy import inside function body; no top-level fastapi import confirmed by AST check |
| `tests/test_cli_mod02.py` | `core/cli/*.py` | `ast.walk` import scan | WIRED | Active test scanning all 6 CLI modules; 0 violations confirmed |

### Data-Flow Trace (Level 4)

The CLI modules are adapters, not data renderers. All state flows through `BotService` (which reads from SQLite via `get_items_sync`). The data-flow for `items list`:

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `core/cli/items.py:handle_items_list` | `rows` from `svc.list_items()` | `BotService.list_items()` → `get_items_sync()` → SQLite | Yes — real DB query wrapped by BotService | FLOWING |
| `core/cli/config_cmd.py:handle_config_show` | `cfg` from `svc.get_config()` | `BotService.get_config()` returns `AppConfig` loaded from `config.yml` | Yes — real config load | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `--help` shows all 5 subcommands | `python -c "from core.service import main; main(['--help'])"` | Prints run/setup/items/config/web with descriptions; exits 0 | PASS |
| Parser dispatches `items list` correctly | `python -c "from core.cli import build_parser; ..."` | `a.func is handle_items_list`; bare `b.func is None` | PASS |
| No top-level fastapi import in web.py | AST check on `core/cli/web.py` | Zero top-level Import/ImportFrom nodes for fastapi | PASS |
| CLI imports clean with fastapi poisoned | `python -c "import sys; sys.modules['fastapi']=None; from core.cli import build_parser; ..."` | All core CLI imports succeed | PASS |
| Full test suite | `python -m pytest -q` | 274 passed, 1 xpassed, 2 warnings | PASS |

### Probe Execution

No probe scripts declared in PLAN files. Step 7c: SKIPPED (no `scripts/*/tests/probe-*.sh` for this phase).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CLI-01 | 09-01 | `shoppybot run` starts bot through BotService; `python main.py` shim preserved | SATISFIED | `test_bare_defaults_to_run`, `test_run_subcommand_calls_botservice_run`, `test_main_delegates_to_botservice_run` all pass; both paths call `BotService.run()` |
| CLI-02 | 09-02 | `shoppybot setup` stores credentials interactively via getpass/CredentialStore | SATISFIED (automated) | `test_setup_writes_credentials`, `test_setup_no_secret_echo`, `test_enter_skips_key`, `test_setup_writes_backend`, `test_setup_migrate` pass; live TTY check is human-only |
| CLI-03 | 09-02, 09-03 | `items list/add/remove` and `config show/set` via BotService/config | SATISFIED | 8 tests covering all subcommands pass; `test_config_set_invalid_key` confirms exit 2 on bad key |
| CLI-04 | 09-04 | CLI fully functional without FastAPI installed | SATISFIED | `test_web_no_fastapi`, `test_run_works_without_fastapi` pass; zero top-level fastapi imports in CLI package |
| MOD-02 | 09-03 | No front-end module bypasses BotService to call orchestrator/registry/DB directly | SATISFIED | `test_cli_no_direct_model_imports` AST scan finds 0 violations across all `core/cli/*.py` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `core/cli/web.py` | 24 | `# Phase 10 will implement the web server here` (comment placeholder) | Info | Expected stub — Phase 10 scope; not a runtime hollow path; `handle_web` returns non-zero when fastapi absent, which is the specified behavior |

No TBD, FIXME, XXX, or HACK markers found in any `core/cli/*.py` or `tests/test_cli_*.py` file.

The `core/cli/web.py` placeholder comment is informational, not a code stub — the function body is complete per Phase 9 scope (lazy import seam + install hint). Phase 10 will add the server implementation.

### Human Verification Required

#### 1. Windows PowerShell — Live Terminal Echo Suppression

**Test:** On a Windows machine with the package installed, open PowerShell and run `shoppybot setup` (or `python -c "from core.service import main; main(['setup'])"` if not installed). At the first credential prompt, type a value.
**Expected:** The typed characters are NOT echoed to the terminal. The confirmation line shows `  Stored: {KEY_NAME}` with the key name only — the value you typed does not appear anywhere in the output.
**Why human:** `getpass.getpass()` terminal masking depends on whether stdout/stdin are a real TTY. The piped-stdin path (EOFError skip) is covered by automated tests; live TTY masking cannot be asserted by `monkeypatch.setattr`. Phase 11 will include this in the cross-platform verification matrix.

#### 2. Ubuntu Interactive Terminal — Live Terminal Echo Suppression

**Test:** On Ubuntu desktop or with an interactive terminal session, run `shoppybot setup`. At one credential prompt, enter a value; at another, press Enter to skip.
**Expected:** Characters are not echoed. Skipped keys produce no output. Stored keys show `  Stored: {KEY_NAME}`. Backend prompt accepts Enter for default `auto`. Final line: `Setup complete. N key(s) stored.`
**Why human:** Same rationale as above — live TTY behavior on Linux. This is explicitly called out in `09-VALIDATION.md` under Manual-Only Verifications.

### Gaps Summary

No gaps. All 4 ROADMAP Success Criteria are verified in the codebase:

1. Both `shoppybot run` and `python main.py` call `BotService.run()` — confirmed by source code and 9 tests covering both paths.
2. `shoppybot setup` uses getpass with no echo, stores via `CredentialStore.set()`, confirms by key name only — confirmed by 5 automated tests; live TTY behavior is the only remaining human check.
3. `items list/add/remove` and `config show/set` all route through `BotService` — confirmed by 8 tests; MOD-02 enforced by active AST guard.
4. FastAPI optional: uninstalling it leaves run/setup/items/config functional — confirmed by 2 tests with `sys.modules['fastapi']=None` sentinel; zero top-level fastapi imports in CLI package.

Full test suite: 274 passed, 1 xpassed (pre-existing), 0 failures, 0 skips in CLI test files.

---

_Verified: 2026-06-04_
_Verifier: Claude (gsd-verifier)_
