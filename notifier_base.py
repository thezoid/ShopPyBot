"""Notifier contract for ShopPyBot (Phase 5).

Mirrors RetailerPlugin from plugin_base.py. Notifiers fan out from the
orchestrator's notification_writer via asyncio.gather(return_exceptions=True),
so each notifier's send() runs concurrently and per-channel failures are
isolated.

Per Phase 5 CONTEXT D-01: `name` and `enabled` are class attributes; `send`
is the only required abstract method; `shutdown` is a non-abstract async
no-op that subclasses override only when they hold resources (SMTP pool,
persistent HTTP client). NotificationEvent is frozen=True for hashability
and in-flight tamper safety.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

NOTIFIER_API_VERSION: int = 1


@dataclass(frozen=True)
class NotificationEvent:
    """Single notification payload pushed onto the notification_queue.

    timestamp must be a tz-aware UTC datetime (CONTEXT pitfall 9).
    action distinguishes a stock detection from a successful auto-buy.
    """
    item_name: str
    url: str
    platform: str
    timestamp: datetime
    action: Literal["detected", "purchased"]


class Notifier(ABC):
    """Abstract base for notification channels (sound, Discord, email, SMS)."""

    name: str = ""
    enabled: bool = False

    @abstractmethod
    async def send(self, event: NotificationEvent) -> None:
        """Deliver `event` over this channel. Raise on transport failure."""
        raise NotImplementedError

    async def shutdown(self) -> None:
        """No-op default. Override only when holding resources (pool, client)."""
        return None
