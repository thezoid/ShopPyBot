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
import getpass
import json
import os
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

import keyring
from keyring.backends import fail as _keyring_fail
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from logger import writeLog

if TYPE_CHECKING:
    from core.config_schema import AppConfig

from core.paths import data_dir as _paths_data_dir

# ---------------------------------------------------------------------------
# Default data directory anchored via core/paths.py (XPLAT-01)
# ---------------------------------------------------------------------------
_DEFAULT_STORE_PATH: Path = _paths_data_dir() / "creds.bin"

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
    """Return True only when a functional OS keyring is available.

    Type-checks against fail.Keyring and null.Keyring first (fast path).
    Then performs a functional round-trip probe to handle ChainerBackend
    wrapping only fail/null leaves (e.g. headless Linux, CI boxes) where
    the chain is neither type but still no-ops on set/get (WR-01).
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
    # Functional probe: confirm the backend can actually round-trip a value.
    # This catches ChainerBackend composed entirely of fail/null leaves.
    # Uses "shopbot-probe" service (not "shopbot") so a leaked entry never
    # collides with real secrets. Cleanup is in finally to guarantee best-effort
    # deletion even when set/get raises; delete failure does not propagate.
    ok = False
    try:
        keyring.set_password("shopbot-probe", "__probe__", "1")
        ok = keyring.get_password("shopbot-probe", "__probe__") == "1"
    except Exception:
        return False
    finally:
        try:
            keyring.delete_password("shopbot-probe", "__probe__")
        except Exception:
            pass
    return ok


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
        self._lock: threading.Lock = threading.Lock()

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
        with self._lock:
            secrets = self._load()
            secrets[key] = value
            self._save(secrets)

    def delete(self, key: str) -> None:
        with self._lock:
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


def _resolve_passphrase() -> bytes | None:
    """Return the store passphrase as bytes, or None if not available.

    Reads SHOPBOT_STORE_PASSPHRASE from the environment.
    Does NOT call getpass.getpass() here -- getpass is only called in
    _build_store when the file backend is explicitly required (not during
    auto-detect probing) to avoid blocking the event loop (RESEARCH Pitfall 3).
    """
    val = os.environ.get("SHOPBOT_STORE_PASSPHRASE")
    if val:
        return val.encode()
    return None


def _build_store(backend_name: str, cfg: AppConfig) -> CredentialStore:
    """Select and construct the backend by precedence (CRED-05).

    Precedence:
      explicit cfg.credentials.backend in {keyring, file, env}
        -> build that backend directly, ignoring auto-detect
      'auto':
        1. KeyringBackend if _has_real_keyring()
        2. EncryptedFileBackend if SHOPBOT_STORE_PASSPHRASE is set
        3. EnvVarBackend (fallback)

    Logs the active backend NAME only -- never a secret value (T-08-09).
    """
    store_path = (
        Path(cfg.credentials.data_dir) / "creds.bin"
        if getattr(cfg.credentials, "data_dir", "")
        else _DEFAULT_STORE_PATH
    )

    if backend_name == "keyring":
        store = KeyringBackend()
        _log_backend("keyring")
        return store

    if backend_name == "env":
        store = EnvVarBackend()
        _log_backend("env-var")
        return store

    if backend_name == "file":
        passphrase = _resolve_passphrase()
        if passphrase is None:
            passphrase = getpass.getpass(
                "ShopPyBot credential store passphrase: "
            ).encode()
        store = EncryptedFileBackend(store_path, passphrase)
        _log_backend("encrypted-file")
        return store

    # auto-detect path
    if _has_real_keyring():
        _log_backend("keyring")
        return KeyringBackend()

    passphrase = _resolve_passphrase()
    if passphrase is not None:
        _log_backend("encrypted-file")
        return EncryptedFileBackend(store_path, passphrase)

    _log_backend("env-var")
    return EnvVarBackend()


def _log_backend(label: str) -> None:
    """Emit startup log with active backend label only -- never a secret value."""
    writeLog(f"CredentialStore: {label} backend active", "INFO")


def migrate_from_env(store: CredentialStore) -> list[str]:
    """Write each set env-var secret into store. Return list of migrated key NAMES.

    Reads SECRET_KEYS from os.environ; for each that is set, calls store.set(key, val)
    then verifies the write via store.get(key) before appending the key NAME to the
    returned list. If the read-back fails (no-op backend), the key is skipped and a
    warning is logged (WR-06). The value is never printed, logged, or included in
    the return value (T-08-14 / CRED-07).
    """
    migrated: list[str] = []
    for key in SECRET_KEYS:
        val = os.environ.get(key)
        if val:
            try:
                store.set(key, val)
                if store.get(key) is not None:
                    migrated.append(key)   # name only -- never the value
                else:
                    writeLog(
                        f"migrate_from_env: {key} set failed (backend returned None on read-back)",
                        "WARNING",
                    )
            except Exception as exc:
                writeLog(
                    f"migrate_from_env: {key} set raised {exc.__class__.__name__}",
                    "WARNING",
                )
    return migrated


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
