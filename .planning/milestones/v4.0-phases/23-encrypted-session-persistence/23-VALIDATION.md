---
phase: 23
slug: encrypted-session-persistence
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-12
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (asyncio_mode=auto) |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `pytest tests/test_session_store.py tests/test_session_persistence.py tests/test_no_committed_sessions.py` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~30-60 seconds |

---

## Sampling Rate

- **After every task commit:** Run touched test files
- **After every plan wave:** Run `pytest`
- **Before verify:** Full suite green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task | Requirement | Secure Behavior | Test Type | Command | Status |
|------|-------------|-----------------|-----------|---------|--------|
| session-store | REL-04 | SessionStore.save/restore round-trips a cookie list; on-disk file is Fernet-encrypted (NOT plaintext JSON); no passphrase → disabled (None) | unit | `pytest tests/test_session_store.py` | ⬜ pending |
| no-plaintext | REL-04 | written data/sessions/*.bin is not parseable as JSON (encrypted); never a plaintext .json/.pickle | unit | `pytest tests/test_session_store.py` | ⬜ pending |
| restore-safe | REL-04 | restore returns None/False on missing file, InvalidToken (wrong passphrase), corrupt file — no crash | unit | `pytest tests/test_session_store.py` | ⬜ pending |
| cookieparam | REL-04 | Cookie↔CookieParam serialization round-trips name/value/domain/path/expires/http_only/secure/same_site; sameSite enum + TimeSinceEpoch handled | unit | `pytest tests/test_session_persistence.py` | ⬜ pending |
| restore-skips-login | REL-04 | restore_session True (session exists) → relaunch/startup skips login(); False → login proceeds; uses raw CDP set_cookies not CookieJar.set_all | unit | `pytest tests/test_session_persistence.py` | ⬜ pending |
| save-after-login | REL-04 | save_session called after successful login when session_persistence enabled | unit | `pytest tests/test_session_persistence.py` | ⬜ pending |
| config | REL-04 | session_persistence: bool defaults False on all 7 platform models (opt-in) | unit | `pytest tests/test_config_schema.py` | ⬜ pending |
| ci-no-commit | REL-04 | no session-file pattern is git-tracked; data/sessions/ gitignored | unit | `pytest tests/test_no_committed_sessions.py` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_session_store.py` — new: round-trip, no-plaintext, restore-safe (model on tests/test_credentials.py EncryptedFileBackend tests)
- [ ] `tests/test_session_persistence.py` — new: CookieParam serialization + restore-skips-login + save-after-login (fake tab.send)
- [ ] `tests/test_no_committed_sessions.py` — new: git-tracked + gitignore check
- [ ] Existing fake-tab/fake-plugin fixtures (conftest.py)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live cross-restart MFA/login skip on a real retailer | REL-04 | Requires a real logged-in session + restart + live retailer to confirm cookies restore a valid session and skip MFA | Deferred as UAT debt: log in once with session_persistence enabled, restart the bot, confirm it does NOT re-prompt login/MFA and the restored session is accepted by the retailer |

*All in-process behaviors have automated verification (encryption, serialization, restore-safety, config, CI guard).*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
