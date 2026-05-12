---
phase: 01-foundations-security
plan: 06
type: execute
wave: 3
depends_on: ["01", "02", "03", "04", "05"]
files_modified:
  - main.py
  - config.py
  - amazon_bot.py
  - README.md
  - tests/test_main_smoke.py
  - tests/test_docs.py
autonomous: true
requirements:
  - SEC-06
tags:
  - integration
  - main
  - readme
  - disclaimer

must_haves:
  truths:
    - "Running `python main.py` with a valid config.yml + env credentials starts the bot without raising"
    - "main.py contains no `sys.stdout = open(os.devnull` substring"
    - "main.py imports AppConfig from config_schema, build_driver from driver, collect_cvvs from credentials, configure from logger"
    - "main.py contains a Python version guard that exits with 'requires Python 3.11+' if sys.version_info < (3, 11)"
    - "main.py reads bestbuy credentials from app_config.platforms['bestbuy'].credentials.* and the cvvs dict, NOT config['app']['bb_*']"
    - "amazon_bot.amz_sign_in reads email/password from config.platforms['amazon'].credentials.{email,password}"
    - "README.md contains an explicit personal-use / TOS-compliance / account-risk disclaimer"
    - "config.py is either deleted or reduced to a thin re-export pointing at config_schema.AppConfig"
  artifacts:
    - path: "main.py"
      provides: "Wired entrypoint using AppConfig + build_driver + collect_cvvs + configure logger"
      contains: "from config_schema import AppConfig"
    - path: "README.md"
      provides: "Personal-use disclaimer + env-var setup instructions"
      contains: "personal use"
    - path: "tests/test_main_smoke.py"
      provides: "Source-grep smoke tests for main.py invariants"
    - path: "tests/test_docs.py"
      provides: "README disclaimer substring test"
  key_links:
    - from: "main.py"
      to: "AppConfig"
      via: "from config_schema import AppConfig"
      pattern: "from config_schema import AppConfig"
    - from: "main.py"
      to: "build_driver"
      via: "from driver import build_driver"
      pattern: "from driver import build_driver"
    - from: "main.py"
      to: "collect_cvvs"
      via: "from credentials import collect_cvvs"
      pattern: "from credentials import collect_cvvs"
    - from: "main.py"
      to: "configure logger"
      via: "from logger import configure as configure_logger, writeLog"
      pattern: "configure_logger"
---

<objective>
Wire the AppConfig + driver factory + credentials + logger refactor into `main.py`, propagate the new credential-read sites into `amazon_bot.py` and `bestbuy_bot.py`, retire the legacy `config.py`, add the personal-use / TOS / account-risk disclaimer to `README.md` (SEC-06), and ship two smoke tests that lock the integration invariants.

Purpose: This plan is the final wave of Phase 1. After it ships, the bot still runs end-to-end on Selenium (per D-03) but every Phase 1 success criterion in ROADMAP.md is satisfied: AppConfig validates startup, no plaintext credentials anywhere, ChromeDriver hardened, CVV runtime-only, logger singleton, requirements pinned, README disclosed.

Output: rewritten `main.py`, minimal credential-read edits to `amazon_bot.py` and `bestbuy_bot.py`, retirement of `config.py`, new `README.md` disclaimer section, two smoke tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundations-security/01-CONTEXT.md
@.planning/phases/01-foundations-security/01-PATTERNS.md
@.planning/phases/01-foundations-security/01-RESEARCH.md
@main.py
@amazon_bot.py
@bestbuy_bot.py
@config.py
</context>

<interfaces>
<!-- Final main.py startup block. Source: PATTERNS.md "main.py" + RESEARCH.md lines 657-677. -->

```python
import sys
if sys.version_info < (3, 11):
    sys.exit(f"ShopPyBot requires Python 3.11+. Detected: {sys.version}")

import os
import requests
import webbrowser

from config_schema import AppConfig
from credentials import collect_cvvs
from driver import build_driver
from logger import configure as configure_logger, writeLog
from amazon_bot import check_amazon_item, auto_buy_amazon_item, detect_captcha
from bestbuy_bot import check_bestbuy_item, auto_buy_bestbuy_item
from utils import play_notification_sound, play_buy_sound, play_available_sound
from models import initialize_db, add_items, get_items
from webdriver_manager.chrome import ChromeDriverManager

def get_chromedriver_path(driver_path: str) -> str:
    if not os.path.exists(driver_path):
        writeLog(f"Chromedriver not found at {driver_path}. Downloading.", "WARNING")
        driver_path = ChromeDriverManager().install()
        if not os.path.exists(driver_path):
            writeLog("Failed to download Chromedriver. Exiting.", "ERROR")
            sys.exit(1)
    return driver_path

def make_tiny(url: str) -> str:
    response = requests.get(f"http://tinyurl.com/api-create.php?url={url}")
    return response.text

def main():
    try:
        app_config = AppConfig()
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)

    configure_logger(app_config.debug.logging_level)
    writeLog("Starting ShopPyBot", "INFO")

    cvvs = collect_cvvs(app_config)

    driver_path = get_chromedriver_path(app_config.selenium.driver_path)
    driver = build_driver(driver_path)

    initialize_db()
    items = [(it.name, it.link, it.auto_buy, it.quantity, False)
             for it in app_config.available.items]
    add_items(items)

    test_mode = app_config.debug.test_mode
    open_browser = app_config.open_browser

    while True:
        # ... existing polling loop, with the bestbuy auto_buy line updated to:
        #   auto_buy_bestbuy_item(driver, link,
        #                         app_config.platforms['bestbuy'].credentials.email,
        #                         app_config.platforms['bestbuy'].credentials.password,
        #                         cvvs['bestbuy'], quantity)
        # and the amazon auto_buy still passes app_config (now an AppConfig instance) through:
        #   auto_buy_amazon_item(driver, link, app_config, quantity, test_mode)
        ...

if __name__ == "__main__":
    main()
```

<!-- amazon_bot.py credential-read change. Source: PATTERNS.md "amazon_bot.py" section. -->
Inside `amz_sign_in(driver, config)` body, lines 58-59 of current file:
```python
# BEFORE
email = config['app']['amz_email']
password = config['app']['amz_pwd']
# AFTER
email = config.platforms['amazon'].credentials.email
password = config.platforms['amazon'].credentials.password
```
NO signature change. NO removal of bare `except:` (deferred — PATTERNS.md "Anti-pattern noted, NOT fixed in Phase 1").

<!-- bestbuy_bot.py: Option A — caller-side change only. Source: PATTERNS.md "bestbuy_bot.py" section. -->
`auto_buy_bestbuy_item(driver, item_url, email, password, cvv, quantity)` signature unchanged. Caller in main.py constructs the four credential args from app_config + cvvs.
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write smoke tests for main.py invariants and README disclaimer (RED)</name>
  <files>tests/test_main_smoke.py, tests/test_docs.py</files>
  <read_first>
    - main.py (current — to confirm what we're replacing)
    - .planning/phases/01-foundations-security/01-PATTERNS.md (sections "tests/test_main_smoke.py" and "tests/test_docs.py")
    - .planning/phases/01-foundations-security/01-CONTEXT.md (D-05 + Pitfall 6 for python version guard)
  </read_first>
  <behavior>
    - test_no_stdout_monkey_patch: main.py source contains no `sys.stdout = open(os.devnull` substring
    - test_no_stderr_monkey_patch: main.py source contains no `sys.stderr = open(os.devnull` substring
    - test_imports_appconfig: main.py source contains `from config_schema import AppConfig`
    - test_imports_build_driver: main.py source contains `from driver import build_driver`
    - test_imports_collect_cvvs: main.py source contains `from credentials import collect_cvvs`
    - test_imports_configure_logger: main.py source contains `from logger import configure`
    - test_python_version_guard: main.py contains both `sys.version_info < (3, 11)` and a `sys.exit` referencing 3.11
    - test_no_old_app_credential_reads: main.py, amazon_bot.py, AND bestbuy_bot.py contain no forbidden substrings: `config['app']['bb_email']`, `config['app']['bb_password']`, `config['app']['bb_cvv']`, `config['app']['amz_email']`, `config['app']['amz_pwd']`
    - test_readme_has_disclaimer: README.md contains all three substrings: "personal use", "TOS" (case-insensitive), "account"
  </behavior>
  <action>
    1. Create `tests/test_main_smoke.py`:
       ```python
       import pathlib


       def _src():
           return pathlib.Path("main.py").read_text()


       def test_no_stdout_monkey_patch():
           assert "sys.stdout = open(os.devnull" not in _src(), "INFRA-03"


       def test_no_stderr_monkey_patch():
           assert "sys.stderr = open(os.devnull" not in _src(), "INFRA-03"


       def test_imports_appconfig():
           assert "from config_schema import AppConfig" in _src()


       def test_imports_build_driver():
           assert "from driver import build_driver" in _src()


       def test_imports_collect_cvvs():
           assert "from credentials import collect_cvvs" in _src()


       def test_imports_configure_logger():
           assert "from logger import configure" in _src(), "logger.configure must be imported"


       def test_python_version_guard():
           src = _src()
           assert "sys.version_info < (3, 11)" in src
           assert "3.11+" in src or "3.11" in src


       def test_no_old_app_credential_reads():
           # INFRA: forbid every legacy `config['app']['*']` credential read across
           # main.py, amazon_bot.py, and bestbuy_bot.py. A regression in any of the
           # three would silently re-introduce a YAML credential path.
           forbidden = [
               "config['app']['bb_email']",
               "config['app']['bb_password']",
               "config['app']['bb_cvv']",
               "config['app']['amz_email']",
               "config['app']['amz_pwd']",
           ]
           for fname in ("main.py", "amazon_bot.py", "bestbuy_bot.py"):
               src = pathlib.Path(fname).read_text(encoding="utf-8")
               for needle in forbidden:
                   assert needle not in src, f"{fname} still contains {needle!r}"
       ```
    2. Create `tests/test_docs.py`:
       ```python
       import pathlib


       def test_readme_has_disclaimer():
           text = pathlib.Path("README.md").read_text(encoding="utf-8").lower()
           assert "personal use" in text, "SEC-06: README must mention personal use"
           assert "tos" in text or "terms of service" in text, "SEC-06: README must mention TOS / terms of service"
           assert "account" in text, "SEC-06: README must mention account risk"
       ```
    3. Run `pytest -x tests/test_main_smoke.py tests/test_docs.py` — most tests fail (RED state confirmed).
  </action>
  <verify>
    <automated>pytest -x tests/test_main_smoke.py 2>&1 | grep -E "FAILED|fail" | head -3</automated>
    <automated>python -c "import pathlib; assert pathlib.Path('tests/test_main_smoke.py').exists() and pathlib.Path('tests/test_docs.py').exists(); print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_main_smoke.py` exists with 8 test functions
    - `tests/test_docs.py` exists with `test_readme_has_disclaimer`
    - Running pytest reports failures (RED) — these will go GREEN in Task 2
  </acceptance_criteria>
  <done>Smoke test files committed, RED state verified</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Rewrite main.py, edit bot modules, retire config.py, write README disclaimer (GREEN)</name>
  <files>main.py, config.py, amazon_bot.py, README.md</files>
  <read_first>
    - main.py (current — full file)
    - amazon_bot.py (lines 50-65 — amz_sign_in body where credential reads live)
    - bestbuy_bot.py (signature of auto_buy_bestbuy_item)
    - config.py (current — 7 lines, will be retired)
    - README.md (current — to know what disclaimer block must be added)
    - tests/test_main_smoke.py (failing tests from Task 1)
    - tests/test_docs.py (failing test from Task 1)
    - .planning/phases/01-foundations-security/01-PATTERNS.md (sections "main.py", "amazon_bot.py", "bestbuy_bot.py", "config.py")
    - .planning/phases/01-foundations-security/01-RESEARCH.md lines 657-677 (main.py example)
  </read_first>
  <behavior>
    - All 8 smoke tests in tests/test_main_smoke.py pass
    - tests/test_docs.py::test_readme_has_disclaimer passes
    - Full pytest suite (Plans 01-06) passes
    - `python -c "import main"` does not raise (module-level imports succeed)
    - main.py preserves the polling loop semantics: domain routing, CAPTCHA prompt, auto_buy gating, sound playback
  </behavior>
  <action>
    1. **Rewrite main.py** following the <interfaces> shape. Specifically:
       - Move the Python version guard to the very top (before any other import beyond `sys`) — Pitfall 6
       - DELETE `import yaml` (no longer needed)
       - DELETE `from logger import setup_logger` reference (setup_logger no longer exists in logger.py per Plan 05)
       - DELETE the entire `def load_config():` function
       - DELETE the duplicate `from selenium.webdriver.chrome.options import Options` import (line 14 of current file is a duplicate of line 7)
       - REPLACE the chromeOptions setup block (lines 45-65 of current main.py) with a single call: `driver = build_driver(driver_path)`
       - DELETE the entire stdout/stderr monkey-patch block (lines 67-69, 73-75 of current main.py)
       - REPLACE `config = load_config()` with the AppConfig try/except block per <interfaces>
       - ADD `configure_logger(app_config.debug.logging_level)` immediately after AppConfig() succeeds
       - ADD `cvvs = collect_cvvs(app_config)` after configure_logger
       - REPLACE `items = [(item['name'], ...) for item in config['available']['items']]` with `items = [(it.name, it.link, it.auto_buy, it.quantity, False) for it in app_config.available.items]`
       - REPLACE `test_mode = config['debug'].get('test_mode', False)` with `test_mode = app_config.debug.test_mode`
       - REPLACE `open_browser = config['app'].get('open_browser', False)` with `open_browser = app_config.open_browser`
       - REPLACE the bestbuy auto_buy call (line 124) with:
         ```python
         auto_buy_bestbuy_item(driver, link,
                               app_config.platforms['bestbuy'].credentials.email,
                               app_config.platforms['bestbuy'].credentials.password,
                               cvvs['bestbuy'], quantity)
         ```
       - The amazon auto_buy call still passes `config` through; it now receives `app_config` (an AppConfig instance) — pass `app_config` instead: `auto_buy_amazon_item(driver, link, app_config, quantity, test_mode)`
       - Replace `exit(1)` with `sys.exit(1)` everywhere in main.py
       - Drop the `if __name__ == "__main__": logger = setup_logger(); main()` tail in favor of just `main()` (logger.configure already runs inside main)
    2. **Edit amazon_bot.py** (`amz_sign_in` body, around line 58-59 in current file):
       - Replace `email = config['app']['amz_email']` with `email = config.platforms['amazon'].credentials.email`
       - Replace `password = config['app']['amz_pwd']` with `password = config.platforms['amazon'].credentials.password`
       - No other change. Bare `except:` clauses are LEFT IN PLACE per PATTERNS.md (deferred to a future cleanup phase).
    3. **bestbuy_bot.py: NO EDIT REQUIRED.** Confirmed during plan revision by reading the current file:
       - Line 40: `def auto_buy_bestbuy_item(driver, item_url, email, password, cvv, quantity):` — already takes the four credential args directly (Option A signature).
       - Line 27: `def bb_sign_in(driver, email, password):` — already takes credentials as args.
       - File contains zero `config['app']['bb_*']` references.
       Action: leave `bestbuy_bot.py` unchanged. The wiring change happens entirely in main.py step 1 (the bestbuy auto_buy call site already passes the credential args). The new `test_no_old_app_credential_reads` test (Task 1, expanded in revision) will assert this invariant at the file-source level.
       Sanity check command (will be run as part of step 6 verify): `python -c "import pathlib; t = pathlib.Path('bestbuy_bot.py').read_text(); assert \"config['app']\" not in t; print('bestbuy_bot.py clean')"`
    4. **Retire config.py.** Replace its entire contents with:
       ```python
       """Compatibility shim. The legacy `config` dict has been replaced by AppConfig.

       Importers should switch to:
           from config_schema import AppConfig
           app_config = AppConfig()

       This module remains only to fail loudly if old import patterns survive.
       """
       raise ImportError(
           "`from config import config` is no longer supported. "
           "Use `from config_schema import AppConfig` and instantiate `AppConfig()` instead."
       )
       ```
       (Keeping the file in place rather than deleting prevents accidental partial deployments where some module still does `from config import config` and silently picks up a stale install.)
    5. **Add the SEC-06 disclaimer to README.md.** Append a new section near the top (right after the project tagline / first paragraph). If README.md does not exist, create it. Required content (use exactly these phrasings so the test_docs.py greps pass):
       ```markdown
       ## Disclaimer

       ShopPyBot is intended for **personal use** only. Automating retail purchases
       may violate the Terms of Service (TOS) of the platforms it interacts with.
       You are solely responsible for any consequences, including the suspension
       or banning of your account, that result from running this software. Review
       each retailer's Terms of Service before enabling auto-buy on that platform.

       ## Credentials & Environment

       Credentials are read from environment variables, not from `config.yml`.
       Set the following before running:

       - `SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL`
       - `SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__PASSWORD`
       - `SHOPBOT_PLATFORMS__BESTBUY__CREDENTIALS__EMAIL`
       - `SHOPBOT_PLATFORMS__BESTBUY__CREDENTIALS__PASSWORD`

       The CVV is prompted at runtime via `getpass`. For headless deployments
       only, set `SHOPBOT_ALLOW_CVV_ENV=true` and supply per-platform
       `SHOPBOT_<PLATFORM>_CVV` env vars (visible in `/proc/<pid>/environ` —
       trusted infrastructure only).
       ```
    6. Run `pytest -x -q`. All tests across Plans 01-06 must pass.
    7. Run `python -c "import main"` — must succeed without ImportError or syntax error (this proves all import statements resolve, even though `main()` is not invoked).
  </action>
  <verify>
    <automated>pytest -x -q tests/test_main_smoke.py tests/test_docs.py</automated>
    <automated>python -c "import main; print('main module imported OK')"</automated>
    <automated>python -c "import pathlib; t = pathlib.Path('main.py').read_text(); assert 'sys.stdout = open' not in t; assert 'from config_schema import AppConfig' in t; assert 'from driver import build_driver' in t; assert 'from credentials import collect_cvvs' in t; assert 'sys.version_info < (3, 11)' in t; print('OK')"</automated>
    <automated>python -c "import pathlib; t = pathlib.Path('amazon_bot.py').read_text(); assert \"config['app']['amz_email']\" not in t; assert 'platforms[' in t and 'amazon' in t; print('OK')"</automated>
    <automated>python -c "import pathlib; t = pathlib.Path('bestbuy_bot.py').read_text(); assert \"config['app']\" not in t; print('bestbuy_bot.py clean')"</automated>
    <automated>pytest -x -q</automated>
  </verify>
  <acceptance_criteria>
    - All 8 tests in `tests/test_main_smoke.py` pass
    - `tests/test_docs.py::test_readme_has_disclaimer` passes
    - `python -c "import main"` exits 0
    - `main.py` contains no `sys.stdout = open(os.devnull` or `sys.stderr = open(os.devnull` substring
    - `main.py` contains the four key imports: AppConfig, build_driver, collect_cvvs, logger.configure
    - `main.py` contains `sys.version_info < (3, 11)` and exits with a 3.11 reference
    - `amazon_bot.py` no longer references `config['app']['amz_email']` or `config['app']['amz_pwd']`
    - `config.py` raises ImportError on import (or the file is deleted with a corresponding test update — chosen approach is the shim)
    - README.md contains "personal use", "TOS" (or "Terms of Service"), and "account"
    - Full `pytest -x -q` exits 0 with all Plan 01-06 tests passing
  </acceptance_criteria>
  <done>main.py wired, bot modules read credentials from AppConfig, config.py retired, README disclosed, all tests green, `import main` succeeds</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| user clone of public repo -> running bot | First-run experience must surface every Phase 1 invariant: env vars required, CVV runtime-only, account/TOS risk acknowledged |
| Python interpreter -> main.py | Old Python versions silently produce cryptic errors without the version guard |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-1-SEC-06 | Repudiation | user runs bot without acknowledging TOS / account risk | mitigate | README.md disclaimer section with "personal use", TOS, account-risk language; `test_readme_has_disclaimer` enforces presence |
| T-1-INFRA-03b | Repudiation | sys.stdout / sys.stderr monkey-patch silently swallowing real Python errors at startup | mitigate | Removed in Plan 04 (driver.py owns ChromeDriver output via Service log_path); `test_no_stdout_monkey_patch` enforces no re-introduction in main.py |
| T-1-PYVER-01b | Denial of Service | runtime on Python <3.11 produces cryptic stdlib errors | mitigate | Top-of-main.py guard `sys.version_info < (3, 11)` exits with a clear message (Pitfall 6); `test_python_version_guard` enforces |
| T-1-INTEGRATION | Tampering | a future change re-introduces `config['app']['bb_*']` reads, leaking credential reads back into YAML space | mitigate | `test_no_old_app_credential_reads` enforces absence in main.py source; deprecated-key validator in config_schema (Plan 03) catches the YAML side |
| T-1-CONFIG-IMPORT | Repudiation | someone does `from config import config` after the migration | mitigate | config.py raises ImportError with explicit migration instructions instead of silently producing a stale dict |
</threat_model>

<verification>
- `pytest -x -q` (full suite) exits 0
- `python -c "import main"` exits 0
- `grep -E "sys.stdout = open\(os.devnull|sys.stderr = open\(os.devnull" main.py` returns nothing
- `grep -E "config\['app'\]\['(amz|bb)_" main.py amazon_bot.py bestbuy_bot.py` returns nothing
- `grep -E "personal use|TOS|account" README.md` matches
- `python -c "import config"` raises ImportError (the shim)
</verification>

<success_criteria>
- SEC-06 satisfied: README.md disclaimer covers personal use, TOS, account risk
- All Phase 1 ROADMAP success criteria reachable end-to-end via the integrated main.py
- The bot still runs (Selenium retained per D-03); Phase 2 can begin the nodriver swap from a known-good baseline
- No regression in existing polling loop semantics (domain routing, CAPTCHA prompt, sound playback all preserved)
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundations-security/01-06-SUMMARY.md`
</output>
