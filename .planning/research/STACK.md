# Technology Stack

**Project:** ShopPyBot — Async Plugin-Based Shopping Bot
**Researched:** 2026-04-19 (v1/v2 baseline); v3.0 additions researched 2026-06-06
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
- `requests` continued — sync-only; inconsistent with the async event loop; replace entirely with `httpx`
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

---

---

# v3.0 Stack Additions — Resilience + Ecosystem

**Researched:** 2026-06-06
**Confidence:** MEDIUM-HIGH overall. nodriver proxy API is still maturing (proxy_server in
create_context confirmed; authenticated proxy extension approach confirmed via community demo).
CAPTCHA SDK async class verified from PyPI and GitHub. Fingerprint benchmark data from
independent 31-target study.

Fixed baseline (verified current as of 2026-06-06): nodriver 0.50.3, Python 3.13.

---

## Feature 1: Proxy Rotation

### Decision: DIY thin wrapper using nodriver `create_context(proxy_server=...)` — no external library

**How nodriver handles proxies (MEDIUM confidence — verified from official docs + community demo):**

`Browser.create_context()` accepts `proxy_server: str` and `proxy_bypass_list: str`. This is the
correct insertion point per official docs at
https://ultrafunkamsterdam.github.io/nodriver/nodriver/classes/browser.html.

Unauthenticated: pass directly as `"http://host:port"` or `"socks5://host:port"`.
SOCKS5 with auth: `"socks://USERNAME:PASSWORD@SERVER:PORT"` (documented).
HTTP with auth: Chrome ignores username/password in `--proxy-server` CLI args. Use a small
Chrome extension (a temp ZIP with a background.js that calls
`chrome.webRequest.onAuthRequired`) loaded via `--load-extension`. This is documented in the
community demo at https://github.com/TufayelLUS/Python-nodriver-use-all-type-proxy and is the
standard workaround for authenticated HTTP proxies in Chromium-based tools.

**Why DIY, not a library:**

Every proxy-rotation library (scrapy-rotating-proxies, proxy-pool, proxybroker) is Scrapy-coupled,
requests/httpx-only, or unmaintained. The rotation logic for this bot is: a list of proxy strings
in config, `itertools.cycle` over them, advance on request or on `check_availability` failure.
That is 15-20 lines in `core/proxy.py` — not a dependency.

### Stack addition for Feature 1

| Library | pip name | Version | License | Purpose |
|---------|----------|---------|---------|---------|
| None (stdlib only) | — | — | — | `itertools.cycle`, `zipfile`, `tempfile` for extension ZIP |

**Integration into plugin ABC:**
- Add optional `proxy_list: list[str] = []` to per-platform pydantic config model.
- `core/proxy.py` exposes `ProxyRotator(proxy_list)` with `.next() -> str` and
  `.make_auth_extension(host, port, user, pwd) -> Path` (writes temp ZIP, returns path).
- `RetailerPlugin.setup()` reads `self.config.platforms.<key>.proxy_list`, constructs a
  `ProxyRotator`, and passes the next proxy to `nodriver.start()` or `create_context()`.
- On `check_availability` failure that looks like a block (HTTP 403, timeout), rotate to next
  proxy on the subsequent call. No per-request rotation — that requires per-request
  `create_context`, which re-navigates the entire session and is too expensive for checkout flows.

### What NOT to add for Feature 1

| Avoid | Why |
|-------|-----|
| `proxybroker` | Unmaintained since 2020; Python 3.10+ incompatible |
| `scrapy-rotating-proxies` | Scrapy-only; incompatible with nodriver/asyncio |
| `proxy-pool` | Requires Redis; absurd overhead for a personal bot |
| `selenium-wire` | Selenium-only; conflicts with nodriver architecture |
| FlareSolverr sidecar | Docker dependency; overkill for personal use |
| Per-request proxy rotation | Forces full browser session restart per check; destroys login state |

---

## Feature 2: CAPTCHA-Solving Integration

### Decision: `2captcha-python` with `AsyncTwoCaptcha`

**Comparison of viable options (verified 2026-06-06):**

| SDK | pip name | Version | License | Async | reCAPTCHA v2/v3 | Turnstile | hCaptcha | PerimeterX |
|-----|----------|---------|---------|-------|-----------------|-----------|----------|------------|
| `2captcha-python` | `2captcha-python` | 2.0.7 | MIT | YES (`AsyncTwoCaptcha`) | YES | YES | Not documented | NO direct |
| `capsolver` | `capsolver` | 1.0.7 | MIT | NO | YES | YES | YES | YES (Akamai BMP) |
| `anticaptchaofficial` | `anticaptchaofficial` | unknown | MIT | NO | YES | partial | YES | NO |

**Choose `2captcha-python` because:**

1. `AsyncTwoCaptcha` is a first-class async class verified in the official GitHub README (v2.0.7,
   released May 2026). Drop it directly into `await` calls inside plugin coroutines — no
   `run_in_executor` wrapping needed.
2. Version 2.0.7 released May 29, 2026 — actively maintained; the latest release of any option.
3. MIT license, no usage restrictions for personal bots.
4. Covers the CAPTCHA types actually encountered on the 7 supported platforms: reCAPTCHA v2/v3
   (Amazon checkout), Cloudflare Turnstile (GameStop/NewEgg), Amazon WAF, GeeTest, DataDome.
5. hCaptcha appears in repo tags but is not in the official CAPTCHA type table — LOW confidence.
   For Walmart (PerimeterX/HUMAN) and Target (Akamai), automated CAPTCHA solving via any of
   these SDKs is not viable — the protection is behavioral/fingerprint-based, not a solvable
   CAPTCHA token. Keep the existing `detect_captcha() -> True` + `asyncio.Event` manual-pause
   pattern for those platforms.

**capsolver is NOT chosen:** PyPI package v1.0.7 was last released July 2023 (nearly 3 years
stale). No async API. The unofficial `python3-capsolver` fork (v1.2.0) adds aiohttp support but
has no official backing — too high a maintenance risk for a core feature.

**anticaptchaofficial is NOT chosen:** Sync-only; would require `run_in_executor` wrapping that
blocks the write-queue-drain pattern; PyPI page was unreachable during research.

**PerimeterX/HUMAN bypass services (RiskByPass, ScraperAPI) are explicitly out of scope:**
These cost $5-7 per 1,000 solves and are priced for commercial scraping operations, not a personal
bot that might hit one CAPTCHA per week.

### Stack addition for Feature 2

| Library | pip name | Version | License | Purpose |
|---------|----------|---------|---------|---------|
| 2captcha-python | `2captcha-python` | 2.0.7 | MIT | `AsyncTwoCaptcha` for in-plugin CAPTCHA token solving |

**Integration into plugin ABC:**

`detect_captcha()` already exists on `RetailerPlugin` as an async no-op. Extend the ABC with:
- A default `solve_captcha(url: str, sitekey: str, captcha_type: str) -> str | None` method that
  returns the solved token string or `None` if no API key is configured.
- The implementation instantiates `AsyncTwoCaptcha(api_key)` where `api_key` comes from
  `CredentialStore.get("captcha_api_key")` — never from config.yml or hardcoded.
- Plugins that encounter solvable CAPTCHAs (Amazon WAF, Turnstile) override `detect_captcha` to
  return True, then call `await self.solve_captcha(...)` and inject the token via `tab.evaluate`.
- Platforms with PerimeterX/HUMAN keep `detect_captcha` returning True but do NOT attempt
  solve — they emit the existing `asyncio.Event` to pause for manual intervention.

**Install:**
```bash
pip install "2captcha-python==2.0.7"
```

Add to `requirements.txt` or as an optional extra:
```toml
[project.optional-dependencies]
captcha = ["2captcha-python==2.0.7"]
```

### What NOT to add for Feature 2

| Avoid | Why |
|-------|-----|
| `capsolver` (pip) | Stale (July 2023), no async API |
| `python3-capsolver` | Unofficial fork, no official backing |
| `anticaptchaofficial` | Sync-only; wrapping adds complexity |
| RiskByPass / ScraperAPI subscriptions | $5-7/1k; commercial scale only |
| `2captcha-python-async` (separate package) | Superseded by `AsyncTwoCaptcha` in main package |

---

## Feature 3: Stronger Browser Fingerprint Resilience

### Decision: CDP `Emulation` overrides via nodriver's raw CDP API — no new library

**What nodriver already provides (do NOT duplicate — HIGH confidence):**

nodriver 0.50.3 achieved 0 hard blocks across 31 Cloudflare targets in an independent benchmark
(https://ianlpaterson.com/blog/anti-detect-browser-benchmark-patchright-nodriver-curl-cffi/).
No other tool tested scored better. This is the result of architectural decisions, not patches:
- `navigator.webdriver` is `false` by design — WebDriver wire protocol was never activated
- No `Runtime.enable` CDP call — eliminates the primary Playwright-era detection vector
- Connects via raw WebSocket CDP — indistinguishable from Chrome DevTools itself
- No init scripts — nothing patches anything, so patches themselves are not a detection signal

**What nodriver does NOT do (gaps to fill with ~30 lines of code):**

- Canvas fingerprint is identical across all runs (reported in issue #2153). Sites using
  canvas-based fingerprinting can link sessions.
- Timezone and locale default to the host system — if a proxy routes through a different country,
  timezone mismatch is a detection signal.
- WebGL renderer string is Chrome's real renderer — not spoofed.

**Fill these gaps using nodriver's exposed CDP modules (no new library):**

nodriver exposes the full CDP `Emulation` and `Page` domains. Implement `core/fingerprint.py`:

```python
# core/fingerprint.py — ~30 lines, no new deps
import nodriver.cdp.emulation as emulation
import nodriver.cdp.page as page

async def apply_emulation_overrides(tab, timezone_id: str, locale: str) -> None:
    await tab.send(emulation.set_timezone_override(timezone_id=timezone_id))
    await tab.send(emulation.set_locale_override(locale=locale))

CANVAS_NOISE_JS = """
(function() {
    const orig = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(...args) {
        const ctx = this.getContext('2d');
        if (ctx) {
            const d = ctx.getImageData(0, 0, 1, 1);
            d.data[0] ^= 1; ctx.putImageData(d, 0, 0);
        }
        return orig.apply(this, args);
    };
})();
"""

async def inject_canvas_noise(tab) -> None:
    await tab.send(page.add_script_to_evaluate_on_new_document(source=CANVAS_NOISE_JS))
```

Plugins call both functions inside `setup()` after the first tab is created. Timezone and locale
values come from the platform config section (optional; default: host values if not set).

**Why camoufox is NOT chosen:** Camoufox is Firefox-based. All 7 plugins are Chrome/nodriver.
Switching browsers requires a full rewrite of every plugin's DOM selectors and checkout flows.
In the same 31-target benchmark, camoufox scored 25/31 vs nodriver's 31/31 — nodriver is already
superior for the specific sites this bot targets.

**Why patchright is NOT chosen:** Patchright is Playwright-based — reintroduces the exact
protocol layer nodriver was adopted to eliminate. Its benchmark gains came from using system
Chrome 148 (not from patch quality); running system Chrome is already what nodriver does.

### Stack addition for Feature 3

| Library | pip name | Version | License | Purpose |
|---------|----------|---------|---------|---------|
| None — use nodriver CDP | — | — | — | Emulation.setTimezoneOverride, setLocaleOverride, Page.addScriptToEvaluateOnNewDocument |

### What NOT to add for Feature 3

| Avoid | Why |
|-------|-----|
| `camoufox` | Firefox only; requires full plugin rewrite; worse benchmark than nodriver |
| `patchright` | Reintroduces Playwright; reintroduces the detection vector nodriver eliminated |
| `playwright-stealth` | Playwright-only; broad patch surface is itself a fingerprint signal |
| `undetected-chromedriver` | The predecessor nodriver replaced; more detectable than nodriver |
| FlareSolverr | Docker sidecar; overkill for personal use |
| Any comprehensive JS injection framework | A 5-line canvas shim via raw CDP is simpler and less detectable than a full stealth plugin |

---

## Feature 4: Price Monitoring

### Decision: Per-plugin DOM parsing with shared `core/price.py` helper; price history as a new SQLite table

**Price parsing approach (HIGH confidence — no new library):**

Each plugin already navigates the product page in a live nodriver tab. The price is in the DOM.
Add `parse_price(tab) -> float | None` to the `RetailerPlugin` ABC with a default `return None`
(existing plugins require zero changes). Each plugin implements its own CSS selector because
retailer DOM structures differ (Amazon `.a-price-whole .a-price-fraction`, BestBuy
`.priceView-hero-price span`, etc.). A shared helper in `core/price.py` handles cleanup:

```python
import re

def clean_price(text: str | None) -> float | None:
    if not text:
        return None
    digits = re.sub(r"[^\d.]", "", text)
    try:
        return float(digits)
    except ValueError:
        return None
```

nodriver's `await tab.find()` and `await element.get_attribute("textContent")` retrieve the price
text — no additional parsing library needed.

**Price history storage (HIGH confidence — extends existing SQLite pattern):**

Add a `price_history` table using the same idempotent `PRAGMA table_info` + `ALTER TABLE` approach
already in `initialize_db()`:

```sql
CREATE TABLE IF NOT EXISTS price_history (
    id         INTEGER PRIMARY KEY,
    item_link  TEXT    NOT NULL,
    price      REAL    NOT NULL,
    checked_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ph_link_time ON price_history(item_link, checked_at);
```

Add `target_price REAL` as a nullable column on the `items` table (same idempotent ALTER pattern).

Extend `models.py` with `insert_price_sync(link, price, ts)` and
`get_price_history_sync(link, limit) -> list[tuple]` — consistent with the existing `_sync`
naming convention.

**Price-drop alert:** Enqueue a `("price_drop", link, price)` tuple through the existing write
queue drain. The orchestrator's `_dispatch_write` extension handles it by calling `dispatcher.notify()`
with `action="price_drop"`. Reuses the existing notification fan-out — no new notification channel.
The orchestrator calls `_check_price` alongside `_check_and_buy` in the per-plugin poll loop.

### Stack addition for Feature 4

| Library | pip name | Version | License | Purpose |
|---------|----------|---------|---------|---------|
| None — stdlib only | — | — | — | `re` for price cleanup; `sqlite3` already in use |

### What NOT to add for Feature 4

| Avoid | Why |
|-------|-----|
| `beautifulsoup4` / `lxml` | nodriver's DOM API suffices for a live rendered page; adding a parser for Chrome-rendered HTML is redundant |
| `httpx` / `aiohttp` for price fetching | Would bypass the authenticated browser session; prices behind login/AJAX require the live tab |
| `pandas` / `matplotlib` | Price history CSV export or charting is out of scope for a personal stock bot |
| `APScheduler` | The existing asyncio poll loop handles scheduling; a second scheduler adds complexity with no benefit |
| `SQLAlchemy` | The existing raw `sqlite3` pattern is simple and consistent; an ORM is over-engineering |

---

## Feature 5: Plugin Ecosystem Tooling (Wiki Registry)

### Decision: Pure Python script `tools/generate_wiki.py` — no new library, no new runtime dep

**Approach:**

The generator script runs in CI (not at bot runtime):
1. Imports each `plugins/shopbot_plugin_*.py` via `importlib` (same mechanism as `PluginRegistry`).
2. Reads three new class attributes from each plugin: `platform_name: str`,
   `anti_detection_difficulty: str` (one of `"low"/"medium"/"high"/"extreme"`), and
   `supported_actions: list[str]` (e.g. `["check_availability", "auto_buy"]`).
3. Generates `Plugin-Registry.md` using f-strings — a Markdown table with columns: Platform,
   Domains, Actions, Anti-Detection Difficulty, Maintainer.
4. Pushes to the wiki repo via `subprocess.run(["git", "commit", ...])` against a checked-out
   `<repo>.wiki.git` clone. The wiki repo is a separate bare git clone (standard GitHub wiki
   mechanism — clone `<repo>.wiki.git`, commit files, push).

This is a CI artifact script. Zero new pip dependencies. The `gh` CLI already present in CI
handles authentication. The wiki clone + push pattern is the standard GitHub wiki automation
approach (no dedicated API needed).

### Stack addition for Feature 5

| Library | pip name | Version | License | Purpose |
|---------|----------|---------|---------|---------|
| None — stdlib only | — | — | — | `importlib`, `pathlib`, `subprocess`, f-strings |

### What NOT to add for Feature 5

| Avoid | Why |
|-------|-----|
| `mkdocs` / `sphinx` | Full doc generators for a single Markdown table; extreme over-engineering |
| `jinja2` | f-strings are sufficient for one table; templating adds a dep for zero gain |
| `PyGithub` / `PyGitHub` | `subprocess git` against the wiki clone is simpler and needs no extra OAuth token scope |
| `markitdown` | Converts FROM other formats TO Markdown; the source is already Python metadata |

---

## v3.0 Consolidated Additions

### New runtime dependencies (one)

| Package | pip name | Version | License | Feature |
|---------|----------|---------|---------|---------|
| 2captcha-python | `2captcha-python` | 2.0.7 | MIT | CAPTCHA solving (AsyncTwoCaptcha) |

### New stdlib-only modules (internal, no pip)

| Module | Location | Feature |
|--------|----------|---------|
| `core/proxy.py` | ProxyRotator + auth extension builder | Proxy rotation |
| `core/fingerprint.py` | apply_emulation_overrides + inject_canvas_noise | Fingerprint resilience |
| `core/price.py` | clean_price() helper | Price parsing |
| `tools/generate_wiki.py` | CI script | Wiki registry generation |

### requirements.txt change

```
# Add:
2captcha-python==2.0.7

# Optional extra in pyproject.toml:
# [project.optional-dependencies]
# captcha = ["2captcha-python==2.0.7"]
```

### Existing dependencies — no version changes needed

| Package | Pinned | Status |
|---------|--------|--------|
| nodriver | 0.50.3 | Current (verified 2026-06-06) |
| cryptography | 44.0.2 | Current |
| keyring | 25.7.0 | Current |
| pydantic | 2.13.3 | Current |
| pygame | 2.6.1 | Current |

---

## v3.0 Alternatives Considered

| Category | Chosen | Rejected | Reason Rejected |
|----------|--------|----------|-----------------|
| Proxy management | DIY `itertools.cycle` | proxybroker, proxy-pool, scrapy-rotating-proxies | Unmaintained / wrong runtime / Redis dependency |
| CAPTCHA SDK | `2captcha-python` AsyncTwoCaptcha | `capsolver` (stale), `anticaptchaofficial` (sync) | No async; stale releases |
| Fingerprint resilience | nodriver CDP Emulation + script | camoufox, patchright | Firefox rewrite; re-introduces Playwright |
| Price parsing | nodriver DOM + stdlib `re` | beautifulsoup4, lxml, httpx | Redundant with live browser tab already open |
| Wiki generation | Pure Python + subprocess git | mkdocs, jinja2, PyGithub | Over-engineering for one Markdown table |
| PerimeterX/HUMAN bypass | Manual pause (existing pattern) | RiskByPass, ScraperAPI | $5-7/1k pricing; commercial scale only |

---

## v3.0 Sources

- nodriver PyPI (v0.50.3, verified 2026-06-06): https://pypi.org/project/nodriver/
- nodriver Browser class docs — proxy_server in create_context: https://ultrafunkamsterdam.github.io/nodriver/nodriver/classes/browser.html
- nodriver authenticated proxy demo: https://github.com/TufayelLUS/Python-nodriver-use-all-type-proxy
- 2captcha-python PyPI (v2.0.7, verified 2026-06-06): https://pypi.org/project/2captcha-python/
- 2captcha-python GitHub — AsyncTwoCaptcha confirmed: https://github.com/2captcha/2captcha-python
- capsolver PyPI (v1.0.7, last release July 2023): https://pypi.org/project/capsolver/
- Anti-detect browser benchmark 31 Cloudflare targets (nodriver 0 hard blocks, best result): https://ianlpaterson.com/blog/anti-detect-browser-benchmark-patchright-nodriver-curl-cffi/
- Camoufox vs nodriver 2026: https://www.proxies.sx/blog/ai-browser-automation-camoufox-nodriver-2026
- nodriver same fingerprint across runs (issue #2153): https://github.com/ultrafunkamsterdam/undetected-chromedriver/issues/2153
- Price tracker SQLite schema pattern: https://scrapfly.io/blog/posts/how-to-build-a-price-tracker-in-python
- GitHub wiki automation via git clone+push: https://therenegadecoder.com/code/how-to-automate-your-github-wiki/
- PerimeterX/HUMAN solving services comparison 2026: https://scrapingproxies.best/blog/tools/best-perimeterx-solvers/

---
*v3.0 stack additions researched: 2026-06-06*

---

---

# v4.0 Stack Additions — Win-the-Drop (Checkout Automation + Reliability)

**Researched:** 2026-06-10
**Confidence:** HIGH overall. nodriver API verified from source code. asyncio primitives verified
from Python 3.13 stdlib docs. CredentialStore reuse patterns confirmed from in-repo code.

**Verdict: Zero new runtime dependencies required for v4.0.**

Every v4.0 feature is achievable with the existing pinned stack. The analysis below maps each
feature to specific existing APIs and explains why no external library is needed.

---

## Acquisition Core Features

### Checkout Profile Form-Fill (shipping/billing)

**Mechanism:** nodriver `tab.select(selector)` + `element.send_keys(value)` sequences.
This is the exact pattern already used in `BestBuyPlugin.login()` and the existing checkout
flows — shipping/billing form-fill is structurally identical to credential field-fill.

**Profile storage:** A new `CheckoutProfile` Pydantic model (name, address1, address2, city,
state, zip, country, phone) added to `core/config_schema.py`. Values stored in `CredentialStore`
using new keys appended to `SECRET_KEYS`. Payment CVV already collected via `getpass` at runtime
and never persisted (existing PCI-safe pattern, unchanged).

**No new dep.** nodriver 0.50.3, Pydantic 2.13.3, and `core/credentials.py` cover this entirely.

---

### Order-Confirmation Detection

**Mechanism:** After the place-order click, poll for DOM confirmation signals (order number
element, URL transition to `/thank-you` or `/order-confirmation`, or page title containing
"Order" or "Thank You") using `tab.find()` or `tab.evaluate()`. Wrap the polling loop in
`asyncio.timeout(budget_secs)` as a hard deadline. The `purchased` flag in SQLite is only
written after a confirmation signal fires — not on button click.

**No new dep.** `asyncio.timeout` (stdlib, Python 3.11+, already used in `_solve_or_pause()`),
nodriver `tab.find()` / `tab.evaluate()`.

---

### Bounded Retry-on-Cart with Backoff

**Mechanism:** A `_retry_checkout(plugin, url, max_attempts, base_delay)` helper in
`core/orchestrator.py`. Inner loop:

```python
for attempt in range(max_attempts):
    if await loop.run_in_executor(None, get_item_purchased_sync, url):
        return True   # idempotency guard
    try:
        success = await plugin.auto_buy(url)
        if success:
            return True
    except Exception as exc:
        writeLog(f"checkout attempt {attempt+1} failed: {exc.__class__.__name__}", "WARNING")
    jitter = random.uniform(0, 1)
    await asyncio.sleep(base_delay * (2 ** attempt) + jitter)
return False
```

**No new dep.** `random` (stdlib), `asyncio.sleep` (stdlib). The idempotency guard reuses the
existing `get_item_purchased_sync` read path. `tenacity` and `backoff` are NOT used: the retry
semantics are domain-specific (max 3 attempts, bounded by a per-item checkout budget) and the
5-line manual loop is clearer than decorator indirection for a bounded case.

---

### Per-Step/Per-Item Checkout Time Budget

**Mechanism:** `asyncio.timeout(n)` context manager wrapping individual checkout steps within
plugin `auto_buy()` and wrapping `_check_and_buy()` in `run_plugin()`. Budget values from config:
`app.item_timeout_secs` (default 120) and `app.checkout_step_timeout_secs` (default 30). On
`asyncio.TimeoutError`, log the item URL and continue to the next item — do not raise into the
supervisor.

**No new dep.** `asyncio.timeout` is stdlib since Python 3.11.

---

### Monitor-Only Run Mode

**Mechanism:** A `--monitor-only` CLI flag sets `cfg.app.monitor_only = True`. In
`_try_auto_buy()` (orchestrator), guard:

```python
if getattr(cfg.app, "monitor_only", False):
    return
```

This closes the `test_mode` place-order hole: even if a plugin's `test_mode` check is missing,
the orchestrator never calls `auto_buy()` in monitor-only mode. The config flag is a Pydantic
`bool` field with `default=False`.

**No new dep.**

---

## Always-On Reliability Features

### Per-Coroutine Supervision + Backoff Restart

**Mechanism:** Replace the bare `tg.create_task(run_plugin(...))` in `async_main()` with a
supervisor wrapper:

```python
async def _supervise_plugin(plugin, write_queue, poll_interval, dispatcher, max_failures=5):
    attempt = 0
    while attempt < max_failures:
        try:
            await run_plugin(plugin, write_queue, poll_interval, dispatcher)
        except asyncio.CancelledError:
            raise   # propagate clean shutdown, never swallow
        except Exception as exc:
            writeLog(f"[{plugin.__class__.__name__}] crash #{attempt+1}: {exc}", "ERROR")
            attempt += 1
            await asyncio.sleep(min(2 ** attempt, 60))
    writeLog(f"[{plugin.__class__.__name__}] max_failures reached -- retiring", "ERROR")
```

The supervisor itself is what `TaskGroup` holds. A single plugin crash no longer propagates to
siblings via the `except*` unwinding path.

**No new dep.** Pure asyncio + stdlib math. `tenacity` is not used: the supervisor loop is
stateful (it needs to relaunch the browser, not just retry a function call), and a custom
supervisor gives cleaner control over the browser-crash relaunch sequence.

---

### Browser-Crash/Disconnect Detection + Relaunch

**Mechanism:** nodriver's `Browser.stopped` property checks `self._process.returncode is None`.
When `returncode is not None`, the process has exited. Add a crash check at the top of
`run_plugin()`'s inner loop:

```python
if plugin.driver and plugin.driver.stopped:
    raise RuntimeError(f"[{plugin.__class__.__name__}] browser process exited")
```

This raises into `_supervise_plugin`, which handles:
1. `await plugin.teardown()` — safe even if driver is None
2. Backoff sleep
3. `await plugin.setup()` — relaunches Chrome, re-applies stealth + proxy
4. Re-login via `await plugin.login()`
5. Restore session cookies from encrypted session store (see below)

`browser._process_pid` (int) is used in log messages only.

Re-applying stealth and proxy on relaunch reuses `apply_stealth()`, `build_proxy_browser_args()`,
and `setup_proxy_auth()` from the existing `core/stealth.py` — no new code.

**No new dep.** `browser.stopped` confirmed from nodriver source at `nodriver/core/browser.py`:
property returns `True` when `self._process.returncode is not None`.

---

### Encrypted Session/Cookie Persistence

**Mechanism:**

**Save path (called after successful login):**
1. `cookies = await plugin.driver.cookies.get_all()` — returns `List[cdp.network.Cookie]`
2. Serialize: `payload = json.dumps([c.to_json() for c in cookies]).encode()`
3. Encrypt using existing Fernet machinery (reuse `_derive_key` + `Fernet` from `core/credentials.py`)
4. Write ciphertext to `platformdirs.user_data_dir("shoppybot") / "sessions" / f"{platform_key}.bin"`

**Restore path (called after browser relaunch, before first navigation):**
1. Read and decrypt ciphertext using same key derivation
2. Deserialize: `cookie_params = [cdp.network.CookieParam(**c) for c in json.loads(plaintext)]`
3. Restore via raw CDP: `await plugin.driver.main_tab.send(cdp.storage.set_cookies(cookies=cookie_params))`

**Why raw CDP, not `browser.cookies.set_all()`:** `CookieJar.set_all()` has a confirmed bug
(nodriver Issues #1816, #2020) where the implementation calls `get_cookies` internally and
discards the argument. Using `cdp.storage.set_cookies()` directly bypasses the buggy wrapper.
`cdp.storage` is already imported transitively via `from nodriver import cdp` in `core/stealth.py`.

**Why not `browser.cookies.save()` / `browser.cookies.load()`:** These write and read a
plaintext file on disk. That violates the project's security posture (no plaintext secrets on
disk). Manual encryption via the existing `cryptography.fernet.Fernet` path maintains the same
security guarantee as `EncryptedFileBackend`.

**Passphrase:** Reuses `SHOPBOT_STORE_PASSPHRASE` from `_resolve_passphrase()` in
`core/credentials.py` — no new secrets to manage.

**New file:** `core/session_store.py` (~60 lines). No new pip deps.

**No new dep.** Reuses: `cryptography` (Fernet, already pinned), `json` (stdlib),
`platformdirs` (already pinned), `cdp.storage` (already importable from nodriver).

---

### DB Read-Path Error Isolation

**Mechanism:** In `run_plugin()`, wrap `get_items_sync` in explicit DB error guards:

```python
try:
    items = await loop.run_in_executor(None, get_items_sync)
except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
    writeLog(f"DB read failed, skipping poll cycle: {exc.__class__.__name__}", "ERROR")
    await asyncio.sleep(poll_interval)
    continue
```

Per-item errors in `_check_and_buy` already have broad `except Exception` guards. This change
closes the `get_items_sync` path which currently has no isolation.

**No new dep.** `sqlite3.OperationalError` and `sqlite3.DatabaseError` are stdlib.

---

### Per-Item Orchestrator Timeout

**Mechanism:** Wrap `_check_and_buy()` in `run_plugin()` with `asyncio.timeout`:

```python
async with asyncio.timeout(getattr(cfg.app, "item_timeout_secs", 120)):
    await _check_and_buy(plugin, name, link, auto_buy, write_queue, dispatcher=dispatcher)
```

On `asyncio.TimeoutError`, log the item URL and `continue` to the next item. The timeout is
configurable in `config.yml` as `app.item_timeout_secs`.

**No new dep.**

---

### Structured Health/Heartbeat Surface

**Mechanism:** A shared `HealthState` dataclass in `core/health.py`:

```python
from dataclasses import dataclass, field
import time

@dataclass
class HealthState:
    started_at: float = field(default_factory=time.monotonic)
    last_tick: float = field(default_factory=time.monotonic)
    plugin_states: dict[str, str] = field(default_factory=dict)
    errors_since_start: int = 0
```

Exposed two ways:
1. Orchestrator calls `health.last_tick = time.monotonic()` and updates `plugin_states` each
   poll cycle. `writeLog(f"[HEALTH] {health.summary()}", "DEBUG")` emits a parseable heartbeat.
2. FastAPI `/health` route (FastAPI already present as optional dep) returns `health.to_dict()`
   as JSON. No new web framework.

**No new dep.** `dataclasses` (stdlib), `time.monotonic()` (stdlib), FastAPI already present.

---

### SIGTERM/SIGINT Teardown Bridge (Opportunistic)

**Mechanism:** Cross-platform signal bridge in `async_main()`:

```python
import signal, sys

def _request_shutdown(loop, stop_event):
    loop.call_soon_threadsafe(stop_event.set)

stop_event = asyncio.Event()
loop = asyncio.get_running_loop()

if sys.platform != "win32":
    loop.add_signal_handler(signal.SIGTERM, _request_shutdown, loop, stop_event)
else:
    # Windows: add_signal_handler raises NotImplementedError; use signal.signal instead
    signal.signal(signal.SIGTERM, lambda *_: loop.call_soon_threadsafe(stop_event.set))
```

When `stop_event` fires, cancel the TaskGroup tasks; the existing `finally` block in
`async_main()` calls `registry.teardown_all()` to close Chrome processes before exit.

**No new dep.** `signal` (stdlib), `asyncio.Event` (stdlib). Note: on Windows, `signal.SIGTERM`
via `signal.signal()` is not guaranteed to fire from external process terminators; this is a
best-effort guard, not a hard guarantee.

---

### Headless pygame Import-Crash Guard (Opportunistic)

**Mechanism:** In `utils.py`, promote the existing ad-hoc import to a module-level flag:

```python
try:
    import pygame
    _pygame_available = True
except Exception:
    _pygame_available = False
```

All sound functions guard on `_pygame_available` before calling any `pygame` API. This prevents
`ImportError` on headless servers where `pygame` fails to find a display.

**No new dep.**

---

## v4.0 Consolidated Additions

### New runtime dependencies

**None.** Zero changes to `requirements.txt` or `pyproject.toml` for v4.0.

### New stdlib-only internal modules

| Module | Location | Purpose |
|--------|----------|---------|
| `core/session_store.py` | Encrypted cookie save/restore | Browser session persistence |
| `core/health.py` | `HealthState` dataclass + summary | Heartbeat surface |

### Config schema additions (Pydantic, no new dep)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `app.monitor_only` | `bool` | `False` | Monitor-only run mode |
| `app.item_timeout_secs` | `int` | `120` | Per-item orchestrator timeout |
| `app.checkout_step_timeout_secs` | `int` | `30` | Per-step checkout budget |
| `app.checkout_max_attempts` | `int` | `3` | Bounded retry-on-cart limit |
| `app.supervisor_max_failures` | `int` | `5` | Per-plugin supervisor failure cap |

### SECRET_KEYS additions (CredentialStore, no new dep)

New keys for checkout profile fields (appended to `SECRET_KEYS` list in `core/credentials.py`):
`CHECKOUT_NAME`, `CHECKOUT_ADDRESS1`, `CHECKOUT_ADDRESS2`, `CHECKOUT_CITY`, `CHECKOUT_STATE`,
`CHECKOUT_ZIP`, `CHECKOUT_COUNTRY`, `CHECKOUT_PHONE`.

---

## What NOT to Add for v4.0

| Proposed Dep | Why to Reject | Use Instead |
|---|---|---|
| `tenacity` or `backoff` | Bounded 3-attempt checkout retry is a 10-line loop; decorator-based retry obscures the stateful relaunch logic in the supervisor | `asyncio.sleep` + `while attempt < max_attempts` |
| `aiohttp` or `httpx` | No new HTTP calls introduced in v4.0; 2captcha HTTP is already `requests` in executor | `requests` in `run_in_executor` (existing) |
| `async-healthcheck` or `aio-tiny-healthcheck` | FastAPI already present for the web UI; adding a second HTTP server is redundant | FastAPI `/health` route + heartbeat log line |
| `structlog` | Introduces a second logging system alongside the existing `writeLog()` convention; migration cost, inconsistency risk | `writeLog()` with structured format strings |
| `APScheduler` | All scheduling is `asyncio.sleep` in the existing poll loop | `asyncio.sleep` + `_get_plugin_sleep()` |
| nodriver upgrade beyond 0.50.3 | `set_all` bug exists across multiple versions; upgrading risks breaking anti-detection; raw CDP workaround (`cdp.storage.set_cookies`) is version-stable | Pin at 0.50.3, use raw CDP for cookie restore |
| `cryptography` upgrade | 44.0.2 is current and covers all Fernet/scrypt needs for session encryption | No change needed |
| `pickle` for cookie serialization | Pickle is a binary execution vector; an encrypted pickle file is still a deserialization risk | `json.dumps` + `cdp.network.Cookie.to_json()` |

---

## Integration Points

| v4.0 Feature | Existing Hook | New Files/Changes |
|---|---|---|
| Checkout profile form-fill | Plugin `auto_buy()` override | `core/config_schema.py` (CheckoutProfile model), `SECRET_KEYS` additions |
| Order-confirmation detection | `auto_buy()` return contract | Plugin files only |
| Bounded retry-on-cart | `_try_auto_buy()` in orchestrator | `core/orchestrator.py` (`_retry_checkout` helper) |
| Per-step timeout | Plugin `auto_buy()` internals | Plugin files + `core/config_schema.py` |
| Monitor-only mode | `_try_auto_buy()` guard | `core/orchestrator.py`, `core/config_schema.py`, CLI |
| Supervisor + backoff | `tg.create_task` replacement | `core/orchestrator.py` (`_supervise_plugin`) |
| Browser crash + relaunch | `run_plugin()` crash check | `core/orchestrator.py`, `core/plugin_base.py` |
| Encrypted cookie persistence | Post-login save; post-relaunch restore | New `core/session_store.py` |
| DB read-path isolation | `run_plugin()` `get_items_sync` call | `core/orchestrator.py` |
| Per-item orchestrator timeout | `run_plugin()` inner loop | `core/orchestrator.py` |
| Health/heartbeat | Orchestrator poll cycle + FastAPI | New `core/health.py`; `web/routes.py` |
| SIGTERM bridge | `async_main()` startup | `core/orchestrator.py` |
| pygame import guard | `utils.py` | `utils.py` |

---

## nodriver API Reference for v4.0 (HIGH confidence — verified from source)

| API | Location | Notes |
|-----|----------|-------|
| `browser.stopped` | `nodriver/core/browser.py` | `True` when `self._process.returncode is not None` |
| `browser._process_pid` | `nodriver/core/browser.py` | int; set at launch; log-safe |
| `browser.cookies.get_all()` | `CookieJar` | Returns `List[cdp.network.Cookie]`; each has `.to_json()` |
| `browser.cookies.set_all()` | `CookieJar` | BUGGY — discards argument; do not use |
| `tab.send(cdp.storage.set_cookies(...))` | CDP direct | Correct cookie restore path; bypasses set_all bug |
| `browser.cookies.save(file)` | `CookieJar` | Writes plaintext — do not use; encrypt manually |
| `browser.cookies.load(file)` | `CookieJar` | Reads plaintext — do not use; decrypt manually |

---

## v4.0 Sources

- nodriver `Browser` class source, `stopped` property and `_process_pid`:
  https://github.com/ultrafunkamsterdam/nodriver/blob/main/nodriver/core/browser.py (verified 2026-06-10)
- nodriver `CookieJar.set_all()` bug (Issues #1816, #2020):
  https://github.com/ultrafunkamsterdam/undetected-chromedriver/issues/1816
  https://github.com/ultrafunkamsterdam/undetected-chromedriver/issues/2020
- Python 3.13 `asyncio.timeout` docs: https://docs.python.org/3.13/library/asyncio-task.html
- Python 3.13 `signal` module Windows limitations: https://docs.python.org/3/library/asyncio-eventloop.html
- `core/stealth.py` in-repo — `from nodriver import cdp` confirms `cdp.storage` importable (HIGH confidence)
- `core/credentials.py` in-repo — Fernet + scrypt path confirmed reusable (HIGH confidence)
- `core/orchestrator.py` in-repo — existing `asyncio.timeout(120)` usage confirms pattern (HIGH confidence)

---
*v4.0 stack additions researched: 2026-06-10*
