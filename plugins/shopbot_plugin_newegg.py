"""NewEgg retailer plugin for ShopPyBot.

Anti-detection risk: MEDIUM
Protection: Likely Cloudflare or lightweight protection (no major vendor confirmed).
Reason: NewEgg is known for tech/PC parts with moderate bot activity around GPU
drops historically. Headless detection can occur; UA rotation and headless toggle
reduce signal at the margins but do not guarantee evasion.

Credentials are sourced exclusively from environment variables (SEC-01):
    NEWEGG_EMAIL    -- NewEgg account email
    NEWEGG_PASSWORD -- NewEgg account password

ASYNC-05: auto_buy returns True on success without calling update_item_purchased
directly. The orchestrator's write queue owns the sole write path.
"""

import random

import nodriver

from core.credentials import get_store

from core.config_schema import DEFAULT_USER_AGENTS
from core.plugin_base import RetailerPlugin
from logger import writeLog


class NeweggPlugin(RetailerPlugin):
    """NewEgg platform plugin; owns one isolated nodriver Browser process.

    Anti-detection risk: MEDIUM -- likely Cloudflare or lightweight protection (PLG-08).
    UA rotation (ANTI-02) and per-platform headless toggle (ANTI-03) are applied
    in setup(). Selectors are best-effort and must be verified against the live site.
    Covers both newegg.com (US) and newegg.ca (Canada).
    """

    domain_patterns = ["newegg.com", "newegg.ca"]
    platform_key = "newegg"  # matches config.platforms.newegg

    async def setup(self) -> None:
        """Launch nodriver browser with ANTI-02 UA rotation and ANTI-03 headless toggle.

        Reads config.platforms.newegg.headless (ANTI-03) and user_agents (ANTI-02).
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
        if ua_list:
            ua = random.choice(ua_list)
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
        writeLog(f"Checking NewEgg availability: {url}", "DEBUG")
        try:
            tab = await self.driver.get(url)
            # TODO: verify selectors against live newegg.com
            # NewEgg known "Add to Cart" button (ASSUMED -- no authoritative selector source):
            add_to_cart = await tab.select(".btn-primary.btn-wide", timeout=10)
            if add_to_cart:
                writeLog("Add-to-cart button found on NewEgg", "INFO")
                writeLog("Item is available on NewEgg", "SUCCESS")
                return True
            # Fallback: availability itemprop (ASSUMED)
            avail_elem = await tab.select('[itemprop="availability"]', timeout=5)
            if avail_elem:
                writeLog("Availability element found on NewEgg", "INFO")
                return True
            # Fallback: text-based search (ASSUMED)
            add_to_cart_text = await tab.find("Add to Cart", timeout=5)
            if add_to_cart_text:
                writeLog("Add-to-cart text found on NewEgg", "INFO")
                return True
            writeLog("Add-to-cart button not found on NewEgg", "INFO")
            return False
        except Exception as exc:
            writeLog(f"Error checking NewEgg item: {exc}", "ERROR")
            return False

    async def login(self) -> None:
        """Sign in to NewEgg using NEWEGG_EMAIL / NEWEGG_PASSWORD env vars (SEC-01)."""
        # SEC-01: credentials from credential store only -- never from config.yml or hardcoded.
        store = get_store()
        email = store.get("NEWEGG_EMAIL") or ""
        password = store.get("NEWEGG_PASSWORD") or ""
        # Guard: if credentials are missing, log and abort (never log their values).
        if not email or not password:
            writeLog(
                "NEWEGG_EMAIL or NEWEGG_PASSWORD not set -- skipping login",
                "ERROR",
            )
            return

        try:
            tab = await self.driver.get("https://secure.newegg.com/identity/signin")
            # TODO: verify selectors against live newegg.com login page
            email_field = await tab.select("#labeled-input-signEmail", timeout=10)
            if email_field:
                await email_field.send_keys(email)

            sign_in_btn = await tab.select(".btn.btn-orange", timeout=10)
            if sign_in_btn:
                await sign_in_btn.click()

            password_field = await tab.select("#labeled-input-password", timeout=10)
            if password_field:
                await password_field.send_keys(password)

            submit_btn = await tab.select('[data-testid="sign-in-button"]', timeout=10)
            if not submit_btn:
                submit_btn = await tab.select(".btn.btn-orange", timeout=10)
            if submit_btn:
                await submit_btn.click()

            writeLog("Signed in to NewEgg", "INFO")
        except Exception as exc:
            writeLog(f"Error during NewEgg sign-in: {exc}", "ERROR")

    async def auto_buy(self, url: str) -> bool:
        """Attempt to purchase the item at url. Returns True on success.

        ASYNC-05: does NOT call update_item_purchased directly. The orchestrator's
        write queue owns the sole write path; auto_buy returns True on success and
        the orchestrator enqueues the DB write.

        NOTE: NewEgg has MEDIUM anti-detection risk; auto-buy may be interrupted
        by bot detection or login challenges.
        """
        writeLog(
            "experimental: NewEgg auto_buy may be blocked by site protection",
            "WARNING",
        )
        writeLog(f"Entering auto_buy for NewEgg: {url}", "DEBUG")
        try:
            tab = await self.driver.get(url)

            # TODO: verify selectors against live newegg.com
            add_to_cart = await tab.select(".btn-primary.btn-wide", timeout=10)
            if not add_to_cart:
                add_to_cart = await tab.find("Add to Cart", timeout=5)
            if not add_to_cart:
                writeLog("Add-to-cart button not found on NewEgg", "ERROR")
                return False
            await add_to_cart.click()
            writeLog("Added to cart on NewEgg", "INFO")

            # TODO: verify cart URL and checkout selectors against live newegg.com
            tab = await self.driver.get("https://secure.newegg.com/shop/cart")

            checkout_btn = await tab.select(".btn-primary.btn-wide", timeout=10)
            if not checkout_btn:
                checkout_btn = await tab.find("Secure Checkout", timeout=5)
            if not checkout_btn:
                writeLog("Checkout button not found on NewEgg", "ERROR")
                return False
            await checkout_btn.click()
            writeLog("Proceeded to checkout on NewEgg", "INFO")

            await self.login()

            # TODO: verify place order selector against live newegg.com
            place_order = await tab.select(".btn-primary.btn-wide", timeout=10)
            if not place_order:
                place_order = await tab.find("Place Order", timeout=5)
            if not place_order:
                writeLog("Place order button not found on NewEgg", "ERROR")
                return False
            await place_order.click()
            writeLog("Order placed on NewEgg", "SUCCESS")
            # ASYNC-05: return True; orchestrator enqueues write_queue.put(url).
            return True
        except Exception as exc:
            writeLog(f"Error during NewEgg auto-buy: {exc}", "ERROR")
            return False
