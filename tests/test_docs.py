"""Docs / example contract tests.

SEC-06: README disclaimer substring tests (Plan 01-06).
CORE-08: example_plugin.py + PLUGIN_DEV.md tests (Plan 02-05).
"""
import ast
import importlib.util
import pathlib
import sys
import types

import pytest


# ---------------------------------------------------------------------------
# SEC-06 (Plan 01-06)
# ---------------------------------------------------------------------------
def test_readme_has_disclaimer():
    text = pathlib.Path("README.md").read_text(encoding="utf-8").lower()
    assert "personal use" in text, "SEC-06: README must mention personal use"
    assert "tos" in text or "terms of service" in text, (
        "SEC-06: README must mention TOS / terms of service"
    )
    assert "account" in text, "SEC-06: README must mention account risk"


# ---------------------------------------------------------------------------
# CORE-08 (Plan 02-05): example_plugin.py + PLUGIN_DEV.md
# ---------------------------------------------------------------------------
EXAMPLE_FILE = pathlib.Path("plugins/example_plugin.py")
PLUGIN_DEV_FILE = pathlib.Path("plugins/PLUGIN_DEV.md")


def _parse_example():
    return ast.parse(EXAMPLE_FILE.read_text(encoding="utf-8"))


def _example_class_def() -> ast.ClassDef:
    for node in ast.walk(_parse_example()):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "RetailerPlugin":
                    return node
    raise AssertionError("No RetailerPlugin subclass found in example_plugin.py")


def test_example_plugin_file_exists():
    assert EXAMPLE_FILE.exists(), f"{EXAMPLE_FILE} must exist"


def test_example_plugin_filename_is_not_auto_loaded():
    # Registry only auto-loads files starting with "shopbot_plugin_".
    assert EXAMPLE_FILE.name.startswith("example"), (
        "example_plugin.py must start with 'example' so the registry skips it"
    )
    assert not EXAMPLE_FILE.name.startswith("shopbot_plugin_"), (
        "example_plugin.py must NOT start with 'shopbot_plugin_' or it would be auto-loaded"
    )


def test_example_plugin_subclasses_retailer_plugin():
    cls = _example_class_def()
    assert cls is not None
    # The subclass should be the only one; sanity check the name.
    assert cls.name.endswith("Plugin"), (
        "Plugin subclass should follow XxxPlugin naming convention"
    )


def test_example_plugin_declares_domain_pattern_list():
    cls = _example_class_def()
    for node in cls.body:
        if isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == "domain_pattern":
                assert isinstance(node.value, ast.List), (
                    "domain_pattern must be a list literal (D-01: list[str])"
                )
                return
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "domain_pattern":
                    assert isinstance(node.value, ast.List), (
                        "domain_pattern must be a list literal (D-01: list[str])"
                    )
                    return
    raise AssertionError("example_plugin.py must declare domain_pattern at class level")


def test_example_plugin_imports_build_driver():
    found = False
    for node in ast.walk(_parse_example()):
        if isinstance(node, ast.ImportFrom) and node.module == "driver":
            for alias in node.names:
                if alias.name == "build_driver":
                    found = True
    assert found, "example_plugin.py must `from driver import build_driver`"


def test_example_plugin_no_config_singleton_import():
    src = EXAMPLE_FILE.read_text(encoding="utf-8")
    assert "from config import" not in src, (
        "Anti-pattern (Q9 #1): plugins must never `from config import config`"
    )


def test_example_plugin_constructs_via_mock(monkeypatch):
    # Stub selenium.webdriver.common.by so `from selenium.webdriver.common.by import By`
    # succeeds without selenium's chrome submodule being available.
    selenium = types.ModuleType("selenium")
    webdriver_pkg = types.ModuleType("selenium.webdriver")
    common = types.ModuleType("selenium.webdriver.common")
    by_mod = types.ModuleType("selenium.webdriver.common.by")

    class _By:
        TAG_NAME = "tag name"

    by_mod.By = _By
    monkeypatch.setitem(sys.modules, "selenium", selenium)
    monkeypatch.setitem(sys.modules, "selenium.webdriver", webdriver_pkg)
    monkeypatch.setitem(sys.modules, "selenium.webdriver.common", common)
    monkeypatch.setitem(sys.modules, "selenium.webdriver.common.by", by_mod)

    # Stub `driver` module so `from driver import build_driver` returns a sentinel.
    sentinel = object()
    driver_stub = types.ModuleType("driver")
    driver_stub.build_driver = lambda *a, **kw: sentinel
    monkeypatch.setitem(sys.modules, "driver", driver_stub)

    spec = importlib.util.spec_from_file_location(
        "shoppybot_plugins.example_plugin_test", EXAMPLE_FILE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    plugin_cls = None
    for value in vars(module).values():
        if isinstance(value, type) and value.__name__.endswith("Plugin") and value.__module__ == module.__name__:
            plugin_cls = value
            break
    assert plugin_cls is not None, "example_plugin.py must define a *Plugin class"
    instance = plugin_cls(platform_config=None)
    assert instance.driver is sentinel, "build_driver must be called inside __init__"


# ---------------------------------------------------------------------------
# PLUGIN_DEV.md tests
# ---------------------------------------------------------------------------
def _plugin_dev_text() -> str:
    return PLUGIN_DEV_FILE.read_text(encoding="utf-8")


def test_plugin_dev_md_exists():
    assert PLUGIN_DEV_FILE.exists(), f"{PLUGIN_DEV_FILE} must exist"


REQUIRED_SECTION_SUBSTRINGS = [
    "what is a plugin",
    "the contract",
    "file naming",
    "domain_pattern",
    "driver",
    "config",
    "test",
    "plugin_api_version",
    # anti-patterns OR things-not-to-do — either heading wording is acceptable
]


@pytest.mark.parametrize("substring", REQUIRED_SECTION_SUBSTRINGS)
def test_plugin_dev_md_required_sections(substring):
    text = _plugin_dev_text().lower()
    assert substring in text, (
        f"PLUGIN_DEV.md must contain a section/heading mentioning '{substring}'"
    )


def test_plugin_dev_md_anti_patterns_section():
    text = _plugin_dev_text().lower()
    assert "anti-pattern" in text or "things not to do" in text, (
        "PLUGIN_DEV.md must include an anti-patterns / things-not-to-do section"
    )


def test_plugin_dev_md_references_example_plugin():
    assert "example_plugin.py" in _plugin_dev_text(), (
        "PLUGIN_DEV.md must reference example_plugin.py by filename"
    )


def test_plugin_dev_md_documents_list_str_type():
    assert "list[str]" in _plugin_dev_text(), (
        "PLUGIN_DEV.md must document domain_pattern as list[str] (locks D-01)"
    )


def test_plugin_dev_md_documents_login_at_startup():
    assert "login_at_startup" in _plugin_dev_text(), (
        "PLUGIN_DEV.md must document login_at_startup (D-03)"
    )


def test_plugin_dev_md_documents_one_class_per_file():
    assert "one plugin class per file" in _plugin_dev_text().lower(), (
        "PLUGIN_DEV.md must include the literal phrase 'one plugin class per file'"
    )


def test_plugin_dev_md_links_contributing():
    assert "CONTRIBUTING.md" in _plugin_dev_text(), (
        "PLUGIN_DEV.md must forward-link to CONTRIBUTING.md (Phase 3)"
    )


def test_plugin_dev_md_no_em_dashes():
    assert "—" not in _plugin_dev_text(), (
        "PLUGIN_DEV.md must not contain em dashes (CLAUDE.md style)"
    )


def test_plugin_dev_md_no_horizontal_rule():
    for lineno, line in enumerate(_plugin_dev_text().splitlines(), start=1):
        stripped = line.strip()
        assert stripped not in ("---", "***", "___"), (
            f"PLUGIN_DEV.md line {lineno} is a horizontal-rule line; use heading boundaries instead"
        )


# ---------------------------------------------------------------------------
# DOCS-01/02 (Plan 03-01): CONTRIBUTING.md
# ---------------------------------------------------------------------------
CONTRIBUTING_FILE = pathlib.Path("CONTRIBUTING.md")

COMMIT_TYPE_NAMES = {"feat", "fix", "docs", "style", "refactor", "test", "chore"}


def _contributing_text() -> str:
    return CONTRIBUTING_FILE.read_text(encoding="utf-8")


def test_contributing_md_exists():
    assert CONTRIBUTING_FILE.exists(), f"{CONTRIBUTING_FILE} must exist at repo root"


def test_contributing_md_documents_workflow():
    text = _contributing_text().lower()
    assert "fork" in text, "CONTRIBUTING.md must document the fork step"
    assert "branch" in text, "CONTRIBUTING.md must document the branch step"
    assert "pull request" in text or " pr " in text or "pr " in text, (
        "CONTRIBUTING.md must document pull request / PR step"
    )


def test_contributing_md_documents_commit_convention():
    text = _contributing_text()
    assert "type(scope): description" in text, (
        "CONTRIBUTING.md must document the literal 'type(scope): description' convention"
    )
    lower = text.lower()
    found = [name for name in COMMIT_TYPE_NAMES if name in lower]
    assert len(found) >= 3, (
        f"CONTRIBUTING.md must list at least 3 commit type names from {COMMIT_TYPE_NAMES}; found {found}"
    )


def test_contributing_md_documents_pytest():
    assert "pytest" in _contributing_text().lower(), (
        "CONTRIBUTING.md must mention pytest as the test runner"
    )


def test_contributing_md_links_plugin_dev():
    assert "plugins/PLUGIN_DEV.md" in _contributing_text(), (
        "CONTRIBUTING.md must link to plugins/PLUGIN_DEV.md"
    )


def test_contributing_md_links_security():
    assert "SECURITY.md" in _contributing_text(), (
        "CONTRIBUTING.md must link to SECURITY.md"
    )


def test_contributing_md_links_readme():
    assert "README.md" in _contributing_text(), (
        "CONTRIBUTING.md must link to README.md for TOS/disclaimer context"
    )


def test_contributing_md_has_plugin_checklist():
    assert "plugin submission checklist" in _contributing_text().lower(), (
        "CONTRIBUTING.md must include a 'Plugin Submission Checklist' section"
    )


def test_contributing_md_checklist_items():
    text = _contributing_text()
    required = [
        "shopbot_plugin_",
        "check_availability",
        "auto_buy",
        "domain_pattern",
        "list[str]",
        "anti-detection",
    ]
    missing = [s for s in required if s not in text]
    assert not missing, f"CONTRIBUTING.md checklist missing required substrings: {missing}"


def test_contributing_md_no_em_dashes():
    assert "—" not in _contributing_text(), (
        "CONTRIBUTING.md must not contain em dashes (CLAUDE.md style)"
    )


def test_contributing_md_no_horizontal_rule():
    for lineno, line in enumerate(_contributing_text().splitlines(), start=1):
        stripped = line.strip()
        assert stripped not in ("---", "***", "___"), (
            f"CONTRIBUTING.md line {lineno} is a horizontal-rule line; use heading boundaries instead"
        )
