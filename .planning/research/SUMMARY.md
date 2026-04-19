# Research Summary — ShopPyBot

## Executive Summary

ShopPyBot is being refactored from a sequential Selenium monolith into an async shopping bot with a drop-in community plugin framework. The plugin ABC and importlib-based auto-discovery must be locked and versioned **before** any platform code is written — every other component depends on that contract.

The recommended approach replaces Selenium with `nodriver` (async-native CDP-direct successor to undetected-chromedriver), raises the Python floor to 3.11, migrates raw YAML loading to `pydantic-settings`, and replaces `requests` with `httpx`. Concurrency model: one dedicated browser instance per plugin, asyncio dispatching to a `ThreadPoolExecutor`.

Two highest risks are architectural and must be resolved in Phase 1: shared single WebDriver (crash-on-async) and CVV/credentials in plaintext config.yml (security incident before open source launch).

---

## Recommended Stack Changes

| Action | Library | Replaces | Reason |
|--------|---------|---------|--------|
| Adopt | `nodriver 0.48.1` | `selenium` | Async-native, CDP-direct, bot-detection resistant |
| Adopt | `pydantic-settings[yaml] 2.13.1` | `pyyaml` direct | Typed config, startup validation |
| Adopt | `httpx` | `requests` | Sync+async in one client; webhook dispatch |
| Adopt | `tenacity 9.1.4` | manual retries | Exponential jitter, native async |
| Adopt | `asyncio.TaskGroup` (3.11 stdlib) | `asyncio.gather` | Sibling cancellation on failure |
| Drop | `selenium` | — | Replaced by nodriver |
| Drop | `requests` | — | Replaced by httpx |
| Drop | `webdriver-manager` | — | nodriver manages its own Chrome binary (verify) |
| Retain | `sqlite3`, `pygame`, `colorama` | — | Working; wrap in proper abstractions |

**Python floor:** Raise to 3.11 minimum (Python 3.8 EOL Oct 2024; TaskGroup requires 3.11; pydantic-settings 2.x requires 3.10+).

---

## Table Stakes vs. Differentiators

### Must Have (survive the refactor)
- Stock availability check per item URL
- Continuous async polling loop
- Configurable check interval per platform
- Duplicate-purchase prevention (SQLite purchased flag)
- Test mode / dry run
- Sound alert on stock detection
- Structured logging with file output
- Per-item auto-buy toggle
- CAPTCHA detection with manual fallback (generalized per plugin)

### Should Have (differentiators for v1)
- Drop-in plugin framework with ABC interface — the core project identity
- Plugin auto-discovery at startup (importlib, zero config)
- `example_plugin.py` + `PLUGIN_DEV.md` contributor template
- Async parallel platform checking
- Discord webhook notifications
- Email/SMTP notifications
- Per-platform configurable delay + jitter
- Headless mode toggle in config
- Rotating user agents

### Defer to v2+
- SMS/Twilio (valid but secondary; adds per-message cost)
- Target, GameStop, Square Enix, NewEgg plugins (high detection risk)
- Proxy rotation, automatic CAPTCHA solving, GUI

---

## Recommended Build Order

**Phase 1 — Foundations and Security Hardening**
`core/plugin_base.py` (ABC), `core/config_schema.py` (Pydantic), credential migration to env vars, driver stealth fixes, requirements cleanup. Must complete before open source launch.

**Phase 2 — Plugin Migration (Amazon + BestBuy)**
Refactor existing bots to implement ABC. `core/plugin_registry.py` (importlib scanner). Fix BestBuy `update_item_purchased` gap. Write `example_plugin.py` + contributor docs.

**Phase 3 — Async Orchestrator**
`core/orchestrator.py` with `asyncio.TaskGroup` + `ThreadPoolExecutor`. SQLite WAL mode + write queue. Replace all `input()` blocking calls. Stagger driver startup.

**Phase 4 — Notification System**
`NotifierABC` + `NotificationDispatcher`. `SoundNotifier`, `DiscordNotifier`, `EmailNotifier`. Per-item deduplication (one alert per restock event).

**Phase 5 — Community Platform Expansion**
Walmart plugin (label PerimeterX risk). GitHub wiki registry. Additional platforms as community contributions.

---

## Top 5 Pitfalls

1. **Shared WebDriver across async workers** (Phase 3) — One `self.driver` per plugin in `__init__`; stagger startup 1.5s per worker. Without this: non-deterministic crashes and wrong-platform DOM reads.

2. **CVS and credentials in plaintext config.yml** (Phase 1, before going public) — CVV via `getpass` at runtime; credentials via env vars; pre-commit hook for `_pwd`/`_cvv` patterns.

3. **`navigator.webdriver` and `--disable-web-security` flags expose bot** (Phase 1) — CDP patch to hide webdriver property; remove `--disable-web-security`; use real Chrome UA.

4. **SQLite `database is locked` under concurrent writers** (Phase 3) — WAL mode + `busy_timeout=5000`; context managers on all connections; single async write queue.

5. **Plugin interface breakage kills contributor trust** (Phase 1) — Only `check_availability` and `auto_buy` abstract; others get no-op defaults. Add `PLUGIN_API_VERSION = 1` before any external plugins exist.

---

## Conflicts and Resolutions

| Conflict | Resolution |
|----------|-----------|
| nodriver (STACK) vs. Selenium/run_in_executor (ARCHITECTURE) | Adopt nodriver Phase 1/2. Orchestrator supports both native async (nodriver) and `run_in_executor` (Selenium fallback). |
| `asyncio.TaskGroup` (STACK) vs. `asyncio.gather` (ARCHITECTURE) | Use `TaskGroup` — `gather()` leaves zombie browser sessions on plugin failure. |
| Plugin naming: scan all `*.py` (ARCHITECTURE) vs. `shopbot_plugin_{platform}.py` only (PITFALLS) | Enforce naming convention; log warning for non-matching files rather than silently skipping. |

---

## Research Flags

- **Phase 3:** nodriver's exact async session lifecycle needs validation against the plugin interface before Phase 3 planning.
- **Phase 5 (Walmart):** PerimeterX/HUMAN bypass viability with nodriver needs targeted research before committing.
- **Phase 1:** Config migration warning messages need explicit authoring for existing users upgrading from old `config.yml` schema.
