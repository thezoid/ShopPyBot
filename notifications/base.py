"""Notifier ABC and NotificationEvent dataclass (Phase 5 contract).

All channel notifiers (sound, Discord, email, SMS) subclass Notifier and
implement send(). The dispatcher calls send() on each registered notifier
inside its own try/except so a single channel failure never blocks others.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class NotificationEvent:
    """Carries context for a single stock alert or purchase confirmation.

    Fields:
        item_name: Human-readable item name from config.
        item_url:  Canonical item URL (used for dedup and embed linking).
        platform:  Retailer name, e.g. "Amazon" or "BestBuy".
        timestamp: UTC datetime of the event; formatters convert to ISO-8601.
        action:    "detected" (stock found) or "purchased" (auto-buy success).
    """

    item_name: str
    item_url: str
    platform: str
    timestamp: datetime
    action: str  # "detected" | "purchased"


class Notifier(ABC):
    """Abstract base for all notification channels.

    Subclasses must implement send(). The dispatcher awaits send() inside a
    per-channel try/except; raising is safe -- other channels still fire.
    """

    @abstractmethod
    async def send(self, event: NotificationEvent) -> None:
        """Deliver notification for event. Raise on unrecoverable failure."""
        ...
