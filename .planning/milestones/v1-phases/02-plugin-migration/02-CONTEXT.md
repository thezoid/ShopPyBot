# Phase 2: Plugin Migration - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate Amazon and BestBuy from standalone modules (`amazon_bot.py`, `bestbuy_bot.py`) into the `RetailerPlugin` ABC as drop-in plugins under `plugins/`. Build a registry that auto-discovers `shopbot_plugin_*.py` files via `importlib` (warns + ignores non-matching `.py`), routes item URLs to the right plugin by domain, and gives each plugin its own isolated driver. Ship contributor tooling (`example_plugin.py` + `plugins/PLUGIN_DEV.md`) so an external developer can build a working plugin without reading core source.

Requirements: CORE-03, CORE-04, CORE-08, PLG-01, PLG-02, PLG-03.

**Explicitly NOT in this phase:** new platforms (Walmart/Target/etc.), real concurrent/parallel item checking, per-platform flexible config sections, notification integrations. These are separate roadmap items.

</domain>

<decisions>
## Implementation Decisions

### Driver Technology & Concurrency
- **D-01:** Migrate both platforms to **nodriver** (the locked `nodriver==0.50.3` dep) this phase, using its async API. Port the proven Amazon/BestBuy DOM check/buy logic from Selenium to nodriver. This honors the Phase-1 note that nodriver replaces Selenium in Phase 2.
- **D-02:** **Remove** the Phase-1 Selenium `navigator.webdriver` CDP stealth patch and the Selenium driver setup from `main.py` — nodriver handles stealth architecturally (SEC-04 carries over to nodriver).
- **D-03:** Build the **async plumbing** (async ABC methods + `asyncio` main loop) but execute **sequentially** — `await plugin.check_availability(...)` one item at a time. Real concurrent checking (`asyncio.gather`) is DEFERRED to its own phase (already on the roadmap as a separate requirement).
- **D-04:** **One nodriver `Browser` process per plugin** (separate Chrome process + profile). Strongest isolation, satisfies PLG-03 "no shared global driver", and lets each platform set its own stealth/UA. Accepted cost: one Chrome process per active plugin.

### RetailerPlugin ABC Revision
- **D-05:** Revise the Phase-1 ABC (`core/plugin_base.py`). Methods become **async** and **drop the `driver` parameter** (use `self.driver`). Bump **`PLUGIN_API_VERSION` 1 → 2**. This intentionally supersedes the Phase-1 "locked" v1 interface — the migration is the reason it changes.
- **D-06:** Reconcile PLG-03's "driver in `__init__`" with nodriver's async start via an **`async setup()`** method the registry awaits after construction (`__init__` sets `self.driver = None`; `setup()` builds the Browser). Add a matching **`async teardown()`** to close the browser at shutdown. Do NOT build the browser inside `__init__` (nested-event-loop risk once the main loop is async).
- **D-07:** Target interface shape:
  ```python
  PLUGIN_API_VERSION = 2
  class RetailerPlugin(ABC):
      domain_patterns: list[str]
      def __init__(self, config): self.config = config; self.driver = None
      async def setup(self): ...        # registry awaits; builds nodriver Browser
      @abstractmethod
      async def check_availability(self, url) -> bool: ...
      @abstractmethod
      async def auto_buy(self, url) -> bool: ...
      async def login(self) -> None: ...        # no-op default
      async def detect_captcha(self) -> bool: ...  # no-op default
      async def teardown(self) -> None: ...     # close browser
  ```
- **D-08:** Plugins receive the **typed `AppConfig`** (from Phase-1 `core/config_schema.py`); amazon/bestbuy read `config.platforms.<name>` + global `config.debug` / `config.selenium`. Reuses Phase-1 typing. The community-plugin config-extensibility gap (AppConfig's `PlatformsConfig` has fixed amazon/bestbuy fields, so a new community platform can't add config keys without a core edit) is **DEFERRED** to the future "per-platform flat config sections" phase.

### Driver Lifecycle / Instantiation
- **D-09:** **Eager discovery, lazy browser launch.** At startup the registry instantiates ALL discovered plugins (cheap objects; reads `domain_patterns` for routing) but awaits `setup()` (launches Chrome) ONLY for plugins that have ≥1 matching item in config. Unused plugins never open a browser. `teardown()` all launched plugins at shutdown.

### URL Routing
- **D-10:** Plugins declare **`domain_patterns: list[str]`**. The registry parses the URL host via `urlparse(url).hostname` and routes to a plugin if any pattern is a substring of the host (`any(p in host for p in plugin.domain_patterns)`). Matching the host (not the raw URL) avoids false hits on paths/query strings; the list handles multi-domain retailers (e.g. `amazon.com`, `amazon.co.uk`).

### Specified (not gray areas — implement as written)
- **PLG-02:** The BestBuy plugin MUST add the missing `update_item_purchased()` call after a successful purchase (the known bug PLG-02 calls out).

### Claude's Discretion
Planner/researcher decide these (user opted not to discuss):
- Registry file location (e.g. `core/registry.py`) and internal structure.
- `example_plugin.py` demo platform (fictional vs real-simple) and exact `PLUGIN_DEV.md` outline — must satisfy criterion 4 (working skeleton without reading core).
- Exact warning text/log level for non-matching `.py` files (CORE-03) and handling of a plugin that fails import / `setup()` (recommend: log + skip that plugin, don't abort the bot — aligns with success criterion 2's "does not crash" intent).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 2: Plugin Migration" — goal + 4 success criteria
- `.planning/REQUIREMENTS.md` — CORE-03, CORE-04, CORE-08, PLG-01, PLG-02, PLG-03 (full text)
- `.planning/PROJECT.md` — core value (the plugin framework), out-of-scope list

### Existing code to migrate / revise
- `core/plugin_base.py` — Phase-1 `RetailerPlugin` ABC v1; REVISE per D-05/06/07 (async, self.driver, setup/teardown, v2)
- `amazon_bot.py` — source of Amazon check/buy DOM logic to port into `plugins/shopbot_plugin_amazon.py` (PLG-01)
- `bestbuy_bot.py` — source of BestBuy check/buy/sign-in logic to port into `plugins/shopbot_plugin_bestbuy.py` (PLG-02); add `update_item_purchased()` call
- `main.py` — sequential Selenium loop + Phase-1 CDP stealth patch + getpass CVV + AppConfig validation; convert loop to async, remove Selenium driver setup + CDP patch, route via registry
- `core/config_schema.py` — `AppConfig` / `PlatformsConfig` passed to plugins (D-08)
- `models.py` — `update_item_purchased()` (PLG-02) and `get_items()` consumed by the loop

### Dependency
- `nodriver==0.50.3` (locked in `requirements.txt`, Phase 1) — async browser automation library replacing Selenium

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/plugin_base.py`: existing ABC scaffold (no-op `login`/`detect_captcha` defaults) — extend, don't rebuild.
- Amazon/BestBuy DOM selectors + flow in `amazon_bot.py` / `bestbuy_bot.py` are proven (validated in Phase-1 UAT cold-start run) — port the logic, only swap the driver API (Selenium → nodriver async).
- `main.py` already does AppConfig startup validation, env-var credential sourcing (BB_EMAIL/BB_PASSWORD), and the getpass CVV gate — preserve these; rehome the driver/loop parts.

### Established Patterns
- Domain routing already exists informally in `main.py` (`if "amazon.com" in link / elif "bestbuy.com" in link`) — the registry formalizes this via `domain_patterns` (D-10).
- Phase-1 convention: secrets only from env/getpass, never config.yml/logs — plugins MUST keep this (no credentials in plugin code or config).

### Integration Points
- Registry sits between `main.py` loop and the plugins: discovers (`importlib`), routes by host, owns plugin lifecycle (setup/teardown).
- `getpass` CVV gate is sync and blocking; it runs once at startup before the async loop — keep it there (don't call it inside async item iteration).

</code_context>

<specifics>
## Specific Ideas

- ABC target shape is pinned in D-07 (use it verbatim as the contract).
- Lazy-launch flow pinned in D-09: discover all → route → `setup()` only matched plugins → loop → `teardown()`.

</specifics>

<deferred>
## Deferred Ideas

- **Real concurrent / parallel item checking** (`asyncio.gather` across plugins/items) — async plumbing lands now, but concurrent execution is its own roadmap requirement. (D-03)
- **Per-platform flexible config sections** — community plugins adding their own validated config keys without editing core `AppConfig`. Needed for true community extensibility; belongs in the future "per-platform flat config sections" phase. (D-08)
- **New platforms** (Walmart, Target, GameStop, Square Enix, NewEgg) — depend on this framework but are later phases.

</deferred>

---

*Phase: 2-plugin-migration*
*Context gathered: 2026-06-02*
