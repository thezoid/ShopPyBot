"""Amazon retailer plugin for ShopPyBot.

Credentials are sourced exclusively from environment variables (SEC-01):
    AMZ_EMAIL    -- Amazon account email
    AMZ_PASSWORD -- Amazon account password

Neither value is ever logged, stored to disk, or written to config.yml.
"""

import asyncio
import json as _json
import logging
import math
import re

import nodriver

from core.credentials import get_store
from core.plugin_base import RetailerPlugin
from core.stealth import apply_stealth, build_proxy_browser_args, setup_proxy_auth, _is_ban_response
from logger import writeLog
from utils import play_notification_sound

_log = logging.getLogger(__name__)

# Price selectors tried in order; first non-empty element text wins.
_PRICE_SELECTORS = [
    ".a-price .a-offscreen",
    "#corePrice_feature_div .a-offscreen",
    "#priceblock_ourprice",
]


def _parse_price_to_cents(text: str | None) -> int | None:
    """Parse a price string into integer cents. Returns None for invalid input.

    Strips all characters except digits and '.' via re.sub, then converts via
    round(float * 100). Rejects empty, non-finite, zero, negative, or strings
    containing a '-' sign (negative prices are invalid).
    Never uses eval/exec on scraped text (T-16-PRICESTR).
    """
    if not text:
        return None
    # Reject any string containing a minus sign before stripping (T-04 guard).
    if "-" in text:
        return None
    cleaned = re.sub(r"[^\d.]", "", text)
    if not cleaned or not any(c.isdigit() for c in cleaned):
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    return round(value * 100)


_WAF_PROBE_JS = (
    "(function(){var p=window.gokuProps;"
    "if(p)return JSON.stringify({key:p.key,iv:p.iv,context:p.context});"
    "return null;})();"
)
_SITEKEY_JS = "document.querySelector('[data-sitekey]')?.getAttribute('data-sitekey')||''"


class AmazonPlugin(RetailerPlugin):
    """Amazon platform plugin; owns one isolated nodriver Browser process."""

    domain_patterns = ["amazon.com", "amazon.co.uk", "amazon.ca"]

    def __init__(self, config) -> None:
        super().__init__(config)
        # SEC-02: CVV sourced at runtime via getpass; injected by orchestrator
        # after setup(). Never logged or written to disk.
        self._cvv = None
        # One Event per distinct intervention type (ASYNC-03).
        # asyncio.Event() is safe to create before loop start in Python 3.10+.
        self.captcha_event: asyncio.Event = asyncio.Event()
        self.passkey_event: asyncio.Event = asyncio.Event()
        self.otp_event: asyncio.Event = asyncio.Event()
        self.test_pause_event: asyncio.Event = asyncio.Event()
        # Injected by PluginRegistry.assign_solver (Plan 02); None when disabled.
        self._captcha_solver = None

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

    async def _extract_sitekey(self, tab) -> str:
        """Return reCAPTCHA v2 sitekey from data-sitekey attribute, or empty string."""
        try:
            return await tab.evaluate(_SITEKEY_JS) or ""
        except Exception:
            return ""

    async def _inject_token(self, tab, token: str) -> None:
        """Inject a validated reCAPTCHA token into the page via JS callbacks."""
        safe = _json.dumps(token)   # produces "..." with all special chars escaped (CR-02)
        inject_js = (
            f"(function(){{"
            f"var el=document.getElementById('g-recaptcha-response');"
            f"if(el){{el.value={safe};}}"
            f"var c=window.___grecaptcha_cfg&&window.___grecaptcha_cfg.clients;"
            f"if(c){{Object.values(c).forEach(function(x){{"
            f"if(x&&x.callback){{try{{x.callback({safe});}}catch(e){{}}}}"
            f"}});}}}})();"
        )
        await tab.evaluate(inject_js)

    async def _solve_or_pause(self, tab, pageurl: str) -> None:
        """Attempt automated reCAPTCHA v2 solve; fall back to manual pause on any failure.

        Decision tree (ANTI-06, T-14-inject, T-14-block2, T-14-silent, T-14-waf):
          1. No solver or can_solve() False -> manual pause
          2. window.gokuProps present (WAF) -> INFO log + manual pause (deferred)
          3. Empty sitekey -> manual pause
          4. Solve raises / times out -> manual pause
          5. Token empty or contains quote/newline -> manual pause
          6. All OK -> inject token; no manual pause
        """
        solver = self._captcha_solver
        if solver is None or not solver.can_solve():
            await self._wait_user_action(
                self.captcha_event,
                "CAPTCHA detected on Amazon. Solve it in the browser, then press Enter.",
            )
            return

        # WAF detection: window.gokuProps present means Amazon WAF CAPTCHA (deferred).
        try:
            waf_raw = await tab.evaluate(_WAF_PROBE_JS)
        except Exception:
            waf_raw = None
        if waf_raw:
            _log.info("Amazon WAF CAPTCHA detected -- auto-solve deferred; falling back to manual pause")
            await self._wait_user_action(
                self.captcha_event,
                "Amazon WAF CAPTCHA detected. Solve it in the browser, then press Enter.",
            )
            return

        sitekey = await self._extract_sitekey(tab)
        if not sitekey:
            await self._wait_user_action(
                self.captcha_event,
                "CAPTCHA detected on Amazon (no sitekey). Solve it in the browser, then press Enter.",
            )
            return

        # Solve via run_in_executor; timeout wraps ONLY the executor call (Pitfall 3).
        # WR-01: asyncio.timeout cancels the await but not the executor thread.
        # The thread can run up to _POLL_INTERVAL_SECS + requests timeout (10s) past
        # the 120s gate. _MAX_POLLS is sized so normal runs finish before timeout fires.
        loop = asyncio.get_running_loop()
        try:
            async with asyncio.timeout(120):
                token = await loop.run_in_executor(
                    None, solver.solve_recaptcha, sitekey, pageurl
                )
        except (asyncio.TimeoutError, Exception) as exc:
            _log.warning("CAPTCHA solve failed: %s", exc.__class__.__name__)
            await self._wait_user_action(
                self.captcha_event,
                "CAPTCHA solve failed on Amazon. Solve it in the browser, then press Enter.",
            )
            return

        # V5 input validation: reject token containing quote, backslash, or newline (CR-02).
        if not token or "'" in token or "\\" in token or "\n" in token:
            _log.warning("CAPTCHA token failed validation -- falling back to manual pause")
            await self._wait_user_action(
                self.captcha_event,
                "CAPTCHA token invalid on Amazon. Solve it in the browser, then press Enter.",
            )
            return

        await self._inject_token(tab, token)

    async def setup(self) -> None:
        # Fail loudly if proxy required but pool is exhausted (T-13-10, Pitfall 2).
        if getattr(self, "_proxy_required", False) and getattr(self, "_proxy", None) is None:
            writeLog("Proxy enabled but pool exhausted -- refusing direct launch", "ERROR")
            raise RuntimeError("AmazonPlugin: proxy pool exhausted; cannot launch")

        headless = True
        if self.config:
            platform_cfg = getattr(getattr(self.config, "platforms", None), "amazon", None)
            if platform_cfg is not None:
                headless = getattr(platform_cfg, "headless", True)

        proxy = getattr(self, "_proxy", None)
        browser_args = build_proxy_browser_args(proxy)   # WR-02: returns [] or [...]; never None
        self.driver = await nodriver.start(headless=headless, browser_args=browser_args)

        # ANTI-08: apply stealth BEFORE first navigation (Pitfall 8).
        await apply_stealth(self.driver.main_tab)

        # Authenticated proxy: register CDP Fetch handlers (Pitfall 4+5).
        if proxy and proxy.username:
            await setup_proxy_auth(self.driver.main_tab, proxy.username, proxy.password)

        # BUY-07: load checkout profile once per bot run; None when unconfigured.
        from core.checkout_profile import load_checkout_profile
        self._checkout_profile = load_checkout_profile()

    async def teardown(self) -> None:
        if self.driver:
            # Browser.stop() is synchronous; it terminates the subprocess and
            # handles any missing-connection edge case internally (RESEARCH Pattern 7).
            self.driver.stop()
            self.driver = None

    async def get_price(self, url: str) -> int | None:
        """Scrape the current Amazon listing price and return integer cents.

        Tries an ordered list of CSS selectors; takes the first non-empty text;
        delegates to _parse_price_to_cents for sanitization. Any exception
        (network, selector, parse) logs the class name and returns None (T-16-DOS).
        Selector list is site-specific and may need maintenance (documented in SUMMARY).
        """
        try:
            tab = await self.driver.get(url)
            for selector in _PRICE_SELECTORS:
                element = await tab.select(selector, timeout=10)
                if element is None:
                    continue
                text = getattr(element, "text", None) or ""
                result = _parse_price_to_cents(text)
                if result is not None:
                    return result
            return None
        except Exception as exc:
            writeLog(f"[AmazonPlugin] get_price error: {exc.__class__.__name__}", "ERROR")
            return None

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
                await self._solve_or_pause(tab, url)

            # ANTI-05: scan body for ban phrases; record failure on proxy (restart-only).
            body_text = ""
            try:
                body_text = await tab.evaluate("document.body.innerText") or ""
            except Exception:
                pass
            if self._handle_ban(body_text):
                return False

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
            writeLog(f"Error checking Amazon item: {exc.__class__.__name__}", "ERROR")
            return False

    async def login(self) -> None:
        """Sign in to Amazon using AMZ_EMAIL / AMZ_PASSWORD env vars (SEC-01)."""
        # SEC-01: credentials from credential store only -- never from config.yml or hardcoded.
        store = get_store()
        email = store.get("AMZ_EMAIL") or ""
        password = store.get("AMZ_PASSWORD") or ""
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
            writeLog(f"Error during Amazon sign-in: {exc.__class__.__name__}", "ERROR")

    async def auto_buy(self, url: str) -> bool:
        """Attempt to purchase the item at url. Returns True on success.

        ASYNC-05: does NOT call update_item_purchased directly. The orchestrator's
        write queue owns the sole write path; auto_buy returns True on success and
        the orchestrator enqueues the DB write.

        Defense-in-depth (CR-02): monitor_only suppresses at method entry before any
        DOM interaction. test_mode is intentionally NOT suppressed here -- it navigates
        through to the final place_order_guarded call (which suppresses the actual
        order), enabling cart inspection before the guarded click.
        """
        writeLog(f"Entering auto_buy for Amazon: {url}", "DEBUG")
        if self.config is None:
            writeLog("[AmazonPlugin] auto_buy called with no config -- suppressing", "WARNING")
            return False
        debug = getattr(self.config, "debug", None)
        if getattr(debug, "monitor_only", False):
            writeLog("[AmazonPlugin] auto_buy suppressed (monitor_only)", "INFO")
            return False
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

            debug = getattr(self.config, "debug", None) if self.config else None
            if getattr(debug, "test_mode", False):
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

            # BUY-07: enter CVV from self._cvv when set.
            # Amazon's CVV field only appears in some sessions (Pitfall 4 / T-20-10):
            # absent CVV field is a valid state (payment pre-verified) -- do NOT return False.
            if self._cvv:
                cvv_field = await tab.select("#addCreditCardCvvInput", timeout=5)
                if cvv_field:
                    # SEC-02: CVV sourced from self._cvv; never logged.
                    await cvv_field.send_keys(self._cvv)
                # CVV field absent: skip gracefully, continue to place_order_guarded

            self._last_tab = tab  # BUY-03: expose confirmation page to orchestrator
            return await self.place_order_guarded(place_order.click)
        except Exception as exc:
            writeLog(f"Error during Amazon auto-buy: {exc.__class__.__name__}", "ERROR")
            return False

    def get_active_tab(self):
        """Return the tab last navigated by auto_buy(), or fall back to main_tab."""
        return getattr(self, "_last_tab", None) or getattr(self.driver, "main_tab", None)
