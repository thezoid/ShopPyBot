# Requirements — ShopPyBot

## v1 Requirements

### Core Framework

- [x] **CORE-01**: Plugin base class (ABC) defines `check_availability(url) → bool`, `auto_buy(driver, url, config) → bool`, `login(driver, config) → None`, `detect_captcha(driver) → bool`
- [x] **CORE-02**: `PLUGIN_API_VERSION = 1` constant exported from plugin base; default no-op implementations for `login` and `detect_captcha` so plugins can be check-only
- [ ] **CORE-03**: Plugin registry auto-discovers `shopbot_plugin_*.py` files in `plugins/` at startup via `importlib`; logs warning for non-matching `.py` files
- [ ] **CORE-04**: Plugin registry routes item URLs to correct plugin via `domain_pattern` attribute on each plugin class
- [x] **CORE-05**: Pydantic `AppConfig` validates `config.yml` at startup; startup fails with actionable error messages on missing/invalid fields
- [x] **CORE-06**: Config schema supports flat per-platform credential sections (`platforms.amazon.email`, `platforms.bestbuy.cvv`, etc.)
- [x] **CORE-07**: Config migration warnings emitted when old `app.amz_email` / `app.bb_email` keys are detected, guiding user to new schema
- [ ] **CORE-08**: `example_plugin.py` with stub implementations + inline comments; `plugins/PLUGIN_DEV.md` contributor guide

### Security

- [x] **SEC-01**: Credentials (`amz_email`, `amz_pwd`, `bb_email`, `bb_password`) read from environment variables; config.yml holds non-sensitive settings only
- [ ] **SEC-02**: CVV collected via `getpass.getpass()` at runtime — never stored in config.yml or logs
- [ ] **SEC-03**: `--disable-web-security` Chrome flag removed from driver setup
- [ ] **SEC-04**: CDP patch applied at driver startup to hide `navigator.webdriver` property
- [ ] **SEC-05**: Real Chrome user agent string used instead of Selenium default
- [ ] **SEC-06**: README includes disclaimer on personal use, TOS compliance, and account risk

### Platform Plugins — Existing (Refactor)

- [ ] **PLG-01**: `plugins/shopbot_plugin_amazon.py` implements `RetailerPlugin` ABC; all purchase logic migrated from `amazon_bot.py`
- [ ] **PLG-02**: `plugins/shopbot_plugin_bestbuy.py` implements `RetailerPlugin` ABC; fixes missing `update_item_purchased()` call after successful purchase
- [ ] **PLG-03**: Each plugin owns its own WebDriver instance (`self.driver`) initialized in `__init__`; no shared global driver

### Platform Plugins — New

- [ ] **PLG-04**: `plugins/shopbot_plugin_walmart.py` — availability check + auto-buy; documented as high anti-detection risk (PerimeterX/HUMAN Security)
- [ ] **PLG-05**: `plugins/shopbot_plugin_target.py` — availability check; checkout labeled experimental (Akamai blocks headless Selenium consistently)
- [ ] **PLG-06**: `plugins/shopbot_plugin_gamestop.py` — availability check + auto-buy; CAPTCHA on checkout documented
- [ ] **PLG-07**: `plugins/shopbot_plugin_squareenix.py` — availability check + auto-buy
- [ ] **PLG-08**: `plugins/shopbot_plugin_newegg.py` — availability check + auto-buy

### Async Orchestrator

- [ ] **ASYNC-01**: Orchestrator runs all active plugins concurrently using `asyncio.TaskGroup`; one thread per plugin via `ThreadPoolExecutor`
- [ ] **ASYNC-02**: Plugin WebDriver instances are staggered on startup (1.5s delay between each) to avoid ChromeDriver port conflicts
- [ ] **ASYNC-03**: All `input()` blocking calls replaced with `asyncio.Event` + notification pattern
- [ ] **ASYNC-04**: SQLite uses WAL mode and `busy_timeout=5000`; all connection usage wrapped in context managers
- [ ] **ASYNC-05**: Single async write queue serializes all `update_item_purchased()` calls to prevent concurrent write conflicts

### Anti-Detection

- [ ] **ANTI-01**: Per-platform configurable check interval with random jitter (`min_delay`, `max_delay` in config per platform)
- [ ] **ANTI-02**: Rotating user agent strings drawn from a configurable list
- [ ] **ANTI-03**: Headless mode toggle per platform in config (`headless: true/false`)

### Notifications

- [ ] **NOTIF-01**: Notification dispatcher fan-outs to all configured channels; per-channel failures are isolated (one channel error does not block others)
- [ ] **NOTIF-02**: Deduplication: one notification per item per restock event — not one per poll cycle; SQLite tracks `last_notified` timestamp per item
- [ ] **NOTIF-03**: Sound notifier wraps existing `play_available_sound()` / `play_buy_sound()` / `play_notification_sound()`
- [ ] **NOTIF-04**: Discord webhook notifier posts standardized embed (item name, URL, platform, timestamp, action taken)
- [ ] **NOTIF-05**: Email/SMTP notifier sends alert on stock detection; configurable sender/recipient in config
- [ ] **NOTIF-06**: SMS/Twilio notifier (opt-in only; disabled by default to avoid accidental charges)

### Infrastructure

- [x] **INFRA-01**: `requirements.txt` pinned to exact versions; duplicates removed; `python_requires >= 3.11`
- [x] **INFRA-02**: Logger singleton loaded once at module level; does not re-read `config.yml` on every log call
- [ ] **INFRA-03**: `sys.stdout` suppression block in `main.py` removed; ChromeDriver output suppressed via service log path

### Community Documentation

- [ ] **DOCS-01**: `CONTRIBUTING.md` covers fork/branch/PR workflow, commit conventions, test requirements, and links to `plugins/PLUGIN_DEV.md` for plugin contributions
- [ ] **DOCS-02**: `CONTRIBUTING.md` includes plugin submission checklist: naming convention, required ABC methods, domain_pattern, test coverage, anti-detection risk declaration
- [ ] **DOCS-03**: `SECURITY.md` covers responsible disclosure policy, known TOS/legal risks per platform, and guidance on keeping credentials out of commits
- [ ] **DOCS-04**: GitHub issue templates for bug reports, plugin requests, and platform-specific issues
- [ ] **DOCS-05**: GitHub PR template with checklist covering ABC compliance, naming convention, test presence, and risk documentation

---

## v2 Requirements (Deferred)

- GitHub wiki plugin registry with per-platform anti-detection difficulty ratings
- Proxy rotation support
- Automatic CAPTCHA solving integration
- Browser fingerprint spoofing beyond user agent
- Price monitoring / price drop alerts
- Web dashboard or GUI

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
| CORE-03 | Phase 2 — Plugin Migration | Pending |
| CORE-04 | Phase 2 — Plugin Migration | Pending |
| CORE-05 | Phase 1 — Foundations + Security | Complete |
| CORE-06 | Phase 1 — Foundations + Security | Complete |
| CORE-07 | Phase 1 — Foundations + Security | Complete |
| CORE-08 | Phase 2 — Plugin Migration | Pending |
| SEC-01 | Phase 1 — Foundations + Security | Complete |
| SEC-02 | Phase 1 — Foundations + Security | Pending |
| SEC-03 | Phase 1 — Foundations + Security | Pending |
| SEC-04 | Phase 1 — Foundations + Security | Pending |
| SEC-05 | Phase 1 — Foundations + Security | Pending |
| SEC-06 | Phase 1 — Foundations + Security | Pending |
| PLG-01 | Phase 2 — Plugin Migration | Pending |
| PLG-02 | Phase 2 — Plugin Migration | Pending |
| PLG-03 | Phase 2 — Plugin Migration | Pending |
| PLG-04 | Phase 6 — Platform Expansion | Pending |
| PLG-05 | Phase 6 — Platform Expansion | Pending |
| PLG-06 | Phase 6 — Platform Expansion | Pending |
| PLG-07 | Phase 6 — Platform Expansion | Pending |
| PLG-08 | Phase 6 — Platform Expansion | Pending |
| ASYNC-01 | Phase 4 — Async Orchestrator | Pending |
| ASYNC-02 | Phase 4 — Async Orchestrator | Pending |
| ASYNC-03 | Phase 4 — Async Orchestrator | Pending |
| ASYNC-04 | Phase 4 — Async Orchestrator | Pending |
| ASYNC-05 | Phase 4 — Async Orchestrator | Pending |
| ANTI-01 | Phase 6 — Platform Expansion | Pending |
| ANTI-02 | Phase 6 — Platform Expansion | Pending |
| ANTI-03 | Phase 6 — Platform Expansion | Pending |
| NOTIF-01 | Phase 5 — Notification System | Pending |
| NOTIF-02 | Phase 5 — Notification System | Pending |
| NOTIF-03 | Phase 5 — Notification System | Pending |
| NOTIF-04 | Phase 5 — Notification System | Pending |
| NOTIF-05 | Phase 5 — Notification System | Pending |
| NOTIF-06 | Phase 5 — Notification System | Pending |
| INFRA-01 | Phase 1 — Foundations + Security | Complete |
| INFRA-02 | Phase 1 — Foundations + Security | Complete |
| INFRA-03 | Phase 1 — Foundations + Security | Pending |
| DOCS-01 | Phase 3 — Community Documentation | Pending |
| DOCS-02 | Phase 3 — Community Documentation | Pending |
| DOCS-03 | Phase 3 — Community Documentation | Pending |
| DOCS-04 | Phase 3 — Community Documentation | Pending |
| DOCS-05 | Phase 3 — Community Documentation | Pending |
