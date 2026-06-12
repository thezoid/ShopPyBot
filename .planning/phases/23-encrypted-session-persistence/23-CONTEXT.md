# Phase 23: Encrypted Session Persistence - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can opt into encrypted cookie persistence so the bot skips re-login and MFA across restarts without storing any auth material in plaintext (REL-04). This phase replaces Phase 22's no-op `restore_session` stub with a live `SessionStore.restore()`.

Deliverables:
1. `core/session_store.py` — a `SessionStore` (Fernet-encrypted cookie save/restore, reusing the credential scrypt KDF).
2. `save_session()` after a successful login (when enabled) + `restore_session()` that decrypts and restores cookies via raw CDP, replacing the P22 stub.
3. `session_persistence: bool = False` per-platform config (opt-in).
4. CI check that no session file is committed; `data/sessions/` gitignored.

Out of scope: the health surface (Phase 24); changes to the credential store itself.
</domain>

<decisions>
## Implementation Decisions

### SessionStore Design & Encryption
- `core/session_store.py` exposes a `SessionStore` with `save(platform, cookies)` and `restore(platform) -> list | None`. Encryption is Fernet, reusing the scrypt `_derive_key` helper + passphrase machinery from `core/credentials.py`.
- Passphrase source is the SAME `SHOPBOT_STORE_PASSPHRASE` mechanism as the credential store (scrypt → Fernet key). If no passphrase is configured, session persistence is silently disabled (cannot encrypt → no plaintext fallback).
- File format/location: `data/sessions/<platform>.bin`, `[SALT_LEN bytes salt][Fernet token of JSON cookie list]`, mirroring `EncryptedFileBackend`. The `data/sessions/` directory is created on demand and is already gitignored by the existing `data/*` rule.
- Stored content: the cookie list only (name, value, domain, path, expires, httpOnly, secure, sameSite) JSON-serialized then Fernet-encrypted. No other auth material; never plaintext.

### Save & Restore Wiring
- Cookies are saved after a successful `login()` (when `session_persistence` is enabled for that platform) via a `save_session()` hook.
- `restore_session()` replaces the Phase 22 no-op stub: if `session_persistence` is enabled AND a session file exists → decrypt → restore cookies via the raw CDP path → return True (so `relaunch()`/startup skips `login()`); otherwise return False (login proceeds).
- Live cookies are read for saving via the nodriver CDP `storage.get_cookies` / `network.get_all_cookies` path on the tab, then serialized (plan-phase research confirms the exact 0.50.3 API).
- A `session_persistence: bool = False` field is added to ALL platform config models (additive, opt-in, default off) so any plugin can opt in; the ABC `save_session`/`restore_session` are generic.

### CDP Path, Scope & Safety
- Cookie restore uses raw `cdp.storage.set_cookies()` with `CookieParam` objects, bypassing the confirmed nodriver `CookieJar.set_all()` bug (issues #1816/#2020). plan-phase research MUST confirm the exact import path and `CookieParam` constructor signature against installed nodriver 0.50.3 before implementing.
- `save_session`/`restore_session` are implemented generically on the `RetailerPlugin` ABC using `SessionStore`, so any plugin with the config flag benefits (Amazon + BestBuy are the primary users). Additive — no `PLUGIN_API_VERSION` bump.
- A CI test asserts no session-file pattern (`data/sessions/*.bin`) is git-tracked and that `data/sessions/` is gitignored (REL-04 criterion 3).
- `restore_session` returns False (no crash) on a missing file, decryption failure, or wrong passphrase → falls back to login. Session issues NEVER crash the bot.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/credentials.py` — `_derive_key(passphrase, salt)` (scrypt n=2**14/r=8/p=1, lines ~217), `EncryptedFileBackend` (Fernet AES-128-CBC+HMAC, file format `[salt][Fernet token of JSON]`, lines ~231-268), `SALT_LEN`, `SHOPBOT_STORE_PASSPHRASE` resolution. SessionStore reuses `_derive_key` + the same passphrase + the same file-format idiom.
- `core/plugin_base.py` — `restore_session()` no-op stub (line ~166, returns False) to REPLACE; `relaunch()` calls it (line ~159) and runs `login()` only if it returns False. Add `save_session()` (called after login). `get_active_tab()` (line ~94) returns the tab for CDP cookie ops. Additive (no API bump).
- `core/config_schema.py` — the 7 platform config models (AmazonPlatformConfig, BestBuyPlatformConfig, WalmartPlatformConfig, TargetPlatformConfig, GameStopPlatformConfig, SquareEnixPlatformConfig, NeweggPlatformConfig). Add `session_persistence: bool = False` to each (or a shared base).
- `.gitignore` — `data/*` already ignores `data/sessions/` (line 8). The CI test confirms no tracked session files.
- Plugins (Amazon/BestBuy) — `login()` is where save_session is called after success; `setup()`/`relaunch()` is where restore_session runs.

### Established Patterns
- Fernet + scrypt encrypted file with `[salt][token]` layout; passphrase via env (`SHOPBOT_STORE_PASSPHRASE`); InvalidToken handling.
- Additive ABC hooks with no-op/None defaults; opt-in config disabled by default (`enabled: bool = False` style).
- Platform branching / getattr-safe config reads; nodriver CDP usage already present (stealth, confirmation P19 used `tab.target.url`).

### Integration Points
- `core/session_store.py` (NEW — SessionStore).
- `core/plugin_base.py` (restore_session replaces stub; new save_session; both generic via SessionStore).
- `core/config_schema.py` (session_persistence per platform).
- `core/credentials.py` (reuse `_derive_key` + passphrase — import, do not modify).
- Plugins Amazon/BestBuy (call save_session after login; restore via the ABC path).
- A CI test for no-committed-session-files.

</code_context>

<specifics>
## Specific Ideas

- RESEARCH flag (roadmap): the exact `nodriver cdp.storage.set_cookies()` import path and `CookieParam` constructor signature must be verified against installed nodriver 0.50.3 before implementing the restore path. The `CookieJar.set_all()` workaround is confirmed from issues #1816/#2020 but the exact API shape needs local verification. Also confirm the get-cookies API for saving.
- This phase completes the cross-phase contract from Phase 22: the no-op `restore_session` stub becomes the live `SessionStore.restore()`. relaunch() already skips login() when restore_session returns True (P22), so enabling persistence transparently skips MFA on relaunch.
- Security: cookies are auth-bearing — the encrypted-at-rest guarantee (Fernet, no plaintext .json/.pickle) is the core security property. A test must assert no plaintext session file is ever written.

</specifics>

<deferred>
## Deferred Ideas

- Health surface / per-plugin liveness + heartbeat → Phase 24 (REL-07).
- Cookie refresh/rotation policy, multi-profile sessions → future (out of v4.0 scope).
- Live cross-restart MFA-skip verification on a real retailer → UAT debt (tracked, not blocking).

</deferred>
