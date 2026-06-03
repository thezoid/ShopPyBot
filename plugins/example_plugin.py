"""Example plugin for a fictional retailer -- copy this file as your starting point.

To build a real plugin:
  1. Rename this file to shopbot_plugin_<yourplatform>.py (required for discovery).
  2. Replace FakeShopPlugin with a class name matching your platform.
  3. Update domain_patterns with the hostname substrings for your retailer.
  4. Implement check_availability and auto_buy with real CSS selectors.
  5. Run the test suite to confirm your plugin satisfies the ABC.

See plugins/PLUGIN_DEV.md for the full contributor guide.

NOTE: This file is intentionally named example_plugin.py (not shopbot_plugin_*.py)
so the registry ignores it as a template and does not try to load it at runtime.
"""

import nodriver

from core.plugin_base import RetailerPlugin
from logger import writeLog
from models import update_item_purchased


class FakeShopPlugin(RetailerPlugin):
    """Skeleton plugin for a fictional retailer (FakeShop).

    Copy this class verbatim into your shopbot_plugin_<name>.py and replace
    the FakeShop-specific parts with your target retailer's selectors and URLs.
    All methods are async; that is required by the v2 RetailerPlugin ABC.
    """

    # domain_patterns: list of substrings matched against urlparse(url).hostname.
    # The registry routes any URL whose hostname contains one of these strings
    # to this plugin. Add more entries for multi-region domains:
    #   e.g. ["fakeshop.com", "fakeshop.co.uk", "fakeshop.ca"]
    domain_patterns = ["fakeshop.com"]

    async def setup(self) -> None:
        """Start an isolated Chrome process for this plugin.

        nodriver.start() MUST be called from an async context -- never in __init__.
        Browser.__init__ raises RuntimeError if no running event loop (RESEARCH Pitfall 1).
        The registry awaits setup() after asyncio.run() has started the event loop.
        """
        self.driver = await nodriver.start(headless=False)

    async def check_availability(self, url: str) -> bool:
        """Return True if the item at url is in stock and purchasable.

        tab.select() returns None if the element is not found within the timeout;
        it never raises. Checking 'element is not None' is the correct idiom.
        """
        try:
            # Navigate to the product page; always get a fresh Tab reference.
            tab = await self.driver.get(url)

            # Replace "#add-to-cart" with the real CSS selector for this retailer's
            # add-to-cart (or buy-now) button.
            # ID selector:    "#add-to-cart-button"   (translates from By.ID "add-to-cart-button")
            # Class selector: ".add-to-cart-button"   (translates from By.CLASS_NAME)
            element = await tab.select("#add-to-cart", timeout=10)

            # None means the button was not found within the timeout (item unavailable).
            return element is not None
        except Exception as exc:
            writeLog(f"FakeShop check_availability error: {exc}", "ERROR")
            return False

    async def auto_buy(self, url: str) -> bool:
        """Attempt to purchase the item at url. Return True on success.

        The general flow for most retailers:
          1. Navigate to the product page.
          2. Click the add-to-cart button.
          3. Navigate to the checkout page.
          4. Click the place-order button.
          5. Call update_item_purchased(url) to mark the item as done in the DB.
          6. Return True.

        Always wrap the whole flow in try/except and return False on any failure
        so the bot keeps running for other items.
        """
        try:
            # Step 1: Navigate to the product page.
            tab = await self.driver.get(url)

            # Step 2: Add to cart. Guard against None before calling .click().
            add_btn = await tab.select("#add-to-cart", timeout=10)
            if not add_btn:
                # Log the failure so the operator can see which selector to fix.
                writeLog("FakeShop: add-to-cart button not found", "ERROR")
                return False
            await add_btn.click()

            # Step 3: Navigate to the checkout page.
            # Replace with the real checkout URL for your retailer.
            tab = await self.driver.get("https://www.fakeshop.com/checkout")

            # Step 4: Place the order.
            place_btn = await tab.select("#place-order", timeout=10)
            if not place_btn:
                writeLog("FakeShop: place-order button not found", "ERROR")
                return False
            await place_btn.click()

            writeLog("Order placed on FakeShop", "SUCCESS")

            # Step 5: Mark the item as purchased in the database so the bot does
            # not attempt to buy it again on the next loop iteration.
            # Always call this immediately after the place-order click succeeds.
            update_item_purchased(url)

            return True
        except Exception as exc:
            writeLog(f"FakeShop auto_buy error: {exc}", "ERROR")
            return False

    async def teardown(self) -> None:
        """Close the browser process owned by this plugin.

        Browser.stop() is synchronous; it terminates the Chrome subprocess and
        handles any missing-connection edge case internally (RESEARCH Pattern 7).
        """
        if self.driver:
            self.driver.stop()
            self.driver = None
