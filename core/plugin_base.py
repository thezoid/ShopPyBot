import time
from abc import ABC, abstractmethod
from typing import Literal

from nodriver.cdp import network as cdp_network
from nodriver.cdp import storage as cdp_storage

from core.session_store import build_session_store
from core.stealth import _is_ban_response
from logger import writeLog

PLUGIN_API_VERSION = 2  # bumped from 1; v1 subclasses are not compatible

_VALID_DIFFICULTY = frozenset({"easy", "medium", "hard"})


def _dicts_to_cookie_params(dicts: list[dict]) -> list[cdp_network.CookieParam]:
    """Convert serialized cookie dicts to CookieParam objects for CDP set_cookies.

    Filters out expired cookies (expires < time.time()).
    Maps same_site string to CookieSameSite enum (None on unknown value).
    Wraps expires as TimeSinceEpoch (float subclass) per Pitfall 2.

    NEVER passes network.Cookie objects -- those have extra fields that Chrome
    CDP rejects (nodriver bug #1816/#2020). Always builds fresh CookieParam.
    """
    now = time.time()
    params: list[cdp_network.CookieParam] = []
    for d in dicts:
        exp = d.get("expires")
        if exp is not None and float(exp) < now:
            continue  # skip expired cookies (Pitfall 3 / T-23-10)
        same_site = None
        if d.get("same_site"):
            try:
                same_site = cdp_network.CookieSameSite(d["same_site"])
            except ValueError:
                same_site = None
        expires_param = cdp_network.TimeSinceEpoch(float(exp)) if exp is not None else None
        params.append(
            cdp_network.CookieParam(
                name=d["name"],
                value=d["value"],
                domain=d.get("domain"),  # preserve domain/path exactly (Pitfall 4)
                path=d.get("path"),
                expires=expires_param,
                http_only=d.get("http_only"),
                secure=d.get("secure"),
                same_site=same_site,
            )
        )
    return params


class RetailerPlugin(ABC):
    """Base class for all retail platform plugins.

    Concrete plugins must implement check_availability and auto_buy.
    All other methods have working no-op defaults.
    """

    domain_patterns: list[str]  # class attribute; registry reads before __init__

    # REG-02: additive registry metadata -- existing plugins inherit these defaults
    # (no PLUGIN_API_VERSION bump required; additive class attributes are non-breaking)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    requires_proxy: bool = False
    requires_captcha: bool = False

    def __init_subclass__(cls, **kwargs) -> None:
        # Import-time validation is intentional: an invalid difficulty value is a
        # plugin author error that should fail loudly at discovery, not silently at
        # runtime.  Plugins that omit `difficulty` inherit "medium" and are never
        # invalidated by this hook.
        super().__init_subclass__(**kwargs)
        if cls.difficulty not in _VALID_DIFFICULTY:
            raise ValueError(
                f"{cls.__name__}.difficulty={cls.difficulty!r} is not one of "
                f"{sorted(_VALID_DIFFICULTY)}"
            )

    def __init__(self, config) -> None:
        self.config = config   # typed AppConfig passed by registry
        self.driver = None     # set by setup(); never in __init__ (nodriver constraint:
                               # Browser.__init__ raises RuntimeError with no running loop)
        # BUY-07: checkout profile loaded by setup() via load_checkout_profile().
        # Default None so plugins that do not call load_checkout_profile() still have
        # the attribute and raise no AttributeError on access. Non-breaking additive
        # default; PLUGIN_API_VERSION stays 2.
        self._checkout_profile = None
        self._checkout_stage: str = ""  # BUY-06: set before each DOM stage; readable on CancelledError

    def _handle_ban(self, body_text: str) -> bool:
        """Check body_text for ban signals and record proxy failure if banned (CR-02).

        Returns True if the response is a ban page so the caller can return False early.
        Reads self._proxy and self._pool if set; safe to call when proxy is disabled.
        """
        if not _is_ban_response(0, body_text):
            return False
        proxy = getattr(self, "_proxy", None)
        pool = getattr(self, "_pool", None)
        if proxy and pool:
            pool.record_failure(proxy)
        return True

    async def setup(self) -> None:
        """Build the nodriver Browser. Registry awaits this after construction."""
        ...

    @abstractmethod
    async def check_availability(self, url: str) -> bool:
        """Return True if the item at url is in stock and purchasable."""
        ...

    @abstractmethod
    async def auto_buy(self, url: str) -> bool:
        """Attempt to purchase the item at url. Return True on success."""
        ...

    async def get_price(self, url: str) -> int | None:
        """Return the current item price as integer cents, or None if unsupported.

        Default returns None (price monitoring unsupported for this plugin).
        PLUGIN_API_VERSION stays 2 -- additive non-abstract method (PRICE-02).
        Override in platform plugins that can scrape a live price.
        """
        return None

    def get_active_tab(self):
        """Return the live tab for confirmation detection after auto_buy().

        Default returns driver.main_tab. Override in plugins that store the
        last-navigated tab explicitly (Amazon, BestBuy).
        PLUGIN_API_VERSION stays 2 -- additive concrete method (BUY-03).
        """
        return getattr(self.driver, "main_tab", None)

    async def place_order_guarded(self, click_fn) -> bool:
        """Invoke click_fn only when test_mode and monitor_only are both False.

        Returns True when the click fires, False when suppressed.
        Never raises. PLUGIN_API_VERSION stays 2 (additive concrete method, BUY-02).

        Safe-default behavior when config or debug is absent:
        - test_mode defaults to True (suppressed): missing config prevents an order.
        - monitor_only defaults to True (suppressed): missing/legacy config also
          suppresses. DebugConfig.monitor_only defaults to False in the schema, so
          normal configs are unaffected; only pathological/legacy configs benefit
          from this fail-safe (CR-01).
        - If self.config is None or has no debug attribute, both flags default to
          True and the guard always suppresses.
        """
        debug = getattr(self.config, "debug", None) if self.config else None
        test_mode = getattr(debug, "test_mode", True)
        monitor_only = getattr(debug, "monitor_only", True)   # CR-01: was False; fail-safe must suppress
        if test_mode or monitor_only:
            writeLog("place-order suppressed (monitor_only/test_mode)", "INFO")
            return False
        await click_fn()
        return True

    async def login(self) -> None:
        """Authenticate with the retail platform. No-op default."""
        return None

    async def detect_captcha(self) -> bool:
        """Return True if a CAPTCHA is present. No-op default."""
        return False

    async def teardown(self) -> None:
        """Close the browser. Registry calls at shutdown."""
        ...

    async def relaunch(self) -> None:
        """Cold-restart the browser: teardown -> setup (stealth + proxy) -> restore_session -> login.

        Called by supervise() on browser-death detection. Sequence is fixed:
        1. teardown() -- close the dead browser process (safe to call if already dead)
        2. setup() -- Browser.create() + apply_stealth() + setup_proxy_auth()
           (stealth MUST re-inject: CDP add_script_to_evaluate_on_new_document is
           session-scoped and NOT persisted across Browser.stop() + Browser.create().
           setup() is the single injection point. [VERIFIED nodriver 0.50.3])
        3. restore_session() -- no-op stub in Phase 22; Phase 23 replaces (REL-04)
        4. login() -- re-authenticate if restore_session returned False

        proxy re-assignment (assign_proxy) is the supervisor's responsibility BEFORE
        calling relaunch(); relaunch() takes no registry reference.
        PLUGIN_API_VERSION stays 2 -- additive concrete method (REL-03).
        """
        plugin_name = self.__class__.__name__
        writeLog(f"[{plugin_name}] relaunch: tearing down", "INFO")
        try:
            await self.teardown()
        except Exception as exc:
            writeLog(
                f"[{plugin_name}] teardown error during relaunch: {exc.__class__.__name__}",
                "WARNING",
            )
        writeLog(f"[{plugin_name}] relaunch: starting new browser", "INFO")
        await self.setup()
        session_restored = await self.restore_session()
        if not session_restored:
            writeLog(f"[{plugin_name}] restore_session=False; re-logging in", "INFO")
            await self.login()
        else:
            writeLog(f"[{plugin_name}] relaunch: session restored; skipping login", "INFO")

    def _session_platform_key(self) -> str | None:
        """Return platform_key attribute if defined on the subclass, else None."""
        return getattr(self, "platform_key", None)

    def _session_enabled(self) -> bool:
        """Return True when session_persistence is enabled for this platform.

        Uses getattr-safe reads (mirrors place_order_guarded idiom) so plugins
        without a platform_key or a matching platforms config never raise.
        """
        key = self._session_platform_key()
        if key is None:
            return False
        platform_cfg = getattr(getattr(self.config, "platforms", None), key, None)
        return bool(getattr(platform_cfg, "session_persistence", False))

    async def restore_session(self) -> bool:
        """Restore browser session from encrypted cookies via raw CDP set_cookies.

        Returns True when cookies were successfully restored (login can be skipped).
        Returns False on: session_persistence disabled, no passphrase, no tab,
        missing/corrupt session file, or expired-only cookie list.

        Uses tab.send(cdp_storage.set_cookies([CookieParam(...)])) directly.
        NEVER passes network.Cookie objects and NEVER calls CookieJar.set_all()
        -- those paths trigger the confirmed nodriver bug (issues #1816/#2020)
        where extra Cookie fields (size, session, sourceScheme, sourcePort) cause
        Chrome to silently reject the restore.

        PLUGIN_API_VERSION stays 2 -- additive non-abstract method (REL-04).
        """
        if not self._session_enabled():
            return False
        key = self._session_platform_key()
        store = build_session_store()
        cookies = store.restore(key)   # returns None on no passphrase, missing file, bad token
        if not cookies:
            return False
        tab = self.get_active_tab()
        if tab is None:
            return False
        params = _dicts_to_cookie_params(cookies)
        if not params:
            return False
        try:
            await tab.send(cdp_storage.set_cookies(params))
            writeLog(
                f"[{self.__class__.__name__}] restore_session: {len(params)} cookies restored",
                "INFO",
            )
            return True
        except Exception as exc:
            writeLog(
                f"[{self.__class__.__name__}] restore_session CDP error:"
                f" {exc.__class__.__name__}; falling back to login",
                "WARNING",
            )
            return False

    async def save_session(self) -> None:
        """Save browser cookies after successful login when session_persistence enabled.

        No-op when session_persistence is False, passphrase absent, or tab unavailable.
        Reads cookies via tab.send(cdp_storage.get_cookies()), serializes the 8
        CookieParam-compatible fields, and persists via SessionStore.save.
        Exceptions are caught and logged by class name -- save failure must never
        break the login flow.

        PLUGIN_API_VERSION stays 2 -- additive non-abstract method (REL-04).
        """
        if not self._session_enabled():
            return
        tab = self.get_active_tab()
        if tab is None:
            return
        key = self._session_platform_key()
        try:
            raw_cookies = await tab.send(cdp_storage.get_cookies())
            dicts = [
                {
                    "name": c.name,
                    "value": c.value,
                    "domain": c.domain,
                    "path": c.path,
                    "expires": float(c.expires) if c.expires is not None else None,
                    "http_only": c.http_only,
                    "secure": c.secure,
                    "same_site": c.same_site.value if c.same_site is not None else None,
                }
                for c in raw_cookies
            ]
            build_session_store().save(key, dicts)
            writeLog(
                f"[{self.__class__.__name__}] save_session: {len(dicts)} cookies saved",
                "INFO",
            )
        except Exception as exc:
            writeLog(
                f"[{self.__class__.__name__}] save_session error: {exc.__class__.__name__}",
                "WARNING",
            )
