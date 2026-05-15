"""GameStop retailer plugin (PLG-06).

nodriver-based async plugin. GameStop uses hCaptcha at checkout; this plugin
detects it via two complementary selectors (iframe + widget container) and
pauses for manual solve via `await asyncio.to_thread(input, ...)` (Phase 4
D-02 pattern). The to_thread bridge blocks only the GameStop worker thread,
so the orchestrator's event loop continues serving the other plugins.

Auto-buy is gated behind SHOPBOT_ENABLE_RISKY_AUTOBUY=true at __init__
(D-02 mirrors Phase 5 SMS two-lock + Wave 1 sibling pattern).

O-3 (nodriver 0.50.3, surfaced by Plan 06-02): Browser.stop() is SYNC and
returns None. shutdown() calls stop() and only awaits the return value if it
is awaitable, covering both the current sync shape and a future coroutine
release without crashing the orchestrator.

DOM selectors are representative per RESEARCH O-5; runtime verification
against live GameStop PDP/checkout will refine.
"""
import asyncio
import inspect
import os
import random

import nodriver as uc

from driver import DEFAULT_USER_AGENTS
from logger import writeLog
from plugin_base import RetailerPlugin

# TODO: re-verify against live GameStop PDP/checkout (Plan 06-04 Task 1).
# Representative ATC selector per RESEARCH per-retailer table (Q3).
_ATC_SELECTOR = 'button.add-to-cart:not(:disabled)'
# hCaptcha embed surfaces both as an iframe and a widget container div.
_HCAPTCHA_IFRAME = 'iframe[src*="hcaptcha.com"]'
_HCAPTCHA_WIDGET = 'div[data-hcaptcha-widget-id]'


class GamestopPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["gamestop.com"]
    login_at_startup: bool = False
    name: str = "gamestop"

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
        self._tab = None

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
            writeLog(f"GamestopPlugin.check_availability error on {url}: {e}", "ERROR")
            return False

    async def detect_captcha(self) -> bool:
        if self._tab is None:
            return False
        try:
            iframe = await self._tab.select(_HCAPTCHA_IFRAME)
            if iframe is not None:
                return True
            widget = await self._tab.select(_HCAPTCHA_WIDGET)
            return widget is not None
        except Exception as e:
            writeLog(f"GamestopPlugin.detect_captcha error: {e}", "TRACE")
            return False

    async def auto_buy(self, url: str, config) -> bool:
        if not self._riskyAutoBuyEnabled:
            writeLog(
                "GameStop auto_buy skipped: set SHOPBOT_ENABLE_RISKY_AUTOBUY=true to enable",
                "WARNING",
            )
            return False
        return await self._purchaseFlow(url, config)

    async def _purchaseFlow(self, url: str, config) -> bool:
        try:
            self._tab = await self.driver.get(url)
            atc = await self._tab.select(_ATC_SELECTOR)
            if atc is None:
                writeLog(f"GameStop auto_buy: ATC button not present on {url}", "WARNING")
                return False
            await atc.click()
            self._tab = await self.driver.get("https://www.gamestop.com/cart/")
            if await self.detect_captcha():
                writeLog("GameStop CAPTCHA detected; pausing for manual solve", "WARNING")
                await asyncio.to_thread(
                    input,
                    "GameStop CAPTCHA detected; solve in the browser and press Enter to continue",
                )
            checkoutBtn = await self._tab.select('button.checkout-continue')
            if checkoutBtn is None:
                writeLog("GameStop auto_buy: checkout button not present", "WARNING")
                return False
            await checkoutBtn.click()
            if await self.detect_captcha():
                writeLog("GameStop CAPTCHA detected at checkout; pausing for manual solve", "WARNING")
                await asyncio.to_thread(
                    input,
                    "GameStop CAPTCHA detected; solve in the browser and press Enter to continue",
                )
            placeOrderBtn = await self._tab.select('button.place-order')
            if placeOrderBtn is None:
                writeLog("GameStop auto_buy: place-order button not present", "WARNING")
                return False
            if getattr(getattr(config, "debug", None), "test_mode", True):
                writeLog("GameStop auto_buy: test_mode on, skipping final click", "INFO")
                return False
            await placeOrderBtn.click()
            return True
        except Exception as e:
            writeLog(f"GamestopPlugin.auto_buy error on {url}: {e}", "ERROR")
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
            writeLog(f"GamestopPlugin.shutdown: driver.stop raised: {e}", "WARNING")
