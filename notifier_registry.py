"""Notifier discovery for ShopPyBot (Phase 5).

Mirrors plugin_registry.discover_async. Loads every shopbot_notifier_*.py
under notifiers/ via importlib, finds the single Notifier subclass per file,
and instantiates it with the app_config slice it needs. Per-notifier failures
log WARNING and are skipped (lenient load; consistent with plugin_registry
Phase A semantics from Phase 2 D-04).
"""
import asyncio
import importlib.util
import inspect
import sys
from pathlib import Path

from logger import writeLog
from notifier_base import Notifier

NOTIFIER_PREFIX = "shopbot_notifier_"


def _load_module(path: Path):
    mod_name = f"shoppybot_notifiers.{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not build spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def _find_notifier_class(module) -> type[Notifier]:
    candidates = [
        cls for _, cls in inspect.getmembers(module, inspect.isclass)
        if issubclass(cls, Notifier)
        and cls is not Notifier
        and cls.__module__ == module.__name__
    ]
    if len(candidates) == 0:
        raise ImportError(f"{module.__name__}: no Notifier subclass found")
    if len(candidates) > 1:
        names = ", ".join(c.__name__ for c in candidates)
        raise ImportError(
            f"{module.__name__}: expected one notifier class, found {len(candidates)}: {names}"
        )
    return candidates[0]


def _instantiate(cls, name: str, app_config) -> Notifier:
    """Pass per-channel config slice + full app_config (SMS needs test_mode)."""
    notifications = getattr(app_config, "notifications", None) if app_config else None
    sub = getattr(notifications, name, None) if notifications else None
    return cls(sub_config=sub, app_config=app_config)


def _iter_notifier_paths(notifiers_dir: Path):
    for path in sorted(Path(notifiers_dir).glob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        if not path.stem.startswith(NOTIFIER_PREFIX):
            writeLog(
                f"Skipped {path.name} (not auto-loaded; copy to "
                f"{NOTIFIER_PREFIX}<name>.py to enable)",
                "INFO",
            )
            continue
        yield path


def _load_and_instantiate(path: Path, app_config):
    try:
        cls = _find_notifier_class(_load_module(path))
    except Exception as e:
        writeLog(f"Failed to load {path.name}: {e}", "WARNING")
        return None
    name = getattr(cls, "name", "") or path.stem.removeprefix(NOTIFIER_PREFIX)
    try:
        inst = _instantiate(cls, name, app_config)
    except Exception as e:
        writeLog(
            f"Failed to instantiate {cls.__name__} from {path.name}: {e}",
            "WARNING",
        )
        return None
    inst.name = name
    return inst


async def discover_notifiers(
    notifiers_dir: Path,
    *,
    app_config,
) -> list[Notifier]:
    """Walk notifiers_dir for shopbot_notifier_*.py files and return instances.

    Mirrors plugin_registry.discover_async but with stagger=0 (no port race for
    notifiers) and no URL-routing coverage check. Each instantiation runs via
    asyncio.to_thread for symmetry with plugin discovery.
    """
    instances: list[Notifier] = []
    for path in _iter_notifier_paths(notifiers_dir):
        inst = await asyncio.to_thread(_load_and_instantiate, path, app_config)
        if inst is not None:
            instances.append(inst)
    return instances
