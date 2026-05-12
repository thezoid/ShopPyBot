---
phase: 01-foundations-security
plan: 04
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - driver.py
  - tests/test_driver_setup.py
autonomous: true
requirements:
  - SEC-03
  - SEC-04
  - SEC-05
  - INFRA-03
tags:
  - selenium
  - chromedriver
  - cdp
  - bot-detection

must_haves:
  truths:
    - "build_driver() returns a webdriver.Chrome instance with no --disable-web-security flag"
    - "build_driver() invokes execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {source: ...navigator.webdriver...})"
    - "build_driver() sets a Chrome user agent that does NOT contain 'Selenium' or 'HeadlessChrome'"
    - "build_driver() routes ChromeDriver output via Service(log_path=...) — no sys.stdout monkey-patch in this module"
    - "logs/chromedriver.log directory parent exists or is created when build_driver runs"
  artifacts:
    - path: "driver.py"
      provides: "build_driver factory + CHROME_UA constant"
      contains: "def build_driver"
      min_lines: 40
    - path: "tests/test_driver_setup.py"
      provides: "Mock-based contract tests for SEC-03/04/05 + INFRA-03"
      min_lines: 60
  key_links:
    - from: "driver.py build_driver"
      to: "Page.addScriptToEvaluateOnNewDocument CDP command"
      via: "execute_cdp_cmd call after webdriver.Chrome() construction, before any driver.get()"
      pattern: "execute_cdp_cmd.*Page.addScriptToEvaluateOnNewDocument"
    - from: "driver.py build_driver"
      to: "logs/chromedriver.log"
      via: "Service(executable_path=..., log_path=...)"
      pattern: "Service\\(.*log_path"
---

<objective>
Extract Selenium driver construction from `main.py` into a standalone `build_driver(driver_path, log_path)` factory in a new `driver.py` module. The factory removes `--disable-web-security` (SEC-03), hides `navigator.webdriver` via CDP (SEC-04), sets a real Chrome user agent (SEC-05), and routes ChromeDriver output via `Service(log_path=...)` instead of the sys.stdout monkey-patch (INFRA-03).

Purpose: Phase 2 will replace Selenium with nodriver atomically per D-03; until then, Phase 1 hardens the existing Selenium driver against the bot-detection signals that would get the codebase TOS-flagged the moment it is open-sourced. By extracting to its own module, Plan 05 can swap `webdriver.Chrome(...)` calls in main.py for `build_driver(...)` with one import line.

Output: `driver.py` (new), `tests/test_driver_setup.py` (new). Does NOT modify `main.py` — that integration is Plan 05.
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
</context>

<interfaces>
<!-- Source: RESEARCH.md Pattern 4 (lines 480-512). -->

```python
# driver.py — final shape
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

WEBDRIVER_HIDE_JS = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"


def build_driver(driver_path: str, log_path: str = "logs/chromedriver.log"):
    """Construct a Selenium Chrome driver with Phase 1 stealth + INFRA-03 hardening.

    SEC-03: no --disable-web-security flag.
    SEC-04: CDP patch hides navigator.webdriver before page scripts run.
    SEC-05: real Chrome UA (no Selenium/HeadlessChrome substring).
    INFRA-03: ChromeDriver output via Service log_path; no sys.stdout reassignment.
    """
    opts = Options()
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "autofill.profile_enabled": False,
        "autofill.credit_card_enabled": False,
    }
    opts.add_experimental_option("prefs", prefs)
    opts.add_argument(f"--user-agent={CHROME_UA}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-site-isolation-trials")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--disable-save-password-bubble")
    opts.add_argument("--disable-translate")

    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    service = Service(executable_path=driver_path, log_path=log_path)
    driver = webdriver.Chrome(service=service, options=opts)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": WEBDRIVER_HIDE_JS},
    )
    return driver
```

CRITICAL deletions vs current main.py (PATTERNS.md "main.py" section, points 2 + 3):
- DROP: `chromeOptions.add_argument("--disable-web-security")` (SEC-03)
- DROP: `chromeOptions.add_argument("--disable-features=AutofillServerCommunication,...")` (long autofill string is not security-relevant; trims surface area but not required)
- DROP: `sys.stdout = open(os.devnull, 'w')` and the matching `sys.stderr = open(...)` and the post-restore lines (INFRA-03)
- ADD: `--user-agent=...` (SEC-05)
- ADD: `Service(executable_path=..., log_path=...)` (INFRA-03)
- ADD: `execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {...})` (SEC-04)
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write failing driver setup tests (RED)</name>
  <files>tests/test_driver_setup.py</files>
  <read_first>
    - tests/test_models.py (analog for test structure)
    - .planning/phases/01-foundations-security/01-PATTERNS.md (section "tests/test_driver_setup.py")
    - .planning/phases/01-foundations-security/01-RESEARCH.md lines 480-517 (Pattern 4 + UA notes)
    - main.py lines 45-78 (current driver setup — confirm what build_driver replaces)
  </read_first>
  <behavior>
    - test_no_disable_web_security: `--disable-web-security` not present in any captured Options argument
    - test_real_user_agent_set: at least one option matches `--user-agent=` and the value contains `Chrome/` and does NOT contain `Selenium` or `HeadlessChrome`
    - test_cdp_webdriver_hide_called: mock driver.execute_cdp_cmd called once with first arg `"Page.addScriptToEvaluateOnNewDocument"` and source containing `navigator.webdriver`
    - test_service_uses_log_path: Service constructor receives a non-empty `log_path` kwarg
    - test_no_stdout_monkey_patch: source of `driver.py` does not contain the substring `sys.stdout = open`
  </behavior>
  <action>
    1. Create `tests/test_driver_setup.py`:
       ```python
       from unittest.mock import patch, MagicMock
       import pathlib


       def test_no_stdout_monkey_patch_in_source():
           src = pathlib.Path("driver.py").read_text()
           assert "sys.stdout = open" not in src, "INFRA-03: no sys.stdout monkey-patch"
           assert "sys.stderr = open" not in src, "INFRA-03: no sys.stderr monkey-patch"


       @patch("driver.webdriver.Chrome")
       @patch("driver.Service")
       def test_no_disable_web_security(mock_service, mock_chrome, tmp_path):
           from driver import build_driver
           build_driver("/fake/chromedriver", log_path=str(tmp_path / "cd.log"))
           # Inspect the Options instance that was passed to Chrome()
           _, kwargs = mock_chrome.call_args
           opts = kwargs["options"]
           assert "--disable-web-security" not in opts.arguments


       @patch("driver.webdriver.Chrome")
       @patch("driver.Service")
       def test_real_user_agent_set(mock_service, mock_chrome, tmp_path):
           from driver import build_driver
           build_driver("/fake/chromedriver", log_path=str(tmp_path / "cd.log"))
           _, kwargs = mock_chrome.call_args
           opts = kwargs["options"]
           ua_args = [a for a in opts.arguments if a.startswith("--user-agent=")]
           assert len(ua_args) == 1, f"expected 1 user-agent arg, got {ua_args}"
           ua = ua_args[0]
           assert "Chrome/" in ua
           assert "Selenium" not in ua
           assert "HeadlessChrome" not in ua


       @patch("driver.webdriver.Chrome")
       @patch("driver.Service")
       def test_cdp_webdriver_hide_called(mock_service, mock_chrome, tmp_path):
           fake_driver = MagicMock()
           mock_chrome.return_value = fake_driver
           from driver import build_driver
           build_driver("/fake/chromedriver", log_path=str(tmp_path / "cd.log"))
           fake_driver.execute_cdp_cmd.assert_called_once()
           call_args = fake_driver.execute_cdp_cmd.call_args
           assert call_args.args[0] == "Page.addScriptToEvaluateOnNewDocument"
           source = call_args.args[1]["source"]
           assert "navigator.webdriver" in source


       @patch("driver.webdriver.Chrome")
       @patch("driver.Service")
       def test_service_uses_log_path(mock_service, mock_chrome, tmp_path):
           from driver import build_driver
           log = str(tmp_path / "cd.log")
           build_driver("/fake/chromedriver", log_path=log)
           _, kwargs = mock_service.call_args
           assert kwargs.get("log_path") == log, f"Service log_path missing or wrong: {kwargs}"
       ```
    2. Run `pytest -x tests/test_driver_setup.py` — must fail with `ModuleNotFoundError: No module named 'driver'` (RED).
  </action>
  <verify>
    <automated>pytest -x tests/test_driver_setup.py 2>&1 | grep -E "ModuleNotFoundError|No module named 'driver'"</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_driver_setup.py` exists with 5 test functions named exactly as in <behavior>
    - All 5 fail with `ModuleNotFoundError: No module named 'driver'` (or the source-grep test fails because driver.py does not exist)
  </acceptance_criteria>
  <done>Test file committed, RED state verified</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement driver.py (GREEN)</name>
  <files>driver.py</files>
  <read_first>
    - tests/test_driver_setup.py (the failing tests from Task 1)
    - .planning/phases/01-foundations-security/01-RESEARCH.md lines 480-517 (Pattern 4)
    - main.py lines 45-78 (current driver setup — for prefs + flag list to preserve except SEC-03 removal)
  </read_first>
  <behavior>
    - All 5 tests in tests/test_driver_setup.py pass
    - Module exposes `build_driver(driver_path, log_path="logs/chromedriver.log")` and `CHROME_UA` constant
    - Module does NOT import or modify `sys.stdout` / `sys.stderr`
  </behavior>
  <action>
    Create `driver.py` at the repo root using the contents in <interfaces> above. Specifically:
    - CHROME_UA = the Mozilla/5.0 string with Chrome/131.0.0.0 (per RESEARCH line 487; planner-acknowledged "131 is illustrative" — this is fine for SEC-05 because acceptance only checks for absence of `Selenium`/`HeadlessChrome` and presence of `Chrome/`)
    - Preserve every flag from current main.py EXCEPT `--disable-web-security` (drop) and the long `--disable-features=Autofill...` string (drop; not security-relevant, reduces surface)
    - Preserve the `prefs` dict verbatim from main.py lines 47-53
    - Use `os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)` to ensure the log directory exists before Service() opens the log file
    - CDP call must come AFTER `webdriver.Chrome(...)` returns and BEFORE returning the driver (Pitfall 3 in RESEARCH lines 624-629 — must fire before any driver.get)
    - No `sys` import; no stdout/stderr reassignment
  </action>
  <verify>
    <automated>pytest -x -q tests/test_driver_setup.py</automated>
    <automated>python -c "import ast, pathlib; tree = ast.parse(pathlib.Path('driver.py').read_text()); names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]; assert 'build_driver' in names; print('OK')"</automated>
    <automated>python -c "import pathlib; src = pathlib.Path('driver.py').read_text(); assert '--disable-web-security' not in src; assert 'execute_cdp_cmd' in src; assert 'Page.addScriptToEvaluateOnNewDocument' in src; assert 'log_path' in src; assert 'sys.stdout' not in src; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `driver.py` exists at repo root, exports `build_driver` function and `CHROME_UA` constant
    - All 5 tests in `tests/test_driver_setup.py` pass
    - `grep "disable-web-security" driver.py` returns nothing (SEC-03)
    - `grep "execute_cdp_cmd.*Page.addScriptToEvaluateOnNewDocument" driver.py` matches (SEC-04)
    - `grep "user-agent" driver.py` matches and the UA value does not contain `Selenium` or `HeadlessChrome` (SEC-05)
    - `grep "log_path" driver.py` matches in a `Service(...)` call (INFRA-03)
    - `grep "sys.stdout" driver.py` returns nothing (INFRA-03)
    - File under 60 lines
  </acceptance_criteria>
  <done>driver.py implemented, all 5 driver tests green</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| selenium-driven Chrome -> retail website JS | Anti-bot scripts inspect navigator.webdriver, user agent, and security flags during initial JS evaluation; getting flagged here means CAPTCHAs everywhere or full account ban |
| ChromeDriver process -> stdout/stderr | Driver chatters protocol logs on stdout; previous monkey-patch swallowed real Python errors |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-1-SEC-03 | Tampering | Chrome same-origin policy | mitigate | Remove `--disable-web-security` from Options; tested by `test_no_disable_web_security` |
| T-1-SEC-04 | Spoofing | navigator.webdriver bot fingerprint | mitigate | CDP `Page.addScriptToEvaluateOnNewDocument` hides property before any page script reads it (Pitfall 3); tested by `test_cdp_webdriver_hide_called` |
| T-1-SEC-05 | Spoofing | Selenium default user agent fingerprint | mitigate | `--user-agent=` arg with real Chrome UA; absence of `Selenium`/`HeadlessChrome` enforced by `test_real_user_agent_set` |
| T-1-INFRA-03 | Repudiation | sys.stdout monkey-patch swallowing real errors | mitigate | Replaced by `Service(log_path=...)`; source-grep test enforces no re-introduction |
| T-1-UA-DRIFT | Spoofing | UA major version goes stale (still claims Chrome/131) | accept | Per RESEARCH line 517: major version is not load-bearing for SEC-05 acceptance; refresh in a future maintenance pass |
| T-1-CDP-ORDER | Spoofing | CDP injected after first navigation | mitigate | Code structure forces CDP call inside build_driver, before returning the driver, so the first `driver.get(...)` in main.py loop already has the patch |
</threat_model>

<verification>
- `pytest -x -q tests/test_driver_setup.py` passes (5 tests)
- `grep -E "(disable-web-security|sys.stdout = open)" driver.py` returns nothing
- `grep -c "execute_cdp_cmd" driver.py` >= 1
- `grep -c "log_path" driver.py` >= 1
- `wc -l driver.py` reports < 60
</verification>

<success_criteria>
- SEC-03 satisfied: `--disable-web-security` flag absent
- SEC-04 satisfied: CDP-based navigator.webdriver hide is present
- SEC-05 satisfied: real Chrome UA set, no Selenium/HeadlessChrome tokens
- INFRA-03 satisfied: ChromeDriver output via Service log_path; sys.stdout untouched
- Plan 05 can integrate via single-line `from driver import build_driver`
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundations-security/01-04-SUMMARY.md`
</output>
