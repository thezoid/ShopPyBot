---
phase: 12-stability-foundation
reviewed: 2026-06-09T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - logger.py
  - web/config_web.py
  - core/paths.py
  - tests/test_logger_config_path.py
  - tests/test_no_env_secret_reads.py
  - tests/test_paths.py
  - tests/test_web_config.py
  - tests/test_web_dashboard.py
findings:
  critical: 0
  warning: 3
  info: 1
  total: 4
status: fixed
---

# Phase 12: Code Review Report

**Reviewed:** 2026-06-09
**Depth:** standard
**Files Reviewed:** 7 (+1 cross-ref: core/paths.py)
**Status:** issues_found

## Summary

Phase 12 is a narrow debt-paydown phase (TD-1 through TD-4). Production changes are minimal: one lazy-import fix in `logger.py` and a documentation comment block in `web/config_web.py`. The five test files add regression coverage for those fixes. No new security vulnerabilities were introduced. Three findings are Warnings (two in tests, one in production code), one is Info.

## Warnings

### WR-01: Dead exported variable `_CONFIG_PATH` points to non-existent wrong-path file

**File:** `logger.py:10`

**Issue:** `_CONFIG_PATH` is declared at module level and documented as "Retained for tooling inspection only." It resolves to the repo-root `config.yml` (e.g., `E:\repos\ShopPyBot\config.yml`), which no longer exists after path migration. The live read now correctly uses `core.paths.config_path()` (AppData location). The dead variable is misleading: any tooling, introspector, or developer reading this variable will be handed a stale path to a missing file. Because it is a public module attribute (`logger._CONFIG_PATH`), it is importable and usable by callers.

**Fix:** Remove the dead variable entirely. If a canonical path constant is genuinely needed for tooling, expose `core.paths.config_path` instead.

```python
# Remove this line entirely:
# _CONFIG_PATH: Path = Path(__file__).parent / "config.yml"
```

If it must be retained for a specific tooling contract, update it to the live value and add a `# noqa` note documenting why the import below is not used instead:

```python
from core.paths import config_path as _config_path
_CONFIG_PATH: Path = _config_path()  # resolved once at import; for external tooling only
```

### WR-02: `test_dashboard_no_platform_config_toggles` uses `OR` where `AND` is required -- assertion always passes

**File:** `tests/test_web_dashboard.py:132`

**Issue:** The loop body uses:
```python
assert f'name="{platform}"' not in html or f'data-key="{platform}"' not in html
```
This is a De Morgan's-law inversion. The condition `A_absent OR B_absent` is trivially satisfied whenever *either* pattern is absent -- which is always true for `data-key="{platform}"` since the template never emits `data-key` attributes. The assertion will pass even if `name="amazon"` (or any other platform name) is present in the HTML. The intent (neither pattern appears) requires `AND`:
```python
assert f'name="{platform}"' not in html and f'data-key="{platform}"' not in html
```
The two explicit assertions directly above (lines 129-130) for `id="cfg-amazon"` and `id="cfg-bestbuy"` are correct and tight, so the regression value of this test for those platforms is fine -- but the loop body provides false confidence for the five remaining platforms.

**Fix:**
```python
for platform in platform_names:
    assert f'name="{platform}"' not in html and f'data-key="{platform}"' not in html, (
        f"Platform config toggle for {platform!r} leaked into SSR HTML"
    )
```

### WR-03: `_load_logging_level()` called at module import; migrated config may not exist yet on first boot

**File:** `logger.py:21`

**Issue:** `_LOGGING_LEVEL: int = _load_logging_level()` runs once at import time. `_load_logging_level()` now reads from `core.paths.config_path()` (the migrated AppData location). `migrate_legacy_paths()` runs inside `core/service.py:main()`, which is invoked *after* all module imports resolve. Therefore on the very first boot after the path migration, `core.paths.config_path()` returns a path to a file that does not yet exist. The `FileNotFoundError` branch falls back to `5`. If the repo-root `config.yml` had `logging_level` set to anything other than 5, the user loses that setting silently for the entire session.

This is not a new design flaw (the module-global snapshot was always stale once config changed at runtime), but Phase 12's rerouting makes the first-boot regression materially more likely: before this change, the repo-root file existed; after this change, the migrated-path file does not exist until `main()` runs.

The fallback behavior (level 5 = TRACE) is the maximum verbosity level, so the practical impact is that users see *more* logs, not fewer -- a noisy inconvenience rather than a silent failure. However, the intent of the user's config setting is violated.

**Fix (minimal, in-scope):** Expand the fallback chain in `_load_logging_level()` to check the legacy repo-root path when the migrated path is absent:

```python
def _load_logging_level() -> int:
    from core.paths import config_path as _config_path
    candidates = [_config_path(), Path(__file__).parent / "config.yml"]
    for path in candidates:
        try:
            with open(path, 'r') as f:
                settings = yaml.safe_load(f)
            return int(settings.get('debug', {}).get('logging_level', 5))
        except (FileNotFoundError, KeyError, TypeError, ValueError):
            continue
    return 5
```

## Info

### IN-01: `test_no_hardcoded_separators` does not scan `web/` directory

**File:** `tests/test_paths.py:59-63`

**Issue:** The separator-guard test scans `core/`, `logger.py`, `models.py`, and `utils.py`. The `web/` package is excluded. Phase 12 did not introduce hardcoded separators in `web/config_web.py` (verified), but any future file added under `web/` would be invisible to this guard. The test's non-empty and presence assertions are correct and an improvement over the pre-phase state, but the scan scope does not cover all source directories.

**Fix:** Add `web/` to the `src_files` collection:

```python
src_files = (
    list((repo_root / "core").rglob("*.py"))
    + list((repo_root / "web").rglob("*.py"))
    + [repo_root / "logger.py", repo_root / "models.py", repo_root / "utils.py"]
)
```

---

_Reviewed: 2026-06-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
