from pathlib import Path

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


# ---------------------------------------------------------------------------
# REG-02: registry metadata class attributes (difficulty, requires_proxy, requires_captcha)
# ---------------------------------------------------------------------------


def test_defaults():
    """MinimalPlugin inherits difficulty='medium', requires_proxy=False, requires_captcha=False."""
    p = MinimalPlugin(config=None)
    assert p.difficulty == "medium"
    assert p.requires_proxy is False
    assert p.requires_captcha is False


def test_override():
    """A subclass explicitly setting difficulty='hard' and requires_proxy=True reports those values."""
    class HardPlugin(RetailerPlugin):
        domain_patterns = ["hard.com"]
        difficulty = "hard"
        requires_proxy = True

        async def check_availability(self, url: str) -> bool:
            return True

        async def auto_buy(self, url: str) -> bool:
            return False

    p = HardPlugin(config=None)
    assert p.difficulty == "hard"
    assert p.requires_proxy is True
    assert p.requires_captcha is False  # still inherits default


def test_invalid_difficulty_raises():
    """Defining a subclass with an invalid difficulty value raises ValueError at class-definition time."""
    with pytest.raises(ValueError, match="Easy"):
        class BadPlugin(RetailerPlugin):
            domain_patterns = ["bad.com"]
            difficulty = "Easy"  # wrong case -- must fail at class-definition time

            async def check_availability(self, url: str) -> bool:
                return True

            async def auto_buy(self, url: str) -> bool:
                return False


def test_existing_plugins_load():
    """All existing shopbot_plugin_*.py files load unchanged with valid defaults (REG-02)."""
    from core.registry import _discover_plugins

    plugins_dir = Path(__file__).parent.parent / "plugins"
    plugin_classes = _discover_plugins(plugins_dir)
    assert len(plugin_classes) >= 7, (
        f"Expected >= 7 plugin classes, found {len(plugin_classes)}"
    )
    _valid = {"easy", "medium", "hard"}
    for cls in plugin_classes:
        instance = cls(config=None)
        assert instance.difficulty in _valid, (
            f"{cls.__name__}.difficulty={instance.difficulty!r} is not a valid value"
        )
        assert isinstance(instance.requires_proxy, bool), (
            f"{cls.__name__}.requires_proxy is not a bool"
        )
        assert isinstance(instance.requires_captcha, bool), (
            f"{cls.__name__}.requires_captcha is not a bool"
        )
