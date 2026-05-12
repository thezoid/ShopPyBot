"""Retail plugin contract for ShopPyBot.

All retailer integrations subclass RetailerPlugin and implement the two
abstract methods (check_availability, auto_buy). login() and detect_captcha()
have no-op defaults so check-only plugins do not need boilerplate.

Per D-01 (Phase 1 CONTEXT): ABC methods do NOT take a `driver` argument.
Subclasses construct `self.driver` in `__init__`.
"""
from abc import ABC, abstractmethod

PLUGIN_API_VERSION: int = 1


class RetailerPlugin(ABC):
    """Abstract base for retail platform plugins.

    Subclasses MUST set `domain_pattern` (class attribute, e.g. "amazon.com")
    and implement `check_availability` and `auto_buy`.
    """

    domain_pattern: str = ""

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
