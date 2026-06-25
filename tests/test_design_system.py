"""test_design_system.py: CSS file static analysis and vendor file existence tests."""
import re
import pathlib

ROOT = pathlib.Path(__file__).parent.parent


def test_no_hardcoded_hex_in_components():
    """components.css must contain zero hardcoded hex or rgb() color values."""
    css = (ROOT / "web" / "static" / "components.css").read_text(encoding="utf-8")
    # Strip comments before scanning
    css_no_comments = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
    hex_pattern = re.compile(r'(?<![a-zA-Z0-9_-])#[0-9a-fA-F]{3,6}\b')
    rgb_pattern = re.compile(r'rgb\(')
    assert not hex_pattern.search(css_no_comments), "Hardcoded hex found in components.css"
    assert not rgb_pattern.search(css_no_comments), "Hardcoded rgb() found in components.css"


def test_all_required_tokens_declared():
    """tokens.css must declare all --color-* and --space-* tokens from UI-SPEC."""
    css = (ROOT / "web" / "static" / "tokens.css").read_text(encoding="utf-8")
    required = [
        "--color-bg", "--color-surface", "--color-border", "--color-text",
        "--color-text-muted", "--color-accent", "--color-accent-fg",
        "--color-destructive", "--color-destructive-fg", "--color-destructive-subtle",
        "--color-status-ok", "--color-status-neutral", "--color-status-warn",
        "--color-status-err",
        "--space-xs", "--space-sm", "--space-md", "--space-lg",
        "--space-xl", "--space-2xl",
        "--text-sm", "--text-body", "--text-lg", "--text-xl",
        "--weight-normal", "--weight-semibold",
        "--font-family",
    ]
    for token in required:
        assert token in css, f"Token {token!r} not declared in tokens.css"


def test_uplot_vendor_files_exist():
    """uPlot 1.6.32 vendor files must exist at web/static/vendor/."""
    js_path  = ROOT / "web" / "static" / "vendor" / "uplot.iife.min.js"
    css_path = ROOT / "web" / "static" / "vendor" / "uplot.min.css"
    assert js_path.exists(),  f"Missing: {js_path}"
    assert css_path.exists(), f"Missing: {css_path}"
