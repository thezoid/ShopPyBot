# Phase 6: Platform Expansion - Context

**Gathered:** 2026-05-15
**Status:** Ready for research and planning
**Source:** /gsd-discuss-phase 6 (interactive)

<domain>
## Phase Boundary

Phase 6 ships five new retail plugins (Walmart, Target, GameStop, Square Enix, NewEgg) plus three anti-detection features (per-platform jitter, UA rotation, headless toggle). The five new plugins use nodriver (async-native CDP-direct) for better anti-detection; the existing Selenium-based Amazon and BestBuy plugins stay as-is. All five new plugins ship full auto-buy capability, gated behind a `SHOPBOT_ENABLE_RISKY_AUTOBUY=true` env var so accidental account-ban risk is opt-in.

Eight in-scope requirements: PLG-04, PLG-05, PLG-06, PLG-07, PLG-08, ANTI-01, ANTI-02, ANTI-03.

Out of scope (defer):
- Slack / Telegram / generic webhook notifiers (Phase 5 backlog)
- Phase 5 SMS two-lock follow-ups (already covered)
- Async-only RetailerPlugin contract refactor (the ABC stays driver-agnostic; no breaking changes to Amazon/BestBuy)
- nodriver swap for Amazon and BestBuy plugins (deferred to a future hardening phase; Selenium is still working there)
- Walmart PerimeterX/HUMAN deep-bypass research (researcher should call out the risk; deep mitigation is a follow-up)

</domain>

<decisions>
## Implementation Decisions

### Driver runtime for new plugins (supports PLG-04..08)

**D-01: All five new plugins use nodriver. Existing Amazon/BestBuy stay on Selenium. The `RetailerPlugin` ABC stays driver-agnostic.**
- `self.driver` is an instance attribute with no ABC type constraint. nodriver plugins assign a `nodriver.Browser` (or similar) to `self.driver`; Selenium plugins assign a `selenium.webdriver.Chrome`. The ABC does NOT enforce a type because the contract is method-level (`check_availability`, `auto_buy`, `login`, `detect_captcha`, `shutdown`), not attribute-level.
- nodriver pinned in requirements.txt at the version current at execution time (researcher verifies pip index for latest stable).
- `build_driver(driver_path, log_path, headless=False)` factory remains Selenium-only. New plugins do NOT call it. Each nodriver plugin owns its own async driver-construction code inside `__init__` (and may need its own `async def __aenter__` / `__aexit__` for nodriver's async lifecycle — researcher confirms).
- `shutdown()` in nodriver plugins overrides the Phase 4 D-04 default to call `await self.driver.stop()` (nodriver API) instead of `await asyncio.to_thread(self.driver.quit)` (Selenium API).
- Rationale: nodriver's async-native CDP is far better at evading PerimeterX/HUMAN/Akamai than Selenium. Mixing drivers in the same registry is acceptable because the orchestrator only invokes plugin methods, never poking driver internals.

### Risky auto-buy gate (PLG-04..08)

**D-02: All five new plugins ship full auto-buy capability, gated at runtime by env var `SHOPBOT_ENABLE_RISKY_AUTOBUY=true`. Mirrors the SMS two-lock pattern from Phase 5.**
- Each new plugin's `__init__` reads `os.environ.get("SHOPBOT_ENABLE_RISKY_AUTOBUY") == "true"` and stores the result on `self._riskyAutoBuyEnabled: bool`.
- Inside each plugin's `auto_buy(url, config)`:
  - If `self._riskyAutoBuyEnabled is False`: log WARNING via writeLog ("Plugin <name> auto_buy called but SHOPBOT_ENABLE_RISKY_AUTOBUY not set; check-only mode") and return early. No purchase attempt.
  - If True: full auto-buy logic runs.
- `check_availability` is unaffected by the gate. Even without the env var, the plugin still polls and reports availability to the notification system; only the purchase action is gated.
- CAPTCHA flow (GameStop and any plugin that hits one): mirrors Amazon's OTP pattern from Phase 4 D-02. Use `await asyncio.to_thread(input, "GameStop CAPTCHA detected; solve and press Enter")` inside `detect_captcha()` or `auto_buy()`.
- Walmart specifics: even with the env var enabled, the Walmart plugin logs an INFO note at first auto_buy attempt warning the user about PerimeterX/HUMAN detection risk and pointing them at SECURITY.md.
- Rationale: ships full feature surface (no half-built code) while preventing one-line accidents. Mirrors the SMS opt-in model users already understand.

### Per-platform jitter (ANTI-01)

**D-03: `min_delay: float` and `max_delay: float` live in each platform's config sub-model (`platforms.<name>.min_delay` / `platforms.<name>.max_delay`).**
- Pydantic `PlatformConfig` (from Phase 1) gets two new fields with sensible defaults (e.g., `min_delay: float = 3.0`, `max_delay: float = 8.0`).
- Each plugin's polling loop draws a fresh `random.uniform(min_delay, max_delay)` between polls. Replaces Phase 4's global `app.delay` for plugins that opt in. Existing Amazon/BestBuy can also adopt by reading their own platforms.amazon/bestbuy block.
- The orchestrator's `poll_plugin` loop in main.py changes to `await asyncio.sleep(plugin.next_delay())` where `next_delay()` is a non-abstract method on `RetailerPlugin` with default `return random.uniform(self.min_delay, self.max_delay)`. Plugins set `self.min_delay` and `self.max_delay` from their `platform_config` in `__init__`.
- Rationale: matches REQUIREMENTS.md ANTI-01 wording exactly ("per-platform configurable check interval with random jitter"). Per-plugin defaults exist for contributors who skip explicit config.

### Headless toggle (ANTI-03)

**D-04: Extend the Phase 1 `build_driver` factory: `build_driver(driver_path, log_path, headless: bool = False)`.**
- New kwarg; default False preserves Phase 1 behavior. Existing Amazon/BestBuy plugin `__init__` code stays unchanged (call site uses kwargs already).
- When `headless=True`: add `--headless=new` to Chrome options (modern headless mode that survives most Cloudflare-light fingerprinting).
- Selenium plugins (Amazon, BestBuy) read `platforms.<name>.headless: bool` from app_config and pass to build_driver.
- nodriver plugins do NOT use build_driver. They configure headless mode via nodriver's own start-args (researcher confirms API: typically `await nodriver.start(headless=True)`).
- `PlatformConfig` gets `headless: bool = False` field. Same default everywhere.
- Phase 1 driver hardening tests (`tests/test_driver_setup.py`) extended to cover headless=True path.
- Rationale: single factory, single test surface. ANTI-03 wording satisfied. Selenium kwarg pile-up is small (3 args, well-named).

### Claude's Discretion

The planner / researcher decides:

- **ANTI-02 UA rotation shape** — likely a config field `app.user_agents: list[str] | None = None` with a sensible bundled default list. `build_driver` (Selenium) picks `random.choice(user_agents)` on each call. nodriver plugins read the same list and pass to their start-args. Planner picks: per-platform UA list override, single global list, or both.
- **Plugin name resolution for new plugins** — follow Phase 2 D-04 convention: optional `name: str` class attr; defaults to filename stem with `shopbot_plugin_` prefix removed.
- **`domain_pattern` per plugin** — Walmart: `["walmart.com"]`; Target: `["target.com"]`; GameStop: `["gamestop.com"]`; Square Enix: `["square-enix.com", "store.eu.square-enix-games.com"]` (planner verifies); NewEgg: `["newegg.com"]`.
- **Test strategy for the 5 new plugins** — cannot CI-test against live retailers. Recommend: each plugin gets unit tests for DOM-parse helpers and a mock-driver smoke test verifying ABC contract. Integration tests are out of scope (note this in PLUGIN_DEV.md for contributors).
- **nodriver async lifecycle** — research must confirm whether nodriver's `Browser` needs `await browser.start()` in __init__ or whether it can be deferred to first `check_availability` call. Affects the 1.5s stagger pattern from Phase 4 (which assumes driver init happens in __init__).
- **GameStop CAPTCHA flow timing** — Phase 4 D-02 said input() goes through asyncio.to_thread. Inside a plugin method called by orchestrator's `await asyncio.to_thread(plugin.auto_buy, ...)`, the input() call is already in a worker thread and blocks only that thread. Same pattern applies — researcher confirms.
- **UA list source** — bundled with the bot or contributor-supplied? Recommend a small bundled default (5-10 real Chrome UA strings refreshed for current Chrome major) with config override.
- **nodriver+selenium coexistence in plugin_registry** — `discover_async`'s 1.5s stagger applies to BOTH driver types. Sleep happens before nodriver.start() OR build_driver() depending on plugin type.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1-5 outputs (locked contracts)
- `plugin_base.py` — `RetailerPlugin` ABC (driver-agnostic). Phase 6 does NOT modify the ABC.
- `plugin_registry.py` — `discover_async()` with 1.5s stagger. Works for both Selenium and nodriver plugins (sleep is type-agnostic).
- `config_schema.py` — `AppConfig` + `PlatformConfig`. Phase 6 adds `min_delay`, `max_delay`, `headless` to `PlatformConfig`; optionally adds `app.user_agents`.
- `driver.py` — `build_driver(driver_path, log_path)` Phase 1 factory. Phase 6 D-04 extends with `headless` kwarg.
- `notifier_base.py` + `notifier_registry.py` — Phase 5 notification system. New plugins fire NotificationEvents the same way Amazon/BestBuy do via the orchestrator's queue put.
- `main.py` — Phase 4+5 async orchestrator. Phase 6 changes the polling `await asyncio.sleep(app.delay)` to `await asyncio.sleep(plugin.next_delay())` per ANTI-01.
- `plugins/PLUGIN_DEV.md` — Phase 2 contributor guide. Phase 6 may extend with a "nodriver vs Selenium" guidance section.
- `SECURITY.md` — Phase 3 doc. Walmart/Target/GameStop risks already documented there.

### Project decisions
- `.planning/PROJECT.md` — nodriver preferred for new plugins, Walmart PerimeterX risk flagged
- `.planning/REQUIREMENTS.md` — PLG-04..08, ANTI-01..03 wording
- `.planning/phases/04-async-orchestrator/04-CONTEXT.md` — Phase 4 D-01 deferred nodriver swap to Phase 6 or later
- `.planning/phases/02-plugin-migration/02-CONTEXT.md` — D-01..D-04 plugin patterns to mirror

### New dependency
- `nodriver` Python package — pin a known-good version (researcher verifies pip index, falls back to latest stable). nodriver is the official successor to undetected-chromedriver, async-native, CDP-direct.

</canonical_refs>

<specifics>
## Specific Implementation Notes

### Target plugin file layout

```
plugins/
  shopbot_plugin_amazon.py     # Selenium (Phase 2)
  shopbot_plugin_bestbuy.py    # Selenium (Phase 2)
  shopbot_plugin_walmart.py    # nodriver (Phase 6) — high risk autobuy
  shopbot_plugin_target.py     # nodriver (Phase 6) — high risk autobuy
  shopbot_plugin_gamestop.py   # nodriver (Phase 6) — CAPTCHA pause
  shopbot_plugin_squareenix.py # nodriver (Phase 6)
  shopbot_plugin_newegg.py     # nodriver (Phase 6)
  example_plugin.py            # not auto-loaded
  PLUGIN_DEV.md
```

### Risky auto-buy gate (D-02) pattern per plugin

```
class WalmartPlugin(RetailerPlugin):
    domain_pattern = ["walmart.com"]
    login_at_startup = False

    def __init__(self, *, platform_config, cvv, ...):
        self._riskyAutoBuyEnabled = os.environ.get("SHOPBOT_ENABLE_RISKY_AUTOBUY") == "true"
        # ... nodriver init

    async def auto_buy(self, url, config):
        if not self._riskyAutoBuyEnabled:
            writeLog(
                f"Walmart auto_buy skipped: set SHOPBOT_ENABLE_RISKY_AUTOBUY=true to enable",
                "WARNING",
            )
            return False
        # ... actual purchase flow
```

### Pitfalls to encode as must_haves

1. nodriver and Selenium plugins coexist in the same registry. The ABC type constraint on `self.driver` is NONE. Tests must verify nodriver plugins instantiate without Selenium imports and vice versa.
2. `SHOPBOT_ENABLE_RISKY_AUTOBUY` is read in `__init__` (env-at-init pattern, mirrors Phase 5 D-04). NOT inside `auto_buy()`. Test confirms.
3. `build_driver(headless=True)` adds `--headless=new` (modern headless), NOT `--headless` alone (deprecated). Test asserts the exact flag string.
4. `random.uniform(min_delay, max_delay)` requires min_delay <= max_delay. Pydantic validator on `PlatformConfig` enforces.
5. nodriver's async lifecycle: `await Browser.start()` must complete BEFORE the plugin returns from `__init__` or the 1.5s stagger from Phase 4 ASYNC-02 becomes meaningless. Research confirms whether nodriver allows blocking start() inside `__init__` via `asyncio.run`, or whether plugins need an `async def init_driver()` separate from `__init__`. If the latter: the discover_async loop calls `await plugin.init_driver()` after instantiation, before next stagger sleep.
6. Walmart auto_buy logs a one-time INFO note about PerimeterX risk on first call, NOT on every call (use `self._walmartRiskNoted = False` flag).
7. GameStop CAPTCHA `input()` runs inside the plugin method, which itself runs inside `asyncio.to_thread` in the orchestrator. So input() only blocks the worker thread, not the event loop. Confirm by tests.
8. UA rotation: `random.choice(user_agents)` on EACH `build_driver` call, not cached at module load. Different driver builds in the same session get different UAs.
9. Headless mode and OTP: Amazon's amz_sign_in uses input() — incompatible with headless. The Phase 1 docs already say Amazon login requires manual passkey/OTP. Setting `platforms.amazon.headless: true` should produce a clear startup error like "Amazon plugin does not support headless mode (requires manual OTP)".
10. NewEgg / Square Enix / GameStop with auto_buy enabled MUST integrate with the Phase 5 notification system the same way Amazon/BestBuy do — the orchestrator puts a "purchased" NotificationEvent after the plugin's auto_buy returns successfully. No plugin-level notification calls.

</specifics>

<deferred>
## Deferred Ideas

- Walmart PerimeterX/HUMAN deep-bypass research — flag in researcher findings; deep mitigation work is its own follow-up phase
- Target Akamai bypass — same; v2 if user demands it
- nodriver swap for Amazon and BestBuy — defer to a future hardening phase; Selenium is working
- Per-plugin proxy rotation — out of scope for v1
- Mobile UA strings — UA list should be desktop Chrome only for v1
- Session cookie persistence across restarts — out of scope
- Plugin-level retry policy on availability check (currently the orchestrator's gather + log handles failures) — v2 if needed
- Walmart / Target check-only mode WITH explicit UI to disable auto_buy at the plugin level — the env-var gate covers this for v1

</deferred>

*Phase: 06-platform-expansion*
*Context gathered: 2026-05-15 via /gsd-discuss-phase 6*
