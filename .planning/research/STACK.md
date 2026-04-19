# Technology Stack

**Project:** ShopPyBot — Async Plugin-Based Shopping Bot
**Researched:** 2026-04-19
**Brownfield context:** Existing Selenium + PyYAML + SQLite + pygame stack. This is an evolution, not a rewrite.

---

## Python Version Baseline

**Upgrade floor to Python 3.10.** Do not preserve the "3.8+" stated minimum.

Rationale:
- `asyncio.TaskGroup` (structured concurrency) requires 3.11+
- `pydantic-settings` 2.x (the YAML-capable version) requires 3.10+
- `nodriver` (async browser automation) requires 3.9+
- Python 3.8 reached end-of-life October 2024

**Recommendation:** Target 3.11 as minimum. 3.11 unlocks TaskGroup, is widely available, and aligns with all library requirements. The environment running this project is 3.14.3 — no constraints there.

---

## Recommended Stack

### 1. Browser Automation

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `nodriver` | 0.48.1 | Primary async browser driver | Async-first, CDP-direct, active successor to undetected-chromedriver |
| `playwright` | 1.58.0 | Fallback / alternative interface | Better documented, broader community, explicit async API |

**Decision: Use `nodriver` as the primary driver for all plugins.**

`nodriver` is the officially designated successor to `undetected-chromedriver` by the same author (ultrafunkamsterdam). It is fully async from the ground up (not bolted on), communicates via CDP without the WebDriver HTTP intermediary layer, and is specifically designed to bypass anti-bot systems like Cloudflare, Akamai, and DataDome. Latest release: November 2025 (0.48.1). Requires Python >= 3.9 — compatible with our 3.11 floor.

**Do NOT use:**
- Selenium async wrappers (`selenium-wire`, async thread pools around sync Selenium) — threading around a sync driver is fragile and defeats the purpose of the refactor
- `undetected-chromedriver` — nodriver supersedes it; the old package is no longer the primary target of maintenance
- `playwright` as primary — Playwright's stealth story requires `playwright-stealth` (a separate maintained package, v2.0.2 as of 2025), adds complexity, and benchmark data shows Playwright at ~25% bypass success vs. nodriver/zendriver at 25-75%. For a bot targeting retail checkout flows, the CDP-direct approach of nodriver is architecturally cleaner.
- Synchronous Selenium — incompatible with the asyncio parallel execution requirement

**Confidence: HIGH** — nodriver PyPI page verified, release date confirmed, successor relationship confirmed from official GitHub.

---

### 2. Async Concurrency

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `asyncio` (stdlib) | 3.11+ | Event loop, task scheduling | Built-in, no dep, TaskGroup in 3.11 |
| `asyncio.TaskGroup` | 3.11+ | Parallel plugin execution | Structured concurrency, better than gather() |

**Decision: Use `asyncio.TaskGroup` for concurrent platform checks.**

`asyncio.gather()` is the pre-3.11 approach but has a critical flaw for plugin execution: if one platform plugin raises an exception, gather() does not automatically cancel the remaining tasks. `TaskGroup` (3.11+) cancels all siblings on any failure — exactly the behavior needed when one platform's browser session crashes and you don't want zombie tasks.

Pattern for plugin dispatch:
```python
async with asyncio.TaskGroup() as tg:
    for plugin in loaded_plugins:
        tg.create_task(plugin.check_availability(item))
```

**Do NOT use:**
- `asyncio.gather()` — no structured cancellation; silently continues past failures
- `concurrent.futures.ThreadPoolExecutor` wrapping sync Selenium — reintroduces GIL contention, negates async gains
- `trio` or `anyio` — unnecessary abstraction layer; asyncio stdlib is sufficient for this use case

**Confidence: HIGH** — Python 3.11 docs verified, TaskGroup behavior confirmed from official documentation.

---

### 3. Plugin Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `importlib` (stdlib) | 3.11+ | Dynamic plugin loading | Built-in, sufficient for file-based discovery |
| `abc.ABC` (stdlib) | 3.11+ | Plugin interface enforcement | Enforces the 4-method contract at import time |

**Decision: Use `importlib` + `ABC` directly. Do NOT add `pluggy`.**

The project requirement is a `plugins/` directory with `.py` files that are auto-discovered. This is precisely the "naming convention discovery" pattern described in the Python Packaging User Guide. It requires zero external dependencies.

Discovery pattern:
```python
import importlib.util, pathlib
from bot.plugin_base import BotPlugin  # ABC

def load_plugins(plugin_dir: pathlib.Path) -> list[BotPlugin]:
    plugins = []
    for path in plugin_dir.glob("*.py"):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type)
                    and issubclass(obj, BotPlugin)
                    and obj is not BotPlugin):
                plugins.append(obj())
    return plugins
```

ABC enforces the contract:
```python
from abc import ABC, abstractmethod

class BotPlugin(ABC):
    platform: str  # e.g. "amazon"

    @abstractmethod
    async def login(self, browser) -> None: ...

    @abstractmethod
    async def check_availability(self, browser, item: dict) -> bool: ...

    @abstractmethod
    async def auto_buy(self, browser, item: dict, config: dict) -> bool: ...

    @abstractmethod
    async def detect_captcha(self, browser) -> bool: ...
```

**Do NOT use:**
- `pluggy` — designed for hook-based plugin systems (pytest-style); overkill for a simple auto-discovery pattern where all plugins implement the same interface. Adds a learning curve for contributors.
- Entry point registration (`importlib.metadata`) — requires `pyproject.toml` per plugin, contradicts the "drop a .py file" contributor story
- `stevedore` — heavyweight, originally from OpenStack, unnecessary

**Confidence: HIGH** — Python stdlib docs verified, pattern is well-established.

---

### 4. Configuration Management

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `pydantic-settings` | 2.13.1 | Typed config with YAML source | Validation at startup, replaces raw yaml.safe_load |
| `pyyaml` | existing | YAML parsing (via pydantic-settings[yaml]) | Keep as transitive dep, don't load it directly |

**Decision: Migrate from raw `yaml.safe_load()` to `pydantic-settings` with a YAML source.**

The existing config is a raw dict from `yaml.safe_load()` with no validation — typos in config.yml produce KeyErrors at runtime inside bot loops. `pydantic-settings` with `YamlConfigSettingsSource` gives:
1. Type coercion (strings to bool, int, etc.)
2. Validation errors at startup, not mid-run
3. Per-platform credential sections map naturally to nested Pydantic models
4. Optional environment variable overrides for CI/secrets (no code change needed)

The planned flat per-platform config (`platforms: amazon: {email, pwd, delay_ms}`) maps directly to a typed model hierarchy.

Install: `pip install pydantic-settings[yaml]` — this pulls PyYAML as a transitive dep. Remove the direct `pyyaml` from requirements.txt.

**Do NOT use:**
- Raw `yaml.safe_load()` continued — no validation, runtime errors only
- `dynaconf` — excellent for multi-environment server apps; overkill here. Adds a `dynaconf` binary, settings.toml + .secrets.toml convention the contributors don't need. The bot has one environment: the user's machine.
- `python-dotenv` — appropriate for 12-factor apps; doesn't serve the YAML-first, human-editable config.yml workflow this audience expects

**Confidence: HIGH** — pydantic-settings 2.13.1 on PyPI confirmed, YAML extra confirmed, Python 3.10+ requirement confirmed.

**Python version note:** pydantic-settings 2.x requires Python >= 3.10. This is one of the forcing functions for the 3.11 floor recommendation above.

---

### 5. HTTP / Notification Dispatch

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `httpx` | latest stable | Discord webhook, async HTTP | Sync + async API, drop-in for requests |
| `twilio` | latest stable | SMS notifications | Official SDK, well-maintained |
| `smtplib` (stdlib) | 3.11+ | Email/SMTP | Built-in, sufficient for transactional email |

**Decision: Use `httpx` for webhook dispatch. Keep `smtplib` for email. Use official `twilio` SDK for SMS.**

`httpx` provides both a synchronous and async client with an API nearly identical to `requests`. Since the codebase already uses `requests` for the TinyURL call, replacing `requests` with `httpx` unifies the HTTP client story. The async client (`httpx.AsyncClient`) slots into the async plugin dispatch pattern without wrapping.

For Discord webhook delivery, a single POST to the webhook URL suffices — no persistent connection, no high concurrency. `httpx` is appropriate (vs. `aiohttp` which excels at sustained high-concurrency pools). Benchmark data shows `aiohttp` outperforms `httpx` under heavy sustained load, but webhook dispatch (fire-and-forget POST on stock events) is not that workload.

`smtplib` + `email.mime` (stdlib) handles SMTP without an external dep. For the notification use case (send one email on stock event), it's sufficient.

`twilio` SDK: the official Python package, actively maintained, handles auth and API versioning. Do not handroll SMS via raw HTTP.

**Do NOT use:**
- `aiohttp` — async-only, requires session lifecycle management, higher complexity than the notification dispatch pattern warrants
- `requests` continued — sync-only, inconsistent with the async event loop; replace entirely with `httpx`
- Third-party Discord libraries (`discord.py`, etc.) — webhook dispatch doesn't need a bot client library

**Confidence: MEDIUM** — httpx vs aiohttp choice informed by multiple WebSearch sources. For this workload profile the distinction is low-stakes; either would work.

---

### 6. Retry and Rate Limiting

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `tenacity` | 9.1.4 | Retry with exponential backoff | Native async support, decorator API |
| `asyncio.sleep` (stdlib) | 3.11+ | Per-platform delay between checks | Built-in, no dep |

**Decision: Use `tenacity` for retry logic. Use `asyncio.sleep()` for inter-check delays.**

`tenacity` 9.x has full async support — the same `@retry` decorator applies to both sync and async functions. For the pattern of retrying a captcha-failed check or a transient network error on a platform check, it provides:
- `wait_exponential_jitter` — jitter prevents all platforms from hammering simultaneously after a backoff
- `stop_after_attempt` — prevents infinite retry loops
- `retry_if_exception_type` — selective retry on specific error types

Per-platform delays (`delay_ms` in config) should be implemented with `await asyncio.sleep(delay / 1000)` inside each plugin's check loop — not with tenacity, which is for exceptional retry paths, not normal pacing.

**Do NOT use:**
- `backoff` library — older, less maintained than tenacity, no meaningful advantage
- `time.sleep()` inside async code — blocks the event loop, defeats concurrent execution entirely
- `asyncio.sleep()` for retry logic — manually implementing exponential backoff with jitter is error-prone; use tenacity

**Confidence: HIGH** — tenacity 9.1.4 confirmed on PyPI, async support confirmed via official docs and WebSearch.

---

### 7. Retained from Existing Stack (No Change)

| Technology | Purpose | Notes |
|------------|---------|-------|
| `sqlite3` (stdlib) | Purchased-item tracking | Sufficient; no ORM needed for this schema |
| `pygame` | Audio alerts | Working, retain as-is |
| `colorama` | Colored terminal output | Working, retain as-is |
| `webdriver-manager` | ChromeDriver download | May become redundant if nodriver manages its own Chrome; evaluate during implementation |

**On SQLite:** The purchased-item tracking schema is simple (name, link, purchased flag). Do not introduce SQLAlchemy or any ORM. `sqlite3` stdlib is correct here.

**On webdriver-manager:** nodriver manages its own Chrome binary download differently from webdriver-manager. During Phase 1 implementation, verify whether `webdriver-manager` is still needed or can be dropped.

---

## Final Requirements.txt Shape

```
# Browser automation
nodriver>=0.48.1

# Config
pydantic-settings[yaml]>=2.13.1

# HTTP / notifications
httpx>=0.27.0
twilio>=9.0.0

# Retry
tenacity>=9.0.0

# Retained
pygame
colorama

# Dev / test
pytest
pytest-asyncio
```

**Remove:**
- `requests` (replaced by httpx)
- `pyyaml` (now a transitive dep via pydantic-settings[yaml])
- `selenium` (replaced by nodriver)
- `webdriver_manager` (evaluate; likely replaceable by nodriver's own install mechanism)
- duplicate entries in current requirements.txt (`selenium` and `pyyaml` each listed twice)

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Browser automation | nodriver | playwright + playwright-stealth | Playwright stealth is a separate package, more complex setup; nodriver is async-native and purpose-built for bot detection evasion |
| Browser automation | nodriver | selenium (async wrappers) | No native async; thread-pool wrapping is fragile and doesn't scale to 7+ platforms |
| Plugin discovery | importlib + ABC | pluggy | pluggy is hook-oriented, not interface-oriented; adds contributor complexity with no benefit for a uniform 4-method interface |
| Plugin discovery | importlib + ABC | entry_points | Requires pyproject.toml per plugin; contradicts drop-in .py contributor story |
| Config | pydantic-settings | dynaconf | Dynaconf suits multi-environment server apps; adds unnecessary complexity for a single-user CLI tool |
| Config | pydantic-settings | raw PyYAML | No validation; runtime KeyErrors inside bot loops are unacceptable |
| HTTP | httpx | aiohttp | aiohttp is async-only and shines under sustained high concurrency; webhook dispatch is low-frequency fire-and-forget |
| HTTP | httpx | requests | Sync-only; incompatible with asyncio event loop |
| Concurrency | asyncio.TaskGroup | asyncio.gather | gather() does not cancel siblings on failure; TaskGroup provides structured concurrency with automatic cleanup |

---

## Sources

- nodriver PyPI: https://pypi.org/project/nodriver/ (verified 0.48.1, Nov 2025)
- nodriver GitHub: https://github.com/ultrafunkamsterdam/nodriver
- playwright PyPI: https://pypi.org/project/playwright/ (verified 1.58.0, Jan 2026)
- playwright-stealth PyPI: https://pypi.org/project/playwright-stealth/
- Anti-bot benchmark comparison: https://medium.com/@dimakynal/baseline-performance-comparison-of-nodriver-zendriver-selenium-and-playwright-against-anti-bot-2e593db4b243
- pydantic-settings PyPI: https://pypi.org/project/pydantic-settings/ (verified 2.13.1, Feb 2026, Python >=3.10)
- tenacity PyPI: https://pypi.org/project/tenacity/ (verified 9.1.4, Feb 2026)
- asyncio.TaskGroup docs: https://docs.python.org/3/library/asyncio-task.html
- Python plugin discovery guide: https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/
- httpx vs aiohttp comparison: https://www.speakeasy.com/blog/python-http-clients-requests-vs-httpx-vs-aiohttp
- Playwright vs Selenium 2025: https://www.browserless.io/blog/playwright-vs-selenium-2025-browser-automation-comparison
