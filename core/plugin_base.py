from abc import ABC, abstractmethod

PLUGIN_API_VERSION = 1  # importable without instantiation; defined before class body

class RetailerPlugin(ABC):
    """Base class for all retail platform plugins.

    Subclasses must implement check_availability and auto_buy.
    login and detect_captcha have working no-op defaults so check-only
    plugins can omit them.
    """

    @abstractmethod
    def check_availability(self, url: str) -> bool:
        """Return True if the item at url is available for purchase."""
        ...

    @abstractmethod
    def auto_buy(self, driver, url: str, config: dict) -> bool:
        """Attempt to purchase the item at url. Return True on success."""
        ...

    def login(self, driver, config: dict) -> None:
        """Authenticate with the retail platform. No-op default."""
        return None

    def detect_captcha(self, driver) -> bool:
        """Return True if a CAPTCHA is present on the current page. No-op default."""
        return False
