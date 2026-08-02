# Phase 33: Config Refactor - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous). Infrastructure/refactor phase with two real design decisions — pre-decided at Claude's discretion with a risk-minimizing rationale; exact mechanics deferred to research.

<domain>
## Phase Boundary

Platform delay-config fields have ONE canonical name across every plugin (CFG-01), old configs still load via a back-compat shim, and a plugin can declare its own per-platform config section with zero edits to the core config-schema file (CFG-02).

**Sequencing (hard):** CFG-01 lands before CFG-02 — both touch the same config-schema surface (`core/config_schema.py`), and CFG-02 builds on the harmonized field set.

**In scope:** unify the delay-field naming; a back-compat shim mapping legacy names → canonical; a generic per-platform config declaration mechanism; tests proving both old- and new-style configs load and that a new undeclared plugin section validates without core schema edits.

**Out of scope:** changing actual delay VALUES/timing behavior (the refactor must be behavior-preserving); live-selector tuning for community plugins (operator debt).
</domain>

<decisions>
## Implementation Decisions

### CFG-01 Canonical delay-field scheme — DECIDED: `delay_seconds` / `delay_jitter`
- Canonical = `delay_seconds` / `delay_jitter` (the scheme Amazon + BestBuy already use).
- **Rationale (risk-minimizing):** canonical = the field names Amazon/BestBuy already declare, minimizing churn on the live-tested plugins. Convert the 5 community plugins from `min_delay`/`max_delay`.
- **CORRECTION (post-research, Assumption A1 — supersedes the original premise):** research proved Amazon/BestBuy's `delay_seconds`/`delay_jitter` fields are DEAD — consumed by zero runtime code; those two plugins actually poll on flat `poll_interval` (30s) via the shared `_get_plugin_sleep`. So the original "keeps Amazon/BestBuy behavior UNCHANGED" claim is FALSE. Unifying the consumed scheme necessarily activates jitter for Amazon/BestBuy (flat 30s → `delay_seconds`(30) + `uniform(0, delay_jitter=10)` = 30-40s).
  - **DECISION (Option A, accepted at Claude's discretion — grey area, operator was away):** ACCEPT the jitter activation for Amazon/BestBuy. It affects only availability-poll cadence (NOT checkout/DOM/timing-sensitive paths), is an anti-detection improvement over flat polling, activates the plugins' own long-declared defaults, and keeps `_get_plugin_sleep` uniform across all 7 platforms (no special-casing). This is a documented, scoped behavior change — update `tests/test_orchestrator_jitter.py::test_fallback_for_amazon_shaped_config` to assert the new jittered behavior, and record it as an operator-UAT item (live Amazon/BestBuy poll cadence changed). The "behavior-preserving" HARD constraint remains strict for the 5 community plugins (their effective delay distribution must be identical via the shim mapping).
- **Back-compat shim:** a config that uses the legacy `min_delay` / `max_delay` fields (or any user config still on the old names) must still load and produce equivalent runtime timing. Implement via a pydantic mechanism (validation alias / model pre-validator / `AliasChoices`) that maps legacy → canonical. **RESEARCH QUESTION (primary):** determine the exact behavior-preserving mapping. `min_delay`/`max_delay` defines a uniform range; `delay_seconds`/`delay_jitter` is base+jitter. Read how BOTH the Amazon/BestBuy plugins (consume delay_seconds/delay_jitter) AND the 5 community plugins (consume min_delay/max_delay) actually compute their wait, then define the mapping that preserves each community plugin's effective delay distribution when its config is expressed in canonical fields. The shim must be proven by a test loading an old-style (min_delay/max_delay) config AND a new-style (delay_seconds/delay_jitter) config and asserting both resolve correctly.

### CFG-02 Generic per-platform config — DECIDED: allow plugin-declared sections without core schema edits
- A plugin can add a NEW per-platform config section that loads + validates WITHOUT editing `core/config_schema.py`. Today `PlatformsConfig` hard-codes all 7 platform models — CFG-02 removes that as a hard requirement for new platforms.
- **RESEARCH QUESTION (secondary):** choose the cleanest mechanism against the existing pydantic `PlatformsConfig`. Candidate approaches: (a) `PlatformsConfig` with `model_config = ConfigDict(extra="allow")` so unknown platform keys pass through, plus a plugin-side config model the plugin validates itself; (b) a per-platform config registry where plugins register their pydantic model at import/discovery time and the loader validates against the registry; (c) a generic `dict[str, PlatformConfigBase]` with a base model plugins subclass. Prefer the approach that: keeps existing 7 platforms' validation intact, requires zero core edits for a new plugin, and fits the existing plugin-discovery pattern (`platform_key`). Prove with a test/fixture plugin declaring a brand-new section that loads + validates with the core schema file untouched.
- Preserve the existing SquareEnix "no underscore" key convention and all current platform validation.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/config_schema.py` — pydantic models: `AmazonPlatformConfig`/`BestBuyPlatformConfig` (delay_seconds/delay_jitter), `Walmart/Target/GameStop/SquareEnix/Newegg PlatformConfig` (min_delay/max_delay), aggregated in `PlatformsConfig`; `AppConfig(BaseSettings)` top-level.
- Plugin discovery uses `platform_key` (e.g. `squareenix` no underscore) — the mechanism CFG-02 should hook into.
- Existing config-schema test suite (must stay green).

### Established Patterns
- Retry uses `backoff_base`/`backoff_jitter` (base+jitter) — the delay_seconds/delay_jitter canonical choice is consistent with this existing base+jitter idiom.
- getattr-safe config reads throughout (plugins tolerate missing config).
- Pydantic v2 (BaseModel / BaseSettings, `Field`, `model_config`).

### Integration Points
- `core/config_schema.py` (canonical fields + shim + generic section), the 5 community plugin files (field-name reads), the config loader, `sample.config.yml` (document canonical names + note legacy still works), tests.
</code_context>

<specifics>
## Specific Ideas

- Behavior-preserving is the hard constraint: no config's effective delay distribution may change. The shim + community-plugin conversion must be timing-equivalent, verified by tests.
- Update `sample.config.yml` to use canonical names and add a comment that legacy names still load via the shim.
- CFG-01 strictly before CFG-02.
</specifics>

<deferred>
## Deferred Ideas

- Community-plugin live-selector tuning (operator debt, unrelated to config-field naming).
- Broader config-schema redesign beyond the two requirements.
</deferred>
