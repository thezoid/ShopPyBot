"""Square Enix retailer plugin for ShopPyBot.

Anti-detection risk: MEDIUM
Protection: Likely basic Cloudflare or OEM protection (no major vendor confirmed).
Reason: The Square Enix NA store (na.store.square-enix-games.com) is a lower-volume
retail site than Walmart or Target; bot detection is likely less aggressive than
PerimeterX or Akamai, but headless detection can still occur. UA rotation and
headless toggle reduce signal at the margins but do not guarantee evasion.

Credentials are sourced exclusively from environment variables (SEC-01):
    SQUAREENIX_EMAIL    -- Square Enix account email
    SQUAREENIX_PASSWORD -- Square Enix account password

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


class SquareEnixPlugin(RetailerPlugin):
    """Square Enix platform plugin; owns one isolated nodriver Browser process.

    Anti-detection risk: MEDIUM -- likely Cloudflare or OEM protection (PLG-07).
    UA rotation (ANTI-02) and per-platform headless toggle (ANTI-03) are applied
    in setup(). Selectors are best-effort and must be verified against the live site.
    """

    domain_patterns = ["store.square-enix-games.com"]
    # Broad substring covers na.store.square-enix-games.com, apac.store.*, etc.
    # NOTE: the NA store host is na.store.*, NOT store.na.* (RESEARCH Pitfall 1).
    platform_key = "squareenix"  # matches config.platforms.squareenix (no underscore)

    async def setup(self) -> None:
        """Launch nodriver browser with ANTI-02 UA rotation and ANTI-03 headless toggle.

        Reads config.platforms.squareenix.headless (ANTI-03) and user_agents (ANTI-02).
        Falls back to headless=True and DEFAULT_USER_AGENTS when config is absent.
        """
        # Fail loudly if proxy required but pool is exhausted (T-13-10, Pitfall 2).
        if getattr(self, "_proxy_required", False) and getattr(self, "_proxy", None) is None:
            writeLog("Proxy enabled but pool exhausted -- refusing direct launch", "ERROR")
            raise RuntimeError("SquareEnixPlugin: proxy pool exhausted; cannot launch")

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
        writeLog(f"Checking Square Enix availability: {url}", "DEBUG")
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
            # TODO: verify selectors against live na.store.square-enix-games.com
            # Generic e-commerce add-to-cart pattern (ASSUMED -- no authoritative source):
            add_to_cart = await tab.select('[name="add-to-cart"]', timeout=10)
            if add_to_cart:
                writeLog("Add-to-cart button found on Square Enix store", "INFO")
                writeLog("Item is available on Square Enix store", "SUCCESS")
                return True
            # Fallback: text-based search (ASSUMED)
            add_to_cart_text = await tab.find("Add to Cart", timeout=5)
            if add_to_cart_text:
                writeLog("Add-to-cart text found on Square Enix store", "INFO")
                return True
            writeLog("Add-to-cart button not found on Square Enix store", "INFO")
            return False
        except Exception as exc:
            writeLog(f"Error checking Square Enix item: {exc.__class__.__name__}", "ERROR")
            return False

    async def login(self) -> bool:
        """Sign in to Square Enix using SQUAREENIX_EMAIL / SQUAREENIX_PASSWORD env vars (SEC-01).

        Returns True only after _verify_login_generic confirms the post-submit
        URL/DOM signal (D-12); missing creds, an exception, or an unconfirmed
        signal all return False (D-13).
        """
        # SEC-01: credentials from credential store only -- never from config.yml or hardcoded.
        store = get_store()
        email = store.get("SQUAREENIX_EMAIL") or ""
        password = store.get("SQUAREENIX_PASSWORD") or ""
        # Guard: if credentials are missing, log and abort (never log their values).
        if not email or not password:
            writeLog(
                "SQUAREENIX_EMAIL or SQUAREENIX_PASSWORD not set -- skipping login",
                "ERROR",
            )
            return False

        try:
            tab = await self.driver.get("https://na.store.square-enix-games.com/account/login")
            # TODO: verify selectors against live na.store.square-enix-games.com login page
            email_field = await tab.select('[type="email"]', timeout=10)
            if email_field:
                await email_field.send_keys(email)

            password_field = await tab.select('[type="password"]', timeout=10)
            if password_field:
                await password_field.send_keys(password)

            sign_in_btn = await tab.select('[type="submit"]', timeout=10)
            if sign_in_btn:
                await sign_in_btn.click()

            writeLog("Signed in to Square Enix store", "INFO")
            verified = await self._verify_login_generic(tab, "/account/login", '[type="email"]')
            if not verified:
                writeLog("Square Enix login verification failed", "WARNING")
                return False
            return True
        except Exception as exc:
            writeLog(f"Error during Square Enix sign-in: {exc.__class__.__name__}", "ERROR")
            return False

    async def auto_buy(self, url: str) -> bool:
        """Attempt to purchase the item at url. Returns True on success.

        ASYNC-05: does NOT call update_item_purchased directly. The orchestrator's
        write queue owns the sole write path; auto_buy returns True on success and
        the orchestrator enqueues the DB write.

        NOTE: Square Enix store has MEDIUM anti-detection risk; auto-buy may be
        interrupted by bot detection or login challenges.
        """
        writeLog(
            "experimental: Square Enix auto_buy may be blocked by site protection",
            "WARNING",
        )
        writeLog(f"Entering auto_buy for Square Enix: {url}", "DEBUG")
        try:
            tab = await self.driver.get(url)

            # TODO: verify selectors against live na.store.square-enix-games.com
            add_to_cart = await tab.select('[name="add-to-cart"]', timeout=10)
            if not add_to_cart:
                add_to_cart = await tab.find("Add to Cart", timeout=5)
            if not add_to_cart:
                writeLog("Add-to-cart button not found on Square Enix store", "ERROR")
                return False
            await add_to_cart.click()
            writeLog("Added to cart on Square Enix store", "INFO")

            # TODO: verify cart URL and checkout selectors against live na.store.square-enix-games.com
            tab = await self.driver.get("https://na.store.square-enix-games.com/cart")

            checkout_btn = await tab.select('[data-testid="checkout-button"]', timeout=10)
            if not checkout_btn:
                checkout_btn = await tab.find("Checkout", timeout=5)
            if not checkout_btn:
                writeLog("Checkout button not found on Square Enix store", "ERROR")
                return False
            await checkout_btn.click()
            writeLog("Proceeded to checkout on Square Enix store", "INFO")

            self._checkout_stage = "login"
            login_ok = await self.login()
            if not login_ok:
                writeLog("Square Enix login failed during auto_buy -- aborting checkout", "ERROR")
                return False

            # TODO: verify place order selector against live na.store.square-enix-games.com
            place_order = await tab.select('[data-testid="place-order-button"]', timeout=10)
            if not place_order:
                place_order = await tab.find("Place Order", timeout=5)
            if not place_order:
                writeLog("Place order button not found on Square Enix store", "ERROR")
                return False
            return await self.place_order_guarded(place_order.click)
        except Exception as exc:
            writeLog(f"Error during Square Enix auto-buy: {exc.__class__.__name__}", "ERROR")
            return False
