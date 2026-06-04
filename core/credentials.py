"""Credential store abstraction (Phase 8 -- CRED-01..CRED-07).

Exposes:
    CredentialStore      -- ABC with get/set/delete/list
    EnvVarBackend        -- identity fallback; reads os.environ (CRED-04)
    KeyringBackend       -- OS secret service via keyring lib (CRED-02)
    EncryptedFileBackend -- Fernet + scrypt encrypted file (CRED-03)
    SECRET_KEYS          -- 19 canonical secret key names (CRED-01)
    get_store()          -- returns process-wide store; lazy-falls-back to EnvVarBackend
    init_store(cfg)      -- called once at startup to set the process-wide store

Selection logic (auto-detect) -- plan 08-03 (CRED-05).
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

import keyring
import keyring.core
from keyring.backends import fail as _keyring_fail
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

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
# Scrypt KDF constants (CRED-03 / RFC 7914 recommended interactive-login params)
# ---------------------------------------------------------------------------
SCRYPT_N: int = 2**14   # ~100ms on modern hardware; memory-hard
SCRYPT_R: int = 8
SCRYPT_P: int = 1
SALT_LEN: int = 16


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
# _has_real_keyring: guard against null/fail backends (CRED-02 / T-08-06)
# ---------------------------------------------------------------------------


def _has_real_keyring() -> bool:
    """Return True only when a non-null, non-fail OS keyring is available.

    keyring.backends.fail.Keyring is the default when no OS backend is found.
    keyring.backends.null.Keyring is the explicit no-op backend.
    Both are treated as absent (RESEARCH Pattern 2 / Pitfall 5).
    """
    backend = keyring.get_keyring()
    if isinstance(backend, _keyring_fail.Keyring):
        return False
    try:
        from keyring.backends.null import Keyring as _NullKeyring
        if isinstance(backend, _NullKeyring):
            return False
    except ImportError:
        pass
    return True


# ---------------------------------------------------------------------------
# KeyringBackend: OS secret service via keyring lib (CRED-02)
# ---------------------------------------------------------------------------


class KeyringBackend(CredentialStore):
    """Store secrets in the OS keyring (Windows Credential Manager on win32).

    SERVICE is the keyring service name; all keys live under "shopbot".
    keyring has no enumerate API, so list() probes each known SECRET_KEY
    individually (RESEARCH Pitfall 5).
    """

    SERVICE = "shopbot"

    def get(self, key: str) -> str | None:
        return keyring.get_password(self.SERVICE, key)

    def set(self, key: str, value: str) -> None:
        keyring.set_password(self.SERVICE, key, value)

    def delete(self, key: str) -> None:
        keyring.delete_password(self.SERVICE, key)

    def list(self) -> list[str]:
        # keyring has no enumerate API; intersection of known keys that have values
        return [k for k in SECRET_KEYS if keyring.get_password(self.SERVICE, k) is not None]


# ---------------------------------------------------------------------------
# _derive_key: scrypt KDF helper used by EncryptedFileBackend
# ---------------------------------------------------------------------------


def _derive_key(passphrase: bytes, salt: bytes) -> bytes:
    """Derive a 32-byte URL-safe-b64-encoded Fernet key from passphrase + salt.

    Uses scrypt n=2**14 / r=8 / p=1 (RFC 7914 interactive-login parameters).
    """
    kdf = Scrypt(salt=salt, length=32, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return base64.urlsafe_b64encode(kdf.derive(passphrase))


# ---------------------------------------------------------------------------
# EncryptedFileBackend: Fernet AES-128-CBC + HMAC, key from scrypt (CRED-03)
# ---------------------------------------------------------------------------


class EncryptedFileBackend(CredentialStore):
    """Store secrets in a binary file encrypted with Fernet (AES-128-CBC + HMAC).

    File format: [SALT_LEN bytes random salt][Fernet token of JSON-encoded dict]

    The passphrase is never written to disk. On decryption failure (wrong
    passphrase or corrupted file) raises a clear ValueError naming only the
    env-var SHOPBOT_STORE_PASSPHRASE, never a raw cryptography exception
    (RESEARCH Pitfall 4 / T-08-08).

    Atomic write: tempfile.mkstemp + fd closed inside with-block, then
    os.replace outside the with-block so the fd is closed before replace
    on Windows (RESEARCH Pitfall 6 / T-08-07).
    """

    def __init__(self, path: Path, passphrase: bytes) -> None:
        self._path = path
        self._passphrase = passphrase

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        data = self._path.read_bytes()
        salt, token = data[:SALT_LEN], data[SALT_LEN:]
        key = _derive_key(self._passphrase, salt)
        try:
            plaintext = Fernet(key).decrypt(token)
        except InvalidToken:
            raise ValueError(
                "Cannot decrypt credential store -- check SHOPBOT_STORE_PASSPHRASE"
            )
        return json.loads(plaintext)

    def _save(self, secrets: dict[str, str]) -> None:
        salt = os.urandom(SALT_LEN)
        key = _derive_key(self._passphrase, salt)
        token = Fernet(key).encrypt(json.dumps(secrets).encode())
        dir_ = self._path.parent
        dir_.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(dir_))
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(salt + token)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def get(self, key: str) -> str | None:
        return self._load().get(key)

    def set(self, key: str, value: str) -> None:
        secrets = self._load()
        secrets[key] = value
        self._save(secrets)

    def delete(self, key: str) -> None:
        secrets = self._load()
        secrets.pop(key, None)
        self._save(secrets)

    def list(self) -> list[str]:
        return list(self._load().keys())


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
