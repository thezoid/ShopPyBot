---
phase: 02-plugin-migration
plan: 05
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - plugins/example_plugin.py
  - plugins/PLUGIN_DEV.md
  - tests/test_docs.py
autonomous: true
requirements:
  - CORE-08
tags:
  - documentation
  - example
  - contributor
  - python

must_haves:
  truths:
    - "plugins/example_plugin.py exists and defines exactly one RetailerPlugin subclass (ExamplePlugin)"
    - "plugins/example_plugin.py is intentionally NOT auto-loaded by the registry: filename does not start with shopbot_plugin_"
    - "ExamplePlugin demonstrates a working check-only plugin (login_at_startup = False; auto_buy returns False with informational log)"
    - "ExamplePlugin uses inline comments to teach each integration point: domain_pattern, __init__ + build_driver, check_availability return semantics, writeLog usage"
    - "plugins/PLUGIN_DEV.md exists with the 9 sections enumerated in 02-RESEARCH Q7"
    - "PLUGIN_DEV.md links to (does not duplicate) CONTRIBUTING.md (Phase 3 placeholder reference acceptable)"
    - "PLUGIN_DEV.md documents the locked file-naming rule, one-class-per-file rule, ABC method signatures (no driver param), and domain_pattern: list[str] type"
    - "PLUGIN_DEV.md documents the anti-pattern list from 02-RESEARCH Q9 (NEVER from config import config; NEVER module-level driver; NEVER sys.path.insert; NEVER pass a single string for domain_pattern; etc.)"
    - "tests/test_docs.py asserts both files exist and contain expected anchors"
  artifacts:
    - path: "plugins/example_plugin.py"
      provides: "Working httpbin-based example plugin contributors copy as a starting template"
      contains: "class ExamplePlugin(RetailerPlugin)"
      min_lines: 40
    - path: "plugins/PLUGIN_DEV.md"
      provides: "Contributor contract reference for retail plugins"
      contains: "RetailerPlugin"
      min_lines: 100
    - path: "tests/test_docs.py"
      provides: "Source-grep tests asserting example plugin and PLUGIN_DEV.md exist with required content"
  key_links:
    - from: "plugins/example_plugin.py"
      to: "plugin_base.RetailerPlugin"
      via: "class inheritance (proves the example actually subclasses the ABC contributors will implement)"
      pattern: "class ExamplePlugin\\(RetailerPlugin\\)"
    - from: "plugins/PLUGIN_DEV.md"
      to: "plugins/example_plugin.py"
      via: "documentation references the file by name; tests assert the reference"
      pattern: "example_plugin.py"
---

<objective>
Ship the two contributor-facing artifacts that CORE-08 requires: a working `plugins/example_plugin.py` template that demonstrates every integration point, and `plugins/PLUGIN_DEV.md` — the technical contract reference for plugin contributors. This plan is parallel-safe with Plans 02 and 03 (no overlapping files; only touches docs and a non-auto-loaded plugin file).

Purpose: After this plan, a new contributor can read `PLUGIN_DEV.md`, copy `example_plugin.py` to `plugins/shopbot_plugin_<their_platform>.py`, edit the bodies, and have a discoverable plugin. The example is a working "echo" plugin (against `httpbin.org/html`) rather than a stub-with-pass body, so contributors learn the integration shape, not just the function signatures.

Output: `plugins/example_plugin.py`, `plugins/PLUGIN_DEV.md`, and source-grep tests in `tests/test_docs.py` (extend or create) asserting both artifacts exist with the required anchors.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-plugin-migration/02-CONTEXT.md
@.planning/phases/02-plugin-migration/02-RESEARCH.md
@.planning/phases/02-plugin-migration/02-01-registry-and-abc-amendment-PLAN.md
@plugin_base.py
@driver.py
@logger.py
</context>

<interfaces>
ExamplePlugin (`plugins/example_plugin.py`) shape — working check-only plugin against `httpbin.org/html`:

```python
"""Example RetailerPlugin (CORE-08).

This file is intentionally NOT auto-loaded by the registry — its filename
does not start with `shopbot_plugin_`. Copy it to
`plugins/shopbot_plugin_<your_platform>.py` to enable discovery.

The example demonstrates:
  - domain_pattern: list[str]
  - login_at_startup opt-out (this plugin is check-only)
  - self.driver construction in __init__ via build_driver
  - check_availability returning True/False based on a DOM probe
  - auto_buy as an informational no-op (returns False)

See plugins/PLUGIN_DEV.md for the full contract reference.
"""
from selenium.webdriver.common.by import By

from driver import build_driver
from logger import writeLog
from plugin_base import RetailerPlugin


class ExamplePlugin(RetailerPlugin):
    # List of hostnames this plugin handles. urlparse(url).netloc matched
    # via subdomain-anchored .endswith() check inside the registry.
    domain_pattern: list[str] = ["httpbin.org"]
    # No auth required for httpbin; inherit no-op login default by leaving this False.
    login_at_startup: bool = False
    # Optional override; registry defaults to filename stem with shopbot_plugin_ removed.
    name: str = "example"

    def __init__(self, platform_config, *, cvv=None, driver_path=None):
        super().__init__(platform_config)
        self.cvv = cvv
        self.driver = build_driver(driver_path or "chromedriver.exe")

    def check_availability(self, url: str) -> bool:
        """Return True if the page at `url` contains an <h1> tag."""
        try:
            self.driver.get(url)
            elements = self.driver.find_elements(By.TAG_NAME, "h1")
            available = len(elements) > 0
            writeLog(
                f"Example plugin check_availability({url}) -> {available}",
                "DEBUG",
            )
            return available
        except Exception as e:
            writeLog(f"Example plugin error: {e}", "ERROR")
            return False

    def auto_buy(self, url: str, config) -> bool:
        """Check-only plugin: auto-buy is not implemented."""
        writeLog(
            "auto_buy not implemented for ExamplePlugin (this is a check-only template)",
            "INFO",
        )
        return False
```

PLUGIN_DEV.md outline (RESEARCH Q7 lines 380-394, expanded). Sections required:

1. **What is a plugin?** (one paragraph)
2. **The contract** — `RetailerPlugin` ABC reference: required abstract methods, default no-op methods, class attributes (`domain_pattern: list[str]`, `login_at_startup: bool`, optional `name: str`)
3. **File naming convention** — `plugins/shopbot_plugin_<name>.py` required; one class per file; `example_plugin.py` is the starter template (not auto-loaded; filename prefix mismatch)
4. **`domain_pattern` matching rules** — list of lowercase hostnames; subdomain-anchored `.endswith`; URL shortener support via multiple entries; ASCII-only (no IDN/punycode notes)
5. **Driver construction** — `build_driver(driver_path, log_path)` in `__init__`; `self.driver`; no module-level driver
6. **Reading config** — `self.platform_config` slice; never `from config import config`
7. **Testing your plugin** — minimum: import test, contract test, mocked `build_driver`, parametrized URL routing test; reference `tests/test_plugin_base.py` and `tests/test_plugins_amazon.py` as templates
8. **`PLUGIN_API_VERSION`** — current value (1), what triggers a v2 bump
9. **Submitting** — link to `CONTRIBUTING.md` (Phase 3) for fork/PR workflow; this doc is contract-only
10. **Anti-patterns (Things NOT to do)** — from RESEARCH Q9: no `from config import config`, no module-level driver, no `sys.path.insert`, no re-importing `plugin_base` by file path, no >1 class per file, no string for `domain_pattern`, no `update_item_purchased` from `check_availability`

Length target: 100-200 lines. No emojis. No em dashes. No `---` horizontal rules in body (the YAML frontmatter `---` markers in PLAN.md are fine; PLUGIN_DEV.md has no frontmatter and should use Markdown headings only for section breaks).
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write RED tests for example_plugin.py + PLUGIN_DEV.md</name>
  <files>tests/test_docs.py</files>
  <read_first>
    - tests/test_docs.py (if it exists from Phase 1 — extend; otherwise create)
    - plugin_base.py (amended ABC from Plan 01 — example plugin must conform)
    - .planning/phases/02-plugin-migration/02-RESEARCH.md (Q7 outline, Q8 example shape)
  </read_first>
  <behavior>
    Append (or create) the following tests in `tests/test_docs.py`:

      - test_example_plugin_file_exists: plugins/example_plugin.py exists
      - test_example_plugin_filename_is_not_auto_loaded: starts with "example", NOT "shopbot_plugin_"
      - test_example_plugin_subclasses_retailer_plugin: AST walk finds a ClassDef whose bases include Name(id="RetailerPlugin")
      - test_example_plugin_declares_domain_pattern_list: AST walk asserts the class body assigns `domain_pattern` to a List node (not a Str)
      - test_example_plugin_imports_build_driver: ast asserts `from driver import build_driver` ImportFrom node
      - test_example_plugin_no_config_singleton_import: source-grep asserts `from config import` is absent
      - test_example_plugin_constructs_via_mock(monkeypatch): patch driver.build_driver; load the module by file path; instantiate ExamplePlugin; assert plugin.driver is the sentinel

      - test_plugin_dev_md_exists: plugins/PLUGIN_DEV.md exists
      - test_plugin_dev_md_required_sections: source-grep asserts these section headings (case-insensitive substring match) all appear: "what is a plugin", "the contract", "file naming", "domain_pattern", "driver", "config", "test", "PLUGIN_API_VERSION", "anti-pattern" (or "things not to do")
      - test_plugin_dev_md_references_example_plugin: source-grep asserts "example_plugin.py" appears
      - test_plugin_dev_md_documents_list_str_type: source-grep asserts the literal "list[str]" appears (locks D-01 in the docs)
      - test_plugin_dev_md_documents_login_at_startup: source-grep asserts "login_at_startup" appears
      - test_plugin_dev_md_documents_one_class_per_file: source-grep asserts the substring "one plugin class per file" (case-insensitive) appears
      - test_plugin_dev_md_links_contributing: source-grep asserts "CONTRIBUTING.md" appears (forward link to Phase 3)
      - test_plugin_dev_md_no_em_dashes: source-grep asserts the em-dash character `—` does NOT appear (CLAUDE.md style)
      - test_plugin_dev_md_no_horizontal_rule: source-grep asserts no line equals exactly `---` or `***` or `___`
  </behavior>
  <action>
    1. Read existing `tests/test_docs.py`. If the file exists (from Phase 1 plan 06), append.
       If it does not exist, create it.

    2. Add the 16 tests listed under <behavior>. For the AST + monkeypatch tests, use the
       importlib-by-file-path pattern from Plans 02 and 03 since `plugins/` is not a package:
       ```python
       import importlib.util
       import pathlib

       EXAMPLE_FILE = pathlib.Path("plugins/example_plugin.py")
       PLUGIN_DEV_FILE = pathlib.Path("plugins/PLUGIN_DEV.md")
       ```

    3. Run `rtk pytest -x -q tests/test_docs.py`. All new tests fail because neither
       `plugins/example_plugin.py` nor `plugins/PLUGIN_DEV.md` exist yet (RED state).
  </action>
  <verify>
    <automated>rtk pytest tests/test_docs.py 2>&1 | rtk grep -E "FAILED|example_plugin.py|PLUGIN_DEV.md"</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_docs.py` exists with the 16 new tests appended (preserving any Phase 1 tests)
    - `rtk pytest tests/test_docs.py` shows failures for the new tests
    - No new tests spawn Chrome (monkeypatched build_driver)
  </acceptance_criteria>
  <done>Docs tests committed in RED state</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Ship example_plugin.py and PLUGIN_DEV.md (GREEN)</name>
  <files>plugins/example_plugin.py, plugins/PLUGIN_DEV.md</files>
  <read_first>
    - tests/test_docs.py (RED tests from Task 1)
    - plugin_base.py (amended ABC contract)
    - .planning/phases/02-plugin-migration/02-RESEARCH.md (Q7 outline, Q8 example shape, Q9 anti-patterns)
    - plugins/shopbot_plugin_amazon.py (Plan 02 output — use as concrete reference in docs)
    - plugins/shopbot_plugin_bestbuy.py (Plan 03 output — use as concrete reference in docs)
  </read_first>
  <behavior>
    - All 16 tests in tests/test_docs.py pass
    - ExamplePlugin can be loaded via importlib.spec_from_file_location and instantiated when build_driver is patched
    - PLUGIN_DEV.md contains every required section and anti-pattern listed in Task 1 behavior
    - No em dashes; no horizontal-rule lines; no emojis (CLAUDE.md global style)
  </behavior>
  <action>
    1. Ensure `plugins/` directory exists. Create it if neither Plan 02 nor Plan 03 has run.

    2. Create `plugins/example_plugin.py` with the body shown in <interfaces> above. The file
       MUST:
       - Subclass `RetailerPlugin`
       - Declare `domain_pattern: list[str] = ["httpbin.org"]`
       - Declare `login_at_startup: bool = False` (check-only template)
       - Declare `name: str = "example"`
       - Build `self.driver = build_driver(driver_path or "chromedriver.exe")` in `__init__`
       - Implement `check_availability` against `<h1>` presence (DOM probe via selenium)
       - Implement `auto_buy` as an informational no-op returning False
       - Carry inline comments teaching each integration point
       - NOT use any emojis or em dashes; ASCII only

       Length target: 40-80 lines.

    3. Create `plugins/PLUGIN_DEV.md`. Use the outline in <interfaces>. Concrete content rules:
       - Every section heading is a Markdown `##` heading (or `#` for the doc title)
       - No `---` horizontal rule lines anywhere; use heading boundaries instead
       - No em dashes (use colons or sentence restructure)
       - No emojis
       - Reference `example_plugin.py` by filename when describing the template-copy workflow
       - Include a literal `list[str]` in the domain_pattern section
       - Include a literal `login_at_startup` reference in the contract section
       - Include the literal phrase "one plugin class per file" in the file naming section
       - Reference `CONTRIBUTING.md` once in the Submitting section (Phase 3 placeholder)
       - Anti-patterns section quotes the bullet list from RESEARCH Q9 (NEVER from config import; NEVER module-level driver; etc.)

       Recommended structure (each section 5-25 lines):
       ```markdown
       # Plugin Developer Guide

       ## What is a plugin?
       <paragraph>

       ## The contract
       <ABC method signatures + class attributes table>

       ## File naming convention
       <shopbot_plugin_*.py rule; one plugin class per file>

       ## domain_pattern matching rules
       <list[str], subdomain-anchored .endswith, lowercase>

       ## Driver construction
       <build_driver in __init__; self.driver; no module-level driver>

       ## Reading config
       <self.platform_config; never `from config import config`>

       ## Testing your plugin
       <minimum tests; mock build_driver; reference tests/test_plugins_amazon.py>

       ## PLUGIN_API_VERSION
       <value 1; v2 bump triggers>

       ## Submitting
       <link to CONTRIBUTING.md (Phase 3)>

       ## Anti-patterns (Things NOT to do)
       <bullet list from RESEARCH Q9>
       ```

    4. Run `rtk pytest -x -q tests/test_docs.py`. All 16 tests pass.

    5. Run full suite `rtk pytest -x -q`. No regressions.

    6. Visual style sanity:
       - `rtk grep -n "—" plugins/PLUGIN_DEV.md` returns no matches
       - `rtk grep -nE "^---$|^\\*\\*\\*$|^___$" plugins/PLUGIN_DEV.md` returns no matches
  </action>
  <verify>
    <automated>rtk pytest -x -q tests/test_docs.py</automated>
    <automated>rtk pytest -x -q</automated>
    <automated>python -c "import importlib.util; spec = importlib.util.spec_from_file_location('ex', 'plugins/example_plugin.py'); m = importlib.util.module_from_spec(spec); print('module parses')"</automated>
    <automated>rtk grep -c "list\[str\]" plugins/PLUGIN_DEV.md</automated>
    <automated>rtk grep -c "login_at_startup" plugins/PLUGIN_DEV.md</automated>
    <automated>rtk grep -c "example_plugin.py" plugins/PLUGIN_DEV.md</automated>
    <automated>rtk grep -n "—" plugins/PLUGIN_DEV.md 2>&1 | rtk grep -E "^$|No matches"</automated>
  </verify>
  <acceptance_criteria>
    - `plugins/example_plugin.py` exists and subclasses RetailerPlugin
    - `plugins/example_plugin.py` filename does NOT start with `shopbot_plugin_` (so registry skips it)
    - `plugins/PLUGIN_DEV.md` exists with all 10 required sections from the outline
    - PLUGIN_DEV.md contains the literal substrings `list[str]`, `login_at_startup`, `example_plugin.py`, `CONTRIBUTING.md`, `one plugin class per file`
    - PLUGIN_DEV.md contains zero em dashes and zero horizontal-rule lines
    - All 16 tests in `tests/test_docs.py` pass
    - Full pytest suite green
    - `example_plugin.py` parses as valid Python
  </acceptance_criteria>
  <done>example_plugin.py + PLUGIN_DEV.md shipped, docs tests green</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| contributor reads docs -> writes plugin | Misleading or incomplete docs lead to plugins that violate the contract (e.g., string domain_pattern, module-level driver). Docs are a security control: they teach the locked anti-patterns |
| example_plugin.py imitated -> production plugin | A copy-paste of example_plugin.py inherits its patterns. The example must model correct behavior (driver in __init__, no `from config import config`, etc.) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-2-CORE-08-DRIFT | Tampering | PLUGIN_DEV.md vs. plugin_base.py | mitigate | Tests assert the literal `list[str]` and `login_at_startup` strings appear in the doc — if the ABC ever changes type, the test fails and prompts a doc update |
| T-2-CORE-08-AUTO-LOAD | Spoofing | example_plugin.py | mitigate | Filename `example_plugin.py` (NOT `shopbot_plugin_example.py`) means the registry intentionally skips it with an INFO log; tests assert this skip-by-naming rule |
| T-2-CORE-08-COPY-PASTE | Tampering | example_plugin.py teaches anti-patterns by accident | mitigate | Example uses `build_driver` in __init__ (PLG-03 correct), reads no config singleton, has exactly one class. Mirrors the production plugins' shape so copy-paste produces a correct plugin |
| T-2-CORE-08-HTTPBIN | Denial of Service | example uses httpbin.org | accept | If httpbin.org goes down, the example does not work end-to-end but still teaches the contract. Plan does not run the example live; documented as known external dependency in the example file docstring |
</threat_model>

<verification>
- `rtk pytest -x -q tests/test_docs.py` passes (16 tests)
- `rtk pytest -x -q` full suite passes
- `rtk find plugins/example_plugin.py plugins/PLUGIN_DEV.md` returns both files
- `rtk grep -n "shopbot_plugin_" plugins/example_plugin.py` reports 0 matches in the filename context (it may appear in docstring as a copy-target reference; that is fine)
- `python -c "import importlib.util, ast; ast.parse(open('plugins/example_plugin.py').read())"` exits 0
</verification>

<success_criteria>
- CORE-08 satisfied: working example plugin + technical contract reference shipped
- Contributors can copy `example_plugin.py` to `plugins/shopbot_plugin_<name>.py` and have a discoverable plugin without reading any other source
- Docs are tested for drift: if the ABC type or locked decisions change, the doc-grep tests fail and force a doc update
</success_criteria>

<output>
After completion, create `.planning/phases/02-plugin-migration/02-05-SUMMARY.md`
</output>
