"""Example RetailerPlugin (CORE-08).

This file is intentionally NOT auto-loaded by the registry: its filename does
not start with `shopbot_plugin_`. To create a real plugin, copy this file to
`plugins/shopbot_plugin_<your_platform>.py` and edit the bodies.

The example demonstrates a check-only plugin against `httpbin.org/html`:
  * `domain_pattern: list[str]` (D-01)
  * `login_at_startup = False` (D-03 opt-out; uses inherited no-op login)
  * `self.driver` constructed in `__init__` via `build_driver` (PLG-03)
  * `check_availability` returning True/False from a DOM probe
  * `auto_buy` as an informational no-op returning False

See `plugins/PLUGIN_DEV.md` for the full contract reference. See
`plugins/shopbot_plugin_amazon.py` and `plugins/shopbot_plugin_bestbuy.py`
for real-world references.

Anti-patterns to avoid (see PLUGIN_DEV.md "Anti-patterns" section):
  * NEVER import the legacy config singleton (Phase 1 retired it)
  * NEVER build a shared module-level driver (open Chrome inside __init__)
  * NEVER pass a single string to domain_pattern; it is `list[str]`
  * NEVER call `update_item_purchased` from `check_availability`
"""
from selenium.webdriver.common.by import By

from driver import build_driver
from logger import writeLog
from plugin_base import RetailerPlugin


class ExamplePlugin(RetailerPlugin):
    # List of hostnames this plugin handles. The registry normalizes the URL
    # netloc (lowercase, port stripped) and matches with a subdomain-anchored
    # endswith check, so "httpbin.org" matches "www.httpbin.org" but NOT
    # "evilhttpbin.org".
    domain_pattern: list[str] = ["httpbin.org"]

    # No auth required for httpbin: leave login_at_startup False to inherit
    # the no-op login default. Real plugins that need a startup sign-in flow
    # set this to True and override .login(config).
    login_at_startup: bool = False

    # Optional class attribute. If omitted, the registry derives the name
    # from the filename stem (shopbot_plugin_<name>.py -> "<name>").
    name: str = "example"

    def __init__(self, platform_config, *, cvv=None, driver_path=None):
        # Always call super().__init__ first: it stores platform_config on
        # self.platform_config for downstream methods.
        super().__init__(platform_config)
        self.cvv = cvv
        # PLG-03: each plugin owns its WebDriver. build_driver is the locked
        # factory from Phase 1; do not construct webdriver.Chrome directly.
        self.driver = build_driver(driver_path or "chromedriver.exe")

    def check_availability(self, url: str) -> bool:
        """Return True if the page at `url` contains an <h1> tag.

        Demonstration of the contract: probe the DOM, log the result via
        writeLog (NOT print), and return a bool. Exceptions are caught and
        logged: the polling loop must never crash on a single failed check.
        """
        try:
            self.driver.get(url)
            elements = self.driver.find_elements(By.TAG_NAME, "h1")
            available = len(elements) > 0
            writeLog(
                f"Example plugin check_availability({url}) -> {available}",
                "DEBUG",
            )
            return available
        except Exception as e:
            writeLog(f"Example plugin error: {e}", "ERROR")
            return False

    def auto_buy(self, url: str, config) -> bool:
        """Check-only template: auto-buy is not implemented.

        Real plugins implement the purchase flow here and call
        `models.update_item_purchased(url)` after a confirmed order. Never
        call update_item_purchased from check_availability.
        """
        writeLog(
            "auto_buy not implemented for ExamplePlugin "
            "(this is a check-only template)",
            "INFO",
        )
        return False
