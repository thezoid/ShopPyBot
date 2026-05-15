"""Amazon retailer plugin (PLG-01, PLG-03).

Migrated from amazon_bot.py per Phase 2 CONTEXT.md. Plan 02-04 will delete
amazon_bot.py and wire main.py through the registry. Until then both modules
coexist so wave-1 plans can land in parallel.
"""
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from driver import build_driver
from logger import writeLog
from models import update_item_purchased
from plugin_base import RetailerPlugin
from utils import play_notification_sound

AMAZON_SIGNIN_URL = (
    "https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0"
    "&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3Fref_%3Dnav_signin"
    "&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
    "&openid.assoc_handle=usflex&openid.mode=checkid_setup"
    "&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
    "&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
)

_CAPTCHA_XPATH = "//h4[contains(text(), 'Enter the characters you see below')]"


class AmazonPlugin(RetailerPlugin):
    domain_pattern: list[str] = ["amazon.com", "amzn.to"]
    login_at_startup: bool = True
    name: str = "amazon"

    def __init__(self, platform_config, *, cvv=None, driver_path=None, user_agents=None):
        super().__init__(platform_config)
        self.cvv = cvv
        # user_agents kwarg accepted for registry compat (Plan 06-07 wires it
        # through to build_driver). Currently ignored by Selenium plugins.
        self._user_agents = user_agents
        self.driver = build_driver(driver_path or "chromedriver.exe")

    def detect_captcha(self) -> bool:
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, _CAPTCHA_XPATH))
            )
            return True
        except Exception as e:
            writeLog(f"detect_captcha: no CAPTCHA element: {e}", "TRACE")
            return False

    def check_availability(self, url: str) -> bool:
        writeLog(f"Entering check_availability for URL: {url}", "DEBUG")
        try:
            if self.driver.current_url != url:
                self.driver.get(url)
            self._handle_captcha_if_present()
            add_btn = self._find_button("add-to-cart-button", "Add-to-cart")
            buy_btn = self._find_button("buy-now-button", "Buy-now")
            if add_btn or buy_btn:
                writeLog("Item is available on Amazon", "SUCCESS")
                return True
            writeLog("Item is not available on Amazon", "INFO")
            return False
        except Exception as e:
            writeLog(f"Error checking Amazon item: {e}", "ERROR")
            return False

    def _handle_captcha_if_present(self) -> None:
        if self.detect_captcha():
            writeLog("CAPTCHA detected. Please solve it manually.", "WARNING")
            try:
                self.driver.focus()
            except Exception as e:
                writeLog(f"driver.focus() unavailable: {e}", "TRACE")
            input("--------------------\nPress Enter after solving the CAPTCHA...\n--------------------\n")

    def _find_button(self, element_id: str, label: str):
        try:
            return WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, element_id))
            )
        except Exception as e:
            writeLog(f"Could not find {label} button (assume unavailable): {e}", "WARNING")
            return None

    def login(self, config) -> None:
        try:
            email = self.platform_config.credentials.email
            password = self.platform_config.credentials.password
            if self._already_signed_in():
                return
            writeLog("User is not signed in, proceeding with sign-in", "INFO")
            self.driver.get(AMAZON_SIGNIN_URL)
            self._enter_email(email)
            play_notification_sound()
            input("Press enter once you dismiss the passkey prompt...")
            self._enter_password(password)
            self._click_signin()
            self._handle_mfa()
            writeLog("Signed in to Amazon", "INFO")
        except Exception as e:
            writeLog(f"Error during Amazon sign-in: {e}", "ERROR")

    def _already_signed_in(self) -> bool:
        writeLog("Checking if user is already signed in", "INFO")
        try:
            account_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "nav-link-accountList"))
            )
            sign_in_button = account_element.find_element(
                By.CLASS_NAME, "nav-action-signin-button"
            )
            if sign_in_button:
                writeLog("User is not signed in", "INFO")
                return False
            writeLog("User is already signed in", "INFO")
            return True
        except Exception as e:
            writeLog(f"Error checking sign-in state: {e}", "ERROR")
            return False

    def _enter_email(self, email: str) -> None:
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "ap_email"))
            ).send_keys(email)
            self.driver.find_element(By.ID, "continue").click()
        except Exception as e:
            writeLog(f"Error during Amazon sign-in when entering email: {e}", "ERROR")
            raise Exception("Sign-in failed - failed to enter email")

    def _enter_password(self, password: str) -> None:
        try:
            writeLog("Attempting to enter password", "INFO")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "ap_password"))
            ).send_keys(password)
        except Exception as e:
            writeLog(f"Error during Amazon sign-in when entering password: {e}", "ERROR")
            raise Exception("Sign-in failed - failed to enter password")

    def _click_signin(self) -> None:
        try:
            writeLog("Attempting to click sign-in button", "INFO")
            self.driver.find_element(By.ID, "signInSubmit").click()
        except Exception as e:
            writeLog(f"Error during Amazon sign-in when clicking sign-in button: {e}", "ERROR")
            raise Exception("Sign-in failed")

    def _handle_mfa(self) -> None:
        try:
            writeLog("Checking for MFA prompt", "INFO")
            mfa_form = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "auth-mfa-form"))
            )
            if mfa_form:
                writeLog("MFA prompt detected. Please enter the OTP manually.", "WARNING")
                play_notification_sound()
                input("Press Enter after entering the OTP...")
        except Exception as e:
            writeLog(f"No MFA prompt detected: {e}", "WARNING")

    def auto_buy(self, url: str, config) -> bool:
        writeLog(f"Entering auto_buy for URL: {url}", "DEBUG")
        quantity = self._lookup_quantity(url, config)
        test_mode = bool(config.debug.test_mode)
        self.login(config)
        return self._purchase_flow(url, quantity, test_mode)

    def _lookup_quantity(self, url: str, config) -> int:
        for item in config.available.items:
            if item.link == url:
                return int(item.quantity)
        writeLog(f"No item entry found for {url}; defaulting quantity to 1", "WARNING")
        return 1

    def _purchase_flow(self, url: str, quantity: int, test_mode: bool) -> bool:
        try:
            if self.driver.current_url != url:
                self.driver.get(url)
            if not self._select_quantity(quantity):
                return False
            if test_mode:
                writeLog("Test mode active: Pausing before final purchase step", "DEBUG")
                input("Press Enter to continue...")
            if not self._click_buy_now():
                return False
            return self._place_order(url, test_mode)
        except Exception as e:
            writeLog(f"Error during Amazon auto-buy: {e}", "ERROR")
            return False

    def _select_quantity(self, quantity: int) -> bool:
        try:
            writeLog("Attempting to find quantity dropdown", "INFO")
            start = time.time()
            dropdown = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "a-button-dropdown"))
            )
            writeLog(f"Time to find quantity dropdown: {time.time() - start:.2f}s", "DEBUG")
            dropdown.click()
        except Exception as e:
            writeLog(f"Error finding quantity dropdown: {e}", "ERROR")
            return False
        try:
            writeLog(f"Attempting to find quantity option for {quantity}", "INFO")
            option = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, f"quantity_{quantity - 1}"))
            )
            option.click()
            return True
        except Exception as e:
            writeLog(f"Error finding quantity option: {e}", "ERROR")
            return False

    def _click_buy_now(self) -> bool:
        try:
            writeLog("Attempting to find buy-now button", "INFO")
            start = time.time()
            buy_btn = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "buy-now-button"))
            )
            writeLog(f"Time to find buy-now button: {time.time() - start:.2f}s", "DEBUG")
            buy_btn.click()
            return True
        except Exception as e:
            writeLog(f"Error finding buy-now button: {e}", "ERROR")
            return False

    def _place_order(self, url: str, test_mode: bool) -> bool:
        try:
            writeLog("Attempting to find place order button", "INFO")
            place_btn = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "submitOrderButtonId"))
            )
            if not test_mode:
                place_btn.click()
                writeLog("Order placed on Amazon", "SUCCESS")
                update_item_purchased(url)
                return True
            writeLog(
                "Test mode active: Skipping final purchase step, otherwise submitOrderButton would have been clicked!",
                "SUCCESS",
            )
            input("Press Enter to continue...")
            return False
        except Exception as e:
            writeLog(f"Error finding place order button: {e}", "ERROR")
            return False
