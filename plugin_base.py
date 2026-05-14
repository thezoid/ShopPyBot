"""Retail plugin contract for ShopPyBot.

All retailer integrations subclass RetailerPlugin and implement the two
abstract methods (check_availability, auto_buy). login(), detect_captcha(),
and shutdown() have working defaults so check-only plugins do not need boilerplate.

Per D-01 (Phase 1 CONTEXT): ABC methods do NOT take a `driver` argument.
Subclasses construct `self.driver` in `__init__`.

Per Phase 4 D-04: `shutdown()` is an async coroutine; default implementation
awaits asyncio.to_thread(self.driver.quit) so the orchestrator can run all
plugin teardowns under asyncio.shield in a TaskGroup finally block.
"""
import asyncio
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
    """

    domain_pattern: list[str] = []
    login_at_startup: bool = False
    name: str = ""

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
