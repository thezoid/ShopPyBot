"""ShopPyBot entrypoint (Phase 5: notification fan-out + async orchestrator).

Concurrency model:
- async def main() drives an asyncio.TaskGroup with one task per plugin plus
  one purchase_writer task plus one notification_writer task.
- Blocking Selenium calls bridged via asyncio.to_thread.
- Shared ThreadPoolExecutor sized max(4, N*2) installed via
  loop.set_default_executor BEFORE TaskGroup opens (Pitfall 4-2).
- Plugin task crashes are isolated (try/except Exception inside poll_plugin).
- purchase_writer and notification_writer crashes are FATAL (Pitfall 4-10):
  they tear down the TaskGroup.
- notification_writer fans out per-event across all notifiers via
  asyncio.gather(return_exceptions=True) so per-channel failures stay isolated
  (NOTIF-01). Detected events run through should_notify dedup gate; purchased
  events bypass dedup (RESEARCH Q8).
- Shutdown: asyncio.shield wraps every plugin.shutdown() AND every
  notifier.shutdown() in a single gather (RESEARCH Q10.5).
- Windows: SelectorEventLoopPolicy installed (Pitfall 4-6).
"""
import sys

if sys.version_info < (3, 11):
    sys.exit(f"ShopPyBot requires Python 3.11+. Detected: {sys.version}")

import asyncio
import os
import signal
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from webdriver_manager.chrome import ChromeDriverManager

from config_schema import AppConfig
from credentials import collect_cvvs
from logger import configure as configure_logger, writeLog
from models import (
    add_items,
    get_items,
    initialize_db,
    mark_notified,
    should_notify,
    update_item_purchased,
)
from notifier_base import NotificationEvent, Notifier
from notifier_registry import discover_notifiers
from plugin_registry import discover_async, route_url, verify_coverage


def get_chromedriver_path(driver_path: str) -> str:
    writeLog("Entering get_chromedriver_path", "DEBUG")
    if not os.path.exists(driver_path):
        writeLog(
            f"Chromedriver not found at {driver_path}. Downloading.",
            "WARNING",
        )
        driver_path = ChromeDriverManager().install()
        if not os.path.exists(driver_path):
            writeLog("Failed to download Chromedriver. Exiting.", "ERROR")
            sys.exit(1)
    writeLog(f"Chromedriver path: {driver_path}", "DEBUG")
    return driver_path


def make_tiny(url: str) -> str:
    response = requests.get(f"http://tinyurl.com/api-create.php?url={url}")
    return response.text


async def purchase_writer(queue: asyncio.Queue) -> None:
    """Single consumer for serialized SQLite writes (D-03).

    Critical infrastructure: a crash here is FATAL and propagates to TaskGroup
    (Pitfall 4-10). Only the inner update call is try/except/finally to
    guarantee queue.task_done() runs even on write failure (Pitfall 4-5).
    """
    while True:
        url, *_ = await queue.get()
        try:
            await asyncio.to_thread(update_item_purchased, url)
        except Exception as e:
            writeLog(f"purchase_writer: write failed for {url}: {e}", "ERROR")
        finally:
            queue.task_done()


async def notification_writer(
    queue: asyncio.Queue,
    notifiers: list[Notifier],
    restock_window_seconds: int,
) -> None:
    """Single consumer for fan-out notification dispatch (NOTIF-01).

    Mirrors purchase_writer. A crash here is FATAL by design (Phase 4 Pitfall
    4-10). Per-notifier exceptions isolated via gather(return_exceptions=True).
    Dedup check + mark_notified happen INSIDE this writer for the detected
    action (single-writer eliminates race). Purchased events bypass dedup.
    """
    while True:
        event = await queue.get()
        try:
            if event.action == "detected":
                allowed = await asyncio.to_thread(
                    should_notify, event.url, restock_window_seconds,
                )
                if not allowed:
                    continue
            active = [n for n in notifiers if n.enabled]
            results = await asyncio.gather(
                *(n.send(event) for n in active),
                return_exceptions=True,
            )
            for n, r in zip(active, results):
                if isinstance(r, Exception):
                    writeLog(
                        f"notifier {n.name} failed on {event.url}: {r}",
                        "ERROR",
                    )
            if event.action == "detected":
                try:
                    await asyncio.to_thread(mark_notified, event.url)
                except Exception as e:
                    writeLog(
                        f"mark_notified failed for {event.url}: {e}",
                        "ERROR",
                    )
        finally:
            queue.task_done()


async def _attempt_purchase(
    plugin, link, name, app_config, purchase_queue, notification_queue,
) -> None:
    try:
        await asyncio.to_thread(plugin.auto_buy, link, app_config)
        await purchase_queue.put((link,))
        await notification_queue.put(NotificationEvent(
            item_name=name,
            url=link,
            platform=plugin.name,
            timestamp=datetime.now(timezone.utc),
            action="purchased",
        ))
    except Exception as e:
        writeLog(
            f"{plugin.name}: auto_buy raised on {link}: {e}",
            "ERROR",
        )


async def _poll_once(
    plugin, app_config, purchase_queue, notification_queue, open_browser,
) -> None:
    """One iteration: fetch items, check, enqueue notification, auto-buy if requested."""
    items = await asyncio.to_thread(get_items)
    for name, link, autoBuy, _qty, purchased in items:
        if purchased:
            continue
        matched = route_url(link, [plugin])
        if matched is None:
            continue
        try:
            available = await asyncio.to_thread(plugin.check_availability, link)
        except Exception as e:
            writeLog(
                f"{plugin.name}: check_availability raised on {link}: {e}",
                "ERROR",
            )
            continue
        if not available:
            continue
        writeLog(f"{name} is available: {make_tiny(link)}", "SUCCESS")
        await notification_queue.put(NotificationEvent(
            item_name=name,
            url=link,
            platform=plugin.name,
            timestamp=datetime.now(timezone.utc),
            action="detected",
        ))
        if autoBuy:
            await _attempt_purchase(
                plugin, link, name, app_config, purchase_queue, notification_queue,
            )
        elif open_browser:
            webbrowser.open(link)


async def poll_plugin(
    plugin,
    app_config,
    purchase_queue: asyncio.Queue,
    notification_queue: asyncio.Queue,
    stop_event: asyncio.Event,
) -> None:
    """Run one plugin's polling loop. Crash-isolated per Pitfall 4-1."""
    open_browser = getattr(app_config, "open_browser", False)
    delay = app_config.app.delay
    while not stop_event.is_set():
        try:
            await _poll_once(
                plugin, app_config, purchase_queue, notification_queue, open_browser,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            writeLog(f"{plugin.name}: unexpected error: {e}", "ERROR")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass


def _seed_items(app_config) -> None:
    initialize_db()
    add_items([
        (it.name, it.link, it.auto_buy, it.quantity, False)
        for it in app_config.available.items
    ])


def _install_signal_handler(stop_event: asyncio.Event) -> None:
    """Pitfall 4-6: explicit SIGINT handler so Ctrl-C sets stop_event cleanly."""
    loop = asyncio.get_running_loop()

    def _handler(_signum, _frame):
        writeLog("SIGINT received; signaling stop", "INFO")
        try:
            loop.call_soon_threadsafe(stop_event.set)
        except RuntimeError:
            stop_event.set()
    signal.signal(signal.SIGINT, _handler)


async def _startup_logins(registry, app_config) -> None:
    """Sequential per Phase 2 D-03 + Pitfall 4-11 (stdin contention)."""
    for plugin in registry:
        if plugin.login_at_startup:
            await asyncio.to_thread(plugin.login, app_config)


async def _shutdown_all(registry, notifiers) -> None:
    """Pitfall 4-4 + D-04 + RESEARCH Q10.5: shield every shutdown from Ctrl-C cancellation."""
    writeLog("Shutting down plugins and notifiers", "INFO")
    await asyncio.gather(
        *(asyncio.shield(p.shutdown()) for p in registry),
        *(asyncio.shield(n.shutdown()) for n in notifiers),
        return_exceptions=True,
    )


async def main() -> None:
    try:
        app_config = AppConfig()
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)

    configure_logger(app_config.debug.logging_level)
    writeLog("Starting ShopPyBot (async)", "INFO")

    cvvs = await asyncio.to_thread(collect_cvvs, app_config)
    app_config.selenium.driver_path = await asyncio.to_thread(
        get_chromedriver_path, app_config.selenium.driver_path,
    )

    registry = await discover_async(
        Path("plugins"), app_config=app_config, cvvs=cvvs,
    )
    verify_coverage(registry, app_config.available.items)
    notifiers = await discover_notifiers(
        Path("notifiers"), app_config=app_config,
    )

    loop = asyncio.get_running_loop()
    max_workers = max(4, len(registry) * 2)
    executor = ThreadPoolExecutor(
        max_workers=max_workers, thread_name_prefix="shopbot",
    )
    loop.set_default_executor(executor)

    await _startup_logins(registry, app_config)
    _seed_items(app_config)

    purchase_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    notification_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    stop_event = asyncio.Event()
    _install_signal_handler(stop_event)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(purchase_writer(purchase_queue))
            tg.create_task(notification_writer(
                notification_queue,
                notifiers,
                app_config.notifications.restock_window_seconds,
            ))
            for plugin in registry:
                tg.create_task(
                    poll_plugin(
                        plugin, app_config, purchase_queue, notification_queue, stop_event,
                    )
                )
    except* KeyboardInterrupt:
        pass
    except* asyncio.CancelledError:
        pass
    finally:
        await _shutdown_all(registry, notifiers)
        executor.shutdown(wait=True, cancel_futures=False)
        writeLog("ShopPyBot stopped cleanly", "INFO")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
