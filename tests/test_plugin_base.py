import typing

import pytest
from plugin_base import RetailerPlugin, PLUGIN_API_VERSION


class _MinimalPlugin(RetailerPlugin):
    domain_pattern = ["example.com"]

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


def test_domain_pattern_is_list():
    hints = typing.get_type_hints(RetailerPlugin)
    assert hints["domain_pattern"] == list[str]


def test_domain_pattern_default_is_empty_list():
    assert RetailerPlugin.domain_pattern == []


def test_login_at_startup_default_false():
    assert RetailerPlugin.login_at_startup is False


def test_shutdownIsAsyncCoroutineFunction():
    """Phase 4 D-04: shutdown must be an async coroutine, not a sync method."""
    import inspect
    from plugin_base import RetailerPlugin
    assert inspect.iscoroutinefunction(RetailerPlugin.shutdown)
