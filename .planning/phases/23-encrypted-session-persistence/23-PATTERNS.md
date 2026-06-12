# Phase 23: Encrypted Session Persistence - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 8 (6 modified, 2 new source + 2 new test files)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `core/session_store.py` | service | file-I/O | `core/credentials.py` (EncryptedFileBackend) | exact |
| `core/plugin_base.py` | base-class | request-response | `core/plugin_base.py` (restore_session stub + relaunch) | self-edit, exact |
| `core/config_schema.py` | config | -- | `core/config_schema.py` (headless bool fields) | self-edit, exact |
| `core/registry.py` | orchestrator | request-response | `core/registry.py` (setup_for_items loop) | self-edit, exact |
| `plugins/shopbot_plugin_amazon.py` | plugin | request-response | `plugins/shopbot_plugin_bestbuy.py` login() | role-match |
| `plugins/shopbot_plugin_bestbuy.py` | plugin | request-response | `plugins/shopbot_plugin_amazon.py` login() | role-match |
| `tests/test_session_store.py` | test | -- | `tests/test_credentials.py` (EncryptedFileBackend tests) | exact |
| `tests/test_no_committed_sessions.py` | test (CI guard) | -- | `tests/test_no_plaintext.py` (file-scan pattern) | role-match |

## Pattern Assignments

### `core/session_store.py` (service, file-I/O)

**Analog:** `core/credentials.py` lines 217-281

**Imports pattern** (lines 15-31 of credentials.py):
```python
from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from core.paths import data_dir as _paths_data_dir
```

**KDF constants to import/reuse** (lines 86-89 of credentials.py):
```python
# Import these from core.credentials -- do NOT redeclare
from core.credentials import SALT_LEN, _derive_key
```

**Core save pattern** (lines 265-281 of credentials.py -- `EncryptedFileBackend._save`):
```python
def _save(self, secrets: dict[str, str]) -> None:
    salt = os.urandom(SALT_LEN)
    key = _derive_key(self._passphrase, salt)
    token = Fernet(key).encrypt(json.dumps(secrets).encode())
    dir_ = self._path.parent
    dir_.mkdir(parents=True, exist_ok=True)   # BEFORE mkstemp (Pitfall 6)
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
```

**Core load pattern** (lines 251-263 of credentials.py -- `EncryptedFileBackend._load`):
```python
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
```

**Passphrase resolution pattern** (lines 323-334 of credentials.py):
```python
def _resolve_passphrase() -> bytes | None:
    val = os.environ.get("SHOPBOT_STORE_PASSPHRASE")
    if val:
        return val.encode()
    return None
```

**SessionStore adaptations from the analog:**
- Replace `dict[str, str]` with `list[dict]` (cookie list not secrets dict)
- Replace single `self._path` with `self._session_path(platform)` returning `data/sessions/<platform>.bin`
- On `InvalidToken` in `restore()`: return `None` (do NOT raise -- silent fallback is the contract)
- No `threading.Lock` needed (one writer post-login, one reader at startup; not concurrent)
- `save()` and `restore()` are no-ops when `self._passphrase is None`

**File location:** `data_dir() / "sessions" / f"{platform}.bin"` (mirrors `_paths_data_dir() / "creds.bin"`)

---

### `core/plugin_base.py` (base-class, request-response)

**Analog:** self -- lines 159-172 (relaunch + existing stub)

**Existing restore_session stub to replace** (lines 166-172):
```python
async def restore_session(self) -> bool:
    """Restore browser session from encrypted cookies. No-op stub for Phase 22.

    Returns False always. Phase 23 (REL-04) replaces with Fernet cookie restore.
    PLUGIN_API_VERSION stays 2 -- additive non-abstract method.
    """
    return False
```

**Existing relaunch sequence showing where save_session is NOT yet called** (lines 148-165):
```python
async def relaunch(self) -> None:
    ...
    await self.setup()
    session_restored = await self.restore_session()
    if not session_restored:
        writeLog(f"[{plugin_name}] restore_session=False; re-logging in", "INFO")
        await self.login()
    else:
        writeLog(f"[{plugin_name}] relaunch: session restored; skipping login", "INFO")
```

**get_active_tab pattern** (lines 87-94) -- used by both save_session and restore_session:
```python
def get_active_tab(self):
    return getattr(self.driver, "main_tab", None)
```

**Config getattr-safe read pattern** (lines 111-113 of place_order_guarded):
```python
debug = getattr(self.config, "debug", None) if self.config else None
test_mode = getattr(debug, "test_mode", True)
```
Apply same pattern for `session_persistence`:
```python
platform_cfg = getattr(getattr(self.config, "platforms", None), self._platform_key, None)
if not getattr(platform_cfg, "session_persistence", False):
    return
```

**New save_session signature to add after restore_session:**
```python
async def save_session(self) -> None:
    """Save browser cookies after successful login (when session_persistence enabled).

    No-op when session_persistence is False or passphrase absent.
    PLUGIN_API_VERSION stays 2 -- additive non-abstract method (REL-04).
    """
```

---

### `core/config_schema.py` (config)

**Analog:** self -- existing `headless: bool = True` and `enabled: bool = False` fields

**Pattern for bool field with default** (lines 74, 83, 92, 101, 109, 117, 129 -- one per platform):
```python
class AmazonPlatformConfig(BaseModel):
    delay_seconds: float = 30.0
    delay_jitter: float = 10.0
    headless: bool = True           # <-- existing opt-in bool field: exact pattern to copy
    user_agents: list[str] = Field(default_factory=list)
    session_persistence: bool = False  # <-- ADD: same pattern, default off (opt-in)
```

**All 7 models to modify:** AmazonPlatformConfig (line 67), BestBuyPlatformConfig (line 78), WalmartPlatformConfig (line 87), TargetPlatformConfig (line 96), GameStopPlatformConfig (line 105), SquareEnixPlatformConfig (line 114), NeweggPlatformConfig (line 126). Each gets an identical `session_persistence: bool = False` line appended to its field list.

---

### `core/registry.py` (orchestrator, request-response)

**Analog:** self -- `setup_for_items` loop lines 138-159

**Current loop to extend** (lines 154-159 of registry.py):
```python
for plugin in needed:
    try:
        await plugin.setup()
        self._active_plugins.append(plugin)
    except Exception as exc:
        writeLog(f"Plugin setup failed: {exc} -- skipping", "WARNING")
```

**Extension pattern** -- mirror relaunch() lines 159-164 of plugin_base.py:
```python
for plugin in needed:
    try:
        await plugin.setup()
        self._active_plugins.append(plugin)
        session_restored = await plugin.restore_session()
        if session_restored:
            writeLog(f"[{plugin.__class__.__name__}] startup: session restored; skipping login", "INFO")
        else:
            await plugin.login()
    except Exception as exc:
        writeLog(f"Plugin setup failed: {exc} -- skipping", "WARNING")
```

Note: The `login()` call moves from the orchestrator/bot-service into this loop, mirroring `relaunch()`. Verify with `core/service.py` where `login()` is currently called to avoid double-login.

---

### `plugins/shopbot_plugin_amazon.py` (plugin, request-response)

**Analog:** `plugins/shopbot_plugin_bestbuy.py` login() -- same pattern applies symmetrically

**Hook point in amazon login()** (line 360 of amazon plugin):
```python
writeLog("Signed in to Amazon", "INFO")
# ADD HERE:
await self.save_session()
```

The call goes immediately after the success log, before the except clause. `save_session()` on the ABC is a no-op when `session_persistence=False` or passphrase absent, so no config guard is needed at the call site.

---

### `plugins/shopbot_plugin_bestbuy.py` (plugin, request-response)

**Hook point in bestbuy login()** (line 249 of bestbuy plugin):
```python
writeLog("Signed in to BestBuy", "INFO")
# ADD HERE:
await self.save_session()
```

Same pattern as Amazon: single line addition after success log.

---

### `tests/test_session_store.py` (test)

**Analog:** `tests/test_credentials.py` (EncryptedFileBackend tests, lines 195-228)

**Round-trip test pattern** (lines 195-204):
```python
def test_file_backend(tmp_path):
    """EncryptedFileBackend round-trip: set/get/delete/list."""
    from core.credentials import EncryptedFileBackend

    store = EncryptedFileBackend(tmp_path / "creds.bin", b"test-passphrase")
    store.set("AMZ_EMAIL", "file@example.com")
    assert store.get("AMZ_EMAIL") == "file@example.com"
```

**Adapt to SessionStore:**
```python
def test_save_restore_roundtrip(tmp_path):
    from core.session_store import SessionStore

    cookies = [{"name": "session-id", "value": "abc123", "domain": ".amazon.com",
                "path": "/", "expires": None, "http_only": True, "secure": True,
                "same_site": "None"}]
    store = SessionStore(tmp_path / "sessions", b"test-passphrase")
    store.save("amazon", cookies)
    result = store.restore("amazon")
    assert result == cookies
```

**No-plaintext test pattern** (lines 207-215 of test_credentials.py):
```python
def test_encrypted_file_is_not_plaintext(tmp_path):
    store_path = tmp_path / "creds.bin"
    store = EncryptedFileBackend(store_path, b"test-passphrase")
    store.set("AMZ_EMAIL", "mytest@example.com")
    raw = store_path.read_bytes()
    assert b"mytest@example.com" not in raw
```

**Wrong-passphrase / InvalidToken pattern** (lines 218-227 of test_credentials.py):
```python
def test_file_backend_wrong_passphrase(tmp_path):
    store = EncryptedFileBackend(tmp_path / "creds.bin", b"correct-passphrase")
    store.set("AMZ_EMAIL", "secret@example.com")
    bad = EncryptedFileBackend(tmp_path / "creds.bin", b"wrong-passphrase")
    with pytest.raises(ValueError, match="SHOPBOT_STORE_PASSPHRASE"):
        bad.get("AMZ_EMAIL")
```

**Adapt for SessionStore** (restore returns None, does not raise):
```python
def test_restore_wrong_passphrase(tmp_path):
    store = SessionStore(tmp_path / "sessions", b"correct")
    store.save("amazon", [{"name": "x", "value": "y"}])
    bad = SessionStore(tmp_path / "sessions", b"wrong")
    assert bad.restore("amazon") is None   # never raises
```

**ABC hook no-op test pattern** -- from `tests/test_relaunch.py` lines 18-55 (AsyncMock + side_effect recording):
```python
plugin.restore_session = AsyncMock(side_effect=_restore_session_side_effect)
plugin.login = AsyncMock(side_effect=_login_side_effect)
```

---

### `tests/test_no_committed_sessions.py` (CI guard test)

**Analog:** `tests/test_no_plaintext.py` (file-scan pattern, lines 33-86)

**File-scan skip pattern** (lines 33-43 of test_no_plaintext.py):
```python
def test_no_plaintext_secrets_in_config_yml():
    config_path = Path("config.yml")
    if not config_path.exists():
        pytest.skip("config.yml not present in this environment")
    content = config_path.read_text(errors="replace")
    for key, val in _non_trivial_secret_values():
        assert val not in content, ...
```

**Git-tracked files check pattern** -- use `subprocess.run(["git", "ls-files", "data/sessions/"])`:
```python
import subprocess

def test_no_committed_session_files():
    """No data/sessions/*.bin file is git-tracked."""
    result = subprocess.run(
        ["git", "ls-files", "data/sessions/"],
        capture_output=True, text=True, check=True,
    )
    tracked = [line for line in result.stdout.splitlines() if line.endswith(".bin")]
    assert tracked == [], f"Session files are git-tracked: {tracked}"

def test_sessions_dir_gitignored():
    """data/sessions/ is covered by .gitignore."""
    gitignore = Path(".gitignore").read_text()
    # data/* rule covers data/sessions/
    assert "data/*" in gitignore or "data/sessions" in gitignore
```

---

## Shared Patterns

### Passphrase Resolution
**Source:** `core/credentials.py` lines 323-334 (`_resolve_passphrase`)
**Apply to:** `core/session_store.py` SessionStore init and `core/plugin_base.py` save_session/restore_session
```python
val = os.environ.get("SHOPBOT_STORE_PASSPHRASE")
return val.encode() if val else None
```
Import `_resolve_passphrase` from `core.credentials` rather than duplicating.

### Fernet + scrypt KDF
**Source:** `core/credentials.py` lines 217-223 (`_derive_key`) and lines 86-89 (constants)
**Apply to:** `core/session_store.py`
```python
from core.credentials import _derive_key, SALT_LEN
```
Do not redeclare `SCRYPT_N/R/P` or `SALT_LEN`. Single source of truth.

### Getattr-safe config read
**Source:** `core/plugin_base.py` lines 111-113 (`place_order_guarded`)
**Apply to:** `save_session()` and `restore_session()` in plugin_base.py
```python
platform_cfg = getattr(getattr(self.config, "platforms", None), self._platform_key, None)
if not getattr(platform_cfg, "session_persistence", False):
    return  # False / None -- fall through to login
```

### Additive ABC method (no API bump)
**Source:** `core/plugin_base.py` lines 78-94 (`get_price`, `get_active_tab`)
**Apply to:** `save_session()` and updated `restore_session()` in plugin_base.py
Docstring must contain: "PLUGIN_API_VERSION stays 2 -- additive non-abstract method (REL-04)."

### Error logging (class name only, never passphrase)
**Source:** `core/credentials.py` line 392 (`_log_backend`)
**Apply to:** `core/session_store.py` on any decrypt/IO error
```python
writeLog(f"SessionStore: {exc.__class__.__name__} restoring {platform}; falling back to login", "WARNING")
# Never log passphrase value or cookie values
```

### Atomic file write (Windows-safe)
**Source:** `core/credentials.py` lines 265-281 (`EncryptedFileBackend._save`)
**Apply to:** `SessionStore.save()`
fd must be closed inside the `with os.fdopen` block; `os.replace` runs AFTER the with-block closes the fd. This is the Windows-safe ordering (Pitfall 6 in RESEARCH).

## No Analog Found

None. All 8 files have a direct analog in the codebase.

## Metadata

**Analog search scope:** `core/`, `plugins/`, `tests/`
**Files scanned:** 9 source files read in full
**Pattern extraction date:** 2026-06-12
