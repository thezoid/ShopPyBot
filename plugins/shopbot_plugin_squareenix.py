"""Square Enix retailer plugin (PLG-07).

nodriver-based async plugin. Light Cloudflare protection sits in front of the
storefront per RESEARCH per-retailer table; headless mode is feasible but the
PlatformConfig default remains False for safety. Dual-domain pattern covers
both square-enix.com (US store) and square-enix-games.com (EU/games subdomain
and its store.* / store.na.* / store.eu.* hosts via suffix match in the
registry).

Auto-buy is gated behind SHOPBOT_ENABLE_RISKY_AUTOBUY=true.

O-1 (resolved POSITIVE, Plan 06-02): await uc.start() works inside the
orchestrator's asyncio.run loop, so we use the standard async pattern.

O-3 (resolved NEGATIVE, Plan 06-02): nodriver 0.50.3's Browser.stop() is a
SYNC method returning None. shutdown() uses inspect.isawaitable() on the
return value rather than a bare await to handle both shapes.

DOM selectors are representative — executor verifies against live Square Enix
PDP at implementation time per RESEARCH O-5. TODO marker retained until live
verification refines the selector.
"""
import inspect
import os
import random

import nodriver as uc

from driver import DEFAULT_USER_AGENTS
from logger import writeLog
from plugin_base import RetailerPlugin

# TODO: re-verify against live Square Enix PDP per Plan 06-05 Task 1.
# Representative ATC selector per RESEARCH per-retailer table.
_ATC_SELECTOR = 'button.product-detail-add-to-cart'


class SquareEnixPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["square-enix.com", "square-enix-games.com"]
    login_at_startup: bool = False
    name: str = "squareenix"

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
            btn = await tab.select(_ATC_SELECTOR)
            return btn is not None
        except Exception as e:
            writeLog(f"SquareEnixPlugin.check_availability error on {url}: {e}", "ERROR")
            return False

    async def auto_buy(self, url: str, config) -> bool:
        if not self._riskyAutoBuyEnabled:
            writeLog(
                "Square Enix auto_buy skipped: set SHOPBOT_ENABLE_RISKY_AUTOBUY=true to enable",
                "WARNING",
            )
            return False
        return await self._purchaseFlow(url, config)

    async def _purchaseFlow(self, url: str, config) -> bool:
        try:
            tab = await self.driver.get(url)
            atc = await tab.select(_ATC_SELECTOR)
            if atc is None:
                writeLog(f"Square Enix auto_buy: ATC button not present on {url}", "WARNING")
                return False
            await atc.click()
            checkoutBtn = await tab.select('button.checkout-button')
            if checkoutBtn is None:
                writeLog("Square Enix auto_buy: checkout button not present", "WARNING")
                return False
            await checkoutBtn.click()
            placeOrderBtn = await tab.select('button.place-order-button')
            if placeOrderBtn is None:
                writeLog("Square Enix auto_buy: place-order button not present", "WARNING")
                return False
            if getattr(getattr(config, "debug", None), "test_mode", True):
                writeLog("Square Enix auto_buy: test_mode on, skipping final click", "INFO")
                return False
            await placeOrderBtn.click()
            return True
        except Exception as e:
            writeLog(f"SquareEnixPlugin.auto_buy error on {url}: {e}", "ERROR")
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
            writeLog(f"SquareEnixPlugin.shutdown: driver.stop raised: {e}", "WARNING")
