---
phase: 01-foundations-security
fixed_at: 2026-06-02T00:00:00Z
review_path: .planning/phases/01-foundations-security/01-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-06-02
**Source review:** .planning/phases/01-foundations-security/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-03: AppConfig._active_yaml_file mutable class-level race condition

**Files modified:** `core/config_schema.py`
**Commit:** 8853a27
**Applied fix:** Added `import threading` and a module-level `_yaml_path_local: threading.local = threading.local()`. Removed the `_active_yaml_file: Path` class attribute entirely. Rewrote `__init__` to set `_yaml_path_local.active` instead of mutating the class attribute. Updated `settings_customise_sources` to read via `getattr(_yaml_path_local, "active", _DEFAULT_YAML_PATH)`. All 5 test_config_schema tests pass.

### WR-05: pydantic not pinned in requirements.txt

**Files modified:** `requirements.txt`
**Commit:** 0971403
**Applied fix:** Added `pydantic==2.13.3` (installed version confirmed via `python -c "import pydantic; print(pydantic.__version__)"`) on the line immediately before `pydantic-settings[yaml]==2.14.0`, satisfying the INFRA-01 exact-pin requirement.

### WR-02: CVV prompt fires even when test_mode=True

**Files modified:** `main.py`
**Commit:** 5d23468
**Applied fix:** Added `not test_mode` as the first condition of `needs_bb_autobuy`. The expression now evaluates to False whenever `test_mode=True`, so `collect_cvv()` is never called and CI cannot deadlock on a getpass prompt when BestBuy items are present in config with `auto_buy: true`.

### WR-04: logger.py reads config.yml relative to CWD at import time

**Files modified:** `logger.py`
**Commit:** 5d55cc1
**Applied fix:** Added `from pathlib import Path` and defined `_CONFIG_PATH: Path = Path(__file__).parent / "config.yml"` at module level. Updated `_load_logging_level` to open `_CONFIG_PATH` instead of the bare `'config.yml'` string. Logger and AppConfig now resolve the same file regardless of process CWD. Module-level caching of `_LOGGING_LEVEL` is preserved. test_logger passes.

### WR-06: test_config.py validates deprecated legacy credential schema

**Files modified:** `tests/test_config.py`
**Commit:** 6e603b6
**Applied fix:** Rewrote the file with three tests against `AppConfig` (replacing the single test against the deprecated `config.py` singleton):
1. `test_legacy_credentials_trigger_deprecation_warning`: asserts `amz_email` in a YAML triggers `DeprecationWarning` via `AppConfig`.
2. `test_appconfig_has_no_credential_fields`: asserts `AppConfig` has no `amz_email`, `amz_pwd`, `bb_email`, `bb_password`, or `bb_cvv` attributes (new credential-free contract).
3. `test_appconfig_items_still_load_correctly`: sanity check that structured sections still load from a config that contains legacy keys.
All 3 new tests pass; full suite: 17/17 passed.

---

_Fixed: 2026-06-02_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
