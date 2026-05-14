"""Plugin discovery, URL routing, and coverage check (Phase 2).

Two-phase load per CONTEXT.md D-04:
- Phase A (discover): lenient. Import errors logged + skipped.
- Phase B (verify_coverage): strict. Missing plugin for any URL raises ValueError.
"""
import asyncio
import importlib.util
import inspect
import sys
from pathlib import Path
from urllib.parse import urlparse

from logger import writeLog
from plugin_base import RetailerPlugin

PLUGIN_PREFIX = "shopbot_plugin_"
DEFAULT_STAGGER_SECONDS: float = 1.5


def _normalize_netloc(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    if ":" in netloc:
        netloc = netloc.split(":", 1)[0]
    if netloc.endswith("."):
        netloc = netloc[:-1]
    return netloc


def _matches(netloc: str, pattern: str) -> bool:
    p = pattern.lower().lstrip(".")
    return netloc == p or netloc.endswith("." + p)


def _load_module(path: Path):
    mod_name = f"shoppybot_plugins.{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not build spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def _find_plugin_class(module) -> type[RetailerPlugin]:
    candidates = [
        cls for _, cls in inspect.getmembers(module, inspect.isclass)
        if issubclass(cls, RetailerPlugin)
        and cls is not RetailerPlugin
        and cls.__module__ == module.__name__
    ]
    if len(candidates) == 0:
        raise ImportError(f"{module.__name__}: no RetailerPlugin subclass found")
    if len(candidates) > 1:
        names = ", ".join(c.__name__ for c in candidates)
        raise ImportError(
            f"{module.__name__}: expected one plugin class, found {len(candidates)}: {names}"
        )
    return candidates[0]


def _safe_platform(app_config, name):
    if app_config is None:
        return None
    platforms = getattr(app_config, "platforms", None) or {}
    if isinstance(platforms, dict):
        return platforms.get(name)
    return getattr(platforms, name, None)


def _safe_driver_path(app_config):
    if app_config is None:
        return None
    selenium = getattr(app_config, "selenium", None)
    return getattr(selenium, "driver_path", None) if selenium else None


def _load_plugin_class(path: Path) -> type[RetailerPlugin]:
    """Load module at path and return its single RetailerPlugin subclass.

    Raises ImportError on load failure, no-class, multi-class, or empty
    domain_pattern (D-01 import-time validation surfaced via D-04 Phase A).
    """
    module = _load_module(path)
    cls = _find_plugin_class(module)
    if not cls.domain_pattern:
        raise ImportError(
            f"{cls.__name__} declares empty domain_pattern; set "
            f"domain_pattern: list[str] to a non-empty list of hostnames"
        )
    return cls


def _instantiate(cls, name, app_config, cvvs):
    return cls(
        platform_config=_safe_platform(app_config, name),
        cvv=cvvs.get(name) if cvvs else None,
        driver_path=_safe_driver_path(app_config),
    )


def _iter_plugin_paths(plugins_dir: Path):
    """Yield sorted plugin file paths, logging+skipping non-conforming names."""
    for path in sorted(Path(plugins_dir).glob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        if not path.stem.startswith(PLUGIN_PREFIX):
            writeLog(
                f"Skipped {path.name} (not auto-loaded; copy to "
                f"{PLUGIN_PREFIX}<name>.py to enable)",
                "INFO",
            )
            continue
        yield path


def _load_and_instantiate(path: Path, app_config, cvvs):
    """Load module, find plugin class, instantiate. Returns instance or None.

    Per D-04 Phase A: load/instantiate failures log WARNING and return None.
    """
    try:
        cls = _load_plugin_class(path)
    except Exception as e:
        writeLog(f"Failed to load {path.name}: {e}", "WARNING")
        return None
    name = getattr(cls, "name", "") or path.stem.removeprefix(PLUGIN_PREFIX)
    try:
        inst = _instantiate(cls, name, app_config, cvvs)
    except Exception as e:
        writeLog(
            f"Failed to instantiate {cls.__name__} from {path.name}: {e}",
            "WARNING",
        )
        return None
    inst.name = name
    return inst


def discover(plugins_dir: Path, *, app_config, cvvs: dict[str, str]) -> list[RetailerPlugin]:
    """Walk plugins_dir for shopbot_plugin_*.py files and return instances.

    Per D-04 Phase A, per-plugin failures are logged as WARNING and skipped.
    """
    instances: list[RetailerPlugin] = []
    for path in _iter_plugin_paths(plugins_dir):
        inst = _load_and_instantiate(path, app_config, cvvs)
        if inst is not None:
            instances.append(inst)
    return instances


async def discover_async(
    plugins_dir: Path,
    *,
    app_config,
    cvvs: dict[str, str],
    stagger_seconds: float = DEFAULT_STAGGER_SECONDS,
) -> list[RetailerPlugin]:
    """Async plugin discovery with `stagger_seconds` sleep between plugins.

    The sleep happens BEFORE each plugin's instantiation (Pitfall 7) so the
    chromedriver TCP bind window cannot race with the next plugin. The first
    plugin instantiates immediately with no leading sleep. Per-plugin failures
    are logged as WARNING and skipped (D-04 Phase A). Each instantiation runs
    via asyncio.to_thread because plugin __init__ calls blocking Selenium I/O.
    """
    instances: list[RetailerPlugin] = []
    paths = list(_iter_plugin_paths(plugins_dir))
    for index, path in enumerate(paths):
        if index > 0:
            await asyncio.sleep(stagger_seconds)
        inst = await asyncio.to_thread(
            _load_and_instantiate, path, app_config, cvvs
        )
        if inst is not None:
            instances.append(inst)
    return instances


def route_url(url: str, registry: list[RetailerPlugin]) -> RetailerPlugin | None:
    """Return the first plugin whose domain_pattern matches `url`, else None."""
    netloc = _normalize_netloc(url)
    for plugin in registry:
        for pattern in plugin.domain_pattern:
            if _matches(netloc, pattern):
                return plugin
    return None


def verify_coverage(registry: list[RetailerPlugin], items) -> None:
    """Phase B (D-04): raise ValueError naming the first uncovered URL."""
    for item in items:
        link = getattr(item, "link", None) or getattr(item, "url", None)
        if link is None:
            continue
        if route_url(link, registry) is None:
            raise ValueError(
                f"URL {link} has no plugin. Expected a "
                f"plugins/{PLUGIN_PREFIX}<name>.py whose domain_pattern matches "
                f"{_normalize_netloc(link)} (check WARNING log above for any "
                f"plugin import errors)."
            )
