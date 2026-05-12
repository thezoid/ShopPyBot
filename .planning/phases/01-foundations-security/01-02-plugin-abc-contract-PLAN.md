---
phase: 01-foundations-security
plan: 02
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - plugin_base.py
  - tests/test_plugin_base.py
autonomous: true
requirements:
  - CORE-01
  - CORE-02
tags:
  - plugin-architecture
  - abc
  - python

must_haves:
  truths:
    - "A developer can `from plugin_base import RetailerPlugin, PLUGIN_API_VERSION`"
    - "PLUGIN_API_VERSION equals integer 1"
    - "Calling RetailerPlugin({}) raises TypeError because abstract methods are unimplemented"
    - "A subclass that implements only check_availability and auto_buy can be instantiated"
    - "login() default returns None (no-op); detect_captcha() default returns False"
  artifacts:
    - path: "plugin_base.py"
      provides: "RetailerPlugin ABC + PLUGIN_API_VERSION constant"
      contains: "class RetailerPlugin(ABC)"
      min_lines: 30
    - path: "tests/test_plugin_base.py"
      provides: "ABC contract tests"
      min_lines: 30
  key_links:
    - from: "plugin_base.py"
      to: "abc.ABC"
      via: "class inheritance + @abstractmethod decorators"
      pattern: "@abstractmethod"
---

<objective>
Lock the plugin contract that every retail plugin in Phases 2-6 must implement: `RetailerPlugin` ABC with `PLUGIN_API_VERSION = 1`. Only `check_availability` and `auto_buy` are abstract; `login` and `detect_captcha` ship as no-op defaults so check-only plugins compile without boilerplate (CORE-01, CORE-02).

Purpose: Phase 2 atomically swaps Selenium for nodriver and migrates Amazon/BestBuy to plugins. That migration cannot start until this contract is in source. Per D-01, ABC method signatures drop the `driver` parameter entirely (driver lives on `self.driver`).

Output: `plugin_base.py` and `tests/test_plugin_base.py` — pure-stdlib, no third-party imports.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundations-security/01-CONTEXT.md
@.planning/phases/01-foundations-security/01-PATTERNS.md
@.planning/phases/01-foundations-security/01-RESEARCH.md
@tests/test_models.py
</context>

<interfaces>
<!-- Final contract per D-01 (CONTEXT.md). Source: RESEARCH.md Pattern 1 (lines 247-312). -->

```python
PLUGIN_API_VERSION: int = 1

class RetailerPlugin(ABC):
    domain_pattern: str  # class attribute set by subclasses (e.g., "amazon.com")

    def __init__(self, platform_config) -> None:
        # subclasses store platform_config and build self.driver here
        pass

    @abstractmethod
    def check_availability(self, url: str) -> bool: ...

    @abstractmethod
    def auto_buy(self, url: str, config) -> bool: ...

    def login(self, config) -> None:
        # no-op default
        return None

    def detect_captcha(self) -> bool:
        # no-op default
        return False
```

CORE-01 in REQUIREMENTS.md still lists `driver` as a parameter on three methods. CONTEXT.md D-01 explicitly defers the REQUIREMENTS.md text edit to Plan 03 (where `config_schema.py` work also needs it). This plan does NOT touch REQUIREMENTS.md.
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write failing ABC contract tests (RED)</name>
  <files>tests/test_plugin_base.py</files>
  <read_first>
    - tests/test_models.py (analog for pytest unit-test structure)
    - .planning/phases/01-foundations-security/01-PATTERNS.md (section "tests/test_plugin_base.py")
    - .planning/phases/01-foundations-security/01-RESEARCH.md (Pattern 1 test block, lines 292-312)
  </read_first>
  <behavior>
    - test_api_version_is_one: PLUGIN_API_VERSION == 1
    - test_cannot_instantiate_abstract: instantiating RetailerPlugin directly raises TypeError
    - test_subclass_with_required_methods_works: subclass implementing only check_availability + auto_buy can be instantiated
    - test_login_default_is_noop: subclass without overriding login can call .login(None) and get None
    - test_detect_captcha_default_returns_false: subclass without overriding detect_captcha gets False
  </behavior>
  <action>
    1. Create `tests/test_plugin_base.py`:
       ```python
       import pytest
       from plugin_base import RetailerPlugin, PLUGIN_API_VERSION


       class _MinimalPlugin(RetailerPlugin):
           domain_pattern = "example.com"

           def check_availability(self, url: str) -> bool:
               return True

           def auto_buy(self, url: str, config) -> bool:
               return True


       def test_api_version_is_one():
           assert PLUGIN_API_VERSION == 1
           assert isinstance(PLUGIN_API_VERSION, int)


       def test_cannot_instantiate_abstract():
           with pytest.raises(TypeError):
               RetailerPlugin({})


       def test_subclass_with_required_methods_works():
           plugin = _MinimalPlugin({})
           assert plugin.check_availability("https://example.com") is True
           assert plugin.auto_buy("https://example.com", {}) is True


       def test_login_default_is_noop():
           plugin = _MinimalPlugin({})
           assert plugin.login(None) is None


       def test_detect_captcha_default_returns_false():
           plugin = _MinimalPlugin({})
           assert plugin.detect_captcha() is False
       ```
    2. Run `pytest -x -q tests/test_plugin_base.py`. It MUST fail with `ModuleNotFoundError: No module named 'plugin_base'` (RED state confirmed).
  </action>
  <verify>
    <automated>pytest -x tests/test_plugin_base.py 2>&1 | grep -E "ModuleNotFoundError|No module named 'plugin_base'"</automated>
  </verify>
  <acceptance_criteria>
    - File `tests/test_plugin_base.py` exists with 5 test functions
    - `pytest -x tests/test_plugin_base.py` exits non-zero with `ModuleNotFoundError: No module named 'plugin_base'`
    - File contains exactly the test names listed in <behavior>
  </acceptance_criteria>
  <done>Test file committed, RED state verified</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement plugin_base.py (GREEN)</name>
  <files>plugin_base.py</files>
  <read_first>
    - tests/test_plugin_base.py (the failing tests written in Task 1)
    - .planning/phases/01-foundations-security/01-PATTERNS.md (section "plugin_base.py")
    - .planning/phases/01-foundations-security/01-RESEARCH.md (Pattern 1, lines 247-291)
  </read_first>
  <behavior>
    - All 5 tests in tests/test_plugin_base.py pass
    - Module exports `RetailerPlugin` and `PLUGIN_API_VERSION`
    - Module imports only from stdlib (`abc` + typing); no third-party deps
  </behavior>
  <action>
    Create `plugin_base.py` at the repo root (flat layout per PATTERNS.md "Established Patterns"):
    ```python
    """Retail plugin contract for ShopPyBot.

    All retailer integrations subclass RetailerPlugin and implement the two
    abstract methods (check_availability, auto_buy). login() and detect_captcha()
    have no-op defaults so check-only plugins do not need boilerplate.

    Per D-01 (Phase 1 CONTEXT): ABC methods do NOT take a `driver` argument.
    Subclasses construct `self.driver` in `__init__`.
    """
    from abc import ABC, abstractmethod

    PLUGIN_API_VERSION: int = 1


    class RetailerPlugin(ABC):
        """Abstract base for retail platform plugins.

        Subclasses MUST set `domain_pattern` (class attribute, e.g. "amazon.com")
        and implement `check_availability` and `auto_buy`.
        """

        domain_pattern: str = ""

        def __init__(self, platform_config) -> None:
            """Store platform-scoped config slice. Subclasses build self.driver here."""
            self.platform_config = platform_config

        @abstractmethod
        def check_availability(self, url: str) -> bool:
            """Return True if the item at `url` is in stock."""
            raise NotImplementedError

        @abstractmethod
        def auto_buy(self, url: str, config) -> bool:
            """Attempt to purchase the item at `url`. Return True on success."""
            raise NotImplementedError

        def login(self, config) -> None:
            """No-op default. Override if the platform requires authentication."""
            return None

        def detect_captcha(self) -> bool:
            """No-op default returning False. Override to detect platform-specific CAPTCHAs."""
            return False
    ```
    Per PATTERNS.md "plugin_base.py" section: do NOT raise NotImplementedError in __init__ (would prevent super().__init__() in subclasses). Body is `self.platform_config = platform_config`.
  </action>
  <verify>
    <automated>pytest -x -q tests/test_plugin_base.py</automated>
    <automated>python -c "from plugin_base import RetailerPlugin, PLUGIN_API_VERSION; assert PLUGIN_API_VERSION == 1; print('OK')"</automated>
    <automated>python -c "import plugin_base, ast; tree = ast.parse(open('plugin_base.py').read()); imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]; assert imports == ['abc'], f'expected only abc import, got {imports}'; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `plugin_base.py` exists at repo root
    - All 5 tests in `tests/test_plugin_base.py` pass
    - `from plugin_base import RetailerPlugin, PLUGIN_API_VERSION` succeeds
    - `PLUGIN_API_VERSION == 1`
    - Only stdlib imports (`abc`); no `import yaml`, `import selenium`, `import pydantic`
    - Class definition contains `@abstractmethod` decorator on both `check_availability` and `auto_buy`
    - File is under 60 lines
  </acceptance_criteria>
  <done>plugin_base.py committed, all ABC contract tests green</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| third-party plugin code → core | A community-supplied plugin is loaded into the same process; the ABC is the structural contract that lets us reject malformed plugins early |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-1-CORE-01 | Tampering | RetailerPlugin contract | mitigate | Abstract methods enforced by Python `abc` machinery; subclass missing required methods fails at instantiation, not at runtime mid-purchase |
| T-1-CORE-02 | Repudiation | PLUGIN_API_VERSION | mitigate | Integer constant in source enables future plugin-registry version checks (Phase 2 PLG infrastructure) to refuse incompatible plugins |
| T-1-CORE-IMPORT | Elevation of Privilege | plugin_base.py imports | accept | ABC file imports only stdlib `abc`; no attack surface introduced. Plugin loading sandbox is a Phase 2 concern (PLG-01..03) |
</threat_model>

<verification>
- `pytest -x -q tests/test_plugin_base.py` passes (5 tests)
- `python -c "from plugin_base import RetailerPlugin, PLUGIN_API_VERSION"` succeeds with no stderr output
- `wc -l plugin_base.py` reports < 60 lines
- `grep -c "@abstractmethod" plugin_base.py` reports 2
</verification>

<success_criteria>
- CORE-01 satisfied: ABC defines all four methods with the D-01 signatures (no `driver` param)
- CORE-02 satisfied: `PLUGIN_API_VERSION = 1` exported; `login` and `detect_captcha` have working no-op defaults
- Phase 2 contributors can subclass RetailerPlugin with only two method bodies
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundations-security/01-02-SUMMARY.md`
</output>
