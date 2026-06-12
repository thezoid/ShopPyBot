---
phase: 23-encrypted-session-persistence
fixed_at: 2026-06-12T00:00:00Z
review_path: .planning/phases/23-encrypted-session-persistence/23-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 23: Code Review Fix Report

**Fixed at:** 2026-06-12T00:00:00Z
**Source review:** .planning/phases/23-encrypted-session-persistence/23-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8
- Fixed: 8
- Skipped: 0

## Fixed Issues

### CR-01: Remove private `_passphrase` access in restore_session

**Files modified:** `core/plugin_base.py`
**Commit:** f3a0e55
**Applied fix:** Deleted the `if store._passphrase is None: return False` guard. Rely
on `store.restore(key)` returning `None` (its public contract for no-passphrase) and
the existing `if not cookies: return False` guard. The `_passphrase` private attribute
is no longer accessed from outside `SessionStore`. The existing test
`test_restore_session_false_no_passphrase` validates the no-passphrase path via the
public interface.

### CR-02: Add `.tmp` suffix to mkstemp; widen CI guard

**Files modified:** `core/session_store.py`, `tests/test_no_committed_sessions.py`
**Commit:** d838419
**Applied fix:** Added `suffix=".tmp"` to `tempfile.mkstemp(...)` so orphaned files
from a crashed atomic write are visually distinct in `data/sessions/`. Widened the
`test_no_committed_session_files` guard from `line.endswith(".bin")` to
`line.strip()` (any non-empty line from `git ls-files data/sessions/`), so `.tmp`
orphans are also caught by CI.

### WR-01: Treat `expires=0` as session cookie

**Files modified:** `core/plugin_base.py`, `tests/test_session_persistence.py`
**Commit:** 437c69f
**Applied fix:** Changed the expiry filter in `_dicts_to_cookie_params` from
`exp is not None and float(exp) < now` to
`exp is not None and float(exp) != 0.0 and float(exp) < now`.
Also changed `expires_param` to map `exp=0` to `None` (same as `exp=None`) rather
than `TimeSinceEpoch(0)`. Added two regression tests:
`test_cookie_param_expires_zero_kept_as_session_cookie` (expires=0 passes through
with expires param = None) and `test_cookie_param_past_positive_expiry_is_filtered`
(positive past timestamp is still dropped).

### WR-02 + WR-03: Scope save_session to plugin domain; skip empty saves

**Files modified:** `core/plugin_base.py`, `tests/test_session_persistence.py`
**Commit:** 924c8b4
**Applied fix (WR-02):** Added domain filter to the `save_session` list comprehension.
Reads `self.domain_patterns` via `getattr` and keeps only cookies whose `domain`
field contains any of the patterns (substring match). If `domain_patterns` is empty
all cookies are kept (safe fallback for plugins without domain scoping).

**Applied fix (WR-03):** Added early-return guard after the domain filter: if `dicts`
is empty, log a DEBUG message and return without writing a session file. Prevents
persisting an empty/unauthenticated session after a failed login. Added a comment
that full post-login DOM success verification is out of scope and tracked as UAT debt.

Updated `test_save_session_writes_encrypted_file` to use `domain=".test.example.com"`
(matches `_TestPlugin.domain_patterns = ["test.example.com"]`). Added
`test_save_session_domain_filter_keeps_matching_cookies` and
`test_save_session_noop_when_no_domain_matching_cookies`.

### WR-04: Document async cookie-expiry race in restore_session

**Files modified:** `core/plugin_base.py`
**Commit:** 6d426d0
**Applied fix:** Added a comment above `tab.send(cdp_storage.set_cookies(params))`
documenting the narrow async window where Chrome may silently discard cookies it
considers expired at injection time, causing a false-True return from restore_session.
Notes that relaunch() handles the downstream consequence via re-login, and that live
UAT must confirm end-to-end session acceptance (tracked as UAT debt).

### IN-01: Remove redundant `InvalidToken` from except tuple

**Files modified:** `core/session_store.py`
**Commit:** e433f4c
**Applied fix:** Replaced `except (InvalidToken, Exception)` with `except Exception`
plus an inline comment `# Includes Fernet.InvalidToken (wrong passphrase or truncated data)`.
`InvalidToken` is a subclass of `Exception`; the tuple implied special handling that
did not exist.

### IN-02: Anchor gitignore path to repo root

**Files modified:** `tests/test_no_committed_sessions.py`
**Commit:** e433f4c
**Applied fix:** Added `_REPO_ROOT = Path(__file__).resolve().parent.parent` as a
module-level constant. Updated `gitignore_path` to use `_REPO_ROOT / ".gitignore"`
and the `git ls-files` subprocess call to use `["git", "-C", str(_REPO_ROOT), ...]`
so both checks are repo-root-relative regardless of pytest invocation directory.

---

_Fixed: 2026-06-12T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
