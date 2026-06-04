---
phase: 08-credential-store
fixed_at: 2026-06-04T00:00:00Z
review_path: .planning/phases/08-credential-store/08-REVIEW.md
iteration: 2
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 8: Code Review Fix Report

**Fixed at:** 2026-06-04T00:00:00Z
**Source review:** .planning/phases/08-credential-store/08-REVIEW.md
**Iteration:** 2

**Summary:**
- Findings in scope: 2 (2 Warning; 3 Info out of scope per fix_scope=critical_warning)
- Fixed: 2
- Skipped: 0

Test suite result: 255 passed, 1 xpassed, 0 failures (python -m pytest -q)

## Fixed Issues

### WR-01: data_dir config field treated as full file path rather than directory

**Files modified:** `core/credentials.py`
**Commit:** 05d11ac
**Applied fix:** Changed `_build_store` to resolve `store_path` as `Path(cfg.credentials.data_dir) / "creds.bin"` when `data_dir` is set, so an operator setting `data_dir: "data"` correctly produces `data/creds.bin` rather than treating the directory path as the file target. The default `_DEFAULT_STORE_PATH` branch (`data/creds.bin` project-relative) is unchanged.

### WR-02: keyring probe writes to live shopbot service and can leave stray entry

**Files modified:** `core/credentials.py`
**Commit:** 880ed73
**Applied fix:** Changed `_has_real_keyring()` probe to use service name `"shopbot-probe"` instead of `"shopbot"` so a leaked entry never collides with real credentials. Restructured the probe to use `try/finally` so the `delete_password` call is guaranteed to run even when `set_password` or `get_password` raises. Delete failure in `finally` is silently swallowed and does not propagate. On `set/get` exception the function still returns False.

---

_Fixed: 2026-06-04T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
