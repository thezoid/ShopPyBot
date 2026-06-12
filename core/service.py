"""BotService: single API seam wrapping registry, orchestrator, config, and models.

Design: start/stop use a background thread that owns its own asyncio event loop.
This makes start() non-blocking from any sync caller (web UI, CLI, shim) and
allows stop() to cancel the running task without requiring a shared event loop.

CVV and other secrets arrive as method parameters; this module never prompts
for secrets or interactive input -- secrets are collected by the front-end
and passed in (T-07-04, ASYNC-03).
"""

import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Optional

from core.config_schema import AppConfig
from core.credentials import init_store
from core.health import HealthRegistry
from core.orchestrator import async_main
from core.stealth import ProxyPool
from logger import writeLog
from models import add_items_sync, get_items_sync, remove_item_sync, get_price_history_sync

_log = logging.getLogger(__name__)


class BotService:
    """Stable API surface for all bot operations.

    Background-run mechanism: start() launches a daemon thread that creates
    its own asyncio event loop and runs async_main(cfg, cvv) inside it.
    stop() cancels the running task from outside via thread-safe call.
    """

    def __init__(self, cfg: Optional[AppConfig] = None) -> None:
        self._cfg: AppConfig = cfg if cfg is not None else AppConfig()
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._task: Optional[asyncio.Task] = None
        self._start_time: Optional[float] = None
        # Single HealthRegistry created here so get_status() is safe before start() (REL-07).
        self._health_registry: HealthRegistry = HealthRegistry()
        # Initialize the credential store before the daemon thread launches
        # so the store is available without a race (RESEARCH thread-safety note).
        init_store(self._cfg)
        # ANTI-04: emit startup log when proxy rotation is enabled (T-13-09 mitigation).
        # Log only the integer pool size -- never log URLs or credentials.
        if self._cfg.proxy.enabled:
            n = len(self._cfg.proxy.urls)
            writeLog(f"Proxy rotation: enabled, pool_size={n}", "INFO")
        # ANTI-06: emit startup log when CAPTCHA solving is enabled (T-14-log mitigation).
        # Log only the integer cap and float threshold -- NEVER the API key (key is
        # read later in async_main via get_store; it is never present here).
        if getattr(self._cfg.captcha, "enabled", False):
            _log.info(
                "CAPTCHA solving: enabled, max_solves_per_run=%d, low_balance_threshold=%.2f",
                self._cfg.captcha.max_solves_per_run,
                self._cfg.captcha.low_balance_threshold,
            )

    # ------------------------------------------------------------------
    # Read-only accessors (callable without start)
    # ------------------------------------------------------------------

    def get_config(self) -> AppConfig:
        """Return the AppConfig this service was constructed with."""
        return self._cfg

    def get_status(self) -> dict:
        """Return structured health surface. Safe to call before start() (REL-07).

        Cheap and non-blocking: all reads are in-memory only.
        """
        uptime = 0.0
        if self._start_time is not None and self._running:
            uptime = time.monotonic() - self._start_time
        return {
            "running": self._running,
            "uptime_secs": uptime,
            "plugins": self._health_registry.get_snapshot(),
        }

    def list_items(self) -> list:
        """Return all DB rows as plain tuples (no bot start required)."""
        return get_items_sync()

    def get_price_history(self, name: str, limit: int = 10) -> list[tuple[int, str, str]]:
        """Return last N (price_cents, currency, scraped_at) rows for the named item.

        Resolves name to link via exact case-sensitive match. Returns [] if not found.
        No bot start required (read-only, no network). MOD-02: CLI calls only BotService.
        """
        rows = get_items_sync()
        match = next((r for r in rows if r[0] == name), None)
        if match is None:
            return []
        link = match[1]
        return get_price_history_sync(link, limit)

    def list_plugins(self) -> list[dict]:
        """Return one dict per discovered plugin from _all_plugins.

        Reads registry._all_plugins (eager, no browser, no network).
        Never reads _active_plugins (empty until setup_for_items runs).
        Returns dicts with keys: name, domain_patterns, difficulty,
        requires_proxy, requires_captcha.
        """
        from core.registry import PluginRegistry

        plugins_dir = Path(__file__).parent.parent / "plugins"
        registry = PluginRegistry(self._cfg, plugins_dir)
        return [
            {
                "name": type(plugin).__name__,
                "domain_patterns": (
                    [plugin.domain_patterns]
                    if isinstance(plugin.domain_patterns, str)
                    else list(getattr(plugin, "domain_patterns", []))
                ),
                "difficulty": getattr(plugin, "difficulty", "medium"),
                "requires_proxy": getattr(plugin, "requires_proxy", False),
                "requires_captcha": getattr(plugin, "requires_captcha", False),
            }
            for plugin in registry._all_plugins
        ]

    # ------------------------------------------------------------------
    # Item CRUD -- delegate to models single source of truth
    # ------------------------------------------------------------------

    def add_item(self, name: str, link: str, auto_buy: bool, quantity: int) -> None:
        """Insert one item into the DB (purchased defaults to False)."""
        add_items_sync([(name, link, auto_buy, quantity, False)])

    def remove_item(self, link: str) -> None:
        """Delete the item with the given link from the DB."""
        remove_item_sync(link)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, cvv: Optional[str] = None) -> None:
        """Launch async_main in a background daemon thread; returns immediately.

        Calling start() when already running is a no-op. _running is set
        synchronously before the thread starts so a concurrent start() call
        cannot launch a second thread (WR-03).
        """
        if self._running or (self._thread is not None and self._thread.is_alive()):
            return

        self._running = True
        self._start_time = time.monotonic()
        ready = threading.Event()

        def _run_loop() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop

            async def _main():
                self._task = asyncio.current_task()
                ready.set()
                try:
                    await async_main(self._cfg, cvv, health_registry=self._health_registry)
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    writeLog(
                        f"Bot loop terminated abnormally: {exc.__class__.__name__}",
                        "ERROR",
                    )
                finally:
                    self._running = False
                    self._start_time = None
                    self._task = None

            try:
                loop.run_until_complete(_main())
            finally:
                loop.close()
                self._loop = None
                self._running = False

        self._thread = threading.Thread(target=_run_loop, daemon=True, name="BotService-loop")
        self._thread.start()
        started = ready.wait(timeout=5.0)
        if not started:
            writeLog("BotService loop did not signal ready within 5s", "WARNING")

    def stop(self) -> None:
        """Signal the background run to shut down and wait for the thread to exit.

        Routes through async_main's existing cancellation path so teardown_all runs.
        Calling stop() when not running is a no-op.
        """
        loop = self._loop   # capture before any race with daemon thread
        task = self._task   # capture before any race with daemon thread
        if not self._running or loop is None:
            return

        if task is not None:
            loop.call_soon_threadsafe(task.cancel)

        if self._thread is not None:
            self._thread.join(timeout=15.0)

    def run(self, cvv: Optional[str] = None) -> None:
        """Blocking convenience: runs async_main directly in the calling thread.

        Equivalent to asyncio.run(async_main(cfg, cvv)). Used by main.py shim
        and CLI (Phase 9) where blocking is acceptable.
        """
        self._start_time = time.monotonic()
        try:
            asyncio.run(async_main(self._cfg, cvv, health_registry=self._health_registry))
        finally:
            self._start_time = None


# ---------------------------------------------------------------------------
# Module-level entry point (console_scripts target: core.service:main)
# ---------------------------------------------------------------------------


def main(argv=None) -> None:
    """Console entry point for the shoppybot command.

    Delegates parsing to core.cli.build_parser() and dispatches via
    set_defaults(func=...) on each subcommand. Uses parse_known_args(argv)
    to avoid sys.argv contamination in tests (RESEARCH Pitfall 7).

    Dispatch rules:
    - top-level --migrate with no subcommand: back-compat alias for setup --migrate
    - bare invocation (func is None): default to handle_run
    - all other subcommands: sys.exit(args.func(args, BotService()) or 0)
    """
    import sys as _sys
    from core.paths import migrate_legacy_paths
    from core.cli import build_parser
    from core.cli.run import handle_run
    from core.cli.setup import handle_setup
    from models import initialize_db

    migrate_legacy_paths()  # idempotent; must run before any DB/store/config access
    initialize_db()  # idempotent (CREATE TABLE IF NOT EXISTS); the console entry
    # point must create the items table itself so shoppybot run/items work on a
    # fresh install without ever running the main.py shim (MOD-01/MOD-03/CLI-01/CLI-03)

    parser = build_parser()
    args, _ = parser.parse_known_args(argv)

    # Back-compat: top-level --migrate with no subcommand -> setup --migrate (T-09-03)
    if getattr(args, "migrate", False) and getattr(args, "command", None) is None:
        _sys.exit(handle_setup(args, BotService()) or 0)

    # Bare shoppybot = run (RESEARCH Pitfall 1)
    if getattr(args, "func", None) is None:
        _sys.exit(handle_run(args, BotService()) or 0)

    _sys.exit(args.func(args, BotService()) or 0)
