---
phase: 01-foundations-security
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - requirements.txt
  - pyproject.toml
  - tests/conftest.py
  - tests/test_requirements.py
  - tests/test_python_version.py
autonomous: true
requirements:
  - INFRA-01
tags:
  - python
  - pytest
  - pydantic-settings
  - dependency-pinning

must_haves:
  truths:
    - "pytest collects from tests/ with no import errors"
    - "Every line in requirements.txt has an exact == version pin"
    - "requirements.txt contains no duplicate package names (after PEP 503 normalization)"
    - "pyproject.toml declares requires-python >= 3.11"
    - "pydantic, pydantic-settings[yaml], selenium, webdriver-manager, pygame, colorama, requests, pytest are all pinned"
  artifacts:
    - path: "requirements.txt"
      provides: "Pinned dependency manifest"
      contains: "pydantic==2.13.3"
    - path: "pyproject.toml"
      provides: "Build metadata + Python version constraint + pytest config"
      contains: "requires-python = \">=3.11\""
    - path: "tests/conftest.py"
      provides: "Shared pytest fixtures (env isolation, tmp_config_yml)"
    - path: "tests/test_requirements.py"
      provides: "Smoke test enforcing pinning + no duplicates"
    - path: "tests/test_python_version.py"
      provides: "Smoke test enforcing requires-python declaration"
  key_links:
    - from: "pyproject.toml"
      to: "pytest"
      via: "[tool.pytest.ini_options] testpaths"
      pattern: "testpaths.*tests"
---

<objective>
Bootstrap the test framework, pin every dependency, and declare Python 3.11+ as the project minimum so all subsequent plans in this phase have a working pytest harness and a deterministic dependency surface (INFRA-01).

Purpose: Phase 1 has no test infrastructure today (`tests/test_config.py` exists but pytest is unpinned and no conftest exists). This plan ships Wave 0 so Plans 02-05 can write tests against a stable pytest installation.

Output: pinned `requirements.txt`, new `pyproject.toml`, `tests/conftest.py`, two smoke tests proving the pinning contract.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundations-security/01-CONTEXT.md
@.planning/phases/01-foundations-security/01-PATTERNS.md
@.planning/phases/01-foundations-security/01-VALIDATION.md
@requirements.txt
@tests/test_models.py
</context>

<interfaces>
<!-- requirements.txt today (current contents, to be replaced) -->
```
pytest
selenium
webdriver-manager
pyyaml
selenium          # duplicate
pyyaml            # duplicate
colorama
pygame
urllib3
requests
webdriver_manager # duplicate (different normalization)
```

<!-- Target dependency set (PATTERNS.md "requirements.txt" section, RESEARCH.md lines 166-175) -->
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

Notes: pyyaml drops out (transitive via pydantic-settings[yaml]); urllib3 drops out (transitive via requests).
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Pin requirements.txt and add pyproject.toml</name>
  <files>requirements.txt, pyproject.toml</files>
  <read_first>
    - requirements.txt (current state — will be fully replaced)
    - .planning/phases/01-foundations-security/01-PATTERNS.md (sections "requirements.txt" and "pyproject.toml")
  </read_first>
  <behavior>
    - requirements.txt contains exactly 8 lines, each `package==X.Y.Z`, no duplicates, no blank lines
    - pyproject.toml has `[project]` table with `name = "shoppybot"`, `version = "0.1.0"`, `requires-python = ">=3.11"`
    - pyproject.toml has `[tool.pytest.ini_options]` table with `testpaths = ["tests"]`
  </behavior>
  <action>
    1. Replace `requirements.txt` entirely with these 8 lines (one per line, no comments, no trailing blank line):
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
       Per D-07 (pydantic-settings) and PATTERNS.md "requirements.txt" section. Hash pins deferred per RESEARCH Open Question #2.
    2. Create `pyproject.toml` (file does not exist today):
       ```toml
       [project]
       name = "shoppybot"
       version = "0.1.0"
       requires-python = ">=3.11"

       [tool.pytest.ini_options]
       testpaths = ["tests"]
       ```
    3. Run `pip install -r requirements.txt` to confirm the pin set resolves cleanly.
  </action>
  <verify>
    <automated>python -c "import pathlib, re; lines = [l for l in pathlib.Path('requirements.txt').read_text().splitlines() if l.strip()]; assert len(lines) == 8, f'expected 8 lines, got {len(lines)}'; assert all('==' in l for l in lines), 'every line must have =='; names = [re.split(r'[=\\[]', l)[0].lower().replace('_','-') for l in lines]; assert len(names) == len(set(names)), f'duplicates: {names}'; print('OK')"</automated>
    <automated>python -c "import pathlib; t = pathlib.Path('pyproject.toml').read_text(); assert 'requires-python = \">=3.11\"' in t; assert '[tool.pytest.ini_options]' in t; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `requirements.txt` has 8 lines, every line matches regex `^[a-zA-Z0-9_.\-]+(\[[a-zA-Z]+\])?==\d+\.\d+\.\d+$`
    - No duplicate normalized package names in `requirements.txt`
    - `pyproject.toml` exists with `requires-python = ">=3.11"` substring
    - `pyproject.toml` contains `[tool.pytest.ini_options]` with `testpaths = ["tests"]`
    - `pip install -r requirements.txt` exits 0
  </acceptance_criteria>
  <done>requirements.txt fully replaced, pyproject.toml committed, pip install succeeds</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add tests/conftest.py and Wave 0 smoke tests</name>
  <files>tests/conftest.py, tests/test_requirements.py, tests/test_python_version.py</files>
  <read_first>
    - tests/test_models.py (analog for pytest fixture style — PATTERNS.md "test fixture style")
    - tests/test_config.py (analog for tmp_path pattern — to be deleted in Plan 03; do not import from it)
    - .planning/phases/01-foundations-security/01-VALIDATION.md (Wave 0 Requirements section)
  </read_first>
  <behavior>
    - test_requirements.py asserts every line in requirements.txt has `==` and there are no normalized duplicates
    - test_python_version.py asserts pyproject.toml declares `requires-python` with `>=3.11`
    - conftest.py exposes `tmp_config_yml(tmp_path, monkeypatch)` fixture that writes a minimal valid config.yml and chdirs into tmp_path
    - conftest.py exposes `clean_env(monkeypatch)` fixture that deletes any env var matching `SHOPBOT_*` so credential tests start clean
  </behavior>
  <action>
    1. Create `tests/conftest.py` with two fixtures:
       ```python
       import os
       import pytest

       @pytest.fixture
       def clean_env(monkeypatch):
           for key in list(os.environ):
               if key.startswith("SHOPBOT_"):
                   monkeypatch.delenv(key, raising=False)
           return monkeypatch

       @pytest.fixture
       def tmp_config_yml(tmp_path, monkeypatch):
           cfg = tmp_path / "config.yml"
           cfg.write_text(
               "selenium:\n  driver_path: ./chromedriver.exe\n"
               "debug:\n  logging_level: 3\n  test_mode: true\n"
               "open_browser: false\n"
               "platforms:\n  amazon:\n    enabled: true\n    credentials:\n      email: ''\n      password: ''\n"
               "available:\n  items: []\n"
           )
           monkeypatch.chdir(tmp_path)
           return cfg
       ```
    2. Create `tests/test_requirements.py`:
       ```python
       import pathlib
       import re

       def test_every_line_has_exact_pin():
           lines = [l for l in pathlib.Path("requirements.txt").read_text().splitlines() if l.strip()]
           pin_re = re.compile(r"^[a-zA-Z0-9_.\-]+(\[[a-zA-Z0-9_,\-]+\])?==\d+\.\d+\.\d+$")
           for line in lines:
               assert pin_re.match(line), f"unpinned or malformed: {line!r}"

       def test_no_duplicate_packages():
           lines = [l for l in pathlib.Path("requirements.txt").read_text().splitlines() if l.strip()]
           names = [re.split(r"[=\[]", l)[0].lower().replace("_", "-") for l in lines]
           assert len(names) == len(set(names)), f"duplicates present: {names}"
       ```
    3. Create `tests/test_python_version.py`:
       ```python
       import pathlib

       def test_requires_python_declared():
           text = pathlib.Path("pyproject.toml").read_text()
           assert 'requires-python = ">=3.11"' in text, "pyproject.toml must declare requires-python >= 3.11"
       ```
    4. Run `pytest -x -q tests/test_requirements.py tests/test_python_version.py` — both must pass.
  </action>
  <verify>
    <automated>pytest -x -q tests/test_requirements.py tests/test_python_version.py</automated>
    <automated>python -c "import pathlib; assert pathlib.Path('tests/conftest.py').exists(); t = pathlib.Path('tests/conftest.py').read_text(); assert 'tmp_config_yml' in t and 'clean_env' in t; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `tests/conftest.py` exists, exports `clean_env` and `tmp_config_yml` fixtures
    - `tests/test_requirements.py` passes both `test_every_line_has_exact_pin` and `test_no_duplicate_packages`
    - `tests/test_python_version.py::test_requires_python_declared` passes
    - `pytest -x -q` exits 0 with at least 3 tests collected
  </acceptance_criteria>
  <done>conftest + 2 smoke test files committed, all green</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| developer install → runtime | Unpinned deps allow supply-chain version drift |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-1-INFRA-01 | Tampering | requirements.txt | mitigate | Exact `==X.Y.Z` pins on every line; smoke test (`tests/test_requirements.py`) blocks PRs that re-introduce unpinned entries |
| T-1-INFRA-01b | Tampering | requirements.txt duplicates | mitigate | Normalized-name duplicate check in `test_no_duplicate_packages` (PEP 503 normalization) |
| T-1-PYVER-01 | Denial of Service | runtime on Python <3.11 | mitigate | `requires-python = ">=3.11"` in pyproject.toml + `test_python_version.py` smoke; runtime guard added in Plan 05 (main.py) |
| T-1-PIN-HASH | Tampering | pip resolver | accept | Hash pins deferred per RESEARCH Open Question #2; revisit when supply-chain attack surface widens |
</threat_model>

<verification>
- `pytest -x -q` collects and runs at least 3 tests, exit code 0
- `pip install -r requirements.txt` resolves cleanly on Python 3.11+
- `cat requirements.txt | wc -l` reports 8
- `grep -c "^[a-z]" requirements.txt` reports 8 (one package per line)
</verification>

<success_criteria>
- INFRA-01 satisfied: every dep pinned, no duplicates, Python 3.11+ declared
- Wave 0 framework available: pytest discovers tests, conftest fixtures importable, all subsequent plans can write `pytest`-runnable tests
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundations-security/01-01-SUMMARY.md`
</output>
