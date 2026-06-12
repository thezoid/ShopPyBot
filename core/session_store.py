"""Encrypted session/cookie persistence (Phase 23 -- REL-04).

Exposes:
    SessionStore          -- Fernet save/restore of a cookie list per platform
    build_session_store() -- constructs SessionStore with env-resolved passphrase

File format: data/sessions/<platform>.bin
    [SALT_LEN bytes random salt][Fernet token of JSON-encoded cookie list]

Mirrors EncryptedFileBackend from core/credentials.py. Reuses _derive_key and
SALT_LEN (single source of truth -- do NOT redeclare scrypt params here).

When passphrase is None (SHOPBOT_STORE_PASSPHRASE absent), both save() and
restore() are silent no-ops; restore() returns None. Never writes plaintext.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from core.credentials import SALT_LEN, _derive_key, _resolve_passphrase
from core.paths import data_dir
from logger import writeLog


class SessionStore:
    """Save and restore a per-platform cookie list as a Fernet-encrypted file.

    File layout: [SALT_LEN bytes salt][Fernet token of JSON cookie list]
    Mirrors EncryptedFileBackend._save / ._load from core/credentials.py.
    """

    def __init__(
        self,
        sessions_dir: Path | None = None,
        passphrase: bytes | None = None,
    ) -> None:
        self._dir = Path(sessions_dir) if sessions_dir is not None else data_dir() / "sessions"
        self._passphrase = passphrase

    def _session_path(self, platform: str) -> Path:
        return self._dir / f"{platform}.bin"

    def save(self, platform: str, cookies: list[dict]) -> None:
        """Encrypt and write cookies to data/sessions/<platform>.bin.

        No-op when passphrase is None (persistence disabled -- no plaintext fallback).
        Atomic write: tempfile + os.replace (Windows-safe, mirrors credentials.py Pitfall 6).
        """
        if self._passphrase is None:
            return
        salt = os.urandom(SALT_LEN)
        key = _derive_key(self._passphrase, salt)
        token = Fernet(key).encrypt(json.dumps(cookies).encode())
        path = self._session_path(platform)
        self._dir.mkdir(parents=True, exist_ok=True)   # BEFORE mkstemp (Pitfall 6)
        fd, tmp = tempfile.mkstemp(dir=str(self._dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(salt + token)
            os.replace(tmp, path)                        # fd closed before replace (Windows)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def restore(self, platform: str) -> list[dict] | None:
        """Decrypt and return cookie list, or None on any failure.

        Returns None (never raises) on: passphrase absent, missing file,
        corrupt/truncated data, or wrong passphrase (InvalidToken).
        """
        if self._passphrase is None:
            return None
        path = self._session_path(platform)
        if not path.exists():
            return None
        data = path.read_bytes()
        salt, token = data[:SALT_LEN], data[SALT_LEN:]
        key = _derive_key(self._passphrase, salt)
        try:
            plaintext = Fernet(key).decrypt(token)
            return json.loads(plaintext)
        except Exception as exc:
            # Includes Fernet.InvalidToken (wrong passphrase or truncated data)
            writeLog(
                f"SessionStore: {exc.__class__.__name__} restoring {platform};"
                " falling back to login",
                "WARNING",
            )
            return None


def build_session_store() -> SessionStore:
    """Construct a SessionStore with the env-resolved passphrase.

    Callers (Plan 23-04 plugin ABC) use this to avoid duplicating passphrase
    resolution logic. Returns a disabled store when SHOPBOT_STORE_PASSPHRASE
    is absent (passphrase=None).
    """
    return SessionStore(passphrase=_resolve_passphrase())
