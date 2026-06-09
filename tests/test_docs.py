"""Doc-presence tests locking REG-01 and REG-04 content requirements."""

from pathlib import Path

ROOT = Path(__file__).parent.parent

_REGISTRY_DOC = ROOT / "docs" / "PLUGIN_REGISTRY.md"
_CONTRIBUTING = ROOT / "CONTRIBUTING.md"
_PR_TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
_PLUGIN_DEV = ROOT / "plugins" / "PLUGIN_DEV.md"

_REGISTRY_FIELDS = [
    "name",
    "platform",
    "domain patterns",
    "maintainer",
    "difficulty",
    "methods implemented",
    "last-verified",
    "proxy-required",
    "captcha-required",
]

_REQUIRED_ATTRS = ["difficulty", "requires_proxy", "requires_captcha"]


def test_plugin_registry_doc_has_9_fields():
    """docs/PLUGIN_REGISTRY.md exists and contains all 9 required field names (REG-01)."""
    text = _REGISTRY_DOC.read_text(encoding="utf-8").lower()
    for field in _REGISTRY_FIELDS:
        assert field in text, f"Missing field in PLUGIN_REGISTRY.md: {field!r}"
    assert "wiki" in text, "PLUGIN_REGISTRY.md must mention the GitHub wiki"


def test_contributing_requires_attrs():
    """CONTRIBUTING.md contains the 3 structured plugin metadata attributes (REG-04)."""
    text = _CONTRIBUTING.read_text(encoding="utf-8")
    for attr in _REQUIRED_ATTRS:
        assert attr in text, f"Missing attribute in CONTRIBUTING.md: {attr!r}"


def test_pr_template_requires_attrs():
    """.github/PULL_REQUEST_TEMPLATE.md contains the 3 structured attributes (REG-04)."""
    text = _PR_TEMPLATE.read_text(encoding="utf-8")
    for attr in _REQUIRED_ATTRS:
        assert attr in text, f"Missing attribute in PULL_REQUEST_TEMPLATE.md: {attr!r}"


def test_plugin_dev_documents_attrs():
    """plugins/PLUGIN_DEV.md ABC contract table documents the 3 new attributes (REG-04)."""
    text = _PLUGIN_DEV.read_text(encoding="utf-8")
    for attr in _REQUIRED_ATTRS:
        assert attr in text, f"Missing attribute in PLUGIN_DEV.md: {attr!r}"
