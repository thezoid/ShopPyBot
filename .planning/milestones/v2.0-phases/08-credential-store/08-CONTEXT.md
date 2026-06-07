# Phase 8: Credential Store - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

A `CredentialStore` abstraction with three runtime-selectable backends (OS keyring, encrypted file, env-var) that centralizes ALL secret access; no plaintext secrets on disk; every plugin and notifier reads credentials through the store. Covers CRED-01..CRED-07. New deps allowed: `keyring`, `cryptography`.

NOT in scope: the CLI front-end shell (Phase 9 — but `shoppybot setup --migrate` for CRED-07 is implemented here as the migration entry; Phase 9 wraps the broader setup UX), web UI (Phase 10), cross-platform CI (Phase 11).
</domain>

<decisions>
## Implementation Decisions

### CredentialStore Interface & Key Scheme (CRED-01)
- `CredentialStore` interface: `get(key) -> str|None`, `set(key, value)`, `delete(key)`, `list() -> list[str]`. Lives in `core/`.
- Keys reuse the EXISTING env-var names verbatim (DISCORD_WEBHOOK_URL, SMTP_PASSWORD, TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM, AMZ_EMAIL/AMZ_PASSWORD, BB_EMAIL/BB_PASSWORD, and the per-platform WALMART_*/TARGET_*/GAMESTOP_*/SQUAREENIX_*/NEWEGG_* + GENERIC creds). A canonical SECRET_KEYS list defines the known set (used by migration + the no-plaintext test). `store.get(KEY)` replaces `os.environ.get(KEY)` 1:1.
- Access: a module accessor `core/credentials.py` `get_store()` returns the process-wide store (initialized once at startup); plugins/notifiers call `get_store().get(KEY)` (a one-line swap from os.environ.get). BotService initializes the store.

### Backends & Selection (CRED-02..05)
- Keyring backend (CRED-02): `keyring` lib -> Windows Credential Manager / Linux Secret Service when a real backend is available (guard against keyring's fail/null backend).
- Encrypted-file backend (CRED-03): `cryptography` Fernet (AES128-CBC + HMAC) with a key derived from a passphrase via scrypt; secrets stored in a binary file under the data dir. Passphrase from `SHOPBOT_STORE_PASSPHRASE` env (unattended) else `getpass` prompt; required only when the file backend is active.
- Env-var backend (CRED-04): reads os.environ (today's behavior) when nothing else is configured.
- Selection precedence (CRED-05): explicit config override (a `credentials.backend: auto|keyring|file|env` setting) > keyring (if an OS backend is present) > encrypted-file (if a passphrase is available) > env-var. Auto-detect at startup; LOG the active backend NAME only (e.g. "CredentialStore: keyring backend active"), never secret values.

### No Plaintext On Disk (CRED-06)
- Secrets are NEVER written to config.yml, logs, or SQLite. The encrypted-file store is the only at-rest form and it is encrypted (the file is binary, not plaintext-readable). A test asserts none of the SECRET_KEYS values appear as plaintext in config.yml, log files, or the SQLite DB.

### Migration (CRED-07)
- `shoppybot setup --migrate` reads each known SECRET_KEYS env var that is currently set and writes it into the active backend, then confirms each imported key BY NAME (never the value). Implemented as a migration function callable from the entry point (Phase 9 gives it a fuller setup UX).

### Claude's Discretion
- Exact module layout (core/credentials.py with backend classes vs a small package), the data-dir resolver (per-OS), the scrypt parameters, the Fernet file format, and how get_store() lazy-initializes, provided the locked decisions hold and the 227-test suite stays green (env-var backend keeps current behavior so existing tests using monkeypatch.setenv still pass).
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Current secret reads to migrate (replace os.environ.get -> get_store().get):
  - notifications/discord_notifier.py (DISCORD_WEBHOOK_URL), email_notifier.py (SMTP_PASSWORD), sms_notifier.py (TWILIO_*)
  - plugins/shopbot_plugin_*.py (AMZ_/BB_/WALMART_/TARGET_/GAMESTOP_/SQUAREENIX_/NEWEGG_ EMAIL+PASSWORD)
  - core/config_schema.py SMS validator (checks TWILIO_* presence) -> route through the store's known-keys check
- core/service.py BotService (Phase 7): initializes the store at startup; passes nothing secret into the loop beyond what front-ends collect.
- The CVV stays getpass-collected in the front-end (not a stored secret) — out of the credential store.

### Established Patterns
- Secrets env-only, never logged (Phase 1) — the store generalizes this: still never logged, now also never plaintext on disk.
- Existing tests set secrets via monkeypatch.setenv — keep the env-var backend behavior so those tests pass unmodified (the store's env backend reads os.environ).

### Integration Points
- get_store() initialized once (BotService / entry point); plugins + notifiers consume it.
- config_schema gains a small `credentials` section (backend selector + data-dir override); secrets themselves never live in config.
</code_context>

<specifics>
## Specific Ideas

- SC1 grep must pass: no os.environ secret reads remain in plugins/notifications/core (the env-var BACKEND inside core/credentials.py is the single allowed os.environ read site for secrets).
- SC3/SC6 no-plaintext test is the key security guardrail.
- SC4: log the backend name on startup, never a secret.
- Keep the 227-test suite green: the env-var backend must make existing monkeypatch.setenv-based tests pass as-is.
</specifics>

<deferred>
## Deferred Ideas

- Full `shoppybot setup` interactive UX (Phase 9) — Phase 8 ships the --migrate function + store.
- Web UI credential management (Phase 10).
- Cross-platform CI matrix (Phase 11).
- Rotating/expiring secrets, multiple profiles — future.
</deferred>

---

*Phase: 8-credential-store*
*Context gathered: 2026-06-04*
