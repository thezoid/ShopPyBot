---
phase: 08-credential-store
reviewed: 2026-06-04T00:00:00Z
depth: standard
iteration: 2
files_reviewed: 13
files_reviewed_list:
  - core/credentials.py
  - core/service.py
  - notifications/__init__.py
  - notifications/discord_notifier.py
  - plugins/shopbot_plugin_amazon.py
  - plugins/shopbot_plugin_bestbuy.py
  - plugins/shopbot_plugin_gamestop.py
  - plugins/shopbot_plugin_newegg.py
  - plugins/shopbot_plugin_squareenix.py
  - plugins/shopbot_plugin_target.py
  - plugins/shopbot_plugin_walmart.py
  - tests/conftest.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 8: Code Review Report (Iteration 2 -- Fix Verification)

**Reviewed:** 2026-06-04T00:00:00Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

This is a re-review verifying the fixer's iteration-1 changes against the prior 1 Critical + 7 Warning findings, and scanning for regressions introduced by those fixes.

**CR-01 (secret leakage) is resolved.** All 21 exception handlers across the 7 reviewed plugins (`check_availability`, `login`, `auto_buy`) now log `f"...: {exc.__class__.__name__}"` and never interpolate the raw exception object. A repo-wide scan for `{exc}` / `str(exc)` / `repr(exc)` returns zero hits inside the seven reviewed plugins. The two secret-bearing call sites that motivated the blocker -- Amazon/BestBuy/etc. `send_keys(password)` in `login()` and `send_keys(self._cvv)` in BestBuy `auto_buy` (line 160) -- are each wrapped by an in-plugin `try/except` that now logs the type only and returns False/True, so no secret-bearing exception can propagate to the orchestrator. The full suite passes: 255 passed, 1 xpassed, 0 failures.

**All 7 warnings (WR-01..WR-07) and 2 info items (IN-02, IN-05) are correctly applied:**
- WR-01: `_has_real_keyring()` now does a `set/get/delete` round-trip probe after the type checks (credentials.py:159-168), catching a ChainerBackend over fail/null leaves.
- WR-02: service loop splits `except asyncio.CancelledError: pass` from `except Exception as exc: writeLog(... exc.__class__.__name__ ...)` (service.py:98-104).
- WR-03: `_running = True` set synchronously before thread start (service.py:85); duplicate-launch guard checks both `_running` and `_thread.is_alive()` (line 82); `ready.wait()` return value is checked and logged on timeout (lines 118-120).
- WR-04: `isolated_keyring` captures `original = get_keyring()` and restores via `set_keyring(original)` (conftest.py:294-298).
- WR-05: `EncryptedFileBackend` gets a per-instance `threading.Lock`; `set`/`delete` wrap load-modify-save in `with self._lock` (credentials.py:237, 274-284).
- WR-06: `migrate_from_env` read-back-verifies via `store.get(key)` before appending the key name, warns (name-only) on no-op, and catches/logs `set` exceptions by type (credentials.py:392-410).
- WR-07: `build_dispatcher` reads `DISCORD_WEBHOOK_URL` once and passes it to `DiscordNotifier(discord_url)`; the notifier accepts `webhook_url` and no longer re-reads the store (init.py:43-45, discord_notifier.py:63-68).
- IN-02 / IN-05: dead set/del/set triple removed; unused `import keyring.core` removed from `credentials.py`.

The fixes introduced no new Critical issues. Two Warnings remain: one is a latent semantic mismatch in `data_dir` handling (pre-existing, not introduced by the fix but located in a reviewed file and worth flagging), and one is a side effect of the new keyring probe that writes to the live OS keyring. Three Info items cover residual edge cases and minor dead-import cleanup.

## Warnings

### WR-01: `data_dir` config field is treated as a full file path, not a directory, contradicting its name and docstring

**File:** `core/credentials.py:338-342`, `core/config_schema.py:206-212`

**Issue:** `CredentialsConfig.data_dir` is documented as "where the encrypted file lives" and named like a directory; the default comment says "empty = data/creds.bin (project-relative default)". But `_build_store` does:
```python
store_path = (
    Path(cfg.credentials.data_dir)
    if getattr(cfg.credentials, "data_dir", "")
    else _DEFAULT_STORE_PATH
)
```
and passes `store_path` straight to `EncryptedFileBackend(store_path, passphrase)` as the file path. If an operator sets `data_dir: "data"` (a directory, as the name strongly implies), `EncryptedFileBackend._save` computes `dir_ = self._path.parent` (the parent of `data`), writes a tempfile there, then `os.replace(tmp, Path("data"))`. If `data` already exists as a directory, `os.replace` raises (`IsADirectoryError` / `PermissionError` on Windows); if it does not, the encrypted blob is written as a file literally named `data` in the CWD instead of inside it. The credential store silently lands in the wrong place or fails to save on first `set`. The `_DEFAULT_STORE_PATH` branch correctly points at `data/creds.bin`, so the only-broken case is the explicit-config case the field exists to serve. Not introduced by the iteration-1 fixes, but it sits in a reviewed file and is a real foot-gun.

**Fix:** Treat `data_dir` as a directory and append the filename, or rename the field to `store_path`. Minimal directory-semantics fix:
```python
store_path = (
    Path(cfg.credentials.data_dir) / "creds.bin"
    if getattr(cfg.credentials, "data_dir", "")
    else _DEFAULT_STORE_PATH
)
```

### WR-02: `_has_real_keyring()` functional probe writes to the live OS keyring and can leave a stray `__probe__` entry

**File:** `core/credentials.py:159-168`

**Issue:** The WR-01-iteration-1 fix added a round-trip probe that runs against the *real* default keyring during auto-detect:
```python
keyring.set_password("shopbot", "__probe__", "1")
ok = keyring.get_password("shopbot", "__probe__") == "1"
try:
    keyring.delete_password("shopbot", "__probe__")
except Exception:
    pass
return ok
```
Two consequences: (1) a "read-only" backend-detection step now performs a *write* into the user's OS credential manager under the same `shopbot` service the app uses for real secrets; (2) if `set_password` succeeds but `delete_password` raises (caught and swallowed), a stray `shopbot/__probe__` entry persists in the user's keyring indefinitely. It is not a secret (value `"1"`) and `KeyringBackend.list()` only enumerates `SECRET_KEYS`, so it will not surface in `list()`, but it is residue in the user's credential store from a detection probe. The probe also runs on every `init_store()` call, so the write/delete churn repeats each startup.

**Fix:** Use a service name distinct from the real store for the probe (e.g. `"shopbot-probe"`) so a leaked entry never collides with real keys, and consider gating the probe behind the existing type checks only when the backend is a chainer (the common false-positive case) rather than always. At minimum, document that auto-detect performs a keyring write.

## Info

### IN-01: `start()` can return with `_running == True` but `_loop`/`_task` unset on a slow-loop timeout

**File:** `core/service.py:85, 118-120, 128`

**Issue:** WR-03's fix sets `_running = True` synchronously (good for the duplicate-launch guard). On the success path the ordering is correct: `_task` is assigned (line 94) before `ready.set()` (line 95), so a returning `start()` sees both `_loop` and `_task` populated. But if the daemon thread is slow and `ready.wait(timeout=5.0)` returns `False`, `start()` returns (after logging the warning) with `_running == True` while `_loop`/`_task` may still be `None`. A `stop()` called in that window passes the `not self._running` guard (line 128) but then finds `self._loop is None` and returns as a silent no-op, even though the thread is in fact starting up. The window is narrow and now logged, so this is Info rather than Warning.

**Fix:** On `ready.wait()` timeout, either reset `self._running = False` and raise/return an explicit failure, or have `stop()` additionally `join()` the thread handle when `_loop is None` so a starting-up thread is not orphaned.

### IN-02: `conftest.py` imports `keyring.core as _keyring_core` but no longer uses it

**File:** `tests/conftest.py:13`

**Issue:** After the WR-04 fix switched teardown to `_keyring_module.set_keyring(original)`, the `_keyring_core` import is dead -- it now serves only to gate `_KEYRING_AVAILABLE` (which `import keyring as _keyring_module` already establishes). Harmless, but it reads as leftover from the old `_keyring_backend = None` reset approach.

**Fix:** Drop `import keyring.core as _keyring_core`; the bare `import keyring as _keyring_module` inside the same `try` already sets `_KEYRING_AVAILABLE` correctly.

### IN-03: `core/credentials.py` still exceeds the 300-line project file limit

**File:** `core/credentials.py:1-425`

**Issue:** The file grew to 425 lines (was 397 at iteration 1) after the lock and probe additions; CLAUDE.md sets a 300-line ceiling. Carried over from IN-01 in the prior review; not load-bearing for correctness.

**Fix:** Optional split: move the three backend classes into `core/credential_backends.py`, leaving `credentials.py` as the selection/singleton/migration surface.

---

_Reviewed: 2026-06-04T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Iteration: 2_
