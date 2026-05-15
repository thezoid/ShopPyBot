"""Phase 5 RED skeleton for notifier_registry (see 05-01-PLAN.md).

All tests in this file FAIL today (ImportError at collection) until Plan
05-02 ships notifier_registry.py with discover_notifiers.
"""
import inspect
from pathlib import Path

import pytest

# RED: notifier_registry does not exist yet; collection ImportError is the signal.
from notifier_registry import discover_notifiers  # type: ignore[import-not-found]


def test_discoverNotifiersIsAsyncCoroutine():
    assert inspect.iscoroutinefunction(discover_notifiers)


@pytest.mark.asyncio
async def test_discoverFindsShopbotNotifierFiles(tmp_path):
    notifiersDir = tmp_path / "notifiers"
    notifiersDir.mkdir()
    (notifiersDir / "__init__.py").write_text("")
    (notifiersDir / "shopbot_notifier_a.py").write_text(
        "from notifier_base import Notifier\n"
        "class ANotifier(Notifier):\n"
        "    name = 'a'\n"
        "    async def send(self, event): return None\n"
    )
    (notifiersDir / "shopbot_notifier_b.py").write_text(
        "from notifier_base import Notifier\n"
        "class BNotifier(Notifier):\n"
        "    name = 'b'\n"
        "    async def send(self, event): return None\n"
    )
    instances = await discover_notifiers(notifiersDir, app_config=None)
    assert len(instances) == 2
