# Platform Verification Guide

This document covers platform-specific path locations, expected credential backends per
environment, steps to reproduce the CI verification matrix locally, and the manual checklist
matrix for milestone sign-off (including the deferred live checks from Phases 8, 9, and 10).

## Resolved Paths per OS

All paths are resolved at runtime by `core/paths.py` via `platformdirs`. The `SHOPBOT_DATA_DIR`
environment variable overrides all path resolution to the given root (used in CI and isolated
test runs).

| Location | Windows | Ubuntu |
|----------|---------|--------|
| Data dir | `%LOCALAPPDATA%\shoppybot` | `~/.local/share/shoppybot` |
| Config path | `%LOCALAPPDATA%\shoppybot\config.yml` | `~/.local/share/shoppybot/config.yml` |
| Log dir | `%LOCALAPPDATA%\shoppybot\Logs` | `~/.local/state/shoppybot/log` |
| DB path | `%LOCALAPPDATA%\shoppybot\shop_py_bot.db` | `~/.local/share/shoppybot/shop_py_bot.db` |
| Creds file | `%LOCALAPPDATA%\shoppybot\creds.bin` | `~/.local/share/shoppybot/creds.bin` |

Notes:
- `appauthor=False` is passed to `platformdirs.PlatformDirs` to suppress the redundant vendor
  subdir on Windows (producing `%LOCALAPPDATA%\shoppybot`, not `%LOCALAPPDATA%\shoppybot\shoppybot`).
- On Ubuntu, `user_log_dir` is `XDG_STATE_HOME/shoppybot/log` (defaults to
  `~/.local/state/shoppybot/log`), not the data dir (XDG separation of state vs data).
- First-run migration: if legacy project-relative files (`data/shop_py_bot.db`,
  `data/creds.bin`, `config.yml`, `logs/`) exist, they are copied to the OS-standard
  locations on the first run and then removed. The migration is idempotent.

## Expected Credential Backend per Environment

| Environment | Backend | Key Store | Notes |
|-------------|---------|-----------|-------|
| Windows (any) | keyring (Credential Manager) | Windows Credential Manager | `_has_real_keyring()` returns True on all Windows sessions |
| Ubuntu desktop (GNOME/KDE with Secret Service) | keyring (Secret Service) | GNOME Keyring / KWallet | Requires an active D-Bus session and Secret Service daemon |
| Ubuntu headless (no D-Bus / CI runner) | encrypted-file | `creds.bin` (Fernet+scrypt) | `_has_real_keyring()` returns False; passphrase from `SHOPBOT_STORE_PASSPHRASE` env var |
| Any OS, no keyring, no passphrase env var | env-var fallback | process environment | `EnvVarBackend`; reads `BB_EMAIL`, `BB_PASSWORD`, etc. directly from env |

The selection order in `_build_store`:
1. Explicit backend from config (`credentials.backend` key).
2. Real keyring available (`_has_real_keyring()` True): `KeyringBackend`.
3. `SHOPBOT_STORE_PASSPHRASE` set in env: `EncryptedFileBackend`.
4. Fallback: `EnvVarBackend`.

## Reproduce the Verification Matrix

### Prerequisites

```
pip install -e .[web]
```

This installs the full surface including FastAPI routes and all test dependencies.

### Automated half (CI matrix)

The GitHub Actions workflow `.github/workflows/ci.yml` runs automatically on push and pull
request to `master` and `dev`. It covers:

- ubuntu-latest and windows-latest in parallel (`strategy.fail-fast: false`)
- Python 3.13
- Full pytest suite (`pytest --tb=short`)
- Headless guards via job-level env vars:
  - `SDL_AUDIODRIVER=dummy`: prevents `pygame.mixer.init()` failure (no audio device on CI)
  - `SDL_VIDEODRIVER=dummy`: prevents pygame display init error
  - `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring`: prevents D-Bus probe hang on
    headless Ubuntu; `_has_real_keyring()` detects `NullKeyring` and returns False
  - `SHOPBOT_DATA_DIR=${{ runner.temp }}/shopbot`: redirects all path resolution to a
    writable temp dir so tests never write to the runner home directory

To reproduce the CI environment locally:

```bash
# Linux
export SDL_AUDIODRIVER=dummy
export SDL_VIDEODRIVER=dummy
export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
export SHOPBOT_DATA_DIR=/tmp/shopbot-test
pytest --tb=short

# Windows (PowerShell)
$env:SDL_AUDIODRIVER = "dummy"
$env:SDL_VIDEODRIVER = "dummy"
$env:PYTHON_KEYRING_BACKEND = "keyring.backends.null.Keyring"
$env:SHOPBOT_DATA_DIR = "$env:TEMP\shopbot-test"
pytest --tb=short
```

### Manual half (real hardware)

See the checklist matrix below. The CI matrix covers the automated columns; the desktop and
headless Ubuntu columns require real Linux environments.

## Manual Verification Checklist

Use this matrix on real hardware to close the milestone. Check each cell after verifying.

Legend: [x] = verified, [ ] = not yet verified, N/A = not applicable for this environment.

### Core CLI Commands

| Check | Ubuntu desktop | Ubuntu headless | Windows |
|-------|---------------|-----------------|---------|
| `shoppybot --help` exits 0 | [ ] | [ ] | [ ] |
| `shoppybot items list` exits 0 (empty DB) | [ ] | [ ] | [ ] |
| `shoppybot config show` exits 0 | [ ] | [ ] | [ ] |
| `shoppybot items add <url> <name>` exits 0 | [ ] | [ ] | [ ] |
| `shoppybot items remove <name>` exits 0 | [ ] | [ ] | [ ] |

### Credential Backend Selection

| Check | Ubuntu desktop | Ubuntu headless | Windows |
|-------|---------------|-----------------|---------|
| Auto-selects keyring backend | [ ] | N/A | [ ] |
| Auto-selects encrypted-file on headless (no Secret Service) | N/A | [ ] | N/A |
| `shoppybot setup` completes with keyring backend | [ ] | N/A | [ ] |
| `shoppybot setup` completes with encrypted-file backend | N/A | [ ] | N/A |
| `shoppybot setup` completes with env-var backend | [ ] | [ ] | [ ] |

### Path Resolution

| Check | Ubuntu desktop | Ubuntu headless | Windows |
|-------|---------------|-----------------|---------|
| DB created under `~/.local/share/shoppybot/` | [ ] | [ ] | N/A |
| DB created under `%LOCALAPPDATA%\shoppybot\` | N/A | N/A | [ ] |
| Logs written under `~/.local/state/shoppybot/log/` | [ ] | [ ] | N/A |
| Logs written under `%LOCALAPPDATA%\shoppybot\Logs\` | N/A | N/A | [ ] |
| First-run migration runs when legacy `data/` exists | [ ] | [ ] | [ ] |
| Migration is idempotent on second run | [ ] | [ ] | [ ] |

### Phase 8 Deferred Live Checks: Credential Store Persistence

These checks were deferred from Phase 8 (credential store). Verify on real hardware.

Phase 12 execution note (2026-06-09, Windows dev machine, non-interactive agent environment):
MC-1 (keyring restart survival) and the encrypted-file restart variant require an interactive terminal
and a real process restart cycle, neither of which are available in the agent environment. Windows
variants are recorded as PENDING; Ubuntu variants require a second machine and are also pending.

| Check | Ubuntu desktop | Ubuntu headless | Windows |
|-------|---------------|-----------------|---------|
| Keyring secret survives process restart: run `shoppybot setup`, exit, restart, confirm retrieval with no env var | pending Ubuntu access | N/A | PENDING -- pending interactive manual run on a real Windows TTY |
| Headless Ubuntu auto-selects `encrypted-file` when no Secret Service is active | N/A | pending Ubuntu access | N/A |
| Encrypted-file secret survives process restart: set `SHOPBOT_STORE_PASSPHRASE`, restart, confirm retrieval | pending Ubuntu access | pending Ubuntu access | PENDING -- pending interactive manual run on a real Windows TTY |

Repro steps for keyring restart check:
1. Run `shoppybot setup` and complete credential entry with keyring backend.
2. Exit the process completely.
3. Unset any credential env vars.
4. Run `shoppybot config show` or `shoppybot items list` -- must not prompt for credentials again.

### Phase 9 Deferred Live Checks: CLI Setup TTY

These checks were deferred from Phase 9 (CLI front end). Verify on real hardware.

Phase 12 execution note (2026-06-09, Windows dev machine, non-interactive agent environment):
MC-2 (masked-TTY credential prompt) requires an interactive terminal session with a human observer
to confirm no-echo behavior. The agent environment has no real TTY available. Windows variants are
PENDING; Ubuntu variants require a separate machine.

| Check | Ubuntu desktop | Ubuntu headless | Windows |
|-------|---------------|-----------------|---------|
| `shoppybot setup` prompts for credentials with no echo (masked TTY) | pending Ubuntu access | pending Ubuntu access | PENDING -- pending interactive manual run on a real Windows TTY |
| Credential input does not appear in terminal history | pending Ubuntu access | pending Ubuntu access | PENDING -- pending interactive manual run on a real Windows TTY |
| Name-only confirm prompt shows item name only (no secret values) | pending Ubuntu access | pending Ubuntu access | PENDING -- pending interactive manual run on a real Windows TTY |

Repro steps:
1. Open a fresh terminal (PowerShell on Windows; bash/zsh on Ubuntu).
2. Run `shoppybot setup`.
3. At each credential prompt: type a value and verify no characters are echoed.
4. At the confirmation prompt: verify only the item name is shown, not the entered value.

### Phase 10 Deferred Live Checks: Web Dashboard

These checks were deferred from Phase 10 (optional web UI). Verify on real hardware.

Phase 12 execution note (2026-06-09, Windows dev machine, non-interactive agent environment):
MC-3 (live dashboard render, Start/Stop, log polling) and MC-4 (0.0.0.0 banner live render) require
an interactive browser session that cannot be automated in this agent environment. Windows variants
are PENDING. Ubuntu browser variants require a separate machine. Headless Ubuntu for `shoppybot web`
startup-only (no browser) could be checked but requires Ubuntu access.

MC-4 automated note: The `is_non_local` banner Jinja2 conditional is CI-asserted by
`tests/test_web_dashboard.py` (Plan 12-03, committed 2026-06-09). Both directions proven:
banner present when `is_non_local=True`, absent when `is_non_local=False`. The live browser
render is still PENDING human verification.

| Check | Ubuntu desktop | Ubuntu headless | Windows |
|-------|---------------|-----------------|---------|
| `shoppybot web` starts without error | pending Ubuntu access | pending Ubuntu access | PENDING -- pending interactive manual run on a real Windows TTY |
| Dashboard renders in browser at `http://localhost:8000` | pending Ubuntu access | N/A | PENDING -- pending interactive manual run on a real Windows TTY |
| Dashboard shows items list section | pending Ubuntu access | N/A | PENDING -- pending interactive manual run on a real Windows TTY |
| Dashboard shows config section | pending Ubuntu access | N/A | PENDING -- pending interactive manual run on a real Windows TTY |
| Start/Stop bot button triggers live state change | pending Ubuntu access | N/A | PENDING -- pending interactive manual run on a real Windows TTY |
| Log panel updates via live polling (no full-page reload) | pending Ubuntu access | N/A | PENDING -- pending interactive manual run on a real Windows TTY |
| `shoppybot web --host 0.0.0.0` shows non-local binding warning banner (MC-4; CI-asserted by tests/test_web_dashboard.py Plan 12-03) | pending Ubuntu access | pending Ubuntu access | PENDING -- pending interactive manual run on a real Windows TTY |

Repro steps for non-local banner:
1. Run `shoppybot web --host 0.0.0.0`.
2. Open `http://localhost:8000` in a browser.
3. Verify a warning banner is visible indicating the server is accessible from non-local addresses.

Repro steps for live log polling:
1. Start the web server with `shoppybot web`.
2. In a separate terminal, run `shoppybot run` (or trigger a bot action).
3. Observe the log panel in the browser updating without a page reload.
