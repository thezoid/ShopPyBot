import pytest
from core.plugin_base import RetailerPlugin, PLUGIN_API_VERSION


# ---------------------------------------------------------------------------
# Module-level concrete stub for v2 ABC (async methods, no driver parameter)
# ---------------------------------------------------------------------------


class MinimalPlugin(RetailerPlugin):
    """Minimal concrete subclass satisfying the v2 abstract contract."""

    domain_patterns = ["example.com"]

    async def check_availability(self, url: str) -> bool:
        return True

    async def auto_buy(self, url: str) -> bool:
        return False


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


def test_version_constant():
    assert PLUGIN_API_VERSION == 2


# ---------------------------------------------------------------------------
# ABC enforcement (sync — TypeError on instantiation; no async needed)
# ---------------------------------------------------------------------------


def test_incomplete_plugin_raises():
    """A subclass that implements nothing cannot be instantiated."""
    class Incomplete(RetailerPlugin):
        pass

    with pytest.raises(TypeError):
        Incomplete(config=None)


def test_abstract_methods_enforced():
    """A subclass missing auto_buy cannot be instantiated."""
    class MissingBuy(RetailerPlugin):
        domain_patterns = ["x.com"]

        async def check_availability(self, url):
            return True

    with pytest.raises(TypeError):
        MissingBuy(config=None)


def test_minimal_plugin_instantiates():
    """A complete subclass with both abstract methods CAN be instantiated."""
    p = MinimalPlugin(config=None)
    assert isinstance(p, RetailerPlugin)


# ---------------------------------------------------------------------------
# Async no-op defaults
# ---------------------------------------------------------------------------


async def test_login_noop():
    p = MinimalPlugin(config=None)
    result = await p.login()
    assert result is None


async def test_detect_captcha_noop():
    p = MinimalPlugin(config=None)
    result = await p.detect_captcha()
    assert result is False


# ---------------------------------------------------------------------------
# __init__ contract (D-06: driver is None after construction; built in setup())
# ---------------------------------------------------------------------------


def test_init_sets_driver_none():
    p = MinimalPlugin(config=None)
    assert p.driver is None
