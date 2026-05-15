---
phase: 06-platform-expansion
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - requirements.txt
  - plugin_base.py
  - plugin_registry.py
  - driver.py
  - config_schema.py
  - tests/test_plugin_base.py
  - tests/test_registry_stagger.py
  - tests/test_driver_setup.py
  - tests/test_config_schema.py
  - tests/test_plugins_walmart.py
  - tests/test_plugins_target.py
  - tests/test_plugins_gamestop.py
  - tests/test_plugins_squareenix.py
  - tests/test_plugins_newegg.py
  - tests/conftest.py
autonomous: true
requirements:
  - PLG-04
  - PLG-05
  - PLG-06
  - PLG-07
  - PLG-08
  - ANTI-01
  - ANTI-02
  - ANTI-03
tags:
  - python
  - nodriver
  - pydantic
  - abc
  - schema
  - red-skeletons
  - wave-0

must_haves:
  truths:
    - "requirements.txt pins `nodriver==0.50.3` on a single new line; no duplicates introduced (D-01 + INFRA-01)"
    - "plugin_base.py adds non-abstract `async def open(self) -> None` default no-op on RetailerPlugin; PLUGIN_API_VERSION stays at 1 (additive change per RESEARCH Q2)"
    - "plugin_base.py adds class attrs `min_delay: float = 3.0` and `max_delay: float = 8.0` on RetailerPlugin (RESEARCH pitfall #13 defensive defaults)"
    - "plugin_base.py adds non-abstract `def next_delay(self) -> float` returning `random.uniform(self.min_delay, self.max_delay)` on RetailerPlugin (D-03 + RESEARCH Q9)"
    - "config_schema.py PlatformConfig adds `min_delay: float = 3.0`, `max_delay: float = 8.0`, `headless: bool = False` fields (D-03 + D-04)"
    - "config_schema.py PlatformConfig adds `@model_validator(mode='after')` that raises ValueError when min_delay <= 0 or max_delay <= 0 or min_delay > max_delay (RESEARCH pitfall #4)"
    - "config_schema.py PlatformConfig.credentials becomes `PlatformCredentials | None = None` so check-only plugins (Walmart/Target/NewEgg) don't require credentials (RESEARCH Q6)"
    - "config_schema.py AppSettings adds `user_agents: list[str] | None = None` field at app-level (per ANTI-02; access path remains `app_config.app.user_agents`)"
    - "driver.py defines `DEFAULT_USER_AGENTS: list[str]` module constant with 6 desktop Chrome UA strings covering Chrome 135-140 across Win10/Win11/macOS/Linux (RESEARCH Q8)"
    - "driver.py build_driver signature becomes `build_driver(driver_path, log_path='logs/chromedriver.log', headless: bool = False, user_agents: list[str] | None = None)` (D-04 + ANTI-02)"
    - "build_driver(headless=True) appends exactly `--headless=new` to Chrome options (RESEARCH pitfall #3 + Q7); the legacy bare `--headless` string MUST NOT appear"
    - "build_driver picks `random.choice(user_agents or DEFAULT_USER_AGENTS)` on EACH call and passes via `--user-agent=<chosen>` arg; no module-level cache (RESEARCH pitfall #8)"
    - "plugin_registry.py `_instantiate` passes `user_agents=app_config.app.user_agents` kwarg to plugin __init__ (RESEARCH O-2 option a: surgical addition)"
    - "plugin_registry.py `discover_async` awaits `inst.open()` AFTER `_load_and_instantiate` returns successfully AND BEFORE the next stagger sleep (RESEARCH Q2 + pitfall #5)"
    - "plugin_registry.py `discover_async` catches exceptions from `inst.open()`, logs WARNING with `type(inst).__name__`, and SKIPS adding the plugin to the registry (RESEARCH pitfall #12 + D-04 Phase A semantics)"
    - "Five RED skeleton test files exist (tests/test_plugins_walmart.py, target, gamestop, squareenix, newegg); each fails today at collection (ImportError on missing plugin module) or execution (AttributeError); zero PASS"
    - "tests/conftest.py adds a `fakeBrowser` fixture: an `AsyncMock` shaped to expose `.get`, `.stop`, and `.select` so nodriver plugins can be unit-tested without spawning Chrome (RESEARCH Q10 test strategy)"
    - "tests/test_plugin_base.py extended with RED assertions covering `open()` no-op default, `next_delay()` returns value in [min_delay, max_delay], and class-attr defaults (3.0, 8.0)"
    - "tests/test_registry_stagger.py extended with RED assertion that `open()` is awaited exactly once per plugin AND that a plugin whose `open()` raises is NOT added to the registry"
    - "tests/test_driver_setup.py extended with RED assertions: `--headless=new` flag presence when headless=True; UA rotation via `random.choice` picks DIFFERENT UAs across two builds when forced; DEFAULT_USER_AGENTS is a non-empty list of strings"
    - "tests/test_config_schema.py extended with RED assertions for the three new PlatformConfig fields, the validator rejecting min_delay > max_delay AND min_delay <= 0, and the credentials-optional change (PlatformConfig with no credentials parses cleanly)"
    - "Pre-existing Phase 1-5 pytest suite remains green after Wave 0 GREEN steps (no regressions); only the 5 new plugin test files stay RED for Wave 1 to flip"
  artifacts:
    - path: "requirements.txt"
      provides: "nodriver==0.50.3 pin"
      contains: "nodriver==0.50.3"
    - path: "plugin_base.py"
      provides: "open() + next_delay() defaults + min_delay/max_delay class attrs"
      contains: "async def open"
      min_lines: 80
    - path: "plugin_registry.py"
      provides: "discover_async awaits open() with skip-on-failure; _instantiate plumbs user_agents"
      contains: "await inst.open()"
    - path: "driver.py"
      provides: "DEFAULT_USER_AGENTS + headless=new + UA rotation via random.choice"
      contains: "DEFAULT_USER_AGENTS"
      min_lines: 60
    - path: "config_schema.py"
      provides: "PlatformConfig min_delay/max_delay/headless + validator + optional credentials + app.user_agents"
      contains: "validate_delay_range"
    - path: "tests/conftest.py"
      provides: "fakeBrowser fixture for nodriver plugin tests"
      contains: "fakeBrowser"
    - path: "tests/test_plugins_walmart.py"
      provides: "RED skeleton covering PLG-04"
      min_lines: 30
    - path: "tests/test_plugins_target.py"
      provides: "RED skeleton covering PLG-05"
      min_lines: 30
    - path: "tests/test_plugins_gamestop.py"
      provides: "RED skeleton covering PLG-06"
      min_lines: 30
    - path: "tests/test_plugins_squareenix.py"
      provides: "RED skeleton covering PLG-07"
      min_lines: 30
    - path: "tests/test_plugins_newegg.py"
      provides: "RED skeleton covering PLG-08"
      min_lines: 30
  key_links:
    - from: "plugin_base.RetailerPlugin"
      to: "random.uniform"
      via: "next_delay default returns random.uniform(self.min_delay, self.max_delay)"
      pattern: "random\\.uniform\\(self\\.min_delay"
    - from: "plugin_registry.discover_async"
      to: "inst.open"
      via: "await inst.open() after _load_and_instantiate, before next stagger"
      pattern: "await\\s+inst\\.open\\(\\)"
    - from: "driver.build_driver"
      to: "DEFAULT_USER_AGENTS"
      via: "random.choice fallback when user_agents kwarg is None"
      pattern: "random\\.choice\\("
    - from: "config_schema.PlatformConfig"
      to: "model_validator"
      via: "validate_delay_range mode=after"
      pattern: "validate_delay_range"
---

<objective>
Wave 0 foundation for Phase 6. Land four mechanically-locked changes: (1) pin nodriver==0.50.3; (2) extend the RetailerPlugin ABC with non-abstract `open()` + `next_delay()` defaults plus class-attr min_delay/max_delay; (3) extend `build_driver` with headless + UA rotation kwargs and add `DEFAULT_USER_AGENTS`; (4) extend `PlatformConfig` with min_delay/max_delay/headless + validator and make credentials Optional. Wire `discover_async` to await `inst.open()` with skip-on-failure. Land 5 RED test skeletons (one per new plugin) for Wave 1 to flip.

Purpose: Wave 0 ships the entire scaffold so Wave 1's five plugin plans run in parallel with zero file overlap. The ABC change is additive (PLUGIN_API_VERSION stays at 1 per RESEARCH Q2). The validator + Optional credentials change is the single PlatformConfig touch — Wave 1 plans MUST NOT edit config_schema.py.

Output: Foundation files + 5 RED test skeletons. Wave 1 unblocked.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/06-platform-expansion/06-CONTEXT.md
@.planning/phases/06-platform-expansion/06-RESEARCH.md
@.planning/REQUIREMENTS.md
@plugin_base.py
@plugin_registry.py
@driver.py
@config_schema.py
@requirements.txt
@tests/conftest.py
@tests/test_plugin_base.py
@tests/test_registry_stagger.py
@tests/test_driver_setup.py
@tests/test_config_schema.py
</context>

<interfaces>
Target `plugin_base.py` additions (keep existing class body intact):

```python
import random

class RetailerPlugin(ABC):
    domain_pattern: list[str] = []
    login_at_startup: bool = False
    name: str = ""
    min_delay: float = 3.0
    max_delay: float = 8.0

    # existing __init__, abstract check_availability/auto_buy, login/detect_captcha/shutdown unchanged

    async def open(self) -> None:
        """No-op default. Override in async-native plugins (nodriver) to build self.driver.

        Called by discover_async AFTER __init__ AND BEFORE the next stagger sleep.
        Selenium plugins inherit the no-op (they build their driver in __init__).
        """
        return None

    def next_delay(self) -> float:
        """Return random.uniform(min_delay, max_delay) — fresh sample per call (ANTI-01)."""
        return random.uniform(self.min_delay, self.max_delay)
```

Target `plugin_registry.py` amendments:

```python
def _instantiate(cls, name, app_config, cvvs):
    user_agents = None
    if app_config is not None and getattr(app_config, "app", None) is not None:
        user_agents = getattr(app_config.app, "user_agents", None)
    return cls(
        platform_config=_safe_platform(app_config, name),
        cvv=cvvs.get(name) if cvvs else None,
        driver_path=_safe_driver_path(app_config),
        user_agents=user_agents,
    )

async def discover_async(plugins_dir, *, app_config, cvvs, stagger_seconds=DEFAULT_STAGGER_SECONDS):
    instances: list[RetailerPlugin] = []
    paths = list(_iter_plugin_paths(plugins_dir))
    for index, path in enumerate(paths):
        if index > 0:
            await asyncio.sleep(stagger_seconds)
        inst = await asyncio.to_thread(_load_and_instantiate, path, app_config, cvvs)
        if inst is None:
            continue
        try:
            await inst.open()
        except Exception as e:
            writeLog(
                f"{type(inst).__name__}.open() raised: {e}; skipping plugin",
                "WARNING",
            )
            continue
        instances.append(inst)
    return instances
```

NOTE on `_instantiate` signature change: existing Selenium plugins (Amazon/BestBuy) currently accept `platform_config, *, cvv=None, driver_path=None`. To stay backwards compatible, those plugin __init__ signatures must accept `**_ignored` OR the new `user_agents=None` kwarg. Pick the smaller blast radius: add `user_agents=None` kwarg to Amazon and BestBuy plugin __init__ as part of this plan (two extra lines per plugin, no behavior change for Selenium plugins).

Target `driver.py` additions (keep existing build_driver body, extend signature + UA rotation):

```python
import random

DEFAULT_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
]


def build_driver(
    driver_path: str,
    log_path: str = "logs/chromedriver.log",
    headless: bool = False,
    user_agents: list[str] | None = None,
):
    opts = Options()
    # ...existing prefs and base args, BUT drop the hardcoded --user-agent=CHROME_UA line
    chosen_ua = random.choice(user_agents or DEFAULT_USER_AGENTS)
    opts.add_argument(f"--user-agent={chosen_ua}")
    # ...existing stealth args
    if headless:
        opts.add_argument("--headless=new")
    # ...existing Service + CDP patch
    return driver
```

Target `config_schema.py` PlatformConfig changes:

```python
class PlatformConfig(BaseModel):
    enabled: bool = True
    credentials: PlatformCredentials | None = None
    min_delay: float = 3.0
    max_delay: float = 8.0
    headless: bool = False

    @model_validator(mode="after")
    def validate_delay_range(self) -> "PlatformConfig":
        if self.min_delay <= 0 or self.max_delay <= 0:
            raise ValueError("min_delay and max_delay must be > 0")
        if self.min_delay > self.max_delay:
            raise ValueError(
                f"min_delay ({self.min_delay}) must be <= max_delay ({self.max_delay})"
            )
        return self


class AppSettings(BaseModel):
    delay: float = Field(default=5.0, ge=0.1, le=3600.0)
    user_agents: list[str] | None = None
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Land foundation source changes (requirements + ABC + driver + schema + registry)</name>
  <files>requirements.txt, plugin_base.py, plugin_registry.py, driver.py, config_schema.py, plugins/shopbot_plugin_amazon.py, plugins/shopbot_plugin_bestbuy.py</files>
  <read_first>
    - .planning/phases/06-platform-expansion/06-CONTEXT.md (D-01..D-04)
    - .planning/phases/06-platform-expansion/06-RESEARCH.md Q1, Q2, Q7, Q8, Q9, pitfalls 1-13
    - plugin_base.py, plugin_registry.py, driver.py, config_schema.py current source
    - plugins/shopbot_plugin_amazon.py and plugins/shopbot_plugin_bestbuy.py __init__ signatures
  </read_first>
  <action>
    1. Append `nodriver==0.50.3` to requirements.txt on its own line (verify it isn't already present, do not duplicate).

    2. Update plugin_base.py per <interfaces>: add `import random`, add class attrs `min_delay = 3.0` / `max_delay = 8.0`, add `async def open(self) -> None` no-op default, add `def next_delay(self) -> float` returning `random.uniform(self.min_delay, self.max_delay)`. PLUGIN_API_VERSION stays at 1. Update class docstring to note the two additive methods.

    3. Update plugin_registry.py per <interfaces>: amend `_instantiate` to read `user_agents` from `app_config.app.user_agents` (with getattr fallback chain to None) and pass as kwarg. Amend `discover_async` to `await inst.open()` AFTER `_load_and_instantiate` AND BEFORE the next stagger; catch + log WARNING + skip on failure (do not add to registry).

    4. Update driver.py per <interfaces>: add `import random`, add `DEFAULT_USER_AGENTS` module constant with the 6 UA strings, extend `build_driver` signature with `headless: bool = False, user_agents: list[str] | None = None`, REMOVE the existing hardcoded `opts.add_argument(f"--user-agent={CHROME_UA}")` line and replace with `chosen_ua = random.choice(user_agents or DEFAULT_USER_AGENTS); opts.add_argument(f"--user-agent={chosen_ua}")`. Add `if headless: opts.add_argument("--headless=new")` BEFORE the Service line. Keep CHROME_UA constant for backwards compat but stop using it.

    5. Update config_schema.py per <interfaces>: change `PlatformConfig.credentials` to `PlatformCredentials | None = None`; add `min_delay: float = 3.0`, `max_delay: float = 8.0`, `headless: bool = False`; add `validate_delay_range` model_validator(mode="after"). Add `user_agents: list[str] | None = None` to AppSettings.

    6. Update plugins/shopbot_plugin_amazon.py AND plugins/shopbot_plugin_bestbuy.py __init__ to accept `user_agents: list[str] | None = None` kwarg (additive; ignored by Selenium plugins for now — Plan 06-07 wires it through to build_driver). No behavior change.

    7. Run `rtk pytest -q` and confirm Phase 1-5 tests still pass (the validator change should not break anything because existing Amazon/BestBuy PlatformConfig entries have credentials).

    NOTE: keep all functions under 30 lines; nesting depth max 3.
  </action>
  <verify>
    <automated>rtk grep -n "nodriver==0.50.3" requirements.txt</automated>
    <automated>rtk grep -n "async def open" plugin_base.py</automated>
    <automated>rtk grep -n "def next_delay" plugin_base.py</automated>
    <automated>rtk grep -n "await inst.open()" plugin_registry.py</automated>
    <automated>rtk grep -n "--headless=new" driver.py</automated>
    <automated>rtk grep -n "DEFAULT_USER_AGENTS" driver.py</automated>
    <automated>rtk grep -n "validate_delay_range" config_schema.py</automated>
    <automated>rtk grep -n "credentials: PlatformCredentials | None" config_schema.py</automated>
    <automated>rtk pytest -q tests/test_plugin_base.py tests/test_registry_stagger.py tests/test_driver_setup.py tests/test_config_schema.py</automated>
  </verify>
  <done>Foundation source lands. ABC additive change locked. Phase 1-5 suite remains green.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Extend GREEN tests for foundation + write RED skeletons for 5 plugins</name>
  <files>tests/test_plugin_base.py, tests/test_registry_stagger.py, tests/test_driver_setup.py, tests/test_config_schema.py, tests/conftest.py, tests/test_plugins_walmart.py, tests/test_plugins_target.py, tests/test_plugins_gamestop.py, tests/test_plugins_squareenix.py, tests/test_plugins_newegg.py</files>
  <read_first>
    - tests/conftest.py (existing fixtures: fakePluginFactory, fakeNotifierFactory if present)
    - tests/test_plugin_base.py (existing GREEN tests to extend)
    - tests/test_registry_stagger.py (existing stagger tests)
    - .planning/phases/06-platform-expansion/06-RESEARCH.md Q10 (test strategy)
  </read_first>
  <behavior>
    GREEN extensions (Task 1 source must satisfy):
    - test_openDefaultIsNoOp: RetailerPlugin.open returns None and is a coroutine.
    - test_nextDelayInRange: 100 calls all fall in [3.0, 8.0]; with custom min/max attrs, all calls fall in that range.
    - test_classAttrDefaults: RetailerPlugin.min_delay == 3.0 and max_delay == 8.0 at class level.
    - test_discoverAsyncAwaitsOpen: fake plugin records open() invocation; assert called exactly once per instance, BEFORE the next stagger sleep.
    - test_discoverAsyncSkipsBrokenOpen: fake plugin whose open() raises; instance NOT in returned registry; WARNING log captured.
    - test_buildDriverHeadlessNewFlag: build_driver(headless=True) -> options arguments contain exactly "--headless=new" and NOT the bare "--headless".
    - test_userAgentRotation: monkeypatch random.choice to alternate; two build_driver calls record DIFFERENT UA args.
    - test_userAgentsKwargOverride: build_driver(user_agents=["UA-X"]) -> options arg contains "--user-agent=UA-X".
    - test_platformConfigDelayValidator: PlatformConfig(min_delay=0) raises; min_delay=5, max_delay=3 raises; min_delay=3, max_delay=8 parses.
    - test_platformConfigCredentialsOptional: PlatformConfig(enabled=True) parses with credentials=None.
    - test_appSettingsUserAgents: AppSettings(user_agents=["X"]).user_agents == ["X"]; default is None.

    RED skeletons (must FAIL today, flipped GREEN in Wave 1):
    - For each retailer (walmart, target, gamestop, squareenix, newegg): tests/test_plugins_<retailer>.py contains at minimum:
      - test_<retailer>PluginImportable: `from plugins.shopbot_plugin_<retailer> import <Retailer>Plugin` -> succeeds (RED today: file does not exist).
      - test_<retailer>SubclassesRetailerPlugin: issubclass(<Retailer>Plugin, RetailerPlugin) (RED today).
      - test_<retailer>DomainPattern: <Retailer>Plugin.domain_pattern is non-empty list[str] (RED today).
      - test_<retailer>RiskyAutobuyGateOff: monkeypatch.delenv("SHOPBOT_ENABLE_RISKY_AUTOBUY"); instantiate with fakeBrowser fixture; await auto_buy(...) -> returns False; WARNING log fires.
      - test_<retailer>RiskyAutobuyGateOn: monkeypatch.setenv("SHOPBOT_ENABLE_RISKY_AUTOBUY", "true"); instantiate; assert `_riskyAutoBuyEnabled is True`.
      - Walmart-only extra: test_walmartRiskNoteLoggedOnce — env=on, auto_buy twice, assert INFO log "PerimeterX" appears exactly once.
      - GameStop-only extra: test_gamestopCaptchaPause — monkeypatch input via asyncio.to_thread; detect_captcha returns True; auto_buy proceeds past pause without blocking event loop.
      - Amazon headless guard sanity (in Walmart only as a phase-level smoke): assert AmazonPlugin import does NOT break under PlatformConfig(headless=False) — this passes today; Plan 06-07 adds the headless=True ValueError.
  </behavior>
  <action>
    1. Extend tests/test_plugin_base.py with the four GREEN tests (open default, next_delay range x2, class-attr defaults). Use `inspect.iscoroutinefunction` for the open() coroutine check.

    2. Extend tests/test_registry_stagger.py with GREEN tests asserting `open()` is awaited per instance AND that broken `open()` causes skip + WARNING. Use the existing fakePluginFactory pattern; add an `open_impl=` kwarg that defaults to no-op and accepts a callable that raises.

    3. Extend tests/test_driver_setup.py with GREEN tests for `--headless=new`, UA rotation (monkeypatch `driver.random.choice`), and `user_agents` kwarg override. Inspect `opts.arguments` list for the exact substring.

    4. Extend tests/test_config_schema.py with GREEN tests for the validator (min_delay > max_delay, min_delay <= 0), credentials Optional, and user_agents on AppSettings.

    5. Add `fakeBrowser` fixture to tests/conftest.py: a `unittest.mock.AsyncMock` shaped object with `.get`, `.stop`, `.select`, `.select_all` async methods. Use `pytest.fixture` returning a fresh AsyncMock per test.

    6. Create the 5 RED skeleton files tests/test_plugins_<retailer>.py. Each file imports `from plugins.shopbot_plugin_<retailer> import <Retailer>Plugin` (will ImportError today — that IS the RED). Wrap import in a try/except at module level so the rest of the file can be parsed by pytest and clearly show "collected 0 items / 6 errors" or "ImportError at collection". Standard convention: use `pytest.importorskip` is FORBIDDEN here — we want the test to RED-fail, not skip. Instead, do the import inside each test function so collection succeeds and each test fails with ImportError/AttributeError when called.

    7. Run `rtk pytest -q tests/test_plugin_base.py tests/test_registry_stagger.py tests/test_driver_setup.py tests/test_config_schema.py`. All GREEN.

    8. Run `rtk pytest -q tests/test_plugins_walmart.py tests/test_plugins_target.py tests/test_plugins_gamestop.py tests/test_plugins_squareenix.py tests/test_plugins_newegg.py`. All RED (every test fails with ImportError or AttributeError because plugin files do not exist).

    9. Run `rtk pytest -q --ignore=tests/test_plugins_walmart.py --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_squareenix.py --ignore=tests/test_plugins_newegg.py`. Full pre-existing Phase 1-5 suite GREEN.

    File-ownership declaration (so Wave 1 plans overwrite cleanly): each test_plugins_<retailer>.py file is OWNED by its Wave 1 plan and may be fully rewritten there. Wave 0 lands ONLY the import-error skeleton.
  </action>
  <verify>
    <automated>rtk pytest -q tests/test_plugin_base.py tests/test_registry_stagger.py tests/test_driver_setup.py tests/test_config_schema.py</automated>
    <automated>rtk pytest -q tests/test_plugins_walmart.py tests/test_plugins_target.py tests/test_plugins_gamestop.py tests/test_plugins_squareenix.py tests/test_plugins_newegg.py</automated>
    <automated>rtk pytest -q --ignore=tests/test_plugins_walmart.py --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_squareenix.py --ignore=tests/test_plugins_newegg.py</automated>
    <automated>rtk grep -n "fakeBrowser" tests/conftest.py</automated>
  </verify>
  <done>Foundation tests GREEN; 5 RED plugin skeletons in place; pre-existing suite green. Wave 1 unblocked.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| config.yml -> PlatformConfig | Untrusted user input drives min_delay/max_delay/headless; validator enforces sane ranges |
| app.user_agents (config) -> Chrome arg | User-supplied UA list becomes a `--user-agent=` Chrome arg; no shell metacharacter execution path (Chrome arg is array form, not shell) |
| nodriver dependency (new) | Third-party async browser automation; pinned to 0.50.3 for reproducibility (INFRA-01) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-06-01-DELAY-DOS | Denial of Service | PlatformConfig validator | mitigate | min_delay > 0 enforced; 0 or negative raises ValueError at startup |
| T-06-01-UA-INJECTION | Tampering | build_driver UA arg | accept | Chrome arg list passed as array; no shell expansion path; UA strings are user-trusted by definition (user owns their config) |
| T-06-01-NODRIVER-SUPPLY | Tampering (supply chain) | nodriver pin | mitigate | Exact pin to 0.50.3 (INFRA-01); pip --require-hashes is out of scope but version pin prevents silent major-version bumps |
| T-06-01-OPEN-CRASH-LEAK | Information Disclosure | discover_async open() catch | mitigate | Exception caught + logged with `type(inst).__name__` only; no full traceback exposed; skip rather than crash registry |
</threat_model>

<verification>
- `rtk grep -n "nodriver==0.50.3" requirements.txt` matches exactly one line
- `rtk grep -n "PLUGIN_API_VERSION" plugin_base.py` shows the value still `= 1` (additive ABC change confirmed)
- `rtk pytest -q tests/test_plugin_base.py tests/test_registry_stagger.py tests/test_driver_setup.py tests/test_config_schema.py` all GREEN
- `rtk pytest -q tests/test_plugins_walmart.py tests/test_plugins_target.py tests/test_plugins_gamestop.py tests/test_plugins_squareenix.py tests/test_plugins_newegg.py` all RED (ImportError / AttributeError)
- `rtk pytest -q --ignore=tests/test_plugins_walmart.py --ignore=tests/test_plugins_target.py --ignore=tests/test_plugins_gamestop.py --ignore=tests/test_plugins_squareenix.py --ignore=tests/test_plugins_newegg.py` GREEN (Phase 1-5 regression check)
</verification>

<success_criteria>
- nodriver==0.50.3 pinned
- RetailerPlugin gains open() + next_delay() defaults; class attrs min_delay=3.0, max_delay=8.0; PLUGIN_API_VERSION stays at 1
- discover_async awaits inst.open() with skip-on-failure
- build_driver supports headless=True (--headless=new) and user_agents=...
- DEFAULT_USER_AGENTS module constant in driver.py
- PlatformConfig has min_delay/max_delay/headless + validator; credentials optional; AppSettings gains user_agents
- 5 RED plugin skeleton test files exist (each fails today)
- Phase 1-5 pre-existing suite stays green
</success_criteria>

<output>
After completion, create `.planning/phases/06-platform-expansion/06-01-SUMMARY.md`
</output>
