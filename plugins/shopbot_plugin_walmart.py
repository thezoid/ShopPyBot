"""Walmart retailer plugin (PLG-04).

nodriver-based async plugin. PerimeterX/HUMAN risk is documented in SECURITY.md
and logged once per instance on first auto_buy attempt. Risky auto_buy is gated
behind SHOPBOT_ENABLE_RISKY_AUTOBUY=true (D-02 mirrors Phase 5 SMS two-lock).

Lifecycle (RESEARCH Q1 + O-1): self.driver is built asynchronously inside
open(), called by discover_async after __init__. uc.start() is awaited from
inside the orchestrator's existing asyncio.run loop; we never call uc.loop().

O-1 smoke (2026-05-15): uc.start(headless=True) succeeded inside asyncio.run().
O-3 surfaced: nodriver 0.50.3's browser.stop() is SYNC (returns None), not a
coroutine. shutdown() handles both shapes via inspect.iscoroutine fallback.
"""
import inspect
import os
import random

import nodriver as uc

from driver import DEFAULT_USER_AGENTS
from logger import writeLog
from plugin_base import RetailerPlugin

# TODO: re-verify against live Walmart PDP — see Plan 06-02 Task 1.
# Representative ATC selector per RESEARCH per-retailer table (A4).
_ATC_SELECTOR = 'button[data-automation-id="atc-button"]'


class WalmartPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["walmart.com"]
    login_at_startup: bool = False
    name: str = "walmart"

    def __init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None):
        super().__init__(platform_config)
        self._riskyAutoBuyEnabled = (
            os.environ.get("SHOPBOT_ENABLE_RISKY_AUTOBUY", "").strip().lower() == "true"
        )
        self._walmartRiskNoted = False
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
            atc = await tab.select(_ATC_SELECTOR)
            return atc is not None
        except Exception as e:
            writeLog(f"WalmartPlugin.check_availability error on {url}: {e}", "ERROR")
            return False

    async def auto_buy(self, url: str, config) -> bool:
        if not self._riskyAutoBuyEnabled:
            writeLog(
                "Walmart auto_buy skipped: set SHOPBOT_ENABLE_RISKY_AUTOBUY=true to enable",
                "WARNING",
            )
            return False
        if not self._walmartRiskNoted:
            writeLog(
                "Walmart auto_buy: PerimeterX/HUMAN may block automation; see SECURITY.md",
                "INFO",
            )
            self._walmartRiskNoted = True
        return await self._purchaseFlow(url, config)

    async def _purchaseFlow(self, url: str, config) -> bool:
        try:
            tab = await self.driver.get(url)
            atc = await tab.select(_ATC_SELECTOR)
            if atc is None:
                writeLog(f"Walmart auto_buy: ATC button not present on {url}", "WARNING")
                return False
            await atc.click()
            cartTab = await self.driver.get("https://www.walmart.com/cart")
            checkoutBtn = await cartTab.select('button[data-automation-id="checkout-btn"]')
            if checkoutBtn is None:
                writeLog("Walmart auto_buy: checkout button not present", "WARNING")
                return False
            await checkoutBtn.click()
            placeOrderBtn = await cartTab.select('button[data-automation-id="place-order-btn"]')
            if placeOrderBtn is None:
                writeLog("Walmart auto_buy: place-order button not present", "WARNING")
                return False
            if getattr(getattr(config, "debug", None), "test_mode", True):
                writeLog("Walmart auto_buy: test_mode on, skipping final click", "INFO")
                return False
            await placeOrderBtn.click()
            return True
        except Exception as e:
            writeLog(f"WalmartPlugin.auto_buy error on {url}: {e}", "ERROR")
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
            writeLog(f"WalmartPlugin.shutdown: driver.stop raised: {e}", "WARNING")
