"""Concurrent async orchestrator: TaskGroup of per-plugin poll coroutines.

ASYNC-01: asyncio.TaskGroup runs one long-lived poll coroutine per active plugin.
ASYNC-02: Plugin drivers initialized at least 1.5s apart; each init is logged.
ASYNC-05: Single write-queue drain task serializes all update_item_purchased_sync calls.
ASYNC-03: Single stdin-listener thread sets plugin asyncio.Events via call_soon_threadsafe.

Design constraints:
- run_in_executor ONLY for sqlite3 calls and stdin readline (both genuinely blocking).
- No input() anywhere in this module (ASYNC-03).
- No bare except clauses.
- Functions stay under 30 lines.
"""

import asyncio
import sys
from pathlib import Path

from core.registry import PluginRegistry
from logger import writeLog
from models import (
    get_items_sync,
    update_item_purchased_sync,
    set_item_available_sync,
    clear_item_available_sync,
    get_item_notification_state_sync,
)


_STAGGER_SECS = 1.5
_KNOWN_EVENTS = ("captcha_event", "passkey_event", "otp_event", "test_pause_event")


async def run_plugin(plugin, write_queue: asyncio.Queue, poll_interval: float) -> None:
    """Long-running poll coroutine for one plugin. Cancelled on shutdown."""
    loop = asyncio.get_running_loop()
    while True:
        items = await loop.run_in_executor(None, get_items_sync)
        for name, link, auto_buy, quantity, purchased in items:
            if purchased:
                continue
            if not any(p in (link or "") for p in plugin.domain_patterns):
                continue
            await _check_and_buy(plugin, name, link, auto_buy, write_queue)
        await asyncio.sleep(poll_interval)


async def _check_and_buy(plugin, name, link, auto_buy, write_queue):
    """Check one item and optionally buy it. Logs and continues on any error."""
    try:
        available = await plugin.check_availability(link)
    except Exception as exc:
        writeLog(f"[{plugin.__class__.__name__}] check error: {exc}", "ERROR")
        return
    if not available:
        return
    from utils import play_available_sound
    play_available_sound()
    writeLog(f"{name} is AVAILABLE -- {link}", "SUCCESS")
    if not auto_buy:
        return
    try:
        success = await plugin.auto_buy(link)
        if success:
            from utils import play_buy_sound
            play_buy_sound()
            await write_queue.put(link)
    except Exception as exc:
        writeLog(f"[{plugin.__class__.__name__}] auto_buy error: {exc}", "ERROR")


async def _dispatch_write(loop, item) -> None:
    """Execute a single typed write-queue item against the correct models function.

    Supported tuple tags:
      ("purchased", link)            -> update_item_purchased_sync(link)
      ("set_available", link, ts)    -> set_item_available_sync(link, ts)
      ("clear_available", link)      -> clear_item_available_sync(link)
    """
    if not isinstance(item, tuple):
        # Legacy bare-link support: treat as purchased
        await loop.run_in_executor(None, update_item_purchased_sync, item)
        writeLog(f"Marked purchased: {item}", "INFO")
        return

    tag = item[0]
    if tag == "purchased":
        link = item[1]
        await loop.run_in_executor(None, update_item_purchased_sync, link)
        writeLog(f"Marked purchased: {link}", "INFO")
    elif tag == "set_available":
        link, ts = item[1], item[2]
        await loop.run_in_executor(None, set_item_available_sync, link, ts)
        writeLog(f"Marked available: {link}", "DEBUG")
    elif tag == "clear_available":
        link = item[1]
        await loop.run_in_executor(None, clear_item_available_sync, link)
        writeLog(f"Cleared available: {link}", "DEBUG")
    else:
        writeLog(f"Unknown write-queue tag '{tag}' -- skipped", "WARNING")


async def _write_queue_drain(queue: asyncio.Queue) -> None:
    """Serializes all DB writes. Runs until cancelled."""
    loop = asyncio.get_running_loop()
    while True:
        item = await queue.get()
        try:
            await _dispatch_write(loop, item)
        except Exception as exc:
            writeLog(f"DB write failed for {item!r}: {exc}", "ERROR")
        finally:
            queue.task_done()


async def _staggered_setup(registry, items, stagger_secs: float = _STAGGER_SECS) -> None:
    """Init only matched plugins; 1.5s apart (ASYNC-02). Logs each init."""
    needed = registry.plugins_for_items(items)
    for idx, plugin in enumerate(needed):
        if idx > 0:
            writeLog(
                f"[STAGGER-{idx}] Waiting {stagger_secs}s before next driver init",
                "INFO",
            )
            await asyncio.sleep(stagger_secs)
        writeLog(
            f"[STAGGER-{idx}] Initializing {plugin.__class__.__name__} browser",
            "INFO",
        )
        try:
            await plugin.setup()
            registry._active_plugins.append(plugin)
        except Exception as exc:
            writeLog(
                f"Plugin {plugin.__class__.__name__} setup failed: {exc} -- skipping",
                "WARNING",
            )


def _stdin_listener_thread(plugins: list, loop: asyncio.AbstractEventLoop) -> None:
    """Blocking thread: reads Enter from stdin, signals all known intervention events.

    Security: reads only line terminators via readline(); never stores, echoes, logs,
    or forwards any typed bytes. Credentials are handled by getpass before asyncio.run()
    in a separate synchronous scope (SEC-01/02). Events set exclusively via
    loop.call_soon_threadsafe (thread-safe bridge -- RESEARCH Pitfall 1).
    """
    while True:
        try:
            sys.stdin.readline()
        except (EOFError, OSError):
            break
        for plugin in plugins:
            for attr in _KNOWN_EVENTS:
                event = getattr(plugin, attr, None)
                if event is not None:
                    loop.call_soon_threadsafe(event.set)


def _start_stdin_listener(plugins: list, loop: asyncio.AbstractEventLoop) -> None:
    """Submit the stdin listener to the default executor (one thread, daemon)."""
    loop.run_in_executor(None, _stdin_listener_thread, plugins, loop)


async def async_main(cfg, cvv) -> None:
    """Entry point: stagger setup, run TaskGroup, teardown cleanly."""
    plugins_dir = Path(__file__).parent.parent / "plugins"
    registry = PluginRegistry(cfg, plugins_dir)
    loop = asyncio.get_running_loop()

    items = await loop.run_in_executor(None, get_items_sync)
    await _staggered_setup(registry, items)

    if cvv:
        bb_plugin = registry.route("https://www.bestbuy.com/")
        if bb_plugin:
            bb_plugin._cvv = cvv

    poll_interval = float(getattr(cfg.app, "poll_interval", 30))
    write_queue: asyncio.Queue = asyncio.Queue()

    _start_stdin_listener(registry._active_plugins, loop)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_write_queue_drain(write_queue), name="write-queue-drain")
            for plugin in registry._active_plugins:
                tg.create_task(
                    run_plugin(plugin, write_queue, poll_interval),
                    name=f"poll-{plugin.__class__.__name__}",
                )
    except* KeyboardInterrupt:
        pass
    finally:
        try:
            await asyncio.wait_for(write_queue.join(), timeout=10)
        except asyncio.TimeoutError:
            writeLog("Write queue flush timed out on shutdown", "WARNING")
        await registry.teardown_all()
