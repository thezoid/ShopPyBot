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
import random
import signal
import sqlite3
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from core.captcha import CaptchaSolver
from core.credentials import get_store
from core.registry import PluginRegistry
from core.retry import RetryPolicy, compute_delay, with_retry
from core.stealth import ProxyPool
from logger import writeLog
from models import (
    get_items_sync,
    update_item_purchased_sync,
    update_item_confirmed_sync,
    set_item_available_sync,
    clear_item_available_sync,
    get_item_notification_state_sync,
    get_item_order_state_sync,
    increment_checkout_attempts_sync,
    append_price_history_sync,
    get_last_price_sync,
    get_item_price_config_sync,
    get_price_alert_state_sync,
    set_price_alert_armed_sync,
    clear_price_alert_armed_sync,
)


_STAGGER_SECS = 1.5
_KNOWN_EVENTS = ("captcha_event", "passkey_event", "otp_event", "test_pause_event")
_FAILURE_WINDOW_SECS = 600  # rolling failure-budget window (REL-02)


def _is_browser_dead_exc(exc: Exception) -> bool:
    """Return True if exc indicates a dead/disconnected Chrome process.

    Matches exactly the three exception surfaces confirmed from nodriver 0.50.3
    connection.py -- no more, no less:
    - RuntimeError("WebSocket is not connected") -- socket is None (L424)
    - ConnectionError("Connection closed") / ("Connection closing") -- _fail_pending_futures
    - websockets.exceptions.ConnectionClosed -- ws.send() failure

    ConnectionError is an OSError subclass and is intentionally specific.
    Bare OSError is NOT matched: disk/fs errors (PermissionError, FileNotFoundError, etc.)
    must NOT trigger a browser relaunch (CR-02).
    """
    if isinstance(exc, ConnectionError):
        return True
    if isinstance(exc, RuntimeError) and "WebSocket" in str(exc):
        return True
    try:
        import websockets.exceptions as _ws_exc
        if isinstance(exc, _ws_exc.ConnectionClosed):
            return True
    except ImportError:
        pass
    return False


async def _park_plugin(plugin, n_budget: int, dispatcher) -> None:
    """Log and notify that a plugin has been parked after exceeding its failure budget."""
    writeLog(
        f"[{plugin.__class__.__name__}] failure budget exceeded ({n_budget} failures) -- parked",
        "ERROR",
    )
    if dispatcher is not None:
        await dispatcher.notify(_build_event("", "", plugin.__class__.__name__, "plugin_parked"))


async def supervise(plugin, write_queue, poll_interval, dispatcher, cfg, registry=None) -> None:
    """Wrap run_plugin in a restart loop; absorb all Exceptions before TaskGroup boundary.

    CancelledError is re-raised so clean shutdown propagates (CancelledError inherits
    BaseException, not Exception -- RESEARCH Pitfall 1 verified on Python 3.13).

    Failure budget: alert_on_errors crashes within _FAILURE_WINDOW_SECS=600s parks the
    plugin and dispatches a "plugin_parked" notification (REL-02).

    Browser-death path: assigns a new proxy via registry.assign_proxy(plugin) then calls
    plugin.relaunch() before re-entering run_plugin (REL-03).

    Backoff uses compute_delay from core/retry.py (REL-08 single source).
    """
    checkout_cfg = getattr(cfg, "checkout", None)
    n_budget = getattr(checkout_cfg, "alert_on_errors", 3)
    policy = RetryPolicy(
        max_attempts=999,
        backoff_base=getattr(checkout_cfg, "backoff_base", 2.0),
        backoff_jitter=getattr(checkout_cfg, "backoff_jitter", 0.5),
    )
    failure_times: deque = deque()
    attempt = 0

    while True:
        try:
            await run_plugin(plugin, write_queue, poll_interval, dispatcher=dispatcher, cfg=cfg)
            attempt = 0  # healthy run completed; reset backoff so future failures start fresh (WR-02)
        except asyncio.CancelledError:
            raise  # MUST propagate -- clean shutdown via TaskGroup cancel
        except Exception as exc:
            now = time.monotonic()
            failure_times.append(now)
            # Evict failures outside the rolling window
            while failure_times and (now - failure_times[0]) > _FAILURE_WINDOW_SECS:
                failure_times.popleft()
            writeLog(
                f"[{plugin.__class__.__name__}] crashed: {exc.__class__.__name__} "
                f"({len(failure_times)} in window)",
                "ERROR",
            )
            if len(failure_times) >= n_budget:
                await _park_plugin(plugin, n_budget, dispatcher)
                return  # clean exit; TaskGroup task ends normally

            if _is_browser_dead_exc(exc):
                if registry is not None:
                    registry.assign_proxy(plugin)
                try:
                    await plugin.relaunch()
                except Exception as rel_exc:
                    writeLog(
                        f"[{plugin.__class__.__name__}] relaunch error: {rel_exc.__class__.__name__}",
                        "WARNING",
                    )

            delay = compute_delay(attempt, policy)
            writeLog(
                f"[{plugin.__class__.__name__}] restart in {delay:.1f}s (attempt {attempt + 1})",
                "WARNING",
            )
            await asyncio.sleep(delay)
            attempt += 1


def _build_event(name: str, link: str, plugin_name: str, action: str):
    """Construct a NotificationEvent for the given action."""
    from notifications.base import NotificationEvent
    return NotificationEvent(
        item_name=name,
        item_url=link,
        platform=plugin_name,
        timestamp=datetime.now(timezone.utc),
        action=action,
    )


def _cents_to_display(cents: int | None) -> str:
    """Format integer cents as $X.XX; delegates to shared helper (K-01)."""
    from notifications.base import cents_to_display
    return cents_to_display(cents)


def _pct_from_target(price_cents: int, target_cents: int) -> float:
    """Return percentage price is below target (0.0 when price >= target).

    Rounded to 1 decimal for display only (C-02). The trigger decision in
    _check_price_triggers uses integer-cent arithmetic and never calls this.
    """
    if target_cents <= 0:
        return 0.0
    return max(0.0, round((target_cents - price_cents) / target_cents * 100, 1))


def _pct_drop_from_last(current_cents: int, last_cents: int) -> float:
    """Return percentage drop from last_cents to current_cents (0.0 when price rose)."""
    if last_cents <= 0:
        return 0.0
    return max(0.0, round((last_cents - current_cents) / last_cents * 100, 1))


def _check_price_triggers(
    price_cents: int,
    target_price: int | None,
    price_drop_pct: float | None,
    prev_price: int | None,
) -> bool:
    """Return True if absolute target OR percentage-drop trigger fires.

    Guards each trigger with is-not-None check (Pitfall 4).
    The pct-drop check uses integer-cent arithmetic to avoid false positives
    from pre-rounding (C-01): a 9.96% drop must NOT fire a 10.0% threshold.
    """
    if target_price is not None and price_cents <= target_price:
        return True
    if price_drop_pct is not None and prev_price is not None and prev_price > 0:
        # Compare in integer-cent space: (drop * 100) >= threshold * prev_price
        # avoids floating-point rounding that could fire at 9.96% on a 10% threshold.
        if (prev_price - price_cents) * 100 >= price_drop_pct * prev_price:
            return True
    return False


def _build_price_drop_event(name: str, link: str, plugin_name: str, price_cents: int, target_price: int | None):
    """Build a NotificationEvent with action=price_drop and PRICE-04 payload."""
    from notifications.base import NotificationEvent
    pct = _pct_from_target(price_cents, target_price) if target_price is not None else None
    return NotificationEvent(
        item_name=name,
        item_url=link,
        platform=plugin_name,
        timestamp=datetime.now(timezone.utc),
        action="price_drop",
        price_cents=price_cents,
        target_price_cents=target_price,
        pct_from_target=pct,
    )


async def _evaluate_price_triggers(plugin, name, link, price_cents, prev_price, dispatcher, loop) -> None:
    """Evaluate absolute + pct triggers; dispatch a single price_drop alert per dedup window."""
    item_row = await loop.run_in_executor(None, get_item_price_config_sync, link)
    if item_row is None:
        return
    target_price, price_drop_pct = item_row
    if target_price is None and price_drop_pct is None:
        return

    triggered = _check_price_triggers(price_cents, target_price, price_drop_pct, prev_price)
    if not triggered:
        await loop.run_in_executor(None, clear_price_alert_armed_sync, link)
        return

    armed, _ = await loop.run_in_executor(None, get_price_alert_state_sync, link)
    if armed:
        return

    if dispatcher is not None:
        event = _build_price_drop_event(name, link, plugin.__class__.__name__, price_cents, target_price)
        await dispatcher.notify(event)

    now_iso = datetime.now(timezone.utc).isoformat()
    await loop.run_in_executor(None, set_price_alert_armed_sync, link, now_iso)


def _get_plugin_sleep(plugin, poll_interval: float) -> float:
    """Return per-platform jitter sleep or shared poll_interval as fallback.

    Reads plugin.platform_key to resolve config.platforms.<key>. Returns
    random.uniform(min_delay, max_delay) when both are defined; otherwise
    returns poll_interval. Any attribute lookup failure falls back safely.
    """
    try:
        platform_key = getattr(plugin, "platform_key", None)
        if not platform_key:
            return poll_interval
        platform_cfg = getattr(plugin.config.platforms, platform_key, None)
        if platform_cfg is None:
            return poll_interval
        min_delay = getattr(platform_cfg, "min_delay", None)
        max_delay = getattr(platform_cfg, "max_delay", None)
        if min_delay is None or max_delay is None:
            return poll_interval
        return random.uniform(min_delay, max_delay)
    except Exception:
        return poll_interval


async def run_plugin(plugin, write_queue: asyncio.Queue, poll_interval: float, dispatcher=None, cfg=None) -> None:
    """Long-running poll coroutine for one plugin. Cancelled on shutdown."""
    loop = asyncio.get_running_loop()
    item_timeout = getattr(getattr(cfg, "checkout", None), "item_timeout_secs", 120)
    while True:
        try:
            items = await loop.run_in_executor(None, get_items_sync)
        except sqlite3.OperationalError as exc:
            writeLog(
                f"[{plugin.__class__.__name__}] items read error: {exc.__class__.__name__} -- skipping poll cycle",
                "WARNING",
            )
            await asyncio.sleep(_get_plugin_sleep(plugin, poll_interval))
            continue
        for name, link, auto_buy, quantity, purchased in items:
            if purchased:
                continue
            if not any(p in (link or "") for p in plugin.domain_patterns):
                continue
            try:
                # write_queue.put() calls inside _check_and_buy are safe here because
                # write_queue is UNBOUNDED (maxsize==0, asserted in async_main). An unbounded
                # asyncio.Queue.put() never suspends, so the timeout cannot fire mid-put and
                # orphan a pending DB write (REL-06). If the item times out before reaching
                # put(), the write is simply not reached -- no orphan (WR-01).
                async with asyncio.timeout(item_timeout):
                    await _check_and_buy(plugin, name, link, auto_buy, write_queue, dispatcher=dispatcher)
            except TimeoutError:
                writeLog(
                    f"[{plugin.__class__.__name__}] item timeout ({item_timeout}s): {name} -- skipping",
                    "WARNING",
                )
        await asyncio.sleep(_get_plugin_sleep(plugin, poll_interval))


async def _attempt_buy(plugin, link) -> tuple[bool, str | None]:
    """Retryable unit: run auto_buy + confirmation detection; return (success, order_id).

    No enqueue here -- callers keep write_queue.put() outside the retry loop (WR-02).
    Returns (False, None) on auto_buy failure or exception so the retry loop can decide.
    Returns (True, None) on confirmation detection error: order placed but id undetected.
    """
    from core.confirmation import detect_order_confirmation
    try:
        success = await plugin.auto_buy(link)
    except Exception as exc:
        writeLog(
            f"[{plugin.__class__.__name__}] auto_buy error: {exc.__class__.__name__}",
            "ERROR",
        )
        return False, None
    if not success:
        return False, None
    tab = plugin.get_active_tab()
    platform = plugin.__class__.__name__
    order_id = None
    if tab is not None:
        try:
            order_id = await detect_order_confirmation(tab, platform)
        except Exception as exc:
            writeLog(
                f"[{platform}] confirmation detection error: {exc.__class__.__name__}",
                "ERROR",
            )
    return True, order_id


class _AlreadyConfirmed(Exception):
    """Sentinel: raised inside on_attempt to abort retry when order already confirmed."""
    def __init__(self, order_id: str) -> None:
        self.order_id = order_id


async def _enqueue_buy_result(name, link, platform, order_id, write_queue, dispatcher) -> None:
    """Enqueue confirmation or legacy-purchased after a successful buy (WR-02).

    Called OUTSIDE the retry loop: ensures exactly one enqueue per successful buy.
    """
    if dispatcher is not None:
        await dispatcher.notify(_build_event(name, link, platform, "purchased"))
    if order_id is not None:
        ts = datetime.now(timezone.utc).isoformat()
        await write_queue.put(("confirmed", link, order_id, ts))
    else:
        writeLog(
            f"[{platform}] confirmation not detected -- falling back to legacy purchased write",
            "WARNING",
        )
        await write_queue.put(("purchased", link))


async def _pre_attempt_check(loop, link: str, platform: str) -> None:
    """Re-read DB state before each attempt; raise _AlreadyConfirmed or increment counter.

    Called via on_attempt in _try_auto_buy. Raises _AlreadyConfirmed to abort the retry
    loop when a prior confirmed order_id is found OR item was already purchased via the
    legacy path (BUY-05 no-double-buy). Covers both purchased=True/order_id=NULL (legacy)
    and purchased=True/order_id=<value> (confirmed) states.
    """
    purchased, existing_order_id = await loop.run_in_executor(
        None, get_item_order_state_sync, link
    )
    if existing_order_id is not None:
        writeLog(
            f"[{platform}] prior confirmed order_id={existing_order_id} -- skipping retry",
            "INFO",
        )
        raise _AlreadyConfirmed(existing_order_id)
    if purchased:
        writeLog(
            f"[{platform}] item already purchased (legacy path) -- skipping retry",
            "INFO",
        )
        raise _AlreadyConfirmed("")
    await loop.run_in_executor(None, increment_checkout_attempts_sync, link)


async def _try_auto_buy(plugin, name, link, write_queue, dispatcher) -> None:
    """Cart-retry wrapper; enqueue OUTSIDE loop (WR-02). total=1+max_cart_retries."""
    from core.config_schema import CheckoutConfig
    loop = asyncio.get_running_loop()
    platform = plugin.__class__.__name__
    cfg = getattr(plugin.config, "checkout", None) or CheckoutConfig()
    policy = RetryPolicy(
        max_attempts=cfg.max_cart_retries + 1,
        backoff_base=cfg.backoff_base,
        backoff_jitter=cfg.backoff_jitter,
    )
    try:
        result = await with_retry(
            lambda: _attempt_buy(plugin, link),
            policy,
            should_retry=lambda r: not r[0],  # only retry on auto_buy failure; True+no-order_id flows to legacy enqueue (no-double-buy)
            on_attempt=lambda _: _pre_attempt_check(loop, link, platform),
        )
    except _AlreadyConfirmed as confirmed:
        writeLog(f"[{platform}] idempotency exit: order_id={confirmed.order_id}", "INFO")
        return
    success, order_id = result
    if not success:
        writeLog(f"[{platform}] cart-retry exhausted (stage={plugin._checkout_stage})", "WARNING")
        return
    await _enqueue_buy_result(name, link, platform, order_id, write_queue, dispatcher)


async def _check_and_buy(plugin, name, link, auto_buy, write_queue, dispatcher=None):
    """Check one item and optionally buy it. Logs and continues on any error."""
    loop = asyncio.get_running_loop()
    try:
        available = await plugin.check_availability(link)
    except Exception as exc:
        writeLog(f"[{plugin.__class__.__name__}] check error: {exc.__class__.__name__}", "ERROR")
        return

    # Price monitoring path (PRICE-02): called only after check_availability succeeds.
    price_cents = None
    try:
        price_cents = await plugin.get_price(link)
    except Exception as exc:
        writeLog(f"[{plugin.__class__.__name__}] get_price error: {exc.__class__.__name__}", "ERROR")

    if price_cents is not None and price_cents > 0:
        try:
            # Read previous price BEFORE appending current one (Pitfall 3)
            prev_price = await loop.run_in_executor(None, get_last_price_sync, link)
            now_iso = datetime.now(timezone.utc).isoformat()
            await loop.run_in_executor(None, append_price_history_sync, link, price_cents, now_iso)
            await _evaluate_price_triggers(plugin, name, link, price_cents, prev_price, dispatcher, loop)
        except Exception as exc:
            writeLog(f"[{plugin.__class__.__name__}] price-history error: {exc.__class__.__name__}", "ERROR")

    was_available, _ = await loop.run_in_executor(None, get_item_notification_state_sync, link)

    if available and not was_available:
        writeLog(f"{name} is AVAILABLE -- {link}", "SUCCESS")
        if dispatcher is not None:
            await dispatcher.notify(_build_event(name, link, plugin.__class__.__name__, "detected"))
        now_iso = datetime.now(timezone.utc).isoformat()
        await write_queue.put(("set_available", link, now_iso))
    elif not available and was_available:
        await write_queue.put(("clear_available", link))
        return
    elif not available:
        return

    if auto_buy:
        debug_cfg = getattr(plugin.config, "debug", None) if plugin.config is not None else None
        if getattr(debug_cfg, "monitor_only", False):
            writeLog(
                f"[{plugin.__class__.__name__}] monitor-only: skipping auto_buy for {name}",
                "INFO",
            )
            return
        await _try_auto_buy(plugin, name, link, write_queue, dispatcher)


async def _dispatch_write(loop, item) -> None:
    """Execute a single typed write-queue item against the correct models function.

    Supported tuple tags:
      ("purchased", link)                      -> update_item_purchased_sync(link)
      ("confirmed", link, order_id, ts)        -> update_item_confirmed_sync(link, order_id, ts)
      ("set_available", link, ts)              -> set_item_available_sync(link, ts)
      ("clear_available", link)                -> clear_item_available_sync(link)
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
    elif tag == "confirmed":
        link, order_id, ts = item[1], item[2], item[3]
        await loop.run_in_executor(None, update_item_confirmed_sync, link, order_id, ts)
        writeLog(f"Order confirmed: {link} order_id={order_id}", "INFO")
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
            writeLog(f"DB write failed for {item!r}: {exc.__class__.__name__}", "ERROR")
        finally:
            queue.task_done()


async def _flush_write_queue(queue: asyncio.Queue, loop) -> None:
    """Drain remaining items after TaskGroup exits (drain task was cancelled).

    The _write_queue_drain task may have an in-flight item with task_done() not yet
    called (queue.join() would hang). Manual get_nowait() + task_done() drains it.
    Errors are logged; task_done() is always called so join() does not deadlock (T-22-06).
    """
    while not queue.empty():
        item = queue.get_nowait()
        try:
            await _dispatch_write(loop, item)
        except Exception as exc:
            writeLog(f"Write-queue flush error for {item!r}: {exc.__class__.__name__}", "ERROR")
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
            registry.assign_proxy(plugin)
            registry.assign_solver(plugin)
            await plugin.setup()
            registry._active_plugins.append(plugin)
        except Exception as exc:
            writeLog(
                f"Plugin {plugin.__class__.__name__} setup failed: {exc.__class__.__name__} -- skipping",
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


def _build_proxy_pool(cfg):
    """Return a ProxyPool when proxy is enabled, else None."""
    if not getattr(getattr(cfg, "proxy", None), "enabled", False):
        return None
    return ProxyPool.from_urls(
        cfg.proxy.urls,
        cfg.proxy.max_failures,
        cfg.proxy.cooldown_secs,
    )


def _build_captcha_solver(cfg):
    """Return a CaptchaSolver when captcha is enabled and key is present, else None."""
    if not getattr(getattr(cfg, "captcha", None), "enabled", False):
        return None
    return CaptchaSolver.from_config(cfg.captcha, get_store())


def _register_signals(loop, root_task) -> None:
    """Register SIGTERM/SIGINT handlers for cooperative teardown (SRV-02).

    POSIX: loop.add_signal_handler (thread-safe, runs in event loop).
    Windows ProactorEventLoop: raises NotImplementedError; fallback to signal.signal.
    Both paths use loop.call_soon_threadsafe (mirrors BotService.stop() pattern).
    """
    def _shutdown(*_) -> None:
        writeLog("Shutdown signal received -- initiating teardown", "INFO")
        loop.call_soon_threadsafe(root_task.cancel)

    try:
        loop.add_signal_handler(signal.SIGTERM, _shutdown)
        loop.add_signal_handler(signal.SIGINT, _shutdown)
    except NotImplementedError:
        # Windows ProactorEventLoop does not support add_signal_handler
        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)


async def async_main(cfg, cvv) -> None:
    """Entry point: stagger setup, run TaskGroup, teardown cleanly."""
    from notifications import build_dispatcher

    plugins_dir = Path(__file__).parent.parent / "plugins"
    proxy_pool = _build_proxy_pool(cfg)
    captcha_solver = _build_captcha_solver(cfg)
    loop = asyncio.get_running_loop()
    root_task = asyncio.current_task()
    _register_signals(loop, root_task)

    if captcha_solver is not None:
        await loop.run_in_executor(None, captcha_solver.check_balance_at_startup)

    registry = PluginRegistry(cfg, plugins_dir, proxy_pool=proxy_pool, captcha_solver=captcha_solver)

    items = await loop.run_in_executor(None, get_items_sync)
    await _staggered_setup(registry, items)

    if cvv:
        bb_plugin = registry.route("https://www.bestbuy.com/")
        if bb_plugin:
            bb_plugin._cvv = cvv
        amz_plugin = registry.route("https://www.amazon.com/")
        if amz_plugin:
            amz_plugin._cvv = cvv

    poll_interval = float(getattr(cfg.app, "poll_interval", 30))
    write_queue: asyncio.Queue = asyncio.Queue()
    assert write_queue.maxsize == 0, "write_queue must remain unbounded (REL-06): bounded queue + asyncio.timeout = orphaned writes"
    dispatcher = build_dispatcher(cfg)

    _start_stdin_listener(registry._active_plugins, loop)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_write_queue_drain(write_queue), name="write-queue-drain")
            for plugin in registry._active_plugins:
                tg.create_task(
                    supervise(plugin, write_queue, poll_interval, dispatcher=dispatcher, cfg=cfg, registry=registry),
                    name=f"poll-{plugin.__class__.__name__}",
                )
    except* KeyboardInterrupt:
        pass
    finally:
        await _flush_write_queue(write_queue, loop)
        try:
            await asyncio.wait_for(write_queue.join(), timeout=5)
        except asyncio.TimeoutError:
            writeLog("Write queue join timed out after manual flush", "WARNING")
        await registry.teardown_all()
