# Phase 1: Foundations + Security - Research

**Researched:** 2026-05-02
**Domain:** Python plugin ABC contract, Pydantic config validation, credential hardening, Selenium stealth
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: Plugin ABC method signatures**
- ABC method signatures drop the `driver` parameter. Methods take only `self` plus domain args.
- Final shapes:
  - `check_availability(self, url: str) -> bool` (abstract)
  - `auto_buy(self, url: str, config) -> bool` (abstract)
  - `login(self, config) -> None` (no-op default)
  - `detect_captcha(self) -> bool` (no-op default returning False)
- Plugin owns its driver as `self.driver`, constructed in `__init__`.
- This **revises CORE-01 wording** in REQUIREMENTS.md (currently lists `driver` as a parameter on three methods). REQUIREMENTS.md must be edited during planning to match.

**D-02: Plugin `__init__` shape**
- Signature: `__init__(self, platform_config)`.
- Orchestrator slices `AppConfig.platforms.<name>` and passes only that platform's block.
- Plugin constructs `self.driver` synchronously inside `__init__`. Phase 4 may revisit if nodriver requires async-only construction.
- No global config import inside plugins. No cross-platform reads from `__init__`.

**D-03: Selenium drop deferred to Phase 2**
- Phase 1 keeps Selenium and `webdriver_manager` in `requirements.txt`.
- Phase 1 hardens the existing Selenium driver against bot-detection signals:
  - SEC-03: remove `--disable-web-security` flag from `ChromeOptions`.
  - SEC-04: hide `navigator.webdriver` via Selenium's CDP command (`execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", ...)`).
  - SEC-05: real Chrome user agent string set via `ChromeOptions.add_argument(f"user-agent={...}")`.
- Phase 2 swaps Selenium for nodriver atomically with the plugin migration.
- Bot remains runnable end-to-end after every Phase 1 plan ships.

**D-04: CVV prompt timing**
- `getpass.getpass()` fires once at startup, looping over enabled platforms that have `auto_buy: true` on at least one item.
- CVV held only in memory (no persistence, no logging).
- If a CVV is required but missing, the bot exits before entering the polling loop (fail-fast).

**D-05: Non-TTY behavior**
- Default: when `sys.stdin.isatty()` is False and any platform has `auto_buy: true`, the bot exits with a clear error message.
- Opt-in escape hatch for headless deployments:
  - User must set `SHOPBOT_ALLOW_CVV_ENV=true` (acknowledgement flag).
  - Per-platform CVV read from `SHOPBOT_<PLATFORM>_CVV` env var (e.g., `SHOPBOT_AMAZON_CVV`).
  - Documented in SEC-06 README disclaimer as "trusted infrastructure only".
- Without the opt-in flag, the env var is ignored even if set.

**D-06: Config migration policy**
- On startup, Pydantic validation also scans for deprecated keys (`app.amz_email`, `app.amz_pwd`, `app.bb_email`, `app.bb_password`).
- If any old key is detected:
  1. Print a structured migration block listing each old key and its new location.
  2. Exit with non-zero status.
  3. Do not read or remap old credential fields under any circumstance.
- No back-compat shim. No auto-rewrite.

**D-07: Pydantic strictness + env var naming**
- `model_config = SettingsConfigDict(extra="forbid", env_nested_delimiter="__", env_prefix="SHOPBOT_")`.
- Unknown config keys produce an actionable Pydantic validation error at startup.
- Env var convention: `SHOPBOT_PLATFORMS__AMAZON__EMAIL`, `SHOPBOT_PLATFORMS__BESTBUY__PASSWORD`.
- CVV env vars under the opt-in flag use a flat name: `SHOPBOT_AMAZON_CVV`, `SHOPBOT_BESTBUY_CVV` (separate from nested config schema).

### Claude's Discretion
- Exact wording of Pydantic validation error messages.
- Internal module layout under a `core/` package vs flat root.
- Logger singleton implementation pattern for INFRA-02 (module-level vs `functools.cache` vs metaclass).
- Whether `requirements.txt` pins use `==X.Y.Z` only or `==X.Y.Z` with hash pins.
- `getpass` exception handling (KeyboardInterrupt at prompt = exit 130 vs treat as opt-out).

### Deferred Ideas (OUT OF SCOPE)
- `PluginDriver` Protocol abstraction — defer to `PLUGIN_API_VERSION = 2`.
- Auto-migration of old `config.yml` to new schema with `.bak` backup — explicitly rejected in D-06.
- Two-phase async `__init__` + `setup()` for nodriver-native plugins — Phase 4 concern.
- Per-purchase CVV prompting — rejected in D-04.
- Pre-commit hook scanning for `_pwd` / `_cvv` patterns — INFRA backlog, not Phase 1.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-01 | Plugin ABC defines `check_availability`, `auto_buy`, `login`, `detect_captcha` (revised per D-01: drop `driver` param) | abc.ABC + abstractmethod patterns; signature locked in CONTEXT |
| CORE-02 | `PLUGIN_API_VERSION = 1` constant; no-op defaults for `login` and `detect_captcha` | Module-level constant + concrete method on ABC base class |
| CORE-05 | Pydantic `AppConfig` validates `config.yml` at startup; actionable error messages | pydantic-settings 2.14.0 + YamlConfigSettingsSource |
| CORE-06 | Per-platform credential sections (`platforms.amazon.email`, `platforms.bestbuy.cvv`, etc.) | Nested BaseModel with `dict[str, PlatformConfig]` |
| CORE-07 | Migration warnings for old `app.amz_email`/`app.bb_email` keys | model_validator(mode="before") scanning the raw dict |
| SEC-01 | Credentials from env vars; config.yml holds non-sensitive only | pydantic-settings env_nested_delimiter="__" + env_prefix="SHOPBOT_" |
| SEC-02 | CVV via `getpass.getpass()` at runtime; never stored | stdlib `getpass` module |
| SEC-03 | `--disable-web-security` Chrome flag removed | Direct removal from `main.py` ChromeOptions |
| SEC-04 | CDP patch hides `navigator.webdriver` at driver startup | `driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", ...)` |
| SEC-05 | Real Chrome user agent string | `ChromeOptions.add_argument(f"user-agent=...")` with current Chrome UA |
| SEC-06 | README disclaimer (personal use, TOS, account risk) | Documentation work; reference SECURITY.md skeleton |
| INFRA-01 | requirements.txt pinned + dedup; `python_requires >= 3.11` | Verified versions table below; `pyproject.toml` or `setup.py` declaration |
| INFRA-02 | Logger singleton; no per-call config re-read | Module-level cache or `functools.cache` |
| INFRA-03 | Remove `sys.stdout` monkey-patch; route ChromeDriver via `Service(log_path=...)` | Selenium 4.x `Service(log_path=...)` parameter |
</phase_requirements>

## Summary

Phase 1 is a security-and-foundations gate before open source launch. Three concerns dominate: (1) lock a plugin ABC contract that every retailer plugin must inherit, (2) replace ad-hoc YAML access with Pydantic-validated typed config, and (3) eliminate every credential-in-plaintext / driver-stealth gap so the repo is publishable.

The implementation is mechanical — the ecosystem has standard solutions for each piece (`abc.ABC`, `pydantic-settings` with YAML source, `getpass`, Selenium CDP commands). The bulk of the planning effort goes into ordering the work so the bot remains runnable after every commit, and into the migration UX of D-06 (deprecated key detection with hard-fail and a copy-pasteable migration block).

**Primary recommendation:** Execute in five waves: (1) requirements.txt cleanup and Python 3.11 floor; (2) plugin ABC + `PLUGIN_API_VERSION`; (3) Pydantic AppConfig with deprecated-key validator; (4) credential migration to env vars + getpass CVV prompt; (5) Selenium stealth fixes (SEC-03/04/05) + INFRA-02/03 cleanup. Add tests for each wave; keep Selenium driver intact through the whole phase.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Plugin contract (ABC + version constant) | Core / domain layer | — | Pure Python interface; no I/O |
| Config validation | Process boundary (startup) | — | Fail-fast at import time, before any side effects |
| Credential resolution | Environment / process boundary | — | Env vars + interactive `getpass`; never disk |
| Driver stealth (CDP, UA, flags) | Browser automation layer (`amazon_bot.py`/`bestbuy_bot.py`) | — | Stays at the `webdriver.Chrome(...)` instantiation site for Phase 1 |
| Logger singleton | Cross-cutting infra | — | Module-level state in `logger.py` |
| ChromeDriver output suppression | Browser automation layer | — | `Service(log_path=...)` at driver construction |

## Standard Stack

### Core (Phase 1 additions)
| Library | Version | Purpose | Why Standard | Provenance |
|---------|---------|---------|--------------|------------|
| pydantic | 2.13.3 | Schema definition, validators, error messages | De facto standard for typed Python config; v2 is rewrite in Rust (faster) and is the supported line | [VERIFIED: pip index versions pydantic, latest 2.13.3 as of 2026-05-02] |
| pydantic-settings | 2.14.0 | Settings management with env-var + YAML source loaders | Official extension to pydantic v2; supports `env_nested_delimiter`, `YamlConfigSettingsSource`, multi-source merging | [VERIFIED: pip index versions pydantic-settings, latest 2.14.0] |
| pydantic-settings[yaml] | 2.14.0 | Pulls in `pyyaml` as YAML source dependency | Required for `YamlConfigSettingsSource` | [CITED: docs.pydantic.dev/latest/concepts/pydantic_settings/#yaml] |

### Retained (Phase 1 keeps these; pinned per INFRA-01)
| Library | Version | Purpose | Why Retained | Provenance |
|---------|---------|---------|--------------|------------|
| selenium | 4.43.0 | Browser automation | Phase 1 hardens existing Selenium per D-03; drop deferred to Phase 2 | [VERIFIED: pip index versions selenium] |
| webdriver-manager | 4.0.2 | Auto-download ChromeDriver | Used by `main.py:get_chromedriver_path()` | [VERIFIED: pip index versions webdriver-manager] |
| pyyaml | 6.0.3 | YAML parser (transitive via pydantic-settings[yaml]) | Direct usage replaced by pydantic-settings YAML source; transitive dep remains | [VERIFIED: pip index versions pyyaml] |
| pygame | 2.6.1 | Sound notification playback | Untouched in Phase 1 (Phase 5 wraps in `SoundNotifier`) | [VERIFIED: pip install pygame --dry-run 2026-05-02] |
| colorama | 0.4.6 | Terminal color codes | Used by `logger.py` writeLog | [VERIFIED: pip index versions colorama] |
| requests | 2.33.1 | TinyURL shortener call | Replaced in later phases; retain for Phase 1 | [VERIFIED: pip index versions requests] |
| urllib3 | (transitive) | requests dependency | Pin via constraint in requirements.txt | [VERIFIED: transitive dependency of requests] |

### Test
| Library | Version | Purpose | Provenance |
|---------|---------|---------|------------|
| pytest | 9.0.3 | Test runner | [VERIFIED: pip index versions pytest, latest 9.0.3] |
| pytest 8.x line | 8.3.2 | Last 8.x-line release; safer minimum if 9.x changes break older patterns | [VERIFIED: existing installed version] |

**Recommendation:** Pin to `pytest==8.3.4` or newer in the 8.x series for stability unless 9.x feature is required; verify against existing tests before bumping. [ASSUMED]

### Stdlib (no install)
| Module | Purpose |
|--------|---------|
| `abc` | `ABC`, `abstractmethod` for the plugin base class |
| `getpass` | Runtime CVV prompt (D-04) |
| `os` | Env var reads (`os.environ.get`) |
| `sys` | `sys.stdin.isatty()` for D-05 non-TTY detection |
| `functools` | `cache` decorator option for INFRA-02 |
| `pathlib` | Replace `os.path.join` for new code |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pydantic-settings | dynaconf, environs | pydantic-settings has tighter pydantic v2 integration, official YAML source, and matches CONTEXT.md D-07 verbatim; no reason to deviate |
| pydantic v2 | dataclasses + manual validation | Manual validation duplicates effort; pydantic v2 produces user-readable error messages without extra code (CORE-05 requires actionable errors) |
| getpass | inquirer / prompt-toolkit | getpass is stdlib, no echo of CVV digits; matches D-04 verbatim |

**Installation (proposed `requirements.txt` skeleton):**

```
pydantic==2.13.3
pydantic-settings[yaml]==2.14.0
selenium==4.43.0
webdriver-manager==4.0.2
pygame==2.6.1
colorama==0.4.6
requests==2.33.1
pytest==8.3.4
```

[VERIFIED: all versions checked against `pip index versions` 2026-05-02]

**Python floor declaration (INFRA-01):** Add minimal `pyproject.toml` declaring `requires-python = ">=3.11"`. A `setup.py` is not needed — `pyproject.toml` alone is the modern norm. [CITED: packaging.python.org/en/latest/specifications/pyproject-toml/]

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────┐
   config.yml ────► │  Process Startup        │
   env vars   ────► │  ──────────────────────  │
   stdin (TTY)────► │  AppConfig (pydantic)   │ ── validation fail ──► structured error → exit(1)
                    │   ├ deprecated-key scan ─┴── if old keys ──────► migration block → exit(1)
                    │   └ getpass CVV (D-04)  │
                    └────────────┬────────────┘
                                 │ AppConfig instance + cvv_map
                                 ▼
                    ┌─────────────────────────┐
                    │  Driver Construction     │
                    │  ──────────────────────  │
                    │  ChromeOptions           │ ◄─ SEC-03: no --disable-web-security
                    │  + real UA (SEC-05)      │
                    │  Service(log_path=...)   │ ◄─ INFRA-03: no stdout monkey-patch
                    │  driver.execute_cdp_cmd  │ ◄─ SEC-04: hide navigator.webdriver
                    └────────────┬────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │  Polling Loop (main.py) │ unchanged in Phase 1
                    │  ──────────────────────  │ amazon_bot/bestbuy_bot still domain-routed
                    │  domain dispatch         │ Plugin ABC defined but NOT yet used here
                    └─────────────────────────┘
```

### Recommended Project Structure

Two viable layouts. Planner picks one (Claude's discretion per CONTEXT D).

**Option A: flat root (matches existing convention from CONVENTIONS.md)**
```
ShopPyBot/
├── main.py
├── amazon_bot.py
├── bestbuy_bot.py
├── plugin_base.py        # NEW: RetailerPlugin ABC + PLUGIN_API_VERSION
├── config_schema.py      # NEW: AppConfig (pydantic-settings)
├── credentials.py        # NEW: getpass CVV + env-var resolution + non-TTY logic
├── config.py             # KEPT but rewritten: returns AppConfig instance
├── logger.py             # MODIFIED: singleton, no per-call yaml read
├── models.py
├── utils.py
└── pyproject.toml        # NEW: python_requires>=3.11
```

**Option B: `core/` package**
```
ShopPyBot/
├── main.py
├── amazon_bot.py
├── bestbuy_bot.py
├── core/
│   ├── __init__.py
│   ├── plugin_base.py
│   ├── config_schema.py
│   └── credentials.py
└── ...
```

**Recommendation:** Option A (flat). Rationale: matches existing CONVENTIONS.md ("Flat snake_case modules; no sub-packages"); minimizes import-path churn for the Phase 2 plugin migration; `core/` adds nesting before any consumer exists. [ASSUMED — planner may override]

### Pattern 1: Plugin ABC base class (CORE-01, CORE-02)

**What:** Single abstract base class, two abstract methods, two concrete no-op defaults, one module-level constant.

**When to use:** All retailer plugins inherit from this exactly once.

**Example:**
```python
# plugin_base.py
from abc import ABC, abstractmethod

PLUGIN_API_VERSION = 1


class RetailerPlugin(ABC):
    """Base class for retailer plugins.

    Subclasses MUST construct self.driver in __init__ (D-02, PLG-03).
    Subclasses MUST implement check_availability and auto_buy.
    Subclasses MAY override login and detect_captcha; defaults are no-ops.
    """

    def __init__(self, platform_config) -> None:
        # platform_config is a per-platform pydantic model slice (D-02).
        # Concrete subclasses build self.driver here.
        raise NotImplementedError

    @abstractmethod
    def check_availability(self, url: str) -> bool:
        """Return True if the item at url is in stock."""

    @abstractmethod
    def auto_buy(self, url: str, config) -> bool:
        """Attempt purchase. Return True on confirmed order."""

    def login(self, config) -> None:  # no-op default
        return None

    def detect_captcha(self) -> bool:  # no-op default
        return False
```

[CITED: docs.python.org/3/library/abc.html — ABC + abstractmethod is canonical]

**Test pattern (CORE-01/02 acceptance):**
```python
# tests/test_plugin_base.py
import pytest
from plugin_base import RetailerPlugin, PLUGIN_API_VERSION

def test_api_version_is_one():
    assert PLUGIN_API_VERSION == 1

def test_cannot_instantiate_abstract():
    with pytest.raises(TypeError):
        RetailerPlugin({})  # abstract methods unimplemented

def test_default_login_is_noop():
    class P(RetailerPlugin):
        def __init__(self, cfg): pass
        def check_availability(self, url): return False
        def auto_buy(self, url, cfg): return False
    p = P({})
    assert p.login(None) is None
    assert p.detect_captcha() is False
```

### Pattern 2: Pydantic AppConfig with YAML + env (CORE-05, CORE-06, D-07)

**What:** `BaseSettings` subclass with `extra="forbid"`, env-var nested override, YAML source.

**Example:**
```python
# config_schema.py
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    YamlConfigSettingsSource,
    PydanticBaseSettingsSource,
)


class PlatformCredentials(BaseModel):
    email: str
    password: str
    # cvv is intentionally NOT here — collected at runtime via getpass (SEC-02)


class PlatformConfig(BaseModel):
    enabled: bool = True
    credentials: PlatformCredentials


class SeleniumConfig(BaseModel):
    driver_path: str


class DebugConfig(BaseModel):
    logging_level: int = Field(5, ge=0, le=5)
    test_mode: bool = False


class ItemConfig(BaseModel):
    name: str
    link: str
    auto_buy: bool
    quantity: int = Field(ge=1)


class AvailableConfig(BaseModel):
    items: list[ItemConfig]


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        extra="forbid",
        env_nested_delimiter="__",
        env_prefix="SHOPBOT_",
        yaml_file="config.yml",
    )

    selenium: SeleniumConfig
    debug: DebugConfig = DebugConfig()
    available: AvailableConfig
    platforms: dict[str, PlatformConfig]
    open_browser: bool = False

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Order: init args > env vars > YAML file (env wins for credentials per SEC-01)
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
        )

    @model_validator(mode="before")
    @classmethod
    def reject_deprecated_keys(cls, data):
        # D-06: scan for old credential keys, hard-fail with migration block
        if not isinstance(data, dict):
            return data
        app = data.get("app", {}) if isinstance(data.get("app"), dict) else {}
        deprecated = {
            "amz_email": "SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL or platforms.amazon.credentials.email",
            "amz_pwd":   "SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__PASSWORD",
            "bb_email":  "SHOPBOT_PLATFORMS__BESTBUY__CREDENTIALS__EMAIL or platforms.bestbuy.credentials.email",
            "bb_password": "SHOPBOT_PLATFORMS__BESTBUY__CREDENTIALS__PASSWORD",
            "bb_cvv":    "(removed) prompted at runtime via getpass; opt-in env var SHOPBOT_BESTBUY_CVV with SHOPBOT_ALLOW_CVV_ENV=true",
        }
        found = {k: v for k, v in deprecated.items() if k in app}
        if found:
            lines = [
                "═══ DEPRECATED CONFIG KEYS DETECTED ═══",
                "config.yml uses old credential keys. Migrate before continuing:",
                "",
            ]
            for old, new in found.items():
                lines.append(f"  app.{old}  →  {new}")
            lines.append("")
            lines.append("After migration, remove the entire `app:` section if empty.")
            lines.append("Bot will not start until migration is complete.")
            raise ValueError("\n".join(lines))
        return data
```

[CITED: docs.pydantic.dev/latest/concepts/pydantic_settings/#yaml — YamlConfigSettingsSource]
[CITED: docs.pydantic.dev/latest/concepts/pydantic_settings/#customise-settings-sources — settings_customise_sources]
[CITED: docs.pydantic.dev/latest/api/standard_library_types/#typingdict — dict[str, BaseModel] for `platforms` map]

**Source priority resolution:** environment variables override YAML for the same key. This is what SEC-01 wants: a user can leave `platforms.amazon.credentials.email: ""` in YAML and supply `SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL` in the environment, and pydantic will use the env value. [CITED: docs.pydantic.dev/latest/concepts/pydantic_settings/#field-value-priority]

### Pattern 3: CVV runtime prompt (SEC-02, D-04, D-05)

```python
# credentials.py
import getpass
import os
import sys


def collect_cvvs(app_config) -> dict[str, str]:
    """Returns {platform_name: cvv}. Called once at startup before the polling loop."""
    needed = [
        name for name, plat in app_config.platforms.items()
        if plat.enabled and any(item.auto_buy for item in app_config.available.items)
    ]
    if not needed:
        return {}

    if not sys.stdin.isatty():
        if os.environ.get("SHOPBOT_ALLOW_CVV_ENV", "").lower() == "true":
            cvvs = {}
            for name in needed:
                env_key = f"SHOPBOT_{name.upper()}_CVV"
                val = os.environ.get(env_key)
                if not val:
                    sys.stderr.write(
                        f"ERROR: {env_key} is required because SHOPBOT_ALLOW_CVV_ENV=true and "
                        f"stdin is not a TTY. Set the env var or remove auto_buy from "
                        f"{name} items.\n"
                    )
                    sys.exit(1)
                cvvs[name] = val
            return cvvs
        sys.stderr.write(
            "ERROR: auto_buy is enabled but stdin is not a TTY. "
            "Either run interactively, or set SHOPBOT_ALLOW_CVV_ENV=true and supply "
            "SHOPBOT_<PLATFORM>_CVV env vars (visible in /proc/<pid>/environ — trusted infra only).\n"
        )
        sys.exit(1)

    cvvs = {}
    for name in needed:
        cvvs[name] = getpass.getpass(f"Enter CVV for {name}: ")
        if not cvvs[name]:
            sys.stderr.write(f"ERROR: empty CVV for {name}; aborting.\n")
            sys.exit(1)
    return cvvs
```

[CITED: docs.python.org/3/library/getpass.html — getpass.getpass returns str, no echo]

### Pattern 4: Selenium stealth fixes (SEC-03, SEC-04, SEC-05)

```python
# Updated driver setup in main.py (or whichever module owns it)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

def build_driver(driver_path: str, log_path: str = "logs/chromedriver.log"):
    opts = Options()
    # SEC-03: no --disable-web-security (REMOVED)
    # SEC-05: real UA
    opts.add_argument(f"--user-agent={CHROME_UA}")
    # Existing prefs/flags retained EXCEPT --disable-web-security
    opts.add_argument("--disable-blink-features=AutomationControlled")

    # INFRA-03: route ChromeDriver output via Service log_path; no stdout monkey-patch
    service = Service(executable_path=driver_path, log_path=log_path)

    driver = webdriver.Chrome(service=service, options=opts)

    # SEC-04: CDP patch to hide navigator.webdriver
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        },
    )
    return driver
```

[CITED: selenium-python.readthedocs.io/api.html#selenium.webdriver.chrome.service.Service — log_path parameter]
[CITED: chromedevtools.github.io/devtools-protocol/tot/Page/#method-addScriptToEvaluateOnNewDocument]

**UA string note:** Use a current Chrome UA. `131` is illustrative; planner should pull the UA from a recent stable Chrome release at implementation time, or read `navigator.userAgent` from a vanilla Chrome and strip the `HeadlessChrome` token. The exact major version is not load-bearing for SEC-05 acceptance — what matters is that it does not contain `Selenium` or `HeadlessChrome`. [ASSUMED — current major Chrome version varies; verify at task time]

### Pattern 5: Logger singleton (INFRA-02)

```python
# logger.py — replacement for the per-call yaml load
import os
import functools
from datetime import datetime
from colorama import Fore, Style

LOG_LEVELS = {
    "ALWAYS": (Fore.CYAN, 0),
    "ERROR": (Fore.RED, 1),
    "WARNING": (Fore.YELLOW, 2),
    "SUCCESS": (Fore.GREEN, 2),
    "INFO": (Fore.WHITE, 3),
    "DEBUG": (Fore.BLUE, 4),
    "TRACE": (Fore.MAGENTA, 5),
}

_logging_level: int | None = None  # set once via configure()

def configure(level: int) -> None:
    """Called once from main.py after AppConfig loads."""
    global _logging_level
    _logging_level = level

def writeLog(message: str, type: str, writeTofile: bool = True) -> None:
    if _logging_level is None:
        # Defensive default if configure() was not called
        level_threshold = 5
    else:
        level_threshold = _logging_level
    color, level = LOG_LEVELS.get(type.upper(), (Fore.LIGHTBLACK_EX, 0))
    if level_threshold >= level:
        ts = datetime.now().strftime('%Y%B%d@%H:%M:%S')
        print(f"{color}[{type.upper()}][{ts}] {message}{Style.RESET_ALL}")
        if writeTofile:
            _write_to_file(type, ts, message)

@functools.cache
def _log_dir() -> str:
    here = os.path.dirname(os.path.realpath(__file__))
    d = os.path.join(here, "logs")
    os.makedirs(d, exist_ok=True)
    return d

def _write_to_file(type: str, ts: str, message: str) -> None:
    path = os.path.join(_log_dir(), f"{datetime.now().strftime('%Y%B%d')}.log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{type.upper()}][{ts}] {message}\n")
```

**Backward-compat note:** The function name `writeLog` is preserved (CONVENTIONS.md flags this as a known legacy name to keep). All existing callers continue to work; only internals change.

### Anti-Patterns to Avoid

- **Per-call YAML reload:** confirmed bottleneck; INFRA-02 fixes it. Never re-add it.
- **Module-level config side effects in plugin_base.py:** the ABC must not import `config` (per D-02). Plugins receive their config slice via `__init__`.
- **`except:` (bare):** existing `amazon_bot.py` `detect_captcha` and `amz_sign_in` use bare except. New code in Phase 1 must use `except Exception as e` per CONVENTIONS.md.
- **Reading old `app.amz_email`-style keys "just in case":** D-06 explicitly forbids any back-compat shim. Detect, hard-fail, exit. No silent remap.
- **CVV in env var by default:** D-05 makes the env-var path opt-in only. Default behavior must hard-fail on non-TTY.
- **Storing CVV anywhere (logs, files, DB, config):** SEC-02. CVV exists only in the `cvvs` dict in process memory.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML schema validation | Manual `if "x" not in cfg: raise` chains | `pydantic-settings` v2 BaseSettings + YamlConfigSettingsSource | pydantic produces user-readable error messages with exact field paths, types, and locations — required by CORE-05 acceptance |
| Env-var → nested config mapping | Custom `os.environ.get` + dict merge | pydantic-settings `env_nested_delimiter="__"` | Matches D-07 verbatim; handles type coercion, validation, and source priority for free |
| Password / CVV prompts | `input()` (echoes to terminal!) | `getpass.getpass()` | Stdlib; suppresses echo; matches SEC-02 and D-04 |
| Hide `navigator.webdriver` | JavaScript injection via `driver.execute_script` after page load | `driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", ...)` | CDP runs the script before any page script — `execute_script` runs after, so the property is briefly visible. SEC-04 demands the CDP path. |
| ChromeDriver stdout suppression | `sys.stdout = open(os.devnull)` monkey-patch | `Service(log_path="...")` | Existing monkey-patch swallows real Python errors (CONCERNS.md) — INFRA-03 specifically calls out replacing it |
| Plugin discovery in Phase 1 | importlib scanning | (defer to Phase 2) | CORE-03/04 are Phase 2 — Phase 1 only locks the ABC itself |

**Key insight:** Every Phase 1 requirement maps to a stdlib or `pydantic-settings` feature. There is no place where hand-rolled code is justified.

## Runtime State Inventory

This phase **introduces** new state (env vars, pydantic schema) but does not rename anything. However, D-06 makes deprecated config keys a runtime concern that must be handled, so the inventory below is informative rather than action-required.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 1 does not rename DB collections, item URLs, or stored values. The SQLite `items` table schema is untouched. | None (verified by reading models.py — no string the rename would touch) |
| Live service config | None — there are no external services (n8n, Datadog, Cloudflare, etc.) in scope for this project. | None |
| OS-registered state | None — the bot is not registered with Task Scheduler, systemd, pm2, or launchd. | None |
| Secrets / env vars | NEW: `SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL`, `SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__PASSWORD`, `SHOPBOT_PLATFORMS__BESTBUY__CREDENTIALS__EMAIL`, `SHOPBOT_PLATFORMS__BESTBUY__CREDENTIALS__PASSWORD`, optional `SHOPBOT_ALLOW_CVV_ENV`, `SHOPBOT_AMAZON_CVV`, `SHOPBOT_BESTBUY_CVV`. None of these existed before — they are introduced by Phase 1. User must set them before running. | Document in README; sample.config.yml comment lines pointing at env-var names |
| Build artifacts | NEW: `pyproject.toml` (or amend if planner adds setup.py); `requirements.txt` rewritten. No installed `.egg-info` to clean — project is run via `python main.py`, not pip-installed. | None beyond the file creation/rewrite tasks themselves |

**Nothing else found in any category** — verified by reading the codebase modules and the codebase analysis docs (STRUCTURE.md, STACK.md, CONCERNS.md).

## Common Pitfalls

### Pitfall 1: Env-var override silently masks YAML field
**What goes wrong:** User sets `SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__PASSWORD` in their shell, then edits `config.yml` to fix something. The env value silently wins; user thinks YAML is broken.
**Why it happens:** pydantic-settings source order (env > YAML) is correct for SEC-01 but counter-intuitive for users.
**How to avoid:** Log the source of every credential at startup at INFO level: "amazon.email loaded from env var SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL". Pydantic does not expose this directly — the planner can implement it by checking `os.environ` for each known key after AppConfig is built.
**Warning signs:** "Why isn't my new password working?" support tickets.
[VERIFIED: docs.pydantic.dev/latest/concepts/pydantic_settings/#field-value-priority]

### Pitfall 2: `extra="forbid"` rejects valid future keys
**What goes wrong:** A future phase adds a new optional config key. Existing user configs that haven't added the key are fine, but old configs that have a different unknown key (a typo) fail in production.
**Why it happens:** D-07 mandates `extra="forbid"`. This is the desired behavior for CORE-05 (catch typos), but every new key requires AppConfig to be updated.
**How to avoid:** Document in CONTRIBUTING.md (Phase 3) that adding a config key is a CORE-side change. Maintain an explicit list of supported keys in `config_schema.py` docstring.
**Warning signs:** None — this is intentional design, not a bug.

### Pitfall 3: `navigator.webdriver` patch must run before page load
**What goes wrong:** Engineer uses `driver.execute_script("Object.defineProperty(...)")` after `driver.get(url)`. The page's anti-bot script reads `navigator.webdriver` during initial JS execution and flags the session as a bot before the patch runs.
**Why it happens:** `execute_script` injects after the page is already loaded; CDP `addScriptToEvaluateOnNewDocument` injects before any page script.
**How to avoid:** Always use `driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": ...})`, called once immediately after `webdriver.Chrome(...)` returns and BEFORE the first `driver.get`.
**Warning signs:** Amazon serves CAPTCHA on every visit despite stealth fixes.
[CITED: chromedevtools.github.io/devtools-protocol/tot/Page/#method-addScriptToEvaluateOnNewDocument — "scripts are evaluated after the document was created but before any of its scripts were executed"]

### Pitfall 4: getpass on Windows + non-TTY
**What goes wrong:** User runs the bot via a Windows IDE (PyCharm, VS Code) "Run" button — `sys.stdin.isatty()` returns False inside the IDE, but the user expected to see a prompt.
**Why it happens:** IDE-redirected stdin lacks TTY status. D-05's behavior (hard-fail) is correct, but the error message must be specific.
**How to avoid:** D-05 error message must say "stdin is not a TTY (this happens when running from an IDE Run button or under cron/systemd)". Include the SHOPBOT_ALLOW_CVV_ENV opt-in instructions verbatim in the message.
**Warning signs:** "Bot exits immediately when I press Run in PyCharm."

### Pitfall 5: pydantic v1 docs leak into v2 implementation
**What goes wrong:** Engineer copies `@validator` (v1) instead of `@field_validator` / `@model_validator` (v2). Code "works" but warning-spams or behaves wrong on edge cases.
**Why it happens:** Pydantic v1 was widely used until 2024; v1 examples still rank in search results.
**How to avoid:** Use only `@field_validator(...)`, `@model_validator(mode="before"/"after")`. Do not use `@validator` or `@root_validator`. Reference docs.pydantic.dev/latest/ explicitly (the `latest` URL is v2).
**Warning signs:** `DeprecationWarning: @validator is deprecated`.
[CITED: docs.pydantic.dev/latest/migration/]

### Pitfall 6: pyproject.toml `requires-python` not enforced by `python main.py`
**What goes wrong:** INFRA-01 declares `requires-python = ">=3.11"` in pyproject.toml. User on Python 3.10 runs `python main.py` directly. pyproject.toml is only consulted by `pip install`, not by the Python interpreter at runtime.
**Why it happens:** `pyproject.toml` is build-time metadata; it does not gate `python main.py`.
**How to avoid:** Add a runtime guard at the top of `main.py`:
```python
import sys
if sys.version_info < (3, 11):
    sys.exit(f"ShopPyBot requires Python 3.11+. Detected: {sys.version}")
```
**Warning signs:** Cryptic stdlib errors (e.g., `tomllib` import) on older Python.

## Code Examples

### Example: AppConfig instantiation in `main.py`

```python
from config_schema import AppConfig
from credentials import collect_cvvs
from logger import configure as configure_logger, writeLog

def main():
    try:
        config = AppConfig()  # raises ValidationError on bad config or deprecated keys
    except Exception as e:
        # Pydantic ValidationError prints field paths + messages
        print(str(e), file=sys.stderr)
        sys.exit(1)

    configure_logger(config.debug.logging_level)
    cvvs = collect_cvvs(config)  # may exit(1) on non-TTY without opt-in

    driver = build_driver(config.selenium.driver_path)
    # ... existing polling loop ...
```

[Source: synthesized from CONTEXT decisions D-04, D-05, D-06, D-07; pydantic ValidationError shape per docs.pydantic.dev/latest/concepts/models/#error-handling]

### Example: Test fixture for AppConfig (replaces tests/test_config.py)

```python
# tests/test_config_schema.py
import pytest
from pydantic import ValidationError
from config_schema import AppConfig

def test_deprecated_amz_email_hard_fails(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yml"
    cfg.write_text("""
selenium: {driver_path: "x"}
app:
  amz_email: "leak@example.com"
available: {items: []}
platforms: {}
""")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError) as exc:
        AppConfig()
    assert "amz_email" in str(exc.value)
    assert "SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL" in str(exc.value)

def test_env_var_overrides_yaml(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yml"
    cfg.write_text("""
selenium: {driver_path: "x"}
available: {items: []}
platforms:
  amazon:
    enabled: true
    credentials: {email: "yaml@x.com", password: "yaml"}
""")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL", "env@x.com")
    cfg = AppConfig()
    assert cfg.platforms["amazon"].credentials.email == "env@x.com"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pydantic v1 `@validator` | pydantic v2 `@field_validator` / `@model_validator(mode=...)` | pydantic 2.0 release (2023-06) | All validators in this phase use v2 syntax exclusively |
| `pyyaml.safe_load` direct in app code | `pydantic-settings[yaml]` `YamlConfigSettingsSource` | pydantic-settings 2.2+ added YAML source | Validation, env merging, and YAML loading become one call (`AppConfig()`) |
| `setup.py` for Python project metadata | `pyproject.toml` (PEP 621) | Mainstream since ~2022 | One file declares both build-system and `requires-python` |
| `webdriver.Chrome(executable_path=...)` | `webdriver.Chrome(service=Service(...))` | Selenium 4.0 (2021-10) | Existing code already uses Service; INFRA-03 just adds `log_path` |
| `driver.execute_script` to hide webdriver | `driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", ...)` | Selenium 4.x CDP support | SEC-04 mandates the CDP path |

**Deprecated / outdated:**
- Python 3.8 — EOL October 2024. INFRA-01 raises floor to 3.11. [CITED: devguide.python.org/versions/]
- pydantic 1.x — still maintained for legacy users; new code is v2-only. [CITED: docs.pydantic.dev/latest/migration/]
- `requests` — Phase 1 retains for the TinyURL call only. Future phase migrates to `httpx` (per research/SUMMARY.md). [CITED: SUMMARY.md row "Adopt httpx replaces requests"]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Recommended project structure: flat root (Option A) is preferred over `core/` package | Architecture Patterns → Recommended Project Structure | Low — planner has explicit discretion to override; either layout satisfies all phase requirements |
| A2 | pytest 8.3.4 is the safest minimum pin (vs 9.0.3 latest) | Standard Stack → Test | Medium — if planner picks 9.x and existing tests break on a syntax change, plan needs a remediation task |
| A3 | Chrome UA string `Chrome/131.0.0.0` is current enough | Pattern 4 → CHROME_UA constant | Low — exact major version not load-bearing for SEC-05 acceptance; any non-Selenium, non-Headless UA passes; planner can pull a fresher value at task time |
| A4 | `pyproject.toml` alone (no `setup.py`) satisfies INFRA-01's `python_requires` declaration | Standard Stack → Python floor declaration | Low — PEP 621 is the established standard; only matters if the project ever ships as a pip-installable package, which is not in scope until Phase 6+ |
| A5 | The order of source priority (env > YAML) is what SEC-01 wants | Pattern 2 → settings_customise_sources | Low — D-07 implies this by mandating `env_prefix="SHOPBOT_"` for credentials; the alternative (YAML > env) defeats the credential-from-env goal |

**If the planner needs user confirmation on any A# item, surface it in PLAN.md as an open question.**

## Open Questions (RESOLVED)

1. **Schema for `platforms.<name>.credentials` when a platform is check-only (no auto_buy on any item)** — **RESOLVED in Plan 03 (pydantic config schema)**: `email`/`password` are required whenever `enabled: true`. Plugins that don't need login override `login()` to no-op (ABC default already does this). No "check-only" vs "purchase-capable" modeling in Phase 1.
   - Original analysis:
   - What we know: D-04 says CVV is collected only for platforms that have at least one `auto_buy: true` item.
   - What's unclear: Should `credentials.email` and `credentials.password` also be conditionally optional? Today's bot needs them to sign in even on check-only flows because some sites only show stock to logged-in users.
   - Recommendation: Make `email`/`password` required when `enabled: true`. Plugins that don't need login can override `login()` to no-op (the ABC default already does this); Phase 1 doesn't need to model "check-only" vs "purchase-capable" platforms.

2. **Should `requirements.txt` use hash pins (`==X.Y.Z --hash=sha256:...`)?** — **RESOLVED in Plan 01 (test infra and pinned deps)**: Plain `==X.Y.Z` pins for Phase 1. Hash pins deferred to a future hardening phase.
   - Original analysis:
   - What we know: CONTEXT.md Claude's Discretion list flags this.
   - What's unclear: Hash pins are stronger supply-chain security but a maintenance burden (every bump requires regenerating hashes, typically via `pip-tools`).
   - Recommendation: Plain `==X.Y.Z` for Phase 1. Hash pins can be added later (and are a natural fit for a future Phase 3 community-docs hardening task) without breaking anything.

3. **REQUIREMENTS.md edit per CORE-01 revision (D-01)** — **RESOLVED in Plan 01 Wave 0**: REQUIREMENTS.md edit (CORE-01 drops the `driver` parameter) is bundled into Plan 01's Wave 0 tasks alongside requirements.txt cleanup.
   - Original analysis:
   - What we know: CONTEXT.md says CORE-01 wording must change to drop the `driver` parameter.
   - What's unclear: Whether the edit is part of Phase 1 or a one-line docs commit before planning starts.
   - Recommendation: Include as a small task in Phase 1 (Wave 0 alongside requirements.txt cleanup). Treats REQUIREMENTS.md as a code artifact, keeps the audit trail, and the verifier can confirm the edit.

4. **Reconcile STATE.md staleness** — **DEFERRED**: STATE.md doc-hygiene (bump 5 phases/39 reqs to 6 phases/44 reqs to match ROADMAP) is out of Phase 1 scope. Phase 1 is foundations/security; a STATE.md sync belongs in a separate planning-doc cleanup commit and is not a Phase 1 acceptance criterion.
   - Original analysis:
   - What we know: STATE.md says 5 phases / 39 reqs; ROADMAP is authoritative at 6 phases / 44 reqs.
   - What's unclear: Whether STATE.md regenerates automatically as plans complete or requires a one-time fix.
   - Recommendation: One-line docs commit during Phase 1 planning to bump the numbers. Not a Phase 1 acceptance criterion.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python ≥ 3.11 | INFRA-01 (target floor) | Verify at task time | — | Hard requirement; user upgrades if missing |
| Google Chrome browser | Selenium driver target | Assumed installed (existing project requirement) | — | None — bot does not run without Chrome |
| ChromeDriver binary | Selenium | Auto-downloaded by webdriver-manager 4.0.2 | — | webdriver-manager is the fallback |
| pip / venv | Install pinned requirements | stdlib | — | — |
| TTY stdin | D-04 CVV prompt path | Per-environment | — | SHOPBOT_ALLOW_CVV_ENV opt-in env var (D-05) |

**Missing dependencies with no fallback:** None at planning time. (Python version check happens during install or runtime guard per Pitfall 6.)

**Missing dependencies with fallback:** TTY stdin → env-var path with explicit opt-in.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (currently installed: 8.3.2; pin to 8.3.4 or current stable 8.x) |
| Config file | None today; planner may add `pyproject.toml` `[tool.pytest.ini_options]` section if desired |
| Quick run command | `pytest -x -q` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CORE-01 | ABC has `check_availability` and `auto_buy` abstract; cannot be instantiated raw | unit | `pytest tests/test_plugin_base.py::test_cannot_instantiate_abstract -x` | ❌ Wave 0 |
| CORE-02 | `PLUGIN_API_VERSION == 1`; `login` and `detect_captcha` defaults are no-ops | unit | `pytest tests/test_plugin_base.py -x` | ❌ Wave 0 |
| CORE-05 | Missing required field produces actionable Pydantic error mentioning field path | unit | `pytest tests/test_config_schema.py::test_missing_field_message -x` | ❌ Wave 0 |
| CORE-06 | `platforms.amazon.credentials.email` resolves from YAML | unit | `pytest tests/test_config_schema.py::test_per_platform_credentials -x` | ❌ Wave 0 |
| CORE-07 | Old `app.amz_email` triggers ValidationError with migration message | unit | `pytest tests/test_config_schema.py::test_deprecated_amz_email_hard_fails -x` | ❌ Wave 0 |
| SEC-01 | Env var `SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL` overrides YAML | unit | `pytest tests/test_config_schema.py::test_env_var_overrides_yaml -x` | ❌ Wave 0 |
| SEC-02 | `collect_cvvs` invokes getpass once per auto_buy platform, never logs | unit (with monkeypatch on getpass.getpass) | `pytest tests/test_credentials.py::test_cvv_prompt_once -x` | ❌ Wave 0 |
| SEC-03 | Driver build args do NOT contain `--disable-web-security` | unit (inspect Options.arguments) | `pytest tests/test_driver_setup.py::test_no_disable_web_security -x` | ❌ Wave 0 |
| SEC-04 | `build_driver` calls `execute_cdp_cmd` with the webdriver-hide source | unit (mock driver) | `pytest tests/test_driver_setup.py::test_cdp_webdriver_hide -x` | ❌ Wave 0 |
| SEC-05 | Driver options include a `--user-agent=` that does not contain `Selenium` or `HeadlessChrome` | unit | `pytest tests/test_driver_setup.py::test_real_user_agent -x` | ❌ Wave 0 |
| SEC-06 | README.md contains a disclaimer section (substring match) | smoke | `pytest tests/test_docs.py::test_readme_disclaimer -x` | ❌ Wave 0 |
| INFRA-01 | requirements.txt has no duplicates, all `==` pinned | unit (parse file) | `pytest tests/test_requirements.py::test_pinned_no_duplicates -x` | ❌ Wave 0 |
| INFRA-02 | `writeLog` does not open `config.yml` | unit (monkeypatch builtins.open or file mtime trick) | `pytest tests/test_logger.py::test_no_config_reread -x` | ❌ Wave 0 |
| INFRA-03 | `main.py` does not contain `sys.stdout = open(os.devnull` | unit (source grep) | `pytest tests/test_main_smoke.py::test_no_stdout_monkeypatch -x` | ❌ Wave 0 |

**Manual-only checks (acceptance, not automated):**
- D-05 non-TTY interactive behavior (visual confirmation: launch in IDE Run button, see helpful error)
- Real-world Chrome launch with stealth patches (visual confirmation Amazon does not insta-CAPTCHA)

### Sampling Rate
- **Per task commit:** `pytest -x -q` (fast unit suite)
- **Per wave merge:** `pytest` (full suite including new tests)
- **Phase gate:** Full suite green plus manual non-TTY and Chrome launch confirmation before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_plugin_base.py` — covers CORE-01, CORE-02
- [ ] `tests/test_config_schema.py` — covers CORE-05, CORE-06, CORE-07, SEC-01 (replaces existing tests/test_config.py which tests the old `load_config`)
- [ ] `tests/test_credentials.py` — covers SEC-02 + D-05 non-TTY logic with monkeypatched stdin
- [ ] `tests/test_driver_setup.py` — covers SEC-03, SEC-04, SEC-05, INFRA-03 (build_driver factory)
- [ ] `tests/test_logger.py` — covers INFRA-02
- [ ] `tests/test_requirements.py` — covers INFRA-01 (parses requirements.txt)
- [ ] `tests/test_docs.py` — covers SEC-06 README check
- [ ] `tests/test_main_smoke.py` — covers INFRA-03 monkey-patch removal
- [ ] `tests/conftest.py` — shared fixtures (sample AppConfig, mock driver, tmp_path config.yml)
- [ ] Existing `tests/test_config.py` is obsolete after `config.py` is rewritten — delete or rewrite
- [ ] Framework install: `pip install pytest==8.3.4` (existing 8.3.2 in worktree; pin to a stable 8.x)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes (we authenticate to Amazon/BestBuy on the user's behalf) | Credentials in env vars only (SEC-01); never persisted; existing manual passkey/MFA flow unchanged in Phase 1 |
| V3 Session Management | No | Browser-managed session cookies; out of scope for Phase 1 |
| V4 Access Control | No | Single-user CLI; no multi-tenant model |
| V5 Input Validation | Yes | pydantic v2 validates every config field (CORE-05); `extra="forbid"` rejects unknown keys (D-07) |
| V6 Cryptography | Partial | No hand-rolled crypto; CVV held in plain memory only (acceptable per OWASP CC-1: never persisted, process-lifetime only) |
| V7 Errors and Logging | Yes | Logger must never log credentials or CVV; existing `writeLog` only logs explicit message text (no auto-log of locals); INFRA-02 fix preserves this |
| V8 Data Protection | Yes | CVV in memory only; not in DB, logs, env files committed to git, or any disk artifact |
| V14 Configuration | Yes | requirements.txt pinning (INFRA-01) prevents supply-chain version drift; `extra="forbid"` Pydantic config (D-07) prevents typo-driven misconfig |

### Known Threat Patterns for Python + Selenium + YAML config

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Plaintext credentials in committed config | Information Disclosure | SEC-01: env vars; `.gitignore` already excludes `config.yml`; sample.config.yml uses placeholders only |
| YAML deserialization of untrusted input | Tampering / RCE | `yaml.safe_load` (used today) is safe; pydantic-settings YamlConfigSettingsSource also uses safe loading |
| Bot detection via `navigator.webdriver` / Selenium UA | Spoofing (defensive) | SEC-04 (CDP hide) + SEC-05 (real UA); SEC-03 removes `--disable-web-security` which is a detection signal |
| Credential leak via log message interpolation | Information Disclosure | All credential reads go through pydantic models; `writeLog` only writes explicit `f"..."` strings — no `repr(config)` style dumps |
| CVV persistence | PCI-DSS / Information Disclosure | SEC-02 + D-04: getpass at runtime, in-memory dict only, no disk write, no log line ever references the CVV value |
| TOCTOU on config.yml | Tampering | AppConfig loads once at startup; runtime changes ignored — acceptable for personal-use CLI |
| Process env-var leak via `/proc/<pid>/environ` | Information Disclosure | D-05 explicit warning in error message when SHOPBOT_*_CVV path is used; flagged as "trusted infrastructure only" |

## Project Constraints (from CLAUDE.md)

The repo's `CLAUDE.md` (project-level instructions) does not mandate workflow constraints beyond setup/run/test commands. The user's global CLAUDE.md mandates:

- All shell commands prefixed with `rtk` (handled by hook; impacts execution, not plan content).
- Approval gates before commits/pushes (Phase 1 plans must include explicit commit gates per task).
- No emojis, no em dashes, no horizontal lines (`---`) in any output. **This RESEARCH.md follows that constraint.**
- Functions under 30 lines; files under 300 lines; nesting depth max 3.
- camelCase for variables/functions in JS/TS; for Python the project follows snake_case (CONVENTIONS.md), which the global rule defers to project-specific patterns.
- Never commit secrets — Phase 1's whole purpose.

**Planner directive:** Phase 1 plans must add an explicit `Files to commit / Awaiting approval` step before any commit task. This matches the user's global CLAUDE.md "Before any git commit" gate.

## Sources

### Primary (HIGH confidence)
- pydantic v2 docs — https://docs.pydantic.dev/latest/ (sections: model_validator, BaseSettings, settings_customise_sources, YamlConfigSettingsSource, field value priority, error handling)
- pydantic-settings docs — https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Python stdlib `abc` — https://docs.python.org/3/library/abc.html
- Python stdlib `getpass` — https://docs.python.org/3/library/getpass.html
- Selenium 4 Python — https://selenium-python.readthedocs.io/api.html (Service, ChromeOptions)
- Chrome DevTools Protocol — https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-addScriptToEvaluateOnNewDocument
- Python release schedule — https://devguide.python.org/versions/ (3.8 EOL Oct 2024)
- PEP 621 (pyproject.toml metadata) — https://packaging.python.org/en/latest/specifications/pyproject-toml/
- Verified package versions via `pip index versions <pkg>` 2026-05-02:
  - pydantic 2.13.3
  - pydantic-settings 2.14.0
  - selenium 4.43.0
  - webdriver-manager 4.0.2
  - pyyaml 6.0.3
  - pygame 2.6.1
  - colorama 0.4.6
  - requests 2.33.1
  - pytest 9.0.3 (installed 8.3.2)

### Secondary (MEDIUM confidence)
- Pydantic v2 migration guide — https://docs.pydantic.dev/latest/migration/ (cross-verified by being on the same official site)
- ShopPyBot project research summary — `.planning/research/SUMMARY.md` (internal source, recommendations align with external docs)
- ShopPyBot codebase analysis — `.planning/codebase/{STRUCTURE,CONCERNS,STACK,CONVENTIONS}.md` (internal, fresh as of 2026-04-19)

### Tertiary (LOW confidence)
- Current Chrome stable major version (used in Pattern 4 example UA) — flagged as A3 in Assumptions Log; planner verifies at task time

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified against pip registry today
- Architecture / patterns: HIGH — every pattern maps to documented stdlib or pydantic-settings feature
- Pitfalls: HIGH for #1, #3, #5, #6 (verified against docs); MEDIUM for #2, #4 (extrapolated from D-07 / D-05 design intent)
- Security: HIGH — every SEC-* requirement has a single, well-known stdlib or library mechanism

**Research date:** 2026-05-02
**Valid until:** 2026-06-01 (30 days; the only fast-moving piece is the Chrome UA string, which is informational not load-bearing)
