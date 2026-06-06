"""BotService: single API seam wrapping registry, orchestrator, config, and models.

Design: start/stop use a background thread that owns its own asyncio event loop.
This makes start() non-blocking from any sync caller (web UI, CLI, shim) and
allows stop() to cancel the running task without requiring a shared event loop.

CVV and other secrets arrive as method parameters; this module never prompts
for secrets or interactive input -- secrets are collected by the front-end
and passed in (T-07-04, ASYNC-03).
"""

import asyncio
import threading
from pathlib import Path
from typing import Optional

from core.config_schema import AppConfig
from core.credentials import init_store
from core.orchestrator import async_main
from logger import writeLog
from models import add_items_sync, get_items_sync, remove_item_sync


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
        # Initialize the credential store before the daemon thread launches
        # so the store is available without a race (RESEARCH thread-safety note).
        init_store(self._cfg)

    # ------------------------------------------------------------------
    # Read-only accessors (callable without start)
    # ------------------------------------------------------------------

    def get_config(self) -> AppConfig:
        """Return the AppConfig this service was constructed with."""
        return self._cfg

    def get_status(self) -> dict:
        """Return plain running-state dict. Safe to call before start()."""
        return {"running": self._running}

    def list_items(self) -> list:
        """Return all DB rows as plain tuples (no bot start required)."""
        return get_items_sync()

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
        ready = threading.Event()

        def _run_loop() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop

            async def _main():
                self._task = asyncio.current_task()
                ready.set()
                try:
                    await async_main(self._cfg, cvv)
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    writeLog(
                        f"Bot loop terminated abnormally: {exc.__class__.__name__}",
                        "ERROR",
                    )
                finally:
                    self._running = False
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
        if not self._running or self._loop is None:
            return

        loop = self._loop
        task = self._task

        if task is not None and loop is not None:
            loop.call_soon_threadsafe(task.cancel)

        if self._thread is not None:
            self._thread.join(timeout=15.0)

    def run(self, cvv: Optional[str] = None) -> None:
        """Blocking convenience: runs async_main directly in the calling thread.

        Equivalent to asyncio.run(async_main(cfg, cvv)). Used by main.py shim
        and CLI (Phase 9) where blocking is acceptable.
        """
        asyncio.run(async_main(self._cfg, cvv))


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
