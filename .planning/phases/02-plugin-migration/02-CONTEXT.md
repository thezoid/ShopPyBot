# Phase 2: Plugin Migration - Context

**Gathered:** 2026-05-12
**Status:** Ready for research and planning
**Source:** /gsd-discuss-phase 2 (interactive)

<domain>
## Phase Boundary

Phase 2 migrates the existing `amazon_bot.py` and `bestbuy_bot.py` modules to the `RetailerPlugin` ABC contract locked in Phase 1 (`plugin_base.py`, `PLUGIN_API_VERSION = 1`). The plugins land in `plugins/` as `shopbot_plugin_amazon.py` and `shopbot_plugin_bestbuy.py`, discovered at startup by an `importlib`-based registry, and routed by URL based on a `domain_pattern` class attribute on each plugin. A reference `example_plugin.py` and a `plugins/PLUGIN_DEV.md` contributor guide ship with this phase so external developers have a working template by Phase 2 close.

Six in-scope requirements: CORE-03, CORE-04, CORE-08, PLG-01, PLG-02, PLG-03.

Out of scope (defer to Phase 3 or later):
- CONTRIBUTING.md, SECURITY.md, GitHub templates (Phase 3 — Community Documentation)
- Async/concurrent plugin execution (Phase 4 — Async Orchestrator). Phase 2 keeps the existing blocking `while True` polling loop; plugins are invoked sequentially.
- New platform plugins (Walmart, Target, GameStop, Square Enix, NewEgg) — Phase 6
- Selenium → nodriver swap — Phase 6 (Selenium retained for Phase 2 continuity)

</domain>

<decisions>
## Implementation Decisions

### Plugin URL routing (CORE-04)

**D-01: `domain_pattern` is a list of hostname strings.**
- Each plugin class declares: `domain_pattern: list[str] = ["amazon.com", "amzn.to"]`
- Matching helper performs `urlparse(url).netloc.endswith(pattern)` for each entry
- Rationale: simple for contributors (no regex literacy required), covers URL shorteners and per-region TLDs cleanly, no regex injection or runtime compile cost
- Empty `domain_pattern` is a configuration error and surfaces as an import-time validation failure

### Existing module transition (PLG-01, PLG-02)

**D-02: Hard cut. Delete `amazon_bot.py` and `bestbuy_bot.py` once the new plugins pass import + smoke tests.**
- New plugins absorb all logic from the old modules. No fallback path.
- `main.py` imports the registry only; no direct knowledge of Amazon or BestBuy
- Rationale: the open-source release goal demands a clean public surface; carrying parallel implementations doubles maintenance and contradicts the "plugin framework" identity
- Existing `tests/test_*` references to the old modules are updated or deleted as part of this phase

### Login lifecycle (supports PLG-01 + Amazon OTP behavior)

**D-03: Per-plugin opt-in. Each plugin declares `login_at_startup: bool = False` (class attribute).**
- Registry iterates plugins on startup and calls `.login()` on every plugin where `login_at_startup is True`
- Amazon opts in (interactive OTP runs once at startup, blocks polling until complete)
- BestBuy opts in (existing behavior: sign-in at startup)
- Check-only plugins, or plugins that don't need auth, leave `login_at_startup = False` and `.login()` is never called
- Rationale: keeps the interactive OTP UX from Phase 1 intact, doesn't force every plugin to implement a no-op `login()`, and doesn't stall first restock detection behind a lazy login

### Plugin failure isolation (CORE-03)

**D-04: Strict for referenced URLs, lenient for unreferenced plugins. Two-phase load.**
- Phase A (discovery): registry walks `plugins/shopbot_plugin_*.py` and tries to import each. Import failures are caught, logged as warnings, and the failed plugin is skipped. Loaded plugin instances are collected.
- Phase B (coverage check): after discovery, the registry compares every URL in `config.platforms.<name>.items[]` (or `config.available.items[]` per Phase 1 schema) against the loaded plugins' `domain_pattern` lists. Any item URL with no matching plugin causes a hard-fail with an actionable error naming the URL and the expected plugin filename (e.g., "URL https://amazon.com/dp/XYZ has no plugin. Expected plugins/shopbot_plugin_amazon.py to load — check the warning log above for the import error.").
- Rationale: experimental plugins sitting in `plugins/` while broken don't block the bot; a typo or missing dep on a plugin the user actually needs surfaces with a clear error pointing at the import failure.

### Plugin discovery convention (locked in PROJECT.md)

- Naming: `plugins/shopbot_plugin_*.py` only. Files not matching the prefix emit a warning log (e.g., `plugins/example_plugin.py` is ignored by discovery on purpose — it serves as the template).
- Hidden / dunder files (`__init__.py`, `_helpers.py`, `.something.py`) are ignored without warning.
- One plugin class per file. The registry expects exactly one `RetailerPlugin` subclass in the module.

### Claude's Discretion

The planner / researcher decides:

- **Registry module name and shape** — likely `plugin_registry.py` with a `discover(plugins_dir: Path) -> list[RetailerPlugin]` function and a `route_url(url: str, registry: list) -> RetailerPlugin | None` helper, but exact API is open
- **How registry surfaces in `main.py`** — function call at startup that returns the list, vs module-level singleton populated on first access
- **`example_plugin.py` body** — a working "echo" plugin against a safe target (e.g., httpbin.org or a local fixture) vs pure stubs with TODO comments. Whichever is more useful to a first-time contributor.
- **`plugins/PLUGIN_DEV.md` depth** — Phase 2 owns the technical contract reference (ABC methods, `domain_pattern`, `login_at_startup`, file naming, test expectations). Higher-level "how to contribute to the project" content lives in `CONTRIBUTING.md` (Phase 3) and should be linked, not duplicated.
- **BestBuy `update_item_purchased()` integration point** — PLG-02 fixes the missing call. Place it inside `auto_buy()` after a successful purchase confirmation, mirroring Amazon's existing flow.
- **Plugin instantiation timing** — at discovery (registry holds instances) vs lazy. Picking at-discovery keeps WebDriver startup deterministic (per PLG-03) and matches D-03's startup login flow.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 outputs (locked contracts)
- `plugin_base.py` — `RetailerPlugin` ABC, `PLUGIN_API_VERSION = 1`. Plugins in this phase subclass it. ABC method signatures DO NOT take a `driver` parameter (Phase 1 D-01); driver lives on `self.driver`.
- `config_schema.py` — `AppConfig` Pydantic schema. Plugins read credentials from `config.platforms[<name>].credentials` and item lists from the per-platform structure.
- `driver.py` — `build_driver(driver_path, log_path)` factory. Each plugin's `__init__` calls this to construct its own `self.driver` (PLG-03).
- `credentials.py` — `collect_cvvs(app_config)` returns the CVV dict that plugins consume during `auto_buy`.
- `logger.py` — `writeLog(message, type)` + `configure(level)`. Plugins use `writeLog` for all output.

### Project decisions
- `.planning/PROJECT.md` — plugin naming convention, ABC scope, "drop-in" identity, retention of Selenium for Phase 2
- `.planning/REQUIREMENTS.md` — CORE-03, CORE-04, CORE-08, PLG-01, PLG-02, PLG-03 wording (authoritative for must_haves)
- `.planning/phases/01-foundations-security/01-CONTEXT.md` — Phase 1 D-01 (no driver param on ABC methods)
- `.planning/phases/01-foundations-security/*-SUMMARY.md` — what Phase 1 actually shipped (use these to verify integration points)

### Existing source to migrate (will be deleted after migration per D-02)
- `amazon_bot.py` — current Amazon implementation (`check_amazon_item`, `amz_sign_in`, `auto_buy_amazon_item`)
- `bestbuy_bot.py` — current BestBuy implementation (`check_bestbuy_item`, `bb_sign_in`, `auto_buy_bestbuy_item`)

### Pre-existing technical debt (Phase 2 cleanup window)
- `tests/test_utils.py` — pre-existing pygame collection error; Phase 2 will need to decide whether to fix or delete during plugin migration (utils.py may move into plugins)
- `_deprecated/` folder still tracked with placeholder credentials — recommend scrubbing before public release (flagged in Phase 1 VERIFICATION.md)

</canonical_refs>

<specifics>
## Specific Implementation Notes

- `domain_pattern` matching helper (location TBD by planner — likely `plugin_registry.py`):
  ```
  def match_url(url, plugin):
      netloc = urlparse(url).netloc.lower()
      return any(netloc.endswith(p.lower()) for p in plugin.domain_pattern)
  ```
- BestBuy `update_item_purchased()` call site: inside `auto_buy()` after the purchase-confirmation page assertion; pattern lifted from Amazon's existing flow.
- Existing `main.py` poll loop currently dispatches by `if "amazon" in url: ... elif "bestbuy" in url: ...`. After Phase 2, that block is replaced by `plugin = route_url(item.url, registry); if plugin: plugin.check_availability(item.url)`.
- `example_plugin.py` lives at `plugins/example_plugin.py`. Discovery skips it because the filename doesn't start with `shopbot_plugin_`. A contributor copies it to `plugins/shopbot_plugin_<name>.py` to start a new plugin.

</specifics>

<deferred>
## Deferred Ideas

- Async/concurrent plugin polling — Phase 4 (ASYNC-01..05)
- nodriver replacement for Selenium — Phase 6
- Plugin hot-reload (watch `plugins/` for changes during runtime) — not on roadmap, capture as v2 backlog if desired
- Plugin sandboxing (isolating filesystem / network per plugin) — not on roadmap
- Per-plugin anti-detection difficulty ratings exposed in registry — v2 (per REQUIREMENTS.md v2 backlog)

</deferred>

*Phase: 02-plugin-migration*
*Context gathered: 2026-05-12 via /gsd-discuss-phase 2*
