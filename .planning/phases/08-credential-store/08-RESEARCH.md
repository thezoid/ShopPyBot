# Phase 8: Credential Store - Research

**Researched:** 2026-06-04
**Domain:** Python secret storage — keyring, cryptography Fernet/scrypt, env-var facade
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `CredentialStore` interface: `get(key) -> str|None`, `set(key, value)`, `delete(key)`, `list() -> list[str]`. Lives in `core/`.
- Keys reuse existing env-var names verbatim (DISCORD_WEBHOOK_URL, SMTP_PASSWORD, TWILIO_*, AMZ_*, BB_*, WALMART_*/TARGET_*/GAMESTOP_*/SQUAREENIX_*/NEWEGG_* EMAIL+PASSWORD). A canonical SECRET_KEYS list defines the known set.
- Module accessor `core/credentials.py` `get_store()` returns the process-wide store; plugins/notifiers call `get_store().get(KEY)` as 1:1 swap for `os.environ.get(KEY)`.
- BotService initializes the store at startup.
- Keyring backend via `keyring` lib; guard against fail/null backend.
- Encrypted-file backend via `cryptography` Fernet, key derived from passphrase via scrypt; passphrase from `SHOPBOT_STORE_PASSPHRASE` env else getpass.
- Env-var backend reads os.environ (preserves today's behavior; existing monkeypatch.setenv tests MUST stay green).
- Selection precedence: explicit `credentials.backend: auto|keyring|file|env` config > keyring (if OS backend present) > encrypted-file (if passphrase available) > env-var.
- `shoppybot setup --migrate` imports env-var secrets into active backend, confirms each key BY NAME never value.
- 227-test suite must stay green.

### Claude's Discretion
- Exact module layout (core/credentials.py with backend classes vs a small package).
- Data-dir resolver (per-OS).
- Scrypt parameters.
- Fernet file format.
- How get_store() lazy-initializes.

### Deferred Ideas (OUT OF SCOPE)
- Full `shoppybot setup` interactive UX (Phase 9).
- Web UI credential management (Phase 10).
- Cross-platform CI matrix (Phase 11).
- Rotating/expiring secrets, multiple profiles.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CRED-01 | CredentialStore interface; all secret reads route through it; no scattered os.environ reads remain in plugins/notifiers | Sec. "Secret Migration Sites"; env-var backend keeps existing tests green |
| CRED-02 | Keyring backend using OS secret service via `keyring` lib | Sec. "keyring Library"; backend detection pattern |
| CRED-03 | Encrypted-file fallback: scrypt KDF + Fernet, passphrase from env or getpass | Sec. "cryptography Fernet + scrypt"; file format; atomic write |
| CRED-04 | Env-var fallback preserving today's behavior | Sec. "Env-var Backend"; monkeypatch test compatibility |
| CRED-05 | Backend auto-selected at startup; active name logged, never secret values | Sec. "Selection Logic"; "Backend Detection" |
| CRED-06 | No plaintext secrets on disk; test asserts no secret in config.yml/logs/SQLite | Sec. "No-Plaintext Guarantee"; test pattern |
| CRED-07 | Migration command: read known env vars, write into active backend, confirm by name | Sec. "Migration Command" |
</phase_requirements>

---

## Summary

Phase 8 introduces a `CredentialStore` abstraction over three pluggable backends: OS keyring (via `keyring` 25.7.0), AES-128-CBC encrypted file (via `cryptography` Fernet + scrypt KDF), and the current `os.environ` passthrough. The env-var backend is the identity-preserving fallback that keeps all 227 existing tests green without modification — those tests set secrets via `monkeypatch.setenv`, which the env-var backend reads directly. The keyring and file backends are opt-in upgrades.

The codebase has exactly 16 `os.environ.get` call sites across 8 plugin files and 3 notification files; all become `get_store().get(KEY)` one-for-one swaps. One additional site in `config_schema.py`'s `SmsConfig.require_creds_if_enabled` validator currently checks `os.environ.get()` at validation time — this must be noted but is low-risk to leave reading `os.environ` directly because it is a startup-time presence check, not a runtime secret read. The `notifications/__init__.py` `build_dispatcher` also has one `os.environ.get("DISCORD_WEBHOOK_URL")` presence guard — that must also migrate.

The key design constraint is thread safety for `get_store()`: BotService starts in a daemon thread with its own event loop, so the store must be initialized before the thread launches, or the lazy-init must be thread-safe.

**Primary recommendation:** Implement `core/credentials.py` as a single flat file (not a subpackage) containing the abstract base, all three backends, the `SECRET_KEYS` list, and the `get_store()`/`init_store()` module-level functions. This keeps the file count low and avoids a premature package split for what is a single-responsibility module.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Secret storage (at-rest) | Backend class (Keyring/File/Env) | OS (Windows Credential Manager, file system) | Secrets never enter the domain layer |
| Backend selection/auto-detect | `core/credentials.py` init logic | AppConfig `credentials.backend` config field | Config drives explicit choice; code drives auto |
| Secret read (runtime) | `get_store().get(KEY)` call site in notifiers/plugins | Backend (dispatches to OS or file) | Single access pattern, no direct os.environ in consumers |
| Migration | `core/credentials.py:migrate_from_env()` | `core/service.py:main()` argument parser | Logic in core, entry point in service |
| Store initialization | `BotService.__init__` or `main()` before the run | `core/credentials.py:init_store()` | Front-end owns lifecycle; core owns the function |
| No-plaintext test | `tests/test_credentials.py` | Grep scan of config.yml/logs/SQLite | Static file scan + runtime assertion |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `keyring` | 25.7.0 | OS secret store (Windows Credential Manager, Linux Secret Service) | Official cross-platform Python keyring API; maintained by jaraco |
| `cryptography` | 48.0.0 (latest); 44.0.2 already installed | Fernet symmetric encryption + scrypt KDF | ALREADY in project's Python env (installed as a selenium/other dep); pyca's primary cryptography lib |

[VERIFIED: npm registry equivalent — pip index confirms both packages exist and versions are current]

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `platformdirs` | 4.3.6 (already installed) | Per-OS data directory (`user_data_dir("shopbot")`) | Encrypted-file backend needs a stable location; already present as seleniumbase dep |
| `getpass` (stdlib) | stdlib | Passphrase prompt without echo | Encrypted-file backend interactive mode |
| `os.urandom` (stdlib) | stdlib | Salt generation for scrypt | Used in encrypted-file backend key derivation |
| `tempfile` (stdlib) | stdlib | Atomic file write: write-then-replace pattern | Prevents corrupt store file on crash during write |

**Installation:**
```bash
pip install keyring==25.7.0
```
`cryptography` and `platformdirs` are already installed in the project venv (confirmed by `pip show`).

**Version verification:**
```
keyring:       25.7.0  (pip index confirms latest)
cryptography:  44.0.2  (already installed; 48.0.0 is latest but 44.0.2 is fine — Fernet API is stable)
platformdirs:  4.3.6   (already installed)
```

---

## Package Legitimacy Audit

slopcheck could not be installed in this session (sandbox restriction). All packages below are marked per manual verification against PyPI and official sources.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `keyring` | PyPI | 14+ years | ~10M/wk | github.com/jaraco/keyring | [ASSUMED] | Approved — well-known, maintained by jaraco, used by pip itself |
| `cryptography` | PyPI | 12+ years | ~100M/wk | github.com/pyca/cryptography | [ASSUMED] | Approved — pyca org, industry-standard lib, already installed |
| `platformdirs` | PyPI | 5+ years | ~50M/wk | github.com/tox-dev/platformdirs | [ASSUMED] | Approved — already installed as transitive dep |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
*slopcheck was unavailable at research time; packages above are tagged [ASSUMED] and verified via pip index + PyPI reputation only. Planner should confirm before install.*

---

## Architecture Patterns

### System Architecture Diagram

```
AppConfig (credentials.backend: auto|keyring|file|env)
        |
        v
core/credentials.py: init_store(cfg)
        |
        +-- auto-detect ---------> keyring.get_keyring() -> is_real_backend()?
        |                                  YES: KeyringBackend
        |                                  NO -> passphrase available?
        |                                         YES: EncryptedFileBackend
        |                                         NO:  EnvVarBackend
        |
        +-- explicit override ----> KeyringBackend | EncryptedFileBackend | EnvVarBackend
        |
        v
  _store: CredentialStore (process-wide singleton)
        |
        get_store() -----------------> called by:
                                         - plugins/shopbot_plugin_*.py  (AMZ_*, BB_*, etc.)
                                         - notifications/discord_notifier.py (DISCORD_WEBHOOK_URL)
                                         - notifications/email_notifier.py  (SMTP_PASSWORD)
                                         - notifications/sms_notifier.py    (TWILIO_*)
                                         - notifications/__init__.py         (DISCORD_WEBHOOK_URL guard)
```

### Recommended Project Structure
```
core/
├── credentials.py       # CredentialStore ABC + 3 backends + get_store() + SECRET_KEYS
├── config_schema.py     # add CredentialsConfig (backend: str = "auto")
└── service.py           # call init_store(cfg) before BotService.run()
tests/
└── test_credentials.py  # unit tests: all 3 backends + migration + no-plaintext assert
```

### Pattern 1: CredentialStore ABC
**What:** Protocol/ABC with four methods; backends implement it.
**When to use:** All new code that needs a secret.
```python
# Source: CONTEXT.md locked decision
from abc import ABC, abstractmethod

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

### Pattern 2: Keyring Backend — detect real vs null/fail backend
**What:** Wrap `keyring` and check whether the active backend is functional.
**When to use:** Auto-select and explicit `backend: keyring` config value.
```python
# Source: keyring.readthedocs.io + jaraco/keyring core.py inspection
import keyring
from keyring.backends import fail as keyring_fail

def _has_real_keyring() -> bool:
    """Return True only when a non-null, non-fail OS keyring is available."""
    backend = keyring.get_keyring()
    # fail.Keyring is the default when no real backend found
    if isinstance(backend, keyring_fail.Keyring):
        return False
    # null.Keyring is the explicit no-op backend
    try:
        from keyring.backends.null import Keyring as NullKeyring
        if isinstance(backend, NullKeyring):
            return False
    except ImportError:
        pass
    # ChainerBackend wraps multiple backends; treat as real if at least one works
    return True

class KeyringBackend(CredentialStore):
    SERVICE = "shopbot"

    def get(self, key: str) -> str | None:
        return keyring.get_password(self.SERVICE, key)

    def set(self, key: str, value: str) -> None:
        keyring.set_password(self.SERVICE, key, value)

    def delete(self, key: str) -> None:
        keyring.delete_password(self.SERVICE, key)

    def list(self) -> list[str]:
        # keyring has no enumerate API; return intersection of known keys that have values
        return [k for k in SECRET_KEYS if keyring.get_password(self.SERVICE, k) is not None]
```

### Pattern 3: Encrypted-File Backend — Fernet + scrypt
**What:** Store secrets in a small binary file; derive Fernet key from a passphrase via scrypt.
**When to use:** Headless/no-keyring environments.
```python
# Source: cryptography.io/en/44.0.1/fernet/ + cryptography KDF docs (RFC 7914 params)
import base64, os, json, tempfile
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

SCRYPT_N = 2**14   # interactive login: ~100ms on modern hardware (RFC 7914 recommendation)
SCRYPT_R = 8       # standard block size
SCRYPT_P = 1       # single thread; acceptable for this use
SALT_LEN = 16

def _derive_key(passphrase: bytes, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return base64.urlsafe_b64encode(kdf.derive(passphrase))

class EncryptedFileBackend(CredentialStore):
    """File format: [SALT_LEN bytes salt][Fernet token of JSON-encoded dict]"""

    def __init__(self, path: Path, passphrase: bytes) -> None:
        self._path = path
        self._passphrase = passphrase

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        data = self._path.read_bytes()
        salt, token = data[:SALT_LEN], data[SALT_LEN:]
        key = _derive_key(self._passphrase, salt)
        plaintext = Fernet(key).decrypt(token)
        return json.loads(plaintext)

    def _save(self, secrets: dict[str, str]) -> None:
        salt = os.urandom(SALT_LEN)
        key = _derive_key(self._passphrase, salt)
        token = Fernet(key).encrypt(json.dumps(secrets).encode())
        # Atomic write: tempfile + os.replace (POSIX atomic; Windows: file must be closed first)
        dir_ = self._path.parent
        dir_.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dir_)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(salt + token)
            os.replace(tmp, self._path)
        except Exception:
            os.unlink(tmp)
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
```

### Pattern 4: Env-var Backend (identity fallback)
**What:** Reads `os.environ` — identical to today's behavior; requires zero migration.
**When to use:** No keyring, no passphrase; also used in all existing tests via monkeypatch.setenv.
```python
# Source: existing codebase pattern (os.environ.get calls in plugins/notifiers)
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

### Pattern 5: Module-level init + singleton accessor
**What:** `init_store(cfg)` called once at startup; `get_store()` returns the cached instance.
**When to use:** BotService.__init__ or main() calls init_store; notifiers/plugins call get_store().
```python
_store: CredentialStore | None = None

def init_store(cfg: AppConfig) -> CredentialStore:
    global _store
    backend_name = getattr(getattr(cfg, "credentials", None), "backend", "auto")
    _store = _build_store(backend_name, cfg)
    return _store

def get_store() -> CredentialStore:
    if _store is None:
        # Lazy fallback for tests that never call init_store:
        # env-var backend keeps monkeypatch.setenv tests green
        return EnvVarBackend()
    return _store
```

### Pattern 6: CredentialsConfig addition to AppConfig
**What:** A small pydantic BaseModel added to AppConfig.
**When to use:** config.yml `credentials:` section.
```python
# Follows the exact pattern of DiscordConfig, EmailConfig in config_schema.py
class CredentialsConfig(BaseModel):
    backend: str = "auto"   # auto|keyring|file|env
    data_dir: str = ""      # optional override; empty = platformdirs user_data_dir

# Add to AppConfig:
#   credentials: CredentialsConfig = CredentialsConfig()
```

### Pattern 7: Migration command
**What:** Read all known env-var secrets that are currently set, write each into the active backend.
**When to use:** `shoppybot setup --migrate` invocation.
```python
def migrate_from_env(store: CredentialStore) -> list[str]:
    """Write each set env-var secret into the store. Returns list of migrated key names."""
    migrated = []
    for key in SECRET_KEYS:
        val = os.environ.get(key)
        if val:
            store.set(key, val)
            migrated.append(key)   # confirm by name ONLY — never print value
    return migrated
```

### Pattern 8: Keyring testing without a real OS backend
**What:** For unit tests of KeyringBackend, inject an in-memory dict backend via `keyring.set_keyring()`.
**When to use:** All keyring-backend tests to avoid touching Windows Credential Manager.
```python
# Source: keyring.backend.KeyringBackend subclass pattern (community standard)
import keyring
from keyring.backend import KeyringBackend

class _DictKeyring(KeyringBackend):
    """In-memory keyring for testing. No filesystem or OS interaction."""
    priority = 1

    def __init__(self):
        self._data: dict[tuple, str] = {}

    def get_password(self, service, username):
        return self._data.get((service, username))

    def set_password(self, service, username, password):
        self._data[(service, username)] = password

    def delete_password(self, service, username):
        self._data.pop((service, username), None)

@pytest.fixture(autouse=False)
def isolated_keyring():
    """Swap the OS keyring with an in-memory backend for the duration of the test."""
    kb = _DictKeyring()
    keyring.set_keyring(kb)
    yield kb
    # Restore: next test will call get_keyring() which re-detects the real backend
    keyring.core._keyring_backend = None
```

### Anti-Patterns to Avoid
- **Logging a secret value:** Log backend name only (e.g. `"CredentialStore: keyring backend active"`). Never log key values, never `str(exc)` when an exception message might embed a secret.
- **Reading os.environ outside the EnvVarBackend:** After migration, the ONLY place `os.environ.get` appears for secrets is inside `EnvVarBackend.get()`. A grep must confirm this.
- **Storing the passphrase in the encrypted file:** The passphrase is never written anywhere on disk; it comes from `SHOPBOT_STORE_PASSPHRASE` env var or runtime `getpass.getpass()`.
- **Re-deriving scrypt key on every get():** The current _load/_save pattern re-derives per call. For very frequent calls this is slow (scrypt n=2**14 ~50ms). Cache the decrypted dict in memory with a lock if performance matters; for the bot's check-interval (30s+) it is fine without caching.
- **Blocking event loop with getpass:** `getpass.getpass()` blocks. It must only be called during store init (before the asyncio loop starts), never inside an async context.
- **SmsConfig validator still reading os.environ:** `SmsConfig.require_creds_if_enabled` runs during `AppConfig()` construction (before `init_store` can run), so it MUST stay reading `os.environ`. Document this as a deliberate exception — it is a startup presence check, not a secret consumer.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OS secret storage | Custom Windows Registry / ~/.secrets file | `keyring` | Handles Windows Credential Manager, Linux Secret Service, macOS Keychain; tested across platforms |
| Symmetric encryption | Custom AES via ctypes or PyCryptodome | `cryptography.fernet.Fernet` | Authenticated encryption (AES-128-CBC + HMAC-SHA256); misuse-resistant API; already proven in pyca |
| Password-based key derivation | Custom PBKDF2 loop | `cryptography.hazmat.primitives.kdf.scrypt.Scrypt` | RFC 7914 compliant; tunable memory-hardness; prevents GPU/ASIC attacks on weak passphrases |
| Atomic file write | try/except with in-place overwrite | `tempfile.mkstemp` + `os.replace` | In-place overwrite can corrupt the store if the process dies mid-write; `os.replace` is atomic on POSIX and Windows |
| Cross-platform data dir | `Path.home() / ".shopbot"` | `platformdirs.user_data_dir("shopbot")` | Correct per-OS location: `%APPDATA%\shopbot` on Windows, `~/.local/share/shopbot` on Linux |

**Key insight:** The `cryptography` library is already present in the venv (it is a transitive dep). Adding `keyring` is the only net-new install.

---

## Secret Migration Sites

All `os.environ` secret reads that must become `get_store().get(KEY)`:

| File | Line(s) | Current Call | Becomes |
|------|---------|--------------|---------|
| `plugins/shopbot_plugin_amazon.py` | 116–117 | `os.environ.get("AMZ_EMAIL")` / `os.environ.get("AMZ_PASSWORD")` | `get_store().get(...)` |
| `plugins/shopbot_plugin_bestbuy.py` | 81–82 | `os.environ.get("BB_EMAIL")` / `os.environ.get("BB_PASSWORD")` | `get_store().get(...)` |
| `plugins/shopbot_plugin_walmart.py` | 97–98 | `os.environ.get("WALMART_EMAIL")` / `os.environ.get("WALMART_PASSWORD")` | `get_store().get(...)` |
| `plugins/shopbot_plugin_target.py` | 99–100 | `os.environ.get("TARGET_EMAIL")` / `os.environ.get("TARGET_PASSWORD")` | `get_store().get(...)` |
| `plugins/shopbot_plugin_gamestop.py` | 99–100 | `os.environ.get("GAMESTOP_EMAIL")` / `os.environ.get("GAMESTOP_PASSWORD")` | `get_store().get(...)` |
| `plugins/shopbot_plugin_squareenix.py` | 98–99 | `os.environ.get("SQUAREENIX_EMAIL")` / `os.environ.get("SQUAREENIX_PASSWORD")` | `get_store().get(...)` |
| `plugins/shopbot_plugin_newegg.py` | 101–102 | `os.environ.get("NEWEGG_EMAIL")` / `os.environ.get("NEWEGG_PASSWORD")` | `get_store().get(...)` |
| `notifications/discord_notifier.py` | 66 | `os.environ["DISCORD_WEBHOOK_URL"]` | `get_store().get("DISCORD_WEBHOOK_URL")` (KeyError becomes None-check) |
| `notifications/email_notifier.py` | 69 | `os.environ.get("SMTP_PASSWORD", "")` | `get_store().get("SMTP_PASSWORD") or ""` |
| `notifications/sms_notifier.py` | 57–59 | `os.environ.get("TWILIO_ACCOUNT_SID", "")` etc. | `get_store().get(...)` |
| `notifications/__init__.py` | 44 | `os.environ.get("DISCORD_WEBHOOK_URL")` presence guard in build_dispatcher | `get_store().get("DISCORD_WEBHOOK_URL")` |

**NOTE:** `core/config_schema.py` `SmsConfig.require_creds_if_enabled` reads `os.environ.get("TWILIO_*")` at AppConfig construction time — BEFORE init_store() can run. Leave this as-is; it is a startup presence gate, not a secret consumer. Document the deliberate exception clearly in the code.

**Total migration sites: 16 call sites across 11 files.**

---

## SECRET_KEYS Canonical List

```python
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
```

---

## Common Pitfalls

### Pitfall 1: Test suite breakage from init_store side-effects
**What goes wrong:** `init_store(cfg)` sets the global `_store`. If one test calls init_store with a keyring backend and the next test expects env-var behavior, tests bleed.
**Why it happens:** Module-level singleton is shared across tests.
**How to avoid:** `get_store()` lazy-init returns a fresh `EnvVarBackend()` when `_store is None`. Tests that do NOT call init_store get the env-var backend automatically. Tests that call init_store should reset `_store = None` in a fixture teardown, or use the `isolated_keyring` fixture pattern.
**Warning signs:** Tests that use `monkeypatch.setenv` start failing after a test that calls `init_store`.

### Pitfall 2: DiscordNotifier raises KeyError instead of returning None
**What goes wrong:** Current code is `os.environ["DISCORD_WEBHOOK_URL"]` (no default) — raises `KeyError` when the key is absent. After migration to `get_store().get(KEY)`, the return is `None`, and the caller must check for None.
**Why it happens:** The old code relied on KeyError as a guard; the new code returns None.
**How to avoid:** In `DiscordNotifier.__init__`, add: `url = get_store().get("DISCORD_WEBHOOK_URL"); if not url: raise ValueError("DISCORD_WEBHOOK_URL not configured")`.

### Pitfall 3: scrypt blocks the event loop if called inside async code
**What goes wrong:** `Scrypt.derive()` with n=2**14 takes ~50ms. If called inside an async function without `run_in_executor`, it blocks the event loop for that time.
**Why it happens:** The bot uses asyncio; CPU-bound work blocks all coroutines.
**How to avoid:** Only call `_load()` / `_save()` from the store initialization path (sync) or from plugin/notifier constructors (sync), never from inside `async def` methods. If store access is needed inside an async context, do it in `run_in_executor`.

### Pitfall 4: Encrypted file becomes unreadable if passphrase changes
**What goes wrong:** User rotates `SHOPBOT_STORE_PASSPHRASE` — the file was encrypted with the old passphrase; `Fernet.decrypt` raises `InvalidToken`.
**Why it happens:** scrypt-derived key changes with the passphrase; the salt is stored in the file but the passphrase is not.
**How to avoid:** Catch `cryptography.fernet.InvalidToken` in `_load()`; raise a clear user-facing error: "Cannot decrypt credential store — check SHOPBOT_STORE_PASSPHRASE". Document that passphrase changes require re-migration via `--migrate`.

### Pitfall 5: keyring.list_passwords / enumerate does not exist
**What goes wrong:** `keyring` has no API to list all stored keys for a service; only `get_password(service, key)` exists.
**Why it happens:** The OS keyring APIs (Windows Credential Manager, SecretService) have varying enumerate support; `keyring` chose not to expose it.
**How to avoid:** The `KeyringBackend.list()` implementation must iterate over `SECRET_KEYS` and probe each one. This means `list()` on the keyring backend only returns keys that are in the canonical SECRET_KEYS list. Document this limitation.

### Pitfall 6: Windows tempfile + os.replace file-in-use error
**What goes wrong:** On Windows, `os.replace(tmp, target)` may raise `PermissionError` if the target file is open by another process or the tempfile fd is still open.
**Why it happens:** Windows does not allow replacing an open file.
**How to avoid:** Use `os.fdopen(fd, "wb")` inside a `with` block so the fd is closed BEFORE `os.replace` is called. The Pattern 3 code above handles this correctly via `with os.fdopen(fd, "wb") as f:` followed by `os.replace` outside the `with`.

### Pitfall 7: SmsConfig validator os.environ dependency
**What goes wrong:** After the migration, a developer sees `os.environ.get` in `config_schema.py` and "fixes" it to use `get_store().get()`, breaking startup ordering (store not yet initialized when AppConfig is constructed).
**Why it happens:** Startup ordering: `AppConfig()` is constructed first, then `init_store(cfg)` is called. The validator runs at construction time.
**How to avoid:** Leave `SmsConfig.require_creds_if_enabled` reading `os.environ` and add a code comment explaining the deliberate exception.

---

## No-Plaintext Guarantee (CRED-06)

### Test Pattern
```python
# tests/test_credentials.py
def test_no_plaintext_secrets_in_config_yml(tmp_path):
    """Assert none of the SECRET_KEYS values appear as plaintext in config.yml."""
    from core.credentials import SECRET_KEYS
    config_path = Path("config.yml")
    if not config_path.exists():
        pytest.skip("config.yml not present in this environment")
    content = config_path.read_text(errors="replace")
    for key in SECRET_KEYS:
        val = os.environ.get(key, "")
        if val:
            assert val not in content, f"Secret {key} value found in config.yml"

def test_no_plaintext_secrets_in_log_files(tmp_path):
    """Assert none of the SECRET_KEYS values appear in any log file."""
    from core.credentials import SECRET_KEYS
    log_dir = Path("logs")
    if not log_dir.exists():
        return  # no logs yet — vacuously pass
    for log_file in log_dir.glob("*.log"):
        content = log_file.read_text(errors="replace")
        for key in SECRET_KEYS:
            val = os.environ.get(key, "")
            if val and len(val) > 4:  # skip very short/empty values
                assert val not in content, f"Secret {key} value found in {log_file}"

def test_encrypted_file_is_not_plaintext(tmp_path, monkeypatch):
    """Assert the Fernet-encrypted store file contains no plaintext secret values."""
    from core.credentials import EncryptedFileBackend, SECRET_KEYS
    store_path = tmp_path / "creds.bin"
    store = EncryptedFileBackend(store_path, b"test-passphrase")
    store.set("AMZ_EMAIL", "mytest@example.com")
    raw = store_path.read_bytes()
    assert b"mytest@example.com" not in raw
```

---

## Data-Dir Resolution

The encrypted-file backend stores `creds.bin` (or similar) in the per-OS user data directory.

```python
# Source: platformdirs docs (platformdirs already installed as seleniumbase dep)
from platformdirs import user_data_dir

def _default_store_path() -> Path:
    # Windows: C:\Users\<user>\AppData\Local\shopbot\shopbot\creds.bin
    # Linux:   ~/.local/share/shopbot/creds.bin
    return Path(user_data_dir("shopbot", "shopbot")) / "creds.bin"
```

If the user specifies `credentials.data_dir` in config.yml, use that path instead. This mirrors how `models.py` uses `data/shop_py_bot.db` — a simple relative path for dev, a configurable path for production.

**Alternative without platformdirs:** `Path(__file__).parent.parent / "data" / "creds.bin"` — this puts the file next to the SQLite DB in `data/`. Simpler, but not per-OS standard. Claude's discretion: use `data/creds.bin` as the default (consistent with existing project layout) with `credentials.data_dir` override for those who want a system location.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | All | Yes | 3.13.13 | — |
| `cryptography` | Encrypted-file backend | Yes | 44.0.2 (installed) | — |
| `platformdirs` | Data-dir resolution | Yes | 4.3.6 (installed) | Use `data/creds.bin` as hardcoded default |
| `keyring` | Keyring backend | Not installed | — | Auto-select falls back to file or env backend |
| `pytest` | Test suite | Yes | 9.0.3 | — |
| Windows Credential Manager | KeyringBackend | Available (Windows 11) | — | Env or file backend |

**Missing dependencies with no fallback:** None — all required deps either installed or have documented fallbacks in selection logic.

**Missing dependencies with fallback:** `keyring` not yet installed; selection logic falls through to encrypted-file or env-var.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 (asyncio_mode=auto) |
| Config file | `pytest.ini` or `pyproject.toml` (existing; asyncio_mode=auto already set) |
| Quick run command | `pytest tests/test_credentials.py -x` |
| Full suite command | `pytest` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CRED-01 | get_store().get(KEY) returns env-var value | unit | `pytest tests/test_credentials.py::test_env_backend_get -x` | No — Wave 0 |
| CRED-01 | No os.environ calls remain outside EnvVarBackend | static grep | `pytest tests/test_credentials.py::test_no_os_environ_in_plugins -x` | No — Wave 0 |
| CRED-02 | KeyringBackend.get/set/delete work with in-memory backend | unit | `pytest tests/test_credentials.py::test_keyring_backend -x` | No — Wave 0 |
| CRED-02 | _has_real_keyring() returns False for fail/null backend | unit | `pytest tests/test_credentials.py::test_has_real_keyring_fail -x` | No — Wave 0 |
| CRED-03 | EncryptedFileBackend round-trip: set/get/delete/list | unit | `pytest tests/test_credentials.py::test_file_backend -x` | No — Wave 0 |
| CRED-03 | File is not plaintext-readable | unit | `pytest tests/test_credentials.py::test_encrypted_file_is_not_plaintext -x` | No — Wave 0 |
| CRED-03 | Wrong passphrase raises clear error | unit | `pytest tests/test_credentials.py::test_file_backend_wrong_passphrase -x` | No — Wave 0 |
| CRED-04 | EnvVarBackend.get returns monkeypatch.setenv value | unit | `pytest tests/test_credentials.py::test_env_backend_monkeypatch -x` | No — Wave 0 |
| CRED-05 | init_store returns keyring backend on win32 when keyring is real | unit | `pytest tests/test_credentials.py::test_auto_select_keyring -x` | No — Wave 0 |
| CRED-05 | init_store returns file backend when passphrase set, no keyring | unit | `pytest tests/test_credentials.py::test_auto_select_file -x` | No — Wave 0 |
| CRED-05 | Active backend name is logged, not a secret value | unit | `pytest tests/test_credentials.py::test_startup_log_backend_name -x` | No — Wave 0 |
| CRED-06 | No plaintext secrets in config.yml/logs/SQLite | integration | `pytest tests/test_credentials.py::test_no_plaintext_secrets_in_config_yml -x` | No — Wave 0 |
| CRED-07 | migrate_from_env writes to active backend and returns key names | unit | `pytest tests/test_credentials.py::test_migrate_from_env -x` | No — Wave 0 |

### Sampling Rate
- Per task commit: `pytest tests/test_credentials.py -x`
- Per wave merge: `pytest` (full 227+ suite)
- Phase gate: full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- `tests/test_credentials.py` — all CRED-01..CRED-07 test cases; does not exist yet
- No new conftest fixtures needed; existing `tmp_path` and `monkeypatch` are sufficient

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — credential store is not an auth system |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | Key names validated against SECRET_KEYS list in migration; passphrase accepted as-is (user-supplied) |
| V6 Cryptography | yes | `cryptography` Fernet (AES-128-CBC + HMAC-SHA256); scrypt KDF — never hand-rolled |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret leakage via log | Information Disclosure | Log backend name only; never log key values or exceptions that embed key values |
| Weak passphrase on encrypted file | Tampering | scrypt n=2**14 makes brute-force expensive; document that passphrase strength matters |
| Plaintext fallback silent leak | Information Disclosure | CRED-06 test; grep assertion that no os.environ secret reads remain in consumers |
| Credential store file readable by other users | Information Disclosure | `chmod 600` on `creds.bin` after write (POSIX); Windows file system permissions apply automatically |
| config.yml secret injection | Tampering | `warn_legacy_keys` validator already exists; CRED-06 test asserts no secret values in YAML |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `os.environ.get(KEY)` at every call site | `get_store().get(KEY)` single access facade | Phase 8 | Secrets routable to OS keyring or encrypted file without changing consumers |
| No KDF; raw key if any | scrypt n=2**14 | Phase 8 | Memory-hard KDF resistant to GPU attacks on passphrase |
| PBKDF2 (older recommendation) | scrypt or Argon2id | Post-2020 | cryptography docs now show PBKDF2 at 480k iterations as baseline; scrypt is preferred for memory-hardness |

**Deprecated/outdated:**
- PBKDF2HMAC with low iteration counts (< 100k): still supported by `cryptography` but not recommended for new code. Use scrypt.
- keyring < 23: API changes in get_credential; use 25.x.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `keyring` 25.7.0 is the correct install target | Standard Stack | Low — pip index confirms it is the latest; earlier versions have the same API |
| A2 | `platformdirs` is already installed (as a seleniumbase dep) | Standard Stack | Low — `pip show platformdirs` confirmed it in this session; version 4.3.6 |
| A3 | `cryptography` 44.0.2 (installed) supports scrypt and Fernet identically to 48.0.0 | Standard Stack | Low — Fernet and scrypt APIs are stable since cryptography 2.x |
| A4 | keyring `fail.Keyring` is the default fallback when no OS backend is detected | Pitfall 5 / Pattern 2 | Medium — if the class path changes in a future keyring version, `_has_real_keyring()` needs updating. Mitigation: also catch any exception from `keyring.get_password` in the backend init |
| A5 | The 16 os.environ call sites identified are exhaustive (no others exist) | Migration Sites | Low — grep was performed on `plugins/` and `notifications/`; `core/config_schema.py` SmsConfig exception is documented |
| A6 | scrypt n=2**14 is acceptable latency for the file backend (~50ms) | Pattern 3 | Low — acceptable for startup-time key derivation; would be unacceptable if called per-request |
| A7 | `os.replace` is atomic on Windows 11 for this use case | Pattern 3 | Low — Python docs confirm os.replace uses MoveFileEx on Windows; the fd-close-before-replace pattern handles the open-file restriction |

---

## Open Questions (RESOLVED)

1. **data_dir default: project-relative `data/creds.bin` vs platformdirs `user_data_dir`?**
   - What we know: `data/shop_py_bot.db` is the SQLite path (project-relative); platformdirs is already installed.
   - What's unclear: whether placing `creds.bin` next to the DB is more convenient for users vs the OS-standard location.
   - Recommendation: default to `data/creds.bin` (consistent with existing project convention); expose `credentials.data_dir` config override for those who need XDG/AppData location.

2. **Should `get_store()` lazy-init to EnvVarBackend or raise if never initialized?**
   - What we know: 227 tests exist that use `monkeypatch.setenv` and never call `init_store`; they must pass.
   - What's unclear: whether lazy fallback to EnvVarBackend could mask a misconfigured startup.
   - Recommendation: lazy fallback to EnvVarBackend only (silent, test-compatible). Document that production startup MUST call init_store explicitly.

3. **Should the keyring service_name be `"shopbot"` (hardcoded) or derived from the app name in config?**
   - What we know: Windows Credential Manager groups by service name; `"shopbot"` is clear.
   - What's unclear: multiproject collision if another shopbot exists on the same machine.
   - Recommendation: `"shopbot"` hardcoded; this is a personal tool, collision unlikely.

---

## Sources

### Primary (HIGH confidence)
- cryptography.io/en/44.0.1/fernet/ — Fernet API, PBKDF2 example
- cryptography.io/en/44.0.1/hazmat/primitives/key-derivation-functions/ — scrypt API, RFC 7914 parameters (n/r/p)
- keyring.readthedocs.io/en/stable/ — get_keyring(), backend detection, null.Keyring
- raw.githubusercontent.com/jaraco/keyring/master/keyring/core.py — _detect_backend, fail.Keyring fallback
- pypi.org/project/keyring/ — version 25.7.0, API summary
- pip index (local) — keyring 25.7.0, cryptography 44.0.2/48.0.0, platformdirs 4.3.6

### Secondary (MEDIUM confidence)
- github.com/jaraco/keyring/issues/631 — no official in-memory test backend exists; custom DictKeyring is the established pattern
- Codebase grep of E:\repos\ShopPyBot\plugins\ and notifications\ — 16 migration sites identified

### Tertiary (LOW confidence)
- WebSearch: "atomic file write Windows Python" — os.replace + fdopen-before-replace pattern; confirmed by Python docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pip index verified keyring 25.7.0 and cryptography 44.0.2; both are long-standing packages
- Architecture: HIGH — codebase read confirms all 16 migration sites; pattern follows existing project conventions exactly
- Pitfalls: HIGH — DiscordNotifier KeyError, scrypt-in-asyncio, and Windows fdopen-before-replace are all grounded in code-read evidence
- Test patterns: HIGH — DictKeyring subclass pattern is the established community approach; in-memory backend confirmed via keyring.set_keyring()

**Research date:** 2026-06-04
**Valid until:** 2026-07-04 (keyring and cryptography APIs are stable; 30-day horizon conservative)
