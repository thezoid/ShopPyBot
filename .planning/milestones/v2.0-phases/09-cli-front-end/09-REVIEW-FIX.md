---
phase: 09-cli-front-end
fixed_at: 2026-06-04T14:30:00Z
review_path: .planning/phases/09-cli-front-end/09-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 9: Code Review Fix Report

**Fixed at:** 2026-06-04
**Source review:** .planning/phases/09-cli-front-end/09-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (CR-01, WR-01, WR-02, WR-03, WR-04, WR-05)
- Fixed: 6
- Skipped: 0

Full test suite: 280 passed, 0 failures (2 pre-existing tests that expected main() to return normally were updated to expect SystemExit(0), consistent with the CR-01 fix).

## Fixed Issues

### CR-01: Bare invocation and --migrate discarded handler exit code

**Files modified:** `core/service.py`, `tests/test_cli_run.py`
**Commit:** 65cd4f7
**Applied fix:** Replaced bare `handle_setup(args, ...) / return` and `handle_run(args, ...) / return` with `_sys.exit(handler(...) or 0)` on both paths, matching the existing explicit-subcommand dispatch. Added regression test `test_bare_invocation_propagates_nonzero_exit` asserting exit code 1 when handle_run returns 1 (CVV gate failure scenario). Patched `core.cli.run.handle_run` (the module-level name) because `handle_run` is a local import inside `main()`.

Two pre-existing tests (`test_main_constructs_service_and_runs` in test_service.py, `test_main_migrate_flag` in test_credentials.py) expected `main()` to return normally; both updated to catch `SystemExit(0)` -- committed separately as 6b2282b.

### WR-01/02/03: config set robustness gaps

**Files modified:** `core/cli/config_cmd.py`, `tests/test_cli_config.py`
**Commit:** 1830bea
**Applied fix:**
- WR-01: Wrapped `_DEFAULT_YAML_PATH.read_text()` in a `try/except FileNotFoundError` block that falls back to `raw = ""`, so a fresh checkout with no config.yml starts from an empty dict instead of raising a traceback.
- WR-02: Added a range check `if key == "logging_level" and not (0 <= value <= 5)` after coercion; exits with code 2 and a clear message, consistent with the existing `_coerce` usage-error convention.
- WR-03: Added `dir_.mkdir(parents=True, exist_ok=True)` in `_atomic_yaml_write` before `tempfile.mkstemp`, mirroring the `EncryptedFileBackend._save()` pattern the docstring claimed to follow.
Five new tests added covering all three cases.

### WR-04: YAML comment loss on config set

**Files modified:** `core/cli/config_cmd.py`, `core/cli/__init__.py`
**Commit:** 7ac5cf6
**Applied fix:** No ruamel.yaml dependency added (no-new-deps constraint). Documented the behavior explicitly: added a note to `handle_config_set`'s docstring and added a `description=` paragraph to the `config set` argparse subparser so users see the warning in `shoppybot config set --help`. Accepted as known limitation.

### WR-05: migrate always exits 0 / silent no-op

**Files modified:** `core/cli/setup.py`, `tests/test_cli_setup.py`
**Commit:** 40d0daf
**Applied fix:** After the `migrate_from_env` call, print a `"Migrated {N} key(s)."` summary line unconditionally, and when `migrated` is empty, also print `"No env-var secrets found to migrate."` to stderr. This matches the REVIEW.md suggested fix. Two tests updated/added: existing `test_setup_migrate` now asserts key names and count appear in stdout; new `test_setup_migrate_nothing_to_migrate` asserts the empty-case message appears on stderr and return code is still 0.

---

_Fixed: 2026-06-04_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
