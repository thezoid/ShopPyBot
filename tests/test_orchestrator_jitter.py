"""Scaffold for orchestrator jitter tests.

Downstream plan: 06-02
Requirements: ANTI-01

This file will be filled by Plan 06-02 with tests covering:
  - _get_plugin_sleep returns value in [min_delay, max_delay] when platform config present
  - _get_plugin_sleep returns poll_interval when plugin has no min_delay/max_delay fields
  - _get_plugin_sleep returns poll_interval when plugin.config is None
"""

import pytest


@pytest.mark.skip(reason="scaffold -- filled by Plan 06-02")
def test_placeholder_jitter():
    """Placeholder: see module docstring for what this file will cover."""
    pass
