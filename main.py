"""ShopPyBot entrypoint (Phase 1 integration).

Wires AppConfig (config_schema), build_driver (driver), collect_cvvs
(credentials), and logger.configure into a single startup path. The
polling-loop semantics (domain routing, CAPTCHA prompt, sound playback)
are preserved from the legacy main.py.
"""
import sys

if sys.version_info < (3, 11):
    sys.exit(f"ShopPyBot requires Python 3.11+. Detected: {sys.version}")

import os
import webbrowser

import requests
from webdriver_manager.chrome import ChromeDriverManager

from amazon_bot import auto_buy_amazon_item, check_amazon_item, detect_captcha
from bestbuy_bot import auto_buy_bestbuy_item, check_bestbuy_item
from config_schema import AppConfig
from credentials import collect_cvvs
from driver import build_driver
from logger import configure as configure_logger, writeLog
from models import add_items, get_items, initialize_db
from utils import play_available_sound, play_buy_sound, play_notification_sound


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


def _handle_amazon(driver, name, link, auto_buy, quantity, app_config, test_mode, open_browser):
    writeLog(f"Checking availability for Amazon item: {name}", "INFO")
    driver.get(link)
    if detect_captcha(driver):
        writeLog("CAPTCHA detected. Please solve it manually.", "WARNING")
        play_notification_sound()
        input("Press Enter after solving the CAPTCHA...")
    if not check_amazon_item(driver, link):
        writeLog(f"{name} is not available", "INFO")
        return
    play_available_sound()
    writeLog(f"{name} is available: {make_tiny(link)}", "SUCCESS")
    if auto_buy:
        writeLog(f"Attempting to auto-buy {name} on Amazon", "INFO")
        auto_buy_amazon_item(driver, link, app_config, quantity, test_mode)
        return
    writeLog(f"{name} is available but auto-buy is disabled", "INFO")
    if open_browser:
        webbrowser.open(link)


def _handle_bestbuy(driver, name, link, auto_buy, quantity, app_config, cvvs, test_mode, open_browser):
    writeLog(f"Checking availability for BestBuy item: {name}", "INFO")
    if not check_bestbuy_item(driver, link):
        writeLog(f"{name} is not available", "INFO")
        return
    play_available_sound()
    writeLog(f"{name} is available: {make_tiny(link)}", "SUCCESS")
    if auto_buy:
        writeLog(f"Attempting to auto-buy {name} on BestBuy", "INFO")
        if not test_mode:
            bb = app_config.platforms['bestbuy'].credentials
            auto_buy_bestbuy_item(driver, link, bb.email, bb.password, cvvs['bestbuy'], quantity)
            play_buy_sound()
        else:
            writeLog("Test mode active: Skipping final purchase step", "INFO")
        return
    writeLog(f"{name} is available but auto-buy is disabled", "INFO")
    if open_browser:
        webbrowser.open(link)


def main():
    try:
        app_config = AppConfig()
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)

    configure_logger(app_config.debug.logging_level)
    writeLog("Starting ShopPyBot", "INFO")

    cvvs = collect_cvvs(app_config)

    driver_path = get_chromedriver_path(app_config.selenium.driver_path)
    driver = build_driver(driver_path)

    initialize_db()
    items = [
        (it.name, it.link, it.auto_buy, it.quantity, False)
        for it in app_config.available.items
    ]
    add_items(items)

    test_mode = app_config.debug.test_mode
    open_browser = app_config.open_browser

    while True:
        writeLog("Starting new iteration of item checks", "INFO")
        for item in get_items():
            name, link, auto_buy, quantity, purchased = item
            if purchased:
                writeLog(f"{name} has already been purchased", "INFO")
                continue
            if "amazon.com" in link:
                _handle_amazon(driver, name, link, auto_buy, quantity, app_config, test_mode, open_browser)
            elif "bestbuy.com" in link:
                _handle_bestbuy(driver, name, link, auto_buy, quantity, app_config, cvvs, test_mode, open_browser)
            else:
                writeLog(f"Unsupported URL: {link}", "WARNING")


if __name__ == "__main__":
    main()
