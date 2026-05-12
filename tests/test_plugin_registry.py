"""Tests for plugin_registry: discovery, URL routing, coverage check.

D-04 Phase A: discover() is lenient (warn + skip on per-plugin failure).
D-04 Phase B: verify_coverage() is strict (raises ValueError on uncovered URL).
"""
import pytest

from plugin_base import RetailerPlugin


PLUGIN_BODY_TEMPLATE = '''
from plugin_base import RetailerPlugin

class TestPlugin(RetailerPlugin):
    domain_pattern = {domain_pattern!r}
    login_at_startup = False

    def __init__(self, platform_config, *, cvv=None, driver_path=None):
        super().__init__(platform_config)
        self.driver = None

    def check_availability(self, url):
        return False

    def auto_buy(self, url, config):
        return False
'''


def _write_plugin(plugins_dir, filename, body):
    path = plugins_dir / filename
    path.write_text(body)
    return path


class _Item:
    def __init__(self, link):
        self.link = link


def _make_inline_plugin(patterns):
    """Build a minimal in-memory RetailerPlugin subclass for routing tests."""

    class _InlinePlugin(RetailerPlugin):
        domain_pattern = list(patterns)
        login_at_startup = False

        def __init__(self):
            super().__init__(None)
            self.driver = None

        def check_availability(self, url):
            return False

        def auto_buy(self, url, config):
            return False

    return _InlinePlugin()


# ---------- _normalize_netloc / _matches ----------

def test_normalize_netloc_lowercases_and_strips_port():
    from plugin_registry import _normalize_netloc
    assert _normalize_netloc("https://Amazon.Com:443/dp/X") == "amazon.com"


def test_normalize_netloc_strips_trailing_dot():
    from plugin_registry import _normalize_netloc
    assert _normalize_netloc("https://amazon.com./dp/X") == "amazon.com"


def test_matches_exact_and_subdomain():
    from plugin_registry import _matches
    assert _matches("amazon.com", "amazon.com") is True
    assert _matches("www.amazon.com", "amazon.com") is True


def test_matches_rejects_substring_attack():
    from plugin_registry import _matches
    assert _matches("evilamazon.com", "amazon.com") is False


# ---------- discover() ----------

def test_discover_finds_prefixed_plugin(tmp_plugins_dir):
    from plugin_registry import discover
    _write_plugin(
        tmp_plugins_dir,
        "shopbot_plugin_test.py",
        PLUGIN_BODY_TEMPLATE.format(domain_pattern=["test.example.com"]),
    )
    registry = discover(tmp_plugins_dir, app_config=None, cvvs={})
    assert len(registry) == 1
    assert registry[0].__class__.__name__ == "TestPlugin"


def test_discover_skips_example_plugin(tmp_plugins_dir, capsys):
    from plugin_registry import discover
    _write_plugin(
        tmp_plugins_dir,
        "example_plugin.py",
        PLUGIN_BODY_TEMPLATE.format(domain_pattern=["example.com"]),
    )
    registry = discover(tmp_plugins_dir, app_config=None, cvvs={})
    assert registry == []
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "example_plugin.py" in combined
    assert "INFO" in combined.upper()


def test_discover_ignores_dunder(tmp_plugins_dir, capsys):
    from plugin_registry import discover
    (tmp_plugins_dir / "__init__.py").write_text("")
    (tmp_plugins_dir / "_helpers.py").write_text("x = 1\n")
    registry = discover(tmp_plugins_dir, app_config=None, cvvs={})
    assert registry == []
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "__init__.py" not in combined
    assert "_helpers.py" not in combined


def test_discover_lenient_on_import_error(tmp_plugins_dir, capsys):
    from plugin_registry import discover
    _write_plugin(
        tmp_plugins_dir,
        "shopbot_plugin_broken.py",
        'raise ImportError("nope")\n',
    )
    registry = discover(tmp_plugins_dir, app_config=None, cvvs={})
    assert registry == []
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "shopbot_plugin_broken.py" in combined
    assert "WARNING" in combined.upper()


def test_discover_hard_fails_on_two_classes(tmp_plugins_dir, capsys):
    from plugin_registry import discover
    body = (
        "from plugin_base import RetailerPlugin\n"
        "class PluginA(RetailerPlugin):\n"
        "    domain_pattern = ['a.com']\n"
        "    def __init__(self, platform_config, *, cvv=None, driver_path=None):\n"
        "        super().__init__(platform_config)\n"
        "    def check_availability(self, url): return False\n"
        "    def auto_buy(self, url, config): return False\n"
        "class PluginB(RetailerPlugin):\n"
        "    domain_pattern = ['b.com']\n"
        "    def __init__(self, platform_config, *, cvv=None, driver_path=None):\n"
        "        super().__init__(platform_config)\n"
        "    def check_availability(self, url): return False\n"
        "    def auto_buy(self, url, config): return False\n"
    )
    _write_plugin(tmp_plugins_dir, "shopbot_plugin_twoclasses.py", body)
    registry = discover(tmp_plugins_dir, app_config=None, cvvs={})
    assert registry == []
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "shopbot_plugin_twoclasses.py" in combined
    assert "WARNING" in combined.upper()


def test_discover_uses_name_attribute_when_present(tmp_plugins_dir):
    from plugin_registry import discover
    body = (
        "from plugin_base import RetailerPlugin\n"
        "class TestPlugin(RetailerPlugin):\n"
        "    name = 'custom'\n"
        "    domain_pattern = ['custom.example.com']\n"
        "    def __init__(self, platform_config, *, cvv=None, driver_path=None):\n"
        "        super().__init__(platform_config)\n"
        "    def check_availability(self, url): return False\n"
        "    def auto_buy(self, url, config): return False\n"
    )
    _write_plugin(tmp_plugins_dir, "shopbot_plugin_anything.py", body)
    registry = discover(tmp_plugins_dir, app_config=None, cvvs={})
    assert len(registry) == 1
    assert registry[0].name == "custom"


def test_discover_defaults_name_to_filename_stem(tmp_plugins_dir):
    from plugin_registry import discover
    _write_plugin(
        tmp_plugins_dir,
        "shopbot_plugin_test.py",
        PLUGIN_BODY_TEMPLATE.format(domain_pattern=["test.example.com"]),
    )
    registry = discover(tmp_plugins_dir, app_config=None, cvvs={})
    assert len(registry) == 1
    assert registry[0].name == "test"


def test_discover_rejects_empty_domain_pattern(tmp_plugins_dir, capsys):
    from plugin_registry import discover
    _write_plugin(
        tmp_plugins_dir,
        "shopbot_plugin_empty.py",
        PLUGIN_BODY_TEMPLATE.format(domain_pattern=[]),
    )
    registry = discover(tmp_plugins_dir, app_config=None, cvvs={})
    assert registry == []
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "shopbot_plugin_empty.py" in combined
    assert "WARNING" in combined.upper()


# ---------- route_url ----------

@pytest.mark.parametrize("url,expected_patterns", [
    ("https://www.amazon.com/dp/X", ["amazon.com"]),
    ("https://Amazon.Com:443/dp/X", ["amazon.com"]),
    ("https://www.bestbuy.com/site/X.p", ["bestbuy.com"]),
])
def test_route_url_returns_matching_plugin(url, expected_patterns):
    from plugin_registry import route_url
    amazon = _make_inline_plugin(["amazon.com"])
    bestbuy = _make_inline_plugin(["bestbuy.com"])
    registry = [amazon, bestbuy]
    plugin = route_url(url, registry)
    assert plugin is not None
    assert plugin.domain_pattern == expected_patterns


def test_route_url_returns_none_on_unmatched():
    from plugin_registry import route_url
    amazon = _make_inline_plugin(["amazon.com"])
    assert route_url("https://example.com/x", [amazon]) is None


# ---------- verify_coverage ----------

def test_verify_coverage_passes_when_all_urls_match():
    from plugin_registry import verify_coverage
    amazon = _make_inline_plugin(["amazon.com"])
    bestbuy = _make_inline_plugin(["bestbuy.com"])
    items = [
        _Item("https://www.amazon.com/dp/X"),
        _Item("https://www.bestbuy.com/site/Y.p"),
    ]
    verify_coverage([amazon, bestbuy], items)  # should not raise


def test_verify_coverage_raises_on_missing_plugin():
    from plugin_registry import verify_coverage
    amazon = _make_inline_plugin(["amazon.com"])
    items = [_Item("https://www.target.com/p/Z")]
    with pytest.raises(ValueError) as exc:
        verify_coverage([amazon], items)
    msg = str(exc.value)
    assert "target.com" in msg
    assert "shopbot_plugin_" in msg
