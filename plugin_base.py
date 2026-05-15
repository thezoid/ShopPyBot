"""Retail plugin contract for ShopPyBot.

All retailer integrations subclass RetailerPlugin and implement the two
abstract methods (check_availability, auto_buy). login(), detect_captcha(),
shutdown(), open(), and next_delay() have working defaults so check-only
plugins do not need boilerplate.

Per D-01 (Phase 1 CONTEXT): ABC methods do NOT take a `driver` argument.
Subclasses construct `self.driver` in `__init__`.

Per Phase 4 D-04: `shutdown()` is an async coroutine; default implementation
awaits asyncio.to_thread(self.driver.quit) so the orchestrator can run all
plugin teardowns under asyncio.shield in a TaskGroup finally block.

Per Phase 6 D-03/D-04: `open()` is a non-abstract async coroutine no-op default
(Selenium plugins inherit this; nodriver plugins override to build self.driver
asynchronously). `next_delay()` is a non-abstract sync default returning
`random.uniform(self.min_delay, self.max_delay)` for ANTI-01 anti-detection
jitter. Class attrs `min_delay = 3.0` and `max_delay = 8.0` act as defensive
defaults; plugins or platform_config override via instance attrs.
"""
import asyncio
import random
from abc import ABC, abstractmethod

from logger import writeLog

PLUGIN_API_VERSION: int = 1


class RetailerPlugin(ABC):
    """Abstract base for retail platform plugins.

    Subclasses MUST set `domain_pattern` to a non-empty list of hostnames
    (e.g. ["amazon.com", "amzn.to"]) and implement `check_availability` and
    `auto_buy`. Per Phase 2 D-03, set `login_at_startup = True` to opt in to
    a one-shot `.login()` call at startup before the polling loop begins.
    Per Phase 4 D-04, override `shutdown()` for extra teardown; call
    `await super().shutdown()` at the end to inherit driver.quit cleanup.
    Per Phase 6, override `open()` to build async-native drivers (nodriver).
    """

    domain_pattern: list[str] = []
    login_at_startup: bool = False
    name: str = ""
    min_delay: float = 3.0
    max_delay: float = 8.0

    def __init__(self, platform_config) -> None:
        """Store platform-scoped config slice. Subclasses build self.driver here."""
        self.platform_config = platform_config

    @abstractmethod
    def check_availability(self, url: str) -> bool:
        """Return True if the item at `url` is in stock."""
        raise NotImplementedError

    @abstractmethod
    def auto_buy(self, url: str, config) -> bool:
        """Attempt to purchase the item at `url`. Return True on success."""
        raise NotImplementedError

    def login(self, config) -> None:
        """No-op default. Override if the platform requires authentication."""
        return None

    def detect_captcha(self) -> bool:
        """No-op default returning False. Override to detect platform-specific CAPTCHAs."""
        return False

    async def open(self) -> None:
        """No-op default. Override in async-native plugins (nodriver) to build self.driver.

        Called by discover_async AFTER __init__ AND BEFORE the next stagger
        sleep. Selenium plugins inherit the no-op (they build their driver
        synchronously in __init__).
        """
        return None

    def next_delay(self) -> float:
        """Return random.uniform(min_delay, max_delay): fresh sample per call (ANTI-01)."""
        return random.uniform(self.min_delay, self.max_delay)

    async def shutdown(self) -> None:
        """Default cleanup: quit the Selenium driver in a worker thread.

        Override to add extra cleanup; call `await super().shutdown()` at the
        end. Plugins with no driver (test stubs, check-only) inherit the
        no-op-safe default. Exceptions from `driver.quit` are logged at
        WARNING and swallowed so one plugin's quit failure cannot block the
        orchestrator from shutting down the others.
        """
        driver = getattr(self, "driver", None)
        if driver is None:
            return
        try:
            await asyncio.to_thread(driver.quit)
        except Exception as e:
            writeLog(
                f"{type(self).__name__}.shutdown: driver.quit raised: {e}",
                "WARNING",
            )
