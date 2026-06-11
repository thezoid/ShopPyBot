"""BestBuy retailer plugin for ShopPyBot.

Credentials are sourced exclusively from environment variables (SEC-01):
    BB_EMAIL    -- BestBuy account email
    BB_PASSWORD -- BestBuy account password

The CVV is threaded via self._cvv, set by main.py after setup() is called (SEC-02).
Neither credentials nor CVV are ever logged, stored to disk, or written to config.yml.

ASYNC-05: auto_buy returns True on success without calling update_item_purchased
directly. The orchestrator's write queue owns the sole write path.
"""

import asyncio
import json as _json
import logging

import nodriver

from core.credentials import get_store
from core.plugin_base import RetailerPlugin
from core.stealth import apply_stealth, build_proxy_browser_args, setup_proxy_auth, _is_ban_response
from logger import writeLog

_log = logging.getLogger(__name__)

_SITEKEY_JS = "document.querySelector('[data-sitekey]')?.getAttribute('data-sitekey')||''"


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
        # ANTI-06: captcha event + solver injected by PluginRegistry.assign_solver.
        self.captcha_event: asyncio.Event = asyncio.Event()
        self._captcha_solver = None

    async def _wait_user_action(self, event: asyncio.Event, message: str) -> None:
        """Notify user, await their Enter, clear the event for reuse (ASYNC-03).

        Mirrors AmazonPlugin._wait_user_action. 5-minute unattended guard;
        logs on timeout and continues. Always clears the event in finally.
        """
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
        """Best-effort reCAPTCHA v2 solve; fall back to manual pause on any failure.

        BestBuy may not show reCAPTCHA v2 (Open Question 2) -- empty sitekey
        falls gracefully to manual pause (no silent skip). Same executor +
        asyncio.timeout(120) pattern as AmazonPlugin (T-14-block2, T-14-silent).
        """
        solver = self._captcha_solver
        if solver is None or not solver.can_solve():
            await self._wait_user_action(
                self.captcha_event,
                "CAPTCHA detected on BestBuy. Solve it in the browser, then press Enter.",
            )
            return

        sitekey = await self._extract_sitekey(tab)
        if not sitekey:
            await self._wait_user_action(
                self.captcha_event,
                "CAPTCHA detected on BestBuy (no sitekey). Solve it in the browser, then press Enter.",
            )
            return

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
            _log.warning("BestBuy CAPTCHA solve failed: %s", exc.__class__.__name__)
            await self._wait_user_action(
                self.captcha_event,
                "CAPTCHA solve failed on BestBuy. Solve it in the browser, then press Enter.",
            )
            return

        if not token or "'" in token or "\\" in token or "\n" in token:  # CR-02
            _log.warning("BestBuy CAPTCHA token failed validation -- falling back to manual pause")
            await self._wait_user_action(
                self.captcha_event,
                "CAPTCHA token invalid on BestBuy. Solve it in the browser, then press Enter.",
            )
            return

        await self._inject_token(tab, token)

    async def detect_captcha(self) -> bool:
        """Return True if a reCAPTCHA widget or BestBuy challenge page is present."""
        tab = self.driver.main_tab
        # reCAPTCHA widget presence (data-sitekey)
        try:
            sitekey = await tab.evaluate(_SITEKEY_JS) or ""
            if sitekey:
                return True
        except Exception:
            pass
        # BestBuy challenge page marker (common challenge phrase)
        try:
            element = await tab.find("robot", best_match=False, timeout=2)
            if element is not None:
                return True
        except Exception:
            pass
        return False

    async def setup(self) -> None:
        # Fail loudly if proxy required but pool is exhausted (T-13-10, Pitfall 2).
        if getattr(self, "_proxy_required", False) and getattr(self, "_proxy", None) is None:
            writeLog("Proxy enabled but pool exhausted -- refusing direct launch", "ERROR")
            raise RuntimeError("BestBuyPlugin: proxy pool exhausted; cannot launch")

        headless = True
        if self.config:
            platform_cfg = getattr(getattr(self.config, "platforms", None), "bestbuy", None)
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
            # ANTI-05 / CR-02: scan for ban page before checking availability selectors.
            body_text = ""
            try:
                body_text = await tab.evaluate("document.body.innerText") or ""
            except Exception:
                pass
            if self._handle_ban(body_text):
                return False

            # ANTI-06: detect CAPTCHA and attempt automated solve with manual fallback.
            captcha_present = await self.detect_captcha()
            if captcha_present:
                await self._solve_or_pause(tab, url)
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
            writeLog(f"Error checking BestBuy item: {exc.__class__.__name__}", "ERROR")
            return False

    async def login(self) -> None:
        """Sign in to BestBuy using BB_EMAIL / BB_PASSWORD env vars (SEC-01)."""
        # SEC-01: credentials from credential store only -- never from config.yml or hardcoded.
        store = get_store()
        email = store.get("BB_EMAIL") or ""
        password = store.get("BB_PASSWORD") or ""
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
            writeLog(f"Error during BestBuy sign-in: {exc.__class__.__name__}", "ERROR")

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
            return await self.place_order_guarded(place_order.click)
        except Exception as exc:
            writeLog(f"Error during BestBuy auto-buy: {exc.__class__.__name__}", "ERROR")
            return False
