"""BestBuy retailer plugin (PLG-02, PLG-03).

Migrated from bestbuy_bot.py per Phase 2 CONTEXT.md D-02. Plan 02-04 will
delete bestbuy_bot.py and wire main.py through the registry. Until then both
modules coexist so wave-1 plans can land in parallel.

PLG-02 fix: legacy bestbuy_bot.auto_buy_bestbuy_item did not call
update_item_purchased() after a successful order, so the bot would attempt
to re-buy the item every polling cycle. This implementation calls
update_item_purchased(url) immediately after the place-order click on the
success branch (_place_order).
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from driver import build_driver
from logger import writeLog
from models import update_item_purchased
from plugin_base import RetailerPlugin


SIGNIN_URL = "https://www.bestbuy.com/identity/signin"
CART_URL = "https://www.bestbuy.com/cart"


class BestBuyPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["bestbuy.com"]
    login_at_startup: bool = True
    name: str = "bestbuy"

    def __init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None):
        super().__init__(platform_config)
        self.cvv = cvv
        self._user_agents = user_agents
        self.driver = build_driver(
            driver_path or "chromedriver.exe",
            headless=getattr(platform_config, "headless", False),
            user_agents=user_agents,
        )

    def check_availability(self, url: str) -> bool:
        writeLog(f"Entering check_availability for URL: {url}", "DEBUG")
        try:
            self.driver.get(url)
            writeLog("Waiting for add-to-cart button", "DEBUG")
            button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CLASS_NAME, "add-to-cart-button")
                )
            )
            if button:
                writeLog("Item is available on BestBuy", "SUCCESS")
                return True
            writeLog("Item is not available on BestBuy", "INFO")
            return False
        except Exception as e:
            writeLog(f"Error checking BestBuy item: {e}", "ERROR")
            return False

    def login(self, config) -> None:
        writeLog("Entering BestBuyPlugin.login", "DEBUG")
        try:
            email = self.platform_config.credentials.email
            password = self.platform_config.credentials.password
            self.driver.get(SIGNIN_URL)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "fld-e"))
            ).send_keys(email)
            self.driver.find_element(By.ID, "fld-p1").send_keys(password)
            self.driver.find_element(
                By.CLASS_NAME, "cia-form__controls__submit"
            ).click()
            writeLog("Signed in to BestBuy", "INFO")
        except Exception as e:
            writeLog(f"Error during BestBuy sign-in: {e}", "ERROR")

    def auto_buy(self, url: str, config) -> bool:
        writeLog(f"Entering auto_buy for URL: {url}", "DEBUG")
        quantity = self._lookup_quantity(url, config)
        test_mode = bool(config.debug.test_mode)
        try:
            self._add_to_cart(url)
            self._set_cart_quantity(quantity)
            self._proceed_to_checkout()
            self.login(config)
            self._enter_cvv()
            return self._place_order(url, test_mode)
        except Exception as e:
            writeLog(f"Error during BestBuy auto-buy: {e}", "ERROR")
            return False

    def _lookup_quantity(self, url: str, config) -> int:
        for item in config.available.items:
            if item.link == url:
                return int(item.quantity)
        writeLog(
            f"No item entry found for {url}; defaulting quantity to 1",
            "WARNING",
        )
        return 1

    def _add_to_cart(self, url: str) -> None:
        self.driver.get(url)
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located(
                (By.CLASS_NAME, "add-to-cart-button")
            )
        ).click()
        writeLog("Added to cart on BestBuy", "INFO")

    def _set_cart_quantity(self, quantity: int) -> None:
        self.driver.get(CART_URL)
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located(
                (By.CLASS_NAME, "a-dropdown-prompt")
            )
        ).click()
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, f"//a[@id='quantity_{quantity}']")
            )
        ).click()

    def _proceed_to_checkout(self) -> None:
        self.driver.find_element(
            By.CLASS_NAME, "checkout-buttons__checkout"
        ).click()
        writeLog("Proceeded to checkout on BestBuy", "INFO")

    def _enter_cvv(self) -> None:
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "credit-card-cvv"))
        ).send_keys(self.cvv or "")

    def _place_order(self, url: str, test_mode: bool) -> bool:
        if test_mode:
            writeLog(
                "Test mode active: Skipping final place-order click on BestBuy",
                "INFO",
            )
            return False
        self.driver.find_element(
            By.CLASS_NAME, "button--place-order"
        ).click()
        writeLog("Order placed on BestBuy", "SUCCESS")
        update_item_purchased(url)  # PLG-02 fix
        return True
