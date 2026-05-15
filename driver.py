"""Selenium Chrome driver factory with Phase 1 stealth + INFRA-03 hardening.

SEC-03: removes the same-origin-bypass Chrome flag.
SEC-04: CDP patch hides navigator.webdriver before any page script runs.
SEC-05: real Chrome user agent, no Selenium/HeadlessChrome substring.
INFRA-03: ChromeDriver output via Service log_path; no stdout reassignment.

Phase 6 ANTI-02: build_driver picks a fresh UA via random.choice on each call
(from caller-supplied list or DEFAULT_USER_AGENTS). Phase 6 D-04: optional
`headless=True` adds `--headless=new` (NOT the deprecated bare `--headless`,
which is fingerprintable per RESEARCH pitfall #3).
"""
import os
import random

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

DEFAULT_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
]

WEBDRIVER_HIDE_JS = (
    "Object.defineProperty(Navigator.prototype, 'webdriver', "
    "{get: () => undefined}); "
    "/* hides navigator.webdriver from page scripts */"
)


def build_driver(
    driver_path: str,
    log_path: str = "logs/chromedriver.log",
    headless: bool = False,
    user_agents: list[str] | None = None,
):
    """Construct a hardened Selenium Chrome driver instance.

    Caller owns the returned driver lifecycle. No shared global state.

    Args:
        driver_path: filesystem path to chromedriver binary.
        log_path: chromedriver log destination (INFRA-03).
        headless: when True, adds `--headless=new` Chrome arg (Phase 6 D-04).
        user_agents: optional UA pool; falls back to DEFAULT_USER_AGENTS.
            One UA is chosen per call via random.choice (ANTI-02).
    """
    opts = Options()
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "autofill.profile_enabled": False,
        "autofill.credit_card_enabled": False,
    }
    opts.add_experimental_option("prefs", prefs)
    chosen_ua = random.choice(user_agents or DEFAULT_USER_AGENTS)
    opts.add_argument(f"--user-agent={chosen_ua}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-site-isolation-trials")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--disable-save-password-bubble")
    opts.add_argument("--disable-translate")
    if headless:
        opts.add_argument("--headless=new")

    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    service = Service(executable_path=driver_path, log_path=log_path)
    driver = webdriver.Chrome(service=service, options=opts)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": WEBDRIVER_HIDE_JS},
    )
    return driver
