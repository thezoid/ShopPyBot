"""GameStop retailer plugin for ShopPyBot.

Anti-detection risk: MEDIUM
Protection: checkout CAPTCHA
Reason: GameStop product pages have lighter protection than Walmart/Target, but
a CAPTCHA appears at checkout. Availability checks are likely functional; auto-buy
will be blocked by CAPTCHA without a solver integration. See SECURITY.md for the
full risk table.

Credentials are sourced exclusively from environment variables (SEC-01):
    GAMESTOP_EMAIL    -- GameStop account email
    GAMESTOP_PASSWORD -- GameStop account password

ASYNC-05: auto_buy returns True on success without calling update_item_purchased
directly. The orchestrator's write queue owns the sole write path.
"""

import os
import random

import nodriver

from core.config_schema import DEFAULT_USER_AGENTS
from core.plugin_base import RetailerPlugin
from logger import writeLog


class GameStopPlugin(RetailerPlugin):
    """GameStop platform plugin; owns one isolated nodriver Browser process.

    Anti-detection risk: MEDIUM -- checkout CAPTCHA (PLG-06).
    UA rotation (ANTI-02) and per-platform headless toggle (ANTI-03) are applied
    in setup(). Product page availability checks are likely functional, but
    auto-buy flows will be blocked by CAPTCHA at checkout.
    """

    domain_patterns = ["gamestop.com", "gamestop.ca"]
    platform_key = "gamestop"  # matches config.platforms.gamestop

    async def setup(self) -> None:
        """Launch nodriver browser with ANTI-02 UA rotation and ANTI-03 headless toggle.

        Reads config.platforms.gamestop.headless (ANTI-03) and user_agents (ANTI-02).
        Falls back to headless=True and DEFAULT_USER_AGENTS when config is absent.
        """
        headless = True
        ua_list: list[str] = []

        if self.config:
            platform_cfg = getattr(self.config.platforms, self.platform_key, None)
            if platform_cfg is not None:
                headless = getattr(platform_cfg, "headless", True)
                ua_list = getattr(platform_cfg, "user_agents", [])

        # ANTI-02: rotate UA from platform list or fall back to global default pool
        browser_args: list[str] | None = None
        if ua_list:
            ua = random.choice(ua_list)
            browser_args = [f"--user-agent={ua}"]
        else:
            ua = random.choice(DEFAULT_USER_AGENTS)
            browser_args = [f"--user-agent={ua}"]

        # ANTI-03: per-platform headless toggle; nodriver.Config appends --headless=new when True.
        # NOTE: never pass "--headless" via browser_args -- nodriver raises ValueError.
        self.driver = await nodriver.start(headless=headless, browser_args=browser_args)

    async def teardown(self) -> None:
        if self.driver:
            self.driver.stop()
            self.driver = None

    async def check_availability(self, url: str) -> bool:
        """Return True if the item at url has an add-to-cart button."""
        writeLog(f"Checking GameStop availability: {url}", "DEBUG")
        try:
            tab = await self.driver.get(url)
            # TODO: verify selectors against live gamestop.com
            # GameStop uses "Add to Cart", "Pre-Order" button states (ASSUMED):
            add_to_cart = await tab.select('[value="Add to Cart"]', timeout=10)
            if add_to_cart:
                writeLog("Add-to-cart button found on GameStop", "INFO")
                writeLog("Item is available on GameStop", "SUCCESS")
                return True
            # Fallback: text-based search (ASSUMED)
            add_to_cart_text = await tab.find("Add to Cart", timeout=5)
            if add_to_cart_text:
                writeLog("Add-to-cart text found on GameStop", "INFO")
                return True
            writeLog("Add-to-cart button not found on GameStop", "INFO")
            return False
        except Exception as exc:
            writeLog(f"Error checking GameStop item: {exc}", "ERROR")
            return False

    async def login(self) -> None:
        """Sign in to GameStop using GAMESTOP_EMAIL / GAMESTOP_PASSWORD env vars (SEC-01)."""
        # SEC-01: credentials from env vars only -- never from config.yml or hardcoded.
        email = os.environ.get("GAMESTOP_EMAIL", "")
        password = os.environ.get("GAMESTOP_PASSWORD", "")
        # Guard: if credentials are missing, log and abort (never log their values).
        if not email or not password:
            writeLog("GAMESTOP_EMAIL or GAMESTOP_PASSWORD not set -- skipping login", "ERROR")
            return

        try:
            tab = await self.driver.get("https://www.gamestop.com/login")
            # TODO: verify selectors against live gamestop.com login page
            email_field = await tab.select('input[id="login-form-email"]', timeout=10)
            if email_field:
                await email_field.send_keys(email)

            password_field = await tab.select('input[id="login-form-password"]', timeout=10)
            if password_field:
                await password_field.send_keys(password)

            sign_in_btn = await tab.select('button[data-action="submit"]', timeout=10)
            if sign_in_btn:
                await sign_in_btn.click()

            writeLog("Signed in to GameStop", "INFO")
        except Exception as exc:
            writeLog(f"Error during GameStop sign-in: {exc}", "ERROR")

    async def auto_buy(self, url: str) -> bool:
        """Attempt to purchase the item at url. Returns True on success.

        WARNING: GameStop checkout may be blocked by CAPTCHA. Auto-buy will likely
        fail at the checkout stage without a CAPTCHA solver integration.

        ASYNC-05: does NOT call update_item_purchased directly. The orchestrator's
        write queue owns the sole write path; auto_buy returns True on success and
        the orchestrator enqueues the DB write.
        """
        writeLog(
            "experimental: GameStop auto_buy may be blocked by checkout CAPTCHA",
            "WARNING",
        )
        writeLog(f"Entering auto_buy for GameStop: {url}", "DEBUG")
        try:
            tab = await self.driver.get(url)

            # TODO: verify selectors against live gamestop.com
            add_to_cart = await tab.select('[value="Add to Cart"]', timeout=10)
            if not add_to_cart:
                add_to_cart = await tab.find("Add to Cart", timeout=5)
            if not add_to_cart:
                writeLog("Add-to-cart button not found on GameStop", "ERROR")
                return False
            await add_to_cart.click()
            writeLog("Added to cart on GameStop", "INFO")

            # TODO: verify cart URL and checkout selectors against live gamestop.com
            tab = await self.driver.get("https://www.gamestop.com/cart")

            checkout_btn = await tab.select('a.checkout-btn', timeout=10)
            if not checkout_btn:
                writeLog("Checkout button not found on GameStop", "ERROR")
                return False
            await checkout_btn.click()
            writeLog("Proceeded to checkout on GameStop", "INFO")

            await self.login()

            # TODO: verify place order selector against live gamestop.com
            # NOTE: CAPTCHA may appear here and block the order.
            place_order = await tab.select('button.place-order', timeout=10)
            if not place_order:
                writeLog("Place order button not found on GameStop (CAPTCHA may have blocked)", "ERROR")
                return False
            await place_order.click()
            writeLog("Order placed on GameStop", "SUCCESS")
            # ASYNC-05: return True; orchestrator enqueues write_queue.put(url).
            return True
        except Exception as exc:
            writeLog(f"Error during GameStop auto-buy: {exc}", "ERROR")
            return False
