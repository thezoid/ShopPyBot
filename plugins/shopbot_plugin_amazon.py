"""Amazon retailer plugin for ShopPyBot.

Credentials are sourced exclusively from environment variables (SEC-01):
    AMZ_EMAIL    -- Amazon account email
    AMZ_PASSWORD -- Amazon account password

Neither value is ever logged, stored to disk, or written to config.yml.
"""

import asyncio
import os

import nodriver

from core.plugin_base import RetailerPlugin
from logger import writeLog
from utils import play_notification_sound


class AmazonPlugin(RetailerPlugin):
    """Amazon platform plugin; owns one isolated nodriver Browser process."""

    domain_patterns = ["amazon.com", "amazon.co.uk", "amazon.ca"]

    def __init__(self, config) -> None:
        super().__init__(config)
        # One Event per distinct intervention type (ASYNC-03).
        # asyncio.Event() is safe to create before loop start in Python 3.10+.
        self.captcha_event: asyncio.Event = asyncio.Event()
        self.passkey_event: asyncio.Event = asyncio.Event()
        self.otp_event: asyncio.Event = asyncio.Event()
        self.test_pause_event: asyncio.Event = asyncio.Event()

    async def _wait_user_action(self, event: asyncio.Event, message: str) -> None:
        """Notify user, await their Enter, clear the event for reuse (ASYNC-03).

        Plays alert sound and logs the message, then awaits the event with a
        5-minute unattended guard. On timeout, logs and continues. Always clears
        the event in finally so the next poll cycle genuinely re-waits (Pitfall 7).
        Security: never reads, echoes, or stores any typed text (T-04-13).
        """
        play_notification_sound()
        writeLog(message, "WARNING")
        try:
            await asyncio.wait_for(event.wait(), timeout=300)
        except asyncio.TimeoutError:
            writeLog(
                "User action timed out (300s) -- continuing without intervention",
                "WARNING",
            )
        finally:
            event.clear()

    async def setup(self) -> None:
        # nodriver.start() MUST be awaited from async context.
        # Browser.__init__ raises RuntimeError if no running event loop, so
        # this can never be called in __init__ (see RESEARCH.md Pitfall 1).
        self.driver = await nodriver.start(headless=False)

    async def teardown(self) -> None:
        if self.driver:
            # Browser.stop() is synchronous; it terminates the subprocess and
            # handles any missing-connection edge case internally (RESEARCH Pattern 7).
            self.driver.stop()
            self.driver = None

    async def detect_captcha(self) -> bool:
        """Return True if an Amazon CAPTCHA challenge page is present."""
        tab = self.driver.main_tab
        element = await tab.find(
            "Enter the characters you see below",
            best_match=False,
            timeout=3,  # short: absence is the common case
        )
        return element is not None

    async def check_availability(self, url: str) -> bool:
        """Return True if the item at url has an add-to-cart or buy-now button."""
        writeLog(f"Checking Amazon availability: {url}", "DEBUG")
        try:
            tab = await self.driver.get(url)

            captcha_present = await self.detect_captcha()
            if captcha_present:
                await self._wait_user_action(
                    self.captcha_event,
                    "CAPTCHA detected on Amazon. Solve it in the browser, then press Enter.",
                )

            writeLog("Waiting for add-to-cart or buy-now button", "DEBUG")
            add_to_cart = await tab.select("#add-to-cart-button", timeout=10)
            buy_now = await tab.select("#buy-now-button", timeout=10)

            if add_to_cart or buy_now:
                writeLog("Add-to-cart or buy-now button found", "INFO")
                writeLog("Item is available on Amazon", "SUCCESS")
                return True

            writeLog("Add-to-cart or buy-now button not found", "INFO")
            writeLog("Item is not available on Amazon", "INFO")
            return False
        except Exception as exc:
            writeLog(f"Error checking Amazon item: {exc}", "ERROR")
            return False

    async def login(self) -> None:
        """Sign in to Amazon using AMZ_EMAIL / AMZ_PASSWORD env vars (SEC-01)."""
        # SEC-01: credentials from env vars only -- never from config.yml or hardcoded.
        email = os.environ.get("AMZ_EMAIL", "")
        password = os.environ.get("AMZ_PASSWORD", "")
        # Guard: if credentials are missing, log and abort (never log their values).
        if not email or not password:
            writeLog("AMZ_EMAIL or AMZ_PASSWORD not set -- skipping login", "ERROR")
            return

        try:
            tab = await self.driver.get(
                "https://www.amazon.com/ap/signin"
                "?openid.pape.max_auth_age=0"
                "&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3Fref_%3Dnav_signin"
                "&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
                "&openid.assoc_handle=usflex"
                "&openid.mode=checkid_setup"
                "&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
                "&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
            )

            email_field = await tab.select("#ap_email", timeout=10)
            if not email_field:
                writeLog("Email field not found on Amazon sign-in page", "ERROR")
                return
            await email_field.send_keys(email)

            continue_btn = await tab.select("#continue", timeout=10)
            if continue_btn:
                await continue_btn.click()

            # Passkey prompt: user must dismiss manually before we can enter password.
            await self._wait_user_action(
                self.passkey_event,
                "Amazon passkey prompt visible. Dismiss it in the browser, then press Enter.",
            )

            writeLog("Attempting to enter password", "INFO")
            password_field = await tab.select("#ap_password", timeout=10)
            if not password_field:
                writeLog("Password field not found on Amazon sign-in page", "ERROR")
                return
            await password_field.send_keys(password)

            writeLog("Attempting to click sign-in button", "INFO")
            sign_in_btn = await tab.select("#signInSubmit", timeout=10)
            if not sign_in_btn:
                writeLog("Sign-in submit button not found", "ERROR")
                return
            await sign_in_btn.click()

            # Check for MFA prompt.
            writeLog("Checking for MFA prompt", "INFO")
            mfa_form = await tab.select("#auth-mfa-form", timeout=10)
            if mfa_form:
                await self._wait_user_action(
                    self.otp_event,
                    "MFA/OTP prompt detected. Enter your code in the browser, then press Enter.",
                )

            writeLog("Signed in to Amazon", "INFO")
        except Exception as exc:
            writeLog(f"Error during Amazon sign-in: {exc}", "ERROR")

    async def auto_buy(self, url: str) -> bool:
        """Attempt to purchase the item at url. Returns True on success.

        ASYNC-05: does NOT call update_item_purchased directly. The orchestrator's
        write queue owns the sole write path; auto_buy returns True on success and
        the orchestrator enqueues the DB write.
        """
        writeLog(f"Entering auto_buy for Amazon: {url}", "DEBUG")
        await self.login()
        try:
            tab = await self.driver.get(url)

            # Resolve quantity from config items by matching url; default to 1.
            quantity = 1
            if self.config and hasattr(self.config, "available"):
                for item in self.config.available.items:
                    if item.link == url:
                        quantity = item.quantity
                        break

            writeLog("Attempting to find quantity dropdown", "INFO")
            qty_dropdown = await tab.select(".a-button-dropdown", timeout=10)
            if not qty_dropdown:
                writeLog("Quantity dropdown not found", "ERROR")
                return False
            await qty_dropdown.click()

            writeLog(f"Attempting to find quantity option for {quantity}", "INFO")
            qty_option = await tab.select(f"#quantity_{quantity - 1}", timeout=10)
            if not qty_option:
                writeLog(f"Quantity option {quantity} not found", "ERROR")
                return False
            await qty_option.click()

            test_mode = self.config.debug.test_mode if self.config else True
            if test_mode:
                writeLog("Test mode active: pausing before buy-now", "DEBUG")
                await self._wait_user_action(
                    self.test_pause_event,
                    "TEST MODE: review the browser, then press Enter to continue.",
                )

            writeLog("Attempting to find buy-now button", "INFO")
            buy_now = await tab.select("#buy-now-button", timeout=10)
            if not buy_now:
                writeLog("Buy-now button not found", "ERROR")
                return False
            await buy_now.click()

            writeLog("Attempting to find place order button", "INFO")
            place_order = await tab.select("#submitOrderButtonId", timeout=10)
            if not place_order:
                writeLog("Place order button not found", "ERROR")
                return False

            if not test_mode:
                await place_order.click()
                writeLog("Order placed on Amazon", "SUCCESS")
                return True
            else:
                writeLog(
                    "Test mode active: skipping submitOrderButton click",
                    "SUCCESS",
                )
                await self._wait_user_action(
                    self.test_pause_event,
                    "TEST MODE: order review complete. Press Enter to continue.",
                )
                return False
        except Exception as exc:
            writeLog(f"Error during Amazon auto-buy: {exc}", "ERROR")
            return False
