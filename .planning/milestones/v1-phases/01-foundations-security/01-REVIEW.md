---
phase: 01-foundations-security
reviewed: 2026-06-02T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - core/plugin_base.py
  - core/config_schema.py
  - core/__init__.py
  - main.py
  - logger.py
  - requirements.txt
  - sample.config.yml
  - .env.example
  - README.md
  - pyproject.toml
  - tests/conftest.py
  - tests/test_plugin_base.py
  - tests/test_config_schema.py
  - tests/test_logger.py
  - tests/test_utils.py
  - tests/test_models.py
  - tests/test_config.py
findings:
  critical: 4
  warning: 6
  info: 4
  total: 14
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-06-02
**Depth:** standard
**Files Reviewed:** 14 (plus 3 test files)
**Status:** issues_found

## Summary

Phase 1 correctly removes `--disable-web-security`, wires `AppConfig` at startup, and keeps credentials out of config files. Four critical defects were found: (1) `make_tiny` sends item URLs over plaintext HTTP, leaking purchase intent; (2) `update_item_purchased` is never called after a successful purchase in `main.py`, so the bot will re-attempt to buy already-purchased items on every restart; (3) `_active_yaml_file` is a mutable class-level attribute with a race window that will silently corrupt config in any concurrent-test or future async context; (4) `models.py` never creates the `data/` directory before attempting to open the SQLite DB there, causing a guaranteed crash on first run. Six warnings cover missing response-error handling, CVV prompt not conditioned on `test_mode`, silent swallowing of all Selenium exceptions in `bestbuy_bot.py`, a thread-safety caveat on `_LOGGING_LEVEL`, a missing `pydantic` pin, and a README version mismatch. Four info items cover code style and documentation gaps.

## Critical Issues

### CR-01: `make_tiny` sends item URLs over unencrypted HTTP

**File:** `main.py:34`
**Issue:** The TinyURL API call uses `http://` not `https://`. Every item URL being monitored (including Amazon product URLs with referral parameters) is transmitted in plaintext. This is a privacy and anti-detection risk: a network observer learns exactly which products the bot is watching. TinyURL does respond on HTTPS.
**Fix:**
```python
request_url = f'https://tinyurl.com/api-create.php?url={url}'
```

### CR-02: `update_item_purchased` is never called from `main.py` after a successful purchase

**File:** `main.py:148-181`
**Issue:** After `auto_buy_amazon_item` or `auto_buy_bestbuy_item` returns, `main.py` never calls `update_item_purchased(link)`. The `purchased` flag in SQLite is never set via the main loop. `amazon_bot.py` does call it internally (line 184), but `auto_buy_bestbuy_item` does not (this is the PLG-02 known gap). More critically, even if `amazon_bot.py` sets the flag, the bot re-reads items from the DB each loop iteration via `get_items()`, so a restart will not re-trigger Amazon; but BestBuy purchases will be re-attempted on every restart because the flag is never set. REQUIREMENTS.md lists this as a PLG-02 fix in Phase 2, but the current `main.py` loop makes no provision to set the flag and provides no guard. A successful BestBuy purchase in production will be retried indefinitely.
**Fix:** After each confirmed auto-buy call succeeds, call `update_item_purchased(link)`:
```python
# BestBuy auto-buy path (main.py ~line 178)
result = auto_buy_bestbuy_item(driver, link, bb_email, bb_password, cvv, quantity)
if result:
    update_item_purchased(link)
    play_buy_sound()
```
Add a symmetric call after `auto_buy_amazon_item` (check its return value first, since it currently returns `None`).

### CR-03: `AppConfig._active_yaml_file` is a mutable class-level attribute with a race window

**File:** `core/config_schema.py:78-87`
**Issue:** `__init__` mutates `AppConfig._active_yaml_file` on the class (not the instance) before calling `super().__init__()`. The comment acknowledges this is "safe for single-threaded use". However:
1. The pytest suite already runs multiple test files that each call `AppConfig(yaml_file=...)`. If pytest-xdist or any future parallel runner is used, two concurrent `AppConfig()` constructions will race on the class attribute, and one will silently load the wrong config file.
2. The `settings_customise_sources` classmethod is called by pydantic during `super().__init__()`. There is no guarantee pydantic does not call it from a different thread internally (e.g., via validators).
3. A `PrivateAttr` with default factory, or a module-level threading.local, eliminates the race without changing the test-injection API.

**Fix:** Use a threading.local sentinel, or pass the path directly via a factory:
```python
import threading
_yaml_path_local = threading.local()

def __init__(self, yaml_file: Path | str | None = None, **values):
    _yaml_path_local.active = Path(yaml_file) if yaml_file is not None else _DEFAULT_YAML_PATH
    super().__init__(**values)

@classmethod
def settings_customise_sources(cls, settings_cls, init_settings,
                                env_settings, dotenv_settings, file_secret_settings):
    yaml_file = getattr(_yaml_path_local, "active", _DEFAULT_YAML_PATH)
    return (env_settings, YamlConfigSettingsSource(settings_cls, yaml_file=yaml_file))
```

### CR-04: `data/` directory is never created before SQLite connect

**File:** `models.py:4,9`
**Issue:** `DB_PATH = os.path.join('data', 'shop_py_bot.db')`. `sqlite3.connect(DB_PATH)` will raise `sqlite3.OperationalError: unable to open database file` if the `data/` directory does not exist. The README says "Created at `data/shop_py_bot.db` on first run", but there is no `os.makedirs` call in `initialize_db` or anywhere else in the reviewed files. This is a guaranteed crash on a fresh clone.
**Fix:**
```python
def initialize_db(delete=False):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if delete and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    ...
```

## Warnings

### WR-01: `make_tiny` does not check HTTP response status or handle network errors

**File:** `main.py:35-37`
**Issue:** `response = requests.get(request_url)` followed immediately by `return response.text`. If TinyURL is unreachable or returns a 4xx/5xx, `response.text` will contain an HTML error page or empty string, which is then logged as the short URL and potentially passed to `webbrowser.open`. No `response.raise_for_status()` or error guard is present. A network partition will silently corrupt the logged URL.
**Fix:**
```python
def make_tiny(url):
    request_url = f'https://tinyurl.com/api-create.php?url={url}'
    try:
        response = requests.get(request_url, timeout=5)
        response.raise_for_status()
        short_url = response.text.strip()
        if not short_url.startswith("http"):
            return url  # fall back to original URL
    except requests.RequestException as e:
        writeLog(f"TinyURL request failed: {e}", "WARNING")
        return url
    return short_url
```

### WR-02: CVV prompt fires even in `test_mode=True`

**File:** `main.py:123-127`
**Issue:** `needs_bb_autobuy` is computed purely from `item.auto_buy` and `item.link`, with no check on `test_mode`. In `test_mode: true` (which is the default in `sample.config.yml`), the bot still calls `collect_cvv()` and blocks at a `getpass` prompt before entering the main loop. A CI/CD or test environment with BestBuy items in config will deadlock or `SystemExit` on the non-interactive guard.
**Fix:**
```python
needs_bb_autobuy = (
    not test_mode
    and any("bestbuy.com" in item.link and item.auto_buy for item in cfg.available.items)
)
```

### WR-03: `bestbuy_bot.py` swallows all exceptions silently in `check_bestbuy_item`

**File:** `bestbuy_bot.py:23-25` (not in this phase's file list but called directly from `main.py` and affects phase correctness)
**Issue:** `except Exception as e: writeLog(...); return False` catches everything including `WebDriverException` (browser crash, CDP disconnect). A crashed browser silently returns `False` for every item, so the bot loops forever appearing healthy while never detecting availability. CLAUDE.md forbids silent exception swallowing.
**Fix:** Re-raise `WebDriverException` (or any non-timeout exception) after logging, or propagate to the main loop for a restart decision.

### WR-04: `_LOGGING_LEVEL` module-level cache in `logger.py` reads `config.yml` relative to CWD

**File:** `logger.py:9`
**Issue:** `open('config.yml', 'r')` uses a relative path, resolved at import time against whatever the process CWD is. If `logger.py` is imported before the caller sets CWD to the repo root (e.g., from a test that uses `tmp_path` but hasn't called `monkeypatch.chdir`), the logging level silently defaults to 5 without any indication the config was not found. This also means the cached level reflects CWD at import time, not the config actually used by `AppConfig`. These two configs can diverge.
**Fix:** Use `Path(__file__).parent.parent / "config.yml"` (same pattern used by `config_schema.py`) so the path is always repo-root-relative:
```python
_CONFIG_PATH = Path(__file__).parent / "config.yml"

def _load_logging_level() -> int:
    try:
        with open(_CONFIG_PATH, 'r') as file:
            ...
```

### WR-05: `pydantic` is not pinned in `requirements.txt`

**File:** `requirements.txt:4`
**Issue:** `pydantic-settings[yaml]==2.14.0` depends on `pydantic` as a transitive dependency but `pydantic` is not listed with a version pin. `pydantic-settings` 2.14.0 requires `pydantic>=2.7.0`. A future `pip install -r requirements.txt` may pull a newer pydantic with breaking API changes (pydantic v2 has historically made breaking minor-version changes to `model_validator` behavior). INFRA-01 requires exact pins.
**Fix:**
```
pydantic==2.10.6
pydantic-settings[yaml]==2.14.0
```
(Pin to whatever version `pydantic-settings==2.14.0` resolves to; run `pip show pydantic` after install to confirm.)

### WR-06: `test_config.py` fixture embeds legacy-format credentials as string literals

**File:** `tests/test_config.py:10-17`
**Issue:** The `sample_config` fixture writes a YAML blob containing `"your_amazon_email@example.com"`, `"your_amazon_password"`, `"your_bestbuy_cvv"` as string values. These are placeholder strings, not real secrets, so this is not a credential leak. However, the test exercises the old `config.py` singleton (pre-Phase-1 schema) and asserts `cfg["app"]["amz_email"] == "your_amazon_email@example.com"`. This test validates legacy behavior that Phase 1 explicitly deprecated (CORE-07). It will continue passing while the legacy path exists, masking whether the migration warning actually fires. This is a test correctness concern rather than a security one.
**Fix:** Either delete this test (the old config.py path is untouched but not the subject of Phase 1) or convert it to verify that loading a legacy config triggers the `DeprecationWarning` via `AppConfig`, mirroring `test_legacy_key_warning` in `test_config_schema.py`.

## Info

### IN-01: `plugin_base.py` uses `dict` type annotation for `config` parameter instead of `AppConfig`

**File:** `core/plugin_base.py:19,23`
**Issue:** `auto_buy(self, driver, url: str, config: dict)` and `login(self, driver, config: dict)` type `config` as `dict`. Phase 1 introduced `AppConfig` as the canonical config type. Using `dict` means plugins can be written against an untyped dict API, losing all validation and IDE autocomplete benefits. When Phase 2 migrates plugins to `AppConfig`, this will be a silent type mismatch.
**Fix:** Import and use `AppConfig`:
```python
from core.config_schema import AppConfig

def auto_buy(self, driver, url: str, config: AppConfig) -> bool: ...
def login(self, driver, config: AppConfig) -> None: ...
```

### IN-02: README still states "Python 3.8+" requirement

**File:** `README.md:38`
**Issue:** The Prerequisites section says "Python 3.8+" while `pyproject.toml` requires `>=3.11` and `requirements.txt` has a comment `# python_requires >= 3.11`. The README is stale and will mislead users who try to run on 3.8-3.10 and hit syntax or API errors.
**Fix:** Change `README.md:38` to "Python 3.11+".

### IN-03: `sample.config.yml` contains unknown keys (`short_url`, `alert_type`, `type`) not in `AppConfig`

**File:** `sample.config.yml:22-23,27`
**Issue:** `available.short_url: true`, `available.alert_type: mp3`, and each item's `type: card_mtg` are present in the sample config but not modeled in `AvailableConfig` or `ItemConfig`. `AppConfig` is configured with `extra="ignore"` so these are silently dropped. This is safe but misleading: users who copy the sample config will think these fields do something. The sample config should either model these fields or remove them.
**Fix:** Remove the three unrecognized keys from `sample.config.yml`, or add them to the schema with appropriate types.

### IN-04: `core/__init__.py` is empty

**File:** `core/__init__.py`
**Issue:** The file exists but is empty (0 bytes beyond the newline). This is not a bug, but it means `from core import AppConfig` will fail; users must write `from core.config_schema import AppConfig`. If `core` is intended as a public API surface, re-exporting from `__init__.py` would be cleaner. If it is just a namespace package, the file is fine as-is.
**Fix:** If public API is desired: `from core.config_schema import AppConfig, PLUGIN_API_VERSION` in `core/__init__.py`. Otherwise, no action needed.

---

_Reviewed: 2026-06-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
