---
phase: 08-credential-store
reviewed: 2026-06-04T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - core/credentials.py
  - core/config_schema.py
  - core/service.py
  - notifications/__init__.py
  - notifications/discord_notifier.py
  - notifications/email_notifier.py
  - notifications/sms_notifier.py
  - plugins/shopbot_plugin_amazon.py
  - plugins/shopbot_plugin_bestbuy.py
  - plugins/shopbot_plugin_gamestop.py
  - plugins/shopbot_plugin_newegg.py
  - plugins/shopbot_plugin_squareenix.py
  - plugins/shopbot_plugin_target.py
  - plugins/shopbot_plugin_walmart.py
  - tests/conftest.py
  - tests/test_credentials.py
  - tests/test_no_env_secret_reads.py
  - tests/test_no_plaintext.py
findings:
  critical: 1
  warning: 7
  info: 5
  total: 13
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-06-04T00:00:00Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 8 introduces a credential-store abstraction (`core/credentials.py`) with three backends (env-var, OS keyring, scrypt+Fernet encrypted file) and migrates every consumer (7 plugins, 3 notifiers, dispatcher factory) from direct `os.environ` reads to `get_store().get()`. The core crypto is sound: scrypt parameters are RFC 7914 interactive-login values, salt is per-write random (`os.urandom(16)`), the passphrase is never persisted, decryption failures are caught and re-raised as a clean `ValueError` that names only the env-var, and the atomic write closes the fd before `os.replace`. The no-plaintext and no-env-read guard tests are well-constructed.

The migration itself is largely faithful and identity-preserving for the env backend. However, the review surfaced one blocker (broad secret-bearing exception messages logged at the plugin boundary), several robustness gaps (keyring chainer/null detection, silent exception swallow in the service loop, fragile thread-start handshake), and a handful of quality issues (file exceeds the 300-line project limit, confusing dead test code).

## Critical Issues

### CR-01: Plugin exception handlers log `str(exc)`, which can leak credential values on `send_keys` failure

**File:** `plugins/shopbot_plugin_amazon.py:176-177`, `plugins/shopbot_plugin_amazon.py:109-111`, and the identical pattern in `shopbot_plugin_bestbuy.py:104-105`, `shopbot_plugin_gamestop.py:124-125`, `shopbot_plugin_newegg.py:135-136`, `shopbot_plugin_squareenix.py:126-127`, `shopbot_plugin_target.py:124-125`, `shopbot_plugin_walmart.py:122-123`

**Issue:** Each `login()` reads the password from the store and immediately passes it to `await <field>.send_keys(password)`. The surrounding handler is `except Exception as exc: writeLog(f"Error during <X> sign-in: {exc}", "ERROR")`. `writeLog` mirrors every message to `logs/YYYYMONTHDD.log` (see `logger.py:46`). nodriver/CDP element-interaction errors frequently embed the element value or the arguments being dispatched in their exception text; any exception raised from inside `send_keys(password)` (or `send_keys(email)`, or `send_keys(self._cvv)` in BestBuy `auto_buy`) can therefore write the secret to the on-disk log in plaintext. This directly contradicts the file-level security contract ("Neither value is ever logged") and the project no-plaintext-on-disk guarantee. The notifier modules correctly avoid this by logging only `exc.__class__.__name__` / HTTP status; the plugins do not apply the same discipline.

**Fix:** Never interpolate raw exception objects in the secret-handling paths. Log the exception type only, matching the notifier pattern:
```python
except Exception as exc:
    writeLog(
        f"Error during Amazon sign-in: {exc.__class__.__name__}",
        "ERROR",
    )
```
Apply to every `login()` handler and to BestBuy `auto_buy` (the CVV path at `shopbot_plugin_bestbuy.py:156-160` is inside a handler that logs `{exc}` at line 171). The `check_availability` handlers are lower risk but share the same `{exc}` pattern and should be hardened for consistency.

## Warnings

### WR-01: `_has_real_keyring()` does not detect a chainer that wraps only fail/null backends

**File:** `core/credentials.py:141-157`

**Issue:** The guard checks `isinstance(backend, fail.Keyring)` and `isinstance(backend, null.Keyring)`. On many systems `keyring.get_keyring()` returns a `ChainerBackend` (priority-ordered chain), not the leaf backend. If the chain contains only fail/null leaves (e.g. headless Linux with no Secret Service, or a CI box), the chainer instance is neither a `fail.Keyring` nor a `null.Keyring`, so `_has_real_keyring()` returns `True`. Auto-detect then selects `KeyringBackend`, and the first `keyring.set_password`/`get_password` either raises `NoKeyringError` at runtime or silently no-ops, depending on the chain. The bot would believe it has a real store and skip the encrypted-file fallback.

**Fix:** Probe functionally instead of (or in addition to) type-checking. A round-trip probe is the reliable signal:
```python
def _has_real_keyring() -> bool:
    backend = keyring.get_keyring()
    if isinstance(backend, _keyring_fail.Keyring):
        return False
    try:
        from keyring.backends.null import Keyring as _NullKeyring
        if isinstance(backend, _NullKeyring):
            return False
    except ImportError:
        pass
    try:
        keyring.set_password("shopbot", "__probe__", "1")
        ok = keyring.get_password("shopbot", "__probe__") == "1"
        keyring.delete_password("shopbot", "__probe__")
        return ok
    except Exception:
        return False
```

### WR-02: Service background loop silently swallows every exception from `async_main`

**File:** `core/service.py:95-96`

**Issue:** `except (asyncio.CancelledError, Exception): pass` discards all errors, including real failures (config errors, driver crashes, programming bugs). `_running` is then set to `False` and the thread exits cleanly, so the caller has no signal that the bot died abnormally vs. shut down normally. This violates the project rule "never silently swallow exceptions" and makes field debugging effectively impossible (no log line is emitted). It also widens CR-01's blast radius: an exception that carried a secret is swallowed without even a type-only log.

**Fix:** Separate cancellation (expected) from real errors, and log the type on the error path:
```python
try:
    await async_main(self._cfg, cvv)
except asyncio.CancelledError:
    pass
except Exception as exc:
    writeLog(f"Bot loop terminated abnormally: {exc.__class__.__name__}", "ERROR")
finally:
    self._running = False
    self._task = None
```

### WR-03: `start()` race -- `_running` is set inside the coroutine, after `start()` may have already returned

**File:** `core/service.py:79-110`

**Issue:** `start()` checks `if self._running` at line 79, then launches the thread and waits on `ready` with a 5s timeout (line 110). `_running` is only set to `True` inside the coroutine (line 91). Two problems: (1) `ready.wait(timeout=5.0)` returns whether or not the event fired; if the loop is slow to start, `start()` returns with `_running` still `False` and `_task` still `None`, so a subsequent `stop()` is a silent no-op (line 118) while the thread is in fact starting up. (2) A second `start()` call racing the first sees `_running == False` and can launch a second thread/loop. The handshake is not robust.

**Fix:** Set `self._running = True` synchronously in `start()` before launching the thread (it is the lifecycle owner), or check `ready.wait()`'s return value and raise/log on timeout rather than returning as if started. At minimum, gate the duplicate-launch path on the thread handle, not on `_running`.

### WR-04: `isolated_keyring` fixture teardown does not restore the original OS keyring

**File:** `tests/conftest.py:294-297`

**Issue:** The fixture installs a `_DictKeyring`, yields, then on teardown sets `_keyring_core._keyring_backend = None`. Setting the cached backend to `None` forces keyring to re-run backend auto-detection on next access; it does not restore whatever backend was active before the test. Any test that ran earlier and captured the original via `keyring.get_keyring()` (e.g. `test_has_real_keyring_fail` saves/restores correctly, but other tests relying on a stable backend) can observe a different backend post-teardown. This is order-dependent test pollution.

**Fix:** Capture and restore the original explicitly:
```python
original = _keyring_module.get_keyring()
kb = _DictKeyring()
_keyring_module.set_keyring(kb)
yield kb
_keyring_module.set_keyring(original)
```

### WR-05: `EncryptedFileBackend.set`/`delete` are read-modify-write with no locking; concurrent writers lose data

**File:** `core/credentials.py:262-270`

**Issue:** `set` and `delete` both call `_load()` (full decrypt), mutate the dict, then `_save()` (full re-encrypt with a fresh salt + `os.replace`). The store singleton is shared process-wide and `BotService` runs a background asyncio thread plus the main thread. If `migrate_from_env` (main thread, multiple sequential `set` calls) overlaps any other writer, the last `os.replace` wins and intervening keys are dropped. The module already uses `_store_lock` for the singleton but the backend instance has no write lock.

**Fix:** Guard the load-modify-save in `set`/`delete` with a per-instance `threading.Lock`, or document that the file backend is single-writer and ensure migration runs before the background thread starts. Given `migrate_from_env` is invoked via the `--migrate` CLI path (which exits before `service.run()`), the practical risk is low today, but the contract is unguarded.

### WR-06: `migrate_from_env` writes through whatever backend `get_store()` returns -- can no-op silently against a non-functional keyring

**File:** `core/service.py:162-167`, `core/credentials.py:369-382`

**Issue:** `main(--migrate)` calls `migrate_from_env(get_store())`. If auto-detect selected `KeyringBackend` due to WR-01 (chainer over fail/null), each `store.set(key, val)` may raise or no-op, yet `migrated.append(key)` still runs and the CLI prints `Migrated: <KEY>` for every env var. The operator is told migration succeeded when nothing was persisted, then deletes their env vars believing the secret is safe in the store.

**Fix:** Verify the write inside `migrate_from_env` (read-back) before appending to the migrated list, or have it raise on a failed `set`. Tie this fix to WR-01 so the selected backend is known-functional.

### WR-07: `notifications/__init__.build_dispatcher` reads `DISCORD_WEBHOOK_URL` twice (TOCTOU window)

**File:** `notifications/__init__.py:43` and `notifications/discord_notifier.py:66-68`

**Issue:** The factory gates on `get_store().get("DISCORD_WEBHOOK_URL")` (line 43), then `DiscordNotifier.__init__` independently re-reads the same key and raises `ValueError` if absent (line 68). Between the two reads the store value could change (env backend: another thread `delenv`s it), so the factory decides to include the notifier and the constructor then raises, taking down `build_dispatcher` entirely instead of skipping the channel. Two reads of one secret also doubles the surface for a future logging mistake.

**Fix:** Read once and pass the value in: `url = get_store().get("DISCORD_WEBHOOK_URL"); if notif.discord.enabled and url: notifiers.append(DiscordNotifier(url))`. Have `DiscordNotifier.__init__(self, webhook_url: str)` accept the value rather than re-reading the store.

## Info

### IN-01: `core/credentials.py` exceeds the 300-line project file limit

**File:** `core/credentials.py:1-397`

**Issue:** The file is 397 lines; CLAUDE.md sets a 300-line ceiling. The ABC, three backends, KDF helper, selection logic, singleton accessors, and migration all live in one module.

**Fix:** Optional split: move the three backend classes into `core/credential_backends.py` and keep `credentials.py` as the selection/singleton/migration surface. Not load-bearing for correctness; flagged for convention compliance.

### IN-02: Confusing dead code in `test_auto_select_file` -- set/delenv/set the same env var

**File:** `tests/test_credentials.py:253-255`

**Issue:**
```python
monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "testpassphrase")
monkeypatch.delenv("SHOPBOT_STORE_PASSPHRASE", raising=False)
monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "testpassphrase")
```
The first two lines are dead: the value is set, immediately deleted, then set again. Net effect equals a single `setenv`. Reads as a botched edit and obscures intent.

**Fix:** Delete the first two lines; keep one `monkeypatch.setenv(...)`.

### IN-03: `BestBuy.auto_buy` calls `login()` after navigating to checkout, and the `.a-dropdown-prompt` selector is a known-suspect carry-over

**File:** `plugins/shopbot_plugin_bestbuy.py:154` and `shopbot_plugin_bestbuy.py:127-130`

**Issue:** `login()` runs only after add-to-cart and the cart-page navigation, which is an odd ordering (most flows authenticate before cart manipulation). Separately, the `.a-dropdown-prompt` selector carries an Amazon-style `a-` prefix on a BestBuy page and is flagged by the inline TODO as unverified. Both are pre-existing carry-overs, not introduced by Phase 8, but they sit in code touched by this phase's migration.

**Fix:** Out of scope for the credential phase; track separately. Verify selector against live BestBuy and confirm login ordering during the next functional UAT.

### IN-04: `EmailNotifier` / `SmsNotifier` send empty-string credentials when the store returns `None`

**File:** `notifications/email_notifier.py:69`, `notifications/sms_notifier.py:59-61`

**Issue:** `get_store().get("SMTP_PASSWORD") or ""` (and the three Twilio reads) substitute `""` for a missing secret, so the channel attempts an SMTP `login("", "")` / Twilio auth with blank token. The failure is deferred to the remote server and surfaces as an auth exception rather than a clear "credential not configured" message. For SMS this is partially mitigated by `SmsConfig.require_creds_if_enabled`, but Email has no equivalent startup gate.

**Fix:** Optional: short-circuit with a clear `writeLog(..., "ERROR")` and return when the password/token is falsy, mirroring the plugins' "skipping login" guard.

### IN-05: `import keyring.core` is unused in `core/credentials.py`

**File:** `core/credentials.py:28`

**Issue:** `keyring.core` is imported but never referenced (the code uses `keyring.get_keyring`, `keyring.backends.fail`, and the lazily imported `keyring.backends.null`). `tests/conftest.py` does use `keyring.core` for its reset, but the production module does not.

**Fix:** Remove the unused `import keyring.core` line from `core/credentials.py`.

---

_Reviewed: 2026-06-04T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
