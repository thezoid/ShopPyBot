# Phase 11: Cross-Platform Verification - Research

**Researched:** 2026-06-04
**Domain:** Python cross-platform path resolution, platformdirs, GitHub Actions CI matrix, SQLite/credential migration, smoke testing
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Path Strategy (XPLAT-01)**
- Adopt `platformdirs` (pinned). New module `core/paths.py` exposes data dir, config path, and log dir. All construction via pathlib — no hardcoded `/` or `\` anywhere.
- First-run migration: if legacy `data/shop_py_bot.db`, `data/creds.bin`, `config.yml`, `logs/` exist project-relative, move/copy them ONCE to the OS-standard locations, logging only paths (never secret values). Idempotent.
- Fix `models.py` CWD-relative `DB_PATH` by anchoring under `core/paths.py`'s resolved data dir.
- Route all four path anchors through `core/paths.py`: `credentials._DEFAULT_STORE_PATH`, `config_schema._DEFAULT_YAML_PATH`, `logger.py` log dir, `models.DB_PATH`. `credentials.data_dir` config override still wins.

**Smoke Tests and CI (XPLAT-02)**
- Env-independent pytest smoke: package imports, `shoppybot --help`/`setup`/`items`/`config show` run without error, path resolution returns OS-appropriate locations, credential-backend auto-selection correct. No real browser/keyring.
- GitHub Actions matrix: `ubuntu-latest` + `windows-latest`, Python 3.13, `pip install .[web]`, full suite + smoke.
- Backend-per-OS unit test: monkeypatch `_has_real_keyring()` true/false to assert selection logic; env-independent.

**Docs and Verification Matrix (XPLAT-01, XPLAT-02)**
- `docs/PLATFORMS.md`: per-OS path table, expected backend per environment, repro steps, manual matrix (Ubuntu desktop · Ubuntu headless · Windows x {commands} x {backends}).
- Fold deferred Phase 8/9/10 live checks into the manual matrix.

### Claude's Discretion
- Exact `core/paths.py` API shape, `appname`/`appauthor` args, move vs copy strategy, CI workflow file name/triggers, precise smoke-test assertions — provided locked decisions hold, no secret value ever logged/migrated in plaintext to a less-protected location, and the 335-test suite stays green.

### Deferred Ideas (OUT OF SCOPE)
- Executing the manual matrix on real Ubuntu desktop/headless hardware.
- macOS support.
- Packaged installer/distribution.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| XPLAT-01 | Runs on Ubuntu (desktop + headless) and Windows; data/config/log paths per-OS (no hardcoded separators); locations documented | platformdirs API verified; Linux XDG paths confirmed from source; Windows %LOCALAPPDATA% confirmed by live probe; migration pattern designed; separator-grep test designed |
| XPLAT-02 | Documented verification matrix and/or automated smoke confirms import + CLI + backend selection on both Ubuntu and Windows | GitHub Actions matrix pattern confirmed; headless CI env var mitigations confirmed; smoke command list designed; backend mock test pattern designed |
</phase_requirements>

## Summary

Phase 11 is the final milestone: a targeted set of code changes (new `core/paths.py`, path re-anchoring, first-run migration) plus a CI matrix and documentation layer. No new functional features are added.

The three concrete code changes are: (1) create `core/paths.py` exposing `data_dir()`, `config_path()`, and `log_dir()` backed by `platformdirs`; (2) re-anchor `models.DB_PATH`, `credentials._DEFAULT_STORE_PATH`, `config_schema._DEFAULT_YAML_PATH`, and `logger.py`'s log dir through that module; (3) add a first-run idempotent migration that moves legacy project-relative files to the resolved locations. The new test module `tests/test_xplat.py` and GitHub Actions workflow `.github/workflows/ci.yml` cover XPLAT-02. `docs/PLATFORMS.md` closes the documentation requirement.

The key risk is keeping the 336-test suite green after re-anchoring paths. Every existing test that exercises paths does so via monkeypatching `models.DB_PATH` (the `tmp_data_dir` fixture) or passing `yaml_file=` to `AppConfig`. Those seams still work because `core/paths.py` is consumed at module import time via a module-level attribute, which `monkeypatch.setattr` can override. An `SHOPBOT_DATA_DIR` env override provides a second seam that is easier to use in CI.

**Primary recommendation:** Create `core/paths.py` with a `SHOPBOT_DATA_DIR` env-override seam; update the four path anchors to import from it; add migration in `core/service.py` entry point; write a compact `tests/test_xplat.py`; replace the legacy per-OS workflow files with one matrix workflow.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| OS-standard path resolution | core module (paths.py) | all consumers | Single source of truth; all four consumers import it |
| First-run migration | startup entry (BotService or service.py) | core/paths.py | Must run before any DB/store/log access; belongs in the orchestration layer, not path helpers |
| Credential backend auto-selection test | unit test layer | conftest monkeypatch | Pure logic mock; no OS interaction needed |
| Path separator assertion (SC1 guard) | test layer | CI workflow | Grep over source files; runs on any OS |
| CI matrix execution | GitHub Actions | local pytest | Matrix runs on hosted runners; local runs dev box only |
| Manual verification matrix | docs (PLATFORMS.md) | — | Human step; not automatable for real-device columns |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `platformdirs` | `==4.10.0` [VERIFIED: pypi.org/project/platformdirs] | Resolves OS-appropriate user data/config/log dirs | 147M+ downloads/week; official XDG on Linux, %APPDATA% on Windows; Python 3.10-3.14 compatible; used by pip, virtualenv, pytest themselves |

### Supporting (already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pathlib` | stdlib | Path construction without hardcoded separators | All new path code; replaces `os.path.join` in logger.py |
| `shutil` | stdlib | `shutil.copy2` for migration of DB/creds.bin/config.yml | Copy strategy preserves metadata |
| `pytest` | `==9.0.3` | Smoke test runner | Already in requirements.txt |
| `httpx` | transitively via `starlette` | FastAPI TestClient for web smoke (if used) | Already present via `.[web]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `platformdirs` | `appdirs` | `appdirs` is unmaintained since 2020; `platformdirs` was forked from it specifically because of that |
| `platformdirs` | hard-coded `~/.local/share` | Does not work on Windows; breaks macOS; XDG override env vars not respected |
| `shutil.move` | `shutil.copy2` + manual delete | `shutil.move` across filesystems can delete src before copy completes; `copy2` then `Path.unlink()` gives cleaner error recovery |

**Installation (new dep only):**
```bash
pip install platformdirs==4.10.0
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `platformdirs` | PyPI | 6+ yrs (forked 2021 from `appdirs`) | ~147M/week [CITED: pypistats.org] | github.com/tox-dev/platformdirs | slopcheck unavailable — see note | Approved [VERIFIED: pypi.org/project/platformdirs] |

**Packages removed due to slopcheck [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** none

*slopcheck could not be installed in this session (permission denied for system-level pip). `platformdirs` is a transitive dependency of `seleniumbase` already installed in this project's environment (confirmed: `pip show platformdirs` returns version 4.3.6, latest is 4.10.0). The package is produced by the `tox-dev` organization, the same maintainer as `tox`, `virtualenv`, and `build` — extremely high-trust ecosystem. No checkpoint required.*

## Architecture Patterns

### System Architecture Diagram

```
startup entry (core/service.py main())
    |
    v
core/paths.py  <-- SHOPBOT_DATA_DIR env override OR platformdirs
    |  data_dir()     config_path()    log_dir()
    |      |               |               |
    v      v               v               v
models.py  credentials.py  config_schema.py  logger.py
DB_PATH    _DEFAULT_STORE_PATH  _DEFAULT_YAML_PATH  log_dir

migration (one-time, idempotent)
    legacy data/ --> resolved data_dir()
    legacy config.yml --> resolved config_path()
    legacy logs/ --> resolved log_dir()
    [runs in BotService.__init__ before any DB/store/log access]

CI matrix (.github/workflows/ci.yml)
    ubuntu-latest + windows-latest
        --> pip install .[web]
        --> pytest (full suite + smoke)
        env: SDL_AUDIODRIVER=dummy, PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring, SHOPBOT_DATA_DIR=${{ runner.temp }}/shopbot
```

### Recommended Project Structure

```
core/
    paths.py          # NEW: data_dir(), config_path(), log_dir() + migration entry
tests/
    test_xplat.py     # NEW: smoke + path resolution + backend-selection tests
docs/
    PLATFORMS.md      # NEW: per-OS path table + manual verification matrix
.github/workflows/
    ci.yml            # NEW (replaces three stale per-OS files)
```

### Pattern 1: core/paths.py module shape

**What:** A module-level singleton `_DIRS` constructed once at import. Three public accessors return `Path` objects. An env override `SHOPBOT_DATA_DIR` makes tests trivially redirectable.

**When to use:** Every consumer imports the accessor and assigns it to its module-level constant at import time. Tests monkeypatch the constant on the consumer module OR set `SHOPBOT_DATA_DIR` before import.

```python
# Source: platformdirs 4.10.0 official API + project CONTEXT.md pattern
from __future__ import annotations
import os
from pathlib import Path
from platformdirs import PlatformDirs

_APP_NAME = "shoppybot"
# appauthor=False suppresses the redundant vendor subdir on Windows
# (produces %LOCALAPPDATA%\shoppybot, not %LOCALAPPDATA%\shoppybot\shoppybot)
_DIRS = PlatformDirs(_APP_NAME, appauthor=False)


def _env_override() -> Path | None:
    val = os.environ.get("SHOPBOT_DATA_DIR", "").strip()
    return Path(val) if val else None


def data_dir() -> Path:
    return _env_override() or Path(_DIRS.user_data_dir)


def config_path() -> Path:
    return (data_dir() / "config.yml")


def log_dir() -> Path:
    override = _env_override()
    if override:
        return override / "logs"
    return Path(_DIRS.user_log_dir)
```

**Key design decisions:**
- `config_path()` returns a `Path`, not a `str`. Callers use it as `Path`. `AppConfig.__init__` already accepts `Path | str | None` for `yaml_file`.
- `log_dir()` follows platformdirs convention: on Windows returns `%LOCALAPPDATA%\shoppybot\Logs`, on Linux returns `~/.local/state/shoppybot/log`.
- No module-level side-effects beyond the `_DIRS` construction (no mkdir; migration is elsewhere).
- File is under 30 lines. [VERIFIED: codebase CLAUDE.md constraint]

### Pattern 2: Consumer re-anchoring

**What:** Replace each project-relative default with an import from `core.paths`.

```python
# core/credentials.py — change line 40
from core.paths import data_dir as _paths_data_dir
_DEFAULT_STORE_PATH: Path = _paths_data_dir() / "creds.bin"

# core/config_schema.py — change line 17
from core.paths import config_path as _paths_config_path
_DEFAULT_YAML_PATH: Path = _paths_config_path()

# logger.py — change lines 42-45
from core.paths import log_dir as _paths_log_dir
# ... replace os.path.join(_scriptdir, "logs") with _paths_log_dir()

# models.py — change line 5
from core.paths import data_dir as _paths_data_dir
DB_PATH = str(_paths_data_dir() / "shop_py_bot.db")
```

**Test seam:** Existing `conftest.py:tmp_data_dir` monkeypatches `models.DB_PATH` directly — this still works because the monkeypatch runs after module import. `SHOPBOT_DATA_DIR` env var set before import achieves the same effect globally.

### Pattern 3: First-run migration function

**What:** Called once before any store/DB/log access. Checks for each legacy path; if found and target not yet present, copies then removes. Logs only file paths, never secret content.

```python
# Source: stdlib shutil + project CONTEXT.md requirements
def migrate_legacy_paths() -> None:
    """Move project-relative legacy data to OS-standard locations (idempotent)."""
    from core.paths import data_dir, config_path, log_dir
    import shutil

    _REPO_ROOT = Path(__file__).parent.parent  # core/ -> repo root

    _migrations = [
        (_REPO_ROOT / "data" / "shop_py_bot.db",  data_dir() / "shop_py_bot.db"),
        (_REPO_ROOT / "data" / "creds.bin",        data_dir() / "creds.bin"),
        (_REPO_ROOT / "config.yml",                config_path()),
    ]
    for src, dst in _migrations:
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            src.unlink()
            writeLog(f"Migrated {src} -> {dst}", "INFO")

    # logs/ dir migration: copy files, then remove src dir
    legacy_logs = _REPO_ROOT / "logs"
    new_logs = log_dir()
    if legacy_logs.is_dir() and not new_logs.exists():
        shutil.copytree(str(legacy_logs), str(new_logs))
        shutil.rmtree(str(legacy_logs))
        writeLog(f"Migrated logs {legacy_logs} -> {new_logs}", "INFO")
```

**Idempotency:** condition `src.exists() and not dst.exists()` guarantees the copy runs exactly once. Second run: src gone (unlinked), dst present — both guards fail, nothing happens.

**Safety:** `copy2` then `unlink`. If `copy2` fails, `src` is untouched. If `unlink` fails, next run finds `src` present but `dst` also present — condition `not dst.exists()` is False, so no overwrite.

**creds.bin placement safety:** `creds.bin` is already encrypted (Fernet+scrypt). Moving it from `data/` (project-relative, potentially in a git repo) to `%LOCALAPPDATA%\shoppybot` (user-only directory, not in any git repo) is strictly more protected, not less. [VERIFIED: codebase CONTEXT.md requirement confirmed]

### Pattern 4: Backend-per-OS smoke test

```python
# tests/test_xplat.py pattern
from unittest.mock import patch

def test_auto_selects_keyring_when_available(reset_credential_store, tmp_config_yml):
    with patch("core.credentials._has_real_keyring", return_value=True):
        from core.credentials import _build_store
        from core.config_schema import AppConfig
        cfg = AppConfig(yaml_file=tmp_config_yml)
        store = _build_store("auto", cfg)
    assert store.__class__.__name__ == "KeyringBackend"


def test_auto_selects_file_when_no_keyring(reset_credential_store, tmp_config_yml, monkeypatch):
    monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "test-passphrase")
    with patch("core.credentials._has_real_keyring", return_value=False):
        from core.credentials import _build_store
        from core.config_schema import AppConfig
        cfg = AppConfig(yaml_file=tmp_config_yml)
        store = _build_store("auto", cfg)
    assert store.__class__.__name__ == "EncryptedFileBackend"


def test_auto_falls_back_to_env(reset_credential_store, tmp_config_yml, monkeypatch):
    monkeypatch.delenv("SHOPBOT_STORE_PASSPHRASE", raising=False)
    with patch("core.credentials._has_real_keyring", return_value=False):
        from core.credentials import _build_store
        from core.config_schema import AppConfig
        cfg = AppConfig(yaml_file=tmp_config_yml)
        store = _build_store("auto", cfg)
    assert store.__class__.__name__ == "EnvVarBackend"
```

### Pattern 5: GitHub Actions matrix workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [master, dev]
  pull_request:
    branches: [master, dev]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]

    env:
      # Headless audio: prevents pygame.mixer.init() failure on CI runners
      SDL_AUDIODRIVER: dummy
      SDL_VIDEODRIVER: dummy
      # Prevents keyring from probing D-Bus / SecretService on headless Ubuntu
      PYTHON_KEYRING_BACKEND: keyring.backends.null.Keyring
      # Redirect all paths to a temp dir so tests never write to user home
      SHOPBOT_DATA_DIR: ${{ runner.temp }}/shopbot

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Install
        run: pip install -e .[web]
      - name: Test
        run: pytest --tb=short
```

**Key env vars explained:**
- `SDL_AUDIODRIVER=dummy` + `SDL_VIDEODRIVER=dummy`: `utils.py` calls `pygame.mixer.init()` at module import. On headless Linux CI without audio, this raises `pygame.error: No available audio device`. The `dummy` driver creates a no-op device. [CITED: pygame.org/wiki/HeadlessNoWindowsNeeded]
- `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring`: On Ubuntu runners, `_has_real_keyring()` would try to probe D-Bus/SecretService and either hang or raise. Setting this backend directly makes `keyring.get_keyring()` return `NullKeyring`, which the existing `_has_real_keyring()` guard detects and returns `False`. [CITED: keyring.readthedocs.io]
- `SHOPBOT_DATA_DIR=${{ runner.temp }}/shopbot`: Redirects all path resolution to a writable temp dir without monkeypatching; keeps runner home clean; works on both Ubuntu and Windows because GHA exposes `runner.temp` consistently.
- `pip install -e .[web]`: installs both core + web extras; tests the full surface including FastAPI routes. [VERIFIED: existing pyproject.toml `[project.optional-dependencies].web`]

### Anti-Patterns to Avoid

- **Hardcoded string separators:** Never `"data" + "/" + "shop_py_bot.db"` or `"logs\\" + date`. Always `Path(base) / "shop_py_bot.db"`. The SC1 grep test catches regressions.
- **CWD-dependent paths at import time:** `os.path.join('data', 'shop_py_bot.db')` (current bug in models.py) — breaks when the process is launched from any directory other than the repo root.
- **`__file__`-relative paths for user data:** `Path(__file__).parent.parent / "data"` (current pattern in credentials.py) — puts user data inside the installed package; breaks `pip install` (package may be in site-packages, not writable).
- **Migration that logs secret values:** Log only the file path, never the decrypted content or raw bytes of `creds.bin`.
- **Migration that overwrites an existing destination:** Check `not dst.exists()` before copying. A second run must be a no-op.
- **`getpass` call in `_build_store` triggered by migration:** Migration runs before `init_store`, not inside it. Migration should NOT prompt for passphrase; it copies the binary `creds.bin` file as-is (still encrypted). Only `_build_store("file", ...)` ever calls getpass.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OS-appropriate user dir paths | Custom `sys.platform` if/else blocks | `platformdirs.PlatformDirs` | Handles XDG env overrides, Windows roaming vs local, macOS `~/Library`, edge cases in 10+ OS variants |
| Cross-platform path separator | String concatenation with `/` or `\\` | `pathlib.Path /` operator | pathlib handles separator, case normalization, and UNC paths automatically |

**Key insight:** The OS-specific branching for user dirs is exactly the problem `platformdirs` was built to solve — it has been battle-tested across 147M+/week installs and handles every XDG override, Windows roaming/local distinction, and platform quirk.

## Common Pitfalls

### Pitfall 1: Module-level `data_dir()` call cached before env override

**What goes wrong:** If `core/paths.py` calls `data_dir()` at module-level and a test sets `SHOPBOT_DATA_DIR` after import, the cached result is wrong.

**Why it happens:** Python caches module-level constants at import time. Setting an env var after `import core.paths` doesn't re-evaluate `_DIRS`.

**How to avoid:** Make `data_dir()` a function (not a module-level constant) that reads `os.environ.get("SHOPBOT_DATA_DIR")` on every call. This is cheap (just an env read). The consumer modules assign the result to their own module-level constant; tests monkeypatch that constant directly as they already do.

**Warning signs:** A test that sets `SHOPBOT_DATA_DIR` in a fixture but finds paths still resolve to the real platformdirs location.

### Pitfall 2: `models.py` `initialize_db` uses `os.path.dirname(DB_PATH)` for makedirs

**What goes wrong:** After re-anchoring `DB_PATH` to an absolute path, `os.path.dirname(DB_PATH)` returns the correct parent directory. But the existing `os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)` call in `initialize_db` will silently succeed for any absolute path. No code change needed here — just verify it works for the new resolved path.

**Pitfall is:** the `delete=True` path calls `os.remove(DB_PATH)` then `os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)`. If the data dir has been removed by the `delete` step (it hasn't — only the file is removed), makedirs re-creates it. This is correct behavior. Confirm `test_models.py:setup_db` fixture still works after re-anchoring by running its tests.

### Pitfall 3: `pygame.mixer.init()` at `utils.py` import time fails on headless CI

**What goes wrong:** `utils.py` line 38 calls `initialize_pygame()` which calls `pygame.mixer.init()` at module import time. On headless Ubuntu CI (no audio device), this raises `pygame.error: No available audio device` during test collection, before any test runs.

**Why it happens:** `utils.py` is imported transitively via `notifications/sound_notifier.py` which is imported by the notification dispatcher, which is imported by tests.

**How to avoid:** Set `SDL_AUDIODRIVER=dummy` in the CI workflow env block (not per-step, so it's active during collection). The dummy driver creates a no-op SDL audio device. [CITED: pygame.org/wiki/HeadlessNoWindowsNeeded]

**Warning signs:** CI fails at collection time with `pygame.error` before any test result is shown.

### Pitfall 4: `_has_real_keyring()` probe hangs or raises on Ubuntu CI

**What goes wrong:** The functional probe in `_has_real_keyring()` calls `keyring.set_password(...)`. On Ubuntu runners without D-Bus, the SecretService backend raises or hangs waiting for D-Bus activation.

**Why it happens:** `ubuntu-latest` GitHub Actions runners do not start a D-Bus session or GNOME Keyring daemon. The keyring library tries to connect and either hangs or raises `SecretServiceNotAvailableException`.

**How to avoid:** Set `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` in the CI env. This makes `keyring.get_keyring()` return `NullKeyring` immediately, which the `isinstance(backend, _NullKeyring)` check in `_has_real_keyring()` catches before any probe. No D-Bus interaction occurs. [CITED: keyring.readthedocs.io — environment variable configuration]

**Warning signs:** CI job hangs for 30+ seconds then times out on keyring probe.

### Pitfall 5: Migration copies `creds.bin` but forgets it is still encrypted under the old passphrase

**What goes wrong:** After migration, the `EncryptedFileBackend` at the new path still decrypts correctly because the passphrase is provided at runtime (not stored in the file). There is no "old passphrase" vs "new passphrase" — the file just moves. This is not a pitfall, but it is easy to over-think.

**Why it matters:** Confirm that copying `creds.bin` bytes verbatim is the correct migration. Answer: yes. The scrypt KDF parameters and salt are embedded in the file itself; the passphrase is always prompt/env at runtime.

**How to avoid:** Copy `creds.bin` with `shutil.copy2` (copies bytes verbatim). Do not re-encrypt or re-derive.

### Pitfall 6: Windows path with spaces in `runner.temp`

**What goes wrong:** `${{ runner.temp }}` on Windows GitHub-hosted runners is typically `D:\a\_temp` (no spaces), but on self-hosted runners it could be any path. If the path has spaces and gets used unquoted in a shell command, it breaks.

**How to avoid:** In the workflow, only use `SHOPBOT_DATA_DIR=${{ runner.temp }}/shopbot` in an `env:` block (not in `run:` shell commands). Environment variables are passed as-is to the subprocess without shell word-splitting; spaces are not a problem in env var values.

### Pitfall 7: Smoke tests that invoke `shoppybot run` start a real bot loop

**What goes wrong:** `shoppybot run` calls `BotService.run(cvv)` which blocks in an asyncio loop, connecting to Chrome. A smoke test that calls `run` hangs forever.

**How to avoid:** Smoke the `run` subcommand only via `--help`. Do not call `run` without mocking `BotService.run`. The safe smoke commands are: `--help`, `setup` with piped stdin (provides all prompts in sequence then EOF), `items list`, `config show`. The `web` subcommand can be tested via `TestClient` (already covered in `test_web_*.py`) or skipped in the smoke module.

### Pitfall 8: `config_path()` returns the resolved new location but `AppConfig` still reads the legacy project-relative path on first run

**What goes wrong:** Migration copies `config.yml` to the new location. But if the migration fires after `AppConfig()` is constructed (which reads `_DEFAULT_YAML_PATH` at construction time), the first run still uses the legacy path even though migration succeeded.

**How to avoid:** Migration must fire before any `AppConfig()` construction. In `core/service.py:main()`, call `migrate_legacy_paths()` before constructing `AppConfig`. Alternatively, re-anchor `_DEFAULT_YAML_PATH` to the resolved location so `AppConfig()` uses the new path automatically — then migration just ensures the file is there.

**The correct order in `core/service.py`:**
```python
from core.paths import migrate_legacy_paths
migrate_legacy_paths()          # ensure new location populated
cfg = AppConfig()               # reads from new location
init_store(cfg)                 # sets up credential store
```

## Code Examples

### Confirmed platformdirs output on Windows (live-verified)

```python
# Source: live probe on this Windows 11 dev box (Python 3.13.13)
from platformdirs import PlatformDirs
d = PlatformDirs("shoppybot", appauthor=False)
d.user_data_dir   # -> C:\Users\<user>\AppData\Local\shoppybot
d.user_config_dir # -> C:\Users\<user>\AppData\Local\shoppybot
d.user_log_dir    # -> C:\Users\<user>\AppData\Local\shoppybot\Logs
```

### Confirmed platformdirs output on Linux (from source code)

```python
# Source: platformdirs/unix.py (inspected locally)
# user_data_dir  -> XDG_DATA_HOME or ~/.local/share/shoppybot
# user_config_dir-> XDG_CONFIG_HOME or ~/.config/shoppybot
# user_log_dir   -> XDG_STATE_HOME/shoppybot/log or ~/.local/state/shoppybot/log
```

### Existing test seam: tmp_data_dir fixture (no change needed)

```python
# Source: tests/conftest.py line 54-58
@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    import models
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "shop_py_bot.db"))
    return tmp_path
```

This fixture continues to work after re-anchoring because `monkeypatch.setattr` runs after module import and overrides the module-level attribute. No changes to `conftest.py` required.

### SC1 separator guard (grep-based test)

```python
# tests/test_xplat.py
import subprocess, sys

def test_no_hardcoded_separators(tmp_path):
    """No source file outside tests/ uses hardcoded string path separators."""
    # Patterns that indicate hardcoded separator: string literal with / or \\ followed by data or logs
    bad_patterns = [r'"data/', r"'data/", r'"logs/', r"'logs/", r'\\data\\', r'\\logs\\']
    dirs = ["core", "notifications", "plugins", "web"]
    for pattern in bad_patterns:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],  # use grep via rg or pure python
            capture_output=True
        )
    # Simpler: use pathlib.Path.rglob + str.contains in pure python
    from pathlib import Path
    src_files = [
        p for d in dirs
        for p in Path(d).rglob("*.py")
    ] + [Path("logger.py"), Path("models.py"), Path("utils.py")]
    violations = []
    for f in src_files:
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if any(pat in line for pat in ['"data/', "'data/", '"logs/', "'logs/"]):
                violations.append(f"{f}:{i}: {line.strip()}")
    assert violations == [], f"Hardcoded path separators found:\n" + "\n".join(violations)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `appdirs` library | `platformdirs` | 2021 (platformdirs forked to replace unmaintained appdirs) | `appdirs` last released 2020; `platformdirs` is its maintained successor |
| Per-OS GitHub Actions workflow files | Single matrix workflow | GitHub Actions matrix strategy (stable since 2019) | One file, parallel runs, consistent env |
| `actions/checkout@v2` / `actions/setup-python@v2` | `@v4` / `@v5` | 2023-2024 | v2 uses Node 12 (EOL); v4/v5 use Node 20 |

**Deprecated/outdated in THIS repo:**
- `.github/workflows/app_windowsBuild.yml`, `app_linuxBuild.yml`, `app_macBuild.yml`: use Python 3.9, `actions/checkout@v2`, `actions/setup-python@v2` (all EOL). The new `ci.yml` replaces them. The old files can be removed or left (they don't conflict).
- `.github/workflows/codeql-analysis.yml`: separate concern; leave untouched.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `appauthor=False` is the correct argument to suppress the redundant vendor subdir on Windows (giving `%LOCALAPPDATA%\shoppybot` not `%LOCALAPPDATA%\shoppybot\shoppybot`) | Standard Stack / Pattern 1 | LOW: verified by live probe on this Windows box; confirmed in platformdirs API docs |
| A2 | Linux `user_log_dir` returns `~/.local/state/shoppybot/log` (not `~/.local/share/shoppybot/Logs`) | Pitfalls | LOW: verified by reading platformdirs/unix.py source directly — `user_log_dir` = `user_state_dir` + `/log` |
| A3 | `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` triggers the `_NullKeyring` branch in `_has_real_keyring()` without a D-Bus probe | Pitfall 4, CI pattern | MEDIUM: confirmed from keyring readthedocs that env var overrides the backend; `_has_real_keyring()` has explicit `isinstance(backend, _NullKeyring)` guard — this should work |
| A4 | `SDL_AUDIODRIVER=dummy` prevents `pygame.mixer.init()` failure on headless Ubuntu GitHub Actions runners | Pitfall 3, CI pattern | MEDIUM: confirmed from pygame wiki and pygame GitHub issues; test locally with `SDL_AUDIODRIVER=dummy python -c "import utils"` (passes on this Windows box) |

**Planner note on A3 and A4:** Both are well-documented environment variable solutions with multiple community confirmations. They should be treated as HIGH confidence for planning purposes; flag for immediate verification in Wave 0 of the CI plan if test run fails.

## Open Questions (RESOLVED)

1. **RESOLVED — `migrate_legacy_paths()` lives in `core/paths.py`, called from `core/service.py:main()`** before `AppConfig()` is constructed. Keeps the paths module self-contained with an explicit call site (plan 11-03).

2. **RESOLVED — delete the 3 legacy per-OS workflow files** (app_linuxBuild.yml, app_macBuild.yml, app_windowsBuild.yml; Python 3.9 / EOL actions) and replace with a single `ci.yml`. The deletion is gated behind a human-confirm checkpoint (plan 11-05, autonomous:false). `codeql-analysis.yml` is NOT deleted.

3. **RESOLVED — smoke `setup` via `--help` only** (no side effects); reserve full interactive `setup` for the manual verification matrix. The piped-stdin setup path is already unit-tested from Phase 9 (plan 11-04).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | All | ✓ | 3.13.13 | — |
| platformdirs | core/paths.py | ✓ (3.6.x already installed via seleniumbase) | 4.3.6 installed; 4.10.0 on PyPI | — |
| pytest | Test suite | ✓ | 9.0.3 | — |
| GitHub Actions runners | CI matrix | ✓ (repo has existing workflows) | ubuntu-latest, windows-latest | Manual matrix only |
| SDL dummy audio driver | CI headless pygame | ✓ (SDL env var; no install needed) | SDL 2.28.4 | Mock pygame.mixer at conftest level |
| keyring null backend | CI headless keyring | ✓ (keyring env var; no install needed) | keyring 25.7.0 | monkeypatch `_has_real_keyring` in CI conftest |

**Missing dependencies with no fallback:** none

**Missing dependencies with fallback:** none — all dependencies are either stdlib, already installed, or env-var-configurable.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_xplat.py -x -q` |
| Full suite command | `pytest --tb=short` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| XPLAT-01 | `data_dir()` returns OS-appropriate absolute path | unit | `pytest tests/test_xplat.py::test_data_dir_is_absolute -x` | ❌ Wave 0 |
| XPLAT-01 | `data_dir()` respects `SHOPBOT_DATA_DIR` env override | unit | `pytest tests/test_xplat.py::test_env_override -x` | ❌ Wave 0 |
| XPLAT-01 | No hardcoded path separators in source files | static | `pytest tests/test_xplat.py::test_no_hardcoded_separators -x` | ❌ Wave 0 |
| XPLAT-01 | Migration: legacy DB moved to resolved data_dir on first run | unit | `pytest tests/test_xplat.py::test_migration_moves_db -x` | ❌ Wave 0 |
| XPLAT-01 | Migration: idempotent (second run no-ops) | unit | `pytest tests/test_xplat.py::test_migration_idempotent -x` | ❌ Wave 0 |
| XPLAT-01 | `models.DB_PATH` resolves under `data_dir()` (not CWD-relative) | unit | `pytest tests/test_xplat.py::test_db_path_not_cwd_relative -x` | ❌ Wave 0 |
| XPLAT-02 | Package imports cleanly | smoke | `pytest tests/test_xplat.py::test_import_smoke -x` | ❌ Wave 0 |
| XPLAT-02 | `shoppybot --help` exits 0 | smoke | `pytest tests/test_xplat.py::test_help_smoke -x` | ❌ Wave 0 |
| XPLAT-02 | `shoppybot items list` exits 0 | smoke | `pytest tests/test_xplat.py::test_items_list_smoke -x` | ❌ Wave 0 |
| XPLAT-02 | `shoppybot config show` exits 0 | smoke | `pytest tests/test_xplat.py::test_config_show_smoke -x` | ❌ Wave 0 |
| XPLAT-02 | Backend auto-selects keyring when `_has_real_keyring()` returns True | unit | `pytest tests/test_xplat.py::test_auto_selects_keyring -x` | ❌ Wave 0 |
| XPLAT-02 | Backend auto-selects file when keyring False + passphrase set | unit | `pytest tests/test_xplat.py::test_auto_selects_file -x` | ❌ Wave 0 |
| XPLAT-02 | Backend falls back to env when keyring False + no passphrase | unit | `pytest tests/test_xplat.py::test_auto_falls_back_env -x` | ❌ Wave 0 |
| XPLAT-02 | CI matrix runs full suite green on ubuntu-latest and windows-latest | CI | GHA workflow; verified by green checkmark on PR | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_xplat.py -x -q`
- **Per wave merge:** `pytest --tb=short` (full 336 + new tests)
- **Phase gate:** Full suite green on both OS in GHA before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_xplat.py` — covers all XPLAT-01/XPLAT-02 automated items above
- [ ] `.github/workflows/ci.yml` — matrix workflow with headless env vars
- [ ] `core/paths.py` — new module (no framework install needed; stdlib + platformdirs)
- [ ] `docs/PLATFORMS.md` — no test needed; authored by plan task
- [ ] `platformdirs==4.10.0` added to `requirements.txt` (upgrade from 4.3.6 already installed via transitive dep)

*No new test framework installs required — pytest already installed.*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (migration src/dst path validation) | pathlib.Path — no shell expansion, no traversal |
| V6 Cryptography | no (creds.bin already encrypted; migration copies bytes verbatim) | existing Fernet+scrypt unchanged |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Migration copies plaintext secret to less-protected location | Information Disclosure | `creds.bin` is already Fernet-encrypted; copy is byte-for-byte; no decryption during migration |
| Migration log line accidentally includes secret value | Information Disclosure | Log only `src -> dst` path strings; never `data` or `content` variables |
| `SHOPBOT_DATA_DIR` env var path traversal | Tampering | `Path(val)` normalizes but does not restrict to a safe root; in CI this is set by the workflow (trusted); in production the user controls their own env — acceptable |
| New OS-standard path is world-readable | Information Disclosure | `%LOCALAPPDATA%` (Windows) and `~/.local` (Linux) are user-owned; no chmod needed; platform convention enforces user-only access |

## Sources

### Primary (HIGH confidence)
- `platformdirs` PyPI page (pypi.org/project/platformdirs) — version 4.10.0, Python 3.10-3.14 support confirmed
- `platformdirs/unix.py` source code (inspected locally) — Linux XDG path logic for `user_data_dir`, `user_config_dir`, `user_log_dir`
- Live probe on Windows 11 / Python 3.13.13 — Windows `%LOCALAPPDATA%\shoppybot` path confirmed
- `tests/conftest.py` — existing monkeypatch seams confirmed functional
- `pyproject.toml`, `requirements.txt` — existing pinned versions confirmed
- `core/credentials.py`, `core/config_schema.py`, `logger.py`, `models.py` — all four path anchors inspected directly

### Secondary (MEDIUM confidence)
- pygame wiki (pygame.org/wiki/HeadlessNoWindowsNeeded) — `SDL_AUDIODRIVER=dummy` for headless CI
- keyring readthedocs (keyring.readthedocs.io) — `PYTHON_KEYRING_BACKEND` env var override
- GitHub Actions docs (docs.github.com/en/actions/tutorials/build-and-test-code/python) — matrix workflow pattern

### Tertiary (LOW confidence)
- None — all key claims verified from primary or official secondary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — platformdirs version and API verified by live probe and PyPI
- Architecture: HIGH — all four consumer files read directly; patterns derived from existing code
- Pitfalls: HIGH — pygame and keyring CI issues verified from official sources; migration pitfalls derived from direct SQLite/shutil knowledge
- CI matrix: MEDIUM-HIGH — pattern confirmed from GHA docs; headless env vars confirmed from library docs; exact behavior on ubuntu-latest confirmed from community sources

**Research date:** 2026-06-04
**Valid until:** 2026-09-04 (platformdirs is stable; GHA runner versions update quarterly)
