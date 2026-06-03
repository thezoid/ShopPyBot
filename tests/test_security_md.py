"""SECURITY.md content tests and SC1 registry discovery gate.

Covers:
  SC4 -- SECURITY.md contains a row for each of the five new platforms, plus
         the exact phrases required by the context spec:
           * Walmart: "PerimeterX/HUMAN Security"
           * Target:  "Akamai" and "headless"
           * GameStop: row presence (CAPTCHA risk documented)
           * Square Enix / NewEgg: row presence
  SC1 -- The real plugins/ directory yields exactly 7 discovered plugin classes
         via PluginRegistry with no core edits (amazon, bestbuy, walmart, target,
         gamestop, squareenix, newegg).
"""

from pathlib import Path

import pytest

from core.registry import PluginRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
SECURITY_MD = REPO_ROOT / "SECURITY.md"


def _read_security_md() -> str:
    return SECURITY_MD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SC4: row presence tests
# ---------------------------------------------------------------------------


def test_security_md_has_walmart_row():
    """SECURITY.md must contain a table row for walmart.com (SC4)."""
    assert "walmart.com" in _read_security_md()


def test_security_md_has_target_row():
    """SECURITY.md must contain a table row for target.com (SC4)."""
    assert "target.com" in _read_security_md()


def test_security_md_has_gamestop_row():
    """SECURITY.md must contain a table row for gamestop.com (SC4)."""
    assert "gamestop.com" in _read_security_md()


def test_security_md_has_squareenix_row():
    """SECURITY.md must contain a table row for store.square-enix-games.com (SC4)."""
    assert "store.square-enix-games.com" in _read_security_md()


def test_security_md_has_newegg_row():
    """SECURITY.md must contain a table row for newegg.com (SC4)."""
    assert "newegg.com" in _read_security_md()


# ---------------------------------------------------------------------------
# SC4: exact-phrase tests
# ---------------------------------------------------------------------------


def test_security_md_walmart_phrase_perimeter_x():
    """Walmart row must contain the exact phrase 'PerimeterX/HUMAN Security' (SC4)."""
    assert "PerimeterX/HUMAN Security" in _read_security_md()


def test_security_md_target_phrase_akamai():
    """Target row must contain the exact word 'Akamai' (SC4)."""
    assert "Akamai" in _read_security_md()


def test_security_md_target_phrase_headless():
    """Target row must contain the word 'headless' (SC4)."""
    assert "headless" in _read_security_md()


# ---------------------------------------------------------------------------
# SC1: real plugins/ registry discovers all 7 plugins
# ---------------------------------------------------------------------------


def test_registry_discovers_all_seven_plugins():
    """SC1 gate: PluginRegistry against the real plugins/ dir must find exactly 7 classes.

    Expected: amazon, bestbuy, walmart, target, gamestop, squareenix, newegg.
    This proves all five new plugin files load through the registry with no core edits.
    """
    plugins_dir = REPO_ROOT / "plugins"
    registry = PluginRegistry(config=None, plugins_dir=plugins_dir)
    assert len(registry._all_plugins) == 7, (
        f"Expected 7 plugins, found {len(registry._all_plugins)}: "
        f"{[type(p).__name__ for p in registry._all_plugins]}"
    )
