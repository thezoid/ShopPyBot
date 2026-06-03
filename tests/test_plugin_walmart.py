"""Scaffold for Walmart plugin tests.

Downstream plan: 06-03
Requirements: PLG-04, ANTI-02, ANTI-03, SC4

This file will be filled by Plan 06-03 with tests covering:
  - WalmartPlugin satisfies RetailerPlugin ABC
  - domain_patterns includes "walmart.com"
  - setup() passes headless=True/False to nodriver.start (ANTI-03)
  - setup() passes --user-agent=<ua> in browser_args when user_agents non-empty (ANTI-02)
  - Plugin docstring contains "PerimeterX/HUMAN Security" (SC4)
"""

import pytest


@pytest.mark.skip(reason="scaffold -- filled by Plan 06-03")
def test_placeholder_walmart():
    """Placeholder: see module docstring for what this file will cover."""
    pass
