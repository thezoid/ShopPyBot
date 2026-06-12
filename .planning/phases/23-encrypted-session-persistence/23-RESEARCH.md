# Phase 23: Encrypted Session Persistence - Research

**Researched:** 2026-06-12
**Domain:** nodriver 0.50.3 CDP cookie API; Fernet/scrypt session encryption; plugin ABC wiring
**Confidence:** HIGH (all critical API paths verified against installed package)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- `core/session_store.py` exposes `SessionStore` with `save(platform, cookies)` and
  `restore(platform) -> list | None`. Encryption is Fernet, reusing the scrypt
  `_derive_key` helper + passphrase machinery from `core/credentials.py`.
- Passphrase source is `SHOPBOT_STORE_PASSPHRASE` (env). If absent, session persistence
  is silently disabled (no plaintext fallback).
- File format: `data/sessions/<platform>.bin`, `[SALT_LEN bytes salt][Fernet token of
  JSON cookie list]`, mirroring `EncryptedFileBackend`.
- Stored content: cookie fields (name, value, domain, path, expires, httpOnly, secure,
  sameSite) JSON-serialized then Fernet-encrypted. No other auth material; never plaintext.
- Cookie restore uses raw `cdp.storage.set_cookies()` with `CookieParam` objects,
  bypassing `CookieJar.set_all()`.
- `restore_session()` replaces the Phase 22 no-op stub: returns True (skips login) on
  successful restore, False on missing/corrupt/wrong-passphrase.
- `session_persistence: bool = False` added to ALL 7 platform config models (additive,
  opt-in, default off).
- `save_session()` called after successful `login()` when `session_persistence` is enabled.
- Generic ABC `save_session`/`restore_session` via `SessionStore` (no `PLUGIN_API_VERSION` bump).
- CI test: no session-file pattern (`data/sessions/*.bin`) is git-tracked; `data/sessions/`
  is gitignored.

### Claude's Discretion

- Cookie serialization detail (which optional `CookieParam` fields to round-trip).
- Error message wording on `InvalidToken` / missing-passphrase disabled path.
- Test structure and fixture naming for `test_session_store.py`.

### Deferred Ideas (OUT OF SCOPE)

- Health surface / per-plugin liveness + heartbeat: Phase 24 (REL-07).
- Cookie refresh/rotation policy, multi-profile sessions: future (out of v4.0 scope).
- Live cross-restart MFA-skip verification on a real retailer: UAT debt (tracked, not blocking).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REL-04 | User can opt in to encrypted session/cookie persistence so the bot restores browser cookies across restarts (skipping re-login/MFA); cookies are encrypted via the existing CredentialStore machinery (never plaintext) and restored via the CDP path that avoids the nodriver `set_all()` bug. | CDP API fully verified; Fernet reuse pattern confirmed; set_all bug characterized; gitignore coverage confirmed. |
</phase_requirements>

## Summary

Phase 23 adds opt-in encrypted cookie persistence so the bot can skip re-login and MFA
challenges across restarts. The core insight is that nodriver 0.50.3 exposes two distinct
approaches: the high-level `CookieJar.set_all()` (broken) and the raw
`tab.send(cdp.storage.set_cookies([...]))` path (correct). The broken path is used by
nodriver's own `CookieJar.load()` which passes `network.Cookie` objects where the CDP
protocol expects `network.CookieParam` -- the extra `size` and `session` fields cause
Chrome to reject the call silently on some versions, and `CookieJar.save()` stores
cookies as plaintext pickle, which is also a security non-starter.

The implementation reuses everything already in `core/credentials.py`: `_derive_key`
(scrypt n=2^14/r=8/p=1), `SALT_LEN=16`, the `[salt][Fernet-token]` file layout, and
the `SHOPBOT_STORE_PASSPHRASE` env-var resolution. `SessionStore` is a thin wrapper
around this pattern specialized for cookie lists rather than credential dicts.
`restore_session()` on the ABC replaces the Phase 22 no-op stub and is called in the
already-wired `relaunch()` sequence (teardown -> setup -> restore_session -> login).

For initial startup (not just relaunch), restore needs to be called after `setup()` as
well. Currently `relaunch()` handles this for cold-restart; for bot startup, the
orchestrator or plugin's `setup()` needs to call `restore_session()` if
`session_persistence` is enabled.

**Primary recommendation:** Implement `SessionStore` mirroring `EncryptedFileBackend`'s
`_load`/`_save` pattern; use `tab.send(cdp.storage.set_cookies(params))` for restore and
`tab.send(cdp.storage.get_cookies())` for save; serialize only the
`CookieParam`-compatible fields.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Cookie encryption/decryption | Core library (`core/session_store.py`) | -- | Pure Python, no browser involvement |
| Cookie save (read from browser) | Plugin layer (after login()) | Core via CDP | Browser owns live cookie jar |
| Cookie restore (write to browser) | Plugin layer (restore_session()) | Core via CDP | Browser must be alive before CDP call |
| Passphrase resolution | Core library (mirrors credentials.py) | -- | Single source of truth |
| Session file storage | Core library | -- | `data/sessions/<platform>.bin` |
| Config flag per platform | Config schema (7 models) | -- | Per-platform opt-in |
| CI no-committed-session guard | Test (CI) | -- | Gitignore + assertion |

## Standard Stack

### Core (all already installed, no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cryptography` | installed (pinned) | Fernet + scrypt KDF | Already used in credentials.py |
| `nodriver` | 0.50.3 | CDP cookie read/write | Already the browser driver |
| `json` (stdlib) | -- | Cookie list serialization | No external dep needed |
| `os` (stdlib) | -- | urandom salt, atomic write | Already in credentials.py pattern |

No new packages are required for this phase.

## Package Legitimacy Audit

No new external packages are introduced in this phase. All crypto and CDP operations
reuse existing pinned dependencies (`cryptography`, `nodriver==0.50.3`).

**Packages removed due to slopcheck:** none
**Packages flagged as suspicious:** none

## Architecture Patterns

### System Architecture Diagram

```
login() succeeds
    |
    v
[save_session()] ----------> SessionStore.save(platform, cookies)
    |                               |
    | tab.send(                     | 1. os.urandom(16) -> salt
    |   cdp.storage.get_cookies())  | 2. _derive_key(passphrase, salt) -> Fernet key
    |                               | 3. Fernet.encrypt(json.dumps(cookie_list))
    | -> [network.Cookie, ...]      | 4. write [salt][token] -> data/sessions/<p>.bin
    |
    v (serialize to CookieParam-compatible dicts)

relaunch() / startup:
setup() completes
    |
    v
[restore_session()] -------> SessionStore.restore(platform)
    |                               |
    |                               | 1. read [salt][token] from .bin
    |                               | 2. _derive_key -> Fernet.decrypt -> json.loads
    |                               | 3. return cookie list (or None on error/missing)
    |
    | build CookieParam objects
    | tab.send(cdp.storage.set_cookies([CookieParam(...),...]))
    |
    v
True (skip login) / False (proceed to login)
```

### Recommended Project Structure

```
core/
    session_store.py      # NEW: SessionStore class
    credentials.py        # REUSE: _derive_key, SALT_LEN, _resolve_passphrase pattern
    plugin_base.py        # MODIFY: restore_session stub -> live; add save_session
    config_schema.py      # MODIFY: session_persistence: bool = False on all 7 platform models
data/
    sessions/             # created on demand; covered by data/* gitignore
        amazon.bin        # platform session file (encrypted)
        bestbuy.bin
tests/
    test_session_store.py # NEW: unit tests for SessionStore
```

### Pattern 1: SessionStore mirrors EncryptedFileBackend

The `_load` / `_save` idiom from `core/credentials.py` is the exact pattern to follow,
with cookie list in place of secrets dict. Key differences: no threading lock needed (one
writer: post-login hook; one reader: restore path; not concurrent), and cookie list is
`list[dict]` not `dict[str, str]`.

```python
# Source: core/credentials.py lines 251-281 (verified by Read)
# Mirror pattern:
def _save_session(self, platform: str, cookies: list[dict]) -> None:
    salt = os.urandom(SALT_LEN)
    key = _derive_key(self._passphrase, salt)
    token = Fernet(key).encrypt(json.dumps(cookies).encode())
    path = self._session_path(platform)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(salt + token)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

def _load_session(self, platform: str) -> list[dict] | None:
    path = self._session_path(platform)
    if not path.exists():
        return None
    data = path.read_bytes()
    salt, token = data[:SALT_LEN], data[SALT_LEN:]
    key = _derive_key(self._passphrase, salt)
    try:
        plaintext = Fernet(key).decrypt(token)
    except InvalidToken:
        return None   # wrong passphrase or corrupt; caller falls back to login
    return json.loads(plaintext)
```

[VERIFIED: core/credentials.py lines 251-281]

### Pattern 2: CDP cookie save (get_cookies)

```python
# Source: verified via inspect.getsource on nodriver 0.50.3 installed package
# storage.get_cookies is BROWSER-WIDE (all cookies, all tabs)
# Use tab.send() -- Tab.send() is verified in nodriver.core.tab source

from nodriver.cdp import storage as cdp_storage, network as cdp_network

cookies: list[cdp_network.Cookie] = await tab.send(cdp_storage.get_cookies())
# Serialize to dicts -- store only CookieParam-compatible fields:
cookie_dicts = [
    {
        "name": c.name,
        "value": c.value,
        "domain": c.domain,
        "path": c.path,
        "expires": float(c.expires) if c.expires is not None else None,
        "http_only": c.http_only,
        "secure": c.secure,
        "same_site": c.same_site.value if c.same_site is not None else None,
    }
    for c in cookies
]
```

[VERIFIED: nodriver 0.50.3 site-packages inspected]

### Pattern 3: CDP cookie restore (set_cookies -- the correct path)

```python
# Source: verified via inspect.getsource on nodriver 0.50.3 installed package
# storage.set_cookies -> CDP method 'Storage.setCookies'
# Accepts List[network.CookieParam] -- NOT network.Cookie

from nodriver.cdp import storage as cdp_storage, network as cdp_network

def _dict_to_cookie_param(d: dict) -> cdp_network.CookieParam:
    same_site = None
    if d.get("same_site"):
        try:
            same_site = cdp_network.CookieSameSite(d["same_site"])
        except ValueError:
            same_site = None
    expires = None
    if d.get("expires") is not None:
        expires = cdp_network.TimeSinceEpoch(float(d["expires"]))
    return cdp_network.CookieParam(
        name=d["name"],
        value=d["value"],
        domain=d.get("domain"),
        path=d.get("path"),
        expires=expires,
        http_only=d.get("http_only"),
        secure=d.get("secure"),
        same_site=same_site,
    )

params = [_dict_to_cookie_param(d) for d in cookie_dicts]
await tab.send(cdp_storage.set_cookies(params))
```

[VERIFIED: nodriver 0.50.3 site-packages inspected]

### Pattern 4: save_session hook point in login()

Both `AmazonPlugin.login()` and `BestBuyPlugin.login()` end with a `writeLog("Signed in
to ...")` line followed by a bare `return` (implicit). The `save_session()` call goes
immediately after the success log, inside the try block, before the bare return. If
`session_persistence` is disabled or passphrase absent, `save_session()` is a no-op on
the ABC.

```python
# After writeLog("Signed in to Amazon", "INFO"):
await self.save_session()
```

`save_session()` on the ABC:
```python
async def save_session(self) -> None:
    """Save browser cookies after successful login (when session_persistence enabled)."""
    platform_cfg = getattr(getattr(self.config, "platforms", None), self._platform_key, None)
    if not getattr(platform_cfg, "session_persistence", False):
        return
    tab = self.get_active_tab()
    if tab is None:
        return
    # ... read cookies, serialize, call SessionStore.save()
```

[VERIFIED: plugin_base.py lines 87-94, 120-123; amazon/bestbuy login() end of function]

### Pattern 5: restore_session timing

`relaunch()` already calls `restore_session()` AFTER `setup()` (Phase 22, verified in
`plugin_base.py` lines 158-164). This is correct: browser must exist before CDP call.

For bot startup (not relaunch), `restore_session()` must also be called after `setup()`
during the initial plugin launch. The current startup flow in `BotService` calls
`registry.setup_for_items()` which awaits each plugin's `setup()`. The plugin's
`restore_session()` is NOT currently called at startup -- this is a gap to address.

Options:
1. Call `restore_session()` inside `setup()` at the end (coupling concern).
2. Have `PluginRegistry.setup_for_items()` call `restore_session()` after `setup()` for
   each plugin (preferred: mirrors relaunch() sequence, no coupling).
3. Have `relaunch()` and startup share a helper `_setup_and_restore()`.

Recommendation: Option 2 -- add a post-setup restore call in the registry's setup loop.
This keeps `setup()` single-responsibility and matches the `relaunch()` contract exactly.

[ASSUMED: startup flow gap; confirmed relaunch() already correct]

### Anti-Patterns to Avoid

- **Passing `network.Cookie` to `set_cookies()`:** `Cookie` has `size`, `session`,
  `source_scheme`, `source_port` fields not in `CookieParam`. Chrome CDP rejects or
  silently ignores these extra fields. Always build fresh `CookieParam` objects.
- **Using `CookieJar.save()` / `CookieJar.load()`:** These use `pickle` (plaintext,
  insecure) and pass `Cookie` objects to `set_cookies` (type mismatch bug). Never use
  these methods.
- **Using `CookieJar.set_all()`:** Internally calls `storage.set_cookies()` but requires
  `CookieParam` objects anyway -- no value over calling `tab.send()` directly, and the
  existing `CookieJar.load()` bug demonstrates the method is untested for round-trips.
- **Writing JSON cookie file directly:** Plaintext auth material. Always encrypt with
  Fernet before writing. The CI test must assert the file is not valid JSON.
- **Calling `restore_session()` before `setup()`:** Browser does not exist yet; CDP call
  will raise. `relaunch()` already has correct ordering; startup must replicate it.
- **Using `network.set_cookies` instead of `storage.set_cookies`:** Both accept
  `CookieParam`, but `network.set_cookies` is tab-scoped (URL-filtered). Use
  `storage.set_cookies` to match the browser-wide scope of `storage.get_cookies()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AES encryption | Custom cipher | `cryptography.fernet.Fernet` | Already imported; HMAC + AES-128-CBC; proven in credentials.py |
| Key derivation | Custom hash | `_derive_key` from credentials.py | Same scrypt params, same import, no divergence |
| Atomic file write | rename dance | Copy `_save()` pattern from EncryptedFileBackend | Windows-safe os.replace; tmpfile cleanup |
| Cookie type conversion | Custom CDP call | `cdp_network.CookieParam(...)` + `cdp_storage.set_cookies` | Protocol objects handle JSON serialization |
| SameSite enum | String comparison | `cdp_network.CookieSameSite(value)` | Validates enum membership; safe ValueError catch |

## Common Pitfalls

### Pitfall 1: `network.Cookie` passed to `set_cookies` (the confirmed bug)

**What goes wrong:** Chrome CDP `Storage.setCookies` expects `CookieParam` shape. Passing
a `Cookie` (which includes `size`, `session`, `sourceScheme`, `sourcePort`) either raises
a `ProtocolException` or causes Chrome to silently accept but ignore the cookies.
**Why it happens:** `cookie_jar.get_all()` returns `network.Cookie` objects, and it is
tempting to pass them directly to `set_cookies`.
**How to avoid:** Always convert `Cookie` -> plain dict -> `CookieParam`. Only serialize
the 8 fields: name, value, domain, path, expires, httpOnly, secure, sameSite.
**Warning signs:** Session restore appears to succeed (no exception) but cookies are not
actually set in the browser; login page still appears after restore.

### Pitfall 2: `TimeSinceEpoch` serialization

**What goes wrong:** `Cookie.expires` is `Optional[float]`; `CookieParam.expires` is
`Optional[TimeSinceEpoch]` where `TimeSinceEpoch` is a `float` subclass.
`TimeSinceEpoch.to_json()` returns the `TimeSinceEpoch` object itself (not a raw float),
so JSON serialization of a `CookieParam` dict via `to_json()` works correctly inside the
CDP call. For our JSON storage layer, serialize `expires` as a plain Python `float`
(or `None`); on restore, wrap in `TimeSinceEpoch(float(...))`.
**How to avoid:** Use `float(c.expires)` when writing to JSON; use
`cdp_network.TimeSinceEpoch(float(d["expires"]))` when building `CookieParam`.

### Pitfall 3: Expired cookies restored silently

**What goes wrong:** A cookie with `expires` in the past is set in the browser but
immediately purged, so the session appears restored but the site rejects it.
**How to avoid:** In `SessionStore.restore()`, filter out cookies where `expires is not
None and expires < time.time()` before passing to `set_cookies`. Log the count of skipped
expired cookies at DEBUG level. If all cookies are expired, return `None` (triggers
login). [ASSUMED: filtering strategy; could also let Chrome reject and fall back]

### Pitfall 4: Domain/path mismatch

**What goes wrong:** Amazon cookies are scoped to `.amazon.com`; restoring them before
navigating to amazon.com may work (CDP `storage.set_cookies` is browser-wide, not URL-
filtered), but setting cookies without `domain` set causes them to be host-only (no
subdomain matching).
**How to avoid:** Always preserve `domain` and `path` from the saved cookie; never strip
or replace the domain field. Round-trip test must verify `domain` survives.

### Pitfall 5: No passphrase -> silent disable vs. crash

**What goes wrong:** If `SHOPBOT_STORE_PASSPHRASE` is absent and `session_persistence:
true`, the save/restore silently does nothing -- this is intentional per the locked
decision. But a test that expects the session to be restored will silently fail.
**How to avoid:** `SessionStore.__init__` takes `passphrase: bytes | None`; if None,
`save()` and `restore()` are no-ops returning `None`/`False` immediately. The ABC's
`save_session()` / `restore_session()` must check `passphrase is not None` before
constructing a `SessionStore` with cryptographic state.

### Pitfall 6: `data/sessions/` not created before first write

**What goes wrong:** `_save_session` calls `path.parent.mkdir(parents=True, exist_ok=True)`
inside the method, but if the dir doesn't exist and `tempfile.mkstemp(dir=...)` is
called with a non-existent dir, it raises `FileNotFoundError` before mkdir runs.
**How to avoid:** Call `path.parent.mkdir(parents=True, exist_ok=True)` BEFORE
`tempfile.mkstemp(dir=...)`. This is the same ordering in `EncryptedFileBackend._save()`.
[VERIFIED: credentials.py lines 269-270]

### Pitfall 7: `restore_session()` called at bot startup is currently missing

**What goes wrong:** `relaunch()` already calls `restore_session()` after `setup()`.
But the initial startup sequence (first `setup()` call) does NOT call `restore_session()`.
If a session file exists and `session_persistence: true`, the first run after a restart
will still do a full login even though it could have been skipped.
**How to avoid:** After `registry.setup_for_items()` (or equivalent), call
`restore_session()` on each plugin and skip `login()` if it returns `True`. This is a
new code path not currently in the orchestrator.

## Code Examples

### Full save flow (verified against installed nodriver 0.50.3)

```python
# Source: verified via inspect on nodriver.core.tab.Tab.send + nodriver.cdp.storage
from nodriver.cdp import storage as cdp_storage, network as cdp_network

async def _read_cookies_for_save(tab) -> list[dict]:
    """Read all browser cookies and serialize to JSON-safe dicts."""
    cookies: list[cdp_network.Cookie] = await tab.send(cdp_storage.get_cookies())
    return [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
            "expires": float(c.expires) if c.expires is not None else None,
            "http_only": c.http_only,
            "secure": c.secure,
            "same_site": c.same_site.value if c.same_site is not None else None,
        }
        for c in cookies
    ]
```

### Full restore flow (verified against installed nodriver 0.50.3)

```python
# Source: verified via inspect on nodriver.core.tab.Tab.send + nodriver.cdp.storage/network
import time
from nodriver.cdp import storage as cdp_storage, network as cdp_network

async def _restore_cookies(tab, cookie_dicts: list[dict]) -> None:
    """Build CookieParam objects and set them via raw CDP."""
    now = time.time()
    params = []
    for d in cookie_dicts:
        # Skip expired cookies (Pitfall 3)
        exp = d.get("expires")
        if exp is not None and float(exp) < now:
            continue
        same_site = None
        if d.get("same_site"):
            try:
                same_site = cdp_network.CookieSameSite(d["same_site"])
            except ValueError:
                pass
        expires_param = cdp_network.TimeSinceEpoch(float(exp)) if exp is not None else None
        params.append(cdp_network.CookieParam(
            name=d["name"],
            value=d["value"],
            domain=d.get("domain"),
            path=d.get("path"),
            expires=expires_param,
            http_only=d.get("http_only"),
            secure=d.get("secure"),
            same_site=same_site,
        ))
    if params:
        await tab.send(cdp_storage.set_cookies(params))
```

### CookieParam constructor signature (VERIFIED against nodriver 0.50.3)

```python
# Required fields (no default):
#   name: str
#   value: str
# Optional fields (all default None):
#   url: Optional[str]
#   domain: Optional[str]
#   path: Optional[str]
#   secure: Optional[bool]
#   http_only: Optional[bool]
#   same_site: Optional[CookieSameSite]
#   expires: Optional[TimeSinceEpoch]  # TimeSinceEpoch(float) - float subclass
#   priority: Optional[CookiePriority]
#   source_scheme: Optional[CookieSourceScheme]
#   source_port: Optional[int]
#   partition_key: Optional[CookiePartitionKey]

# CookieSameSite enum values:
#   CookieSameSite.STRICT = 'Strict'
#   CookieSameSite.LAX    = 'Lax'
#   CookieSameSite.NONE   = 'None'
```

[VERIFIED: inspect.getsource(storage.set_cookies) + dataclasses.fields(CookieParam) on
installed nodriver 0.50.3 at C:\Users\brand\AppData\Roaming\Python\Python313\site-packages\nodriver]

### SHOPBOT_STORE_PASSPHRASE resolution (mirrors credentials.py)

```python
# Source: core/credentials.py _resolve_passphrase() lines 323-334 (verified)
import os

def _get_session_passphrase() -> bytes | None:
    val = os.environ.get("SHOPBOT_STORE_PASSPHRASE")
    return val.encode() if val else None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `CookieJar.save()` / pickle | Fernet-encrypted JSON | Phase 23 | Plaintext removed; no pickle deserialization attack surface |
| `CookieJar.set_all()` / `Cookie` objects | `tab.send(cdp.storage.set_cookies([CookieParam(...)]))` | Phase 23 | Correct CDP type; no silent cookie rejection |
| `restore_session()` no-op stub (Phase 22) | Live SessionStore.restore() | Phase 23 | MFA skip across restarts |

**Deprecated/outdated:**
- `CookieJar.save()` / `CookieJar.load()`: use plaintext pickle; do not use.
- `CookieJar.set_all()`: takes `CookieParam` list, but relies on picking a tab from the
  browser iterator (fragile); direct `tab.send()` is more explicit.

## nodriver CDP Cookie API (VERIFIED Summary)

This section is the primary research deliverable. All claims verified against installed
nodriver 0.50.3.

### GET cookies (saving)

```python
from nodriver.cdp import storage as cdp_storage
# Returns List[network.Cookie] -- browser-wide, all tabs
cookies = await tab.send(cdp_storage.get_cookies())
# CDP method: 'Storage.getCookies'
```

### SET cookies (restoring)

```python
from nodriver.cdp import storage as cdp_storage, network as cdp_network
# Accepts List[network.CookieParam] -- browser-wide
# CDP method: 'Storage.setCookies'
await tab.send(cdp_storage.set_cookies(cookies=[CookieParam(name=..., value=..., ...)]))
```

### Import path

```python
from nodriver.cdp import storage as cdp_storage
from nodriver.cdp import network as cdp_network
# cdp_storage.get_cookies()      -> generator for tab.send()
# cdp_storage.set_cookies([...]) -> generator for tab.send()
# cdp_network.CookieParam        -> dataclass for set_cookies param
# cdp_network.CookieSameSite     -> enum (STRICT/LAX/NONE, values 'Strict'/'Lax'/'None')
# cdp_network.TimeSinceEpoch     -> float subclass for expires field
# cdp_network.Cookie             -> return type of get_cookies (DO NOT pass to set_cookies)
```

### The `CookieJar.set_all()` bug (confirmed)

`CookieJar.set_all()` does internally call `cdp.storage.set_cookies()`, BUT:
1. `CookieJar.load()` passes `network.Cookie` objects (from pickle), not `CookieParam`.
   `Cookie.to_json()` includes `size`, `session`, `sourceScheme`, `sourcePort` keys that
   CDP `Storage.setCookies` does not accept in cookie params.
2. `CookieJar.save()` / `load()` uses `pickle` (plaintext, insecure).
3. `CookieJar.set_all()` picks a connection by iterating `self._browser` (fragile if
   browser has no active tab with a target).

The workaround (direct `tab.send()` with fresh `CookieParam` objects built from our
serialized dict) is correct and avoids all three issues.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Filtering expired cookies before restore_session (by comparing float(expires) < time.time()) is the right strategy | Common Pitfalls #3 | Expired cookies silently set; Chrome purges them; login still required (fallback works, just slower) |
| A2 | Startup restore_session() gap should be fixed by calling restore_session() in PluginRegistry.setup_for_items() after setup() | Architecture Patterns #5 | First run after restart still does full login (inconvenient but not broken -- relaunch() path still correct) |
| A3 | `cdp_storage.set_cookies` (browser-wide) is preferable to `cdp_network.set_cookies` (tab-scoped) for restore | Code Examples | Tab-scoped would also work for Amazon/BestBuy since we restore before any navigation |

## Open Questions

1. **Startup restore vs. relaunch-only restore**
   - What we know: `relaunch()` calls `restore_session()` correctly (Phase 22). Initial
     startup does not.
   - What's unclear: Whether the planner should add restore to `setup_for_items()` or
     to a new explicit startup hook.
   - Recommendation: Add to `setup_for_items()` loop immediately after each `plugin.setup()`,
     mirroring the relaunch() sequence exactly. If restore returns True, log and skip login;
     otherwise log and proceed normally.

2. **Config field placement for `session_persistence`**
   - What we know: Locked decision says add to all 7 platform config models individually
     (or a shared base).
   - What's unclear: Whether to add to each of the 7 models individually or introduce a
     shared `PlatformBaseConfig` mixin.
   - Recommendation: Add individually to each of the 7 models for now (simplest, no new
     abstraction needed; the 7 models already share no base class).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python `cryptography` | Fernet + scrypt | Yes | installed (pinned) | -- |
| `nodriver` | CDP cookie API | Yes | 0.50.3 | -- |
| `SHOPBOT_STORE_PASSPHRASE` env var | Session encryption | runtime | set by user | Silent no-op (disabled) |
| `data/sessions/` directory | Session file storage | created on demand | -- | mkdir on first save |

**Missing dependencies with no fallback:** none
**Missing dependencies with fallback:** `SHOPBOT_STORE_PASSPHRASE` absent -> persistence
silently disabled (by design, per locked decisions).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio 1.3.0 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_session_store.py -x` |
| Full suite command | `pytest` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REL-04 | SessionStore save/restore round-trip with fake passphrase | unit | `pytest tests/test_session_store.py::test_save_restore_roundtrip -x` | No - Wave 0 |
| REL-04 | No plaintext file written (file is not valid JSON) | unit | `pytest tests/test_session_store.py::test_no_plaintext_file -x` | No - Wave 0 |
| REL-04 | restore() returns None on missing file | unit | `pytest tests/test_session_store.py::test_restore_missing_file -x` | No - Wave 0 |
| REL-04 | restore() returns None on corrupt data | unit | `pytest tests/test_session_store.py::test_restore_corrupt_data -x` | No - Wave 0 |
| REL-04 | restore() returns None on wrong passphrase (InvalidToken) | unit | `pytest tests/test_session_store.py::test_restore_wrong_passphrase -x` | No - Wave 0 |
| REL-04 | CookieParam serialization round-trip (dict -> CookieParam -> to_json fields) | unit | `pytest tests/test_session_store.py::test_cookie_param_roundtrip -x` | No - Wave 0 |
| REL-04 | restore_session() skips login when session exists (ABC hook) | unit | `pytest tests/test_session_store.py::test_restore_session_skips_login -x` | No - Wave 0 |
| REL-04 | save_session() no-op when session_persistence=False | unit | `pytest tests/test_session_store.py::test_save_noop_when_disabled -x` | No - Wave 0 |
| REL-04 | save_session() no-op when passphrase absent | unit | `pytest tests/test_session_store.py::test_save_noop_no_passphrase -x` | No - Wave 0 |
| REL-04 | session_persistence: bool = False default on all 7 platform configs | unit | `pytest tests/test_config_schema.py -k session_persistence -x` | Partial - extend existing |
| REL-04 | CI: no data/sessions/*.bin tracked in git | CI/unit | `pytest tests/test_no_committed_sessions.py -x` | No - Wave 0 |
| REL-04 | CI: data/sessions/ is gitignored | CI/unit | `pytest tests/test_no_committed_sessions.py::test_sessions_dir_gitignored -x` | No - Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_session_store.py -x`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_session_store.py` -- covers all REL-04 unit tests above
- [ ] `tests/test_no_committed_sessions.py` -- CI guard for no tracked session files

*(Existing `tests/test_config_schema.py` and `tests/test_relaunch.py` need extension,
not new files.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Session restore bypasses login only when decryption succeeds |
| V3 Session Management | yes | Fernet AES-128-CBC+HMAC; scrypt KDF; salt per write |
| V4 Access Control | no | -- |
| V5 Input Validation | yes | `InvalidToken` catch; expired cookie filter; SameSite enum validation |
| V6 Cryptography | yes | Fernet (never hand-rolled); `_derive_key` from credentials.py |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Plaintext cookie file read by attacker | Information Disclosure | Fernet AES-128-CBC+HMAC; assertion test verifies file is not valid JSON |
| Wrong-passphrase session restore | Spoofing | `InvalidToken` caught; returns None; fallback to login (never crash) |
| Pickle deserialization attack | Tampering | No pickle; JSON only |
| Expired session cookie replay | Elevation of Privilege | Filter `expires < time.time()` before set_cookies |
| Session file committed to git | Information Disclosure | `data/*` gitignore covers `data/sessions/`; CI test asserts no tracked files |
| Passphrase logged on error | Information Disclosure | Follow credentials.py pattern: log class name only, never passphrase value |

## Sources

### Primary (HIGH confidence)

- Installed nodriver 0.50.3 at `C:\Users\brand\AppData\Roaming\Python\Python313\site-packages\nodriver` -- inspected via `inspect.getsource()` and `dataclasses.fields()` for: `storage.get_cookies`, `storage.set_cookies`, `network.CookieParam` (all fields + types), `network.Cookie` (all fields), `network.CookieSameSite` (enum values), `network.TimeSinceEpoch` (float subclass), `Tab.send()` (full source), `CookieJar` (full class including `set_all`, `save`, `load`)
- `core/credentials.py` (project codebase) -- `_derive_key` signature, `SALT_LEN`, `EncryptedFileBackend._load/_save` pattern, `_resolve_passphrase`, `SHOPBOT_STORE_PASSPHRASE` resolution
- `core/plugin_base.py` (project codebase) -- `restore_session()` stub, `relaunch()` sequence, `get_active_tab()`, `save_session` hook point
- `core/config_schema.py` (project codebase) -- all 7 platform config models, no shared base class
- `plugins/shopbot_plugin_amazon.py` + `plugins/shopbot_plugin_bestbuy.py` -- `login()` end-of-success hook point, `get_active_tab()` override
- `.gitignore` line 8: `data/*` -- covers `data/sessions/` [VERIFIED]

### Secondary (MEDIUM confidence)

- nodriver issues #1816/#2020 referenced in CONTEXT.md -- bug characterization confirmed by local source inspection: `CookieJar.load()` passes `Cookie` to `set_cookies` (which expects `CookieParam`); `CookieJar.save()` uses pickle

## Metadata

**Confidence breakdown:**
- nodriver CDP API: HIGH -- all signatures verified against installed package via inspect
- Fernet/scrypt reuse: HIGH -- verified against credentials.py source
- Architecture patterns: HIGH -- all hook points confirmed in plugin_base.py, amazon, bestbuy
- Startup restore gap: MEDIUM -- code path traced; implementation approach is ASSUMED
- Expired cookie filter strategy: LOW -- one reasonable approach; others exist

**Research date:** 2026-06-12
**Valid until:** 2026-07-12 (stable APIs; nodriver 0.50.3 is pinned)
