"""Walmart retailer plugin for ShopPyBot.

Anti-detection risk: HIGH
Protection: PerimeterX/HUMAN Security (Bot Defender)
Reason: Walmart deploys PerimeterX/HUMAN Security which scores 2,500+ behavioral
signals per request; headless detection without spoofing is near-certain. Auto-buy
will likely be blocked. Availability check may succeed briefly with a UA override.

Credentials are sourced exclusively from environment variables (SEC-01):
    WALMART_EMAIL    -- Walmart account email
    WALMART_PASSWORD -- Walmart account password

ASYNC-05: auto_buy returns True on success without calling update_item_purchased
directly. The orchestrator's write queue owns the sole write path.
"""

import random

import nodriver

from core.credentials import get_store

from core.config_schema import DEFAULT_USER_AGENTS
from core.plugin_base import RetailerPlugin
from core.stealth import apply_stealth, build_proxy_browser_args, setup_proxy_auth
from logger import writeLog


class WalmartPlugin(RetailerPlugin):
    """Walmart platform plugin; owns one isolated nodriver Browser process.

    Anti-detection risk: HIGH -- PerimeterX/HUMAN Security (PLG-04).
    UA rotation (ANTI-02) and per-platform headless toggle (ANTI-03) are applied
    in setup(), but do not guarantee evasion of PerimeterX/HUMAN Security.
    """

    domain_patterns = ["walmart.com"]
    platform_key = "walmart"  # matches config.platforms.walmart

    async def setup(self) -> None:
        """Launch nodriver browser with ANTI-02 UA rotation and ANTI-03 headless toggle.

        Reads config.platforms.walmart.headless (ANTI-03) and user_agents (ANTI-02).
        Falls back to headless=True and DEFAULT_USER_AGENTS when config is absent.
        """
        # Fail loudly if proxy required but pool is exhausted (T-13-10, Pitfall 2).
        if getattr(self, "_proxy_required", False) and getattr(self, "_proxy", None) is None:
            writeLog("Proxy enabled but pool exhausted -- refusing direct launch", "ERROR")
            raise RuntimeError("WalmartPlugin: proxy pool exhausted; cannot launch")

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

        # ANTI-04: merge proxy + WebRTC args ([] when proxy disabled).
        browser_args = browser_args + build_proxy_browser_args(getattr(self, "_proxy", None))

        # ANTI-03: per-platform headless toggle; nodriver.Config appends --headless=new when True.
        # NOTE: never pass "--headless" via browser_args -- nodriver raises ValueError.
        self.driver = await nodriver.start(headless=headless, browser_args=browser_args)

        # ANTI-08: apply stealth BEFORE first navigation (Pitfall 8).
        await apply_stealth(self.driver.main_tab)

        # Authenticated proxy: register CDP Fetch handlers (Pitfall 4+5).
        proxy = getattr(self, "_proxy", None)
        if proxy and proxy.username:
            await setup_proxy_auth(self.driver.main_tab, proxy.username, proxy.password)

    async def teardown(self) -> None:
        if self.driver:
            self.driver.stop()
            self.driver = None

    async def check_availability(self, url: str) -> bool:
        """Return True if the item at url has an add-to-cart button."""
        writeLog(f"Checking Walmart availability: {url}", "DEBUG")
        try:
            tab = await self.driver.get(url)
            # ANTI-05 / CR-02: scan for ban page before checking availability selectors.
            body_text = ""
            try:
                body_text = await tab.evaluate("document.body.innerText") or ""
            except Exception:
                pass
            if self._handle_ban(body_text):
                return False
            # TODO: verify selectors against live walmart.com
            # Reported "Add to Cart" button on Walmart product pages (ASSUMED):
            add_to_cart = await tab.select('[data-testid="add-to-cart-btn"]', timeout=10)
            if add_to_cart:
                writeLog("Add-to-cart button found on Walmart", "INFO")
                writeLog("Item is available on Walmart", "SUCCESS")
                return True
            # Fallback: text-based search (ASSUMED)
            add_to_cart_text = await tab.find("Add to cart", timeout=5)
            if add_to_cart_text:
                writeLog("Add-to-cart text found on Walmart", "INFO")
                return True
            writeLog("Add-to-cart button not found on Walmart", "INFO")
            return False
        except Exception as exc:
            writeLog(f"Error checking Walmart item: {exc.__class__.__name__}", "ERROR")
            return False

    async def login(self) -> None:
        """Sign in to Walmart using WALMART_EMAIL / WALMART_PASSWORD env vars (SEC-01)."""
        # SEC-01: credentials from credential store only -- never from config.yml or hardcoded.
        store = get_store()
        email = store.get("WALMART_EMAIL") or ""
        password = store.get("WALMART_PASSWORD") or ""
        # Guard: if credentials are missing, log and abort (never log their values).
        if not email or not password:
            writeLog("WALMART_EMAIL or WALMART_PASSWORD not set -- skipping login", "ERROR")
            return

        try:
            tab = await self.driver.get("https://www.walmart.com/account/login")
            # TODO: verify selectors against live walmart.com login page
            email_field = await tab.select("#email", timeout=10)
            if email_field:
                await email_field.send_keys(email)

            password_field = await tab.select("#password", timeout=10)
            if password_field:
                await password_field.send_keys(password)

            sign_in_btn = await tab.select('[data-testid="sign-in-form-submit"]', timeout=10)
            if sign_in_btn:
                await sign_in_btn.click()

            writeLog("Signed in to Walmart", "INFO")
        except Exception as exc:
            writeLog(f"Error during Walmart sign-in: {exc.__class__.__name__}", "ERROR")

    async def auto_buy(self, url: str) -> bool:
        """Attempt to purchase the item at url. Returns True on success.

        ASYNC-05: does NOT call update_item_purchased directly. The orchestrator's
        write queue owns the sole write path; auto_buy returns True on success and
        the orchestrator enqueues the DB write.

        WARNING: Walmart is protected by PerimeterX/HUMAN Security. Auto-buy is
        experimental and will likely be blocked.
        """
        writeLog(
            "experimental: Walmart auto_buy may be blocked by PerimeterX/HUMAN Security",
            "WARNING",
        )
        writeLog(f"Entering auto_buy for Walmart: {url}", "DEBUG")
        try:
            tab = await self.driver.get(url)

            # TODO: verify selectors against live walmart.com
            add_to_cart = await tab.select('[data-testid="add-to-cart-btn"]', timeout=10)
            if not add_to_cart:
                add_to_cart = await tab.find("Add to cart", timeout=5)
            if not add_to_cart:
                writeLog("Add-to-cart button not found on Walmart", "ERROR")
                return False
            await add_to_cart.click()
            writeLog("Added to cart on Walmart", "INFO")

            # TODO: verify cart URL and checkout selectors against live walmart.com
            tab = await self.driver.get("https://www.walmart.com/cart")

            checkout_btn = await tab.select('[data-testid="cartCheckoutBtn"]', timeout=10)
            if not checkout_btn:
                writeLog("Checkout button not found on Walmart", "ERROR")
                return False
            await checkout_btn.click()
            writeLog("Proceeded to checkout on Walmart", "INFO")

            await self.login()

            # TODO: verify place order selector against live walmart.com
            place_order = await tab.select('[data-testid="place-order-button"]', timeout=10)
            if not place_order:
                writeLog("Place order button not found on Walmart", "ERROR")
                return False
            await place_order.click()
            writeLog("Order placed on Walmart", "SUCCESS")
            # ASYNC-05: return True; orchestrator enqueues write_queue.put(url).
            return True
        except Exception as exc:
            writeLog(f"Error during Walmart auto-buy: {exc.__class__.__name__}", "ERROR")
            return False
