# Phase 1: Foundations + Security - Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 17 (8 new, 9 modified)
**Analogs found:** 14 / 17 (3 new files have no close analog; planner uses RESEARCH.md patterns)

## File Classification

### New files (8)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `plugin_base.py` | contract / ABC | request-response (interface) | (no analog) | none — use RESEARCH Pattern 1 |
| `config_schema.py` | config / model | startup-load + validate | `config.py` | role-match (replaces) |
| `credentials.py` | secrets / runtime input | startup-prompt + env-read | (no analog) | none — use RESEARCH Pattern 3 |
| `pyproject.toml` | build-system metadata | static config | `requirements.txt` | partial (build config) |
| `tests/test_plugin_base.py` | test (unit) | assert | `tests/test_models.py` | role-match |
| `tests/test_config_schema.py` | test (unit) | assert + tmp_path | `tests/test_config.py` | exact (replaces) |
| `tests/test_credentials.py` | test (unit) | assert + monkeypatch | `tests/test_config.py` | role-match |
| `tests/test_driver_setup.py` | test (unit) | assert + mock | `tests/test_models.py` | role-match |
| `tests/test_logger.py` | test (unit) | assert + monkeypatch | `tests/test_utils.py` | role-match |
| `tests/test_requirements.py` | test (unit, smoke) | file-parse assert | `tests/test_utils.py` | partial |
| `tests/test_docs.py` | test (unit, smoke) | file-substring assert | `tests/test_utils.py` | partial |
| `tests/test_main_smoke.py` | test (unit, smoke) | source grep assert | `tests/test_utils.py` | partial |
| `tests/conftest.py` | test fixtures | shared | (no analog) | none — pytest convention |

### Modified files (8)

| Modified File | Role | Data Flow | Analog (itself, prior to edit) | Change Type |
|---------------|------|-----------|-------------------------------|-------------|
| `main.py` | orchestrator / entrypoint | startup + polling loop | `main.py` (current) | rewrite startup, keep loop |
| `config.py` | config loader | startup-load | `config.py` (current) | rewrite to wrap AppConfig OR delete |
| `logger.py` | cross-cutting infra | log emit | `logger.py` (current) | refactor: drop per-call yaml load |
| `amazon_bot.py` | retailer bot | request-response | `amazon_bot.py` (current) | minimal: read creds from AppConfig.platforms.amazon, not config['app'] |
| `bestbuy_bot.py` | retailer bot | request-response | `bestbuy_bot.py` (current) | minimal: read creds from AppConfig + cvvs dict |
| `requirements.txt` | dependency manifest | static | `requirements.txt` (current) | dedup, pin all `==X.Y.Z`, add pydantic + pydantic-settings[yaml] |
| `tests/test_config.py` | test (obsolete) | — | itself | delete (replaced by test_config_schema.py) |
| `sample.config.yml` | docs / template | static | `sample.config.yml` (gitignored sibling of config.yml) | update: remove credential keys, add platforms.<name> blocks pointing at env vars |
| `.planning/REQUIREMENTS.md` | docs (spec) | static | itself | edit CORE-01 wording per D-01 (drop `driver` param) |

## Pattern Assignments

### `plugin_base.py` (NEW — contract / ABC)

**Analog:** None in current codebase (no plugin/ABC pattern exists).

**Source pattern:** RESEARCH.md Pattern 1 (lines 247-312). Use verbatim with one adjustment: `__init__` must NOT raise `NotImplementedError` — that prevents subclasses from calling `super().__init__()`. Use `pass` body or accept `platform_config` and store nothing (subclasses override).

**Imports convention to copy from `models.py` lines 1-2:**
```python
import sqlite3
import os
```
Style: stdlib-only, top of file, no aliasing. Apply same minimal-import style to `plugin_base.py`.

**No driver dependency in this file** (per D-02: ABC must not import config or any driver lib).

---

### `config_schema.py` (NEW — config / model, replaces `config.py`)

**Analog:** `config.py` (lines 1-7) — current 7-line `yaml.safe_load` shim.

**Current pattern (to REPLACE entirely):**
```python
# config.py — current
import yaml

def load_config():
    with open('config.yml', 'r') as file:
        return yaml.safe_load(file)

config = load_config()
```

**Replacement source:** RESEARCH.md Pattern 2 (lines 314-419). `AppConfig(BaseSettings)` with:
- `model_config = SettingsConfigDict(extra="forbid", env_nested_delimiter="__", env_prefix="SHOPBOT_", yaml_file="config.yml")`
- `settings_customise_sources` returning `(init_settings, env_settings, YamlConfigSettingsSource(settings_cls))` so env wins over YAML (SEC-01)
- `@model_validator(mode="before")` named `reject_deprecated_keys` for D-06 hard-fail

**Field surface to model from existing `config.yml` consumers:**

From `main.py` line 20: `config['selenium']['driver_path']` → `SeleniumConfig.driver_path: str`
From `main.py` lines 82-83: `config['debug'].get('test_mode', False)`, `config['app'].get('open_browser', False)` → `DebugConfig.test_mode: bool`, top-level `open_browser: bool` (NOT under `app`; `app` namespace is removed)
From `main.py` line 79: `config['available']['items']` with `name`, `link`, `auto_buy`, `quantity` → `ItemConfig` + `AvailableConfig.items: list[ItemConfig]`
From `bestbuy_bot.py` and `main.py` line 124: `config['app']['bb_email']`, `bb_password`, `bb_cvv` → `platforms.bestbuy.credentials.{email,password}` (cvv runtime only)
From `amazon_bot.py` lines 58-59: `config['app']['amz_email']`, `amz_pwd` → `platforms.amazon.credentials.{email,password}`

**Deprecated-key list (for `reject_deprecated_keys` validator):** `app.amz_email`, `app.amz_pwd`, `app.bb_email`, `app.bb_password`, `app.bb_cvv`. Source: `tests/test_config.py` lines 8-13 enumerates them all in the existing sample.

---

### `credentials.py` (NEW — secrets / runtime input)

**Analog:** None (no getpass / env-resolution pattern exists).

**Source pattern:** RESEARCH.md Pattern 3 (lines 427-474). Use verbatim. Key behaviors:
- TTY check: `sys.stdin.isatty()`
- Env opt-in: `os.environ.get("SHOPBOT_ALLOW_CVV_ENV", "").lower() == "true"`
- Per-platform env var: `f"SHOPBOT_{name.upper()}_CVV"`
- Loop only over platforms with `enabled=True` AND any item with `auto_buy=True`

**Stderr error pattern to match:** Use `sys.stderr.write(...)` + `sys.exit(1)` (RESEARCH lines 452-465). Existing codebase uses `exit(1)` (`main.py` line 26); upgrade to `sys.exit(1)` for new code.

**No logging of CVV values, ever** (SEC-02). Do not pass cvvs through `writeLog`.

---

### `main.py` (MODIFIED — orchestrator / entrypoint)

**Analog:** `main.py` itself.

**Three required edits:**

1. **Replace startup block** (current lines 38-44): swap `load_config()` for `AppConfig()` instantiation. Pattern from RESEARCH lines 657-677.

2. **Extract driver build** (current lines 45-75): move the ChromeOptions setup, `Service(...)`, `webdriver.Chrome(...)`, and stdout-monkey-patch block into a new `build_driver(driver_path, log_path)` factory. Apply SEC-03/04/05 + INFRA-03 fixes per RESEARCH Pattern 4 (lines 480-512):
   - DELETE line 60: `chromeOptions.add_argument("--disable-web-security")` (SEC-03)
   - DELETE lines 67-69, 73-75: stdout/stderr monkey-patch (INFRA-03)
   - ADD: `opts.add_argument(f"--user-agent={CHROME_UA}")` (SEC-05)
   - CHANGE line 46: `service = Service(driver_path)` → `service = Service(executable_path=driver_path, log_path="logs/chromedriver.log")` (INFRA-03)
   - ADD after `webdriver.Chrome(...)`: `driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"})` (SEC-04)

3. **Add Python version guard at top** (Pitfall 6, RESEARCH lines 647-652):
```python
import sys
if sys.version_info < (3, 11):
    sys.exit(f"ShopPyBot requires Python 3.11+. Detected: {sys.version}")
```

4. **Polling loop unchanged** (current lines 85-136). Domain routing stays. Plugin registry is Phase 2.

5. **Replace `config['app']['bb_*']` reads** at line 124: substitute with `app_config.platforms['bestbuy'].credentials.email`, `.password`, and `cvvs['bestbuy']`.

---

### `logger.py` (MODIFIED — cross-cutting infra)

**Analog:** `logger.py` itself (lines 1-37).

**Anti-pattern to remove** (lines 7-9 + line 16):
```python
def load_settings():
    with open('config.yml', 'r') as file:
        return yaml.safe_load(file)
# ...
def writeLog(message, type, writeTofile=True):
    settings = load_settings()  # ← per-call yaml load (INFRA-02 target)
    loggingLevel = settings.get('debug', {}).get('logging_level', 5)
```

**Replacement source:** RESEARCH.md Pattern 5 (lines 521-569). Add module-level `_logging_level` + `configure(level: int)` function called once from `main.py` after `AppConfig()` succeeds.

**Preserve verbatim from current `logger.py`:**
- Function name `writeLog` (CONVENTIONS.md keeps legacy name)
- LOG_LEVELS dict structure (lines 18-26)
- Color/timestamp print format (line 29): `f"{color}[{type.upper()}][...] {message}{Style.RESET_ALL}"`
- File-write block (lines 30-37); refactored into `_write_to_file` helper (RESEARCH lines 565-568)

**Drop entirely:**
- `import yaml` (line 5) — no longer needed
- `setup_logger()` (lines 11-13) — vestigial, never used by callers besides `main.py` line 139 which can also be deleted

---

### `amazon_bot.py` (MODIFIED — retailer bot)

**Analog:** itself.

**Minimal Phase 1 change.** Plugin extraction is Phase 2 — Phase 1 only changes the credential read sites:

**Lines 58-59 (`amz_sign_in` body):**
```python
# BEFORE
email = config['app']['amz_email']
password = config['app']['amz_pwd']

# AFTER (Phase 1 — config is now AppConfig instance)
email = config.platforms['amazon'].credentials.email
password = config.platforms['amazon'].credentials.password
```

The function signature (`amz_sign_in(driver, config)`) stays. The `config` param now receives `AppConfig` instead of a dict. `auto_buy_amazon_item` line 125 already passes `config` through — no caller-site change needed.

**Anti-pattern noted, NOT fixed in Phase 1:** bare `except:` at lines 17, 33, 40, 116. RESEARCH calls these out (line 577) — leave them for a future cleanup phase to keep Phase 1 scoped.

---

### `bestbuy_bot.py` (MODIFIED — retailer bot)

**Analog:** itself.

**Minimal Phase 1 change.** `auto_buy_bestbuy_item` currently takes `email`, `password`, `cvv` as positional args (line 40). Two valid options:

**Option A (smaller diff):** Caller in `main.py` line 124 changes to pull from `AppConfig` + `cvvs` dict; `bestbuy_bot.py` body unchanged:
```python
# main.py line 124 BEFORE
auto_buy_bestbuy_item(driver, link, config['app']['bb_email'], config['app']['bb_password'], config['app']['bb_cvv'], quantity)
# AFTER
auto_buy_bestbuy_item(driver, link, app_config.platforms['bestbuy'].credentials.email,
                      app_config.platforms['bestbuy'].credentials.password,
                      cvvs['bestbuy'], quantity)
```

**Option B (Phase-2-aligned):** Change signature to `auto_buy_bestbuy_item(driver, item_url, platform_config, cvv, quantity)`. Closer to D-02 plugin shape but is "Phase 2 work in Phase 1 clothing" — defer.

**Recommendation:** Option A. Keeps Phase 1 minimal; Phase 2 rewrites the file as a plugin anyway.

---

### `requirements.txt` (MODIFIED — dependency manifest)

**Analog:** itself (lines 1-12).

**Current state — duplicates and zero pins:**
```
pytest
selenium
webdriver-manager
pyyaml
selenium       ← dup
pyyaml         ← dup
colorama
pygame
urllib3
requests
webdriver_manager  ← dup (different normalization)
```

**Replacement (from RESEARCH lines 166-175):**
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

`pyyaml` becomes transitive via `pydantic-settings[yaml]`; `urllib3` via `requests`. Both can be dropped from explicit list. Hash pins deferred (RESEARCH Open Question #2).

---

### `pyproject.toml` (NEW — build-system metadata)

**Analog:** None (file does not exist).

**Source:** RESEARCH.md line 179, "PEP 621 / packaging.python.org/en/latest/specifications/pyproject-toml/".

**Minimum content:**
```toml
[project]
name = "shoppybot"
version = "0.1.0"
requires-python = ">=3.11"
```

Optional: `[tool.pytest.ini_options]` section to set `testpaths = ["tests"]` (RESEARCH line 789 mentions this as a planner choice).

---

### `tests/test_plugin_base.py` (NEW — unit test)

**Analog:** `tests/test_models.py` (lines 1-30) — closest existing pytest unit pattern.

**Test structure to copy:**
```python
# tests/test_models.py lines 1-5 — import + fixture style
import os
import sqlite3
import pytest
from models import initialize_db, add_items, get_items, update_item_purchased, DB_PATH
```

**Apply to plugin tests** (RESEARCH Pattern 1 test block, lines 292-312):
```python
import pytest
from plugin_base import RetailerPlugin, PLUGIN_API_VERSION

def test_api_version_is_one():
    assert PLUGIN_API_VERSION == 1

def test_cannot_instantiate_abstract():
    with pytest.raises(TypeError):
        RetailerPlugin({})
```

No fixtures needed (ABC tests are stateless). Skip the `@pytest.fixture(scope='module')` setup pattern from `test_models.py`.

---

### `tests/test_config_schema.py` (NEW — replaces `tests/test_config.py`)

**Analog:** `tests/test_config.py` (lines 1-37) — closest existing config test.

**Pattern to copy from existing test** (lines 5-32):
```python
@pytest.fixture
def sample_config(tmp_path):
    config_content = """..."""
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content)
    return config_file
```

The `tmp_path` + `write_text` + `chdir` shape is exactly what RESEARCH lines 689-718 use. The migration path: keep the fixture skeleton, swap the YAML body to use `platforms.<name>.credentials.*`, and invoke `AppConfig()` instead of `load_config()`.

**Required test cases** (RESEARCH lines 794-806):
- `test_missing_field_message` (CORE-05)
- `test_per_platform_credentials` (CORE-06)
- `test_deprecated_amz_email_hard_fails` (CORE-07) — body in RESEARCH lines 689-702
- `test_env_var_overrides_yaml` (SEC-01) — body in RESEARCH lines 704-718

**Delete `tests/test_config.py`** — `load_config` no longer exists after `config.py` is rewritten.

---

### `tests/test_credentials.py` (NEW — unit test)

**Analog:** `tests/test_config.py` (closest pytest+monkeypatch usage in the codebase, even though current tests don't use monkeypatch — this is a new-pattern file).

**Required behaviors to test** (RESEARCH lines 802, Pitfall 4):
- `test_cvv_prompt_once` — monkeypatch `getpass.getpass` to return a fixed string, assert one call per auto_buy platform
- `test_non_tty_hard_fails` — monkeypatch `sys.stdin.isatty` to return False, assert `SystemExit(1)`
- `test_env_opt_in_path` — set `SHOPBOT_ALLOW_CVV_ENV=true` + `SHOPBOT_AMAZON_CVV=123`, assert returned dict

Use `monkeypatch.setenv`, `monkeypatch.setattr` — standard pytest fixtures.

---

### `tests/test_driver_setup.py` (NEW — unit test)

**Analog:** None precisely, but `tests/test_models.py` for the simple-assert structure.

**Strategy:** Test `build_driver` factory by inspecting the `Options` instance it produces (without launching real Chrome). Mock `webdriver.Chrome` with `unittest.mock.patch` to capture the `service=` and `options=` kwargs.

**Required tests** (RESEARCH lines 803-805):
- `test_no_disable_web_security` — assert `"--disable-web-security"` not in `options.arguments`
- `test_cdp_webdriver_hide` — assert mock_driver.execute_cdp_cmd called with `"Page.addScriptToEvaluateOnNewDocument"` and source containing `navigator.webdriver`
- `test_real_user_agent` — assert at least one option matches `--user-agent=` AND does NOT contain `Selenium` or `HeadlessChrome`

---

### `tests/test_logger.py` (NEW — unit test)

**Analog:** `tests/test_utils.py` (lines 1-6) — closest single-function unit test.

**Test pattern:** Use `monkeypatch.setattr("builtins.open", ...)` to detect any call to `open('config.yml')` during a `writeLog` invocation; assert zero such calls (INFRA-02).

Alternative simpler check: import `logger`, `logger.configure(3)`, call `writeLog("x", "INFO")`, then assert that the `_logging_level` module global is set and that no file-mtime change occurs on `config.yml`.

---

### `tests/test_requirements.py`, `tests/test_docs.py`, `tests/test_main_smoke.py` (NEW — smoke tests)

**Analog:** `tests/test_utils.py` (lines 1-6) — minimal one-function-per-file pytest style.

**Pattern:** Read the file, assert text properties:
- `test_requirements.py`: `pathlib.Path("requirements.txt").read_text()`; assert no duplicate package names; assert every line has `==`.
- `test_docs.py`: `pathlib.Path("README.md").read_text()`; assert disclaimer substring exists (e.g., "personal use", "TOS", "account risk").
- `test_main_smoke.py`: `pathlib.Path("main.py").read_text()`; assert `"sys.stdout = open(os.devnull"` not in source.

---

### `tests/conftest.py` (NEW — shared fixtures)

**Analog:** None (no `conftest.py` exists).

**Recommended fixtures** (RESEARCH line 829):
- `sample_app_config` (a valid `AppConfig` for tests that need one without hitting disk)
- `mock_driver` (a `MagicMock` matching the `webdriver.Chrome` surface)
- `tmp_config_yml` (writes a valid `config.yml` to `tmp_path` and `chdir`s into it)

---

### `sample.config.yml` (MODIFIED — docs / template)

**Analog:** itself (referenced from `tests/test_config.py` lines 7-29 as the ground truth for the OLD shape).

**Old shape (to remove):**
```yaml
app:
  amz_email: "your_amazon_email@example.com"
  amz_pwd: "your_amazon_password"
  bb_email: "your_bestbuy_email@example.com"
  bb_password: "your_bestbuy_password"
  bb_cvv: "your_bestbuy_cvv"
  open_browser: false
```

**New shape (per D-07 + SEC-01):**
```yaml
selenium:
  driver_path: "./chromedriver.exe"
debug:
  logging_level: 5
  test_mode: true
open_browser: false
platforms:
  amazon:
    enabled: true
    # credentials.email / password loaded from env vars:
    #   SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL
    #   SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__PASSWORD
    credentials:
      email: ""
      password: ""
  bestbuy:
    enabled: true
    # CVV prompted at runtime via getpass; opt-in env: SHOPBOT_BESTBUY_CVV (with SHOPBOT_ALLOW_CVV_ENV=true)
    credentials:
      email: ""
      password: ""
available:
  items: []
```

---

## Shared Patterns

### Logging
**Source:** `logger.py` `writeLog(message, type)` — the project standard.
**Apply to:** All new modules that need to emit user-visible output (`credentials.py` is the main consumer; `config_schema.py` should NOT log inside validators — pydantic raises ValidationError instead).

```python
from logger import writeLog
writeLog("Configured logging level: 3", "INFO")
```

**Existing convention** (every module follows this — see `main.py` line 9, `amazon_bot.py` line 5, `bestbuy_bot.py` line 5, `utils.py` line 3):
- Type strings: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"SUCCESS"`, `"ALWAYS"`, `"TRACE"`.
- Never log credentials, CVV, or full config repr (SEC-02, V7).

### Error Handling
**Source convention:** Existing code uses `try / except Exception as e` + `writeLog(f"Error ...: {e}", "ERROR")` (e.g., `amazon_bot.py` lines 52-54, `bestbuy_bot.py` lines 23-25).
**Apply to:** All new code that wraps third-party calls. Do NOT use bare `except:` (CONVENTIONS.md, RESEARCH line 577).

For startup-fatal errors (config invalid, non-TTY without opt-in), use:
```python
sys.stderr.write("ERROR: ...\n")
sys.exit(1)
```
This matches the new pattern in `credentials.py` (RESEARCH lines 460-465). Existing `main.py` line 26 uses bare `exit(1)`; new code should prefer `sys.exit(1)` with explicit `sys` import.

### File-system paths
**Source:** `models.py` line 4 + `utils.py` line 6 use `os.path.join` with `os.path.dirname(__file__)`. RESEARCH (line 156) recommends `pathlib` for new code. Both are acceptable; `pathlib.Path(__file__).parent / "logs"` is preferred for new files but is not mandatory.

### Test fixture style
**Source:** `tests/test_config.py` lines 5-32 (`tmp_path` + `write_text` returning a path) and `tests/test_models.py` lines 6-18 (`@pytest.fixture(scope='module')` with setup/teardown via `yield`).
**Apply to:** All new test files. Prefer module-scoped fixtures only when DB or expensive resources are involved; function-scoped for everything else.

---

## No Analog Found

Files/patterns with no close existing match. Planner uses RESEARCH.md content directly:

| File | Role | Reason |
|------|------|--------|
| `plugin_base.py` | ABC contract | No abstract base class exists in the codebase. Use RESEARCH Pattern 1 verbatim. |
| `credentials.py` | secret prompt + env resolution | No `getpass` usage exists; no env-var convention exists. Use RESEARCH Pattern 3 verbatim. |
| `tests/conftest.py` | shared test fixtures | No `conftest.py` exists; current tests redeclare fixtures per file. Apply pytest standard convention. |

---

## Metadata

**Analog search scope:** repo root (`*.py`), `tests/` (`*.py`), `requirements.txt`. Excluded: `_deprecated/`, `.planning/`.
**Files scanned:** 13 source + 4 test + 1 manifest = 18.
**Pattern extraction date:** 2026-05-02.
