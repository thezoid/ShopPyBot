---
phase: 01-foundations-security
plan: 03
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - config_schema.py
  - sample.config.yml
  - tests/test_config_schema.py
  - tests/test_config.py
  - .planning/REQUIREMENTS.md
autonomous: true
requirements:
  - CORE-05
  - CORE-06
  - CORE-07
  - SEC-01
tags:
  - pydantic
  - pydantic-settings
  - config
  - validation

must_haves:
  truths:
    - "AppConfig() succeeds when given a well-formed config.yml"
    - "AppConfig() raises ValidationError naming the missing field path when config.yml omits a required field"
    - "AppConfig() raises ValueError with a migration block when config.yml contains app.amz_email, app.amz_pwd, app.bb_email, app.bb_password, or app.bb_cvv"
    - "Setting SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL in env overrides the YAML value"
    - "Unknown top-level keys in config.yml are rejected (extra='forbid')"
    - "REQUIREMENTS.md CORE-01 wording matches D-01 (no `driver` parameter on ABC methods)"
    - "sample.config.yml demonstrates the new schema with no plaintext credentials"
  artifacts:
    - path: "config_schema.py"
      provides: "AppConfig + nested models + reject_deprecated_keys validator"
      contains: "class AppConfig(BaseSettings)"
      min_lines: 80
    - path: "sample.config.yml"
      provides: "Documented template with platforms.<name> blocks and env-var pointers"
      contains: "platforms:"
    - path: "tests/test_config_schema.py"
      provides: "Validation contract tests"
      min_lines: 60
  key_links:
    - from: "AppConfig.settings_customise_sources"
      to: "YamlConfigSettingsSource + env_settings"
      via: "source priority tuple (env wins over YAML)"
      pattern: "settings_customise_sources"
    - from: "AppConfig.reject_deprecated_keys"
      to: "config.yml top-level `app` block"
      via: "@model_validator(mode='before')"
      pattern: "reject_deprecated_keys"
---

<objective>
Replace the 7-line `config.py` yaml.safe_load shim with a Pydantic `AppConfig(BaseSettings)` that validates `config.yml` at startup, supports per-platform credential blocks, hard-fails on deprecated `app.amz_*` / `app.bb_*` keys with a copy-pasteable migration block, and lets environment variables override YAML for SEC-01.

Purpose: This unblocks Plan 05 (which wires AppConfig into main.py and the bot modules). The schema must exist and be tested before integration so Plan 05 only has to wire — not design.

Also edits `REQUIREMENTS.md` CORE-01 wording per D-01 (drop `driver` param) — the only plan in Phase 1 that touches REQUIREMENTS.md.

Output: `config_schema.py`, rewritten `sample.config.yml`, `tests/test_config_schema.py`, deletion of obsolete `tests/test_config.py`, REQUIREMENTS.md edit.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundations-security/01-CONTEXT.md
@.planning/phases/01-foundations-security/01-PATTERNS.md
@.planning/phases/01-foundations-security/01-RESEARCH.md
@config.py
@sample.config.yml
@tests/test_config.py
</context>

<interfaces>
<!-- Source: RESEARCH.md Pattern 2 (lines 314-419). Use VERBATIM. -->

```python
# config_schema.py — final shape per D-07 + D-06
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

class PlatformCredentials(BaseModel):
    email: str
    password: str
    # cvv is intentionally NOT here — runtime via getpass (SEC-02)

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
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                   dotenv_settings, file_secret_settings):
        # Order: init > env > YAML (env wins for SEC-01)
        return (init_settings, env_settings, YamlConfigSettingsSource(settings_cls))

    @model_validator(mode="before")
    @classmethod
    def reject_deprecated_keys(cls, data):
        # D-06: hard-fail; no auto-remap
        if not isinstance(data, dict):
            return data
        app = data.get("app", {}) if isinstance(data.get("app"), dict) else {}
        deprecated = {
            "amz_email":   "SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL or platforms.amazon.credentials.email",
            "amz_pwd":     "SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__PASSWORD",
            "bb_email":    "SHOPBOT_PLATFORMS__BESTBUY__CREDENTIALS__EMAIL or platforms.bestbuy.credentials.email",
            "bb_password": "SHOPBOT_PLATFORMS__BESTBUY__CREDENTIALS__PASSWORD",
            "bb_cvv":      "(removed) prompted at runtime via getpass; opt-in env SHOPBOT_BESTBUY_CVV with SHOPBOT_ALLOW_CVV_ENV=true",
        }
        found = {k: v for k, v in deprecated.items() if k in app}
        if found:
            lines = [
                "=== DEPRECATED CONFIG KEYS DETECTED ===",
                "config.yml uses old credential keys. Migrate before continuing:",
                "",
            ]
            for old, new in found.items():
                lines.append(f"  app.{old}  ->  {new}")
            lines.append("")
            lines.append("After migration, remove the entire `app:` section if empty.")
            lines.append("Bot will not start until migration is complete.")
            raise ValueError("\n".join(lines))
        return data
```

Note: PATTERNS.md keeps top-level `open_browser` (no `app` namespace). The `app:` block is now ONLY a deprecation trap.
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write failing config schema tests (RED)</name>
  <files>tests/test_config_schema.py, tests/test_config.py</files>
  <read_first>
    - tests/test_config.py (existing — analog for tmp_path fixture; will be DELETED)
    - .planning/phases/01-foundations-security/01-PATTERNS.md (section "tests/test_config_schema.py")
    - .planning/phases/01-foundations-security/01-RESEARCH.md lines 681-718 (test bodies)
    - tests/conftest.py (Plan 01 — for `tmp_config_yml` and `clean_env` fixtures)
  </read_first>
  <behavior>
    - test_valid_config_loads: a complete config.yml + populated env vars yields a usable AppConfig
    - test_missing_field_message: omitting `selenium.driver_path` raises ValidationError mentioning "selenium" and "driver_path"
    - test_extra_keys_rejected: an unknown top-level key (e.g. `bogus: 1`) raises ValidationError mentioning "bogus" and "extra"
    - test_per_platform_credentials: `config.platforms["amazon"].credentials.email` is reachable
    - test_deprecated_amz_email_hard_fails: setting `app.amz_email` raises ValueError whose message contains "DEPRECATED" and "SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL"
    - test_deprecated_bb_cvv_hard_fails: setting `app.bb_cvv` raises ValueError mentioning "SHOPBOT_BESTBUY_CVV" and "SHOPBOT_ALLOW_CVV_ENV"
    - test_env_var_overrides_yaml: yaml has `email: "yaml@x"`, env `SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL=env@x` -> AppConfig has `env@x`
  </behavior>
  <action>
    1. DELETE `tests/test_config.py` (it tests the old `load_config()` which is going away). Use `git rm tests/test_config.py` or remove file contents and stage deletion.
    2. Create `tests/test_config_schema.py`:
       ```python
       import pytest
       from pydantic import ValidationError


       VALID_YAML = """
       selenium:
         driver_path: ./chromedriver.exe
       debug:
         logging_level: 3
         test_mode: true
       open_browser: false
       platforms:
         amazon:
           enabled: true
           credentials:
             email: yaml@example.com
             password: yamlpw
       available:
         items: []
       """


       def _write_cfg(tmp_path, monkeypatch, body):
           (tmp_path / "config.yml").write_text(body)
           monkeypatch.chdir(tmp_path)


       def test_valid_config_loads(tmp_path, monkeypatch, clean_env):
           _write_cfg(tmp_path, monkeypatch, VALID_YAML)
           from config_schema import AppConfig
           cfg = AppConfig()
           assert cfg.selenium.driver_path == "./chromedriver.exe"
           assert cfg.debug.logging_level == 3
           assert cfg.platforms["amazon"].enabled is True
           assert cfg.platforms["amazon"].credentials.email == "yaml@example.com"


       def test_missing_field_message(tmp_path, monkeypatch, clean_env):
           bad = VALID_YAML.replace("selenium:\n  driver_path: ./chromedriver.exe\n", "")
           _write_cfg(tmp_path, monkeypatch, bad)
           from config_schema import AppConfig
           with pytest.raises(ValidationError) as exc:
               AppConfig()
           msg = str(exc.value)
           assert "selenium" in msg


       def test_extra_keys_rejected(tmp_path, monkeypatch, clean_env):
           _write_cfg(tmp_path, monkeypatch, VALID_YAML + "\nbogus_key: 1\n")
           from config_schema import AppConfig
           with pytest.raises(ValidationError) as exc:
               AppConfig()
           assert "bogus_key" in str(exc.value) or "extra" in str(exc.value).lower()


       def test_per_platform_credentials(tmp_path, monkeypatch, clean_env):
           _write_cfg(tmp_path, monkeypatch, VALID_YAML)
           from config_schema import AppConfig
           cfg = AppConfig()
           assert hasattr(cfg.platforms["amazon"].credentials, "email")
           assert hasattr(cfg.platforms["amazon"].credentials, "password")


       def test_deprecated_amz_email_hard_fails(tmp_path, monkeypatch, clean_env):
           bad = VALID_YAML + "\napp:\n  amz_email: leftover@example.com\n"
           _write_cfg(tmp_path, monkeypatch, bad)
           from config_schema import AppConfig
           with pytest.raises(Exception) as exc:
               AppConfig()
           msg = str(exc.value)
           assert "DEPRECATED" in msg
           assert "SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL" in msg


       def test_deprecated_bb_cvv_hard_fails(tmp_path, monkeypatch, clean_env):
           bad = VALID_YAML + "\napp:\n  bb_cvv: '123'\n"
           _write_cfg(tmp_path, monkeypatch, bad)
           from config_schema import AppConfig
           with pytest.raises(Exception) as exc:
               AppConfig()
           msg = str(exc.value)
           assert "SHOPBOT_BESTBUY_CVV" in msg
           assert "SHOPBOT_ALLOW_CVV_ENV" in msg


       def test_env_var_overrides_yaml(tmp_path, monkeypatch, clean_env):
           _write_cfg(tmp_path, monkeypatch, VALID_YAML)
           monkeypatch.setenv("SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL", "env@example.com")
           from config_schema import AppConfig
           cfg = AppConfig()
           assert cfg.platforms["amazon"].credentials.email == "env@example.com"
       ```
    3. Run `pytest -x tests/test_config_schema.py` — must fail with `ModuleNotFoundError: No module named 'config_schema'` (RED).
  </action>
  <verify>
    <automated>pytest -x tests/test_config_schema.py 2>&1 | grep -E "ModuleNotFoundError|No module named 'config_schema'"</automated>
    <automated>python -c "import os; assert not os.path.exists('tests/test_config.py'), 'old test_config.py should be deleted'; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_config.py` no longer exists (deleted)
    - `tests/test_config_schema.py` exists with 7 test functions named exactly as in <behavior>
    - Pytest collection of the new file fails with `ModuleNotFoundError: No module named 'config_schema'` (RED state)
  </acceptance_criteria>
  <done>Test file committed at RED, old test_config.py deleted</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement config_schema.py and update sample.config.yml + REQUIREMENTS.md (GREEN)</name>
  <files>config_schema.py, sample.config.yml, .planning/REQUIREMENTS.md</files>
  <read_first>
    - tests/test_config_schema.py (the failing tests from Task 1)
    - .planning/phases/01-foundations-security/01-RESEARCH.md lines 314-425 (Pattern 2 verbatim)
    - .planning/phases/01-foundations-security/01-PATTERNS.md (sections "config_schema.py" and "sample.config.yml")
    - .planning/REQUIREMENTS.md (current CORE-01 wording at the top of "Core Framework")
    - sample.config.yml (current state — must be replaced)
  </read_first>
  <behavior>
    - All 7 tests in tests/test_config_schema.py pass
    - sample.config.yml has no `app:` block, no plaintext credential values, includes `platforms.amazon` and `platforms.bestbuy` with comment lines naming the env vars
    - REQUIREMENTS.md CORE-01 entry no longer mentions `driver` as a parameter on `check_availability`, `auto_buy`, or `login`
  </behavior>
  <action>
    1. Create `config_schema.py` at the repo root using the contents from <interfaces> above (RESEARCH.md Pattern 2, lines 314-419). Copy verbatim with these adjustments:
       - Replace box-drawing `═══` with ASCII `===` so error output is grep-friendly on Windows consoles
       - Replace `→` with `->`
       - Otherwise identical to RESEARCH Pattern 2
    2. Replace `sample.config.yml` entirely (per PATTERNS.md "sample.config.yml" section):
       ```yaml
       # ShopPyBot config template. Copy to config.yml and customize.
       # Credentials are NOT stored here — they are read from environment variables.
       # See README.md "Credentials" section for the full env-var list.

       selenium:
         driver_path: ./chromedriver.exe

       debug:
         logging_level: 5
         test_mode: true

       open_browser: false

       platforms:
         amazon:
           enabled: true
           # Credentials loaded from env vars:
           #   SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL
           #   SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__PASSWORD
           credentials:
             email: ""
             password: ""
         bestbuy:
           enabled: true
           # Credentials loaded from env vars:
           #   SHOPBOT_PLATFORMS__BESTBUY__CREDENTIALS__EMAIL
           #   SHOPBOT_PLATFORMS__BESTBUY__CREDENTIALS__PASSWORD
           # CVV prompted at runtime via getpass.
           # Headless opt-in (trusted infra only): set SHOPBOT_ALLOW_CVV_ENV=true and SHOPBOT_BESTBUY_CVV.
           credentials:
             email: ""
             password: ""

       available:
         items: []
       ```
    3. Edit `.planning/REQUIREMENTS.md`. Find the line:
       ```
       - [ ] **CORE-01**: Plugin base class (ABC) defines `check_availability(url) → bool`, `auto_buy(driver, url, config) → bool`, `login(driver, config) → None`, `detect_captcha(driver) → bool`
       ```
       Replace with (per D-01):
       ```
       - [ ] **CORE-01**: Plugin base class (ABC) defines `check_availability(self, url) -> bool`, `auto_buy(self, url, config) -> bool`, `login(self, config) -> None` (no-op default), `detect_captcha(self) -> bool` (no-op default). Plugins own `self.driver`, constructed in `__init__`. (Updated per Phase 1 D-01.)
       ```
    4. Run the full test suite: `pytest -x -q`. All Plan 01 tests + all 7 Plan 03 tests must pass.
  </action>
  <verify>
    <automated>pytest -x -q tests/test_config_schema.py</automated>
    <automated>python -c "import pathlib; t = pathlib.Path('sample.config.yml').read_text(); assert 'amz_email' not in t; assert 'amz_pwd' not in t; assert 'bb_cvv' not in t; assert 'platforms:' in t; assert 'SHOPBOT_PLATFORMS__AMAZON' in t; print('OK')"</automated>
    <automated>python -c "import pathlib; t = pathlib.Path('.planning/REQUIREMENTS.md').read_text(); core01 = [l for l in t.splitlines() if 'CORE-01' in l][0]; assert 'driver,' not in core01 and '(driver,' not in core01 and 'driver, url' not in core01, f'CORE-01 still mentions driver param: {core01}'; assert 'self, url' in core01 or 'self.driver' in core01; print('OK')"</automated>
    <automated>pytest -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `config_schema.py` exists with `class AppConfig(BaseSettings)`, `class PlatformCredentials`, `class PlatformConfig`, `class SeleniumConfig`, `class DebugConfig`, `class ItemConfig`, `class AvailableConfig`
    - `config_schema.py` contains a `reject_deprecated_keys` validator decorated with `@model_validator(mode="before")`
    - `config_schema.py` contains a `settings_customise_sources` classmethod returning `(init_settings, env_settings, YamlConfigSettingsSource(settings_cls))`
    - `sample.config.yml` contains no plaintext credential values, has `platforms:` map, contains the substring `SHOPBOT_PLATFORMS__AMAZON`
    - REQUIREMENTS.md CORE-01 line no longer matches regex `\(driver,` and includes `self.driver` or `self, url`
    - `pytest -x -q` exits 0 with all Plan 01 + Plan 03 tests green
  </acceptance_criteria>
  <done>config_schema.py implemented, sample.config.yml + REQUIREMENTS.md updated, all 7 schema tests + Wave 0 tests green</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| user-supplied config.yml -> process | Untrusted YAML input; could carry deprecated/typo keys, missing fields, or values intended to leak credentials into the file |
| environment variables -> process | Credential surface; env wins over YAML to satisfy SEC-01 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-1-SEC-01 | Information Disclosure | config.yml committed with plaintext credentials | mitigate | Schema does not include credential fields under `app.*`; env-var source priority forces credentials out of YAML; sample.config.yml ships with empty credential strings + comments naming env vars |
| T-1-CORE-05 | Tampering / DoS | malformed config.yml | mitigate | `extra="forbid"` + Pydantic ValidationError with field paths; `test_missing_field_message` and `test_extra_keys_rejected` enforce the contract |
| T-1-CORE-06 | Repudiation | per-platform credential ambiguity | mitigate | Schema models `platforms: dict[str, PlatformConfig]` with `credentials.{email,password}`; reachable from tests |
| T-1-CORE-07 | Information Disclosure | silent re-use of deprecated `app.amz_*` keys leaking creds in YAML | mitigate | `reject_deprecated_keys` model_validator hard-fails with copy-pasteable migration block listing each old key and its new env var; D-06 forbids any back-compat shim |
| T-1-YAML-RCE | Tampering / RCE | yaml deserialization | mitigate | `pydantic-settings[yaml]` uses `yaml.safe_load` internally (per RESEARCH line 853); no custom yaml.load call introduced |
| T-1-EXTRA-FORBID | Tampering | typo'd config keys becoming silent no-ops | mitigate | `extra="forbid"` per D-07 produces ValidationError instead of silent ignore |
</threat_model>

<verification>
- `pytest -x -q tests/test_config_schema.py` passes (7 tests)
- `pytest -x -q` (full suite) exits 0
- `grep -E "amz_email|amz_pwd|bb_email|bb_password|bb_cvv" sample.config.yml` returns nothing (no plaintext credential keys)
- `grep -c "platforms:" sample.config.yml` >= 1
- REQUIREMENTS.md CORE-01 line matches `self, url` and does not match `(driver,`
- `tests/test_config.py` no longer exists
</verification>

<success_criteria>
- CORE-05 satisfied: validation errors are actionable, naming the missing field path
- CORE-06 satisfied: `platforms.<name>.credentials.{email,password}` schema in place
- CORE-07 satisfied: deprecated keys hard-fail with migration block
- SEC-01 satisfied: env vars override YAML; sample.config.yml has no plaintext credentials
- D-01 reflected in REQUIREMENTS.md
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundations-security/01-03-SUMMARY.md`
</output>
