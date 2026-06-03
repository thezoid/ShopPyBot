# Phase 6: Platform Expansion - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Add five new platform plugins (Walmart, Target, GameStop, Square Enix, NewEgg) that load through the existing registry with no core edits, and add per-platform anti-detection configuration: random-jitter check intervals (min/max delay), per-platform headless toggle, and rotating user agents. Covers PLG-04..PLG-08 and ANTI-01..ANTI-03.

Reality note (scope honesty): the five plugins target live, bot-protected retail sites whose DOM selectors cannot be verified from this environment. They are delivered as best-effort scaffolds with researched selectors, a documented anti-detection risk level, and TODO-verify-live markers. The verifiable deliverables this phase OWNS are: registry loads all five with no core changes (SC1), per-platform jitter (SC2), per-platform headless in one process (SC3), and the risk documentation (SC4). Live purchase success on these sites is explicitly out of scope and not a success criterion.

NOT in scope: making the live auto-buy flows actually defeat PerimeterX/Akamai/etc.; proxy rotation / fingerprint spoofing (PROJECT.md out-of-scope); a plugin marketplace.
</domain>

<decisions>
## Implementation Decisions

### New-Plugin Implementation Depth (PLG-04..08)
- Each plugin is a single self-contained `plugins/shopbot_plugin_<name>.py` subclassing RetailerPlugin v2, loaded by the registry with NO core edits (SC1).
- check_availability and auto_buy implemented with researched best-effort selectors, each carrying a `# TODO: verify selectors against live <site>` marker (selectors cannot be live-verified here).
- auto_buy is implemented for Walmart, GameStop, Square Enix, NewEgg; for Target, checkout is labeled experimental (Akamai blocks headless consistently, PLG-05). High-risk auto_buy paths log an explicit "experimental: may be blocked by <protection>" WARNING before attempting.
- Each plugin sets its `domain_patterns` (e.g. walmart.com, target.com, gamestop.com, square-enix-games.com / store.na.square-enix-games.com, newegg.com — researcher confirms exact hosts).

### Per-Platform Anti-Detection Config (ANTI-01, ANTI-02, ANTI-03)
- Extend the per-platform config (platforms.<name>) with: `min_delay`, `max_delay` (seconds, for jitter), `headless` (bool), and optional `user_agents` (list, per-platform override).
- ANTI-01 jitter: the orchestrator sleeps `random.uniform(min_delay, max_delay)` between a plugin's poll cycles (replaces the single shared interval for plugins that set these; falls back to the shared poll_interval otherwise). Setting walmart min_delay=8/max_delay=15 yields 8-15s random intervals with no code change (SC2).
- ANTI-03 headless: each plugin's setup() reads its own `headless` flag and passes it to nodriver; different platforms can run headless vs visible in the SAME process (SC3).
- ANTI-02 rotating user agents: a configurable UA list (a global default pool in config plus optional per-platform `user_agents` override); a UA is selected/rotated per plugin browser session and applied in setup().
- Secrets (any platform credentials) remain env-only per Phase 1; anti-detection settings are non-secret config.

### Anti-Detection Risk Documentation (PLG-04/05/06, SC4)
- Each plugin's module docstring declares its anti-detection risk level + the reason (e.g. Walmart: high, PerimeterX/HUMAN Security; Target: high/experimental, Akamai headless block; GameStop: medium, checkout CAPTCHA; Square Enix: medium; NewEgg: medium). Researcher refines the levels/reasons.
- Each new platform also appends a row to the per-platform risk table in the repo-root SECURITY.md created in Phase 3 (single source of truth for risk ratings).

### Claude's Discretion
- Exact CSS/XPath selectors (best-effort, TODO-marked), the UA pool contents, how jitter integrates with the existing poll loop (per-plugin override vs shared fallback), the per-platform config submodel field names, and whether headless/UA live on each PlatformConfig vs a shared sub-block, provided the locked decisions hold.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `plugins/shopbot_plugin_amazon.py` + `plugins/shopbot_plugin_bestbuy.py` (Phase 2): the structural template for all five new plugins (async nodriver, self.driver in setup(), domain_patterns, no global driver).
- `plugins/example_plugin.py` + `plugins/PLUGIN_DEV.md` (Phase 2): the contributor skeleton the new plugins follow.
- `core/registry.py`: discovers shopbot_plugin_*.py automatically — the five new files load with zero core edits (SC1).
- `core/orchestrator.py` (Phase 4): per-plugin poll loop + 1.5s stagger + run_in_executor — the jitter sleep slots into the per-plugin loop here; setup() stagger already exists.
- `core/config_schema.py`: AppConfig.platforms (PlatformsConfig with amazon/bestbuy). Extend with the five new platforms + the anti-detection fields (min_delay/max_delay/headless/user_agents). NOTE: PlatformsConfig is a fixed model (the community-extensibility gap deferred in Phase 2) — adding five first-party platforms here is a core edit to AppConfig, which is fine for first-party platforms; community plugins still await the per-platform-config phase.
- `SECURITY.md` (Phase 3): per-platform risk table to append rows to.
- nodriver: headless + user-agent are set via browser start options in setup().

### Established Patterns
- One nodriver Browser per plugin; build in async setup() never __init__ (Phase 2/4).
- Secrets env-only, never logged (Phase 1).
- Anti-detection v1 scope: per-platform delays, rotating UAs, headless toggle (PROJECT.md). Proxy/fingerprint spoofing is explicitly out of scope.

### Integration Points
- New plugins drop into plugins/; registry auto-loads them.
- Jitter consumed in orchestrator per-plugin loop; headless + UA consumed in each plugin's setup().
- Risk docs: plugin docstrings + SECURITY.md table.
</code_context>

<specifics>
## Specific Ideas

- SC2 is config-only: walmart min_delay=8/max_delay=15 must change interval behavior with NO code edit — the jitter must read config at runtime.
- SC3 must show mixed headless/visible in one process (e.g. amazon headless:false visible while others headless).
- SC4 names specific protections: Walmart PerimeterX/HUMAN Security; Target Akamai headless blocking — these exact phrases must appear in the docs.
- The five plugins are best-effort scaffolds; live selector/auto-buy success is NOT a success criterion (documented experimental where risky).
</specifics>

<deferred>
## Deferred Ideas

- Making live auto-buy actually defeat PerimeterX/Akamai/CAPTCHA (advanced anti-detection — out of v1 scope per PROJECT.md).
- Proxy rotation / browser fingerprint spoofing (PROJECT.md out-of-scope).
- Community per-platform config extensibility without core AppConfig edits (the Phase-2 deferred gap; first-party platforms added here directly).
- GitHub wiki plugin registry with difficulty ratings (a docs/wiki task, not code).
</deferred>

---

*Phase: 6-platform-expansion*
*Context gathered: 2026-06-03*
