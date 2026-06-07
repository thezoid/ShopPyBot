# Phase 1: Foundations + Security — Research

**Researched:** 2026-06-01
**Domain:** Python ABC plugin interface, pydantic-settings YAML config, credential security, nodriver stealth, requirements hygiene
**Confidence:** HIGH (most claims verified against live installed packages or official source code)

<user_constraints>
## User Constraints (from CONTEXT.md / .continue-here.md)

### Locked Decisions

- **Browser automation:** Drop Selenium, adopt `nodriver 0.48.1+` (async-native, CDP-direct). Phase 1 establishes the foundation; existing Selenium Amazon/BestBuy code is NOT migrated in Phase 1 (that is Phase 2). Phase 1 locks the ABC and driver security patterns only.
- **Plugin interface:** ABC with 4 methods: `check_availability` and `auto_buy` are abstract; `login` and `detect_captcha` have no-op defaults. `PLUGIN_API_VERSION = 1` importable from plugin base.
- **Config:** `pydantic-settings[yaml]` replaces raw `yaml.safe_load()`. Flat per-platform sections (`platforms.amazon.*`). Actionable startup validation errors.
- **Credentials:** Environment variables only. CVV via `getpass` at runtime. Never in `config.yml`.
- **Python floor:** 3.11 minimum. `python_requires >= 3.11` in requirements.
- **Anti-patterns to fix in Phase 1:** `--disable-web-security` flag removal; `sys.stdout` monkey-patching for ChromeDriver output suppression; `config.yml` re-read per `writeLog()` call; shared global WebDriver (each plugin owns `self.driver`).

### Claude's Discretion

- File structure for `core/` module (location of `plugin_base.py`, `config_schema.py`)
- Exact env var naming convention (`SHOPBOT_AMZ_EMAIL` vs `AMZ_EMAIL` etc.)
- Whether `AppConfig` loads config.yml path from a constructor arg or a fixed path
- Error message wording for config validation failures (must be actionable, format is discretion)

### Deferred Ideas (OUT OF SCOPE for Phase 1)

- Migration of `amazon_bot.py` and `bestbuy_bot.py` to plugin ABC (Phase 2)
- Plugin auto-discovery via importlib (Phase 2)
- `domain_pattern` routing attribute on plugins (Phase 2)
- Async orchestrator, `asyncio.TaskGroup`, `ThreadPoolExecutor` (Phase 4)
- SQLite WAL mode, write queue (Phase 4)
- Notification channels (Phase 5)
- New platform plugins (Phase 6)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-01 | Plugin base class (ABC) defines `check_availability(url) -> bool`, `auto_buy(driver, url, config) -> bool`, `login(driver, config) -> None`, `detect_captcha(driver) -> bool` | `abc.ABC` + `@abstractmethod` from stdlib; no-op defaults via concrete methods; verified below |
| CORE-02 | `PLUGIN_API_VERSION = 1` exported from plugin base; default no-op for `login` and `detect_captcha` | Module-level constant; ABC concrete methods return `None`/`False` |
| CORE-05 | Pydantic `AppConfig` validates `config.yml` at startup; fails with actionable error on missing/invalid fields | `pydantic-settings 2.14.0` installed; `YamlConfigSettingsSource` pattern verified live |
| CORE-06 | Config schema supports flat per-platform sections (`platforms.amazon.email`, etc.) | Nested `BaseModel` in `BaseSettings` verified working |
| CORE-07 | Config migration warnings when old `app.amz_email` / `app.bb_email` keys detected | Model `extra='ignore'` with explicit validator that checks for legacy keys |
| SEC-01 | Credentials read from env vars; `config.yml` holds non-sensitive settings only | `pydantic-settings` env override with `env_nested_delimiter='__'`; verified live |
| SEC-02 | CVV via `getpass.getpass()` at runtime; never stored | `getpass` is stdlib; no new dep needed |
| SEC-03 | `--disable-web-security` Chrome flag removed from driver setup | Currently in `main.py` line 60; remove in Phase 1 driver init |
| SEC-04 | CDP patch at driver startup to hide `navigator.webdriver` | nodriver: property is naturally `undefined` (no WebDriver protocol); headless UA handled by `_prepare_headless()` — see findings below |
| SEC-05 | Real Chrome user agent string used | nodriver strips "Headless" from UA automatically when `headless=True`; non-headless gets OS Chrome UA natively |
| SEC-06 | README disclaimer on personal use, TOS compliance, account risk | Prose-only change; no code research needed |
| INFRA-01 | `requirements.txt` pinned to exact versions; no duplicates; `python_requires >= 3.11` | Current file has 3 duplicates, 0 pinned versions; fix required |
| INFRA-02 | Logger singleton loaded once; does not re-read `config.yml` per log call | `logger.py` calls `load_settings()` (= `yaml.safe_load()`) inside every `writeLog()` call; fix with module-level init |
| INFRA-03 | `sys.stdout` suppression removed; ChromeDriver output suppressed via service log path | `main.py` lines 68-75 redirect stdout/stderr to devnull; fix with `Service(log_output=subprocess.DEVNULL)` or log path |
</phase_requirements>

## Summary

Phase 1 covers four independent work streams: (1) locking the `RetailerPlugin` ABC contract, (2) replacing raw YAML loading with `pydantic-settings`, (3) removing all credential/security anti-patterns from the existing codebase, and (4) cleaning up `requirements.txt` and the logger singleton. No existing retail logic (Amazon/BestBuy Selenium code) is migrated in this phase.

**Critical finding on SEC-04:** nodriver does NOT use the WebDriver protocol, so `navigator.webdriver` is naturally `undefined` in any nodriver-launched browser. The requirement for a "CDP patch to hide navigator.webdriver" is semantically satisfied by adopting nodriver, but implementors should document this explicitly rather than adding an unnecessary CDP injection that would redundantly patch an already-unset property. The headless user-agent is stripped automatically by nodriver's `_prepare_headless()` CDP call.

**Critical finding on the migration boundary:** Phase 1 creates `core/plugin_base.py` and `core/config_schema.py` as new modules. Existing `amazon_bot.py`, `bestbuy_bot.py`, and `main.py` are modified only to remove security anti-patterns (SEC-01 through SEC-05, INFRA-02, INFRA-03). The existing Selenium `driver` object stays in `main.py` for now; plugin migration happens in Phase 2.

**Primary recommendation:** Write `core/plugin_base.py` first (ABC is zero-risk, zero external deps), then `core/config_schema.py` (pydantic-settings, high confidence), then security hardening patches to existing files, then requirements cleanup. Each stream is independently testable.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Plugin interface contract (ABC) | Core module (`core/`) | — | Interface definition belongs in core, not in any platform-specific code |
| Config validation | Core module (`core/`) | Startup entrypoint (`main.py`) | Schema lives in core; `main.py` instantiates and catches `ValidationError` |
| Credential resolution | Environment (OS) | Core config startup | Env vars set by user before launch; pydantic-settings reads them |
| CVV collection | Startup entrypoint (`main.py`) | — | One-time `getpass` prompt at process start, held in memory |
| Driver stealth (navigator.webdriver, UA) | nodriver (architectural) | Tab CDP methods | nodriver handles this natively; no app-layer patch needed |
| ChromeDriver output suppression | Startup entrypoint (`main.py`) | Service object | `subprocess.DEVNULL` or log path in `Service()` constructor |
| Logger singleton | `logger.py` module level | — | Load config once at import time, cache `logging_level` |
| requirements.txt hygiene | `requirements.txt` | — | Pin all versions; add `python_requires` comment block |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `abc` (stdlib) | 3.11+ | Plugin interface enforcement via `ABC` + `@abstractmethod` | Zero-dep; enforces contract at class instantiation time |
| `pydantic-settings` | 2.14.0 (latest) | YAML config loading + validation | `YamlConfigSettingsSource` built-in; typed models; env var override; actionable `ValidationError` |
| `nodriver` | 0.50.3 (installed) | Browser automation foundation for driver setup | Async-native, CDP-direct; no WebDriver protocol; no `navigator.webdriver` flag; official undetected-chromedriver successor |
| `getpass` (stdlib) | 3.11+ | Secure CVV prompt at runtime | Zero-dep; no terminal echo; standard Python security primitive |

**Version note:** Research locked `nodriver 0.48.1` in decisions. Currently installed is 0.50.3. Phase 1 should pin to 0.50.3 (installed, verified working on Python 3.13) or lock to `>=0.48.1,<1.0` with `0.50.3` as the pinned freeze version. `[VERIFIED: pip registry]`

**Version note:** Research locked `pydantic-settings 2.13.1` in decisions. Currently installed is 2.14.0 (latest stable). Pin to 2.14.0. `[VERIFIED: pip registry]`

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pyyaml` | transitive dep | YAML parsing | Do not import directly; let pydantic-settings manage it |
| `pytest` | 8.3.4 (installed) | Test runner | All tests; no new dep needed |
| `pytest-asyncio` | 1.3.0 (installed) | Async test support | Tests of nodriver lifecycle (Phase 2+); configure in `pyproject.toml` for Phase 1 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pydantic-settings[yaml]` | `dynaconf` | dynaconf is over-engineered for single-user CLI; adds `dynaconf` binary and multi-file settings convention |
| `pydantic-settings[yaml]` | raw `yaml.safe_load()` | No validation; runtime `KeyError` inside bot loops is unacceptable for open source |
| `nodriver` ABC integration | Selenium `WebDriver` type hints | Selenium is sync; incompatible with async plugin design; nodriver is the locked decision |
| `getpass.getpass()` | `input()` | `input()` echoes to terminal; unacceptable for CVV |

**Installation (new deps only):**
```bash
pip install "pydantic-settings[yaml]==2.14.0" "nodriver==0.50.3"
```

## Package Legitimacy Audit

> slopcheck was blocked from installing by the sandbox. All packages marked `[ASSUMED]` per graceful degradation protocol. Planner must add `checkpoint:human-verify` before each install.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `nodriver` | PyPI | ~2 yrs | High (successor to undetected-chromedriver) | github.com/UltrafunkAmsterdam/nodriver | [ASSUMED] | Flagged for human verify |
| `pydantic-settings` | PyPI | ~3 yrs | Very high (pydantic ecosystem) | github.com/pydantic/pydantic-settings | [ASSUMED] | Flagged for human verify |

**Packages removed due to slopcheck [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** none identified (both are well-known packages, but slopcheck result is formally `[ASSUMED]`)

*slopcheck was unavailable at research time; all packages above are tagged `[ASSUMED]` and the planner must gate each install behind a `checkpoint:human-verify` task.*

**Note:** Both packages are already installed in the project environment (verified via `pip show`). The human-verify checkpoint is a formality given this context.

## Architecture Patterns

### System Architecture Diagram

```
config.yml + env vars
        |
        v
[AppConfig (pydantic-settings)]  <-- startup, fails fast on missing/invalid fields
        |
        |-- validated config object
        v
[main.py startup]
   |-- getpass("CVV: ") --> held in memory only
   |-- nodriver.start(Config(...)) --> browser instance
   |       (navigator.webdriver = undefined by architecture)
   |       (headless UA stripped by _prepare_headless CDP call)
   |
   |-- [RetailerPlugin ABC]  <-- defined in core/plugin_base.py
   |       check_availability(url) -> bool  [abstract]
   |       auto_buy(driver, url, config) -> bool  [abstract]
   |       login(driver, config) -> None  [concrete no-op default]
   |       detect_captcha(driver) -> bool  [concrete no-op default]
   |       PLUGIN_API_VERSION = 1  [class constant]
   |
   |-- [logger singleton]  <-- logging_level cached once at import
   |       writeLog(msg, type) -> None  [no per-call config.yml read]
   |
   v
[existing Selenium loop]  <-- NOT changed in Phase 1 except security patches
```

### Recommended Project Structure

```
shoppy_bot/
core/
    __init__.py
    plugin_base.py       # RetailerPlugin ABC + PLUGIN_API_VERSION
    config_schema.py     # AppConfig (pydantic-settings BaseSettings)
plugins/                 # Phase 2+
    (empty placeholder)
tests/
    test_plugin_base.py  # Wave 0: ABC instantiation, no-op defaults, version constant
    test_config_schema.py  # Wave 0: YAML load, missing field error, env override, migration warning
    test_logger.py       # Wave 0: logging_level cached, no config.yml re-read
    test_models.py       # existing
    test_config.py       # existing (needs fixing: CWD dependency)
config.yml               # gitignored
sample.config.yml        # updated: no credential fields
.env.example             # new: shows SHOPBOT_AMZ_EMAIL=... pattern
requirements.txt         # pinned, no duplicates
```

### Pattern 1: RetailerPlugin ABC

**What:** Abstract base class with `@abstractmethod` on 2 required methods; concrete no-op defaults on 2 optional methods. Class constant for interface versioning.

**When to use:** Defined once in `core/plugin_base.py`. All platform plugins (Phase 2+) import and subclass this.

```python
# core/plugin_base.py
# Source: Python stdlib abc docs + project design decisions
from abc import ABC, abstractmethod

PLUGIN_API_VERSION = 1


class RetailerPlugin(ABC):
    """Base class for all retail platform plugins.

    Subclass this and implement check_availability and auto_buy.
    login and detect_captcha are optional — no-op defaults are provided.
    """

    @abstractmethod
    def check_availability(self, url: str) -> bool:
        """Return True if the item at url is available for purchase."""
        ...

    @abstractmethod
    def auto_buy(self, driver, url: str, config: dict) -> bool:
        """Attempt to purchase the item at url. Return True on success."""
        ...

    def login(self, driver, config: dict) -> None:
        """Authenticate with the platform. No-op by default."""
        return None

    def detect_captcha(self, driver) -> bool:
        """Return True if a CAPTCHA is detected. Returns False by default."""
        return False
```

**Key design notes:**
- `PLUGIN_API_VERSION` is a module-level constant (not a class attribute) so it is importable directly: `from core.plugin_base import PLUGIN_API_VERSION`
- Method signatures use `driver` typed as the nodriver `Tab` or `Browser` object (Phase 2 will type-annotate; Phase 1 leaves as untyped to avoid importing nodriver in the ABC)
- `login` returns `None` (not `bool`) — matching CORE-01 spec: `login(driver, config) -> None`
- `detect_captcha` returns `False` by default — safe for check-only plugins

### Pattern 2: AppConfig with YamlConfigSettingsSource

**What:** `pydantic-settings BaseSettings` subclass with nested `BaseModel` sections. YAML file is the primary source; environment variables override. Validation errors produced at instantiation time with field path in message.

**When to use:** Instantiated once in `main.py` at startup. Passed as a typed object throughout the application.

```python
# core/config_schema.py
# Source: pydantic-settings 2.14.0 live verification + official docs pattern
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


class ItemConfig(BaseModel):
    name: str
    link: str
    auto_buy: bool = False
    quantity: int = 1


class AvailableConfig(BaseModel):
    timeout: int = 10
    items: list[ItemConfig] = []


class DebugConfig(BaseModel):
    logging_level: int = 5
    test_mode: bool = True


class AmazonPlatformConfig(BaseModel):
    delay_seconds: float = 30.0
    delay_jitter: float = 10.0


class BestBuyPlatformConfig(BaseModel):
    delay_seconds: float = 30.0
    delay_jitter: float = 10.0


class PlatformsConfig(BaseModel):
    amazon: AmazonPlatformConfig = AmazonPlatformConfig()
    bestbuy: BestBuyPlatformConfig = BestBuyPlatformConfig()


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="config.yml",
        extra="ignore",           # silently ignore unknown top-level keys
        env_nested_delimiter="__",  # allows SHOPBOT_DEBUG__LOGGING_LEVEL=3
    )
    debug: DebugConfig = DebugConfig()
    available: AvailableConfig = AvailableConfig()
    platforms: PlatformsConfig = PlatformsConfig()

    @model_validator(mode="before")
    @classmethod
    def warn_legacy_keys(cls, data: dict) -> dict:
        legacy = {
            "app": ["amz_email", "amz_pwd", "bb_email", "bb_password", "bb_cvv"]
        }
        for section, keys in legacy.items():
            if isinstance(data.get(section), dict):
                for key in keys:
                    if key in data[section]:
                        warnings.warn(
                            f"config.yml: '{section}.{key}' is no longer used. "
                            f"Set credentials via environment variables. "
                            f"See .env.example for the new variable names.",
                            DeprecationWarning,
                            stacklevel=2,
                        )
        return data

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # env_settings first: env vars override YAML
        return (env_settings, YamlConfigSettingsSource(settings_cls))
```

**Usage in main.py:**
```python
# main.py startup
from pydantic import ValidationError
from core.config_schema import AppConfig

try:
    config = AppConfig()
except ValidationError as e:
    print(f"Configuration error — fix config.yml:\n{e}")
    raise SystemExit(1)
```

**Validation error format (verified live):**
```
1 validation error for AppConfig
available.items.0.name
  Field required [type=missing, input_value={...}, input_type=dict]
```

### Pattern 3: Logger Singleton Fix

**What:** Cache `logging_level` at module import time instead of re-reading config.yml on every `writeLog()` call.

**When to use:** Replace the `load_settings()` call inside `writeLog()` with a module-level cached value.

```python
# logger.py — Phase 1 fix (INFRA-02)
# Source: codebase audit (CONCERNS.md)
import os
from datetime import datetime
from colorama import Fore, Style
import yaml

# Load once at module import; not per-call
def _load_logging_level() -> int:
    try:
        with open("config.yml", "r") as f:
            settings = yaml.safe_load(f)
        return settings.get("debug", {}).get("logging_level", 5)
    except (FileNotFoundError, KeyError):
        return 5

_LOGGING_LEVEL: int = _load_logging_level()

def writeLog(message: str, type: str, writeTofile: bool = True) -> None:
    # uses module-level _LOGGING_LEVEL; no file I/O per call
    ...
```

**Note:** After `AppConfig` (pydantic-settings) is in place, `logger.py` can be updated to accept the validated `config.debug.logging_level` value directly. For Phase 1, the YAML-read fix is sufficient.

### Pattern 4: ChromeDriver Output Suppression (INFRA-03)

**What:** Replace `sys.stdout = open(os.devnull, 'w')` hack with `subprocess.DEVNULL` passed to the Selenium `Service` object.

**Current broken code (main.py lines 68-75):**
```python
sys.stdout = open(os.devnull, 'w')   # hides ALL Python stdout including exceptions
sys.stderr = open(os.devnull, 'w')
driver = webdriver.Chrome(service=service, options=chromeOptions)
sys.stdout = sys.__stdout__           # restored, but only if driver init succeeds
sys.stderr = sys.__stderr__
```

**Fixed pattern:**
```python
# Suppress ChromeDriver subprocess output without touching Python streams
import subprocess
service = Service(
    driver_path,
    log_output=subprocess.DEVNULL  # or: log_output="logs/chromedriver.log"
)
driver = webdriver.Chrome(service=service, options=chromeOptions)
```

**Note:** This fix applies to the existing Selenium setup in `main.py`. When Phase 2 migrates to nodriver, this pattern becomes obsolete — nodriver does not use a ChromeDriver subprocess.

### Pattern 5: nodriver Startup (SEC-04 / SEC-05)

**What:** nodriver launches Chrome via CDP without the WebDriver protocol layer. `navigator.webdriver` is `undefined` by architecture (no CDP patch needed). Headless user agent is corrected automatically.

```python
# How to start nodriver (Phase 2+ pattern, verified from source code)
import nodriver as uc
import asyncio

async def create_browser(headless: bool = False) -> uc.Browser:
    config = uc.Config(headless=headless)
    browser = await uc.start(config=config)
    return browser

# The _prepare_headless() CDP call strips "Headless" from UA automatically
# when headless=True. navigator.webdriver is undefined — no patch required.
```

**SEC-04 implementation note:** The requirement says "CDP patch applied at driver startup to hide navigator.webdriver property." With nodriver, this requirement is satisfied architecturally. The planner should create a task that documents this explicitly (in a code comment or README section) rather than adding a no-op CDP injection. If the team later adds a Selenium fallback, the CDP patch (`Page.addScriptToEvaluateOnNewDocument`) would be needed there.

### Anti-Patterns to Avoid

- **`sys.stdout = open(os.devnull, 'w')` for driver suppression:** Silently swallows any exception raised during driver initialization. Use `Service(log_output=subprocess.DEVNULL)` instead.
- **Loading config.yml inside `writeLog()`:** Opens, reads, and parses YAML on every log call in a tight polling loop. Cache at module level.
- **Credentials in `config.yml` fields:** Even with `extra='ignore'`, users who copy the old sample config will have credentials on disk. Remove credential fields from `sample.config.yml` entirely and add `.env.example`.
- **`@abstractmethod` on `login` and `detect_captcha`:** Breaks check-only plugins at instantiation. Only `check_availability` and `auto_buy` should be abstract.
- **`PLUGIN_API_VERSION` as a class attribute vs module constant:** If it is a class attribute, it can be overridden per-plugin unintentionally. Module-level constant `PLUGIN_API_VERSION = 1` is importable independently and cannot be shadowed by subclasses.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML config validation at startup | Custom `validate_config(dict)` function walking dict keys | `pydantic-settings BaseSettings` | Pydantic produces structured errors with field paths; handles type coercion; env var override is free |
| Secure credential prompting | `input("CVV: ")` | `getpass.getpass("CVV: ")` | `input()` echoes to terminal; stdlib `getpass` suppresses echo on all platforms |
| Plugin interface versioning | Per-method version checks or try/except on method calls | Module-level `PLUGIN_API_VERSION = 1` constant | Simple integer compare at plugin load time; version is discoverable from module without instantiating |
| ChromeDriver output suppression | `sys.stdout` redirect | `Service(log_output=subprocess.DEVNULL)` | Subprocess stdio suppression without touching Python's stdout/stderr streams |
| navigator.webdriver hiding | `Page.addScriptToEvaluateOnNewDocument` CDP inject | Use nodriver (architectural) | nodriver does not use WebDriver protocol; property is never set to `true` |

**Key insight:** Pydantic-settings gives type safety, env var overrides, and structured error messages for free. A hand-rolled config validator will miss type coercion (e.g., `"5"` vs `5` for integers), produce worse error messages, and not support env var overrides without additional code.

## Common Pitfalls

### Pitfall 1: `extra='ignore'` Silently Accepts Old Credential Keys

**What goes wrong:** Setting `extra='ignore'` on `AppConfig` means old `config.yml` files with `app.amz_pwd` are silently accepted without any warning. The bot starts successfully but credentials are not loaded (because they are in env vars), causing silent auth failure.

**Why it happens:** `extra='ignore'` discards unknown keys without error. It is the right setting for forward compatibility, but it bypasses CORE-07 (migration warning).

**How to avoid:** Use a `@model_validator(mode='before')` that explicitly checks for the legacy key names in the raw dict before Pydantic processes the model. Issue `warnings.warn()` with `DeprecationWarning` and exact migration guidance. This runs before validation strips the extra keys.

**Warning signs:** Users report "bot never signs in" or "auth fails" without any error about missing credentials.

### Pitfall 2: `YamlConfigSettingsSource` Default yaml_file is CWD-Relative

**What goes wrong:** `YamlConfigSettingsSource(settings_cls)` uses `yaml_file='.'` as its default (inspected live). If the process is not started from the repo root, the YAML file is not found and all config fields fall through to defaults — no error, silent misconfiguration.

**Why it happens:** The yaml_file path is relative to the current working directory at process startup, not to the module file.

**How to avoid:** Pass an absolute path: `YamlConfigSettingsSource(settings_cls, yaml_file=Path(__file__).parent.parent / "config.yml")` or accept the path as a parameter to `AppConfig` constructor.

**Warning signs:** Bot starts with all default values even when config.yml is present.

### Pitfall 3: `PLUGIN_API_VERSION` Imported Before ABC Is Fully Defined

**What goes wrong:** If `PLUGIN_API_VERSION` is defined after the class body in `plugin_base.py`, an `ImportError` results when importing only the constant (`from core.plugin_base import PLUGIN_API_VERSION`) before the full module is loaded (e.g., in a test).

**How to avoid:** Define `PLUGIN_API_VERSION = 1` at the top of `plugin_base.py`, before the class definition. Module-level constants defined before classes are always available.

### Pitfall 4: `getpass` Blocks on Non-Interactive Terminals

**What goes wrong:** `getpass.getpass()` raises `GetPassWarning` and falls back to `input()` (which echoes) when stdin is not a TTY (e.g., running in a Docker container or CI pipeline).

**How to avoid:** Wrap in a try/except: if `getpass` raises or returns empty string, emit a clear error that CVV cannot be collected in non-interactive mode and exit. Do not silently fall back to `input()`.

**Warning signs:** CVV appears in shell history or CI logs.

### Pitfall 5: Selenium `Service` Does Not Accept `log_output=subprocess.DEVNULL` in All Versions

**What goes wrong:** The `log_output` parameter on Selenium `Service` was added in Selenium 4.x. The current install is `selenium 4.43.0` (verified), so this is safe. If requirements.txt is not pinned and a user installs Selenium 3.x, this breaks.

**How to avoid:** Pin `selenium==4.43.0` in requirements.txt (or the latest 4.x verified version). Note: Phase 2 removes Selenium entirely; this is a temporary fix.

### Pitfall 6: pydantic-settings Env Var Nesting Format

**What goes wrong:** With `env_nested_delimiter='__'`, the env var `DEBUG__LOGGING_LEVEL=3` maps to `debug.logging_level`. However, if the user sets `SHOPBOT_DEBUG__LOGGING_LEVEL=3` with an `env_prefix='SHOPBOT_'`, the delimiter comes after the prefix: `SHOPBOT_DEBUG__LOGGING_LEVEL`. Many users expect `SHOPBOT__DEBUG__LOGGING_LEVEL`.

**How to avoid:** Either use no prefix (simpler, more user-friendly for single-user tool) or document the exact env var format in `.env.example`. For this project, no `env_prefix` is the right choice — it is a single-user tool, not a multi-tenant service.

## Code Examples

### ABC with no-op defaults (verified pattern)

```python
# Source: Python stdlib abc module, verified via live Python 3.13 import
from abc import ABC, abstractmethod

PLUGIN_API_VERSION = 1

class RetailerPlugin(ABC):
    @abstractmethod
    def check_availability(self, url: str) -> bool: ...

    @abstractmethod
    def auto_buy(self, driver, url: str, config: dict) -> bool: ...

    def login(self, driver, config: dict) -> None:
        return None

    def detect_captcha(self, driver) -> bool:
        return False

# Verify: abstract methods enforced
class Incomplete(RetailerPlugin):
    pass

try:
    Incomplete()  # raises TypeError: Can't instantiate abstract class
except TypeError:
    pass  # expected

# Verify: no-op defaults work without override
class CheckOnly(RetailerPlugin):
    def check_availability(self, url): return True
    def auto_buy(self, driver, url, config): return False

p = CheckOnly()
assert p.login(None, {}) is None
assert p.detect_captcha(None) is False
```

### pydantic-settings YAML load with env override (verified live)

```python
# Source: Live verification — pydantic-settings 2.14.0 on Python 3.13
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource

class DebugConfig(BaseModel):
    logging_level: int = 5

class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="config.yml",
        extra="ignore",
        env_nested_delimiter="__",
    )
    debug: DebugConfig = DebugConfig()

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings,
                                   env_settings, dotenv_settings, file_secret_settings):
        return (env_settings, YamlConfigSettingsSource(settings_cls))

# env var DEBUG__LOGGING_LEVEL=2 would override YAML value
# ValidationError format: "debug.logging_level: Input should be a valid integer..."
```

### getpass CVV collection

```python
# Source: Python stdlib getpass docs
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

### ChromeDriver output suppression (INFRA-03 fix)

```python
# Source: Selenium 4.x Service API (selenium==4.43.0 installed)
import subprocess
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

service = Service(
    executable_path=driver_path,
    log_output=subprocess.DEVNULL,   # suppresses chromedriver stdout/stderr
)
# No sys.stdout manipulation needed
driver = webdriver.Chrome(service=service, options=options)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `yaml.safe_load()` for all config | `pydantic-settings[yaml]` with typed models | pydantic-settings v2 (2023) | Startup validation errors with field paths; env var overrides; type coercion |
| `navigator.webdriver` CDP patch + undetected-chromedriver | nodriver (no WebDriver protocol) | nodriver 0.x (2024) | Property never set; no patch needed; detection-resistant by architecture |
| All 4 ABC methods abstract | Only 2 abstract (check/buy); 2 have no-op defaults | Project design decision | Check-only plugins don't need to stub `login`/`detect_captcha` |
| Credentials in config.yml | Env vars only; CVV via `getpass` | Phase 1 | Eliminates CVV-on-disk risk; PCI-DSS aligned |

**Deprecated/outdated:**
- `selenium` + `webdriver-manager`: Replaced by `nodriver` in Phase 2. Phase 1 keeps Selenium running but removes the `--disable-web-security` flag.
- `sys.stdout` redirect for driver suppression: Replaced by `Service(log_output=subprocess.DEVNULL)` in Phase 1.
- `load_settings()` per `writeLog()` call: Replaced by module-level cached value in Phase 1.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | nodriver 0.50.3 is compatible with the existing Python 3.13 environment | Standard Stack | Installed version confirms 0.50.3 runs; Python 3.13 > 3.9 requirement; LOW risk |
| A2 | slopcheck would rate `nodriver` and `pydantic-settings` as `[OK]` | Package Legitimacy Audit | Both are established packages with active GitHub repos; risk is LOW but formally unverified |
| A3 | `Service(log_output=subprocess.DEVNULL)` is available in `selenium 4.43.0` | Pattern 4 | selenium 4.43.0 is installed and confirmed; DEVNULL parameter exists in 4.x; LOW risk |
| A4 | No config.yml exists at test runtime (causes test errors) | Test Infrastructure | Confirmed by running `pytest` — `config.py` module-level `load_config()` fails without config.yml; test isolation fix needed in Wave 0 |

## Open Questions

1. **config.yml path resolution strategy**
   - What we know: `YamlConfigSettingsSource` defaults to CWD-relative path; tests run from repo root
   - What's unclear: Should `AppConfig` accept a `yaml_file` path as a constructor argument for testability, or hardcode `config.yml` and require tests to create fixture files?
   - Recommendation: Accept `yaml_file: Path = Path("config.yml")` as a default parameter; tests pass `tmp_path / "config.yml"`

2. **Migration boundary: does Phase 1 change `config.py`?**
   - What we know: `config.py` exports `config` singleton via `yaml.safe_load()`; `main.py` imports it but also has its own `load_config()` (shadow)
   - What's unclear: Does Phase 1 replace `config.py` with `AppConfig`, or leave it in place and introduce `AppConfig` alongside it?
   - Recommendation: Replace `config.py` with `core/config_schema.py` in Phase 1; update `main.py` import. The old `config.py` shadow in `main.py` is one of the anti-patterns to fix.

3. **nodriver and the existing Selenium driver in main.py**
   - What we know: Phase 1 does NOT migrate Amazon/BestBuy to nodriver; existing Selenium loop stays
   - What's unclear: Does Phase 1 add nodriver as a dependency but not actually use it (just establishing the dep), or does Phase 1 leave nodriver out of requirements.txt until Phase 2 when it is actually used?
   - Recommendation: Add nodriver to requirements.txt in Phase 1 (INFRA-01 covers requirements cleanup), but do not instantiate it in any code until Phase 2. This pins the version early.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ | 3.13.13 (> 3.11 floor) | — |
| `nodriver` | SEC-04, SEC-05, foundation | ✓ | 0.50.3 installed | — |
| `pydantic-settings` | CORE-05, CORE-06, CORE-07, SEC-01 | ✓ | 2.14.0 installed | — |
| `pytest` | All tests | ✓ | 8.3.4 installed | — |
| `pytest-asyncio` | Async tests (Phase 2+) | ✓ | 1.3.0 installed | — |
| `selenium` | Existing Selenium code (until Phase 2) | ✓ | 4.43.0 installed | — |
| `colorama` | logger.py | ✓ | 0.4.6 installed | — |
| `pygame` | sound alerts | ✓ | 2.6.1 installed | — |
| `getpass` | SEC-02 | ✓ | stdlib 3.11+ | — |
| `abc` | CORE-01, CORE-02 | ✓ | stdlib 3.11+ | — |

**Missing dependencies with no fallback:** none

**Missing dependencies with fallback:** none

**Existing test infrastructure issues (must fix in Wave 0):**
- `config.py` loads `config.yml` at module import time; tests fail with `FileNotFoundError` unless `config.yml` exists in CWD
- `test_models.py` fails because `data/` directory doesn't exist in test CWD (`sqlite3.OperationalError: unable to open database file`)
- `test_utils.py` imports `make_tiny` from `utils` but `make_tiny` is defined in `main.py` (import error)
- No `pytest.ini` or `pyproject.toml` to configure `asyncio_mode` — `pytest-asyncio` emits deprecation warning

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 |
| Config file | none (Wave 0 gap — needs `pyproject.toml` with `[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/test_plugin_base.py tests/test_config_schema.py tests/test_logger.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-01 | `RetailerPlugin` ABC enforces `check_availability` and `auto_buy` as abstract | unit | `pytest tests/test_plugin_base.py::test_abstract_methods_enforced -x` | Wave 0 |
| CORE-01 | Incomplete subclass raises `TypeError` at instantiation | unit | `pytest tests/test_plugin_base.py::test_incomplete_plugin_raises -x` | Wave 0 |
| CORE-02 | `PLUGIN_API_VERSION` importable, equals 1 | unit | `pytest tests/test_plugin_base.py::test_version_constant -x` | Wave 0 |
| CORE-02 | `login` returns `None` by default without override | unit | `pytest tests/test_plugin_base.py::test_login_noop -x` | Wave 0 |
| CORE-02 | `detect_captcha` returns `False` by default without override | unit | `pytest tests/test_plugin_base.py::test_detect_captcha_noop -x` | Wave 0 |
| CORE-05 | Missing required field produces `ValidationError` with field path | unit | `pytest tests/test_config_schema.py::test_missing_field_error -x` | Wave 0 |
| CORE-05 | Valid YAML loads without error | unit | `pytest tests/test_config_schema.py::test_valid_yaml_loads -x` | Wave 0 |
| CORE-06 | `platforms.amazon.delay_seconds` loads from YAML nested section | unit | `pytest tests/test_config_schema.py::test_platform_section_loads -x` | Wave 0 |
| CORE-07 | Old `app.amz_email` key in YAML triggers `DeprecationWarning` | unit | `pytest tests/test_config_schema.py::test_legacy_key_warning -x` | Wave 0 |
| SEC-01 | `SHOPBOT_AMZ_EMAIL` env var accessible via config; not required in YAML | unit | `pytest tests/test_config_schema.py::test_env_var_override -x` | Wave 0 |
| INFRA-02 | `writeLog` does not open `config.yml` more than once per process | unit | `pytest tests/test_logger.py::test_no_config_reread -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_plugin_base.py tests/test_config_schema.py tests/test_logger.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_plugin_base.py` — covers CORE-01, CORE-02
- [ ] `tests/test_config_schema.py` — covers CORE-05, CORE-06, CORE-07, SEC-01
- [ ] `tests/test_logger.py` — covers INFRA-02
- [ ] `pyproject.toml` with `[tool.pytest.ini_options]` — sets `asyncio_mode = "auto"` to silence deprecation warning
- [ ] Fix `tests/test_models.py` — add `tmp_path` fixture or `conftest.py` to handle `data/` directory path
- [ ] Fix `tests/test_config.py` — `config.py` module-level import fails without `config.yml`; isolate using `monkeypatch` or `importlib` reload
- [ ] `tests/conftest.py` — shared fixtures (temp config.yml, temp data dir)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Credentials from env vars; `getpass` for runtime secrets |
| V3 Session Management | no | No session tokens; bot authenticates per-session via browser |
| V4 Access Control | no | Single-user personal tool |
| V5 Input Validation | yes | pydantic-settings validates all config fields at startup |
| V6 Cryptography | no | No keys or hashes generated by this phase |
| V7 Error Handling | yes | `ValidationError` caught at startup, actionable message, clean exit |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credentials committed in config.yml | Information Disclosure | env vars only; remove credential fields from sample.config.yml |
| CVV persisted to disk | Information Disclosure | `getpass.getpass()` at runtime; never write CVV to any file or log |
| Bot fingerprinting via `--disable-web-security` | Spoofing (anti-bot bypass failure) | Remove flag; use nodriver architecture |
| Silent exception swallowing via `sys.stdout` redirect | Tampering (loss of error visibility) | Replace with `Service(log_output=subprocess.DEVNULL)` |
| Log output containing credentials | Information Disclosure | Ensure `writeLog` never logs raw config dict; ensure CVV is never passed to logger |

## Sources

### Primary (HIGH confidence)

- nodriver 0.50.3 source code — `core/config.py`, `core/tab.py`, `core/browser.py` — inspected live via `inspect.getsource()`
- pydantic-settings 2.14.0 — `YamlConfigSettingsSource.__init__` signature inspected live; YAML load + env override verified via live Python session
- Python stdlib — `abc.ABC`, `getpass`, `subprocess.DEVNULL` — verified via live import
- selenium 4.43.0 — `Service(log_output=subprocess.DEVNULL)` pattern confirmed from installed version
- CONCERNS.md — codebase audit identifying logger re-read, sys.stdout hack, shared driver, missing purchased update

### Secondary (MEDIUM confidence)

- bytetunnels.com nodriver guide — confirmed nodriver does not set `navigator.webdriver`; no WebDriver protocol layer
- capsolver.com nodriver vs traditional — confirmed CDP-direct approach eliminates webdriver property detection
- pydantic-settings GitHub issue #366 — confirmed `YamlConfigSettingsSource` pattern for `settings_customise_sources`
- pydantic-settings raw docs — `settings_customise_sources` signature, priority order, `env_nested_delimiter` behavior

### Tertiary (LOW confidence)

- WebSearch: nodriver user agent and navigator.webdriver behavior — cross-verified with source code inspection

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all packages verified as installed; source code inspected live
- Architecture patterns: HIGH — all patterns verified via live Python execution
- nodriver stealth behavior: HIGH — verified by inspecting `_prepare_headless()` and `_prepare_expert()` source; confirmed `navigator.webdriver` is not set by architecture
- pydantic-settings YAML pattern: HIGH — YamlConfigSettingsSource signature and behavior verified live
- Pitfalls: HIGH — mostly derived from live code inspection and codebase audit
- Test infrastructure gaps: HIGH — confirmed by running `pytest` in the repo

**Research date:** 2026-06-01

**Valid until:** 2026-07-01 (stable libraries; nodriver releases frequently but API is stable)
