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

    def __init__(self, config, plugins_dir: Path, proxy_pool=None, captcha_solver=None) -> None:
        plugin_classes = _discover_plugins(plugins_dir)
        # Eagerly construct all plugin instances: cheap objects, no browser yet.
        self._all_plugins: list[RetailerPlugin] = [cls(config) for cls in plugin_classes]
        self._active_plugins: list[RetailerPlugin] = []
        self._proxy_pool = proxy_pool
        self._captcha_solver = captcha_solver

    def assign_proxy(self, plugin) -> None:
        """Set proxy state on a plugin instance before setup().

        When a pool is available, advances to the next non-retired entry and
        sets plugin._proxy, plugin._pool, and plugin._proxy_required=True.
        When the pool is exhausted (all retired), _proxy_required=True but
        _proxy=None so the plugin's setup() can fail loudly (Pitfall 2).
        When no pool is configured, sets _proxy_required=False and _proxy=None.
        Credentials are NEVER logged here.
        """
        if self._proxy_pool is None:
            plugin._proxy_required = False
            plugin._proxy = None
            return
        plugin._proxy_required = True
        plugin._pool = self._proxy_pool
        plugin._proxy = self._proxy_pool.advance()

    def assign_solver(self, plugin) -> None:
        """Set captcha solver on a plugin instance before setup().

        When a solver is available, sets plugin._captcha_solver = self._captcha_solver.
        When no solver is configured (disabled or no key), sets plugin._captcha_solver = None.
        The API key is NEVER read or logged here.
        """
        plugin._captcha_solver = self._captcha_solver

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

    def plugins_for_items(self, items) -> list[RetailerPlugin]:
        """Return the subset of _all_plugins that match at least one item link.

        Deduplicates by plugin identity (id()), preserving first-seen order.
        Does NOT call setup() -- caller (orchestrator) staggers setup itself.
        items: iterable of DB rows -- (name, link, auto_buy, quantity, purchased).
        """
        needed: list[RetailerPlugin] = []
        seen: set[int] = set()
        for item in items:
            plugin = self._route_all(item[1])  # item[1] is the link
            if plugin and id(plugin) not in seen:
                needed.append(plugin)
                seen.add(id(plugin))
        return needed

    async def setup_for_items(self, items) -> None:
        """Await setup() only for plugins that have at least one matching item (D-09).

        items: iterable of DB rows -- (name, link, auto_buy, quantity, purchased).
        On setup() failure, logs WARNING and skips that plugin (does not abort).

        WR-03: proxy assignment is the CALLER'S responsibility (orchestrator calls
        assign_proxy before setup_for_items or before individual plugin.setup() calls).
        This method does NOT call assign_proxy to prevent double-advancing the pool.
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
                # Startup restore mirrors relaunch() sequence (RESEARCH Pitfall 7 / Open Question 1).
                # Unlike relaunch(), startup keeps login LAZY (each plugin's auto_buy calls
                # login() internally -- Amazon line 387, BestBuy line 347). Calling login()
                # here unconditionally would double-login or block on MFA at startup.
                session_restored = await plugin.restore_session()
                if session_restored:
                    writeLog(
                        f"[{plugin.__class__.__name__}] startup: session restored; skipping login",
                        "INFO",
                    )
                else:
                    writeLog(
                        f"[{plugin.__class__.__name__}] startup: no session restored; login on demand",
                        "INFO",
                    )
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
