# Phase 11: Cross-Platform Verification - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 11 new/modified files
**Analogs found:** 10 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `core/paths.py` | utility | transform | `core/credentials.py` lines 40, 140-173 | role-match |
| `models.py` (modify line 5) | model | CRUD | self (re-anchor only) | exact |
| `core/config_schema.py` (modify line 17) | config | transform | self (re-anchor only) | exact |
| `core/credentials.py` (modify line 40) | service | request-response | self (re-anchor only) | exact |
| `logger.py` (modify lines 41-45) | utility | transform | self (re-anchor only) | exact |
| `core/service.py` (modify `main()`) | service | request-response | `core/service.py` lines 153-181 | exact |
| `requirements.txt` (add platformdirs pin) | config | — | `requirements.txt` existing pins | exact |
| `.github/workflows/ci.yml` | config | batch | `.github/workflows/app_windowsBuild.yml` | role-match |
| `tests/test_paths.py` / `tests/test_xplat.py` | test | CRUD + transform | `tests/test_credentials.py` | exact |
| `tests/conftest.py` (extend `tmp_data_dir`) | test | transform | `tests/conftest.py` lines 53-58 | exact |
| `docs/PLATFORMS.md` | docs | — | none | no analog |

## Pattern Assignments

### `core/paths.py` (utility, transform)

**Analog:** `core/credentials.py` (module-level singleton + function accessor pattern)

**Imports pattern** (`core/credentials.py` lines 15-35):
```python
from __future__ import annotations

import os
from pathlib import Path
```

**Module-level singleton with lazy function accessors** (`core/credentials.py` lines 39-40, design):
```python
# credentials.py uses Path(__file__).parent.parent as the anchor.
# paths.py replaces that with PlatformDirs — same singleton-at-import, function-accessed pattern.
_DEFAULT_STORE_PATH: Path = Path(__file__).parent.parent / "data" / "creds.bin"
```

The `paths.py` module follows the same shape: one module-level object (`_DIRS`) constructed at import, three public functions that read it on every call so env-override works:

```python
# core/paths.py — full implementation shape from RESEARCH.md Pattern 1
from __future__ import annotations
import os
from pathlib import Path
from platformdirs import PlatformDirs

_APP_NAME = "shoppybot"
_DIRS = PlatformDirs(_APP_NAME, appauthor=False)


def _env_override() -> Path | None:
    val = os.environ.get("SHOPBOT_DATA_DIR", "").strip()
    return Path(val) if val else None


def data_dir() -> Path:
    return _env_override() or Path(_DIRS.user_data_dir)


def config_path() -> Path:
    return data_dir() / "config.yml"


def log_dir() -> Path:
    override = _env_override()
    if override:
        return override / "logs"
    return Path(_DIRS.user_log_dir)
```

**Migration function** (place in `core/paths.py`, called from `core/service.py`):
```python
def migrate_legacy_paths() -> None:
    """Move project-relative legacy data to OS-standard locations (idempotent)."""
    import shutil
    from logger import writeLog

    _REPO_ROOT = Path(__file__).parent.parent

    _migrations = [
        (_REPO_ROOT / "data" / "shop_py_bot.db", data_dir() / "shop_py_bot.db"),
        (_REPO_ROOT / "data" / "creds.bin",       data_dir() / "creds.bin"),
        (_REPO_ROOT / "config.yml",               config_path()),
    ]
    for src, dst in _migrations:
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            src.unlink()
            writeLog(f"Migrated {src} -> {dst}", "INFO")

    legacy_logs = _REPO_ROOT / "logs"
    new_logs = log_dir()
    if legacy_logs.is_dir() and not new_logs.exists():
        shutil.copytree(str(legacy_logs), str(new_logs))
        shutil.rmtree(str(legacy_logs))
        writeLog(f"Migrated logs {legacy_logs} -> {new_logs}", "INFO")
```

**Key constraints:** File must stay under 30 lines for the function bodies (CLAUDE.md). `migrate_legacy_paths` can be in `core/paths.py` or split to a sibling if it pushes past 30 lines per function. No module-level side effects beyond `_DIRS` construction (no mkdir, no migration at import).

---

### `models.py` — re-anchor `DB_PATH` (model, CRUD)

**Analog:** self (existing file, single-line change)

**Current pattern** (`models.py` line 5):
```python
DB_PATH = os.path.join('data', 'shop_py_bot.db')
```

**Target pattern:**
```python
from core.paths import data_dir as _paths_data_dir
DB_PATH = str(_paths_data_dir() / "shop_py_bot.db")
```

**Test seam preserved** (`tests/conftest.py` lines 53-58):
```python
@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect models.DB_PATH to a temp directory so tests don't need data/."""
    import models
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "shop_py_bot.db"))
    return tmp_path
```

`monkeypatch.setattr` runs after module import and overrides the module-level `DB_PATH` attribute — this seam continues to work unchanged after re-anchoring.

**`initialize_db` makedirs call** (`models.py` line 34):
```python
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
```
No change required: `os.path.dirname` of an absolute path returns the correct parent. Verify with `test_models.py::test_add_items` after re-anchoring.

---

### `core/config_schema.py` — re-anchor `_DEFAULT_YAML_PATH` (config, transform)

**Analog:** self (existing file, single-line change)

**Current pattern** (`core/config_schema.py` line 17):
```python
_DEFAULT_YAML_PATH: Path = Path(__file__).parent.parent / "config.yml"
```

**Target pattern:**
```python
from core.paths import config_path as _paths_config_path
_DEFAULT_YAML_PATH: Path = _paths_config_path()
```

**`yaml_file=` test injection seam** (`core/config_schema.py` lines 233-236):
```python
def __init__(self, yaml_file: Path | str | None = None, **values):
    _yaml_path_local.active = Path(yaml_file) if yaml_file is not None else _DEFAULT_YAML_PATH
    super().__init__(**values)
```

Passing `yaml_file=tmp_config_yml` in tests bypasses `_DEFAULT_YAML_PATH` entirely — all existing tests using `tmp_config_yml` remain green without modification.

---

### `core/credentials.py` — re-anchor `_DEFAULT_STORE_PATH` (service, request-response)

**Analog:** self (existing file, single-line change)

**Current pattern** (`core/credentials.py` line 40):
```python
_DEFAULT_STORE_PATH: Path = Path(__file__).parent.parent / "data" / "creds.bin"
```

**Target pattern:**
```python
from core.paths import data_dir as _paths_data_dir
_DEFAULT_STORE_PATH: Path = _paths_data_dir() / "creds.bin"
```

**`data_dir` config override still wins** (`core/credentials.py` lines 343-347):
```python
store_path = (
    Path(cfg.credentials.data_dir) / "creds.bin"
    if getattr(cfg.credentials, "data_dir", "")
    else _DEFAULT_STORE_PATH
)
```

The config override path takes precedence over `_DEFAULT_STORE_PATH` — this remains unchanged.

**`_has_real_keyring` pattern** (`core/credentials.py` lines 140-173) — this is the backend-selection guard that `test_xplat.py` must monkeypatch:
```python
def _has_real_keyring() -> bool:
    backend = keyring.get_keyring()
    if isinstance(backend, _keyring_fail.Keyring):
        return False
    try:
        from keyring.backends.null import Keyring as _NullKeyring
        if isinstance(backend, _NullKeyring):
            return False
    except ImportError:
        pass
    # functional probe ...
    ok = False
    try:
        keyring.set_password("shopbot-probe", "__probe__", "1")
        ok = keyring.get_password("shopbot-probe", "__probe__") == "1"
    except Exception:
        return False
    finally:
        try:
            keyring.delete_password("shopbot-probe", "__probe__")
        except Exception:
            pass
    return ok
```

---

### `logger.py` — re-anchor log dir (utility, transform)

**Analog:** self (existing file, 4-line change)

**Current pattern** (`logger.py` lines 41-45):
```python
_scriptdir = os.path.dirname(os.path.realpath(__file__))
log_dir = os.path.join(_scriptdir, "logs")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file_path = os.path.join(log_dir, f"{datetime.now().strftime('%Y%B%d')}.log")
```

**Target pattern:**
```python
from core.paths import log_dir as _paths_log_dir
_log_dir = _paths_log_dir()
_log_dir.mkdir(parents=True, exist_ok=True)
log_file_path = _log_dir / f"{datetime.now().strftime('%Y%B%d')}.log"
```

Note: the `from core.paths import log_dir` import must be inside `writeLog()` (or at module top) rather than at the call site to avoid circular import if `core/paths.py` imports from `logger`. Since `migrate_legacy_paths` in `core/paths.py` imports `writeLog` from `logger`, `logger.py` must NOT import from `core.paths` at module level — use a lazy import inside `writeLog` instead:

```python
def writeLog(message: str, type: str, writeTofile: bool = True) -> None:
    ...
    if writeTofile:
        from core.paths import log_dir as _paths_log_dir   # lazy: avoids circular import
        _log_dir = _paths_log_dir()
        _log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = _log_dir / f"{datetime.now().strftime('%Y%B%d')}.log"
        with open(log_file_path, "a", encoding="utf-8") as logFile:
            logFile.write(...)
```

---

### `core/service.py` — call migration at startup (service, request-response)

**Analog:** self (`core/service.py` lines 153-181)

**Current `main()` pattern** (`core/service.py` lines 153-181):
```python
def main(argv=None) -> None:
    import sys as _sys
    from core.cli import build_parser
    from core.cli.run import handle_run
    from core.cli.setup import handle_setup

    parser = build_parser()
    args, _ = parser.parse_known_args(argv)
    ...
    _sys.exit(args.func(args, BotService()) or 0)
```

**Target: add migration call before `BotService()` construction** — insert before the first `BotService()` call (or at the top of `main()`):
```python
def main(argv=None) -> None:
    import sys as _sys
    from core.paths import migrate_legacy_paths
    from core.cli import build_parser
    from core.cli.run import handle_run
    from core.cli.setup import handle_setup

    migrate_legacy_paths()   # idempotent; runs before any DB/store/log access

    parser = build_parser()
    args, _ = parser.parse_known_args(argv)
    ...
```

**Ordering rule** (from RESEARCH.md Pitfall 8): `migrate_legacy_paths()` must fire before `AppConfig()` is constructed (AppConfig reads `_DEFAULT_YAML_PATH` at construction time). Since `BotService.__init__` calls `AppConfig()` when none is passed, migration must precede the first `BotService()` call in `main()`.

---

### `requirements.txt` — add `platformdirs` pin (config)

**Analog:** `requirements.txt` existing line pattern (one package per line, `==` exact pin)

**Current pin format** (`requirements.txt` lines 1-15):
```
colorama==0.4.6
cryptography==44.0.2
keyring==25.7.0
```

**Target: add one line** (alphabetical order, between `pyyaml` and `requests` or at end):
```
platformdirs==4.10.0
```

Note: `platformdirs` 4.3.6 is already transitively installed. Pin to 4.10.0 (latest stable, verified on PyPI 2026-06-04).

---

### `.github/workflows/ci.yml` (config, batch)

**Analog:** `.github/workflows/app_windowsBuild.yml` + `.github/workflows/app_linuxBuild.yml`

**Existing per-OS workflow shape** (`.github/workflows/app_windowsBuild.yml` lines 1-31):
```yaml
name: ShopPyBot Windows
on:
  push:
    branches: [master, dev]
  pull_request:
    branches: [master, dev]
jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python 3.9
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Test with pytest
        run: |
          pytest
```

**Target matrix workflow shape** (replace the three legacy files):
```yaml
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
      SDL_AUDIODRIVER: dummy
      SDL_VIDEODRIVER: dummy
      PYTHON_KEYRING_BACKEND: keyring.backends.null.Keyring
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

**Key upgrades from analog:**
- `actions/checkout@v2` -> `@v4`, `actions/setup-python@v2` -> `@v5` (Node 20, not EOL Node 12)
- Python 3.9 -> 3.13 (matches dev environment)
- `pip install -r requirements.txt` -> `pip install -e .[web]` (installs as editable package with web extras)
- Per-OS separate jobs -> single matrix job (DRY)
- `env:` block with four headless CI guards (SDL dummy, null keyring, temp data dir)

---

### `tests/test_paths.py` / `tests/test_xplat.py` (test, transform + CRUD)

**Analog:** `tests/test_credentials.py` (path-injection pattern + monkeypatch pattern)

**Import/fixture pattern** (`tests/test_credentials.py` lines 1-15):
```python
import os
from pathlib import Path
import pytest


def test_env_backend_get(monkeypatch):
    from core.credentials import EnvVarBackend
    monkeypatch.setenv("AMZ_EMAIL", "test@example.com")
    backend = EnvVarBackend()
    assert backend.get("AMZ_EMAIL") == "test@example.com"
```

**Module-under-test import pattern** (`tests/test_credentials.py` lines 80-87):
```python
def test_get_store_lazy_fallback(reset_credential_store):
    import core.credentials as creds
    from core.credentials import EnvVarBackend, get_store
    creds._store = None
    store = get_store()
    assert isinstance(store, EnvVarBackend)
```

**Backend-selection monkeypatch pattern** (from RESEARCH.md Pattern 4):
```python
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

**Path-override via env var pattern** (for `test_data_dir_is_absolute`, `test_env_override`):
```python
def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path / "override"))
    # Must re-import or call function after env set -- functions re-read env on every call
    from core.paths import data_dir
    assert data_dir() == tmp_path / "override"


def test_data_dir_is_absolute(monkeypatch):
    monkeypatch.delenv("SHOPBOT_DATA_DIR", raising=False)
    from core.paths import data_dir
    assert data_dir().is_absolute()
```

**Migration idempotency test pattern** (modeled on `tests/test_models.py` setup_db fixture):
```python
def test_migration_moves_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path / "new"))
    # Create a fake legacy DB in a fake repo root
    legacy = tmp_path / "data" / "shop_py_bot.db"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"fake-db")
    # Patch _REPO_ROOT inside migrate_legacy_paths to point at tmp_path
    import core.paths
    monkeypatch.setattr(core.paths, "_REPO_ROOT_OVERRIDE", tmp_path)
    core.paths.migrate_legacy_paths()
    assert (tmp_path / "new" / "shop_py_bot.db").exists()
    assert not legacy.exists()

def test_migration_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path / "new"))
    legacy = tmp_path / "data" / "shop_py_bot.db"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"fake-db")
    import core.paths
    monkeypatch.setattr(core.paths, "_REPO_ROOT_OVERRIDE", tmp_path)
    core.paths.migrate_legacy_paths()
    core.paths.migrate_legacy_paths()   # second call is no-op
    assert (tmp_path / "new" / "shop_py_bot.db").exists()
```

Note: the `_REPO_ROOT_OVERRIDE` approach requires `migrate_legacy_paths` to check for it:
```python
_REPO_ROOT_OVERRIDE: Path | None = None  # monkeypatched in tests

def _repo_root() -> Path:
    if _REPO_ROOT_OVERRIDE is not None:
        return _REPO_ROOT_OVERRIDE
    return Path(__file__).parent.parent
```

**SC1 separator guard test:**
```python
def test_no_hardcoded_separators():
    """No source file in core/, models.py, logger.py uses bare string path separators."""
    from pathlib import Path
    src_files = list(Path("core").rglob("*.py")) + [
        Path("logger.py"), Path("models.py"), Path("utils.py"),
    ]
    bad_patterns = ['"data/', "'data/", '"logs/', "'logs/"]
    violations = []
    for f in src_files:
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if any(pat in line for pat in bad_patterns):
                violations.append(f"{f}:{i}: {line.strip()}")
    assert violations == [], "Hardcoded path separators:\n" + "\n".join(violations)
```

**Smoke test pattern** (CLI invocation via subprocess, analogous to no existing test):
```python
import subprocess, sys

def test_help_smoke():
    result = subprocess.run(
        [sys.executable, "-m", "core.service", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0

def test_items_list_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))
    result = subprocess.run(
        [sys.executable, "-c",
         "from core.service import main; main(['items', 'list'])"],
        capture_output=True, text=True, env={**__import__("os").environ},
    )
    assert result.returncode == 0
```

---

### `tests/conftest.py` — extend `tmp_data_dir` (test)

**Analog:** self (`tests/conftest.py` lines 53-58)

**Current fixture** (`tests/conftest.py` lines 53-58):
```python
@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect models.DB_PATH to a temp directory so tests don't need data/."""
    import models
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "shop_py_bot.db"))
    return tmp_path
```

**Target: also set `SHOPBOT_DATA_DIR` so `core/paths.data_dir()` agrees:**
```python
@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect models.DB_PATH and SHOPBOT_DATA_DIR to a temp directory."""
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))
    import models
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "shop_py_bot.db"))
    return tmp_path
```

This keeps the existing seam (`monkeypatch.setattr(models, "DB_PATH", ...)`) intact while also redirecting `core/paths.data_dir()` consistently. All 335 existing tests that use `tmp_data_dir` continue to pass unchanged.

---

## Shared Patterns

### Path construction: always `pathlib.Path /` operator

**Source:** `core/config_schema.py` line 17, `core/credentials.py` line 40
**Apply to:** All new code in `core/paths.py`, consumer re-anchors in models.py / credentials.py / config_schema.py / logger.py

```python
# Correct: pathlib operator, OS-independent
path = data_dir() / "shop_py_bot.db"

# Banned: string join, hardcoded separator
path = os.path.join('data', 'shop_py_bot.db')   # CWD-relative AND hardcoded
path = str(_dir) + "/logs"                       # hardcoded separator
```

### Module-level constant + function accessor for monkeypatch seam

**Source:** `core/credentials.py` lines 39-40, `core/config_schema.py` line 17
**Apply to:** `core/paths.py` (all three accessors), all four re-anchored module-level constants

```python
# Pattern: function reads env on every call; module-level constant assigned at import
# Consumer module:
from core.paths import data_dir as _paths_data_dir
DB_PATH = str(_paths_data_dir() / "shop_py_bot.db")   # assigned once at import

# Test: monkeypatch the consumer constant directly (already works in conftest.py)
monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "shop_py_bot.db"))
```

### Lazy import to break circular dependency

**Source:** `core/credentials.py` `TYPE_CHECKING` guard (line 34-35)
**Apply to:** `logger.py` import of `core.paths.log_dir`

```python
# credentials.py uses TYPE_CHECKING to avoid circular import:
if TYPE_CHECKING:
    from core.config_schema import AppConfig

# logger.py must use lazy import inside writeLog() because core/paths.py imports writeLog:
def writeLog(...):
    ...
    if writeTofile:
        from core.paths import log_dir as _paths_log_dir   # lazy, inside function
```

### Logging safety: paths only, never values

**Source:** `core/credentials.py` lines 383-385, 395-413
**Apply to:** `core/paths.py` `migrate_legacy_paths()`

```python
# credentials.py logs the backend label, never a secret value:
def _log_backend(label: str) -> None:
    writeLog(f"CredentialStore: {label} backend active", "INFO")

# Migration must log only src/dst paths, never file content:
writeLog(f"Migrated {src} -> {dst}", "INFO")   # correct
# writeLog(f"creds content: {dst.read_bytes()}", "INFO")  -- NEVER
```

### `reset_credential_store` fixture for singleton isolation

**Source:** `tests/conftest.py` lines 270-281
**Apply to:** All `test_xplat.py` tests that call `_build_store` or `init_store`

```python
@pytest.fixture(autouse=False)
def reset_credential_store():
    from core import credentials
    original = credentials._store
    yield
    credentials._store = original
```

### `tmp_config_yml` fixture for yaml_file injection

**Source:** `tests/conftest.py` lines 37-50
**Apply to:** All `test_xplat.py` tests that construct `AppConfig`

```python
@pytest.fixture
def tmp_config_yml(tmp_path):
    cfg = {
        "debug": {"logging_level": 3, "test_mode": True},
        "available": {"timeout": 10, "items": []},
        "platforms": {
            "amazon": {"delay_seconds": 30.0},
            "bestbuy": {"delay_seconds": 30.0},
        },
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(cfg))
    return config_file
```

### GitHub Actions env block for headless CI

**Source:** RESEARCH.md Pattern 5 (no existing analog in repo)
**Apply to:** `.github/workflows/ci.yml`

```yaml
env:
  SDL_AUDIODRIVER: dummy          # prevents pygame.mixer.init() failure (no audio device)
  SDL_VIDEODRIVER: dummy          # prevents pygame display init failure
  PYTHON_KEYRING_BACKEND: keyring.backends.null.Keyring  # disables D-Bus probe
  SHOPBOT_DATA_DIR: ${{ runner.temp }}/shopbot            # redirects all path resolution
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `docs/PLATFORMS.md` | docs | — | No existing docs/ markdown files in the repo; pure authored content, no code pattern needed |

## Metadata

**Analog search scope:** `core/`, `tests/`, `models.py`, `logger.py`, `.github/workflows/`
**Files scanned:** 10 source files + 4 workflow files
**Pattern extraction date:** 2026-06-04
