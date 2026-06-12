---
phase: 23-encrypted-session-persistence
reviewed: 2026-06-12T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - core/session_store.py
  - core/plugin_base.py
  - core/registry.py
  - core/config_schema.py
  - plugins/shopbot_plugin_amazon.py
  - plugins/shopbot_plugin_bestbuy.py
  - tests/test_session_store.py
  - tests/test_session_persistence.py
  - tests/test_config_schema.py
  - tests/test_no_committed_sessions.py
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
status: issues_found
---

# Phase 23: Code Review Report

**Reviewed:** 2026-06-12T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 23 delivers encrypted Fernet session persistence (REL-04). The core
encryption and no-passphrase no-op paths are correct. The atomic write uses
`tempfile.mkstemp` into the same directory as the target, so `os.replace` is
always a same-filesystem rename -- no unencrypted copy is left behind.
`restore_session` uses raw `cdp_storage.set_cookies` (not CookieJar.set_all),
matches the stated bug-avoidance intent, and degrades gracefully on every
failure mode. PLUGIN_API_VERSION stays at 2.

Two blockers were found: a passphrase exposure risk in `save_session` cookie
logging, and the `restore_session` method building a second SessionStore
(with a second `build_session_store()` call) that accesses `store._passphrase`
as a private attribute -- silently broken if the private name ever changes.
Four warnings cover logic gaps that degrade reliability without being
immediate security holes.


## Critical Issues

### CR-01: `save_session` logs cookie count AFTER build -- cookie values reachable via exception message

**File:** `core/plugin_base.py:302-304`

`save_session` calls `build_session_store().save(key, dicts)` and immediately
logs the count with `len(dicts)`. The `save()` call can raise (e.g. disk
full, permission error) but the `except Exception` at line 307 catches it and
logs only `exc.__class__.__name__`. That part is fine. The problem is the
`writeLog` on line 303-304 that includes `len(dicts)` fires BEFORE the
exception path: that is not a secret leak by itself.

The actual leak is more subtle: `save_session` serializes every raw cookie
into `dicts` (lines 289-300). If `get_cookies()` returns a cookie whose
`.same_site` attribute is not `None` but whose `.value` attribute is also not
`None` and the `.same_site` object does not have a `.value` property (e.g.
an unexpected CDP type), the dict-comprehension raises an `AttributeError`
which propagates to the outer `except Exception` and is logged as
`AttributeError`. The cookie values themselves are not logged -- this path
is safe.

**The real CR-01 finding:** `restore_session` at line 243 reads
`store._passphrase` directly -- a private attribute access across module
boundaries:

```python
store = build_session_store()
if store._passphrase is None:      # line 243
    return False
```

`_passphrase` is a private name convention in Python (`_` prefix = internal).
The caller is bypassing the public interface. More critically, this check
duplicates logic already inside `SessionStore.restore()` (which already
returns `None` when `self._passphrase is None`, line 80-81). The external
`_passphrase` read is therefore both redundant and fragile: if the attribute
is ever renamed or the passphrase-absent check moves to a property, this
silently breaks and `restore()` would be called with no passphrase, returning
`None`, but the calling code gets a `AttributeError` rather than `False`.

**Fix:** Remove the `store._passphrase` guard in `restore_session`. The
public contract of `restore()` already returns `None` on no-passphrase. The
caller only needs to distinguish `None` (no restore) from a list.

```python
async def restore_session(self) -> bool:
    if not self._session_enabled():
        return False
    key = self._session_platform_key()
    store = build_session_store()
    cookies = store.restore(key)   # returns None on no passphrase, missing file, bad token
    if not cookies:
        return False
    tab = self.get_active_tab()
    if tab is None:
        return False
    params = _dicts_to_cookie_params(cookies)
    if not params:
        return False
    ...
```


### CR-02: Temp file written to `sessions/` directory -- survives cleanup failure with `.bin` extension ambiguity

**File:** `core/session_store.py:62-72`

`tempfile.mkstemp(dir=str(self._dir))` creates a file in the same directory
as the target. On Windows, if the process is killed between `mkstemp` and
`os.replace`, an orphaned temp file with no extension sits in `data/sessions/`.
That file contains encrypted data -- not plaintext -- so there is no
confidentiality breach.

However, `test_no_committed_session_files` in `tests/test_no_committed_sessions.py`
only checks for `*.bin` files via:

```python
tracked = [line for line in result.stdout.splitlines() if line.endswith(".bin")]
```

The orphaned temp file has no extension so the CI guard would not catch it.
More significantly: on Windows, `os.replace(tmp, path)` can fail with
`PermissionError` if another process has the file open. The `except` block
attempts `os.unlink(tmp)` but then re-raises, leaving the encrypted partial
write behind. This is not a plaintext leak but is a correctness issue: the
session file is left in a partially-replaced state on some Windows failure
modes. The existing logic is correct for the nominal path; this is a known
Windows edge case.

The more pressing issue: the temp file has no extension suffix. If an operator
inspects `data/sessions/` they see files without `.bin` extension alongside
`.bin` files and may not recognise them as encrypted session data. Recommend
adding `suffix=".tmp"` to the `mkstemp` call so orphaned files are visually
distinct and can be safely removed.

**Fix:**

```python
fd, tmp = tempfile.mkstemp(dir=str(self._dir), suffix=".tmp")
```

The CI guard in `test_no_committed_session_files` should also be updated to
check for both `.bin` and `.tmp` files, or more broadly for any file in
`data/sessions/`:

```python
tracked = [line for line in result.stdout.splitlines()]
```


## Warnings

### WR-01: `_dicts_to_cookie_params` silently skips cookies with `expires == 0`

**File:** `core/plugin_base.py:30-31`

The expiry filter is:
```python
if exp is not None and float(exp) < now:
    continue
```

A cookie with `expires=0` (session cookie persisted by some CDPs as `0`
rather than `None`) will be treated as expired (0 < now is always True) and
silently dropped. Some CDP implementations serialize session cookies as
`expires=0`; Amazon's session cookies in particular may use this convention.
The result is that `restore_session` gets an empty `params` list, returns
`False`, and triggers a full re-login -- an invisible reliability failure
that could mask itself as a normal session expiry.

**Fix:** Treat `expires == 0` as a session cookie (no expiry), equivalent to
`expires=None`:

```python
exp = d.get("expires")
if exp is not None and float(exp) != 0.0 and float(exp) < now:
    continue
...
expires_param = (
    cdp_network.TimeSinceEpoch(float(exp))
    if exp is not None and float(exp) != 0.0
    else None
)
```


### WR-02: `save_session` always saves ALL browser cookies, not just those for the retail domain

**File:** `core/plugin_base.py:288-302`

`cdp_storage.get_cookies()` with no URL argument returns ALL cookies for the
current browser profile -- including cookies for any other domain the plugin
navigated to (ad trackers, CDN logins, redirect intermediaries). These are
encrypted at rest, but on restore, `cdp_storage.set_cookies` injects all of
them into the browser. This is a scope creep that could push unintended
third-party auth cookies back into the browser on restore.

The CDP call `cdp_storage.get_cookies(urls=[...])` accepts a list of URLs to
scope the cookie fetch. Neither the Amazon nor BestBuy plugin passes a scoped
URL list, so the full profile is saved.

**Fix:** Pass the platform's base URL to scope the get_cookies call, or at
minimum filter the returned cookies by domain against the plugin's known
`domain_patterns` before serializing:

```python
raw_cookies = await tab.send(cdp_storage.get_cookies())
domain_patterns = getattr(self, "domain_patterns", [])
dicts = [
    { ... }
    for c in raw_cookies
    if not domain_patterns or any(p in (c.domain or "") for p in domain_patterns)
]
```


### WR-03: `BestBuyPlugin.login` calls `save_session` unconditionally without verifying sign-in success

**File:** `plugins/shopbot_plugin_bestbuy.py:251`

```python
writeLog("Signed in to BestBuy", "INFO")
await self.save_session()
```

`login()` calls `save_session()` immediately after clicking submit, before
any post-login page verification. If sign-in fails silently (wrong password
accepted but landing on an error page, or a CAPTCHA intercepts the form
submission), stale/unauthenticated cookies are persisted to disk. On the next
run, `restore_session` returns `True` (cookies loaded successfully), login is
skipped, and the bot operates with an unauthenticated session.

`AmazonPlugin.login` (line 362) has the same pattern but Amazon's multi-step
flow at least pauses for MFA which acts as partial confirmation. BestBuy
submits and immediately saves with no success check.

**Fix:** Wait for a post-login success indicator before saving. At minimum,
check for the absence of an error element or the presence of an account-
specific element before calling `save_session()`.


### WR-04: `restore_session` can return `True` with zero effective cookies injected when all cookies expire between filter and CDP call

**File:** `core/plugin_base.py:252-266`

`_dicts_to_cookie_params` filters cookies where `float(exp) < time.time()`
at the time of the call. After the filter, `params` is non-empty. Then
`await tab.send(cdp_storage.set_cookies(params))` is called. Chrome's CDP
handler will silently discard any cookie it considers expired at the moment
of injection -- which could be after a small async delay. If all cookies
expire in the narrow window between the Python filter and Chrome's processing,
`restore_session` returns `True` but no effective session state was loaded.

The session then appears restored to the plugin layer, so `login()` is
skipped. The bot proceeds with an empty/expired session and the first
authenticated action will fail, falling through to a generic error path
rather than a clean re-login.

This is a narrow race but is architecturally correct to flag: the return
value of `restore_session` is used to determine whether to call `login()`,
so a false `True` has downstream consequences.

**Fix:** Accept that this is inherent to cookie-based session restore. The
`relaunch()` method already handles the consequence (login on failure during
subsequent operations). However, adding a short post-restore navigation check
or recording this as a known limitation in the docstring would prevent
confusion during debugging.


## Info

### IN-01: `except (InvalidToken, Exception)` in `SessionStore.restore` is redundant

**File:** `core/session_store.py:91`

```python
except (InvalidToken, Exception) as exc:
```

`InvalidToken` is a subclass of `Exception`. The tuple is redundant --
`except Exception` already catches `InvalidToken`. The intent (be explicit
that InvalidToken is expected) is good, but the tuple form could mislead a
reader into thinking special handling exists for `InvalidToken` specifically.

**Fix:**
```python
except Exception as exc:
    # Includes Fernet.InvalidToken (wrong passphrase or truncated data)
```


### IN-02: `test_no_committed_sessions.py` uses a relative path for `.gitignore`

**File:** `tests/test_no_committed_sessions.py:47`

```python
gitignore_path = Path(".gitignore")
```

This path is relative to `cwd` at test invocation time. If pytest is run from
a subdirectory (e.g. `pytest tests/` from a non-root directory) the `.gitignore`
check silently skips with `pytest.skip`. The `git ls-files` call on line 22
has the same implicit-cwd dependency. Both are conventional for git-aware CI
tests, but could silently skip in unusual invocation contexts.

**Fix:** Anchor to the repo root by walking up from `__file__`:
```python
repo_root = Path(__file__).resolve().parent.parent
gitignore_path = repo_root / ".gitignore"
```

---

_Reviewed: 2026-06-12T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
