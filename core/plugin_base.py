from abc import ABC, abstractmethod
from typing import Literal

from core.stealth import _is_ban_response
from logger import writeLog

PLUGIN_API_VERSION = 2  # bumped from 1; v1 subclasses are not compatible

_VALID_DIFFICULTY = frozenset({"easy", "medium", "hard"})


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

    async def restore_session(self) -> bool:
        """Restore browser session from encrypted cookies. No-op stub for Phase 22.

        Returns False always. Phase 23 (REL-04) replaces with Fernet cookie restore.
        PLUGIN_API_VERSION stays 2 -- additive non-abstract method.
        """
        return False
