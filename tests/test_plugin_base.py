import pytest
from core.plugin_base import RetailerPlugin, PLUGIN_API_VERSION


def test_version_constant():
    assert PLUGIN_API_VERSION == 1


def test_incomplete_plugin_raises():
    class Incomplete(RetailerPlugin):
        pass
    with pytest.raises(TypeError):
        Incomplete()


def test_abstract_methods_enforced():
    class MissingBuy(RetailerPlugin):
        def check_availability(self, url):
            return True
    with pytest.raises(TypeError):
        MissingBuy()


def test_login_noop():
    class Minimal(RetailerPlugin):
        def check_availability(self, url):
            return True

        def auto_buy(self, driver, url, config):
            return False

    p = Minimal()
    assert p.login(None, {}) is None


def test_detect_captcha_noop():
    class Minimal(RetailerPlugin):
        def check_availability(self, url):
            return True

        def auto_buy(self, driver, url, config):
            return False

    p = Minimal()
    assert p.detect_captcha(None) is False
