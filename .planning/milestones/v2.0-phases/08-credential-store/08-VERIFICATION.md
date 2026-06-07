---
phase: 08-credential-store
verified: 2026-06-04T00:00:00Z
status: human_needed
score: 4/5
overrides_applied: 0
human_verification:
  - test: "On a machine with a live OS keyring (Windows Credential Manager or Linux Secret Service): call CredentialStore.set('AMZ_EMAIL', 'test@example.com'), restart the Python process with no env var set, call CredentialStore.get('AMZ_EMAIL') — confirm it returns 'test@example.com'."
    expected: "KeyringBackend round-trips a secret across a process restart without any env var."
    why_human: "Requires a live OS keyring daemon. The test suite exercises this with an in-memory DictKeyring; real persistence is not testable without an OS keyring present."
  - test: "On a headless Ubuntu box with no keyring daemon and SHOPBOT_STORE_PASSPHRASE set: start the bot, confirm the startup log line reads 'CredentialStore: encrypted-file backend active' (not 'keyring' or 'env-var')."
    expected: "Encrypted-file backend activates automatically in a headless no-keyring environment."
    why_human: "Requires a headless Ubuntu environment with no Secret Service daemon — cannot be verified on Windows dev machine."
  - test: "Run 'shoppybot setup --migrate' (Phase 9 UX wrapper, not yet implemented). Currently the flag is 'shoppybot --migrate'. Confirm the migrate path works end-to-end with the Phase 9 setup subcommand once Phase 9 ships."
    expected: "The full SC5 CLI form 'shoppybot setup --migrate' works after Phase 9 is complete."
    why_human: "SC5 literal wording ('shoppybot setup --migrate') requires the Phase 9 setup subcommand. Phase 8 ships 'shoppybot --migrate' as the interim form; Phase 9 is explicitly scoped to add the full setup UX. This is a deferred-by-design split, not a gap."
deferred:
  - truth: "Running 'shoppybot setup --migrate' imports env secrets into the active backend and confirms each key by name (not value)"
    addressed_in: "Phase 9"
    evidence: "Phase 9 goal: 'shoppybot setup interactively stores/updates credentials (into CredentialStore)'. Phase 8 CONTEXT.md explicitly: 'Full shoppybot setup interactive UX (Phase 9) -- Phase 8 ships the --migrate function + store.' Phase 8 ships 'shoppybot --migrate' as the functional migration path."
---

# Phase 8: Credential Store — Verification Report

**Phase Goal:** A `CredentialStore` abstraction with three runtime-selectable backends (OS keyring, encrypted file, env-var) centralizes all secret access; no plaintext secrets exist anywhere on disk; every plugin and notifier reads credentials through the store.
**Verified:** 2026-06-04
**Status:** human_needed — all automated checks pass; 2 items require live-OS confirmation (CRED-02 persistence, CRED-03 headless auto-selection)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A grep for os.environ secret-key reads in plugins/, notifications/, core/ returns zero matches except EnvVarBackend.get and the documented SmsConfig validator | VERIFIED | `test_no_os_environ_secret_reads` passes; manual scan of all consumer files confirms zero violations |
| 2 | Keyring backend round-trips a secret via in-memory DictKeyring (unit); live OS persistence requires human test | VERIFIED (automated portion) | `test_keyring_backend`, `test_keyring_list`, `test_has_real_keyring_fail` all pass; live-OS persistence routed to human verification |
| 3 | Encrypted-file backend auto-activates headless; file is binary; no secret value appears as plaintext in config.yml, any log file, or the SQLite DB | VERIFIED | `test_encrypted_file_is_not_plaintext`, `test_no_plaintext_secrets_in_config_yml`, `test_no_plaintext_secrets_in_log_files`, `test_no_plaintext_secrets_in_sqlite` all pass |
| 4 | Env-var fallback activates when no store configured; startup logs active backend NAME only, never a secret value | VERIFIED | `test_auto_select_env`, `test_startup_log_backend_name` pass; `_log_backend()` emits only the label string |
| 5 | `shoppybot setup --migrate` imports env secrets into the active backend and confirms each key by name (not value) | DEFERRED | Phase 8 ships `shoppybot --migrate` (functional); `setup` subcommand is Phase 9 scope. `test_migrate_from_env`, `test_migrate_confirms_by_name`, `test_main_migrate_flag` all pass for the Phase 8 form |

**Score:** 4/5 truths automated-verified (SC5 deferred to Phase 9 by design; see deferred section)

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|--------------|---------|
| 1 | `shoppybot setup --migrate` CLI form | Phase 9 | Phase 9 SC2: "shoppybot setup interactively stores/updates credentials"; Phase 8 CONTEXT.md: "Full shoppybot setup interactive UX (Phase 9)". Phase 8 ships `--migrate` as the functional migration primitive; Phase 9 wraps it under the `setup` subcommand. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/credentials.py` | CredentialStore ABC, EnvVarBackend, KeyringBackend, EncryptedFileBackend, SECRET_KEYS (19 keys), get_store, init_store, migrate_from_env | VERIFIED | All symbols present; 397 lines; substantive implementation confirmed |
| `core/config_schema.py` | CredentialsConfig sub-model wired into AppConfig; SmsConfig deliberate-exception documented | VERIFIED | `class CredentialsConfig` at line 203; `credentials: CredentialsConfig = CredentialsConfig()` at line 231; DELIBERATE comment at line 176 |
| `core/service.py` | `init_store(self._cfg)` in BotService.__init__; `--migrate` flag in main() | VERIFIED | `init_store(self._cfg)` at line 40; `--migrate` argparse at line 155; `migrate_from_env` call at line 164 |
| `tests/test_credentials.py` | 24 tests covering CRED-01..CRED-07 | VERIFIED | 24 collected; 23 passed, 1 xpassed |
| `tests/test_no_plaintext.py` | CRED-06 no-plaintext-on-disk guard | VERIFIED | 4 tests; all pass |
| `tests/test_no_env_secret_reads.py` | SC1 grep guard | VERIFIED | 1 test; passes |
| `tests/conftest.py` | `reset_credential_store` + `isolated_keyring` fixtures | VERIFIED | Both fixtures present; `_DictKeyring` in-memory backend confirmed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `core/config_schema.py AppConfig` | `CredentialsConfig` | `credentials: CredentialsConfig = CredentialsConfig()` | VERIFIED | Line 231 of config_schema.py |
| `core/credentials.py get_store` | `EnvVarBackend` | lazy fallback when `_store is None` | VERIFIED | Lines 284-294; `return EnvVarBackend()` under lock |
| `EncryptedFileBackend._save` | `creds.bin` | `tempfile.mkstemp + os.replace` atomic write | VERIFIED | Lines 247-257; `os.replace(tmp, self._path)` outside the `with` block |
| `EncryptedFileBackend._derive_key` | Scrypt KDF | `n=2**14 r=8 p=1 salt=16B` | VERIFIED | Lines 197-200; `Scrypt(salt=salt, length=32, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)` |
| `core/service.py BotService.__init__` | `core/credentials.init_store` | `init_store(self._cfg)` before thread launch | VERIFIED | Line 40; called before `_thread` is created |
| `core/credentials._build_store` | `writeLog backend name` | `_log_backend(label)` emitting `{label} backend active` | VERIFIED | `_log_backend` at line 364; called in all `_build_store` branches |
| Plugins + notifications consumers | `core.credentials.get_store` | `get_store().get(KEY)` replacing `os.environ.get(KEY)` | VERIFIED | All 7 plugins confirmed; 3 notification files + notifications/__init__.py confirmed |
| `core/service.py main()` | `core.credentials.migrate_from_env` | `--migrate` flag invocation | VERIFIED | Lines 162-167; `migrate_from_env(get_store())` then key-name-only print |

### Data-Flow Trace (Level 4)

Not applicable — Phase 8 produces a backend abstraction library, not a component that renders dynamic data. The key data flow is credentials -> CredentialStore -> consumer, which is exercised by the unit tests.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CredentialStore.get/set/delete round-trip (EnvVarBackend) | `python -m pytest tests/test_credentials.py -k env_backend -q` | 5 passed | PASS |
| KeyringBackend round-trip (in-memory DictKeyring) | `python -m pytest tests/test_credentials.py -k keyring -q` | 3 passed | PASS |
| EncryptedFileBackend round-trip + binary file | `python -m pytest tests/test_credentials.py -k "file or plaintext" -q` | 4 passed | PASS |
| Backend auto-selection precedence | `python -m pytest tests/test_credentials.py -k "select or override" -q` | 4 passed | PASS |
| No-plaintext on-disk scans | `python -m pytest tests/test_no_plaintext.py -q` | 4 passed | PASS |
| SC1 grep guard | `python -m pytest tests/test_no_env_secret_reads.py -q` | 1 passed | PASS |
| migrate_from_env + --migrate flag | `python -m pytest tests/test_credentials.py -k migrate -q` | 3 passed | PASS |
| Full test suite (255 tests) | `python -m pytest -q` | 255 passed, 1 xpassed | PASS |

### Probe Execution

No probe scripts found or declared for this phase. Step 7c: SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CRED-01 | 08-01, 08-04 | CredentialStore interface; all secret reads route through it | SATISFIED | `test_no_os_environ_secret_reads` passes; 16 migration sites confirmed |
| CRED-02 | 08-02 | Keyring backend via `keyring` lib | SATISFIED (automated); human needed for live persistence | `test_keyring_backend` passes with DictKeyring; live OS persistence is human-only |
| CRED-03 | 08-02 | Encrypted-file fallback; Fernet+scrypt; binary file | SATISFIED | `test_file_backend`, `test_encrypted_file_is_not_plaintext` pass |
| CRED-04 | 08-01 | Env-var fallback preserves existing behavior | SATISFIED | `test_env_backend_*` pass; 255-test suite green via env-var backend |
| CRED-05 | 08-03 | Auto-selection precedence + backend-name logging | SATISFIED | `test_auto_select_keyring/file/env`, `test_startup_log_backend_name` pass |
| CRED-06 | 08-03 | No plaintext secrets on disk | SATISFIED | `test_no_plaintext_secrets_in_config_yml/log_files/sqlite` + `test_encrypted_file_is_not_plaintext` pass |
| CRED-07 | 08-04 | Migration command confirms keys by name | SATISFIED (Phase 8 form: `--migrate`; `setup --migrate` deferred to Phase 9) | `test_migrate_from_env`, `test_migrate_confirms_by_name`, `test_main_migrate_flag` pass |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `plugins/shopbot_plugin_walmart.py` | 77, 108, 143, 153, 165 | `# TODO: verify selectors` | Info | Pre-existing from Phase 6 (commit d2043b6); not introduced by Phase 8; Phase 8 only touched credential migration lines in this file |
| `plugins/shopbot_plugin_target.py` | 79, 110, 145, 155, 167 | `# TODO: verify selectors` | Info | Same — pre-existing Phase 6 comments |
| `plugins/shopbot_plugin_gamestop.py` | 79, 110, 145, 155, 167 | `# TODO: verify selectors` | Info | Same — pre-existing Phase 6 comments |
| `plugins/shopbot_plugin_squareenix.py` | 78, 112, 147, 157, 171 | `# TODO: verify selectors` | Info | Same — pre-existing Phase 6 comments |
| `plugins/shopbot_plugin_newegg.py` | 76, 115, 156, 166, 180 | `# TODO: verify selectors` | Info | Same — pre-existing Phase 6 comments |
| `plugins/shopbot_plugin_bestbuy.py` | 127 | `# TODO: verify selector` | Info | Same — pre-existing Phase 6 comment |

Note on `cryptography` dependency: `EncryptedFileBackend` imports `cryptography` (Fernet, Scrypt) directly but `cryptography` is not pinned in `requirements.txt`. `keyring==25.7.0` is pinned (the other net-new dep). `cryptography==44.0.2` is installed as a standalone package but not declared. This is a WARNING against INFRA-01 (exact pins). However `cryptography` was not in `requirements.txt` before Phase 8 and was transitively available; the omission from the pin list means `pip install -r requirements.txt` may install a different version on a fresh machine. Phase 8 introduced the direct dependency without pinning it.

| File | Issue | Severity |
|------|-------|----------|
| `requirements.txt` | `cryptography` used directly by `EncryptedFileBackend` but not pinned | Warning — not a Phase 8 goal blocker, but violates INFRA-01 |

### Human Verification Required

#### 1. OS Keyring Live Persistence (CRED-02)

**Test:** On a machine with Windows Credential Manager or Linux Secret Service active: (1) run `python -c "from core.credentials import KeyringBackend; KeyringBackend().set('AMZ_EMAIL', 'test@example.com')"`, (2) open a new process with no `AMZ_EMAIL` env var, (3) run `python -c "from core.credentials import KeyringBackend; print(KeyringBackend().get('AMZ_EMAIL'))"`.
**Expected:** Prints `test@example.com` — the secret survives a process restart without any env var.
**Why human:** Requires a live OS keyring daemon. The automated test suite exercises the same code path with an in-memory `_DictKeyring`; OS persistence cannot be verified programmatically on this machine without a running Credential Manager.

#### 2. Headless Ubuntu Encrypted-File Auto-Selection (CRED-03)

**Test:** On a headless Ubuntu machine with no keyring daemon: (1) set `SHOPBOT_STORE_PASSPHRASE=testpass`, (2) start the bot (or run `python -c "from core.config_schema import AppConfig; from core.credentials import init_store; init_store(AppConfig())"`), (3) confirm the log line `CredentialStore: encrypted-file backend active` appears.
**Expected:** Auto-selection picks the encrypted-file backend, not keyring or env-var, in the headless no-keyring environment.
**Why human:** Requires a headless Ubuntu environment with no Secret Service daemon — cannot be confirmed on Windows.

#### 3. `shoppybot setup --migrate` (SC5 full form — Phase 9 deferred)

**Test:** After Phase 9 ships the `setup` subcommand: confirm `shoppybot setup --migrate` routes to `migrate_from_env` and prints key names only.
**Expected:** Full SC5 CLI form works end-to-end via the Phase 9 setup UX.
**Why human:** Phase 9 has not been executed yet. Phase 8's `shoppybot --migrate` covers the functional requirement; the `setup` prefix is a UX concern for Phase 9. This item requires re-verification after Phase 9 completes.

### Gaps Summary

No blockers found. All automated success criteria pass. Two items require human verification against live OS environments (CRED-02 persistence, CRED-03 headless auto-selection); one item (SC5 `setup --migrate` form) is deferred to Phase 9 by explicit design.

The only notable warning is that `cryptography` — introduced as a direct dependency for `EncryptedFileBackend` — is not pinned in `requirements.txt`. This violates INFRA-01 but does not block Phase 8's goal. Recommend adding `cryptography==44.0.2` to `requirements.txt` before Phase 9.

---

_Verified: 2026-06-04_
_Verifier: Claude (gsd-verifier)_
