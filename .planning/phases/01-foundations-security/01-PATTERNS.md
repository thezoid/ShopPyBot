# Phase 1: Foundations + Security - Pattern Map

**Mapped:** 2026-06-01
**Files analyzed:** 10 new/modified files
**Analogs found:** 8 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `core/__init__.py` | config | — | `tests/__init__.py` | role-match (empty init) |
| `core/plugin_base.py` | model (interface) | — | `amazon_bot.py` (function set) | partial (no ABC exists yet) |
| `core/config_schema.py` | config | request-response | `config.py` | role-match |
| `logger.py` (patch) | utility | request-response | `logger.py` (self) | exact (modifying in place) |
| `main.py` (patch) | controller | request-response | `main.py` (self) | exact (modifying in place) |
| `sample.config.yml` (patch) | config | — | `sample.config.yml` (self) | exact (modifying in place) |
| `requirements.txt` (patch) | config | — | `requirements.txt` (self) | exact (modifying in place) |
| `pyproject.toml` | config | — | `.claude/worktrees/gallant-ritchie-fa629c/pyproject.toml` | exact |
| `tests/conftest.py` | test | — | `tests/test_models.py` (fixture pattern) | role-match |
| `tests/test_plugin_base.py` | test | — | `tests/test_models.py` | role-match |
| `tests/test_config_schema.py` | test | — | `tests/test_config.py` | exact |
| `tests/test_logger.py` | test | — | `tests/test_models.py` | role-match |

## Pattern Assignments

### `core/__init__.py` (config, empty marker)

**Analog:** `tests/__init__.py` (empty file)

This file is an empty package marker. No imports, no logic.

```python
# core/__init__.py
# (empty)
```

---

### `core/plugin_base.py` (model/interface, no data flow)

**No direct analog exists in codebase.** The closest approximation is the loose collection of functions in `amazon_bot.py` that defines the de-facto contract all retailer modules follow, plus `detect_captcha` which is currently a standalone function.

**Inferred interface from `amazon_bot.py` lines 10-17, 19-54, 56-122, 123-192:**

```python
# amazon_bot.py — existing ad-hoc "interface" (lines 10-17, 19-20, 56-57, 123-124)
def detect_captcha(driver):          # -> bool
def check_amazon_item(driver, item_url):   # -> bool
def amz_sign_in(driver, config):          # -> None (side effects only)
def auto_buy_amazon_item(driver, item_url, config, quantity, test_mode=False):  # -> None
```

**Error handling pattern in `amazon_bot.py`** (lines 50-54 and 190-192):

```python
except Exception as e:
    writeLog(f"Error checking Amazon item: {e}", "ERROR")
    return False
```

**Target pattern for `core/plugin_base.py`** (from RESEARCH.md Pattern 1):

```python
from abc import ABC, abstractmethod

PLUGIN_API_VERSION = 1   # module-level, before class — importable without instantiation

class RetailerPlugin(ABC):
    @abstractmethod
    def check_availability(self, url: str) -> bool: ...

    @abstractmethod
    def auto_buy(self, driver, url: str, config: dict) -> bool: ...

    def login(self, driver, config: dict) -> None:
        return None

    def detect_captcha(self, driver) -> bool:
        return False
```

**Key rules:**
- `PLUGIN_API_VERSION = 1` must be defined BEFORE the class body (Pitfall 3 in RESEARCH.md)
- Only `check_availability` and `auto_buy` are `@abstractmethod`
- `driver` parameter is intentionally untyped in Phase 1 (nodriver type import deferred to Phase 2)
- No imports beyond `abc` stdlib

---

### `core/config_schema.py` (config, request-response)

**Analog:** `config.py` (lines 1-6) — replaces this entirely

**Existing pattern to replace** (`config.py` lines 1-6):

```python
import yaml

def load_config():
    with open('config.yml', 'r') as file:
        return yaml.safe_load(file)

config = load_config()
```

**Problems with analog:** module-level call with no error handling, no validation, no env var support, CWD-relative path, credentials allowed in YAML.

**Imports pattern for new file** (from RESEARCH.md Pattern 2):

```python
from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)
import warnings
```

**Nested model pattern** — each config section is a `BaseModel`; `AppConfig` is the `BaseSettings` root:

```python
class DebugConfig(BaseModel):
    logging_level: int = 5
    test_mode: bool = True

class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="config.yml",
        extra="ignore",
        env_nested_delimiter="__",
    )
    debug: DebugConfig = DebugConfig()
```

**yaml_file path resolution** (Pitfall 2 in RESEARCH.md): Pass absolute path to avoid CWD sensitivity:

```python
# In settings_customise_sources, resolve relative to this file:
yaml_file=Path(__file__).parent.parent / "config.yml"
```

**Migration warning validator** — runs before pydantic strips extra keys:

```python
@model_validator(mode="before")
@classmethod
def warn_legacy_keys(cls, data: dict) -> dict:
    legacy = {"app": ["amz_email", "amz_pwd", "bb_email", "bb_password", "bb_cvv"]}
    for section, keys in legacy.items():
        if isinstance(data.get(section), dict):
            for key in keys:
                if key in data[section]:
                    warnings.warn(
                        f"config.yml: '{section}.{key}' is no longer used. "
                        f"Set credentials via environment variables. See .env.example.",
                        DeprecationWarning,
                        stacklevel=2,
                    )
    return data
```

**Source priority** (`env_settings` beats YAML):

```python
@classmethod
def settings_customise_sources(
    cls,
    settings_cls: type[BaseSettings],
    init_settings: PydanticBaseSettingsSource,
    env_settings: PydanticBaseSettingsSource,
    dotenv_settings: PydanticBaseSettingsSource,
    file_secret_settings: PydanticBaseSettingsSource,
) -> tuple[PydanticBaseSettingsSource, ...]:
    return (env_settings, YamlConfigSettingsSource(settings_cls))
```

---

### `logger.py` (patch — utility, request-response)

**Analog:** `logger.py` itself (modifying in place)

**Current broken pattern** (`logger.py` lines 7-9, 15-17):

```python
# Called on EVERY writeLog() invocation — opens, reads, parses config.yml each time
def load_settings():
    with open('config.yml', 'r') as file:
        return yaml.safe_load(file)

def writeLog(message: str, type: str, writeTofile: bool = True) -> None:
    settings = load_settings()              # FILE I/O ON EVERY CALL
    loggingLevel = settings.get('debug', {}).get('logging_level', 5)
```

**Fixed pattern** (RESEARCH.md Pattern 3): cache at module level, load once:

```python
def _load_logging_level() -> int:
    try:
        with open("config.yml", "r") as f:
            settings = yaml.safe_load(f)
        return settings.get("debug", {}).get("logging_level", 5)
    except (FileNotFoundError, KeyError):
        return 5

_LOGGING_LEVEL: int = _load_logging_level()   # module-level, runs once at import

def writeLog(message: str, type: str, writeTofile: bool = True) -> None:
    # replace: settings = load_settings(); loggingLevel = ...
    # with:    loggingLevel = _LOGGING_LEVEL
    ...
```

**Preservation rule:** Everything else in `writeLog` (lines 18-37 — color map, print, file write) stays unchanged. This is a surgical single-line substitution inside the function body.

---

### `main.py` (patch — controller, request-response)

**Analog:** `main.py` itself (three targeted patches)

**Patch 1 — SEC-03: remove `--disable-web-security`** (line 60):

```python
# REMOVE this line:
chromeOptions.add_argument("--disable-web-security")
```

**Patch 2 — INFRA-03: replace sys.stdout suppression** (lines 67-75):

```python
# REMOVE (lines 67-75):
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')
driver = webdriver.Chrome(service=service, options=chromeOptions)
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

# REPLACE WITH:
import subprocess
service = Service(driver_path, log_output=subprocess.DEVNULL)
driver = webdriver.Chrome(service=service, options=chromeOptions)
```

Note: `service = Service(driver_path)` is currently at line 46 before options are built. The Service instantiation must be moved to where `driver_path` is available AND after `import subprocess` is added at the top of file.

**Patch 3 — SEC-01/SEC-02: replace credential reads from config dict** (lines 83, 124):

```python
# REMOVE (line 83):
open_browser = config['app'].get('open_browser', False)
# (config['app'] section no longer exists in new schema — move to AppConfig)

# REMOVE (line 124):
auto_buy_bestbuy_item(driver, link, config['app']['bb_email'], config['app']['bb_password'], config['app']['bb_cvv'], quantity)
# REPLACE WITH: read from env vars directly via os.environ.get() for Phase 1
# (full credential flow via AppConfig.platforms is Phase 2+)
```

**Patch 4 — replace config import and add startup validation** (lines 38-44):

```python
# REMOVE:
from config import config
def load_config():
    with open('config.yml', 'r') as file:
        return yaml.safe_load(file)

# ADD at top of main():
from pydantic import ValidationError
from core.config_schema import AppConfig

try:
    config = AppConfig()
except ValidationError as e:
    print(f"Configuration error — fix config.yml:\n{e}")
    raise SystemExit(1)
```

**SEC-02 — CVV collection** (add to `main()` startup, after AppConfig):

```python
import getpass
import sys

def collect_cvv() -> str:
    try:
        cvv = getpass.getpass("Enter CVV (input hidden): ").strip()
    except getpass.GetPassWarning:
        print("WARNING: CVV echo suppression unavailable in this terminal", file=sys.stderr)
        raise SystemExit("Cannot collect CVV securely. Run in an interactive terminal.")
    if not cvv:
        raise SystemExit("CVV is required for auto-buy. Exiting.")
    return cvv
```

---

### `sample.config.yml` (patch — config)

**Analog:** `sample.config.yml` itself

**Remove the entire `app:` credential block** (lines 4-10 of current file):

```yaml
# REMOVE:
app:
  amz_email: "your_amazon_email@example.com"
  amz_pwd: "your_amazon_password"
  bb_email: "your_bestbuy_email@example.com"
  bb_password: "your_bestbuy_password"
  bb_cvv: "your_bestbuy_cvv"
  open_browser: false
```

**Add new `platforms:` section** in its place:

```yaml
# ADD — non-sensitive platform settings only:
platforms:
  amazon:
    delay_seconds: 30.0
    delay_jitter: 10.0
  bestbuy:
    delay_seconds: 30.0
    delay_jitter: 10.0
```

---

### `requirements.txt` (patch — config)

**Analog:** `requirements.txt` itself

**Current problems** (all 11 lines): no version pins, `selenium` and `pyyaml` duplicated, `webdriver_manager`/`webdriver-manager` both listed, no python_requires.

**Fixed pattern** — pin exact versions, remove duplicates, add new deps:

```
# python_requires >= 3.11
colorama==0.4.6
nodriver==0.50.3
pygame==2.6.1
pydantic-settings[yaml]==2.14.0
pytest==8.3.4
pytest-asyncio==1.3.0
pyyaml==6.0.2
requests==2.32.3
selenium==4.43.0
urllib3==2.3.0
webdriver-manager==4.0.2
```

Versions for `pyyaml`, `requests`, `urllib3`, `webdriver-manager` should be confirmed via `pip show` before finalizing — placeholders above use current stable values consistent with the installed environment.

---

### `pyproject.toml` (config)

**Analog:** `.claude/worktrees/gallant-ritchie-fa629c/pyproject.toml` (exact copy pattern)

**Copy this exactly** (verified working from the worktree):

```toml
[project]
name = "shoppybot"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

---

### `tests/conftest.py` (test, shared fixtures)

**Analog:** `tests/test_models.py` lines 6-18 (fixture + teardown pattern)

**Existing fixture pattern to copy** (`test_models.py` lines 6-18):

```python
@pytest.fixture(scope='module')
def setup_db():
    initialize_db(delete=True)
    items = [...]
    add_items(items)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
```

**New shared fixtures needed in `conftest.py`:**

```python
import os
import pytest
import yaml

@pytest.fixture
def tmp_config_yml(tmp_path):
    """Write a minimal valid config.yml to tmp_path and return its Path."""
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

@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect models.DB_PATH to a temp directory so tests don't need data/."""
    import models
    db_path = tmp_path / "shop_py_bot.db"
    monkeypatch.setattr(models, "DB_PATH", str(db_path))
    return tmp_path
```

---

### `tests/test_plugin_base.py` (test, unit)

**Analog:** `tests/test_models.py` (overall structure) and `tests/test_config.py` (fixture injection pattern)

**Import pattern from `test_config.py`** (lines 1-4):

```python
import pytest
from config import load_config
```

**Adapted for plugin base** — test structure to follow:

```python
import pytest
from core.plugin_base import RetailerPlugin, PLUGIN_API_VERSION


def test_version_constant():
    assert PLUGIN_API_VERSION == 1


def test_incomplete_plugin_raises():
    class Incomplete(RetailerPlugin):
        pass
    with pytest.raises(TypeError):
        Incomplete()


def test_abstract_methods_enforced():
    # Both check_availability and auto_buy must be implemented
    class MissingBuy(RetailerPlugin):
        def check_availability(self, url): return True
    with pytest.raises(TypeError):
        MissingBuy()


def test_login_noop():
    class Minimal(RetailerPlugin):
        def check_availability(self, url): return True
        def auto_buy(self, driver, url, config): return False
    p = Minimal()
    assert p.login(None, {}) is None


def test_detect_captcha_noop():
    class Minimal(RetailerPlugin):
        def check_availability(self, url): return True
        def auto_buy(self, driver, url, config): return False
    p = Minimal()
    assert p.detect_captcha(None) is False
```

---

### `tests/test_config_schema.py` (test, unit)

**Analog:** `tests/test_config.py` (exact structure — `tmp_path` fixture, YAML write, load call)

**Existing pattern from `test_config.py`** (lines 5-37):

```python
@pytest.fixture
def sample_config(tmp_path):
    config_content = """..."""
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content)
    return config_file

def test_load_config(sample_config):
    config = load_config(sample_config)
    assert config['app']['amz_email'] == "..."
```

**Adapted for AppConfig** — same `tmp_path` + YAML write pattern, different assertions:

```python
import pytest
import warnings
import yaml
from pydantic import ValidationError
from core.config_schema import AppConfig


@pytest.fixture
def valid_config_yml(tmp_path):
    cfg = {
        "debug": {"logging_level": 3, "test_mode": True},
        "available": {"timeout": 10, "items": []},
        "platforms": {"amazon": {"delay_seconds": 30.0}},
    }
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    return f


def test_valid_yaml_loads(valid_config_yml):
    config = AppConfig(_yaml_file=valid_config_yml)   # or however path is injected
    assert config.debug.logging_level == 3


def test_missing_field_error(tmp_path):
    # items entry missing required 'name'
    cfg = {"available": {"items": [{"link": "https://example.com", "auto_buy": True}]}}
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    with pytest.raises(ValidationError) as exc_info:
        AppConfig(_yaml_file=f)
    assert "name" in str(exc_info.value)


def test_platform_section_loads(valid_config_yml):
    config = AppConfig(_yaml_file=valid_config_yml)
    assert config.platforms.amazon.delay_seconds == 30.0


def test_legacy_key_warning(tmp_path):
    cfg = {"app": {"amz_email": "old@example.com"}, "available": {"items": []}}
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        AppConfig(_yaml_file=f)
    assert any("amz_email" in str(w.message) for w in caught)
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_env_var_override(valid_config_yml, monkeypatch):
    monkeypatch.setenv("DEBUG__LOGGING_LEVEL", "1")
    config = AppConfig(_yaml_file=valid_config_yml)
    assert config.debug.logging_level == 1
```

**Note:** The exact mechanism for injecting `yaml_file` path in tests (constructor kwarg vs class-level override) depends on the implementation decision in `core/config_schema.py`. The RESEARCH.md recommendation is to accept `yaml_file: Path = Path("config.yml")` as a default, which maps to `_yaml_file=` in pydantic-settings init kwargs or a subclass override. Planner should resolve this in the implementation task for `core/config_schema.py` before writing `test_config_schema.py`.

---

### `tests/test_logger.py` (test, unit)

**Analog:** `tests/test_models.py` (fixture pattern), `logger.py` (subject under test)

**Pattern to verify** — `_LOGGING_LEVEL` is loaded exactly once, not per `writeLog` call:

```python
import pytest
from unittest.mock import patch, mock_open
import yaml


def test_no_config_reread(tmp_path, monkeypatch):
    """_load_logging_level must be called once at import, not on every writeLog call."""
    cfg_content = yaml.dump({"debug": {"logging_level": 2}})
    config_file = tmp_path / "config.yml"
    config_file.write_text(cfg_content)

    open_call_count = []
    original_open = open

    def counting_open(path, *args, **kwargs):
        if "config.yml" in str(path):
            open_call_count.append(1)
        return original_open(path, *args, **kwargs)

    import importlib
    import logger as logger_module

    with patch("builtins.open", side_effect=counting_open):
        # Multiple writeLog calls should NOT re-read config.yml
        logger_module.writeLog("msg1", "INFO", writeTofile=False)
        logger_module.writeLog("msg2", "INFO", writeTofile=False)
        logger_module.writeLog("msg3", "INFO", writeTofile=False)

    # After module is already loaded, zero additional config reads expected
    assert len(open_call_count) == 0, (
        f"writeLog re-read config.yml {len(open_call_count)} time(s); expected 0"
    )
```

**Note:** This test validates behavior AFTER the module is loaded. Testing the module-level load itself requires `importlib.reload(logger)` with a patched `open` — that variant is more complex and can be a follow-up test. The core INFRA-02 requirement is satisfied by verifying zero re-reads during `writeLog` calls on an already-loaded module.

---

## Shared Patterns

### Error handling (try/except with writeLog)

**Source:** `amazon_bot.py` lines 50-54

**Apply to:** Any new utility functions in `core/`, any patched functions in `main.py`

```python
except Exception as e:
    writeLog(f"Error <doing X>: {e}", "ERROR")
    return False   # or return None, or raise, depending on context
```

**Rule:** Never swallow exceptions silently. Always pass the exception message to `writeLog` at "ERROR" level. Return a typed sentinel (`False`/`None`) rather than letting the exception propagate uncaught inside the polling loop.

### Module-level singleton initialization

**Source:** `config.py` lines 4-6 (pattern to preserve, content to replace)

```python
# Pattern: module-level initialization, cached as a module-global
config = load_config()   # existing
_LOGGING_LEVEL = _load_logging_level()   # new logger.py pattern
```

**Apply to:** `logger.py` (`_LOGGING_LEVEL`), `core/config_schema.py` (the `AppConfig()` call in `main.py` at startup, not at import time in the module itself)

### Test fixture: tmp_path + yaml.dump

**Source:** `tests/test_config.py` lines 5-32

**Apply to:** `tests/test_config_schema.py`, `tests/conftest.py`

```python
@pytest.fixture
def sample_config(tmp_path):
    config_content = """..."""   # or yaml.dump({...})
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content)
    return config_file
```

### Test fixture: module-scoped db with teardown

**Source:** `tests/test_models.py` lines 6-18

**Apply to:** `tests/conftest.py` (promote to shared fixture)

```python
@pytest.fixture(scope='module')
def setup_db():
    initialize_db(delete=True)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `core/plugin_base.py` | model (ABC interface) | — | No ABC or interface pattern exists in codebase; existing code uses standalone functions |
| `.env.example` | config (documentation) | — | No env var documentation file exists; content is pure documentation |

## Metadata

**Analog search scope:** `E:\repos\ShopPyBot\` root — `main.py`, `logger.py`, `config.py`, `models.py`, `amazon_bot.py`, `tests/test_models.py`, `tests/test_config.py`, `tests/test_utils.py`, `requirements.txt`, `sample.config.yml`, `.claude/worktrees/gallant-ritchie-fa629c/pyproject.toml`

**Files scanned:** 11

**Pattern extraction date:** 2026-06-01
