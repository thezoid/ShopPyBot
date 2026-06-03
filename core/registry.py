"""Plugin registry: importlib discovery, hostname routing, lazy lifecycle.

CORE-03: discovers shopbot_plugin_*.py via importlib; warns + ignores non-matching
         .py files; isolates import failures (log + skip, never crash).
CORE-04: routes item URLs to plugins by urlparse(url).hostname substring match.
D-09:    eager discovery (all plugins), lazy browser launch (only matched plugins).
D-10:    domain_patterns substring match against urlparse(url).hostname.
"""

import importlib.util
import inspect
from pathlib import Path
from urllib.parse import urlparse

from core.plugin_base import RetailerPlugin
from logger import writeLog


def _discover_plugins(plugins_dir: Path) -> list[type[RetailerPlugin]]:
    """Scan plugins_dir for shopbot_plugin_*.py files and return plugin classes.

    Non-.py files are skipped silently.
    .py files not starting with "shopbot_plugin_" are logged as WARNING and skipped.
    Files that raise on import are logged as WARNING and skipped (CORE-03 criterion 2).
    """
    found: list[type[RetailerPlugin]] = []

    if not plugins_dir.exists():
        writeLog(f"Plugins directory not found: {plugins_dir}", "WARNING")
        return found

    for path in plugins_dir.iterdir():
        if path.suffix != ".py":
            continue

        if not path.name.startswith("shopbot_plugin_"):
            writeLog(
                f"plugins/{path.name} does not match shopbot_plugin_*.py -- ignoring",
                "WARNING",
            )
            continue

        try:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            module = importlib.util.module_from_spec(spec)
            # CORE-03 criterion 2: arbitrary plugin code can raise anything on import;
            # requirement is log+skip, not crash -- only Exception is caught, never bare.
            spec.loader.exec_module(module)
        except Exception as exc:
            writeLog(f"Failed to import {path.name}: {exc} -- skipping", "WARNING")
            continue

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, RetailerPlugin) and obj is not RetailerPlugin:
                found.append(obj)

    return found


class PluginRegistry:
    """Discovers, routes, and manages the lifecycle of retailer plugins.

    Construction is synchronous and cheap (reads domain_patterns only).
    Browser launch is deferred to setup_for_items (D-09 lazy launch).
    """

    def __init__(self, config, plugins_dir: Path) -> None:
        plugin_classes = _discover_plugins(plugins_dir)
        # Eagerly construct all plugin instances: cheap objects, no browser yet.
        self._all_plugins: list[RetailerPlugin] = [cls(config) for cls in plugin_classes]
        self._active_plugins: list[RetailerPlugin] = []

    def route(self, url: str) -> RetailerPlugin | None:
        """Return the active plugin whose domain_patterns matches url's hostname.

        Uses urlparse(url).hostname so query/path strings cannot spoof a host
        match (D-10). Returns None if no active plugin matches.
        """
        host = urlparse(url).hostname or ""
        for plugin in self._active_plugins:
            if any(p in host for p in plugin.domain_patterns):
                return plugin
        return None

    def _route_all(self, url: str) -> RetailerPlugin | None:
        """Like route() but searches _all_plugins (used during setup before active list exists)."""
        host = urlparse(url).hostname or ""
        for plugin in self._all_plugins:
            if any(p in host for p in plugin.domain_patterns):
                return plugin
        return None

    async def setup_for_items(self, items) -> None:
        """Await setup() only for plugins that have at least one matching item (D-09).

        items: iterable of DB rows -- (name, link, auto_buy, quantity, purchased).
        On setup() failure, logs WARNING and skips that plugin (does not abort).
        """
        needed: set[RetailerPlugin] = set()
        for item in items:
            plugin = self._route_all(item[1])  # item[1] is the link
            if plugin:
                needed.add(plugin)

        for plugin in needed:
            try:
                await plugin.setup()
                self._active_plugins.append(plugin)
            except Exception as exc:
                writeLog(f"Plugin setup failed: {exc} -- skipping", "WARNING")

    async def teardown_all(self) -> None:
        """Await teardown() on every active plugin.

        Logs WARNING on individual teardown errors; never raises.
        """
        for plugin in self._active_plugins:
            try:
                await plugin.teardown()
            except Exception as exc:
                writeLog(f"Plugin teardown error: {exc}", "WARNING")
