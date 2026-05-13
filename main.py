"""ShopPyBot entrypoint (Phase 2 plugin-registry integration).

Drives the polling loop via the plugin registry. Discovery + coverage
verification run at startup; per-iteration dispatch uses route_url. There
is no direct knowledge of Amazon or BestBuy in this module: both are
loaded as plugins under `plugins/shopbot_plugin_*.py`.
"""
import sys

if sys.version_info < (3, 11):
    sys.exit(f"ShopPyBot requires Python 3.11+. Detected: {sys.version}")

import os
import webbrowser
from pathlib import Path

import requests
from webdriver_manager.chrome import ChromeDriverManager

from config_schema import AppConfig
from credentials import collect_cvvs
from logger import configure as configure_logger, writeLog
from models import add_items, get_items, initialize_db
from plugin_registry import discover, route_url, verify_coverage
from utils import play_available_sound, play_buy_sound


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
    writeLog(f"Creating tiny URL for {url}", "DEBUG")
    response = requests.get(f"http://tinyurl.com/api-create.php?url={url}")
    return response.text


def _poll_one(plugin, name, link, autoBuy, appConfig, openBrowser):
    try:
        available = plugin.check_availability(link)
    except Exception as e:
        writeLog(
            f"Plugin {type(plugin).__name__} raised on check_availability for {link}: {e}",
            "ERROR",
        )
        return
    if not available:
        writeLog(f"{name} is not available", "INFO")
        return
    play_available_sound()
    writeLog(f"{name} is available: {make_tiny(link)}", "SUCCESS")
    if autoBuy:
        try:
            plugin.auto_buy(link, appConfig)
            play_buy_sound()
        except Exception as e:
            writeLog(
                f"Plugin {type(plugin).__name__} raised on auto_buy for {link}: {e}",
                "ERROR",
            )
        return
    writeLog(f"{name} is available but auto-buy is disabled", "INFO")
    if openBrowser:
        webbrowser.open(link)


def _seed_items(appConfig):
    initialize_db()
    add_items([
        (it.name, it.link, it.auto_buy, it.quantity, False)
        for it in appConfig.available.items
    ])


def _poll_loop(registry, appConfig):
    openBrowser = appConfig.open_browser
    while True:
        writeLog("Starting new iteration of item checks", "INFO")
        for item in get_items():
            name, link, autoBuy, _qty, purchased = item
            if purchased:
                writeLog(f"{name} has already been purchased", "INFO")
                continue
            plugin = route_url(link, registry)
            if plugin is None:
                writeLog(f"Unsupported URL (no plugin): {link}", "WARNING")
                continue
            _poll_one(plugin, name, link, autoBuy, appConfig, openBrowser)


def main():
    try:
        app_config = AppConfig()
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)

    configure_logger(app_config.debug.logging_level)
    writeLog("Starting ShopPyBot", "INFO")

    cvvs = collect_cvvs(app_config)
    app_config.selenium.driver_path = get_chromedriver_path(app_config.selenium.driver_path)

    registry = discover(Path("plugins"), app_config=app_config, cvvs=cvvs)
    verify_coverage(registry, app_config.available.items)

    for plugin in registry:
        if plugin.login_at_startup:
            plugin.login(app_config)

    _seed_items(app_config)
    _poll_loop(registry, app_config)


if __name__ == "__main__":
    main()
