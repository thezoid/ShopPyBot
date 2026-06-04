---
phase: 09-cli-front-end
reviewed: 2026-06-04T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - core/cli/__init__.py
  - core/cli/run.py
  - core/cli/setup.py
  - core/cli/items.py
  - core/cli/config_cmd.py
  - core/cli/web.py
  - core/service.py
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-06-04
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the Phase 9 CLI front-end: argparse wiring (`__init__.py`), the five
handlers (`run`, `setup`, `items`, `config`, `web`), and the `BotService`/`main()`
entry point in `core/service.py`. Verified against the phase invariants
(SEC secret handling, config allowlist, lazy fastapi import, MOD-02 layering).

The high-weight invariants mostly hold:
- **Secret handling (setup.py):** getpass is used, only key NAMES are printed,
  EOF/GetPassWarning/StopIteration paths return None (skip). No secret value
  reaches stdout. Migrate path prints names only. PASS.
- **fastapi lazy import (web.py):** only `sys` at module level; `import fastapi`
  is inside the handler with a clean missing-dep message and exit 1. PASS.
- **MOD-02 layering:** CLI modules route through `BotService`; no direct
  models/orchestrator/registry imports. The AST guard test enforces it. PASS.
- **config set allowlist:** `set` rejects non-allowlisted keys with exit 2 and
  cannot write arbitrary keys. PASS for the bypass concern, but see WR findings
  for missing-file and value-range gaps.

However there is a real **exit-code contract defect** (bare `shoppybot` swallows
the run handler's failure code) plus several robustness gaps in the config-write
and CVV paths. Details below.

## Critical Issues

### CR-01: Bare `shoppybot` invocation discards handler exit code (exit 0 on CVV failure)

**File:** `core/service.py:178-181`
**Issue:** The bare-invocation and top-level `--migrate` branches call the handler
and `return` without propagating its return value, so `main()` exits 0
unconditionally. `handle_run` can legitimately return `1` (CVV echo-suppression
unavailable in a non-interactive terminal, `run.py:37`). With a bare `shoppybot`
that hits the CVV gate and fails, the process still exits 0, signalling success
to the shell / supervisor while the bot never started.

This also creates a behavior split with the explicit `run` subcommand, which
*does* propagate the code via `_sys.exit(args.func(...) or 0)` (line 183). The
test suite masks this because `test_bare_defaults_to_run` only asserts `run`
was called, never the exit code, and the CVV gate is bypassed (`test_mode=True`).

**Fix:**
```python
# Back-compat: top-level --migrate with no subcommand -> setup --migrate
if getattr(args, "migrate", False) and getattr(args, "command", None) is None:
    _sys.exit(handle_setup(args, BotService()) or 0)

# Bare shoppybot = run
if getattr(args, "func", None) is None:
    _sys.exit(handle_run(args, BotService()) or 0)

_sys.exit(args.func(args, BotService()) or 0)
```

## Warnings

### WR-01: `config set` crashes on missing config.yml (unhandled FileNotFoundError)

**File:** `core/cli/config_cmd.py:84`
**Issue:** `handle_config_set` does `_DEFAULT_YAML_PATH.read_text(...)` with no
guard. If `config.yml` does not exist (gitignored; CLAUDE.md notes it is copied
from `sample.config.yml`, so a fresh checkout has none), this raises an unhandled
`FileNotFoundError` traceback instead of a clean message or seeding a new file.
`setup.py:_write_backend` already handles this case (catches `FileNotFoundError`,
starts from `{}`), so the two YAML writers are inconsistent.

**Fix:**
```python
try:
    raw = _DEFAULT_YAML_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    raw = ""
data = yaml.safe_load(raw) or {}
```

### WR-02: `config set logging_level` accepts out-of-range / negative integers

**File:** `core/cli/config_cmd.py:35-40, 82-86`
**Issue:** `_coerce(int)` accepts any parseable integer. `logging_level` is
documented as 0-5 (CLAUDE.md, `DebugConfig.logging_level`), but the allowlist
write goes straight to YAML, bypassing pydantic. `DebugConfig` declares no
bounds either, so `config set logging_level 9999` (or `-3`) is silently persisted
and later loaded. The allowlist prevents *arbitrary keys* but does not validate
*values* for the keys it does allow.

**Fix:** Add range validation in the allowlist coercion, e.g. extend `ALLOWLIST`
with an optional validator or check `0 <= value <= 5` for `logging_level` before
writing, exiting 2 on violation (consistent with `_coerce`'s usage-error convention).

### WR-03: Atomic YAML write can leave a stale temp file across filesystems / on os.replace failure path mid-write

**File:** `core/cli/config_cmd.py:51-61`
**Issue:** `tempfile.mkstemp(dir=str(dir_))` is created in the same directory, which
is correct for `os.replace` atomicity. However, if `dir_` does not exist (e.g.
`config.yml` path points at a not-yet-created directory), `mkstemp` raises before
the `try`, so no cleanup runs — minor — but more importantly `_atomic_yaml_write`
does not `mkdir(parents=True, exist_ok=True)` the parent the way
`EncryptedFileBackend._save()` (credentials.py:263) does. The "mirrors
EncryptedFileBackend._save() pattern" docstring claim is therefore inaccurate:
the parent-dir creation step was dropped.

**Fix:**
```python
dir_ = path.parent
dir_.mkdir(parents=True, exist_ok=True)
fd, tmp = tempfile.mkstemp(dir=str(dir_), suffix=".yml")
```

### WR-04: `config set` rewrites config.yml through pydantic-free YAML round-trip, risking comment/format loss

**File:** `core/cli/config_cmd.py:84-86`
**Issue:** The setter loads the full YAML with `yaml.safe_load`, mutates one key,
and dumps the entire document back with `yaml.dump`. This strips all comments,
reorders keys, and reformats the user's `config.yml` on every `config set`. The
sample config is comment-heavy (per CLAUDE.md it is the documentation surface for
users). This is data-degrading for a human-edited file even though no secrets
live in config.yml. Not a corruption-of-secrets issue (secrets are not in
config.yml per CRED-06), but it silently destroys user annotations.

**Fix:** Document this as expected, or use a comment-preserving loader
(`ruamel.yaml`) for the read-modify-write. At minimum note the behavior in the
`config set` help text so users are not surprised.

### WR-05: `handle_setup` migrate path always returns 0 even when zero keys migrate / store write silently fails

**File:** `core/cli/setup.py:58-63`
**Issue:** `migrate_from_env` (credentials.py:388) silently skips keys whose
read-back fails (no-op backend such as `EnvVarBackend` writing to a real keyring
context, or a misconfigured backend) and only logs a WARNING. `handle_setup`
prints nothing and returns 0 when `migrated` is empty, so `shoppybot setup
--migrate` reports success to the shell even when nothing was actually persisted.
A user expecting their env secrets to be migrated gets a silent no-op.

**Fix:** Print a summary line and signal a distinct outcome when nothing migrated:
```python
migrated = migrate_from_env(store)
for key in migrated:
    print(f"Migrated: {key}")
if not migrated:
    print("No env-var secrets found to migrate.", file=sys.stderr)
print(f"Migrated {len(migrated)} key(s).")
return 0
```

## Info

### IN-01: `config_cmd.py` module docstring is stale ("stubs (plan 09-02 fills the bodies)")

**File:** `core/cli/config_cmd.py:1`
**Issue:** The docstring still describes the file as stubs to be filled later, but
the bodies are fully implemented. Misleading for future maintainers.
**Fix:** Update the module docstring to describe the implemented behavior.

### IN-02: `_current_prefix` list-mutation pattern is an over-engineered section tracker

**File:** `core/cli/setup.py:67-73`
**Issue:** `_current_prefix: list[str] = []` used as a mutable one-element box
(`_current_prefix[:] = [prefix]`) to track section headers is a needlessly clever
substitute for a plain string variable. Reduces readability for no benefit.
**Fix:**
```python
current_prefix = None
for key in SECRET_KEYS:
    prefix = key.split("_")[0]
    if prefix != current_prefix:
        current_prefix = prefix
        print(f"\n[{prefix}]")
```

### IN-03: `web.py` lazy import binds `fastapi` to an unused local (dead binding)

**File:** `core/cli/web.py:17`
**Issue:** `import fastapi  # noqa: F401` is imported purely as an availability
probe but never used (the body is a Phase 10 stub). This is intentional per the
CLI-04 invariant and is correctly suppressed, but a reviewer should confirm the
probe stays a probe; once Phase 10 lands, ensure `fastapi` is actually consumed
so the import is not silently flagged dead by future linters.
**Fix:** No change required for Phase 9; tracked here for Phase 10 follow-up.

_Reviewed: 2026-06-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
