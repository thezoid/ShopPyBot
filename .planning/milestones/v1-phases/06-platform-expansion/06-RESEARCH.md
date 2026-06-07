# Phase 6: Platform Expansion - Research

**Researched:** 2026-06-03
**Domain:** Python async browser automation (nodriver 0.50.3), per-platform anti-detection config, Pydantic config schema extension
**Confidence:** MEDIUM (nodriver API: HIGH; selector specifics: LOW/unverifiable; anti-detection systems: MEDIUM)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Each plugin is a single self-contained `plugins/shopbot_plugin_<name>.py` subclassing RetailerPlugin v2, loaded by the registry with NO core edits (SC1).
- check_availability and auto_buy implemented with researched best-effort selectors, each carrying a `# TODO: verify selectors against live <site>` marker.
- auto_buy is implemented for Walmart, GameStop, Square Enix, NewEgg; Target checkout is labeled experimental.
- High-risk auto_buy paths log an explicit "experimental: may be blocked by <protection>" WARNING before attempting.
- Extend per-platform config (platforms.<name>) with: `min_delay`, `max_delay` (seconds), `headless` (bool), optional `user_agents` (list).
- ANTI-01 jitter: orchestrator sleeps `random.uniform(min_delay, max_delay)` between a plugin's poll cycles; falls back to shared poll_interval.
- ANTI-03 headless: each plugin's setup() reads its own `headless` flag and passes it to nodriver.
- ANTI-02 UA rotation: configurable list (global default pool + optional per-platform override); applied in setup().
- Secrets remain env-only; anti-detection settings are non-secret config.
- Each plugin docstring declares anti-detection risk level. Each new platform appends a row to SECURITY.md.

### Claude's Discretion

- Exact CSS/XPath selectors (best-effort, TODO-marked).
- UA pool contents.
- How jitter integrates with the existing poll loop (per-plugin override vs shared fallback).
- Per-platform config submodel field names.
- Whether headless/UA live on each PlatformConfig vs a shared sub-block.

### Deferred Ideas (OUT OF SCOPE)

- Making live auto-buy actually defeat PerimeterX/Akamai/CAPTCHA.
- Proxy rotation / browser fingerprint spoofing.
- Community per-platform config extensibility without core AppConfig edits.
- GitHub wiki plugin registry with difficulty ratings.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLG-04 | shopbot_plugin_walmart.py -- availability check + auto-buy; documented as high anti-detection risk (PerimeterX/HUMAN Security) | Domain confirmed: walmart.com; protection confirmed; selectors best-effort [ASSUMED] |
| PLG-05 | shopbot_plugin_target.py -- availability check; checkout labeled experimental (Akamai blocks headless consistently) | Domain confirmed: target.com; Akamai block confirmed MEDIUM; selectors [ASSUMED] |
| PLG-06 | shopbot_plugin_gamestop.py -- availability check + auto-buy; CAPTCHA on checkout documented | Domain: gamestop.com; CAPTCHA at checkout [ASSUMED]; selectors [ASSUMED] |
| PLG-07 | shopbot_plugin_squareenix.py -- availability check + auto-buy | Domain confirmed: na.store.square-enix-games.com; protection [ASSUMED] low-medium |
| PLG-08 | shopbot_plugin_newegg.py -- availability check + auto-buy | Domain: newegg.com; newegg.ca optional; protection [ASSUMED] medium |
| ANTI-01 | Per-platform random jitter: min_delay / max_delay in config; orchestrator reads at runtime | Verified integration point in orchestrator.run_plugin; pattern documented below |
| ANTI-02 | Rotating user agents from configurable list | nodriver CDP override verified from source; exact approach documented below |
| ANTI-03 | Headless toggle per platform | nodriver.start(headless=...) verified from source |
</phase_requirements>

---

## Summary

Phase 6 adds five new plugins and extends the config schema with three anti-detection knobs per platform. The work splits into two independent tracks: (1) five plugin files that are purely additive (no core changes, only drop-ins to `plugins/`), and (2) changes to `core/config_schema.py`, `core/orchestrator.py`, and plugin `setup()` methods to wire up jitter, headless, and UA rotation.

The nodriver API for headless and user-agent override is verified from the installed 0.50.3 source. Headless is a first-class parameter to `nodriver.start()` and to `nodriver.core.config.Config`. For user-agent: the CHOSEN approach (Pattern 4 Option A, which the plans implement) is to pass `browser_args=["--user-agent=<ua>"]` to `nodriver.start()` -- `--user-agent` is NOT in nodriver's blocked-argument list, so it passes through cleanly at launch. A CDP call (`cdp.network.set_user_agent_override`) issued from the tab context is a VALID alternative (Option B, mirroring nodriver's own internal `_prepare_headless` pattern) but is NOT used by these plans. See Pattern 4 below for both; Pattern 4 supersedes this summary line.

The five domain targets are well-established retail sites. Walmart uses PerimeterX/HUMAN Security (confirmed MEDIUM via multiple scraping-service docs). Target uses Akamai Bot Manager (confirmed MEDIUM). GameStop has checkout CAPTCHA (LOW-MEDIUM, widely reported). Square Enix NA store and NewEgg have lighter protections ([ASSUMED] LOW-MEDIUM). Selector-level details for all five are UNVERIFIABLE from this environment and must carry `# TODO: verify selectors against live <site>` markers throughout.

**Primary recommendation:** Implement both tracks in parallel. Config schema + orchestrator jitter first (pure Python, fully testable), then the five plugin scaffolds. Keep the `_prepare_headless` / CDP UA override self-contained in a shared helper or replicated clearly per plugin.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Plugin browser lifecycle | Plugin (setup/teardown) | -- | Each plugin owns its isolated nodriver Browser; established Phase 2 pattern |
| Jitter sleep | Orchestrator (run_plugin loop) | Plugin config | Poll interval logic belongs in orchestrator; plugin exposes config only |
| Headless flag | Plugin setup() reads config | Config schema holds value | Plugin passes flag to nodriver.start(); config schema owns the value |
| UA rotation | Plugin setup() reads config | Config schema holds list | UA applied per-session via CDP after browser start |
| Domain routing | Registry (urlparse match) | Plugin domain_patterns | Registry is the single routing authority |
| Anti-detection risk docs | Plugin docstring + SECURITY.md | -- | Two sources per CONTEXT.md SC4 requirement |
| Config schema extension | core/config_schema.py | -- | PlatformsConfig is the fixed model for first-party platforms |

---

## Standard Stack

### Core (no new packages required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| nodriver | 0.50.3 (installed) | Browser automation for all 5 new plugins | Already in use by Amazon/BestBuy plugins; no new dep |
| pydantic | (installed) | Config submodel for 5 new platform configs | Already in use by AppConfig/PlatformsConfig |
| random | stdlib | `random.uniform(min, max)` for jitter | No external dep needed |

No new packages are required for Phase 6. All capabilities are covered by the existing stack.

**Version verification:** No new packages; existing nodriver 0.50.3 and pydantic are already installed and in use. [VERIFIED: installed .venv source]

---

## Package Legitimacy Audit

> No new packages are installed in Phase 6. All five plugins and anti-detection wiring use the existing installed dependencies (nodriver 0.50.3, pydantic, Python stdlib).

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck not needed -- no new packages.*

---

## Architecture Patterns

### System Architecture Diagram

```
config.yml
  platforms.walmart.min_delay / max_delay / headless / user_agents
  platforms.target.*
  platforms.gamestop.*
  platforms.squareenix.*
  platforms.newegg.*
        |
        v
  AppConfig (config_schema.py)
  PlatformsConfig now has 5 new submodels
        |
        v
  Orchestrator (run_plugin loop)
  reads plugin.platform_cfg.min_delay / max_delay
  replaces fixed poll_interval sleep with:
      await asyncio.sleep(random.uniform(min_delay, max_delay))
  falls back to shared poll_interval if platform_cfg absent
        |
        v
  Plugin (setup())
  reads platform_cfg.headless -> nodriver.start(headless=bool)
  reads platform_cfg.user_agents -> selects 1 UA randomly
  sends CDP UA override on first tab
        |
        v
  Browser (nodriver.Browser per plugin)
  -> product page -> availability check -> auto_buy
        |
        v
  Write Queue -> SQLite (ASYNC-05 unchanged)
```

### Recommended Project Structure

No new directories needed. All additions:

```
plugins/
  shopbot_plugin_walmart.py      # new
  shopbot_plugin_target.py       # new
  shopbot_plugin_gamestop.py     # new
  shopbot_plugin_squareenix.py   # new
  shopbot_plugin_newegg.py       # new
core/
  config_schema.py               # extend PlatformsConfig with 5 new platform submodels
  orchestrator.py                # replace poll_interval sleep with per-plugin jitter
SECURITY.md                      # append 5 rows to the risk table
```

### Pattern 1: Config Schema Extension

**What:** Add five new `*PlatformConfig` submodels to `PlatformsConfig`. Each gets `min_delay`, `max_delay`, `headless`, and `user_agents`. Match the existing `AmazonPlatformConfig` pattern exactly.

**When to use:** Anytime a first-party platform is added. Community plugins still cannot do this (deferred per Phase 2/6 CONTEXT.md).

```python
# Source: core/config_schema.py (verified by reading the file)
# Existing pattern (verified):
class AmazonPlatformConfig(BaseModel):
    delay_seconds: float = 30.0
    delay_jitter: float = 10.0

# New pattern for Phase 6 (each of the 5 new platforms):
class WalmartPlatformConfig(BaseModel):
    min_delay: float = 8.0    # ANTI-01: jitter lower bound
    max_delay: float = 15.0   # ANTI-01: jitter upper bound
    headless: bool = True     # ANTI-03
    user_agents: list[str] = []  # ANTI-02: empty = use global default pool

class PlatformsConfig(BaseModel):
    amazon: AmazonPlatformConfig = AmazonPlatformConfig()
    bestbuy: BestBuyPlatformConfig = BestBuyPlatformConfig()
    walmart: WalmartPlatformConfig = WalmartPlatformConfig()
    target: TargetPlatformConfig = TargetPlatformConfig()
    gamestop: GameStopPlatformConfig = GameStopPlatformConfig()
    squareenix: SquareEnixPlatformConfig = SquareEnixPlatformConfig()
    newegg: NeweggPlatformConfig = NeweggPlatformConfig()
```

Note: Amazon and BestBuy existing config submodels use `delay_seconds`/`delay_jitter` (different field names from the Phase 6 `min_delay`/`max_delay` pattern). The new five platforms get the new field names as specified in CONTEXT.md. The planner may optionally harmonize the old Amazon/BestBuy fields, but it is NOT required -- scope it out unless explicitly needed.

### Pattern 2: Jitter Integration in Orchestrator

**What:** The `run_plugin` coroutine in `orchestrator.py` currently sleeps `poll_interval` (a flat float passed from `async_main`). Replace this with per-plugin jitter read from config, falling back to `poll_interval`.

**When to use:** Every plugin that has `min_delay`/`max_delay` defined in its platform config.

```python
# Source: core/orchestrator.py (verified by reading the file) + design for Phase 6
import random

async def run_plugin(plugin, write_queue, poll_interval, dispatcher=None) -> None:
    """Long-running poll coroutine for one plugin. Cancelled on shutdown."""
    loop = asyncio.get_running_loop()
    while True:
        items = await loop.run_in_executor(None, get_items_sync)
        for name, link, auto_buy, quantity, purchased in items:
            if purchased:
                continue
            if not any(p in (link or "") for p in plugin.domain_patterns):
                continue
            await _check_and_buy(plugin, name, link, auto_buy, write_queue, dispatcher=dispatcher)
        # ANTI-01: per-plugin jitter; fall back to shared poll_interval
        sleep_secs = _get_plugin_sleep(plugin, poll_interval)
        await asyncio.sleep(sleep_secs)


def _get_plugin_sleep(plugin, poll_interval: float) -> float:
    """Return random.uniform(min_delay, max_delay) if platform config has them.

    Falls back to poll_interval if the plugin's platform config is absent or
    does not define both fields (supports plugins without Phase-6 config).
    """
    try:
        platform_name = plugin.__class__.__name__.lower().replace("plugin", "")
        platform_cfg = getattr(plugin.config.platforms, platform_name, None)
        if platform_cfg and hasattr(platform_cfg, "min_delay") and hasattr(platform_cfg, "max_delay"):
            return random.uniform(platform_cfg.min_delay, platform_cfg.max_delay)
    except Exception:
        pass
    return poll_interval
```

Note on platform name derivation: `WalmartPlugin.__name__` is `"WalmartPlugin"`. The mapping to `platforms.walmart` requires lowercasing and stripping `"plugin"`. This is a minor naming contract -- the planner must document it as a convention, or alternatively pass the platform name as a class attribute (e.g. `platform_key = "walmart"`) which is cleaner and more explicit.

**Recommendation:** Give each plugin class a `platform_key: str` class attribute set to the config key name (e.g. `"walmart"`). Use that to look up `getattr(plugin.config.platforms, plugin.platform_key, None)`. This avoids fragile string munging and is consistent with how `domain_patterns` is already a class attribute. This is Claude's Discretion per CONTEXT.md.

### Pattern 3: nodriver Headless Launch

**What:** Pass `headless=True/False` to `nodriver.start()`. This is a first-class parameter.

**Verified from:** `.venv/Lib/site-packages/nodriver/core/util.py` (start function) and `nodriver/core/config.py` (Config.__call__ appends `--headless=new` when `headless=True`).

```python
# Source: nodriver/core/util.py start() and nodriver/core/config.py (VERIFIED: .venv source)
async def setup(self) -> None:
    headless = False  # default
    if self.config:
        platform_cfg = getattr(self.config.platforms, self.platform_key, None)
        if platform_cfg and hasattr(platform_cfg, "headless"):
            headless = platform_cfg.headless
    self.driver = await nodriver.start(headless=headless)
```

nodriver.Config's `__call__` appends `--headless=new` (the modern Chrome headless flag, not legacy `--headless`) when `headless=True`. [VERIFIED: .venv source]

Critical: `nodriver.Config.add_argument()` explicitly blocks any string containing "headless" from being passed via `add_argument` -- it raises ValueError. The `headless` parameter on `start()` / `Config.__init__()` is the only correct path. [VERIFIED: .venv source]

### Pattern 4: User-Agent Override via CDP

**What:** nodriver does not expose a `user_agent` parameter at the `start()` level. The correct approach is a CDP `Network.setUserAgentOverride` call, issued on the active tab after the browser is started.

**Verified from:** nodriver source:
- `nodriver/core/tab.py` `_prepare_headless()` uses `cdp.network.set_user_agent_override()` internally to strip "Headless" from the UA string. [VERIFIED: .venv source]
- `nodriver/cdp/network.py` `set_user_agent_override(user_agent: str, ...)` -- the CDP command. [VERIFIED: .venv source]
- `nodriver/core/config.py` `add_argument()` blocks any arg containing "headless", "data-dir", "no-sandbox", or "lang" from being added via `add_argument`. `user-agent` is NOT in the blocked list, meaning `--user-agent=...` CAN be passed via `browser_args`. [VERIFIED: .venv source]

Two valid approaches:

**Option A (browser_args -- simplest, sets UA at Chrome launch):**
```python
# Source: nodriver/core/config.py add_argument and Config.__init__ (VERIFIED)
# "--user-agent" is not blocked by add_argument; it can be passed in browser_args.
async def setup(self) -> None:
    ua = _select_ua(self.config, self.platform_key)
    browser_args = [f"--user-agent={ua}"] if ua else None
    headless = _get_headless(self.config, self.platform_key)
    self.driver = await nodriver.start(headless=headless, browser_args=browser_args)
```

**Option B (CDP per-tab override -- matches nodriver's own internal pattern):**
```python
# Source: nodriver/core/tab.py _prepare_headless (VERIFIED)
async def setup(self) -> None:
    headless = _get_headless(self.config, self.platform_key)
    self.driver = await nodriver.start(headless=headless)
    # Apply UA override on the main tab after browser start
    ua = _select_ua(self.config, self.platform_key)
    if ua:
        from nodriver import cdp
        await self.driver.main_tab.send(cdp.network.set_user_agent_override(user_agent=ua))
```

**Recommendation:** Option A (browser_args) is simpler and sets the UA at the process level. Option B requires a tab reference and a CDP send. Either works; Option A is preferred for simplicity. The planner should pick one and document it in each plugin's setup().

### Pattern 5: Plugin Structure for a New Platform

All five new plugins follow the exact same structure as Amazon/BestBuy. Template:

```python
"""<Platform> retailer plugin for ShopPyBot.

Anti-detection risk: <HIGH|MEDIUM|LOW>
Protection: <PerimeterX/HUMAN Security | Akamai Bot Manager | checkout CAPTCHA | unknown>
Reason: <one sentence>

Credentials sourced exclusively from environment variables (SEC-01):
    <PLATFORM>_EMAIL    -- account email
    <PLATFORM>_PASSWORD -- account password
"""

import os
import random
import nodriver

from core.plugin_base import RetailerPlugin
from logger import writeLog


class <Platform>Plugin(RetailerPlugin):
    """<Platform> platform plugin; owns one isolated nodriver Browser process.

    Anti-detection risk: <level> -- <reason> (PLG-0X).
    """

    domain_patterns = ["<hostname>"]
    platform_key = "<config_key>"   # matches config.platforms.<config_key>

    async def setup(self) -> None:
        headless = True
        ua_list: list[str] = []
        if self.config:
            platform_cfg = getattr(self.config.platforms, self.platform_key, None)
            if platform_cfg:
                headless = getattr(platform_cfg, "headless", True)
                ua_list = getattr(platform_cfg, "user_agents", [])

        # ANTI-02: rotate UA; fall back to no override if list is empty
        browser_args = None
        if ua_list:
            ua = random.choice(ua_list)
            browser_args = [f"--user-agent={ua}"]

        writeLog(
            f"experimental: {self.__class__.__name__} may be blocked by <protection>",
            "WARNING",
        )
        # ANTI-03: per-platform headless toggle
        self.driver = await nodriver.start(headless=headless, browser_args=browser_args)

    async def teardown(self) -> None:
        if self.driver:
            self.driver.stop()
            self.driver = None

    async def check_availability(self, url: str) -> bool:
        try:
            tab = await self.driver.get(url)
            # TODO: verify selectors against live <site>
            btn = await tab.select("<selector>", timeout=10)
            return btn is not None
        except Exception as exc:
            writeLog(f"Error checking <Platform> item: {exc}", "ERROR")
            return False

    async def auto_buy(self, url: str) -> bool:
        writeLog(
            "experimental: auto_buy on <Platform> may be blocked by <protection>",
            "WARNING",
        )
        try:
            # ... buy flow ...
            return True
        except Exception as exc:
            writeLog(f"Error during <Platform> auto-buy: {exc}", "ERROR")
            return False
```

### Anti-Patterns to Avoid

- **Calling `nodriver.start()` in `__init__`:** Raises `RuntimeError` (no running event loop at construction time). Always in `setup()`. [VERIFIED: existing plugin comments]
- **Using `Config.add_argument("--headless=...")`:** Raises `ValueError` -- blocked explicitly by nodriver. Use the `headless` parameter. [VERIFIED: .venv source]
- **Calling `update_item_purchased()` inside `auto_buy()`:** ASYNC-05 pattern requires `auto_buy` to return True and the orchestrator enqueues the write. Do NOT call `update_item_purchased` directly in a new plugin. (Note: `example_plugin.py` still shows the old direct-call pattern -- do not follow it for Phase 6.)
- **Deriving platform config key from class name at runtime:** Use an explicit `platform_key` class attribute instead.
- **Blocking `asyncio.sleep` with `time.sleep`:** The orchestrator is async; use `await asyncio.sleep(...)`.

---

## Platform Domains and Availability Indicators

### Walmart (PLG-04)

**Domain patterns:** `["walmart.com"]` [VERIFIED: canonical retail domain]
Note: walmart.ca is a separate Canadian subsidiary; omit unless scope widens.

**Anti-detection:** PerimeterX/HUMAN Security [MEDIUM confidence -- multiple scraping-service docs confirm this; HUMAN Security is the rebranded PerimeterX name post-2022]. [CITED: scrapingbee.com/blog/how-to-bypass-perimeterx-anti-bot-system/]

**Risk level:** HIGH. HUMAN Security (PerimeterX) scores 2,500+ behavioral signals per request; headless detection rate without spoofing is near-certain. Auto-buy will likely be blocked immediately. Availability check may survive briefly.

**Best-effort availability selectors (TODO: verify against live site):**
```python
# TODO: verify selectors against live walmart.com
# Reported "Add to Cart" button ID on Walmart product pages (ASSUMED):
add_to_cart = await tab.select('[data-testid="add-to-cart-btn"]', timeout=10)
# OR text-based fallback:
add_to_cart = await tab.find("Add to cart", timeout=5)
# Out-of-stock indicators (ASSUMED): "Out of stock", "Unavailable" text visible
```

**Credentials env vars:** `WALMART_EMAIL`, `WALMART_PASSWORD` [ASSUMED standard convention]

### Target (PLG-05)

**Domain patterns:** `["target.com"]` [VERIFIED: canonical retail domain]

**Anti-detection:** Akamai Bot Manager [MEDIUM confidence -- multiple bot-detection bypass docs cite Target/Akamai]. Akamai's headless detection rate with standard Chromium is ~80% per bypass-service docs. [CITED: scrapfly.io/blog/posts/how-to-bypass-akamai-anti-scraping]

**Risk level:** HIGH / experimental for checkout. Availability check in non-headless mode may succeed intermittently. Auto-buy should be labeled `experimental` in docstring.

**Best-effort availability selectors (TODO: verify against live site):**
```python
# TODO: verify selectors against live target.com
# Reported "Add to Cart" button on Target product pages (ASSUMED):
add_to_cart = await tab.select('[data-test="shipItButton"]', timeout=10)
# OR:
add_to_cart = await tab.select('[data-test="addToCartButton"]', timeout=10)
# Out-of-stock: "Sold out" or "Out of stock" text visible (ASSUMED)
```

**Credentials env vars:** `TARGET_EMAIL`, `TARGET_PASSWORD` [ASSUMED standard convention]

### GameStop (PLG-06)

**Domain patterns:** `["gamestop.com"]` [VERIFIED: canonical retail domain]
Optional: `"gamestop.ca"` for Canadian site.

**Anti-detection:** Checkout CAPTCHA documented by monitoring services; product page availability check has lower protection than Walmart/Target. [LOW-MEDIUM confidence, no major bot-detection vendor explicitly named for GameStop in research]

**Risk level:** MEDIUM. Page-load detection is lighter; CAPTCHA appears at checkout. Availability check likely functional; auto-buy blocked by CAPTCHA without solver.

**Best-effort availability selectors (TODO: verify against live site):**
```python
# TODO: verify selectors against live gamestop.com
# PageCrawl confirms GameStop uses "Add to Cart", "Pre-Order", "Sold Out",
# "Not Available", "Coming Soon" text states. (CITED: pagecrawl.io blog)
add_to_cart = await tab.select('[value="Add to Cart"]', timeout=10)
# OR:
add_to_cart = await tab.find("Add to Cart", timeout=5)
# Out-of-stock: find "Sold Out" or "Not Available" text (ASSUMED)
```

**Credentials env vars:** `GAMESTOP_EMAIL`, `GAMESTOP_PASSWORD` [ASSUMED standard convention]

### Square Enix (PLG-07)

**Domain patterns:** `["na.store.square-enix-games.com", "store.square-enix-games.com"]`

Domain confirmed: the NA store lives at `na.store.square-enix-games.com` (the subdomain prefix is `na.store`, NOT `store.na`). [MEDIUM confidence -- WebSearch result showed `https://na.store.square-enix-games.com/` as the official NA store URL; structure `na.store.*` is consistent with the APAC store at `apac.store.*`]

Note: The older `store.square-enix.com` (different domain, legacy) also exists but is separate infrastructure. Include `"store.square-enix-games.com"` as the broad match to cover both `na.` and potential other regional prefixes.

**Anti-detection:** No major bot protection vendor documented for Square Enix store. Likely basic Cloudflare or OEM protection. [ASSUMED LOW-MEDIUM]

**Risk level:** MEDIUM (best estimate). Store sells physical merchandise and game keys; lower-volume site than major retailers; bot detection likely less aggressive. [ASSUMED]

**Best-effort availability selectors (TODO: verify against live site):**
```python
# TODO: verify selectors against live na.store.square-enix-games.com
# Generic e-commerce patterns (ASSUMED -- no source for exact selectors):
add_to_cart = await tab.select('[name="add-to-cart"]', timeout=10)
# OR:
add_to_cart = await tab.find("Add to Cart", timeout=5)
# Out-of-stock: "Sold Out" or "Out of Stock" text (ASSUMED)
```

**Credentials env vars:** `SQUAREENIX_EMAIL`, `SQUAREENIX_PASSWORD` [ASSUMED standard convention]

### NewEgg (PLG-08)

**Domain patterns:** `["newegg.com", "newegg.ca"]` [newegg.com VERIFIED: canonical; newegg.ca VERIFIED: separate Canadian site per search results showing newegg.ca domain]

**Anti-detection:** No major bot vendor explicitly named for NewEgg in research. Likely Cloudflare or lightweight protection. [ASSUMED LOW-MEDIUM]

**Risk level:** MEDIUM (best estimate). Known for tech/PC parts; moderate bot activity around GPU drops historically. [ASSUMED]

**Best-effort availability selectors (TODO: verify against live site):**
```python
# TODO: verify selectors against live newegg.com
# NewEgg known "Add to Cart" button (ASSUMED -- no authoritative selector source):
add_to_cart = await tab.select(".btn-primary.btn-wide", timeout=10)
# OR:
add_to_cart = await tab.select('[itemprop="availability"]', timeout=10)
# Out-of-stock: "OUT OF STOCK" text or deactivated button (ASSUMED)
```

**Credentials env vars:** `NEWEGG_EMAIL`, `NEWEGG_PASSWORD` [ASSUMED standard convention]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Jitter sleep | Custom delay scheduler | `random.uniform(min, max)` in asyncio.sleep | Already sufficient; no external dep |
| Headless flag | Custom Chrome flag builder | `nodriver.start(headless=bool)` | Verified API; nodriver.Config handles `--headless=new` |
| UA string rotation | Custom UA file parser | `random.choice(ua_list)` from config list | Config-driven; no file I/O |
| CDP UA override | Browser subprocess env var tricks | `cdp.network.set_user_agent_override` or `--user-agent` in browser_args | nodriver's own internal pattern |
| Config submodel | Manual YAML parsing | Pydantic BaseModel (extend PlatformsConfig) | Established pattern in config_schema.py |

**Key insight:** All anti-detection v1 primitives (jitter, headless, UA) are 1-3 line changes using stdlib + verified nodriver API. The complexity is social/legal (anti-bot systems adapt), not technical.

---

## Common Pitfalls

### Pitfall 1: Wrong Square Enix domain pattern

**What goes wrong:** Using `"store.na.square-enix-games.com"` (reversed subdomain order) produces no domain_patterns match for actual URLs from `na.store.square-enix-games.com`.

**Why it happens:** The subdomain order is `na.store.*`, not `store.na.*`. Easy to invert.

**How to avoid:** Use `"store.square-enix-games.com"` as the broad match -- it covers `na.store.*`, `apac.store.*`, and similar regional prefixes via substring matching.

**Warning signs:** Registry routes URLs from na.store.* to None; `route()` returns None for a valid SE URL.

### Pitfall 2: add_argument() blocked keywords

**What goes wrong:** Calling `config.add_argument("--headless=new")` raises `ValueError` in nodriver.

**Why it happens:** `nodriver.core.config.Config.add_argument()` explicitly blocks any arg containing "headless". [VERIFIED: .venv source]

**How to avoid:** Pass `headless=True` to `nodriver.start()` directly. Never use `add_argument` for headless.

### Pitfall 3: Calling update_item_purchased() in auto_buy

**What goes wrong:** Direct call violates ASYNC-05; creates a concurrent write race if multiple plugins buy simultaneously.

**Why it happens:** `example_plugin.py` template still shows the old direct-call pattern (pre-Phase-4 code).

**How to avoid:** Return `True` from `auto_buy`; the orchestrator's write queue handles the DB write. Follow Amazon/BestBuy plugin pattern, not example_plugin.py.

### Pitfall 4: platform_key mismatch with config attribute name

**What goes wrong:** Plugin `platform_key = "squareenix"` but config field is `platforms.square_enix` (underscore) or `"squareEnix"` (camelCase) -- `getattr()` returns None silently; jitter and headless fall back to defaults.

**Why it happens:** Python attribute names can't contain hyphens and PEP 8 prefers underscores; YAML keys are flexible. Pydantic normalizes them.

**How to avoid:** Keep the platform config attribute name and `platform_key` identical. Use no underscores in the class attribute name (e.g. `platform_key = "squareenix"` matching `platforms.squareenix`). Document this convention in the config submodel comment.

### Pitfall 5: Amazon/BestBuy config submodels don't have min_delay/max_delay

**What goes wrong:** `_get_plugin_sleep` checks `hasattr(platform_cfg, "min_delay")` -- Amazon/BestBuy return False; they fall back to poll_interval correctly. But if someone sets `platforms.amazon.min_delay` in YAML it is silently ignored because `AmazonPlatformConfig` has no such field and Pydantic has `extra="ignore"` at the AppConfig level.

**Why it happens:** Old and new platform config shapes differ. AppConfig has `extra="ignore"` (line 129, verified).

**How to avoid:** Acceptable: Amazon/BestBuy keep old fields; five new platforms get new fields. The planner should NOT harmonize old fields in Phase 6 (scope creep). Document the difference in a comment.

### Pitfall 6: nodriver.start() in __init__ (re-statement of existing known pitfall)

**What goes wrong:** RuntimeError -- no running event loop at `__init__` time.

**How to avoid:** Always in `async def setup(self)`. [VERIFIED: established project pattern]

---

## Code Examples

### Full setup() with all three anti-detection features wired

```python
# Source: nodriver/core/util.py (start signature) + nodriver/core/config.py
# (browser_args, headless param) VERIFIED from .venv source
import random
import nodriver

async def setup(self) -> None:
    headless = True
    ua_list: list[str] = []

    if self.config:
        platform_cfg = getattr(self.config.platforms, self.platform_key, None)
        if platform_cfg is not None:
            headless = getattr(platform_cfg, "headless", True)
            ua_list = getattr(platform_cfg, "user_agents", [])

    # ANTI-02: build --user-agent arg if list non-empty
    browser_args: list[str] | None = None
    if ua_list:
        ua = random.choice(ua_list)
        browser_args = [f"--user-agent={ua}"]

    # ANTI-03: headless toggle; nodriver.Config appends --headless=new when True
    self.driver = await nodriver.start(headless=headless, browser_args=browser_args)
```

### Orchestrator jitter helper

```python
# Extends core/orchestrator.py run_plugin (verified from file read)
import random

def _get_plugin_sleep(plugin, poll_interval: float) -> float:
    """Return jitter sleep duration for this plugin, or poll_interval as fallback."""
    try:
        platform_cfg = getattr(
            plugin.config.platforms, getattr(plugin, "platform_key", ""), None
        )
        if platform_cfg and hasattr(platform_cfg, "min_delay") and hasattr(platform_cfg, "max_delay"):
            return random.uniform(platform_cfg.min_delay, platform_cfg.max_delay)
    except Exception:
        pass
    return poll_interval

# In run_plugin, replace:
#   await asyncio.sleep(poll_interval)
# with:
#   await asyncio.sleep(_get_plugin_sleep(plugin, poll_interval))
```

### Default UA pool (suggested starting point)

```python
# Suggested global default UA pool (ASSUMED appropriate -- real UAs from late 2024/2025 Chrome)
# Place in config_schema.py as a module-level constant or as AppSettingsConfig field
_DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]
# A plugin uses its platform_cfg.user_agents if non-empty, else _DEFAULT_USER_AGENTS.
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `--headless` (legacy) | `--headless=new` (Chrome 112+) | Chrome 112, 2023 | Legacy `--headless` is deprecated; nodriver.Config uses `--headless=new` automatically when headless=True |
| PerimeterX | HUMAN Security (Bot Defender) | ~2022 rebrand | Same technology; docs must use "PerimeterX/HUMAN Security" per SC4 requirement |
| store.na.square-enix-games.com (speculated older path) | na.store.square-enix-games.com (confirmed current) | unknown | Domain pattern must match actual URL structure |

**Deprecated/outdated:**

- Legacy `--headless` Chrome flag: replaced by `--headless=new` in Chrome 112+. nodriver handles this automatically.
- `example_plugin.py` direct `update_item_purchased()` call in auto_buy: superseded by ASYNC-05 write queue. New plugins MUST NOT replicate that pattern.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Walmart's protection is correctly called "PerimeterX/HUMAN Security" (not just Akamai or Cloudflare) | Platform Domains -- Walmart | SC4 phrase check fails; docstring/SECURITY.md uses wrong vendor name |
| A2 | GameStop CAPTCHA is at checkout only; product page availability check has lighter protection | Platform Domains -- GameStop | Risk level may be higher than MEDIUM; plugin may be blocked even for availability checks |
| A3 | Square Enix NA store has no named major bot-protection vendor (LOW-MEDIUM risk) | Platform Domains -- Square Enix | Could be Cloudflare or Akamai-protected; risk level wrong |
| A4 | NewEgg protection is LOW-MEDIUM (no named vendor confirmed) | Platform Domains -- NewEgg | Could be Akamai-protected; risk level wrong |
| A5 | All five sets of CSS selectors (add-to-cart, out-of-stock indicators) | Platform Domains (all) | Selectors wrong; availability check always returns False or raises; TODO markers present |
| A6 | Credential env var naming convention (e.g. WALMART_EMAIL, WALMART_PASSWORD) | Platform Domains (all) | Wrong env var names; login() silently skips; TODO markers and .env.example update needed |
| A7 | `--user-agent=` in `browser_args` is not blocked by nodriver's `add_argument` filter | Pattern 4 -- Option A | "user-agent" is not in the blocked list (verified: "headless", "data-dir", "data_dir", "no-sandbox", "no_sandbox", "lang"); but passing via `browser_args` constructor bypasses `add_argument` entirely anyway |
| A8 | Default UA strings are plausible for mid-2025 Chrome releases | Code Examples -- UA pool | UAs too old could be flagged by bot detection; list is non-secret and easily updated |

---

## Open Questions (RESOLVED)

> RESOLVED: (1) Do NOT harmonize Amazon/BestBuy delay fields to min/max this phase (out of scope). (2) Global default UA pool constant lives at config_schema.py module level (DEFAULT_USER_AGENTS). (3) Config attr name is `squareenix` (no underscore). (4) UA override uses browser_args (Pattern 4 Option A), not the CDP call. (5) SC3 explicitly names amazon.headless, so AmazonPlatformConfig AND BestBuyPlatformConfig also gain a headless flag and their plugins read it (added in the revised plan).

1. **platform_key naming convention for `squareenix`**
   - What we know: Python attribute `platforms.squareenix` works as a single-word key.
   - What's unclear: Users writing YAML may expect `square_enix` (with underscore). Pydantic BaseModel uses Python attribute names as YAML keys.
   - Recommendation: Use `squareenix` (no underscore) consistently in both the BaseModel field name and `platform_key` class attribute. Add a comment in `config.yml` sample showing the key.

2. **Amazon/BestBuy config harmonization**
   - What we know: Existing submodels use `delay_seconds`/`delay_jitter` (different from new `min_delay`/`max_delay`).
   - What's unclear: Should Phase 6 harmonize all seven platforms to the new field names?
   - Recommendation: No -- out of Phase 6 scope. Add a comment in config_schema.py noting the naming difference. A future cleanup phase can harmonize.

3. **Global default UA pool location**
   - What we know: A platform's `user_agents: []` (empty) means "use default". Where does the default live?
   - Recommendation: Module-level constant `_DEFAULT_USER_AGENTS` in `config_schema.py` (or in a new `core/anti_detection.py` helper, but that's over-engineering). Plugin setup() checks `platform_cfg.user_agents or _DEFAULT_USER_AGENTS`.

4. **`newegg.ca` in domain_patterns**
   - What we know: newegg.ca is a real Canadian retail site.
   - What's unclear: Whether the operator's item links will ever be .ca URLs.
   - Recommendation: Include it. Substring match `"newegg.com"` already matches `www.newegg.com`; add `"newegg.ca"` for CA coverage. No cost.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| nodriver | All 5 new plugins (setup, teardown) | yes | 0.50.3 | -- |
| pydantic | Config schema extension | yes | (installed) | -- |
| Chrome/Chromium | nodriver browser launch | yes (assumed -- already used by Amazon/BestBuy) | -- | -- |

**Missing dependencies with no fallback:** none

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (pyproject.toml, installed) |
| Config file | pyproject.toml |
| Quick run command | `pytest tests/ -q -x` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLG-04 | WalmartPlugin satisfies ABC; domain_patterns match walmart.com; docstring contains "PerimeterX/HUMAN Security" | unit | `pytest tests/test_plugin_walmart.py -x` | No -- Wave 0 |
| PLG-05 | TargetPlugin satisfies ABC; domain_patterns match target.com; docstring contains "Akamai" and "headless" | unit | `pytest tests/test_plugin_target.py -x` | No -- Wave 0 |
| PLG-06 | GameStopPlugin satisfies ABC; domain_patterns match gamestop.com; docstring contains "CAPTCHA" | unit | `pytest tests/test_plugin_gamestop.py -x` | No -- Wave 0 |
| PLG-07 | SquareEnixPlugin satisfies ABC; domain_patterns match na.store.square-enix-games.com | unit | `pytest tests/test_plugin_squareenix.py -x` | No -- Wave 0 |
| PLG-08 | NeweggPlugin satisfies ABC; domain_patterns match newegg.com | unit | `pytest tests/test_plugin_newegg.py -x` | No -- Wave 0 |
| SC1 | Registry loads all 5 new plugins from plugins/ dir without core changes | unit | `pytest tests/test_registry.py -x` (extend existing) | Yes -- extend |
| ANTI-01 | `_get_plugin_sleep` returns value in [min_delay, max_delay] when platform config present; returns poll_interval otherwise | unit | `pytest tests/test_orchestrator_jitter.py -x` | No -- Wave 0 |
| ANTI-02 | `setup()` passes `--user-agent=<selected>` in browser_args when user_agents list non-empty | unit (mock nodriver.start) | `pytest tests/test_plugin_walmart.py::test_setup_ua_rotation -x` | No -- Wave 0 |
| ANTI-03 | `setup()` passes `headless=True` when config.platforms.walmart.headless=True; False otherwise | unit (mock nodriver.start) | `pytest tests/test_plugin_walmart.py::test_setup_headless -x` | No -- Wave 0 |
| SC4 | WalmartPlugin docstring contains "PerimeterX/HUMAN Security"; TargetPlugin docstring contains "Akamai" | unit (inspect.getdoc) | `pytest tests/test_plugin_walmart.py::test_risk_docstring -x` | No -- Wave 0 |
| SECURITY.md rows | SECURITY.md contains rows for all 5 new platforms | unit (file text check) | `pytest tests/test_security_md.py -x` | No -- Wave 0 |
| Live availability/auto_buy | Actual availability detection and purchase on live sites | manual | n/a | n/a -- NOT a success criterion |

### Sampling Rate

- Per task commit: `pytest tests/ -q -x`
- Per wave merge: `pytest tests/ -q`
- Phase gate: Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_plugin_walmart.py` -- covers PLG-04, ANTI-02, ANTI-03, SC4 for Walmart; mirrors `tests/test_plugin_amazon.py` structure
- [ ] `tests/test_plugin_target.py` -- covers PLG-05, SC4 for Target
- [ ] `tests/test_plugin_gamestop.py` -- covers PLG-06, SC4 for GameStop
- [ ] `tests/test_plugin_squareenix.py` -- covers PLG-07
- [ ] `tests/test_plugin_newegg.py` -- covers PLG-08
- [ ] `tests/test_orchestrator_jitter.py` -- covers ANTI-01; tests `_get_plugin_sleep` with mock plugin configs
- [ ] `tests/test_security_md.py` -- covers SC4 SECURITY.md row presence; reads SECURITY.md and asserts 5 new platform rows exist
- [ ] Extend `tests/test_registry.py` or `tests/test_config_schema.py` for SC1 and new PlatformsConfig fields

---

## Security Domain

### Threat and Dual-Use Note

Anti-detection features in this phase (jitter, UA rotation, headless toggle) are standard browser automation best practices and are documented here honestly:

- These features do not defeat PerimeterX/HUMAN Security, Akamai Bot Manager, or CAPTCHA systems. They reduce detection signal at the margins.
- The intent is personal, non-commercial use per the repo's existing SECURITY.md and README disclaimer.
- Docs must be honest about risk rather than presenting the bot as capable of defeating protections it cannot defeat.
- No credentials are logged at any level. UA strings are non-secret config.
- The risk table in SECURITY.md is the source of truth for per-platform TOS/legal risk.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (per-platform login) | env vars only; no hardcoded creds (SEC-01, established) |
| V3 Session Management | no | bot sessions are ephemeral; no session persistence |
| V4 Access Control | no | single-user personal tool |
| V5 Input Validation | yes (config values) | Pydantic model validation; `min_delay`/`max_delay` should be `Field(ge=0)` |
| V6 Cryptography | no | no cryptographic operations in this phase |

**Field validation recommendation:** Add `Field(ge=0.0)` to `min_delay` and `max_delay` in the new platform config submodels to prevent negative sleep values. Add `Field(default_factory=list)` for `user_agents`. This is a 2-line addition per submodel.

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential leak via logging | Information Disclosure | Never log env var values; established SEC-01 pattern |
| Config injection via YAML (malformed delay values) | Tampering | Pydantic validation with `ge=0` guards |
| Plugin loading arbitrary code from plugins/ dir | Elevation of Privilege | Pre-existing SECURITY.md / PLUGIN_DEV.md guidance; not new to Phase 6 |

---

## Sources

### Primary (HIGH confidence)

- `.venv/Lib/site-packages/nodriver/core/config.py` -- Config.__init__ headless param, add_argument blocked keys, `__call__` appends `--headless=new` [VERIFIED: file read]
- `.venv/Lib/site-packages/nodriver/core/util.py` -- `start()` function signature [VERIFIED: file read]
- `.venv/Lib/site-packages/nodriver/core/tab.py` -- `_prepare_headless` using `cdp.network.set_user_agent_override` [VERIFIED: file read]
- `.venv/Lib/site-packages/nodriver/cdp/network.py` -- `set_user_agent_override` signature [VERIFIED: file read]
- `core/orchestrator.py` -- `run_plugin` loop structure, `poll_interval` sleep location [VERIFIED: file read]
- `core/config_schema.py` -- PlatformsConfig, AmazonPlatformConfig, BestBuyPlatformConfig patterns [VERIFIED: file read]
- `plugins/shopbot_plugin_amazon.py`, `plugins/shopbot_plugin_bestbuy.py` -- established plugin structure [VERIFIED: file read]
- `.planning/phases/06-platform-expansion/06-CONTEXT.md` -- locked decisions [VERIFIED: file read]

### Secondary (MEDIUM confidence)

- WebSearch result: na.store.square-enix-games.com confirmed as NA store hostname [CITED: search result showing official store URL]
- WebSearch result: Walmart + PerimeterX/HUMAN Security [CITED: scrapingbee.com/blog/how-to-bypass-perimeterx-anti-bot-system/]
- WebSearch result: Target + Akamai Bot Manager [CITED: scrapfly.io/blog/posts/how-to-bypass-akamai-anti-scraping]
- WebSearch result: GameStop availability text states ("Add to Cart", "Sold Out", etc.) [CITED: pagecrawl.io/blog/gamestop-in-stock-alerts-restock-notifications]
- newegg.ca domain confirmed via WebSearch [CITED: newegg.ca search results]

### Tertiary (LOW confidence / ASSUMED)

- All CSS/XPath selectors for the five new platforms -- cannot be verified without live access
- GameStop specific bot-protection vendor (unnamed)
- Square Enix and NewEgg bot-protection vendor and risk level
- Credential env var naming conventions for the five new platforms
- Default UA string list (Chrome/Firefox version numbers appropriate for mid-2025)

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH -- no new packages; all existing
- nodriver headless/UA API: HIGH -- verified from installed source
- Architecture / jitter integration: HIGH -- orchestrator code read directly
- Selector specifics: LOW -- unverifiable without live access; all TODO-marked
- Anti-detection vendor claims (Walmart, Target): MEDIUM -- corroborated by multiple scraping-service docs
- Anti-detection vendor claims (GameStop, SqEnix, NewEgg): LOW -- insufficient authoritative sources

**Research date:** 2026-06-03
**Valid until:** 2026-07-03 (nodriver API stable; retail site selectors stale immediately and require live verification regardless)
