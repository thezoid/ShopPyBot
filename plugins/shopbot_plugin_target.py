"""Target retailer plugin for ShopPyBot.

Anti-detection risk: HIGH (experimental checkout)
Protection: Akamai Bot Manager
Reason: Target deploys Akamai Bot Manager which detects headless Chromium with ~80%
accuracy. Running in non-headless mode may intermittently succeed for availability
checks, but auto_buy (checkout) is experimental and frequently blocked by Akamai.

Credentials are sourced exclusively from environment variables (SEC-01):
    TARGET_EMAIL    -- Target account email
    TARGET_PASSWORD -- Target account password

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


class TargetPlugin(RetailerPlugin):
    """Target platform plugin; owns one isolated nodriver Browser process.

    Anti-detection risk: HIGH -- Akamai Bot Manager (PLG-05).
    Availability check may succeed in non-headless mode; auto_buy is experimental
    and labeled as such because Akamai consistently blocks headless checkout flows.
    UA rotation (ANTI-02) and per-platform headless toggle (ANTI-03) are applied
    in setup() but do not guarantee evasion of Akamai Bot Manager.
    """

    domain_patterns = ["target.com"]
    platform_key = "target"  # matches config.platforms.target

    async def setup(self) -> None:
        """Launch nodriver browser with ANTI-02 UA rotation and ANTI-03 headless toggle.

        Reads config.platforms.target.headless (ANTI-03) and user_agents (ANTI-02).
        Falls back to headless=True and DEFAULT_USER_AGENTS when config is absent.
        """
        # Fail loudly if proxy required but pool is exhausted (T-13-10, Pitfall 2).
        if getattr(self, "_proxy_required", False) and getattr(self, "_proxy", None) is None:
            writeLog("Proxy enabled but pool exhausted -- refusing direct launch", "ERROR")
            raise RuntimeError("TargetPlugin: proxy pool exhausted; cannot launch")

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
        writeLog(f"Checking Target availability: {url}", "DEBUG")
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
            # TODO: verify selectors against live target.com
            # Reported "Add to Cart" button on Target product pages (ASSUMED):
            add_to_cart = await tab.select('[data-test="shipItButton"]', timeout=10)
            if add_to_cart:
                writeLog("Ship-it button found on Target", "INFO")
                writeLog("Item is available on Target", "SUCCESS")
                return True
            # Alternate selector (ASSUMED):
            add_to_cart_alt = await tab.select('[data-test="addToCartButton"]', timeout=10)
            if add_to_cart_alt:
                writeLog("Add-to-cart button found on Target", "INFO")
                return True
            writeLog("Add-to-cart button not found on Target", "INFO")
            return False
        except Exception as exc:
            writeLog(f"Error checking Target item: {exc.__class__.__name__}", "ERROR")
            return False

    async def login(self) -> bool:
        """Sign in to Target using TARGET_EMAIL / TARGET_PASSWORD env vars (SEC-01).

        Returns True only after _verify_login_generic confirms the post-submit
        URL/DOM signal (D-12); missing creds, an exception, or an unconfirmed
        signal all return False (D-13).
        """
        # SEC-01: credentials from credential store only -- never from config.yml or hardcoded.
        store = get_store()
        email = store.get("TARGET_EMAIL") or ""
        password = store.get("TARGET_PASSWORD") or ""
        # Guard: if credentials are missing, log and abort (never log their values).
        if not email or not password:
            writeLog("TARGET_EMAIL or TARGET_PASSWORD not set -- skipping login", "ERROR")
            return False

        try:
            tab = await self.driver.get("https://www.target.com/account/signin")
            # TODO: verify selectors against live target.com login page
            email_field = await tab.select('[data-test="accountNav-signIn"] input[type="email"]', timeout=10)
            if email_field:
                await email_field.send_keys(email)

            password_field = await tab.select('input[type="password"]', timeout=10)
            if password_field:
                await password_field.send_keys(password)

            sign_in_btn = await tab.select('[data-test="signInSubmit"]', timeout=10)
            if sign_in_btn:
                await sign_in_btn.click()

            writeLog("Signed in to Target", "INFO")
            verified = await self._verify_login_generic(
                tab, "/account/signin", '[data-test="accountNav-signIn"] input[type="email"]'
            )
            if not verified:
                writeLog("Target login verification failed", "WARNING")
                return False
            return True
        except Exception as exc:
            writeLog(f"Error during Target sign-in: {exc.__class__.__name__}", "ERROR")
            return False

    async def auto_buy(self, url: str) -> bool:
        """Attempt to purchase the item at url. Returns True on success.

        EXPERIMENTAL: Target checkout is frequently blocked by Akamai Bot Manager.
        This method is labeled experimental and may fail even in non-headless mode.

        ASYNC-05: does NOT call update_item_purchased directly. The orchestrator's
        write queue owns the sole write path; auto_buy returns True on success and
        the orchestrator enqueues the DB write.
        """
        writeLog(
            "experimental: Target auto_buy may be blocked by Akamai Bot Manager",
            "WARNING",
        )
        writeLog(f"Entering auto_buy for Target: {url}", "DEBUG")
        try:
            tab = await self.driver.get(url)

            # TODO: verify selectors against live target.com
            add_to_cart = await tab.select('[data-test="shipItButton"]', timeout=10)
            if not add_to_cart:
                add_to_cart = await tab.select('[data-test="addToCartButton"]', timeout=10)
            if not add_to_cart:
                writeLog("Add-to-cart button not found on Target", "ERROR")
                return False
            await add_to_cart.click()
            writeLog("Added to cart on Target", "INFO")

            # TODO: verify cart URL and checkout selectors against live target.com
            tab = await self.driver.get("https://www.target.com/cart")

            checkout_btn = await tab.select('[data-test="checkout"]', timeout=10)
            if not checkout_btn:
                writeLog("Checkout button not found on Target", "ERROR")
                return False
            await checkout_btn.click()
            writeLog("Proceeded to checkout on Target", "INFO")

            self._checkout_stage = "login"
            login_ok = await self.login()
            if not login_ok:
                writeLog("Target login failed during auto_buy -- aborting checkout", "ERROR")
                return False

            # TODO: verify place order selector against live target.com
            place_order = await tab.select('[data-test="placeOrder"]', timeout=10)
            if not place_order:
                writeLog("Place order button not found on Target", "ERROR")
                return False
            return await self.place_order_guarded(place_order.click)
        except Exception as exc:
            writeLog(f"Error during Target auto-buy: {exc.__class__.__name__}", "ERROR")
            return False
