"""Target retailer plugin (PLG-05).

nodriver-based async plugin. Akamai Bot Manager consistently blocks headless
Selenium AND fingerprints headless Chrome; nodriver in non-headless mode is
the recommended posture. When the user opts into headless via platform_config,
this plugin emits a startup WARNING flagging the Akamai risk.

Auto-buy is EXPERIMENTAL per PLG-05 (Akamai may block mid-flow); gated behind
SHOPBOT_ENABLE_RISKY_AUTOBUY=true at __init__ (D-02 mirrors Phase 5 SMS
two-lock). DOM selectors are representative per RESEARCH O-5; executor refines
against the live Target PDP.

O-3 (nodriver 0.50.3, surfaced by Plan 06-02): Browser.stop() is SYNC and
returns None. shutdown() calls stop() and only awaits the return value if it
is awaitable, covering both the current sync shape and any future coroutine
release without crashing the orchestrator.
"""
import inspect
import os
import random

import nodriver as uc

from driver import DEFAULT_USER_AGENTS
from logger import writeLog
from plugin_base import RetailerPlugin

# TODO: re-verify against live Target PDP — see Plan 06-03 Task 1.
# Representative ATC/Pickup selector per RESEARCH per-retailer table (Q3).
_ATC_SELECTOR = 'button[data-test="orderPickupButton"]'


class TargetPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["target.com"]
    login_at_startup: bool = False
    name: str = "target"

    def __init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None):
        super().__init__(platform_config)
        self._riskyAutoBuyEnabled = (
            os.environ.get("SHOPBOT_ENABLE_RISKY_AUTOBUY", "").strip().lower() == "true"
        )
        self.min_delay = getattr(platform_config, "min_delay", 3.0)
        self.max_delay = getattr(platform_config, "max_delay", 8.0)
        self._headless = getattr(platform_config, "headless", False)
        self._userAgents = user_agents or DEFAULT_USER_AGENTS
        self.driver = None
        if self._headless:
            writeLog(
                "Target plugin: headless mode often blocked by Akamai; expect failures",
                "WARNING",
            )

    async def open(self) -> None:
        chosenUa = random.choice(self._userAgents)
        self.driver = await uc.start(
            headless=self._headless,
            browser_args=[
                f"--user-agent={chosenUa}",
                "--disable-blink-features=AutomationControlled",
            ],
        )

    async def check_availability(self, url: str) -> bool:
        try:
            tab = await self.driver.get(url)
            atc = await tab.select(_ATC_SELECTOR)
            return atc is not None
        except Exception as e:
            writeLog(f"TargetPlugin.check_availability error on {url}: {e}", "ERROR")
            return False

    async def auto_buy(self, url: str, config) -> bool:
        if not self._riskyAutoBuyEnabled:
            writeLog(
                "Target auto_buy skipped: set SHOPBOT_ENABLE_RISKY_AUTOBUY=true to enable",
                "WARNING",
            )
            return False
        return await self._purchaseFlow(url, config)

    async def _purchaseFlow(self, url: str, config) -> bool:
        try:
            tab = await self.driver.get(url)
            atc = await tab.select(_ATC_SELECTOR)
            if atc is None:
                writeLog(f"Target auto_buy: ATC button not present on {url}", "WARNING")
                return False
            await atc.click()
            cartTab = await self.driver.get("https://www.target.com/cart")
            checkoutBtn = await cartTab.select('button[data-test="checkout-button"]')
            if checkoutBtn is None:
                writeLog("Target auto_buy: checkout button not present", "WARNING")
                return False
            await checkoutBtn.click()
            placeOrderBtn = await cartTab.select('button[data-test="placeOrderButton"]')
            if placeOrderBtn is None:
                writeLog("Target auto_buy: place-order button not present", "WARNING")
                return False
            if getattr(getattr(config, "debug", None), "test_mode", True):
                writeLog("Target auto_buy: test_mode on, skipping final click", "INFO")
                return False
            await placeOrderBtn.click()
            return True
        except Exception as e:
            writeLog(f"TargetPlugin.auto_buy error on {url}: {e}", "ERROR")
            return False

    async def shutdown(self) -> None:
        driver = getattr(self, "driver", None)
        if driver is None:
            return
        try:
            result = driver.stop()
            if inspect.isawaitable(result):
                await result
        except Exception as e:
            writeLog(f"TargetPlugin.shutdown: driver.stop raised: {e}", "WARNING")
