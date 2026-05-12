"""Selenium Chrome driver factory with Phase 1 stealth + INFRA-03 hardening.

SEC-03: removes the same-origin-bypass Chrome flag.
SEC-04: CDP patch hides navigator.webdriver before any page script runs.
SEC-05: real Chrome user agent, no Selenium/HeadlessChrome substring.
INFRA-03: ChromeDriver output via Service log_path; no stdout reassignment.
"""
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

WEBDRIVER_HIDE_JS = (
    "Object.defineProperty(Navigator.prototype, 'webdriver', "
    "{get: () => undefined}); "
    "/* hides navigator.webdriver from page scripts */"
)


def build_driver(driver_path: str, log_path: str = "logs/chromedriver.log"):
    """Construct a hardened Selenium Chrome driver instance.

    Caller owns the returned driver lifecycle. No shared global state.
    """
    opts = Options()
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "autofill.profile_enabled": False,
        "autofill.credit_card_enabled": False,
    }
    opts.add_experimental_option("prefs", prefs)
    opts.add_argument(f"--user-agent={CHROME_UA}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-site-isolation-trials")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--disable-save-password-bubble")
    opts.add_argument("--disable-translate")

    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    service = Service(executable_path=driver_path, log_path=log_path)
    driver = webdriver.Chrome(service=service, options=opts)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": WEBDRIVER_HIDE_JS},
    )
    return driver
