---
phase: 02-plugin-migration
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - plugin_base.py
  - plugin_registry.py
  - tests/conftest.py
  - tests/test_plugin_base.py
  - tests/test_plugin_registry.py
autonomous: true
requirements:
  - CORE-03
  - CORE-04
tags:
  - plugin-architecture
  - registry
  - importlib
  - python

must_haves:
  truths:
    - "RetailerPlugin.domain_pattern annotation is list[str] with default [] (D-01 amendment to the Phase 1 ABC)"
    - "RetailerPlugin declares login_at_startup: bool = False as a class attribute (D-03)"
    - "plugin_registry.discover(plugins_dir, app_config, cvvs) returns a list of instantiated RetailerPlugin subclasses found in shopbot_plugin_*.py files"
    - "discover() is lenient on per-plugin import failure: logs WARNING via writeLog and continues (D-04 Phase A)"
    - "discover() emits INFO log skipping files whose stem does not start with shopbot_plugin_ (e.g., example_plugin.py)"
    - "discover() silently ignores dunder/underscore-prefixed files (__init__.py, _helpers.py)"
    - "discover() hard-fails when a single plugin module contains more than one RetailerPlugin subclass (one-class-per-file rule)"
    - "discover() resolves plugin name from optional `name: str` class attribute, defaulting to filename stem with shopbot_plugin_ prefix removed"
    - "route_url(url, registry) returns the matching plugin or None using normalized netloc + dotted-subdomain anchor (rejects evilamazon.com vs amazon.com)"
    - "verify_coverage(registry, items) raises a ValueError naming the offending URL when any item URL has no matching plugin (D-04 Phase B)"
    - "discover() raises ImportError naming the plugin file when a loaded plugin's domain_pattern is an empty list, before adding it to the registry (D-01 'import-time validation failure'). The ImportError is caught by the per-plugin try/except per D-04 Phase A and logged as a WARNING, so the bot does not crash, but the plugin is omitted from the registry and verify_coverage will hard-fail if its URLs are referenced in config."
  artifacts:
    - path: "plugin_base.py"
      provides: "Amended RetailerPlugin ABC with domain_pattern: list[str] and login_at_startup: bool"
      contains: "domain_pattern: list[str]"
      min_lines: 40
    - path: "plugin_registry.py"
      provides: "Plugin discovery, URL routing, coverage check helpers"
      contains: "def discover"
      min_lines: 80
    - path: "tests/test_plugin_registry.py"
      provides: "Discovery, routing, and coverage tests"
      min_lines: 120
    - path: "tests/test_plugin_base.py"
      provides: "Extended ABC tests asserting list[str] and login_at_startup defaults"
      min_lines: 40
    - path: "tests/conftest.py"
      provides: "Extended fixtures including tmp_plugins_dir"
      contains: "tmp_plugins_dir"
  key_links:
    - from: "plugin_registry.py"
      to: "plugin_base.RetailerPlugin"
      via: "issubclass check + __module__ filter"
      pattern: "issubclass.*RetailerPlugin"
    - from: "plugin_registry.py"
      to: "importlib.util"
      via: "spec_from_file_location + module_from_spec + exec_module"
      pattern: "spec_from_file_location"
    - from: "plugin_registry.py"
      to: "logger.writeLog"
      via: "import from logger module (no print, no stdlib logging)"
      pattern: "from logger import writeLog"
---

<objective>
Land the two pieces every downstream Phase 2 plan depends on: amend the `RetailerPlugin` ABC contract to match locked decisions D-01 and D-03, and ship a `plugin_registry.py` module that discovers plugins, routes URLs, and enforces coverage. Tests are written RED then GREEN per the Phase 1 precedent.

Purpose: Plans 02 (Amazon) and 03 (BestBuy) cannot start migrating their plugins until the ABC declares `domain_pattern: list[str]` and `login_at_startup: bool`, and the registry is callable. Plan 04 (main.py refactor) cannot integrate without `discover`, `route_url`, and `verify_coverage`. This plan is the gating Wave 0 work.

Output: amended `plugin_base.py`, new `plugin_registry.py`, extended `tests/test_plugin_base.py` and `tests/conftest.py`, new `tests/test_plugin_registry.py`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-plugin-migration/02-CONTEXT.md
@.planning/phases/02-plugin-migration/02-RESEARCH.md
@plugin_base.py
@tests/conftest.py
@tests/test_plugin_base.py
@logger.py
@config_schema.py
</context>

<interfaces>
Final amended ABC (replaces lines 22 and adds one new class attribute on `plugin_base.py`):

```python
class RetailerPlugin(ABC):
    domain_pattern: list[str] = []   # D-01: list of hostnames, e.g. ["amazon.com", "amzn.to"]
    login_at_startup: bool = False   # D-03: registry calls .login() once at startup when True
    name: str = ""                   # optional override; registry defaults to filename stem
```

Registry public API (`plugin_registry.py`):

```python
PLUGIN_PREFIX = "shopbot_plugin_"

def discover(plugins_dir: Path, *, app_config, cvvs: dict[str, str]) -> list[RetailerPlugin]: ...
def route_url(url: str, registry: list[RetailerPlugin]) -> RetailerPlugin | None: ...
def verify_coverage(registry: list[RetailerPlugin], items: list) -> None: ...  # raises ValueError on miss

# Private helpers (also exercised by tests):
def _normalize_netloc(url: str) -> str: ...
def _matches(netloc: str, pattern: str) -> bool: ...
def _load_module(path: Path): ...
def _find_plugin_class(module) -> type[RetailerPlugin]: ...
```

Plugin name resolution rule (resolves RESEARCH open question 1): the registry calls `getattr(cls, "name", "") or path.stem.removeprefix(PLUGIN_PREFIX)`. A plugin may declare a `name` class attribute to override (use case: regional variants sharing one credential block).

`writeLog` is imported from `logger`. No `print`, no stdlib `logging`.
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend tests/conftest.py + write RED tests for amended ABC and registry</name>
  <files>tests/conftest.py, tests/test_plugin_base.py, tests/test_plugin_registry.py</files>
  <read_first>
    - tests/conftest.py (current fixtures: clean_env, tmp_config_yml)
    - tests/test_plugin_base.py (current 5 tests from Phase 1 plan 02)
    - .planning/phases/02-plugin-migration/02-RESEARCH.md (Q5 test patterns, Q3 URL matching table)
  </read_first>
  <behavior>
    tests/test_plugin_base.py additions:
      - test_domain_pattern_is_list: typing.get_type_hints(RetailerPlugin)['domain_pattern'] == list[str]
      - test_domain_pattern_default_is_empty_list: RetailerPlugin.domain_pattern == []
      - test_login_at_startup_default_false: RetailerPlugin.login_at_startup is False

    tests/test_plugin_registry.py (new):
      - test_normalize_netloc_lowercases_and_strips_port: "https://Amazon.Com:443/" -> "amazon.com"
      - test_normalize_netloc_strips_trailing_dot: "https://amazon.com./" -> "amazon.com"
      - test_matches_exact_and_subdomain: ("www.amazon.com","amazon.com") True; ("amazon.com","amazon.com") True
      - test_matches_rejects_substring_attack: ("evilamazon.com","amazon.com") False
      - test_discover_finds_prefixed_plugin: write a minimal shopbot_plugin_test.py, assert one instance returned
      - test_discover_skips_example_plugin: write example_plugin.py, assert NOT in returned registry; assert INFO log emitted
      - test_discover_ignores_dunder: write __init__.py and _helpers.py, assert no warning, none returned
      - test_discover_lenient_on_import_error: write shopbot_plugin_broken.py with `raise ImportError("nope")`, assert returns [] and logs WARNING
      - test_discover_hard_fails_on_two_classes: write a plugin module with TWO RetailerPlugin subclasses, assert ImportError raised (caught by discover, logged WARNING, file skipped)
      - test_discover_uses_name_attribute_when_present: plugin declares `name = "custom"`; assert registry entry .name == "custom"
      - test_discover_defaults_name_to_filename_stem: plugin omits name; assert registry derives "test" from shopbot_plugin_test.py
      - test_discover_rejects_empty_domain_pattern: write a plugin with `domain_pattern = []`; assert plugin is NOT in returned registry AND a WARNING is logged naming the file (D-01 import-time validation failure surfaced via D-04 Phase A warn-and-skip)
      - test_route_url_returns_matching_plugin: parametrize Amazon + BestBuy URL fixtures
      - test_route_url_returns_none_on_unmatched: "https://example.com/x" -> None
      - test_verify_coverage_passes_when_all_urls_match: all items have plugins; no raise
      - test_verify_coverage_raises_on_missing_plugin: assert ValueError text mentions the offending URL and expected plugin filename

    tests/conftest.py addition:
      - tmp_plugins_dir(tmp_path) fixture returning tmp_path / "plugins" (mkdir before return)
      - _write_plugin(dir, filename, body) helper exposed as fixture or module-level utility
  </behavior>
  <action>
    1. Edit `tests/conftest.py` (append, do not rewrite existing fixtures):
       ```python
       @pytest.fixture
       def tmp_plugins_dir(tmp_path):
           d = tmp_path / "plugins"
           d.mkdir()
           return d
       ```
       Keep `clean_env` and `tmp_config_yml` unchanged.

    2. Append to `tests/test_plugin_base.py` three new tests:
       ```python
       import typing

       def test_domain_pattern_is_list():
           hints = typing.get_type_hints(RetailerPlugin)
           assert hints["domain_pattern"] == list[str]

       def test_domain_pattern_default_is_empty_list():
           assert RetailerPlugin.domain_pattern == []

       def test_login_at_startup_default_false():
           assert RetailerPlugin.login_at_startup is False
       ```

    3. Create `tests/test_plugin_registry.py` with all 15 tests listed under <behavior>. Use the
       `tmp_plugins_dir` fixture for filesystem-based discovery tests. For routing tests, build
       two minimal in-memory plugin instances (not via filesystem discovery) with
       `domain_pattern = ["amazon.com"]` and `["bestbuy.com"]` respectively. Mock build_driver
       so plugins do NOT open Chrome (see RESEARCH Q5 monkeypatch recipe).

       For tests that need a synthetic plugin file, use this minimal body:
       ```python
       PLUGIN_BODY_TEMPLATE = """
       from plugin_base import RetailerPlugin
       class TestPlugin(RetailerPlugin):
           domain_pattern = {domain_pattern!r}
           login_at_startup = False
           def __init__(self, platform_config, *, cvv=None, driver_path=None):
               super().__init__(platform_config)
               self.driver = None
           def check_availability(self, url): return False
           def auto_buy(self, url, config): return False
       """
       ```

       For the two-classes test, define two subclasses in the same file body.

       For verify_coverage tests, construct a minimal item-like object with a `.link` attribute
       (do NOT import config_schema; tests stay decoupled):
       ```python
       class _Item:
           def __init__(self, link): self.link = link
       ```

    4. Run `rtk pytest -x -q tests/test_plugin_base.py tests/test_plugin_registry.py`.
       Expect: test_plugin_base FAILS on the three new tests (annotation/default mismatch),
       test_plugin_registry FAILS with `ModuleNotFoundError: No module named 'plugin_registry'`.
       Both failures are the intended RED state.
  </action>
  <verify>
    <automated>rtk pytest -x tests/test_plugin_registry.py 2>&1 | rtk grep -E "ModuleNotFoundError|No module named 'plugin_registry'"</automated>
    <automated>rtk pytest tests/test_plugin_base.py::test_domain_pattern_is_list 2>&1 | rtk grep -E "FAILED|AssertionError"</automated>
  </verify>
  <acceptance_criteria>
    - `tests/conftest.py` contains the `tmp_plugins_dir` fixture in addition to existing fixtures
    - `tests/test_plugin_base.py` contains 5 original tests + 3 new tests (8 total)
    - `tests/test_plugin_registry.py` exists with 15 test functions
    - `rtk pytest tests/test_plugin_registry.py` exits non-zero with `ModuleNotFoundError: No module named 'plugin_registry'`
    - `rtk pytest tests/test_plugin_base.py::test_domain_pattern_is_list` exits non-zero
    - No test file imports `selenium.webdriver` directly; driver construction is monkeypatched
  </acceptance_criteria>
  <done>Test files committed in RED state, registry module does not yet exist</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Amend plugin_base.py and implement plugin_registry.py (GREEN)</name>
  <files>plugin_base.py, plugin_registry.py</files>
  <read_first>
    - tests/test_plugin_base.py (new + existing tests)
    - tests/test_plugin_registry.py (RED tests from Task 1)
    - .planning/phases/02-plugin-migration/02-RESEARCH.md (Q1, Q2, Q3, Q10 reference implementations)
    - logger.py (writeLog signature)
    - plugin_base.py (current ABC body)
  </read_first>
  <behavior>
    - All 8 tests in tests/test_plugin_base.py pass
    - All 15 tests in tests/test_plugin_registry.py pass
    - plugin_base.py imports only stdlib (abc, no typing.List from older form)
    - plugin_registry.py imports only stdlib + logger + plugin_base; no selenium, no third-party
  </behavior>
  <action>
    0. Create the `plugins/` directory at repo root if it does not exist:
       ```
       mkdir -p plugins
       ```
       Wave 0 owns this precursor so Wave 1 plans (02, 03, 05) do not race to create it.
       Do NOT add a `plugins/__init__.py` — `plugin_registry.discover` ignores dunder files
       and the directory is loaded by path, not as a Python package.

    1. Edit `plugin_base.py`. Change line 22 `domain_pattern: str = ""` to `domain_pattern: list[str] = []`.
       Insert directly under that line:
       ```python
       login_at_startup: bool = False
       name: str = ""
       ```
       Update the docstring on the class to reference the list type and the startup-login opt-in.
       Keep the file under 60 lines. Do not modify `__init__`, `check_availability`, `auto_buy`,
       `login`, or `detect_captcha` signatures (Phase 1 contract is otherwise locked).

    2. Create `plugin_registry.py` at repo root. Reference the layout in RESEARCH Q10 lines 491-518:
       ```python
       """Plugin discovery, URL routing, and coverage check (Phase 2).

       Two-phase load per CONTEXT.md D-04:
       - Phase A (discover): lenient. Import errors logged + skipped.
       - Phase B (verify_coverage): strict. Missing plugin for any URL raises ValueError.
       """
       import importlib.util
       import inspect
       import sys
       from pathlib import Path
       from urllib.parse import urlparse

       from logger import writeLog
       from plugin_base import RetailerPlugin

       PLUGIN_PREFIX = "shopbot_plugin_"


       def _normalize_netloc(url: str) -> str:
           netloc = urlparse(url).netloc.lower()
           if ":" in netloc:
               netloc = netloc.split(":", 1)[0]
           if netloc.endswith("."):
               netloc = netloc[:-1]
           return netloc


       def _matches(netloc: str, pattern: str) -> bool:
           p = pattern.lower().lstrip(".")
           return netloc == p or netloc.endswith("." + p)


       def _load_module(path: Path):
           mod_name = f"shoppybot_plugins.{path.stem}"
           spec = importlib.util.spec_from_file_location(mod_name, path)
           if spec is None or spec.loader is None:
               raise ImportError(f"Could not build spec for {path}")
           module = importlib.util.module_from_spec(spec)
           sys.modules[mod_name] = module
           spec.loader.exec_module(module)
           return module


       def _find_plugin_class(module) -> type[RetailerPlugin]:
           candidates = [
               cls for _, cls in inspect.getmembers(module, inspect.isclass)
               if issubclass(cls, RetailerPlugin)
               and cls is not RetailerPlugin
               and cls.__module__ == module.__name__
           ]
           if len(candidates) == 0:
               raise ImportError(f"{module.__name__}: no RetailerPlugin subclass found")
           if len(candidates) > 1:
               names = ", ".join(c.__name__ for c in candidates)
               raise ImportError(
                   f"{module.__name__}: expected one plugin class, found {len(candidates)}: {names}"
               )
           return candidates[0]


       def discover(plugins_dir: Path, *, app_config, cvvs: dict[str, str]) -> list[RetailerPlugin]:
           instances: list[RetailerPlugin] = []
           for path in sorted(Path(plugins_dir).glob("*.py")):
               if path.name.startswith("_") or path.name == "__init__.py":
                   continue
               if not path.stem.startswith(PLUGIN_PREFIX):
                   writeLog(
                       f"Skipped {path.name} (not auto-loaded; copy to "
                       f"{PLUGIN_PREFIX}<name>.py to enable)",
                       "INFO",
                   )
                   continue
               try:
                   module = _load_module(path)
                   cls = _find_plugin_class(module)
                   if not cls.domain_pattern:
                       raise ImportError(
                           f"{cls.__name__} declares empty domain_pattern; "
                           f"set domain_pattern: list[str] to a non-empty list of hostnames"
                       )
               except Exception as e:
                   writeLog(f"Failed to load {path.name}: {e}", "WARNING")
                   continue
               name = getattr(cls, "name", "") or path.stem.removeprefix(PLUGIN_PREFIX)
               try:
                   inst = cls(
                       platform_config=_safe_platform(app_config, name),
                       cvv=cvvs.get(name) if cvvs else None,
                       driver_path=_safe_driver_path(app_config),
                   )
               except Exception as e:
                   writeLog(
                       f"Failed to instantiate {cls.__name__} from {path.name}: {e}",
                       "WARNING",
                   )
                   continue
               # Persist resolved name for verify_coverage error messages.
               inst.name = name
               instances.append(inst)
           return instances


       def _safe_platform(app_config, name):
           # app_config may be None in some test paths; platforms may not declare every plugin.
           if app_config is None:
               return None
           platforms = getattr(app_config, "platforms", None) or {}
           return platforms.get(name) if isinstance(platforms, dict) else getattr(platforms, name, None)


       def _safe_driver_path(app_config):
           if app_config is None:
               return None
           selenium = getattr(app_config, "selenium", None)
           return getattr(selenium, "driver_path", None) if selenium else None


       def route_url(url: str, registry: list[RetailerPlugin]) -> RetailerPlugin | None:
           netloc = _normalize_netloc(url)
           for plugin in registry:
               for pattern in plugin.domain_pattern:
                   if _matches(netloc, pattern):
                       return plugin
           return None


       def verify_coverage(registry: list[RetailerPlugin], items) -> None:
           for item in items:
               link = getattr(item, "link", None) or getattr(item, "url", None)
               if link is None:
                   continue
               if route_url(link, registry) is None:
                   raise ValueError(
                       f"URL {link} has no plugin. Expected a "
                       f"plugins/{PLUGIN_PREFIX}<name>.py whose domain_pattern matches "
                       f"{_normalize_netloc(link)} (check WARNING log above for any "
                       f"plugin import errors)."
                   )
       ```

       Constraint check:
       - Functions under 30 lines each (decompose `discover` only if it exceeds).
       - File under 300 lines.
       - Nesting max 3 levels (the inner `for pattern in plugin.domain_pattern` inside `route_url` is depth 3; do not nest further).
       - No `print`, no stdlib `logging` import. Use `writeLog`.
       - No `sys.path.insert` (forbidden per RESEARCH pitfall #4).

    3. Run `rtk pytest -x -q tests/test_plugin_base.py tests/test_plugin_registry.py`. Both files must be fully green (8 + 15 = 23 tests).

    4. Run full suite `rtk pytest -x -q` to confirm no Phase 1 tests regressed.
  </action>
  <verify>
    <automated>rtk pytest -x -q tests/test_plugin_base.py tests/test_plugin_registry.py</automated>
    <automated>python -c "from plugin_base import RetailerPlugin; assert RetailerPlugin.domain_pattern == [] and RetailerPlugin.login_at_startup is False; print('OK')"</automated>
    <automated>python -c "from plugin_registry import discover, route_url, verify_coverage, _normalize_netloc, _matches; assert _normalize_netloc('https://Amazon.Com:443/') == 'amazon.com'; assert _matches('www.amazon.com', 'amazon.com') is True; assert _matches('evilamazon.com', 'amazon.com') is False; print('OK')"</automated>
    <automated>rtk pytest -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `plugin_base.py` declares `domain_pattern: list[str] = []`, `login_at_startup: bool = False`, `name: str = ""`
    - `plugin_registry.py` exists with `discover`, `route_url`, `verify_coverage`, `_normalize_netloc`, `_matches`, `_load_module`, `_find_plugin_class`
    - All 23 new/updated tests pass; full pytest suite remains green
    - `plugin_registry.py` is under 300 lines and imports zero third-party packages
    - No `print()` calls in `plugin_registry.py`; all output via `writeLog`
  </acceptance_criteria>
  <done>plugin_base.py amended, plugin_registry.py shipped, all tests green</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| plugins/ filesystem -> registry process | Any `shopbot_plugin_*.py` file is executed as Python at startup; a malicious or buggy plugin runs in the same interpreter |
| URL string -> route_url matching | Item URLs come from config.yml (user-controlled); a malformed URL must not corrupt routing or cause false-positive plugin matches |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-2-CORE-03-IMPORT | Tampering | plugin_registry._load_module | mitigate | Module name namespaced under `shoppybot_plugins.<stem>` to prevent sys.modules collision with PyPI packages (RESEARCH Q1 pitfall 1); `sys.path` not mutated |
| T-2-CORE-03-FAIL | Denial of Service | plugin discovery | mitigate | Per-plugin import failure caught + logged as WARNING, discovery continues (D-04 Phase A); coverage check (D-04 Phase B) surfaces the actionable error only for URLs the user actually relies on |
| T-2-CORE-03-MULTI | Tampering | _find_plugin_class | mitigate | Reject modules with >1 RetailerPlugin subclass at discovery time; prevents footgun where contributor copy-pastes example class into the same file |
| T-2-CORE-04-SUBDOMAIN | Spoofing | route_url / _matches | mitigate | Dotted-subdomain anchor (`netloc == p or netloc.endswith("." + p)`) blocks `evilamazon.com` from masquerading as `amazon.com`; lowercase + port stripping normalizes Amazon.Com:443 |
| T-2-CORE-04-EMPTY | Spoofing | discover() domain_pattern check | mitigate | Plugins with empty `domain_pattern` are skipped with WARNING; prevents a misconfigured plugin from claiming every URL via accident |
| T-2-IDN | Spoofing | _normalize_netloc | accept | IDN/punycode hostnames not in scope (Amazon and BestBuy use ASCII); contributors documented to use ASCII forms in PLUGIN_DEV.md (Plan 05) |
</threat_model>

<verification>
- `rtk pytest -x -q tests/test_plugin_base.py tests/test_plugin_registry.py` passes (23 tests)
- `rtk pytest -x -q` full suite passes
- `python -c "from plugin_registry import discover, route_url, verify_coverage"` succeeds
- `rtk grep -n "@abstractmethod" plugin_base.py` reports 2 matches
- `rtk grep -n "import logging" plugin_registry.py` reports 0 matches (writeLog only)
- `rtk grep -n "sys.path" plugin_registry.py` reports 0 matches
</verification>

<success_criteria>
- ABC contract amended to lock D-01 (`domain_pattern: list[str]`) and D-03 (`login_at_startup`)
- CORE-03 satisfied at the registry side: discovery walks `plugins/`, respects naming convention, isolates import failures
- CORE-04 satisfied at the registry side: URL routing with normalized netloc + subdomain anchor; coverage check enforces D-04 Phase B
- Plans 02/03/05 can now build against a stable contract; Plan 04 can integrate `discover` + `verify_coverage` + `route_url`
</success_criteria>

<output>
After completion, create `.planning/phases/02-plugin-migration/02-01-SUMMARY.md`
</output>
