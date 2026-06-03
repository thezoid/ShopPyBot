"""BestBuy retailer plugin for ShopPyBot.

Credentials are sourced exclusively from environment variables (SEC-01):
    BB_EMAIL    -- BestBuy account email
    BB_PASSWORD -- BestBuy account password

The CVV is threaded via self._cvv, set by main.py after setup() is called (SEC-02).
Neither credentials nor CVV are ever logged, stored to disk, or written to config.yml.

ASYNC-05: auto_buy returns True on success without calling update_item_purchased
directly. The orchestrator's write queue owns the sole write path.
"""

import os

import nodriver

from core.plugin_base import RetailerPlugin
from logger import writeLog


class BestBuyPlugin(RetailerPlugin):
    """BestBuy platform plugin; owns one isolated nodriver Browser process.

    CVV threading contract (for Plan 05 / main.py):
        After registry.setup_for_items(), main.py must assign:
            plugin._cvv = cvv
        where cvv is the value collected via getpass before asyncio.run().
        _cvv defaults to None; auto_buy guards on it before sending keys.
    """

    domain_patterns = ["bestbuy.com"]

    def __init__(self, config) -> None:
        super().__init__(config)
        # SEC-02: CVV sourced at runtime via getpass in main.py; threaded here.
        # main.py sets plugin._cvv = cvv after setup_for_items(). Never logged.
        self._cvv = None

    async def setup(self) -> None:
        # nodriver.start() MUST be awaited from async context.
        # Browser.__init__ raises RuntimeError if no running event loop, so
        # this can never be called in __init__ (see RESEARCH.md Pitfall 1).
        # SC3: headless flag is config-driven; read from config.platforms.bestbuy.headless.
        # Defaults to True (headless) when self.config is None or the attribute is absent.
        headless = True
        if self.config:
            platform_cfg = getattr(getattr(self.config, "platforms", None), "bestbuy", None)
            if platform_cfg is not None:
                headless = getattr(platform_cfg, "headless", True)
        self.driver = await nodriver.start(headless=headless)

    async def teardown(self) -> None:
        if self.driver:
            # Browser.stop() is synchronous; handles subprocess termination
            # and missing-connection edge cases internally (RESEARCH Pattern 7).
            self.driver.stop()
            self.driver = None

    async def check_availability(self, url: str) -> bool:
        """Return True if the item at url has an add-to-cart button."""
        writeLog(f"Checking BestBuy availability: {url}", "DEBUG")
        try:
            tab = await self.driver.get(url)
            writeLog("Waiting for add-to-cart button", "DEBUG")
            add_to_cart = await tab.select(".add-to-cart-button", timeout=10)
            if add_to_cart:
                writeLog("Add-to-cart button found", "INFO")
                writeLog("Item is available on BestBuy", "SUCCESS")
                return True
            writeLog("Add-to-cart button not found", "INFO")
            writeLog("Item is not available on BestBuy", "INFO")
            return False
        except Exception as exc:
            writeLog(f"Error checking BestBuy item: {exc}", "ERROR")
            return False

    async def login(self) -> None:
        """Sign in to BestBuy using BB_EMAIL / BB_PASSWORD env vars (SEC-01)."""
        # SEC-01: credentials from env vars only -- never from config.yml or hardcoded.
        email = os.environ.get("BB_EMAIL", "")
        password = os.environ.get("BB_PASSWORD", "")
        # Guard: if credentials are missing, log and abort (never log their values).
        if not email or not password:
            writeLog("BB_EMAIL or BB_PASSWORD not set -- skipping login", "ERROR")
            return

        try:
            tab = await self.driver.get("https://www.bestbuy.com/identity/signin")

            email_field = await tab.select("#fld-e", timeout=10)
            if email_field:
                await email_field.send_keys(email)

            pwd_field = await tab.select("#fld-p1", timeout=10)
            if pwd_field:
                await pwd_field.send_keys(password)

            submit = await tab.select(".cia-form__controls__submit", timeout=10)
            if submit:
                await submit.click()

            writeLog("Signed in to BestBuy", "INFO")
        except Exception as exc:
            writeLog(f"Error during BestBuy sign-in: {exc}", "ERROR")

    async def auto_buy(self, url: str) -> bool:
        """Attempt to purchase the item at url. Returns True on success.

        ASYNC-05: does NOT call update_item_purchased directly. The orchestrator's
        write queue owns the sole write path; auto_buy returns True on success and
        the orchestrator enqueues the DB write.
        """
        writeLog(f"Entering auto_buy for BestBuy: {url}", "DEBUG")
        try:
            tab = await self.driver.get(url)

            add_to_cart = await tab.select(".add-to-cart-button", timeout=10)
            if not add_to_cart:
                writeLog("Add-to-cart button not found", "ERROR")
                return False
            await add_to_cart.click()
            writeLog("Added to cart on BestBuy", "INFO")

            tab = await self.driver.get("https://www.bestbuy.com/cart")

            # TODO: verify ".a-dropdown-prompt" is correct for BestBuy cart
            # (Open Question 2 -- suspicious Amazon-prefix class name, ports as-is
            # from bestbuy_bot.py which was validated in Phase-1 UAT).
            qty_dropdown = await tab.select(".a-dropdown-prompt", timeout=10)
            if qty_dropdown:
                await qty_dropdown.click()

            # Resolve quantity from config items by matching url; default to 1.
            quantity = 1
            if self.config and hasattr(self.config, "available"):
                for item in self.config.available.items:
                    if item.link == url:
                        quantity = item.quantity
                        break

            # BestBuy quantity selector: #quantity_{n} (not n-1 like Amazon).
            qty_option = await tab.select(f"#quantity_{quantity}", timeout=10)
            if qty_option:
                await qty_option.click()

            checkout = await tab.select(".checkout-buttons__checkout", timeout=10)
            if not checkout:
                writeLog("Checkout button not found", "ERROR")
                return False
            await checkout.click()
            writeLog("Proceeded to checkout on BestBuy", "INFO")

            await self.login()

            cvv_field = await tab.select("#credit-card-cvv", timeout=10)
            if cvv_field and self._cvv:
                # SEC-02: CVV sourced from self._cvv (set by main.py via getpass).
                # Never logged or written to disk.
                await cvv_field.send_keys(self._cvv)

            place_order = await tab.select(".button--place-order", timeout=10)
            if not place_order:
                writeLog("Place order button not found", "ERROR")
                return False
            await place_order.click()
            writeLog("Order placed on BestBuy", "SUCCESS")
            # ASYNC-05: return True; orchestrator enqueues write_queue.put(url).
            return True
        except Exception as exc:
            writeLog(f"Error during BestBuy auto-buy: {exc}", "ERROR")
            return False
