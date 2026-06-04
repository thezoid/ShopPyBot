"""Credential store abstraction (Phase 8 -- CRED-01..CRED-07).

Exposes:
    CredentialStore  -- ABC with get/set/delete/list
    EnvVarBackend    -- identity fallback; reads os.environ (CRED-04)
    SECRET_KEYS      -- 19 canonical secret key names (CRED-01)
    get_store()      -- returns process-wide store; lazy-falls-back to EnvVarBackend
    init_store(cfg)  -- called once at startup to set the process-wide store

Backends added in later plans:
    KeyringBackend       -- plan 08-02 (CRED-02)
    EncryptedFileBackend -- plan 08-03 (CRED-03)

Selection logic (auto-detect) -- plan 08-03 (CRED-05).
"""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config_schema import AppConfig

# ---------------------------------------------------------------------------
# Default data directory (project-relative, consistent with data/shop_py_bot.db)
# ---------------------------------------------------------------------------
_DEFAULT_STORE_PATH: Path = Path(__file__).parent.parent / "data" / "creds.bin"

# ---------------------------------------------------------------------------
# 19 canonical secret key names (CRED-01 -- mirrors existing os.environ call sites)
# ---------------------------------------------------------------------------
SECRET_KEYS: list[str] = [
    # Notifications
    "DISCORD_WEBHOOK_URL",
    "SMTP_PASSWORD",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_FROM",
    # Amazon
    "AMZ_EMAIL",
    "AMZ_PASSWORD",
    # BestBuy
    "BB_EMAIL",
    "BB_PASSWORD",
    # Walmart
    "WALMART_EMAIL",
    "WALMART_PASSWORD",
    # Target
    "TARGET_EMAIL",
    "TARGET_PASSWORD",
    # GameStop
    "GAMESTOP_EMAIL",
    "GAMESTOP_PASSWORD",
    # Square Enix
    "SQUAREENIX_EMAIL",
    "SQUAREENIX_PASSWORD",
    # Newegg
    "NEWEGG_EMAIL",
    "NEWEGG_PASSWORD",
]


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class CredentialStore(ABC):
    """Protocol for all credential backends."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Return the secret value for key, or None if not present."""

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        """Store key -> value in the backend."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove key from the backend (no-op if absent)."""

    @abstractmethod
    def list(self) -> list[str]:
        """Return the list of keys currently stored in this backend."""


# ---------------------------------------------------------------------------
# EnvVarBackend: identity fallback -- reads/writes os.environ (CRED-04)
# ---------------------------------------------------------------------------


class EnvVarBackend(CredentialStore):
    """Read secrets from os.environ.

    This is the identity-preserving fallback: all existing monkeypatch.setenv
    tests pass through this backend without modification (CRED-04).
    """

    def get(self, key: str) -> str | None:
        return os.environ.get(key)

    def set(self, key: str, value: str) -> None:
        os.environ[key] = value

    def delete(self, key: str) -> None:
        os.environ.pop(key, None)

    def list(self) -> list[str]:
        return [k for k in SECRET_KEYS if k in os.environ]


# ---------------------------------------------------------------------------
# Module-level singleton + thread-safe accessors
# ---------------------------------------------------------------------------

_store: CredentialStore | None = None
_store_lock: threading.Lock = threading.Lock()


def get_store() -> CredentialStore:
    """Return the process-wide CredentialStore.

    If init_store() has not been called (e.g. during tests that never call it),
    returns a fresh EnvVarBackend so that monkeypatch.setenv tests remain green
    without modification (RESEARCH Pitfall 1).
    """
    with _store_lock:
        if _store is None:
            return EnvVarBackend()
        return _store


def _build_store(backend_name: str, cfg: AppConfig) -> CredentialStore:
    """Select and construct the appropriate backend.

    Stub in plan 08-01: always returns EnvVarBackend.
    Selection logic (auto-detect: keyring -> file -> env) is filled in plan 08-03.
    """
    # plan 08-03 will implement: keyring auto-detect, file backend w/ passphrase
    return EnvVarBackend()


def init_store(cfg: AppConfig) -> CredentialStore:
    """Initialize the process-wide CredentialStore from AppConfig.

    Call once at startup (e.g. BotService.__init__) before the background thread
    launches. Thread-safe: uses _store_lock to prevent races on the singleton.
    """
    global _store
    backend_name = getattr(getattr(cfg, "credentials", None), "backend", "auto")
    store = _build_store(backend_name, cfg)
    with _store_lock:
        _store = store
    return store
