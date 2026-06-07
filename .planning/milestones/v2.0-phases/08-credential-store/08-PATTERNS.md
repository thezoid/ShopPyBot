# Phase 8: Credential Store - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 14 (1 new module, 1 new test file, 1 config addition, 1 service hook, 11 migration sites)
**Analogs found:** 14 / 14

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `core/credentials.py` | service | request-response | `core/config_schema.py` | role-match (singleton init + pydantic-settings co-location) |
| `core/config_schema.py` (add `CredentialsConfig`) | config | request-response | `core/config_schema.py` (existing sub-models) | exact |
| `core/service.py` (call `init_store`) | service | request-response | `core/service.py` (`BotService.__init__`) | exact |
| `notifications/discord_notifier.py` (migrate os.environ) | service | request-response | `notifications/sms_notifier.py` | exact |
| `notifications/email_notifier.py` (migrate os.environ) | service | request-response | `notifications/sms_notifier.py` | exact |
| `notifications/sms_notifier.py` (migrate os.environ) | service | request-response | `notifications/sms_notifier.py` | exact (self) |
| `notifications/__init__.py` (migrate guard) | service | request-response | `notifications/__init__.py` | exact (self) |
| `plugins/shopbot_plugin_amazon.py` (migrate os.environ) | service | request-response | `plugins/shopbot_plugin_walmart.py` | exact |
| `plugins/shopbot_plugin_bestbuy.py` (migrate) | service | request-response | `plugins/shopbot_plugin_walmart.py` | exact |
| `plugins/shopbot_plugin_walmart.py` (migrate) | service | request-response | `plugins/shopbot_plugin_walmart.py` | exact (self) |
| `plugins/shopbot_plugin_target.py` (migrate) | service | request-response | `plugins/shopbot_plugin_walmart.py` | exact |
| `plugins/shopbot_plugin_gamestop.py` (migrate) | service | request-response | `plugins/shopbot_plugin_walmart.py` | exact |
| `plugins/shopbot_plugin_squareenix.py` (migrate) | service | request-response | `plugins/shopbot_plugin_walmart.py` | exact |
| `plugins/shopbot_plugin_newegg.py` (migrate) | service | request-response | `plugins/shopbot_plugin_walmart.py` | exact |
| `tests/test_credentials.py` | test | request-response | `tests/test_notifications.py` | role-match |

---

## Pattern Assignments

### `core/credentials.py` (new service module)

**Analog:** `core/config_schema.py` (module-level singleton + pydantic sub-model pattern) and `models.py` (data-dir path resolution)

**Imports pattern** (copy from `core/config_schema.py` lines 1-14, `models.py` lines 1-5):
```python
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

if TYPE_CHECKING:
    from core.config_schema import AppConfig
```

**Module-level singleton pattern** (modeled on `core/config_schema.py` lines 35-36, `threading.local` pattern):
```python
# Thread-safe singleton: _store is set once at startup before background thread launches.
# get_store() lazy-falls-back to EnvVarBackend so existing monkeypatch.setenv tests
# pass without calling init_store() (RESEARCH Pitfall 1).
_store: CredentialStore | None = None
_store_lock: threading.Lock = threading.Lock()
```

**Data-dir resolution** (modeled on `models.py` line 5 — project-relative `data/` convention):
```python
# Default: data/creds.bin (same directory as data/shop_py_bot.db — project convention)
# Override: credentials.data_dir config key, or SHOPBOT_STORE_PASSPHRASE env for file backend
_DEFAULT_STORE_PATH: Path = Path(__file__).parent.parent / "data" / "creds.bin"
```

**ABC interface** (from RESEARCH Pattern 1; no existing analog — new abstraction):
```python
class CredentialStore(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None: ...
    @abstractmethod
    def set(self, key: str, value: str) -> None: ...
    @abstractmethod
    def delete(self, key: str) -> None: ...
    @abstractmethod
    def list(self) -> list[str]: ...
```

**EnvVarBackend** (mirrors every existing `os.environ.get` call site — e.g. `notifications/sms_notifier.py` lines 58-60):
```python
class EnvVarBackend(CredentialStore):
    def get(self, key: str) -> str | None:
        return os.environ.get(key)

    def set(self, key: str, value: str) -> None:
        os.environ[key] = value

    def delete(self, key: str) -> None:
        os.environ.pop(key, None)

    def list(self) -> list[str]:
        return [k for k in SECRET_KEYS if k in os.environ]
```

**Error handling in backends** (modeled on `models.py` `get_db_connection` lines 8-28 — explicit exception propagation, never swallowed):
```python
# In EncryptedFileBackend._load():
try:
    ...
    return json.loads(plaintext)
except InvalidToken:
    raise ValueError(
        "Cannot decrypt credential store -- check SHOPBOT_STORE_PASSPHRASE"
    )
# Exceptions from keyring calls propagate; never catch BaseException
```

**init_store / get_store accessors** (modeled on `core/config_schema.py` `_yaml_path_local` thread-safety pattern, lines 35-36):
```python
def init_store(cfg: AppConfig) -> CredentialStore:
    global _store
    backend_name = getattr(getattr(cfg, "credentials", None), "backend", "auto")
    store = _build_store(backend_name, cfg)
    with _store_lock:
        _store = store
    return store

def get_store() -> CredentialStore:
    with _store_lock:
        if _store is None:
            return EnvVarBackend()   # lazy fallback keeps monkeypatch tests green
        return _store
```

**Startup logging** (modeled on `logger.py` / existing plugin log calls — `writeLog(msg, "INFO")`):
```python
from logger import writeLog

def _build_store(backend_name: str, cfg: AppConfig) -> CredentialStore:
    # ... backend selection logic ...
    writeLog(f"CredentialStore: {active_backend_label} backend active", "INFO")
    # NEVER: writeLog(f"CredentialStore: key={value}", ...) -- no secret values in logs
    return store
```

---

### `core/config_schema.py` (add `CredentialsConfig` sub-model)

**Analog:** `core/config_schema.py` — existing `DiscordConfig` (lines 148-151), `EmailConfig` (lines 154-163), `SmsConfig` (lines 166-185)

**Sub-model pattern** (copy from lines 148-151 — simplest sub-model with one field):
```python
# From core/config_schema.py lines 148-151 (DiscordConfig — one bool field):
class DiscordConfig(BaseModel):
    """Discord webhook notification config. Webhook URL is env-only (DISCORD_WEBHOOK_URL)."""
    enabled: bool = False
```

**New sub-model to add** (same pattern, placed alongside DiscordConfig/EmailConfig):
```python
class CredentialsConfig(BaseModel):
    """Credential store config. Secrets are NEVER stored here (CRED-06)."""

    backend: str = "auto"   # auto | keyring | file | env
    data_dir: str = ""      # empty = data/creds.bin (project-relative default)
```

**AppConfig field addition** (copy from `AppConfig` lines 207-212 — field declaration pattern):
```python
# Add to AppConfig body after `notifications: NotificationsConfig = NotificationsConfig()`:
credentials: CredentialsConfig = CredentialsConfig()
```

**SmsConfig validator — deliberate os.environ exception** (lines 172-185 — DO NOT migrate this):
```python
# core/config_schema.py lines 172-185 -- INTENTIONALLY left reading os.environ.
# AppConfig() construction runs BEFORE init_store(); this validator is a startup
# presence gate, not a secret consumer. See RESEARCH Pitfall 7.
@model_validator(mode="after")
def require_creds_if_enabled(self) -> "SmsConfig":
    if self.enabled:
        missing = [
            v for v in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM")
            if not os.environ.get(v)
        ]
        ...
```

---

### `core/service.py` (call `init_store` at startup)

**Analog:** `core/service.py` — `BotService.__init__` lines 31-37 (initialization block)

**Hook location — `BotService.__init__`** (lines 31-37 — add init_store after AppConfig construction):
```python
# core/service.py lines 31-37 (BotService.__init__):
def __init__(self, cfg: Optional[AppConfig] = None) -> None:
    self._cfg: AppConfig = cfg if cfg is not None else AppConfig()
    self._running: bool = False
    self._thread: Optional[threading.Thread] = None
    self._loop: Optional[asyncio.AbstractEventLoop] = None
    self._task: Optional[asyncio.Task] = None
    # ADD: init_store(self._cfg) here — before the background thread launches (RESEARCH note)
    # from core.credentials import init_store
    # init_store(self._cfg)
```

**Argparse hook for --migrate** (modeled on `main()` lines 140-153 — extend `parser` with a flag):
```python
# core/service.py lines 140-153 (main() entry point pattern):
def main() -> None:
    parser = argparse.ArgumentParser(...)
    parser.parse_known_args()     # <-- extend: add --migrate flag here
    # ADD:
    # args, _ = parser.parse_known_args()
    # if args.migrate:
    #     from core.credentials import migrate_from_env, get_store
    #     migrated = migrate_from_env(get_store())
    #     for key in migrated:
    #         print(f"Migrated: {key}")  # name only, never value
    #     return
```

---

### `notifications/discord_notifier.py` (migrate `os.environ["DISCORD_WEBHOOK_URL"]`)

**Analog:** `notifications/discord_notifier.py` line 66 (the call site itself)

**Current pattern** (line 66):
```python
# notifications/discord_notifier.py line 66:
self._webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
```

**Migration pattern** (replace with get_store — also handles KeyError-to-None pitfall from RESEARCH Pitfall 2):
```python
# Replace line 66 with:
from core.credentials import get_store
# ...
url = get_store().get("DISCORD_WEBHOOK_URL")
if not url:
    raise ValueError("DISCORD_WEBHOOK_URL not configured")
self._webhook_url = url
# Also remove: import os (if no other os usage in file)
```

**Import block** (lines 17-24 — add `from core.credentials import get_store`; remove `import os` if unused):
```python
# notifications/discord_notifier.py lines 17-24 (current):
import asyncio
import os          # <-- remove after migration if only used for os.environ["DISCORD_WEBHOOK_URL"]
import requests
from logger import writeLog
from notifications.base import Notifier, NotificationEvent
from datetime import timezone
```

---

### `notifications/email_notifier.py` (migrate `os.environ.get("SMTP_PASSWORD", "")`)

**Analog:** `notifications/email_notifier.py` line 69

**Current pattern** (line 69, inside `async def send`):
```python
# notifications/email_notifier.py line 69:
password = os.environ.get("SMTP_PASSWORD", "")
```

**Migration pattern**:
```python
# Replace line 69:
from core.credentials import get_store
# ...
password = get_store().get("SMTP_PASSWORD") or ""
```

Note: `os.environ.get` pattern with default `""` maps exactly to `get_store().get(...) or ""`.

---

### `notifications/sms_notifier.py` (migrate `os.environ.get` calls lines 58-60)

**Analog:** `notifications/sms_notifier.py` lines 58-60 (the call sites themselves)

**Current pattern** (lines 58-60, inside `async def send`):
```python
# notifications/sms_notifier.py lines 58-60:
account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
from_number = os.environ.get("TWILIO_FROM", "")
```

**Migration pattern**:
```python
from core.credentials import get_store
# ...
store = get_store()
account_sid = store.get("TWILIO_ACCOUNT_SID") or ""
auth_token = store.get("TWILIO_AUTH_TOKEN") or ""
from_number = store.get("TWILIO_FROM") or ""
```

---

### `notifications/__init__.py` (migrate presence guard line 44)

**Analog:** `notifications/__init__.py` line 44

**Current pattern** (line 44, inside `build_dispatcher`):
```python
# notifications/__init__.py line 44:
if notif.discord.enabled and os.environ.get("DISCORD_WEBHOOK_URL"):
```

**Migration pattern**:
```python
from core.credentials import get_store
# ...
if notif.discord.enabled and get_store().get("DISCORD_WEBHOOK_URL"):
```

---

### All 7 plugin files (migrate `os.environ.get` in `login()` methods)

**Analog:** `plugins/shopbot_plugin_walmart.py` lines 97-102 (login method credential block)

**Current pattern** (lines 97-102 — identical shape in all 7 plugins, only key names differ):
```python
# plugins/shopbot_plugin_walmart.py lines 97-102:
async def login(self) -> None:
    # SEC-01: credentials from env vars only -- never from config.yml or hardcoded.
    email = os.environ.get("WALMART_EMAIL", "")
    password = os.environ.get("WALMART_PASSWORD", "")
    # Guard: if credentials are missing, log and abort (never log their values).
    if not email or not password:
        writeLog("WALMART_EMAIL or WALMART_PASSWORD not set -- skipping login", "ERROR")
        return
```

**Migration pattern** (same guard structure, store replaces os.environ):
```python
from core.credentials import get_store
# ...
async def login(self) -> None:
    store = get_store()
    email = store.get("WALMART_EMAIL") or ""
    password = store.get("WALMART_PASSWORD") or ""
    if not email or not password:
        writeLog("WALMART_EMAIL or WALMART_PASSWORD not set -- skipping login", "ERROR")
        return
```

**Key name map for the 7 plugins:**

| Plugin file | Email key | Password key |
|---|---|---|
| `shopbot_plugin_amazon.py` lines 116-117 | `AMZ_EMAIL` | `AMZ_PASSWORD` |
| `shopbot_plugin_bestbuy.py` lines 81-82 | `BB_EMAIL` | `BB_PASSWORD` |
| `shopbot_plugin_walmart.py` lines 97-98 | `WALMART_EMAIL` | `WALMART_PASSWORD` |
| `shopbot_plugin_target.py` lines 99-100 | `TARGET_EMAIL` | `TARGET_PASSWORD` |
| `shopbot_plugin_gamestop.py` lines 99-100 | `GAMESTOP_EMAIL` | `GAMESTOP_PASSWORD` |
| `shopbot_plugin_squareenix.py` lines 98-99 | `SQUAREENIX_EMAIL` | `SQUAREENIX_PASSWORD` |
| `shopbot_plugin_newegg.py` lines 101-102 | `NEWEGG_EMAIL` | `NEWEGG_PASSWORD` |

---

### `tests/test_credentials.py` (new test file)

**Analog:** `tests/test_notifications.py` (test file structure) and `tests/conftest.py` (fixture patterns)

**File header and import pattern** (from `tests/test_notifications.py` lines 1-27 and `tests/test_plugin_amazon.py` lines 1-15):
```python
"""Tests for core/credentials.py (CRED-01..CRED-07).

Wave 0: all test stubs (test names match RESEARCH Validation Architecture table).
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
```

**monkeypatch.setenv usage pattern** (from `tests/test_notifications.py` lines 47-55 — existing env-var test pattern):
```python
# tests/test_notifications.py lines 47-55:
def test_sms_misconfigured_raises(monkeypatch):
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    ...

# Phase 8 tests follow the same pattern for env-var backend:
def test_env_backend_get(monkeypatch):
    from core.credentials import EnvVarBackend
    monkeypatch.setenv("AMZ_EMAIL", "test@example.com")
    backend = EnvVarBackend()
    assert backend.get("AMZ_EMAIL") == "test@example.com"
```

**tmp_path fixture for file backend** (from `tests/conftest.py` `tmp_data_dir` fixture line 25-29 — monkeypatch + tmp_path pattern):
```python
# tests/conftest.py lines 25-29 (tmp_data_dir — DB path redirect via monkeypatch.setattr):
@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    import models
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "shop_py_bot.db"))
    return tmp_path

# Phase 8 file backend tests use tmp_path directly (no monkeypatch needed):
def test_file_backend_roundtrip(tmp_path):
    from core.credentials import EncryptedFileBackend
    store = EncryptedFileBackend(tmp_path / "creds.bin", b"passphrase")
    store.set("AMZ_EMAIL", "x@example.com")
    assert store.get("AMZ_EMAIL") == "x@example.com"
    store.delete("AMZ_EMAIL")
    assert store.get("AMZ_EMAIL") is None
```

**Store isolation between tests** (modeled on `tests/test_notifications.py` use of monkeypatch.delenv — global state cleanup):
```python
# Reset the module-level _store singleton between tests that call init_store:
@pytest.fixture(autouse=False)
def reset_credential_store():
    from core import credentials
    original = credentials._store
    yield
    credentials._store = original
```

**Keyring in-memory test backend** (no existing codebase analog — copy from RESEARCH Pattern 8):
```python
# From RESEARCH.md Pattern 8 (keyring DictKeyring):
import keyring
from keyring.backend import KeyringBackend as _KBBase

class _DictKeyring(_KBBase):
    priority = 1
    def __init__(self): self._data: dict = {}
    def get_password(self, s, u): return self._data.get((s, u))
    def set_password(self, s, u, p): self._data[(s, u)] = p
    def delete_password(self, s, u): self._data.pop((s, u), None)

@pytest.fixture
def isolated_keyring():
    kb = _DictKeyring()
    keyring.set_keyring(kb)
    yield kb
    keyring.core._keyring_backend = None
```

---

## Shared Patterns

### Credential access (get_store().get)
**Source:** `notifications/sms_notifier.py` lines 58-60 (current os.environ.get pattern to replace)
**Apply to:** All 7 plugin `login()` methods, 3 notifier `__init__`/`send()` methods, `notifications/__init__.py` guard
**Pattern:** `store.get("KEY") or ""` replaces `os.environ.get("KEY", "")` one-for-one. `store.get("KEY")` with None-check replaces bare `os.environ["KEY"]`.

### Never-log-secret rule
**Source:** `notifications/discord_notifier.py` lines 76-82 (secret-safe error logging)
**Apply to:** `core/credentials.py` backends, all migrated notifiers and plugins
```python
# notifications/discord_notifier.py lines 76-82:
except requests.HTTPError as exc:
    # Secret-safe: log only class name + status, never str(exc) or URL.
    status = exc.response.status_code if exc.response is not None else "?"
    writeLog(f"[DiscordNotifier] HTTP {status} -- delivery failed", "ERROR")
    raise
```

### Guard-and-abort on missing credentials
**Source:** `plugins/shopbot_plugin_walmart.py` lines 97-102
**Apply to:** All plugin `login()` methods after migration
```python
if not email or not password:
    writeLog("WALMART_EMAIL or WALMART_PASSWORD not set -- skipping login", "ERROR")
    return
```

### Sub-model with defaults added to AppConfig
**Source:** `core/config_schema.py` lines 148-151, 207-212
**Apply to:** `CredentialsConfig` addition to `AppConfig`
```python
# Pattern: simple BaseModel sub-model with all-default fields, no validator needed
class DiscordConfig(BaseModel):
    enabled: bool = False
# Then in AppConfig body:
notifications: NotificationsConfig = NotificationsConfig()
```

### Data-dir path pattern
**Source:** `models.py` line 5 (`DB_PATH = os.path.join('data', 'shop_py_bot.db')`) and `core/config_schema.py` line 17 (`Path(__file__).parent.parent / "config.yml"`)
**Apply to:** `core/credentials.py` `_DEFAULT_STORE_PATH`
```python
# models.py line 5 (project-relative data dir):
DB_PATH = os.path.join('data', 'shop_py_bot.db')

# config_schema.py line 17 (absolute-path pattern using __file__):
_DEFAULT_YAML_PATH: Path = Path(__file__).parent.parent / "config.yml"

# For creds.bin: combine both patterns:
_DEFAULT_STORE_PATH: Path = Path(__file__).parent.parent / "data" / "creds.bin"
```

### Monkeypatch for global singletons
**Source:** `tests/conftest.py` lines 25-29 (`tmp_data_dir` uses `monkeypatch.setattr` to redirect DB_PATH)
**Apply to:** `tests/test_credentials.py` `reset_credential_store` fixture (reset `core.credentials._store` between tests)

---

## No Analog Found

All files have analogs within the codebase. The backend class bodies (KeyringBackend, EncryptedFileBackend) are new code with no existing analog; use RESEARCH.md Patterns 2 and 3 verbatim for those.

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `core/credentials.py` KeyringBackend class | service | request-response | No OS keyring integration exists in codebase; use RESEARCH.md Pattern 2 |
| `core/credentials.py` EncryptedFileBackend class | service | file-I/O | No encrypted file I/O exists in codebase; use RESEARCH.md Pattern 3 |

---

## Migration Site Summary

All 16 `os.environ` call sites to swap. The planner should treat these as atomic one-line changes per file:

| File | Line(s) | Change |
|---|---|---|
| `plugins/shopbot_plugin_amazon.py` | 116-117 | `os.environ.get("AMZ_EMAIL")` / `os.environ.get("AMZ_PASSWORD")` → `get_store().get(...)` |
| `plugins/shopbot_plugin_bestbuy.py` | 81-82 | `BB_EMAIL` / `BB_PASSWORD` → `get_store().get(...)` |
| `plugins/shopbot_plugin_walmart.py` | 97-98 | `WALMART_EMAIL` / `WALMART_PASSWORD` → `get_store().get(...)` |
| `plugins/shopbot_plugin_target.py` | 99-100 | `TARGET_EMAIL` / `TARGET_PASSWORD` → `get_store().get(...)` |
| `plugins/shopbot_plugin_gamestop.py` | 99-100 | `GAMESTOP_EMAIL` / `GAMESTOP_PASSWORD` → `get_store().get(...)` |
| `plugins/shopbot_plugin_squareenix.py` | 98-99 | `SQUAREENIX_EMAIL` / `SQUAREENIX_PASSWORD` → `get_store().get(...)` |
| `plugins/shopbot_plugin_newegg.py` | 101-102 | `NEWEGG_EMAIL` / `NEWEGG_PASSWORD` → `get_store().get(...)` |
| `notifications/discord_notifier.py` | 66 | `os.environ["DISCORD_WEBHOOK_URL"]` → `get_store().get(...)` with ValueError guard |
| `notifications/email_notifier.py` | 69 | `os.environ.get("SMTP_PASSWORD", "")` → `get_store().get(...) or ""` |
| `notifications/sms_notifier.py` | 58-60 | Three TWILIO_* calls → `store = get_store(); store.get(...)` |
| `notifications/__init__.py` | 44 | `os.environ.get("DISCORD_WEBHOOK_URL")` → `get_store().get(...)` |
| `core/config_schema.py` SmsConfig validator | 176-178 | **DO NOT MIGRATE** — deliberate os.environ exception (RESEARCH Pitfall 7) |

---

## Metadata

**Analog search scope:** `core/`, `notifications/`, `plugins/`, `tests/`, `models.py`
**Files read:** 14 source files + CONTEXT.md + RESEARCH.md
**Pattern extraction date:** 2026-06-04
