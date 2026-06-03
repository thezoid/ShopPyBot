import sys
import asyncio
import getpass
import requests
import yaml
from pathlib import Path
from logger import setup_logger, writeLog
from utils import play_notification_sound, play_buy_sound, play_available_sound
import webbrowser
from models import initialize_db, add_items, get_items
from pydantic import ValidationError
from core.config_schema import AppConfig
from core.registry import PluginRegistry


def make_tiny(url):
    writeLog(f"Creating tiny URL for {url}", "DEBUG")
    request_url = f'http://tinyurl.com/api-create.php?url={url}'
    response = requests.get(request_url)
    short_url = response.text
    writeLog(f"Tiny URL created: {short_url}", "DEBUG")
    return short_url


def collect_cvv():
    """Collect CVV via hidden input at runtime. Never echoes or stores to disk (SEC-02)."""
    try:
        cvv = getpass.getpass("Enter CVV (input hidden): ").strip()
    except getpass.GetPassWarning:
        print("WARNING: CVV echo suppression unavailable in this terminal", file=sys.stderr)
        raise SystemExit("Cannot collect CVV securely. Run in an interactive terminal.")
    if not cvv:
        raise SystemExit("CVV is required for auto-buy. Exiting.")
    return cvv


async def async_main(cfg, cvv) -> None:
    """Async entry point: drives the plugin registry in a sequential item loop (D-03)."""
    plugins_dir = Path(__file__).parent / "plugins"
    registry = PluginRegistry(cfg, plugins_dir)
    await registry.setup_for_items(get_items())

    # T-02-12: CVV is held in memory only; set on the BestBuy plugin instance
    # after setup so it is available during auto_buy without logging the value.
    if cvv:
        bb_plugin = registry.route("https://www.bestbuy.com/")
        if bb_plugin:
            bb_plugin._cvv = cvv

    try:
        while True:
            writeLog("Starting new iteration of item checks", "INFO")
            for item in get_items():
                name, link, auto_buy, quantity, purchased = item
                if purchased:
                    writeLog(f"{name} has already been purchased", "INFO")
                    continue

                plugin = registry.route(link)
                if not plugin:
                    writeLog(f"No plugin for URL: {link}", "WARNING")
                    continue

                available = await plugin.check_availability(link)
                if available:
                    play_available_sound()
                    short_url = make_tiny(link)
                    writeLog(f"{name} is available: {short_url}", "SUCCESS")
                    if auto_buy:
                        writeLog(f"Attempting to auto-buy {name}", "INFO")
                        # T-02-12: set _cvv lazily on the plugin before auto_buy;
                        # the value never appears in logs or config.
                        if cvv and hasattr(plugin, "_cvv"):
                            plugin._cvv = cvv
                        success = await plugin.auto_buy(link)
                        if success:
                            play_buy_sound()
                    else:
                        writeLog(f"{name} is available but auto-buy is disabled", "INFO")
                else:
                    writeLog(f"{name} is not available", "INFO")
    except KeyboardInterrupt:
        pass
    finally:
        await registry.teardown_all()


def main():
    writeLog("Starting main function", "INFO")

    # Validate config at startup; exit cleanly on schema error (CORE-05)
    try:
        cfg = AppConfig()
    except ValidationError as e:
        print(f"Configuration error -- fix config.yml:\n{e}")
        raise SystemExit(1)

    # Initialize the database and add items from config
    initialize_db()
    items = [
        (item.name, item.link, item.auto_buy, item.quantity, False)
        for item in cfg.available.items
    ]
    add_items(items)

    # SEC-01/02: collect BestBuy CVV from getpass BEFORE asyncio.run() (D-03 / Pitfall 6).
    # Only prompt if not in test_mode AND at least one BestBuy item has auto_buy enabled.
    # In test_mode the purchase step is skipped, so blocking on a getpass prompt would
    # break CI and violate the test_mode contract (WR-02).
    needs_bb_autobuy = (
        not cfg.debug.test_mode
        and any("bestbuy.com" in item.link and item.auto_buy for item in cfg.available.items)
    )
    cvv = collect_cvv() if needs_bb_autobuy else None

    asyncio.run(async_main(cfg, cvv))


if __name__ == "__main__":
    logger = setup_logger()
    main()
