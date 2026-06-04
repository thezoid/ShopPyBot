---
phase: 08-credential-store
fixed_at: 2026-06-04T00:00:00Z
review_path: .planning/phases/08-credential-store/08-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 8: Code Review Fix Report

**Fixed at:** 2026-06-04
**Source review:** .planning/phases/08-credential-store/08-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (1 Critical, 7 Warning; IN-03 out of scope per review)
- Fixed: 8
- Skipped: 0

Test suite result: 253 passed, 3 skipped, 0 failures (python -m pytest -q)

## Fixed Issues

### CR-01: Plugin exception handlers log exc type only

**Files modified:** `plugins/shopbot_plugin_amazon.py`, `plugins/shopbot_plugin_bestbuy.py`, `plugins/shopbot_plugin_gamestop.py`, `plugins/shopbot_plugin_newegg.py`, `plugins/shopbot_plugin_squareenix.py`, `plugins/shopbot_plugin_target.py`, `plugins/shopbot_plugin_walmart.py`
**Commit:** 6d5ed00
**Applied fix:** All 21 exception handlers across 7 plugins (check_availability, login, auto_buy per plugin) changed from `f"...: {exc}"` to `f"...: {exc.__class__.__name__}"`. No secret value can reach the log from a CDP/nodriver send_keys failure.

### WR-01: _has_real_keyring() functional probe for ChainerBackend

**Files modified:** `core/credentials.py`
**Commit:** 4e54c46
**Applied fix:** After the existing type checks for fail.Keyring and null.Keyring, the function now performs a `set_password / get_password / delete_password` round-trip probe. If the probe fails (exception or wrong read-back), returns False. Catches ChainerBackend composed only of fail/null leaves.

### WR-02: Service loop no longer swallows real exceptions

**Files modified:** `core/service.py`
**Commit:** c935378
**Applied fix:** Split `except (asyncio.CancelledError, Exception): pass` into separate `except asyncio.CancelledError: pass` and `except Exception as exc: writeLog(f"Bot loop terminated abnormally: {exc.__class__.__name__}", "ERROR")`. Added `from logger import writeLog` import. Real failures are now observable in the log.

### WR-03: start() sets _running synchronously, checks ready.wait return value

**Files modified:** `core/service.py`
**Commit:** c935378
**Applied fix:** `_running = True` is set before the thread is launched. Duplicate-launch guard checks both `_running` and `_thread.is_alive()`. The `ready.wait()` return value is checked and a WARNING is logged if the 5s timeout elapses without the event firing.

### WR-04: isolated_keyring fixture restores original backend on teardown

**Files modified:** `tests/conftest.py`
**Commit:** 999157a
**Applied fix:** Captures `original = _keyring_module.get_keyring()` before installing the test backend, then restores it via `_keyring_module.set_keyring(original)` on teardown instead of resetting the internal `_keyring_backend` to None.

### WR-05: EncryptedFileBackend set/delete guarded by per-instance lock

**Files modified:** `core/credentials.py`
**Commit:** 06cbfbc
**Applied fix:** Added `self._lock: threading.Lock = threading.Lock()` in `__init__`. Both `set` and `delete` now wrap their load-modify-save cycle in `with self._lock:`, preventing concurrent writers from losing keys.

### WR-06: migrate_from_env verifies write via read-back before recording success

**Files modified:** `core/credentials.py`
**Commit:** 4e54c46
**Applied fix:** After `store.set(key, val)`, calls `store.get(key)` and only appends the key name to `migrated` if the read-back returns a non-None value. Logs a WARNING at key-name level (no value) if the backend no-oped. Exceptions from `set` are also caught and logged by type.

### WR-07: DISCORD_WEBHOOK_URL read once in build_dispatcher, passed to constructor

**Files modified:** `notifications/__init__.py`, `notifications/discord_notifier.py`, `tests/test_notifications.py`
**Commit:** 9722847
**Applied fix:** `build_dispatcher` reads `discord_url = get_store().get("DISCORD_WEBHOOK_URL")` once and passes it as `DiscordNotifier(discord_url)`. `DiscordNotifier.__init__` now accepts `webhook_url: str` rather than re-reading the store, eliminating the TOCTOU window. Removed `from core.credentials import get_store` from discord_notifier.py. Updated the corresponding test to pass the URL directly.

### IN-02: Dead set/del/set triple in test_auto_select_file removed

**Files modified:** `tests/test_credentials.py`
**Commit:** 999157a
**Applied fix:** Removed the first two lines (setenv + delenv) that immediately preceded the final setenv, leaving a single `monkeypatch.setenv("SHOPBOT_STORE_PASSPHRASE", "testpassphrase")`.

### IN-05: Unused import keyring.core removed

**Files modified:** `core/credentials.py`
**Commit:** 4e54c46
**Applied fix:** Removed `import keyring.core` from credentials.py. The module uses `keyring.get_keyring`, `keyring.set_password`, etc. directly via the top-level `import keyring`; the `.core` sub-import was unused in production code.

---

_Fixed: 2026-06-04_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
