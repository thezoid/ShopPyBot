---
phase: 08
slug: credential-store
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-04
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (pytest-asyncio 1.3.0, asyncio_mode=auto) |
| **Config file** | pytest.ini / pyproject.toml (existing) |
| **Quick run command** | `pytest tests/test_credentials.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_credentials.py -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green (227 baseline + new)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | CRED-01 | — | CredentialStore interface (get/set/delete/list) defined in core/ | unit | `pytest tests/test_credentials.py -q` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | CRED-04 | — | Env-var backend reads os.environ; existing setenv tests stay green | unit | `pytest tests/test_credentials.py -q` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | CRED-02 | — | Keyring backend round-trips secret across restart; null-backend guarded | unit | `pytest tests/test_credentials.py -k keyring -q` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 2 | CRED-03 | — | Fernet/scrypt encrypted-file backend round-trips; file is binary | unit | `pytest tests/test_credentials.py -k file -q` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 3 | CRED-05 | — | Selection precedence config>keyring>file>env; logs backend name only | unit | `pytest tests/test_credentials.py -k select -q` | ❌ W0 | ⬜ pending |
| 08-03-02 | 03 | 3 | CRED-06 | — | No secret value appears plaintext in config.yml/logs/SQLite | unit | `pytest tests/test_no_plaintext.py -q` | ❌ W0 | ⬜ pending |
| 08-04-01 | 04 | 4 | CRED-01 | — | All os.environ secret reads in plugins/notifications/core swapped to store | grep | `pytest tests/test_no_env_secret_reads.py -q` | ❌ W0 | ⬜ pending |
| 08-04-02 | 04 | 4 | CRED-07 | — | setup --migrate imports env secrets, confirms each key by name | unit | `pytest tests/test_credentials.py -k migrate -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs indicative — planner finalizes exact plan/task numbering.*

---

## Wave 0 Requirements

- [ ] `tests/test_credentials.py` — stubs for CRED-01..05, CRED-07
- [ ] `tests/test_no_plaintext.py` — CRED-06 plaintext-on-disk guard
- [ ] `tests/test_no_env_secret_reads.py` — SC1 grep guard for CRED-01
- [ ] `tests/conftest.py` — DictKeyring fixture + store reset between tests

*Existing pytest infrastructure covers framework; only new test files needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real OS keyring persistence across process restart | CRED-02 | Requires a live Windows Credential Manager / Linux Secret Service daemon, not present in CI | On a desktop OS: `store.set('AMZ_EMAIL','x')`, restart process, `store.get('AMZ_EMAIL')` returns `'x'` with no env var set |
| Headless Ubuntu auto-selects encrypted-file backend | CRED-03 | Requires a no-keyring-daemon environment | On headless box with `SHOPBOT_STORE_PASSPHRASE` set, start bot, confirm log `CredentialStore: file backend active` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
