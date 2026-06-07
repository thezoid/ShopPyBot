# Architecture Patterns

**Domain:** Python shopping bot — plugin framework + async browser automation
**Researched:** 2026-06-06 (v3.0 integration analysis, supersedes prior v1 research)
**Confidence:** HIGH (existing codebase fully read; all integration points derived from source)

---

## v3.0 Scope

Three feature clusters need to integrate with the shipped v2.0 architecture:

1. **Anti-detection hardening** — proxy rotation, CAPTCHA-solving service, fingerprint resilience
2. **Plugin ecosystem** — GitHub wiki registry generated from plugin metadata
3. **Price monitoring** — per-item target price, price history, price-drop alerts

The analysis below covers each cluster: what touches the existing system, what is new, and a
dependency-ordered build sequence.

---

## Existing Architecture (v2.0 Baseline)

```
BotService (core/service.py)
  └─ async_main (core/orchestrator.py)
       ├─ PluginRegistry (core/registry.py)
       │    └─ RetailerPlugin ABC (core/plugin_base.py)
       │         └─ plugins/shopbot_plugin_*.py  (7 concrete plugins)
       ├─ write_queue drain  →  models.py (SQLite WAL CRUD)
       └─ NotificationDispatcher (notifications/dispatcher.py)
            └─ Notifier ABC (notifications/base.py)
                 ├─ SoundNotifier
                 ├─ DiscordNotifier
                 ├─ EmailNotifier
                 └─ SmsNotifier

core/config_schema.py   — Pydantic AppConfig + per-platform submodels
core/credentials.py     — CredentialStore (get/set/list/delete), SECRET_KEYS list
core/paths.py           — per-OS data/config/log dirs
```

Key facts that constrain integration:

- `RetailerPlugin.setup()` is where each plugin creates its `nodriver` browser. That is the
  correct hook point for proxy/fingerprint configuration because the browser args are set
  exactly once, before any navigation.
- `CredentialStore.SECRET_KEYS` is the authoritative list of all secrets the system knows
  about. New secrets (CAPTCHA API keys, proxy credentials) must be added here.
- `models.py` items table has: `id, name, link, auto_buy, quantity, purchased,
  last_seen_available, last_notified`. Price columns do not exist yet.
- `NotificationEvent` carries `item_name, item_url, platform, timestamp, action`. Price-drop
  alerts need a new action value and optionally a price payload.
- The orchestrator write queue handles typed tuples `("purchased"|"set_available"|"clear_available", ...)`.
  Price writes need a new tag.
- `AppConfig.platforms.*` has per-platform submodels. Proxy and CAPTCHA solver config
  belong there (per-platform opt-in) alongside a global fallback.

---

## Cluster 1: Anti-Detection Hardening

### 1a. Where Proxy/CAPTCHA/Fingerprint Hooks Live

**Decision: shared `BrowserFactory` callable, injected into `RetailerPlugin.setup()`.**

Each plugin currently calls `nodriver.start(headless=headless)` in its own `setup()`.
Across 7 plugins that is 7 identical copies of browser-launch logic. If proxy config,
fingerprint args, or CAPTCHA extension paths must be wired into the browser, every plugin
is modified separately — which defeats the plugin framework's goal.

The correct approach is a `core/browser_factory.py` module that encapsulates all
anti-detection browser launch concerns and is called by the ABC's default `setup()`.

```
core/browser_factory.py   (NEW)
  build_browser(platform_cfg, global_cfg) -> nodriver.Browser
    - reads proxy from platform_cfg.proxy (or global_cfg.proxy as fallback)
    - reads fingerprint seed from platform_cfg or global_cfg
    - loads CAPTCHA solver extension if configured
    - calls nodriver.start(...) with assembled args
    - returns browser instance
```

`RetailerPlugin.setup()` in `core/plugin_base.py` becomes a concrete default that calls
`build_browser(...)`. Plugins that need custom setup override it and call `super().setup()`
or call `build_browser()` directly.

**Backward compat:** The ABC's `setup()` is currently `async def setup(self) -> None: ...`
(a no-op ellipsis). Making it a concrete default that calls `build_browser()` is
backward-compatible: existing plugins that override `setup()` completely are unaffected;
existing plugins that call `await self.driver = nodriver.start(...)` directly keep working
until they are updated to delegate to `build_browser()`. The migration can be done
plugin-by-plugin. Zero forced rewrites at integration time.

### 1b. Config Schema for Proxy and Fingerprint

Per-platform proxy opt-in with a global fallback follows the existing pattern for
`user_agents` and `headless`. Add to each `*PlatformConfig` in `core/config_schema.py`:

```python
class BasePlatformConfig(BaseModel):      # NEW shared base, extract from existing duplication
    min_delay: float = Field(default=5.0, ge=0.0)
    max_delay: float = Field(default=15.0, ge=0.0)
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)
    proxy: str = ""            # NEW: "http://host:port" or "" = disabled
    fingerprint_seed: int = 0  # NEW: 0 = random per session
    captcha_solver: str = ""   # NEW: "" | "2captcha" | "capsolver" | "manual"
```

All 7 platform submodels currently duplicate `min_delay/max_delay/headless/user_agents`.
Consolidating into `BasePlatformConfig` reduces schema duplication. This is a refactor
contained entirely within `config_schema.py` and is backward-compatible (field names unchanged).

A global anti-detection config block handles defaults:

```python
class AntiDetectionConfig(BaseModel):   # NEW
    proxy: str = ""                     # global fallback when per-platform proxy is ""
    fingerprint_seed: int = 0
    captcha_solver: str = ""            # global default solver
    captcha_timeout: int = 120          # seconds to wait for CAPTCHA solve
```

`AppConfig` gains `anti_detection: AntiDetectionConfig = AntiDetectionConfig()`.

**Config resolution in `browser_factory.py`:** per-platform value takes precedence over
global when non-empty/non-zero.

### 1c. CAPTCHA Secrets Through CredentialStore

`core/credentials.py` SECRET_KEYS list must be extended:

```python
# ADD to SECRET_KEYS:
"TWOCAPTCHA_API_KEY",    # 2captcha service
"CAPSOLVER_API_KEY",     # capsolver.com service
"PROXY_USERNAME",        # authenticated proxy credential
"PROXY_PASSWORD",
```

The CAPTCHA solver integration in `browser_factory.py` calls `get_store().get("TWOCAPTCHA_API_KEY")`
(or whichever solver is configured). Keys never appear in config.yml. The `shoppybot setup`
interactive flow and web UI credential routes already handle arbitrary SECRET_KEYS entries,
so adding 4 new keys requires only updating the SECRET_KEYS list — the store, CLI, and web
UI pick them up automatically.

### 1d. CAPTCHA Solve Flow

The existing pattern (amazon plugin's `_wait_user_action` with `asyncio.Event`) handles
manual CAPTCHA already. Automated solving adds a middle path:

```
detect_captcha() returns True
  -> captcha_solver configured?
       YES: call solver API, wait for solution token (up to captcha_timeout)
            inject solution into page
            if inject fails: fall back to manual event flow
       NO:  existing manual asyncio.Event flow (unchanged)
```

This lives in a new `core/captcha.py` helper that plugins call. The `detect_captcha()`
ABC method signature does not change — it remains `async def detect_captcha(self) -> bool`.
A new `async def solve_captcha(self, tab) -> bool` method is added to the ABC as a
concrete (non-abstract) default that calls `core/captcha.py`. Plugins can override.

### 1e. Modified vs New Components — Cluster 1

| Component | Status | Change |
|-----------|--------|--------|
| `core/plugin_base.py` | MODIFIED | `setup()` becomes concrete default calling `build_browser()`; add `solve_captcha()` concrete method |
| `core/config_schema.py` | MODIFIED | Extract `BasePlatformConfig`; add `proxy/fingerprint_seed/captcha_solver` fields; add `AntiDetectionConfig`; add to `AppConfig` |
| `core/credentials.py` | MODIFIED | Add 4 new keys to `SECRET_KEYS` |
| `core/browser_factory.py` | NEW | `build_browser(platform_cfg, global_cfg) -> Browser`; assembles nodriver args for proxy, UA, fingerprint, CAPTCHA extension |
| `core/captcha.py` | NEW | `solve_captcha(tab, solver_name, api_key, timeout) -> bool`; wraps 2captcha/capsolver HTTP APIs |
| `plugins/shopbot_plugin_*.py` (7 files) | MODIFIED (optional) | Each plugin's `setup()` can be simplified to delegate to `super().setup()` — this is a quality improvement, not a hard requirement |

---

## Cluster 2: Plugin Ecosystem Registry

### 2a. Plugin Metadata — New ABC Attributes

The GitHub wiki registry needs structured data per plugin. Add class attributes to
`RetailerPlugin`:

```python
class RetailerPlugin(ABC):
    domain_patterns: list[str]      # EXISTING
    platform_key: str               # EXISTING (used by orchestrator for config lookup)

    # NEW — wiki registry metadata:
    display_name: str = ""          # human name, e.g. "Amazon US"
    maintainer: str = ""            # GitHub handle or email
    risk_level: str = "unknown"     # "low" | "medium" | "high" | "unknown"
    captcha_notes: str = ""         # short free-text, e.g. "reCAPTCHA v2 on checkout"
    auto_buy_supported: bool = True # False = check-only plugin
    plugin_version: str = "1.0.0"
```

These are class attributes with defaults, not abstract. Existing plugins that do not define
them get the defaults (backward-compatible). The registry already reads `domain_patterns`
as a class attribute before `__init__` — same pattern applies here.

**No ABC change breaks existing plugins.** All new attributes have defaults. The ABC
`PLUGIN_API_VERSION` stays at 2.

### 2b. Registry Generation

A new `core/wiki_registry.py` module (or a CLI command) iterates `PluginRegistry._all_plugins`,
reads the class attributes above, and renders a Markdown table. This output is either
committed to the GitHub wiki manually or pushed via GitHub API.

```
core/wiki_registry.py   (NEW)
  generate_registry_markdown(registry: PluginRegistry) -> str
    - iterates plugins
    - reads metadata class attributes
    - formats Markdown table: Plugin | Platforms | Maintainer | Risk | Auto-Buy | Notes
    - returns Markdown string

CLI command: shoppybot registry generate  -> prints or writes to file
```

The wiki push itself (GitHub API) is out-of-scope for the bot process; the CI workflow
or a maintainer runs `shoppybot registry generate > wiki/Plugin-Registry.md` and commits.

### 2c. Modified vs New Components — Cluster 2

| Component | Status | Change |
|-----------|--------|--------|
| `core/plugin_base.py` | MODIFIED | Add 6 class-attribute metadata fields with defaults |
| `core/registry.py` | UNCHANGED | `_discover_plugins` already reads class attributes; no change needed |
| `core/wiki_registry.py` | NEW | `generate_registry_markdown()` function |
| `core/cli/` | MODIFIED | Add `registry` subcommand that calls `wiki_registry.generate_registry_markdown` |
| `plugins/shopbot_plugin_*.py` (7 files) | MODIFIED | Add metadata attributes (display_name, maintainer, risk_level, etc.) to each plugin class |
| `plugins/PLUGIN_DEV.md` | MODIFIED | Document new metadata attributes; update example_plugin.py |

---

## Cluster 3: Price Monitoring

### 3a. Data Model Changes

**Decision: new columns on the existing `items` table, not a separate table.**

Rationale: price is a property of the item being tracked, not a separate entity. A separate
table only makes sense if price history needs indefinite retention with per-timestamp rows.
For the v3.0 scope (current price, target price, price history as a lightweight JSON log),
new columns on `items` plus an optional `price_history` table is the right split.

Items table additions:
```sql
ALTER TABLE items ADD COLUMN current_price REAL;       -- NULL if not fetched yet
ALTER TABLE items ADD COLUMN target_price REAL;        -- NULL = monitor regardless of price
ALTER TABLE items ADD COLUMN currency TEXT DEFAULT 'USD';
ALTER TABLE items ADD COLUMN price_last_checked TEXT;  -- ISO-8601 UTC timestamp
```

Price history table (new, separate — price is time-series data):
```sql
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY,
    item_link TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    checked_at TEXT NOT NULL,            -- ISO-8601 UTC
    FOREIGN KEY (item_link) REFERENCES items(link)
);
```

`models.py` additions (all `_sync` pattern, WAL-safe):
```python
set_item_price_sync(link, price, currency, checked_at)   # updates current_price + logs history
get_item_price_sync(link) -> tuple[float|None, float|None, str|None]  # current, target, checked_at
add_price_history_sync(link, price, currency, checked_at)
get_price_history_sync(link, limit=90) -> list[...]      # for display; default 90 days
```

`initialize_db()` in `models.py` already uses idempotent `ALTER TABLE ... IF NOT EXISTS`
pattern for `last_seen_available` and `last_notified`. Same pattern applies.

Config item schema (`ItemConfig` in `config_schema.py`) gains an optional field:
```python
class ItemConfig(BaseModel):
    name: str
    link: str
    auto_buy: bool = False
    quantity: int = 1
    target_price: float | None = None   # NEW: None = no price gate
```

### 3b. Where Price Parsing Lives

**Decision: optional `get_price()` method on the RetailerPlugin ABC, not a separate parser module.**

Each retailer exposes price differently (DOM selector, JSON-LD, API). The plugin already
owns the browser and knows the page structure. A shared parser would need to handle
7+ different DOM layouts — that is abstraction without value.

```python
# ADD to RetailerPlugin (non-abstract, returns None by default):
async def get_price(self, url: str) -> float | None:
    """Return the current item price as a float, or None if not parseable.

    Default implementation returns None. Plugins that support price monitoring
    override this method. Price is in the currency defined by the item config.
    """
    return None
```

This is additive and backward-compatible. Existing plugins get `None` (no price data).
Plugins that implement it start feeding price history automatically.

The orchestrator calls `get_price()` alongside `check_availability()` in `_check_and_buy()`:

```python
# MODIFIED: core/orchestrator.py _check_and_buy()
price = await plugin.get_price(link)
if price is not None:
    await write_queue.put(("set_price", link, price, "USD", now_iso))
```

A new write-queue tag `"set_price"` is dispatched by `_dispatch_write()`.

### 3c. Price-Drop Alert Through Existing Dispatcher

The `NotificationEvent` dataclass gains two optional fields:

```python
@dataclass
class NotificationEvent:
    item_name: str
    item_url: str
    platform: str
    timestamp: datetime
    action: str    # EXISTING: "detected" | "purchased" | NEW: "price_drop"
    current_price: float | None = None   # NEW
    target_price: float | None = None    # NEW
```

This is a backward-compatible dataclass extension (keyword args with defaults). All existing
notifiers that don't read these fields continue working without modification.

The orchestrator emits a price-drop event when:
```
current_price is not None
AND target_price is not None
AND current_price <= target_price
AND the price was not already at-or-below target on the last check
```

The dedup guard uses the same edge-trigger pattern as stock availability: the event fires
once when price crosses the target, not on every poll cycle while it remains below target.
A new `price_below_target` boolean column on `items` (or a derived check from `current_price`
vs `target_price`) tracks the edge state. Simpler: compare current vs previous price from
the write queue, store `price_alert_sent` timestamp in `items` alongside `last_notified`.

Existing `NotificationDispatcher.notify()` requires no change — it fans out to all
registered notifiers. Each notifier's `send()` method checks `event.action == "price_drop"`
to render the right message. The Discord notifier already formats embeds from event fields;
it needs only a new embed template branch for `price_drop`.

### 3d. BotService and CLI/Web Surface

`BotService` gains price-related item management methods:

```python
def set_item_target_price(self, link: str, price: float | None) -> None: ...
def get_price_history(self, link: str, limit: int = 90) -> list: ...
```

CLI: `shoppybot items set-price --url "..." --target 299.99`
Web UI: items list row gains current price display + target price input field.

### 3e. Modified vs New Components — Cluster 3

| Component | Status | Change |
|-----------|--------|--------|
| `models.py` | MODIFIED | Add 4 columns to items; add price_history table; add price CRUD functions |
| `core/config_schema.py` | MODIFIED | Add `target_price: float | None` to `ItemConfig` |
| `core/plugin_base.py` | MODIFIED | Add `get_price()` non-abstract method returning `None` |
| `core/orchestrator.py` | MODIFIED | Call `get_price()` in `_check_and_buy`; emit `price_drop` events; add `"set_price"` write-queue tag in `_dispatch_write` |
| `notifications/base.py` | MODIFIED | Add `current_price` and `target_price` optional fields to `NotificationEvent` |
| `notifications/discord_notifier.py` | MODIFIED | Add embed branch for `action == "price_drop"` |
| `notifications/email_notifier.py` | MODIFIED | Add message branch for price_drop |
| `core/service.py` | MODIFIED | Add `set_item_target_price()` and `get_price_history()` |
| `core/cli/` | MODIFIED | Add `items set-price` subcommand |
| `web/` | MODIFIED | Extend items routes and template for price display |
| `plugins/shopbot_plugin_*.py` | OPTIONAL | Each can implement `get_price()` incrementally; default is None |

---

## Consolidated Component Map

### New Components

| File | Purpose |
|------|---------|
| `core/browser_factory.py` | `build_browser()` — assembles nodriver args for proxy, UA, fingerprint, CAPTCHA extension |
| `core/captcha.py` | `solve_captcha()` — wraps 2captcha/capsolver APIs; falls back to manual event |
| `core/wiki_registry.py` | `generate_registry_markdown()` — renders plugin metadata to Markdown table |

### Modified Components

| File | What Changes |
|------|-------------|
| `core/plugin_base.py` | `setup()` default calls `build_browser()`; add `solve_captcha()`, `get_price()`, metadata class attributes |
| `core/config_schema.py` | `BasePlatformConfig` extraction; proxy/fingerprint/captcha fields; `AntiDetectionConfig`; `ItemConfig.target_price` |
| `core/credentials.py` | 4 new entries in `SECRET_KEYS` |
| `core/orchestrator.py` | `_check_and_buy` calls `get_price()`; `_dispatch_write` handles `"set_price"` tag; price-drop edge-trigger event |
| `core/service.py` | `set_item_target_price()`, `get_price_history()` |
| `core/cli/` | `registry generate` subcommand; `items set-price` subcommand |
| `core/registry.py` | UNCHANGED |
| `models.py` | 4 new columns on items; price_history table; price CRUD functions |
| `notifications/base.py` | `NotificationEvent` gains `current_price`, `target_price` optional fields; `action` gains `"price_drop"` |
| `notifications/dispatcher.py` | UNCHANGED |
| `notifications/discord_notifier.py` | Price-drop embed branch |
| `notifications/email_notifier.py` | Price-drop message branch |
| `web/` routes + templates | Price display and target-price input |
| `plugins/shopbot_plugin_*.py` | Metadata attributes (required for wiki registry); `setup()` delegation (optional refactor); `get_price()` (optional per plugin) |

---

## Data Flow Changes

### Stock Check (existing + price added)

```
orchestrator._check_and_buy(plugin, name, link, auto_buy, write_queue, dispatcher)
  ├── plugin.check_availability(link)         # UNCHANGED
  ├── plugin.get_price(link)                  # NEW (returns None if not implemented)
  │     -> write_queue.put(("set_price", link, price, currency, ts))  # NEW tag
  ├── price_drop edge check                   # NEW
  │     -> dispatcher.notify(price_drop event)  # NEW action
  └── ... (existing availability/purchase flow unchanged)
```

### Browser Launch (per plugin setup)

```
RetailerPlugin.setup()  [default impl, NEW]
  -> browser_factory.build_browser(platform_cfg, global_anti_detection_cfg)
       ├── resolve proxy (per-platform or global)
       ├── resolve fingerprint seed
       ├── load CAPTCHA extension path if configured
       └── nodriver.start(**assembled_args) -> Browser
  -> self.driver = browser
```

### CAPTCHA Solve (new path alongside existing manual path)

```
plugin.check_availability(link)
  -> plugin.detect_captcha()  returns True
       -> plugin.solve_captcha(tab)  [NEW default impl]
            -> captcha_solver configured?
                 YES: core/captcha.py: call API, inject token, return True/False
                 NO:  _wait_user_action(captcha_event, ...)  [EXISTING unchanged]
```

### Price-Drop Notification

```
models.price_history  <-  set_item_price_sync()
items.current_price   <-  set_item_price_sync()
  |
  v
orchestrator: current_price <= target_price AND was_above_target?
  YES -> dispatcher.notify(NotificationEvent(action="price_drop", current_price=X, target_price=Y))
         -> DiscordNotifier: embed with price fields
         -> EmailNotifier: price-drop subject/body
         -> SoundNotifier: notification sound (existing, unchanged)
```

---

## Backward Compatibility

All 7 existing plugins remain valid without modification. Specifically:

- New ABC class attributes (`display_name`, `risk_level`, etc.) have defaults.
- `setup()` default is now concrete but plugins that override it entirely are unaffected.
- `get_price()` default returns `None` — plugins without price support produce no price events.
- `solve_captcha()` default uses the existing manual event flow if no solver is configured.
- `NotificationEvent` new fields are keyword-only with `None` defaults — existing notifiers
  that ignore them continue working.
- `SECRET_KEYS` additions are additive — existing stored secrets are unaffected.

The only forced change across all 7 plugins is adding the metadata class attributes for the
wiki registry. That is 6 lines per plugin file and does not touch any logic.

---

## Suggested Build Order

Dependencies drive the order. Each step's deliverable must exist before the next begins.

### Step 1: Config schema extensions (no code dependencies)

Target: `core/config_schema.py`

- Extract `BasePlatformConfig`; add `proxy`, `fingerprint_seed`, `captcha_solver` fields
- Add `AntiDetectionConfig`; wire into `AppConfig`
- Add `target_price` to `ItemConfig`

This step has no upstream dependencies and unblocks all other steps.

### Step 2: CredentialStore expansion (depends on Step 1 only for testing context)

Target: `core/credentials.py`

- Add `TWOCAPTCHA_API_KEY`, `CAPSOLVER_API_KEY`, `PROXY_USERNAME`, `PROXY_PASSWORD` to SECRET_KEYS
- Update `shoppybot setup` prompts if they enumerate SECRET_KEYS (verify in cli/setup.py)

### Step 3: Browser factory (depends on Steps 1 and 2)

Target: `core/browser_factory.py` (NEW)

- `build_browser(platform_cfg, global_cfg)` reads proxy, fingerprint, headless, user_agents
- Calls `get_store()` for proxy credentials if `PROXY_USERNAME` is set
- Returns `nodriver` browser instance
- Unit-testable by mocking `nodriver.start`

### Step 4: CAPTCHA solver helper (depends on Steps 2 and 3)

Target: `core/captcha.py` (NEW)

- `solve_captcha(tab, solver_name, api_key, timeout)` wraps 2captcha/capsolver HTTP calls
- Returns bool; raises on API error (caller decides fallback)

### Step 5: ABC updates (depends on Steps 3 and 4)

Target: `core/plugin_base.py`

- `setup()` default: calls `build_browser()` and assigns `self.driver`
- Add `solve_captcha()` concrete method delegating to `core/captcha.py`
- Add `get_price()` returning `None`
- Add metadata class attributes with defaults

At this point all infrastructure is in place. Steps 6-8 can proceed in any order.

### Step 6: Price data layer (depends on Step 1)

Target: `models.py`

- Idempotent `ALTER TABLE` for 4 new items columns
- `CREATE TABLE IF NOT EXISTS price_history`
- Add price CRUD sync functions
- Extend `initialize_db()`

### Step 7: Orchestrator price wiring (depends on Steps 5 and 6)

Target: `core/orchestrator.py`

- `_check_and_buy` calls `plugin.get_price(link)` after availability check
- Add `"set_price"` tuple tag to `_dispatch_write`
- Price-drop edge-trigger check and `dispatcher.notify` call

### Step 8: Notification event and notifier updates (depends on Step 7)

Targets: `notifications/base.py`, `notifications/discord_notifier.py`, `notifications/email_notifier.py`

- Add optional price fields to `NotificationEvent`
- Add `price_drop` branches to Discord embed and email body

### Step 9: Plugin metadata (depends on Step 5)

Targets: `plugins/shopbot_plugin_*.py` (7 files)

- Add metadata class attributes to each plugin
- Optionally simplify each plugin's `setup()` to call `super().setup()`
- Optionally implement `get_price()` for platforms where price DOM is stable

### Step 10: Wiki registry (depends on Step 9)

Target: `core/wiki_registry.py` (NEW)

- `generate_registry_markdown(registry)` reads metadata, renders table

### Step 11: BotService and front-ends (depends on Steps 6, 8, 10)

Targets: `core/service.py`, `core/cli/`, `web/`

- `BotService.set_item_target_price()`, `get_price_history()`
- CLI `items set-price` subcommand
- CLI `registry generate` subcommand
- Web UI price display and target-price input

### Dependency Graph

```
Step 1: config_schema
  └─ Step 2: credentials
       └─ Step 3: browser_factory
            └─ Step 4: captcha.py
                 └─ Step 5: plugin_base (ABC updates)
                      └─ Step 9: plugin metadata
                           └─ Step 10: wiki_registry

Step 1: config_schema
  └─ Step 6: models (price data layer)
       └─ Step 7: orchestrator (price wiring)
            └─ Step 8: notifications (price_drop event/notifiers)
                 └─ Step 11: BotService + CLI + web

All steps must complete before Step 11.
Steps 6-8 and Steps 3-5 can proceed in parallel after Step 1.
```

---

## Anti-Patterns to Avoid

### Each Plugin Reimplements Browser Launch

**What:** Continuing the current pattern where every plugin calls `nodriver.start(headless=...)` directly.
**Why bad:** Proxy/fingerprint/CAPTCHA extension wiring must then be duplicated in 7+ files. A new
contributor's plugin naturally skips it.
**Instead:** `browser_factory.build_browser()` is the single launch point. ABC's default `setup()`
calls it.

### Storing CAPTCHA API Keys in config.yml

**What:** Adding `twocaptcha_api_key: "..."` to a config.yml section.
**Why bad:** Violates the established v2.0 security posture (CRED-06): secrets never plaintext on disk.
**Instead:** Route through `CredentialStore.get("TWOCAPTCHA_API_KEY")` — already the pattern for all
other secrets.

### Separate Price Table as the Primary Store

**What:** Putting `current_price` and `target_price` in a `prices` table joined to `items`.
**Why bad:** Every orchestrator poll cycle requires a join. The item and its price target are 1:1.
**Instead:** 4 columns on `items` (current_price, target_price, currency, price_last_checked).
Only the time-series history goes in a separate `price_history` table.

### Making `get_price` Abstract

**What:** `@abstractmethod async def get_price(self, url: str) -> float | None`
**Why bad:** Breaks all 7 existing plugins immediately; price monitoring is opt-in.
**Instead:** Concrete default returning `None`. Plugins opt in by overriding.

### Embedding Price in NotificationEvent as a Formatted String

**What:** `action: str = "price_drop: $299.99 -> $249.99"`
**Why bad:** Parsers downstream (web UI, future integrations) must string-split. Impossible to
localize currency.
**Instead:** Separate `current_price: float | None` and `target_price: float | None` fields on
`NotificationEvent`. Notifiers format them per-channel.

---

## Scalability Considerations

| Concern | v3.0 scope | Future concern |
|---------|-----------|----------------|
| CAPTCHA API cost | Per-solve billing; rate-limit with exponential backoff in `core/captcha.py` | Monitor spend; add per-platform on/off toggle |
| Proxy rotation pool | Single proxy string per platform for now | Proxy pool list + round-robin if single proxy gets blocked |
| Price history retention | 90-day default; no auto-purge yet | Add `VACUUM` + periodic delete of rows older than N days |
| Browser fingerprint | Seed per session; static during session | Rotate seed per N requests if platforms learn session patterns |
| Plugin registry wiki | Generated locally, manually pushed | Automate via GitHub Actions on plugin PR merge |

---

## Sources

- Codebase read directly: `core/plugin_base.py`, `core/credentials.py`, `core/config_schema.py`,
  `core/orchestrator.py`, `core/registry.py`, `core/service.py`, `models.py`,
  `notifications/base.py`, `notifications/dispatcher.py`, `plugins/shopbot_plugin_amazon.py`
- Existing architecture doc: `.planning/research/ARCHITECTURE.md` (v1 research, superseded)
- Project state: `.planning/PROJECT.md`, `.planning/milestones/v2.0-ROADMAP.md`
- Confidence: HIGH — all integration points derived from reading the actual source, not assumptions
