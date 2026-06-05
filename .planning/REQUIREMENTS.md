# Requirements — ShopPyBot

## v1 Requirements

### Core Framework

- [x] **CORE-01**: Plugin base class (ABC) defines `check_availability(url) → bool`, `auto_buy(driver, url, config) → bool`, `login(driver, config) → None`, `detect_captcha(driver) → bool`
- [x] **CORE-02**: `PLUGIN_API_VERSION = 1` constant exported from plugin base; default no-op implementations for `login` and `detect_captcha` so plugins can be check-only
- [x] **CORE-03**: Plugin registry auto-discovers `shopbot_plugin_*.py` files in `plugins/` at startup via `importlib`; logs warning for non-matching `.py` files
- [x] **CORE-04**: Plugin registry routes item URLs to correct plugin via `domain_pattern` attribute on each plugin class
- [x] **CORE-05**: Pydantic `AppConfig` validates `config.yml` at startup; startup fails with actionable error messages on missing/invalid fields
- [x] **CORE-06**: Config schema supports flat per-platform credential sections (`platforms.amazon.email`, `platforms.bestbuy.cvv`, etc.)
- [x] **CORE-07**: Config migration warnings emitted when old `app.amz_email` / `app.bb_email` keys are detected, guiding user to new schema
- [x] **CORE-08**: `example_plugin.py` with stub implementations + inline comments; `plugins/PLUGIN_DEV.md` contributor guide

### Security

- [x] **SEC-01**: Credentials (`amz_email`, `amz_pwd`, `bb_email`, `bb_password`) read from environment variables; config.yml holds non-sensitive settings only
- [x] **SEC-02**: CVV collected via `getpass.getpass()` at runtime — never stored in config.yml or logs
- [x] **SEC-03**: `--disable-web-security` Chrome flag removed from driver setup
- [x] **SEC-04**: CDP patch applied at driver startup to hide `navigator.webdriver` property
- [x] **SEC-05**: Real Chrome user agent string used instead of Selenium default
- [x] **SEC-06**: README includes disclaimer on personal use, TOS compliance, and account risk

### Platform Plugins — Existing (Refactor)

- [x] **PLG-01**: `plugins/shopbot_plugin_amazon.py` implements `RetailerPlugin` ABC; all purchase logic migrated from `amazon_bot.py`
- [x] **PLG-02**: `plugins/shopbot_plugin_bestbuy.py` implements `RetailerPlugin` ABC; fixes missing `update_item_purchased()` call after successful purchase
- [x] **PLG-03**: Each plugin owns its own WebDriver instance (`self.driver`) initialized in `__init__`; no shared global driver

### Platform Plugins — New

- [x] **PLG-04**: `plugins/shopbot_plugin_walmart.py` — availability check + auto-buy; documented as high anti-detection risk (PerimeterX/HUMAN Security)
- [x] **PLG-05**: `plugins/shopbot_plugin_target.py` — availability check; checkout labeled experimental (Akamai blocks headless Selenium consistently)
- [x] **PLG-06**: `plugins/shopbot_plugin_gamestop.py` — availability check + auto-buy; CAPTCHA on checkout documented
- [x] **PLG-07**: `plugins/shopbot_plugin_squareenix.py` — availability check + auto-buy
- [x] **PLG-08**: `plugins/shopbot_plugin_newegg.py` — availability check + auto-buy

### Async Orchestrator

- [x] **ASYNC-01**: Orchestrator runs all active plugins concurrently using `asyncio.TaskGroup`; one thread per plugin via `ThreadPoolExecutor`
- [x] **ASYNC-02**: Plugin WebDriver instances are staggered on startup (1.5s delay between each) to avoid ChromeDriver port conflicts
- [x] **ASYNC-03**: All `input()` blocking calls replaced with `asyncio.Event` + notification pattern
- [x] **ASYNC-04**: SQLite uses WAL mode and `busy_timeout=5000`; all connection usage wrapped in context managers
- [x] **ASYNC-05**: Single async write queue serializes all `update_item_purchased()` calls to prevent concurrent write conflicts

### Anti-Detection

- [x] **ANTI-01**: Per-platform configurable check interval with random jitter (`min_delay`, `max_delay` in config per platform)
- [x] **ANTI-02**: Rotating user agent strings drawn from a configurable list
- [x] **ANTI-03**: Headless mode toggle per platform in config (`headless: true/false`)

### Notifications

- [x] **NOTIF-01**: Notification dispatcher fan-outs to all configured channels; per-channel failures are isolated (one channel error does not block others)
- [x] **NOTIF-02**: Deduplication: one notification per item per restock event — not one per poll cycle; SQLite tracks `last_notified` timestamp per item
- [x] **NOTIF-03**: Sound notifier wraps existing `play_available_sound()` / `play_buy_sound()` / `play_notification_sound()`
- [x] **NOTIF-04**: Discord webhook notifier posts standardized embed (item name, URL, platform, timestamp, action taken)
- [x] **NOTIF-05**: Email/SMTP notifier sends alert on stock detection; configurable sender/recipient in config
- [x] **NOTIF-06**: SMS/Twilio notifier (opt-in only; disabled by default to avoid accidental charges)

### Infrastructure

- [x] **INFRA-01**: `requirements.txt` pinned to exact versions; duplicates removed; `python_requires >= 3.11`
- [x] **INFRA-02**: Logger singleton loaded once at module level; does not re-read `config.yml` on every log call
- [x] **INFRA-03**: `sys.stdout` suppression block in `main.py` removed; ChromeDriver output suppressed via service log path

### Community Documentation

- [x] **DOCS-01**: `CONTRIBUTING.md` covers fork/branch/PR workflow, commit conventions, test requirements, and links to `plugins/PLUGIN_DEV.md` for plugin contributions
- [x] **DOCS-02**: `CONTRIBUTING.md` includes plugin submission checklist: naming convention, required ABC methods, domain_pattern, test coverage, anti-detection risk declaration
- [x] **DOCS-03**: `SECURITY.md` covers responsible disclosure policy, known TOS/legal risks per platform, and guidance on keeping credentials out of commits
- [x] **DOCS-04**: GitHub issue templates for bug reports, plugin requests, and platform-specific issues
- [x] **DOCS-05**: GitHub PR template with checklist covering ABC compliance, naming convention, test presence, and risk documentation

---

## v2.0 Requirements (Active — Modular Core + Cross-Platform UX)

### Modular Core

- [ ] **MOD-01**: A stable core service API (e.g. `core/service.py` `BotService`) wraps registry + orchestrator + config + credential store and exposes: start/stop the bot, list/add/remove tracked items, read/update config, get status. Both CLI and GUI consume ONLY this API.
- [x] **MOD-02**: No bot logic lives in any front-end (CLI or GUI). Front-ends are thin adapters over `BotService`; a grep shows no orchestrator/registry/DB calls bypassing the service from front-end modules.
- [x] **MOD-03**: Installable package: `pyproject.toml` defines the package + a `shoppybot` console entry point; `pip install -e .` succeeds on Ubuntu and Windows; `python main.py` continues to work as a thin shim.

### Credential Store

- [x] **CRED-01**: `CredentialStore` interface (`get`/`set`/`delete`/`list` by key) abstracts secret storage; ALL secret reads (plugin creds, DISCORD_WEBHOOK_URL, SMTP_PASSWORD, Twilio SID/token/from) route through it — no scattered direct `os.environ` secret reads remain in plugins/notifiers.
- [x] **CRED-02**: Keyring backend uses the OS secret service via the `keyring` library (Windows Credential Manager / Linux Secret Service) when a backend is available.
- [x] **CRED-03**: Encrypted-file fallback for headless/no-keyring environments: a passphrase-derived key (scrypt or PBKDF2) encrypts secrets (AES/Fernet) in a file under the data dir; passphrase via prompt or an env var for unattended runs.
- [x] **CRED-04**: Env-var fallback preserves today's behavior when no store is configured; documented precedence (explicit store > keyring > encrypted-file > env).
- [x] **CRED-05**: Backend auto-selected at startup (detect OS + available backend) with an explicit config override; the ACTIVE backend name is logged, never the secret values.
- [x] **CRED-06**: No plaintext secrets on disk: secrets are never written to config.yml, logs, or SQLite; the encrypted-file store is the only at-rest form and it is encrypted (a test asserts no secret plaintext in those sinks).
- [x] **CRED-07**: Migration command imports existing env-var secrets into the selected store.

### CLI Front-End (default)

- [x] **CLI-01**: `shoppybot run` (default) starts the bot through `BotService` (keeps `python main.py` working as a shim).
- [x] **CLI-02**: `shoppybot setup` interactively stores/updates credentials (into `CredentialStore`) and basic config; works on Ubuntu and Windows.
- [x] **CLI-03**: `shoppybot items` (list/add/remove) and `shoppybot config` manage tracked items + settings via the core API.
- [x] **CLI-04**: The CLI is fully functional with NO web UI installed or running.

### Optional Web UI

- [x] **GUI-01**: Optional local web UI (FastAPI) launched via `shoppybot web`, served on localhost; provides nothing the CLI cannot do.
- [x] **GUI-02**: Manage tracked items (list/add/remove) through the UI via `BotService`.
- [x] **GUI-03**: Manage credentials + per-platform config through the UI, persisting secrets via `CredentialStore` (never plaintext to the browser, localStorage, or disk).
- [x] **GUI-04**: Start/stop the bot and view live status + recent logs from the UI.
- [x] **GUI-05**: The web UI is an optional extra (`pip install .[web]`); core + CLI run without FastAPI installed.
- [x] **GUI-06**: Binds to localhost (127.0.0.1) by default; any non-localhost bind requires explicit opt-in and prints a clear security warning (the UI manages credentials).

### Cross-Platform

- [x] **XPLAT-01**: Runs on Ubuntu (desktop + headless) and Windows; data dir + paths resolved per-OS (no hardcoded separators); the data/config/log locations are documented per OS.
- [ ] **XPLAT-02**: A documented verification matrix (and/or automated smoke) confirms import + CLI + credential-store backend selection on both Ubuntu and Windows.

## v2 Requirements (Deferred)

- GitHub wiki plugin registry with per-platform anti-detection difficulty ratings
- Proxy rotation support
- Automatic CAPTCHA solving integration
- Browser fingerprint spoofing beyond user agent
- Price monitoring / price drop alerts
- (now ACTIVE in v2.0) Web dashboard or GUI — promoted to an optional local web UI this milestone

---

## Out of Scope

- PyPI packaging per plugin — plugins/ folder + GitHub wiki achieves discoverability more simply
- Advanced fingerprint spoofing (FlareSolverr, etc.) — over-engineering for personal use target audience
- GUI / web dashboard — CLI + config.yml sufficient for target users
- Price monitoring — different use case from stock availability

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 — Foundations + Security | Complete |
| CORE-02 | Phase 1 — Foundations + Security | Complete |
| CORE-03 | Phase 2 — Plugin Migration | Complete |
| CORE-04 | Phase 2 — Plugin Migration | Complete |
| CORE-05 | Phase 1 — Foundations + Security | Complete |
| CORE-06 | Phase 1 — Foundations + Security | Complete |
| CORE-07 | Phase 1 — Foundations + Security | Complete |
| CORE-08 | Phase 2 — Plugin Migration | Complete |
| SEC-01 | Phase 1 — Foundations + Security | Complete |
| SEC-02 | Phase 1 — Foundations + Security | Complete |
| SEC-03 | Phase 1 — Foundations + Security | Complete |
| SEC-04 | Phase 1 — Foundations + Security | Complete |
| SEC-05 | Phase 1 — Foundations + Security | Complete |
| SEC-06 | Phase 1 — Foundations + Security | Complete |
| PLG-01 | Phase 2 — Plugin Migration | Complete |
| PLG-02 | Phase 2 — Plugin Migration | Complete |
| PLG-03 | Phase 2 — Plugin Migration | Complete |
| PLG-04 | Phase 6 — Platform Expansion | Complete |
| PLG-05 | Phase 6 — Platform Expansion | Complete |
| PLG-06 | Phase 6 — Platform Expansion | Complete |
| PLG-07 | Phase 6 — Platform Expansion | Complete |
| PLG-08 | Phase 6 — Platform Expansion | Complete |
| ASYNC-01 | Phase 4 — Async Orchestrator | Complete |
| ASYNC-02 | Phase 4 — Async Orchestrator | Complete |
| ASYNC-03 | Phase 4 — Async Orchestrator | Complete |
| ASYNC-04 | Phase 4 — Async Orchestrator | Complete |
| ASYNC-05 | Phase 4 — Async Orchestrator | Complete |
| ANTI-01 | Phase 6 — Platform Expansion | Complete |
| ANTI-02 | Phase 6 — Platform Expansion | Complete |
| ANTI-03 | Phase 6 — Platform Expansion | Complete |
| NOTIF-01 | Phase 5 — Notification System | Complete |
| NOTIF-02 | Phase 5 — Notification System | Complete |
| NOTIF-03 | Phase 5 — Notification System | Complete |
| NOTIF-04 | Phase 5 — Notification System | Complete |
| NOTIF-05 | Phase 5 — Notification System | Complete |
| NOTIF-06 | Phase 5 — Notification System | Complete |
| INFRA-01 | Phase 1 — Foundations + Security | Complete |
| INFRA-02 | Phase 1 — Foundations + Security | Complete |
| INFRA-03 | Phase 1 — Foundations + Security | Complete |
| DOCS-01 | Phase 3 — Community Documentation | Complete |
| DOCS-02 | Phase 3 — Community Documentation | Complete |
| DOCS-03 | Phase 3 — Community Documentation | Complete |
| DOCS-04 | Phase 3 — Community Documentation | Complete |
| DOCS-05 | Phase 3 — Community Documentation | Complete |
| MOD-01 | Phase 7 — Modular Core Service | Pending |
| MOD-02 | Phase 7 — Modular Core Service | Complete |
| MOD-03 | Phase 7 — Modular Core Service | Complete |
| CRED-01 | Phase 8 — Credential Store | Complete |
| CRED-02 | Phase 8 — Credential Store | Complete |
| CRED-03 | Phase 8 — Credential Store | Complete |
| CRED-04 | Phase 8 — Credential Store | Complete |
| CRED-05 | Phase 8 — Credential Store | Complete |
| CRED-06 | Phase 8 — Credential Store | Complete |
| CRED-07 | Phase 8 — Credential Store | Complete |
| CLI-01 | Phase 9 — CLI Front-End | Complete |
| CLI-02 | Phase 9 — CLI Front-End | Complete |
| CLI-03 | Phase 9 — CLI Front-End | Complete |
| CLI-04 | Phase 9 — CLI Front-End | Complete |
| GUI-01 | Phase 10 — Optional Web UI | Complete |
| GUI-02 | Phase 10 — Optional Web UI | Complete |
| GUI-03 | Phase 10 — Optional Web UI | Complete |
| GUI-04 | Phase 10 — Optional Web UI | Complete |
| GUI-05 | Phase 10 — Optional Web UI | Complete |
| GUI-06 | Phase 10 — Optional Web UI | Complete |
| XPLAT-01 | Phase 11 — Cross-Platform Verification | Complete |
| XPLAT-02 | Phase 11 — Cross-Platform Verification | Pending |
