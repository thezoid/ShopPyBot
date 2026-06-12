"""HealthRegistry: per-plugin health store for REL-07.

Read-side complement to the Phase 22 supervisor. The orchestrator (Plan 04)
writes via mutators on the bot event loop; BotService.get_status() (Plan 03)
reads via get_snapshot() which may be called from a different thread.
"""

import time

_IDLE_STATUS = "idle"


class HealthRegistry:
    """Lock-free per-plugin counter store with in-memory armed/disarmed dedup."""

    def __init__(self) -> None:
        self._plugins: dict[str, dict] = {}

    def _ensure(self, name: str) -> None:
        if name not in self._plugins:
            self._plugins[name] = {
                "status": _IDLE_STATUS,
                "last_heartbeat": 0.0,
                "consecutive_errors": 0,
                "items_checked": 0,
                "orders_confirmed": 0,
                "_degraded_armed": False,
            }

    def heartbeat(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["last_heartbeat"] = time.monotonic()

    def set_status(self, name: str, status: str) -> None:
        self._ensure(name)
        self._plugins[name]["status"] = status

    def record_error(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["consecutive_errors"] += 1

    def reset_errors(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["consecutive_errors"] = 0

    def inc_items_checked(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["items_checked"] += 1

    def inc_orders_confirmed(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["orders_confirmed"] += 1

    def is_degraded_armed(self, name: str) -> bool:
        self._ensure(name)
        return self._plugins[name]["_degraded_armed"]

    def arm_degraded(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["_degraded_armed"] = True

    def disarm_degraded(self, name: str) -> None:
        self._ensure(name)
        self._plugins[name]["_degraded_armed"] = False

    def get_snapshot(self) -> dict[str, dict]:
        """Return a deep copy of per-plugin records with private keys stripped."""
        return {
            name: {k: v for k, v in rec.items() if not k.startswith("_")}
            for name, rec in self._plugins.items()
        }
