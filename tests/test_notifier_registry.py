"""GREEN tests for notifier_registry.discover_notifiers (Plan 05-02).

Mirrors plugin_registry discovery tests minus URL routing. Verifies async
shape, sorted iteration, non-prefix skip, and lenient broken-module load.
"""
import inspect
import textwrap
from types import SimpleNamespace

import pytest

from notifier_registry import NOTIFIER_PREFIX, discover_notifiers


def _writeNotifier(notifiersDir, fileName: str, body: str) -> None:
    (notifiersDir / fileName).write_text(textwrap.dedent(body))


def _appConfigStub() -> SimpleNamespace:
    """Minimal stub: provides .notifications with attribute access per name."""
    return SimpleNamespace(notifications=SimpleNamespace(a=None, b=None, broken=None))


def test_discoverNotifiersIsAsyncCoroutine():
    assert inspect.iscoroutinefunction(discover_notifiers)


def test_prefixConstantMatchesPlan():
    assert NOTIFIER_PREFIX == "shopbot_notifier_"


@pytest.mark.asyncio
async def test_discoverFindsShopbotNotifierFiles(tmp_path):
    notifiersDir = tmp_path / "notifiers"
    notifiersDir.mkdir()
    (notifiersDir / "__init__.py").write_text("")
    _writeNotifier(notifiersDir, "shopbot_notifier_a.py", """
        from notifier_base import Notifier
        class ANotifier(Notifier):
            name = 'a'
            def __init__(self, *, sub_config, app_config):
                self.enabled = True
            async def send(self, event):
                return None
    """)
    _writeNotifier(notifiersDir, "shopbot_notifier_b.py", """
        from notifier_base import Notifier
        class BNotifier(Notifier):
            name = 'b'
            def __init__(self, *, sub_config, app_config):
                self.enabled = True
            async def send(self, event):
                return None
    """)

    instances = await discover_notifiers(notifiersDir, app_config=_appConfigStub())

    assert len(instances) == 2
    names = [n.name for n in instances]
    assert names == ["a", "b"]


@pytest.mark.asyncio
async def test_nonPrefixFileSkipped(tmp_path):
    notifiersDir = tmp_path / "notifiers"
    notifiersDir.mkdir()
    _writeNotifier(notifiersDir, "not_a_notifier.py", """
        from notifier_base import Notifier
        class StrayNotifier(Notifier):
            name = 'stray'
            async def send(self, event):
                return None
    """)
    _writeNotifier(notifiersDir, "shopbot_notifier_a.py", """
        from notifier_base import Notifier
        class ANotifier(Notifier):
            name = 'a'
            def __init__(self, *, sub_config, app_config):
                self.enabled = True
            async def send(self, event):
                return None
    """)

    instances = await discover_notifiers(notifiersDir, app_config=_appConfigStub())

    assert [n.name for n in instances] == ["a"]


@pytest.mark.asyncio
async def test_brokenModuleLoggedAndSkipped(tmp_path):
    notifiersDir = tmp_path / "notifiers"
    notifiersDir.mkdir()
    _writeNotifier(notifiersDir, "shopbot_notifier_broken.py", """
        raise ImportError('intentional failure for test')
    """)
    _writeNotifier(notifiersDir, "shopbot_notifier_a.py", """
        from notifier_base import Notifier
        class ANotifier(Notifier):
            name = 'a'
            def __init__(self, *, sub_config, app_config):
                self.enabled = True
            async def send(self, event):
                return None
    """)

    instances = await discover_notifiers(notifiersDir, app_config=_appConfigStub())

    assert [n.name for n in instances] == ["a"]


@pytest.mark.asyncio
async def test_noNotifierSubclassInFileSkipped(tmp_path):
    notifiersDir = tmp_path / "notifiers"
    notifiersDir.mkdir()
    _writeNotifier(notifiersDir, "shopbot_notifier_empty.py", """
        # no Notifier subclass here
        x = 1
    """)
    _writeNotifier(notifiersDir, "shopbot_notifier_a.py", """
        from notifier_base import Notifier
        class ANotifier(Notifier):
            name = 'a'
            def __init__(self, *, sub_config, app_config):
                self.enabled = True
            async def send(self, event):
                return None
    """)

    instances = await discover_notifiers(notifiersDir, app_config=_appConfigStub())

    assert [n.name for n in instances] == ["a"]


@pytest.mark.asyncio
async def test_subConfigWiredFromAppConfig(tmp_path):
    notifiersDir = tmp_path / "notifiers"
    notifiersDir.mkdir()
    _writeNotifier(notifiersDir, "shopbot_notifier_a.py", """
        from notifier_base import Notifier
        class ANotifier(Notifier):
            name = 'a'
            def __init__(self, *, sub_config, app_config):
                self.sub = sub_config
                self.app = app_config
                self.enabled = bool(sub_config and getattr(sub_config, 'enabled', False))
            async def send(self, event):
                return None
    """)
    appConfig = SimpleNamespace(
        notifications=SimpleNamespace(a=SimpleNamespace(enabled=True)),
    )

    instances = await discover_notifiers(notifiersDir, app_config=appConfig)

    assert len(instances) == 1
    inst = instances[0]
    assert inst.enabled is True
    assert inst.sub is appConfig.notifications.a
    assert inst.app is appConfig
