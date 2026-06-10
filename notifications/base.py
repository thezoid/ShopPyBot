"""Notifier ABC and NotificationEvent dataclass (Phase 5 contract).

All channel notifiers (sound, Discord, email, SMS) subclass Notifier and
implement send(). The dispatcher calls send() on each registered notifier
inside its own try/except so a single channel failure never blocks others.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


def cents_to_display(cents: int | None) -> str:
    """Format integer cents as $X.XX; return 'n/a' for None."""
    if cents is None:
        return "n/a"
    return f"${cents / 100:.2f}"


@dataclass
class NotificationEvent:
    """Carries context for a single stock alert or purchase confirmation.

    Fields:
        item_name:           Human-readable item name from config.
        item_url:            Canonical item URL (used for dedup and embed linking).
        platform:            Retailer name, e.g. "Amazon" or "BestBuy".
        timestamp:           UTC datetime of the event; formatters convert to ISO-8601.
        action:              "detected" (stock found), "purchased" (auto-buy success),
                             or "price_drop" (price fell to/below target).
        price_cents:         Current item price in integer cents. Populated only for
                             action == "price_drop". None for all other actions.
        target_price_cents:  Configured target price in integer cents. None when no
                             absolute target is set or action != "price_drop".
        pct_from_target:     Percentage the current price is below the target
                             (positive float, e.g. 10.0 = 10% below). None when
                             no target is set or action != "price_drop".
    """

    item_name: str
    item_url: str
    platform: str
    timestamp: datetime
    action: str  # "detected" | "purchased" | "price_drop"
    # PRICE-04: optional price context; None for non-price events (Pitfall 6: must
    # come after all required fields; all three carry = None defaults).
    price_cents: int | None = None
    target_price_cents: int | None = None
    pct_from_target: float | None = None


class Notifier(ABC):
    """Abstract base for all notification channels.

    Subclasses must implement send(). The dispatcher awaits send() inside a
    per-channel try/except; raising is safe -- other channels still fire.
    """

    @abstractmethod
    async def send(self, event: NotificationEvent) -> None:
        """Deliver notification for event. Raise on unrecoverable failure."""
        ...
