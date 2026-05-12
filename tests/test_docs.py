"""SEC-06: README disclaimer substring tests (Plan 01-06)."""
import pathlib


def test_readme_has_disclaimer():
    text = pathlib.Path("README.md").read_text(encoding="utf-8").lower()
    assert "personal use" in text, "SEC-06: README must mention personal use"
    assert "tos" in text or "terms of service" in text, (
        "SEC-06: README must mention TOS / terms of service"
    )
    assert "account" in text, "SEC-06: README must mention account risk"
