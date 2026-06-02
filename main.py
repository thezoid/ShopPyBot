import sys
import os
import subprocess
import getpass
import yaml
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from logger import setup_logger, writeLog
from amazon_bot import check_amazon_item, auto_buy_amazon_item, detect_captcha
from bestbuy_bot import check_bestbuy_item, auto_buy_bestbuy_item
from utils import play_notification_sound, play_buy_sound, play_available_sound
import webbrowser
from models import initialize_db, add_items, get_items
from pydantic import ValidationError
from core.config_schema import AppConfig

def get_chromedriver_path(cfg):
    writeLog("Entering get_chromedriver_path", "DEBUG")
    driver_path = cfg.selenium.driver_path
    if not os.path.exists(driver_path):
        writeLog(f"Chromedriver not found at {driver_path}. Trying to download the latest version.", "WARNING")
        driver_path = ChromeDriverManager().install()
        if not os.path.exists(driver_path):
            writeLog("Failed to download the latest Chromedriver. Exiting.", "ERROR")
            exit(1)
    writeLog(f"Chromedriver path: {driver_path}", "DEBUG")
    return driver_path

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


def main():
    writeLog("Starting main function", "INFO")

    # Validate config at startup; exit cleanly on schema error (CORE-05)
    try:
        cfg = AppConfig()
    except ValidationError as e:
        print(f"Configuration error -- fix config.yml:\n{e}")
        raise SystemExit(1)

    driver_path = get_chromedriver_path(cfg)

    # Set up Chrome options
    chromeOptions = Options()
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "autofill.profile_enabled": False,
        "autofill.credit_card_enabled": False
    }
    chromeOptions.add_experimental_option("prefs", prefs)
    chromeOptions.add_argument("--disable-blink-features=AutomationControlled")
    chromeOptions.add_argument("--disable-notifications")
    chromeOptions.add_argument("--disable-extensions")
    # SEC-03: disable-web-security flag removed (leaked anti-bot fingerprint)
    # SEC-05: real desktop Chrome UA -- no HeadlessChrome or Selenium marker
    chromeOptions.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    )
    chromeOptions.add_argument("--disable-infobars")
    chromeOptions.add_argument("--disable-save-password-bubble")
    chromeOptions.add_argument("--disable-translate")
    chromeOptions.add_argument(
        "--disable-features=AutofillServerCommunication,PasswordManagerOnboarding,"
        "PasswordManagerSettings,PasswordManagerUI,PasswordManagerInBrowserSettings,"
        "PasswordManagerReauthentication,PasswordManagerAccountStorage,PasswordManager,"
        "PasswordAutofillPublicSuffixDomainMatching,PasswordAutofill,PasswordGeneration,"
        "PasswordImportExport,PasswordLeakDetection,PasswordReuseDetection,PasswordSave"
    )

    # INFRA-03: suppress ChromeDriver subprocess output via Service log_output;
    # no sys.stdout/stderr monkey-patching so Python exceptions remain visible
    service = Service(driver_path, log_output=subprocess.DEVNULL)
    driver = webdriver.Chrome(service=service, options=chromeOptions)

    # SEC-04 (Phase-1 decision): hide navigator.webdriver on the existing Selenium
    # driver via CDP so retailers cannot fingerprint it as automated. This CDP call
    # is removed when nodriver replaces Selenium in Phase 2 (nodriver handles it
    # architecturally). See plan 01-05 objective for full decision rationale.
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
    )

    # Initialize the database and add items from config
    initialize_db()
    items = [
        (item.name, item.link, item.auto_buy, item.quantity, False)
        for item in cfg.available.items
    ]
    add_items(items)

    test_mode = cfg.debug.test_mode
    # open_browser was previously in app: block which no longer exists in schema.
    # Defaulting to False for Phase 1; relocation to AppConfig is a follow-up item.
    open_browser = False

    # SEC-01/02: collect BestBuy credentials from environment; CVV via getpass.
    # Only prompt for CVV if not in test_mode AND at least one BestBuy item has
    # auto_buy enabled. In test_mode the purchase step is skipped, so blocking
    # on a getpass prompt would break CI and violate the test_mode contract (WR-02).
    needs_bb_autobuy = (
        not test_mode
        and any("bestbuy.com" in item.link and item.auto_buy for item in cfg.available.items)
    )
    cvv = collect_cvv() if needs_bb_autobuy else None

    while True:
        writeLog("Starting new iteration of item checks", "INFO")
        for item in get_items():
            name, link, auto_buy, quantity, purchased = item
            if purchased:
                writeLog(f"{name} has already been purchased", "INFO")
                continue
            if "amazon.com" in link:
                writeLog(f"Checking availability for Amazon item: {name}", "INFO")
                driver.get(link)
                if detect_captcha(driver):
                    writeLog("CAPTCHA detected. Please solve it manually.", "WARNING")
                    play_notification_sound()
                    input("Press Enter after solving the CAPTCHA...")
                available = check_amazon_item(driver, link)
                if available:
                    play_available_sound()
                    short_url = make_tiny(link)
                    writeLog(f"{name} is available: {short_url}", "SUCCESS")
                    if auto_buy:
                        writeLog(f"Attempting to auto-buy {name} on Amazon", "INFO")
                        auto_buy_amazon_item(driver, link, cfg, quantity, test_mode)
                    else:
                        writeLog(f"{name} is available but auto-buy is disabled", "INFO")
                        if open_browser:
                            writeLog(f"Opening browser for {name}", "INFO")
                            webbrowser.open(link)
                else:
                    writeLog(f"{name} is not available", "INFO")
            elif "bestbuy.com" in link:
                writeLog(f"Checking availability for BestBuy item: {name}", "INFO")
                available = check_bestbuy_item(driver, link)
                if available:
                    play_available_sound()
                    short_url = make_tiny(link)
                    writeLog(f"{name} is available: {short_url}", "SUCCESS")
                    if auto_buy:
                        writeLog(f"Attempting to auto-buy {name} on BestBuy", "INFO")
                        if not test_mode:
                            # SEC-01: credentials from env vars only; CVV from getpass local
                            bb_email = os.environ.get("BB_EMAIL")
                            bb_password = os.environ.get("BB_PASSWORD")
                            if not bb_email or not bb_password:
                                writeLog(
                                    "ERROR: BB_EMAIL or BB_PASSWORD env var not set. "
                                    "Skipping auto-buy for this item.",
                                    "ERROR"
                                )
                            else:
                                auto_buy_bestbuy_item(
                                    driver, link, bb_email, bb_password, cvv, quantity
                                )
                                play_buy_sound()
                        else:
                            writeLog("Test mode active: Skipping final purchase step", "INFO")
                    else:
                        writeLog(f"{name} is available but auto-buy is disabled", "INFO")
                        if open_browser:
                            writeLog(f"Opening browser for {name}", "INFO")
                            webbrowser.open(link)
                else:
                    writeLog(f"{name} is not available", "INFO")
            else:
                writeLog(f"Unsupported URL: {link}", "WARNING")

if __name__ == "__main__":
    logger = setup_logger()
    main()