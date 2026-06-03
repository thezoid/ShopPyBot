"""Tests for plugins/example_plugin.py contributor skeleton.

Verifies that the FakeShopPlugin:
  - Can be loaded via importlib.util.spec_from_file_location (same path the
    registry uses), proving it is discovery-compatible.
  - Satisfies the RetailerPlugin v2 ABC (all abstract methods implemented,
    domain_patterns declared, driver starts as None).
"""

import importlib.util
from pathlib import Path

from core.plugin_base import RetailerPlugin

_EXAMPLE_PATH = Path(__file__).parent.parent / "plugins" / "example_plugin.py"


def test_example_plugin_imports():
    """Loading example_plugin.py via spec_from_file_location must not raise."""
    spec = importlib.util.spec_from_file_location("example_plugin", _EXAMPLE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # If we reach here without exception, the file loaded cleanly.
    assert module is not None


def test_example_plugin_satisfies_abc():
    """FakeShopPlugin must be a concrete RetailerPlugin v2 subclass."""
    spec = importlib.util.spec_from_file_location("example_plugin", _EXAMPLE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cls = module.FakeShopPlugin

    # Must be a proper subclass of the v2 ABC.
    assert issubclass(cls, RetailerPlugin)

    # Must be instantiable with config=None (all abstract methods implemented).
    instance = cls(config=None)

    # driver is set to None by __init__; setup() (async) is what starts the browser.
    assert instance.driver is None

    # domain_patterns must be the canonical value for this fictional retailer.
    assert instance.domain_patterns == ["fakeshop.com"]
