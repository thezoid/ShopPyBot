# Phase 33: Config Refactor - Research

**Researched:** 2026-07-02
**Domain:** Pydantic v2 config-schema field unification + back-compat shim; generic per-platform config extension point
**Confidence:** HIGH (all claims below are `[VERIFIED: local code]` — read directly from the repository — or `[VERIFIED: local test]` — proven live against the installed `pydantic==2.13.3` / `pydantic-settings==2.14.2`, matching `requirements.txt`. No external package research was needed; this phase touches only already-installed, already-pinned dependencies.)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**CFG-01 Canonical delay-field scheme — DECIDED: `delay_seconds` / `delay_jitter`**
- Canonical = `delay_seconds` / `delay_jitter` (the scheme Amazon + BestBuy already use).
- Rationale (risk-minimizing): Amazon and BestBuy are the two LIVE-TESTED plugins with proven
  timing behavior. Choosing their existing field names as canonical leaves those two plugins
  UNCHANGED (zero risk to proven behavior) and limits code changes to the 5 non-live-verified
  community plugins (Walmart, Target, GameStop, SquareEnix, NewEgg), which currently use
  `min_delay` / `max_delay`. This overrides the "majority uses min_delay/max_delay (5/7)" and
  the source comment labeling delay_seconds/delay_jitter "legacy" — protecting proven live
  behavior is the stronger criterion.
- Back-compat shim: a config that uses the legacy `min_delay` / `max_delay` fields (or any user
  config still on the old names) must still load and produce equivalent runtime timing.
  Implement via a pydantic mechanism (validation alias / model pre-validator / `AliasChoices`)
  that maps legacy → canonical. RESEARCH QUESTION (primary): determine the exact
  behavior-preserving mapping. `min_delay`/`max_delay` defines a uniform range;
  `delay_seconds`/`delay_jitter` is base+jitter. Read how BOTH the Amazon/BestBuy plugins
  (consume delay_seconds/delay_jitter) AND the 5 community plugins (consume min_delay/max_delay)
  actually compute their wait, then define the mapping that preserves each community plugin's
  effective delay distribution when its config is expressed in canonical fields. The shim must
  be proven by a test loading an old-style (min_delay/max_delay) config AND a new-style
  (delay_seconds/delay_jitter) config and asserting both resolve correctly.

  > **Research finding surfaced to the planner:** the premise "leaves those two plugins
  > UNCHANGED" holds for the plugin *files* (verified — zero lines touched) but not
  > automatically for the orchestrator's poll-cadence mechanism once field names are unified.
  > See "CRITICAL FINDING" and Assumption A1 below — this needs an explicit decision before
  > implementation.

**CFG-02 Generic per-platform config — DECIDED: allow plugin-declared sections without core
schema edits**
- A plugin can add a NEW per-platform config section that loads + validates WITHOUT editing
  `core/config_schema.py`. Today `PlatformsConfig` hard-codes all 7 platform models — CFG-02
  removes that as a hard requirement for new platforms.
- RESEARCH QUESTION (secondary): choose the cleanest mechanism against the existing pydantic
  `PlatformsConfig`. Candidate approaches: (a) `PlatformsConfig` with
  `model_config = ConfigDict(extra="allow")` so unknown platform keys pass through, plus a
  plugin-side config model the plugin validates itself; (b) a per-platform config registry
  where plugins register their pydantic model at import/discovery time and the loader
  validates against the registry; (c) a generic `dict[str, PlatformConfigBase]` with a base
  model plugins subclass. Prefer the approach that: keeps existing 7 platforms' validation
  intact, requires zero core edits for a new plugin, and fits the existing plugin-discovery
  pattern (`platform_key`). Prove with a test/fixture plugin declaring a brand-new section that
  loads + validates with the core schema file untouched.
- Preserve the existing SquareEnix "no underscore" key convention and all current platform
  validation.

**Sequencing (hard):** CFG-01 lands before CFG-02 — both touch the same config-schema surface
(`core/config_schema.py`), and CFG-02 builds on the harmonized field set.

**Hard constraint:** Behavior-preserving — the refactor must not change actual delay VALUES/
timing behavior. Out of scope: live-selector tuning for community plugins (operator debt).

### Claude's Discretion
- Exact shim mechanics (AliasChoices vs. `model_validator(mode="before")`) — resolved by this
  research: `model_validator(mode="before")` is required (see CFG-01 section below).
- Exact CFG-02 mechanism among the three candidates — resolved by this research: candidate (a),
  `extra="allow"` + plugin-side validation helper (see CFG-02 section below).

### Deferred Ideas (OUT OF SCOPE)
- Community-plugin live-selector tuning (operator debt, unrelated to config-field naming).
- Broader config-schema redesign beyond the two requirements (CFG-01, CFG-02).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CFG-01 | Platform delay-config field names are unified across all plugins (`delay_seconds/delay_jitter` vs `min_delay/max_delay`) with a back-compat shim for existing configs | Exact consumption formulas quoted with file:line for both schemes (found: `delay_seconds`/`delay_jitter` is currently unconsumed dead config); exact algebraic shim mapping (`delay_seconds := min_delay`, `delay_jitter := max_delay - min_delay`) proven distribution-identical to the legacy formula; `model_validator(mode="before")` shim mechanism verified live against installed pydantic 2.13.3 (precedence, clobber-safety, and validation-error preservation all confirmed); full regression surface of call sites and tests enumerated; CRITICAL FINDING flagged (Assumption A1) requiring an explicit planner/human decision on the Amazon/BestBuy orchestrator-cadence side effect before task-writing |
| CFG-02 | A plugin can declare its own per-platform config section without editing core schema (generic per-platform config in schema + loader) | Construction-order evidence (`AppConfig()` before `PluginRegistry()`, two call sites) rules out the registry-based candidate (b) at low cost; `dict[str, PlatformConfigBase]` candidate (c) shown to break 5+ existing call sites; recommended candidate (a) (`extra="allow"` + `get_platform_config()` helper) verified live to preserve strict validation for the 7 existing platforms while allowing an undeclared platform section to pass through and be validated by the plugin itself, with a concrete code shape and a fixture-plugin test pattern provided |

</phase_requirements>

## Summary

This phase has one finding that changes the shape of the plan and must be surfaced to the
planner before task-writing: **`delay_seconds`/`delay_jitter` are currently dead config.**
`AmazonPlatformConfig`/`BestBuyPlatformConfig` declare these two fields
(`core/config_schema.py:71-72,81-82`) but **zero runtime code reads them** — confirmed by a
repo-wide grep across `core/` and `plugins/`. The only place any delay field is consumed at
runtime is `_get_plugin_sleep()` in `core/orchestrator.py:292-312`, and it reads
`min_delay`/`max_delay` only. Because `AmazonPlatformConfig`/`BestBuyPlatformConfig` never
declared those two attribute names, `_get_plugin_sleep` falls back to the flat, non-jittered
`poll_interval` for Amazon/BestBuy today — a fact locked in by an existing test
(`tests/test_orchestrator_jitter.py::test_fallback_for_amazon_shaped_config`).

CONTEXT.md's stated rationale — "canonical = delay_seconds/delay_jitter... leaves those two
plugins UNCHANGED" — is true for the plugin **files** (zero lines touched in
`shopbot_plugin_amazon.py`/`shopbot_plugin_bestbuy.py`, verified) but is **not automatically
true for the orchestrator's poll-cadence mechanism**, because once the 5 community models
are renamed to the same canonical field names, `_get_plugin_sleep` must read those canonical
names to keep working for them — and Amazon/BestBuy already declare those same names. See
"CRITICAL FINDING" below for the exact mechanics and the recommended resolution.

The exact behavior-preserving shim for the 5 community plugins **is** achievable with zero
distribution drift: `delay_seconds := min_delay`, `delay_jitter := max_delay - min_delay`,
consumed as `delay_seconds + random.uniform(0, delay_jitter)` — algebraically identical to
today's `random.uniform(min_delay, max_delay)`, and it matches the codebase's own established
base+jitter idiom (`core/retry.py:35-44` `compute_delay`, used by `backoff_base`/`backoff_jitter`).
This requires a `model_validator(mode="before")`, not a field-level `AliasChoices` — verified
live: `AliasChoices` can rename one key to one field, but `delay_jitter` is a **derived** value
from two legacy keys, which alias resolution cannot express.

For CFG-02, the existing `PlatformsConfig` is a flat `BaseModel` with `extra` unset (defaults
to `"ignore"`, i.e. an unknown `platforms.<newplatform>` YAML section is silently dropped
today — this is the literal bug CFG-02 must fix). Construction order is fixed and cannot be
cheaply reordered: `AppConfig()` is built **before** `PluginRegistry()` in both `main.py:27`→
`core/orchestrator.py:771` and `core/service.py:39`→`core/service.py:131` — so any mechanism
that requires plugins to register a schema **before** `AppConfig()` validates (candidate (b),
a plugin-registered-model registry) would require inverting this order across three call
sites. Candidate (a) — `PlatformsConfig` with `ConfigDict(extra="allow")` plus a small
plugin-side coercion helper — requires none of that, is a single-line schema change, and was
verified live to leave the 7 existing platforms' strict validation completely untouched.

**Primary recommendation:** Implement the shim as a shared `model_validator(mode="before")`
helper applied to the 5 community platform models (rename fields to `delay_seconds`/
`delay_jitter`); update `_get_plugin_sleep` to read the canonical fields uniformly; add
`ConfigDict(extra="allow")` to `PlatformsConfig` for CFG-02, paired with a new
`RetailerPlugin.get_platform_config(model_cls)` helper in `core/plugin_base.py` so a new
plugin can declare and validate its own section with zero core-schema edits. Bring the
Amazon/BestBuy orchestrator-cadence side effect to the planner as an explicit, scoped decision
point (see Assumptions Log A1) rather than silently resolving it either way.

## Architectural Responsibility Map

This codebase is a single-process bot (not a browser/API/CDN multi-tier app), so tiers are
adapted to its actual layers:

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Canonical delay field declaration | Config Schema (`core/config_schema.py`) | — | Pydantic models are the single source of truth for field names/validation |
| Legacy→canonical field shim | Config Schema (`core/config_schema.py`) | — | `model_validator(mode="before")` runs at model-construction time, co-located with the fields it transforms |
| Delay consumption (poll-cadence jitter) | Runtime/Orchestrator (`core/orchestrator.py`) | — | `_get_plugin_sleep()` is the sole consumer; plugins never read delay fields directly |
| Per-platform config declaration (CFG-02) | Plugin Layer (`plugins/shopbot_plugin_*.py`) | Config Schema (passthrough only) | Plugin author owns their own model; core schema stays generic (`extra="allow"`), never edited per-plugin |
| Plugin discovery / config wiring | Core/Registry (`core/registry.py`) | Core/Config (`core/config_schema.py`) | `AppConfig()` build precedes `PluginRegistry()` construction — this ordering constrains which CFG-02 mechanism is feasible |

## Standard Stack

No new external dependencies are introduced by this phase. Both packages this phase relies on
are already installed and pinned.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pydantic` | 2.13.3 (pinned `requirements.txt:7`) `[VERIFIED: local install]` | Config models, field validation, `model_validator` | Already the project's schema layer; no alternative considered |
| `pydantic-settings` | 2.14.2 (pinned `requirements.txt:8`) `[VERIFIED: local install]` | `AppConfig(BaseSettings)`, YAML+env layered sources | Already in use; unaffected by this phase's changes |

### Supporting
None — this phase adds no new libraries.

### Alternatives Considered
Not applicable at the package level (no new packages). Mechanism-level alternatives for
CFG-02 are covered in "Architecture Patterns" below (this **is** the alternatives analysis
the phase needs).

**Installation:** none required.

## Package Legitimacy Audit

Not applicable — this phase installs no external packages. `slopcheck`/registry verification
was not run because there is nothing to verify.

## CFG-01: Exact Delay-Consumption Formulas (Research Question 1 — PRIMARY)

### Formula A — the 5 community plugins (Walmart, Target, GameStop, SquareEnix, Newegg)

`[VERIFIED: local code]` None of the 5 plugin files read `min_delay`/`max_delay` directly —
confirmed by grep across `plugins/*.py` (zero matches for any delay-field name outside
`core/`). The **only** consumer is:

```python
# core/orchestrator.py:292-312
def _get_plugin_sleep(plugin, poll_interval: float) -> float:
    try:
        platform_key = getattr(plugin, "platform_key", None)
        if not platform_key:
            return poll_interval
        platform_cfg = getattr(plugin.config.platforms, platform_key, None)
        if platform_cfg is None:
            return poll_interval
        min_delay = getattr(platform_cfg, "min_delay", None)
        max_delay = getattr(platform_cfg, "max_delay", None)
        if min_delay is None or max_delay is None:
            return poll_interval
        return random.uniform(min_delay, max_delay)
    except Exception:
        return poll_interval
```

Called from `run_plugin()` (`core/orchestrator.py:343,372`) as the `asyncio.sleep()` duration
between poll cycles for that plugin. **Formula A: `random.uniform(min_delay, max_delay)`** —
a uniform range, confirmed by `tests/test_orchestrator_jitter.py::test_jitter_in_range_for_walmart_config`
(walmart `min_delay=8.0, max_delay=15.0` → result always in `[8.0, 15.0]`).

### Formula B — Amazon/BestBuy's `delay_seconds`/`delay_jitter`

`[VERIFIED: local code]` Grep across `core/` and `plugins/` for `delay_seconds|delay_jitter`
returns **only the declarations** in `core/config_schema.py:71-72,81-82` (plus their mirror in
`sample.config.yml:37-41` and test fixtures). **No code path reads these attributes.** Amazon
and BestBuy's actual orchestrator poll-cadence today comes from `_get_plugin_sleep`'s fallback
branch, because `getattr(AmazonPlatformConfig_instance, "min_delay", None)` returns `None`
(the attribute does not exist on that model) — the function falls back to `poll_interval`
(`AppSettingsConfig.poll_interval`, default `30`, `core/config_schema.py:160`), a flat,
non-jittered value. This exact behavior is locked in by
`tests/test_orchestrator_jitter.py::test_fallback_for_amazon_shaped_config` (docstring: "Amazon
config lacking min/max_delay"). **There is no "Formula B" today — it is a no-op.**

### CRITICAL FINDING: the field-unification forces a choice that touches Amazon/BestBuy's runtime cadence

CFG-01 requires "ONE canonical name across every plugin." Achieving this means the 5
community models' fields are renamed `min_delay`→`delay_seconds`,
`max_delay`→`delay_jitter`-derived. Because `_get_plugin_sleep` currently distinguishes
"has jitter config" vs. "does not" purely by **attribute presence** (`getattr(..., None)`
returns `None` only because the attribute name doesn't exist on the model), and because
Amazon/BestBuy's models **already** declare `delay_seconds`/`delay_jitter` with real numeric
defaults, `_get_plugin_sleep` — once updated to read the canonical names so it keeps working
for the (renamed) community platforms — **will also start matching Amazon/BestBuy** for the
first time. There is no attribute-presence trick left to fall back on post-unification: every
one of the 7 platform models will declare both canonical fields.

Concretely, if `_get_plugin_sleep` is updated to read `delay_seconds`/`delay_jitter`
uniformly:
- **Before this phase:** Amazon/BestBuy poll cadence = flat `poll_interval` (default 30s, zero
  variance).
- **After a naive uniform rewire:** Amazon/BestBuy poll cadence = `delay_seconds +
  random.uniform(0, delay_jitter)` = `30 + uniform(0, 10)` = a jittered 30-40s range, using
  the values already sitting in the schema/`sample.config.yml` today.
- This is a genuine behavior change to a "live-tested, proven" plugin's timing, which the
  phase's hard constraint (behavior-preserving) and CONTEXT.md's explicit "leaves those two
  plugins UNCHANGED" both nominally forbid.

Two important mitigating facts, found in code, temper this:
1. **Zero lines change in `shopbot_plugin_amazon.py`/`shopbot_plugin_bestbuy.py`.** The
   affected surface is exclusively the orchestrator's *inter-poll-cycle* sleep (how often the
   bot re-checks availability), not any DOM/checkout timing inside a single check — the part
   of "proven live behavior" that actually matters for CAPTCHA/WAF/selector timing is
   untouched either way.
2. `AppSettingsConfig`'s own docstring already says: *"Per-platform jitter is Phase 6; do NOT
   add jitter fields here"* (`core/config_schema.py:156-158`) — i.e. `poll_interval` was
   always documented as the pre-per-platform-jitter fallback, superseded platform-by-platform
   as ANTI-01 rolled out. Wiring Amazon/BestBuy into the same mechanism the 5 community
   plugins already use is arguably *completing* that documented migration, not violating it.

**This is flagged as Assumption A1 in the Assumptions Log below — it needs an explicit
planner/human decision before implementation, not a silent resolution.** Both options are
given concrete code shapes so planning is not blocked either way:

- **Option A (recommended):** Update `_get_plugin_sleep` to read canonical
  `delay_seconds`/`delay_jitter` uniformly for all 7 platforms. Accept that Amazon/BestBuy
  gain orchestrator-level poll jitter for the first time (30–40s instead of flat 30s by
  default). Update/remove `test_fallback_for_amazon_shaped_config` accordingly (see
  "Regression Surface").
- **Option B (strict zero-change fallback):** Keep `_get_plugin_sleep`'s dispatch scoped to
  the 5 community `platform_key`s only (a small explicit set or a new opt-in marker field),
  leaving Amazon/BestBuy's `delay_seconds`/`delay_jitter` declared-but-inert exactly as today.
  This achieves byte-identical behavior but requires either a hardcoded platform-key
  allowlist in core orchestrator code (tension with CFG-02's "no core hardcoding for new
  platforms" spirit) or a new opt-in schema field, which is scope creep beyond a pure rename.

### Exact shim mapping (behavior-preserving, verified)

```
delay_seconds := min_delay
delay_jitter  := max_delay - min_delay
```

Applied with the consumption formula `delay_seconds + random.uniform(0, delay_jitter)`, this
is **algebraically identical** to `random.uniform(min_delay, max_delay)`:

```
delay_seconds + uniform(0, delay_jitter)
  = min_delay + uniform(0, max_delay - min_delay)
  = uniform(min_delay, max_delay)                    # exact, not approximate
```

This is exactly the codebase's own established idiom — `core/retry.py:35-44`:
```python
def compute_delay(attempt: int, policy: RetryPolicy, rng=random) -> float:
    base = policy.backoff_base ** attempt
    jitter = rng.uniform(0, policy.backoff_jitter)
    return base + jitter
```
CONTEXT.md's note that canonical naming "is consistent with this existing base+jitter idiom"
is confirmed correct at the formula level, not just the naming level.

### Pydantic v2 shim mechanism — verified live against pydantic 2.13.3

**`AliasChoices`/`validation_alias` alone is insufficient.** It can rename one source key to
one target field (e.g. `min_delay` → `delay_seconds` directly), but `delay_jitter` must be
*computed* from **two** legacy keys (`max_delay - min_delay`), which alias resolution cannot
express. A `model_validator(mode="before")` is required. Verified live (pydantic 2.13.3):

```python
def _shim_legacy_delay_fields(data: dict) -> dict:
    """Map legacy min_delay/max_delay -> canonical delay_seconds/delay_jitter.

    Only triggers when at least one legacy key is present AND neither canonical key
    is already present -- an explicit delay_seconds/delay_jitter value is NEVER
    clobbered (verified: explicit canonical wins even if legacy keys are also present).
    """
    if not isinstance(data, dict):
        return data
    has_legacy = "min_delay" in data or "max_delay" in data
    has_canonical = "delay_seconds" in data or "delay_jitter" in data
    if has_legacy and not has_canonical:
        import warnings
        warnings.warn(
            "config.yml: 'min_delay'/'max_delay' are deprecated; use "
            "'delay_seconds'/'delay_jitter' instead. See sample.config.yml.",
            DeprecationWarning,
            stacklevel=2,
        )
        data = dict(data)
        min_d = float(data.pop("min_delay", 8.0))
        max_d = float(data.pop("max_delay", 15.0))
        data["delay_seconds"] = min_d
        data["delay_jitter"] = max_d - min_d   # do NOT clamp -- let Field(ge=0.0) reject
                                                 # inverted/negative ranges naturally (see
                                                 # Pitfall: "clamping silently swallows
                                                 # validation errors" below)
    return data


class WalmartPlatformConfig(BaseModel):
    """Per-platform anti-detection config for Walmart (ANTI-01/02/03)."""

    delay_seconds: float = Field(default=8.0, ge=0.0)
    delay_jitter: float = Field(default=7.0, ge=0.0)
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)
    session_persistence: bool = False

    @model_validator(mode="before")
    @classmethod
    def _legacy_delay_shim(cls, data):
        return _shim_legacy_delay_fields(data)
```

Live-verified behavior (all four cases proven against installed pydantic 2.13.3, not assumed):

| Input | Result |
|-------|--------|
| `{"min_delay": 8, "max_delay": 15, "headless": False}` (legacy-only) | `delay_seconds=8.0 delay_jitter=7.0 headless=False` |
| `{"delay_seconds": 8.0, "delay_jitter": 7.0}` (canonical-only) | `delay_seconds=8.0 delay_jitter=7.0` |
| `{}` (neither — class defaults) | `delay_seconds=8.0 delay_jitter=7.0` (model's own defaults) |
| `{"min_delay": 1, "max_delay": 2, "delay_seconds": 99, "delay_jitter": 55}` (both present) | `delay_seconds=99.0 delay_jitter=55.0` — **canonical wins, never clobbered** |

Apply the identical `@model_validator(mode="before")` (calling the shared `_shim_legacy_delay_fields`
helper) to `TargetPlatformConfig`, `GameStopPlatformConfig`, `SquareEnixPlatformConfig`,
`NeweggPlatformConfig` — same rename, same shim, DRY via the shared module-level function.
`AmazonPlatformConfig`/`BestBuyPlatformConfig` need **no shim** (they already use canonical
names) — add `Field(..., ge=0.0)` to their `delay_seconds`/`delay_jitter` declarations for
schema consistency (currently bare `float = 30.0` with no bound, `core/config_schema.py:71-72,81-82`
— a minor, in-scope tightening; no existing valid config has a negative value there, so this
adds zero regression risk).

### `_get_plugin_sleep` update (Option A, recommended)

```python
def _get_plugin_sleep(plugin, poll_interval: float) -> float:
    try:
        platform_key = getattr(plugin, "platform_key", None)
        if not platform_key:
            return poll_interval
        platform_cfg = getattr(plugin.config.platforms, platform_key, None)
        if platform_cfg is None:
            return poll_interval
        delay_seconds = getattr(platform_cfg, "delay_seconds", None)
        delay_jitter = getattr(platform_cfg, "delay_jitter", None)
        if delay_seconds is None or delay_jitter is None:
            return poll_interval
        return delay_seconds + random.uniform(0, delay_jitter)
    except Exception:
        return poll_interval
```

## CFG-02: Generic Per-Platform Config Mechanism (Research Question 2 — SECONDARY)

### Construction-order constraint (rules out candidate (b) at low cost)

`[VERIFIED: local code]` `AppConfig()` is always constructed **before** `PluginRegistry()`:

```
main.py:27           cfg = AppConfig()
core/orchestrator.py:771   registry = PluginRegistry(cfg, plugins_dir, ...)

core/service.py:39   self._cfg = AppConfig() if cfg is None else cfg
core/service.py:131  registry = PluginRegistry(self._cfg, plugins_dir)
```

Candidate (b) — "a per-platform config registry where plugins register their pydantic model
at import/discovery time and the loader validates against the registry" — requires plugin
discovery (`_discover_plugins`, `core/registry.py:19-57`) to run **before** `AppConfig()` is
built, so the schema can be assembled dynamically (e.g. via `pydantic.create_model`) from the
discovered plugins' declared models. That is the opposite of the current order in **both**
call sites above, and would require restructuring `main.py`, `core/service.py`, and
`core/orchestrator.py`'s construction sequence — high blast radius for a "zero core edits for
a new plugin" requirement. **Not recommended.**

Candidate (c) — `dict[str, PlatformConfigBase]` replacing the 7 named fields on
`PlatformsConfig` — would break every existing attribute-access call site
(`getattr(self.config.platforms, "amazon", None)`-style reads appear in
`plugins/shopbot_plugin_amazon.py:272`, `plugins/shopbot_plugin_bestbuy.py:167`,
`plugins/shopbot_plugin_walmart.py:55`, `core/plugin_base.py:281`,
`core/orchestrator.py:303`) — every one of these would need to change from dotted-attribute
access to dict-key access. High regression risk for the 7 known platforms just to accommodate
a new one. **Not recommended.**

### Recommended: candidate (a) — `extra="allow"` passthrough + plugin-side validation helper

`[VERIFIED: local test]` A single-line change to `PlatformsConfig`:

```python
class PlatformsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")   # CFG-02: unknown platform keys pass through
                                                 # instead of being silently dropped
    amazon: AmazonPlatformConfig = AmazonPlatformConfig()
    bestbuy: BestBuyPlatformConfig = BestBuyPlatformConfig()
    walmart: WalmartPlatformConfig = WalmartPlatformConfig()
    target: TargetPlatformConfig = TargetPlatformConfig()
    gamestop: GameStopPlatformConfig = GameStopPlatformConfig()
    squareenix: SquareEnixPlatformConfig = SquareEnixPlatformConfig()
    newegg: NeweggPlatformConfig = NeweggPlatformConfig()
```

Verified live: with this change, `PlatformsConfig(**{"amazon": {"delay_seconds": -5}})` still
**raises `ValidationError`** (the 7 declared fields keep their full, strict validation — `extra`
only governs handling of *undeclared* keys) while
`PlatformsConfig(**{"costco": {"min_delay": 5, "max_delay": 9, "headless": True}})` succeeds
and `getattr(instance, "costco", None)` returns the **raw dict** `{'min_delay': 5, 'max_delay':
9, 'headless': True}` (unvalidated passthrough — pydantic does not know a `CostcoPlatformConfig`
exists).

The new plugin validates its own section. Add a shared, reusable helper to
`core/plugin_base.py` (`RetailerPlugin`) so every future community plugin gets this for free
instead of hand-rolling the raw-dict coercion:

```python
# core/plugin_base.py (new method on RetailerPlugin)
def get_platform_config(self, model_cls: type[BaseModel]) -> BaseModel:
    """Return this plugin's per-platform config, validated against model_cls.

    Handles three cases uniformly:
    - One of the 7 built-in platforms: `raw` is already a validated submodel instance
      (unaffected -- returned as-is if it's already model_cls).
    - A new plugin's undeclared section: `raw` is a passthrough dict (extra="allow") --
      constructed into model_cls, letting pydantic raise ValidationError normally on bad
      values (fail loudly, matching the 7 existing platforms' behavior).
    - Missing config/platform_key/section: returns model_cls() defaults (getattr-safe,
      matches the existing idiom used throughout plugin_base.py / plugins).
    """
    platforms = getattr(self.config, "platforms", None) if self.config else None
    key = getattr(self, "platform_key", None)
    raw = getattr(platforms, key, None) if key else None
    if raw is None:
        return model_cls()
    if isinstance(raw, model_cls):
        return raw
    if isinstance(raw, dict):
        return model_cls(**raw)   # raises ValidationError on invalid data -- intentional
    return model_cls()
```

A new community plugin (e.g. `shopbot_plugin_costco.py`) then needs **zero edits to
`core/config_schema.py`**:

```python
# plugins/shopbot_plugin_costco.py
from pydantic import BaseModel, Field
from core.plugin_base import RetailerPlugin

class CostcoPlatformConfig(BaseModel):
    delay_seconds: float = Field(default=10.0, ge=0.0)
    delay_jitter: float = Field(default=5.0, ge=0.0)
    headless: bool = True

class CostcoPlugin(RetailerPlugin):
    domain_patterns = ["costco.com"]
    platform_key = "costco"          # matches config.platforms.costco

    async def setup(self) -> None:
        cfg = self.get_platform_config(CostcoPlatformConfig)
        headless = cfg.headless
        ...
```

**Preserves the 7 existing platforms' validation intact** (verified), **requires zero core
schema edits** for a new plugin (verified), and **fits the existing `platform_key` +
`getattr`-safe pattern** used everywhere else in the codebase (verified against
`plugin_base.py`, `orchestrator.py`, and all 7 plugin files).

Note: a brand-new plugin using only the `extra="allow"` passthrough does **not** automatically
get orchestrator-level poll jitter from `_get_plugin_sleep` (that function does
`getattr(platform_cfg, "delay_seconds", None)`, and a raw `dict` has no such attribute — it
falls back to `poll_interval`, exactly like Amazon/BestBuy do today). This is in-scope and
correct: CFG-02's requirement is that the platform's *own* section loads and validates, not
that every new plugin automatically wires into the orchestrator's jitter internals.

## Regression Surface (Research Question 3)

### Call sites reading `min_delay`/`max_delay` (must convert)

| File | Line(s) | What changes |
|------|---------|--------------|
| `core/config_schema.py` | 89-140 (5 model classes) | Rename fields; add `_legacy_delay_shim` validator |
| `core/orchestrator.py` | 292-312 (`_get_plugin_sleep`) | Read `delay_seconds`/`delay_jitter` instead of `min_delay`/`max_delay` (the only functional consumer in the whole repo) |

No plugin file (`plugins/shopbot_plugin_*.py`) needs changes for CFG-01 — none of them read
delay fields directly (verified by grep).

### Tests asserting on platform config delay fields (must update or add)

| File | Test | Why it must change |
|------|------|---------------------|
| `tests/test_orchestrator_jitter.py` | `test_jitter_in_range_for_walmart_config` | Constructs `WalmartPlatformConfig(min_delay=8.0, max_delay=15.0)` directly — still works via shim, but should add a canonical-construction variant too |
| `tests/test_orchestrator_jitter.py` | `test_jitter_stays_in_range_over_50_iterations` | Same as above |
| `tests/test_orchestrator_jitter.py` | `test_fallback_for_amazon_shaped_config` | **This is the test that operationalizes the CRITICAL FINDING above.** Currently asserts Amazon falls back to `poll_interval`. Must be explicitly rewritten (Option A: assert the new jittered range) or explicitly preserved (Option B: keep as-is, requires the allowlist approach) — cannot be left as-is under Option A without going red |
| `tests/test_config_schema.py` | `test_walmart_platform_fields_load_from_yaml` | Asserts `.min_delay == 8.0` / `.max_delay == 15.0` directly — attribute names no longer exist post-rename; update to `.delay_seconds`/`.delay_jitter`, and add a parallel test proving the legacy YAML keys (`min_delay`/`max_delay`) still populate those canonical attributes correctly (the CONTEXT.md-mandated back-compat proof) |
| `tests/test_config_schema.py` | `test_negative_min_delay_raises_validation_error` | Verified: still raises `ValidationError` post-shim (derived `delay_seconds=-1.0` fails `Field(ge=0.0)`) — no functional change needed, but confirm still green |
| `tests/test_config_schema.py` | `test_negative_max_delay_raises_validation_error` | Verified: still raises (derived `delay_jitter` goes negative, fails `Field(ge=0.0)`) — no functional change needed, but confirm still green |
| `tests/test_config_schema.py` | `test_squareenix_platform_config_reachable` | Asserts `.min_delay`/`.max_delay` directly — same fix as the Walmart test above |
| `tests/test_config_schema.py` | `test_session_persistence_legacy_config_loads` | Uses legacy `min_delay`/`max_delay` for walmart but does not assert on those values — should remain green unchanged; verify as a smoke check |

### Existing config-schema test file(s)

`tests/test_config_schema.py` (primary — platform config field tests) and
`tests/test_orchestrator_jitter.py` (secondary — consumption/jitter behavior tests). Both must
stay green. `tests/test_config.py` covers the unrelated legacy-credential-key shim
(`app.amz_email` etc.) — same established pattern, no changes needed for this phase, but is a
useful precedent (see Code Examples).

## Architecture Patterns

### System Flow (config load → plugin consumption)

```
config.yml (legacy min_delay/max_delay OR canonical delay_seconds/delay_jitter)
        |
        v
AppConfig() constructed in main.py / core/service.py
        |
        v
YamlConfigSettingsSource parses YAML -> nested dict for "platforms" key
        |
        v
PlatformsConfig(**platforms_dict) validated
        |               \
        v                \-- unknown platform key (CFG-02) --> extra="allow" passthrough (raw dict)
  Known platform (7)                                                    |
  submodel construction                                                 v
        |                                                    plugin.get_platform_config(ModelCls)
        v                                                     validates on first plugin access
  model_validator(mode="before")
  _shim_legacy_delay_fields()
  maps min_delay/max_delay -> delay_seconds/delay_jitter
  (only if canonical absent; never clobbers explicit canonical)
        |
        v
  PluginRegistry(cfg, plugins_dir) constructed AFTER AppConfig()
        |
        v
  plugin.platform_key resolves config.platforms.<key> via getattr
        |
        v
  core/orchestrator.py: _get_plugin_sleep(plugin, poll_interval)
  reads delay_seconds/delay_jitter -> delay_seconds + uniform(0, delay_jitter)
  (falls back to poll_interval if either attribute is absent/None)
```

### Recommended file-level changes (no new files needed)
```
core/
├── config_schema.py     # rename 5 models' fields; add _shim_legacy_delay_fields();
│                        # add extra="allow" to PlatformsConfig; add ge=0.0 to
│                        # Amazon/BestBuy delay_seconds/delay_jitter
├── orchestrator.py      # _get_plugin_sleep: read canonical field names
└── plugin_base.py       # add get_platform_config() helper (CFG-02 "loader")

sample.config.yml        # add a comment near `platforms:` documenting canonical names +
                          # back-compat note (no existing community-platform block to
                          # rewrite -- none is currently illustrated there)

tests/
├── test_config_schema.py       # update field-name assertions; add back-compat +
│                                # canonical-name-loading test pairs
└── test_orchestrator_jitter.py # update to canonical construction; resolve the
                                  # Amazon-fallback test per the Assumption A1 decision
```

### Pattern: shared `model_validator(mode="before")` shim (established precedent)

The codebase already has this exact pattern for a different legacy-key case —
`AppConfig.warn_legacy_keys` (`core/config_schema.py:309-325`), which walks a
`_LEGACY_KEYS` dict and emits `DeprecationWarning` for old credential keys before
construction. The recommended delay-field shim mirrors this established idiom (module-level
helper + `DeprecationWarning` + `model_validator(mode="before")`), just scoped to the 5
per-platform submodels rather than the top-level `AppConfig`.

### Anti-Patterns to Avoid
- **Clamping the derived `delay_jitter` to `>= 0` inside the shim itself:** this silently
  swallows what should be a `ValidationError` for a nonsensical legacy config (e.g.
  `max_delay < min_delay`). Let the derived value flow into the canonical field's own
  `Field(ge=0.0)` constraint and raise naturally — verified this preserves both existing
  negative-value tests without any extra clamping logic.
- **Hardcoding platform names in `_get_plugin_sleep`** to preserve Amazon/BestBuy's exact
  fallback (Option B above): technically achieves zero behavior change but directly
  contradicts CFG-02's "no per-platform hardcoding in core" spirit. Use only if the planner
  explicitly requires byte-identical Amazon/BestBuy cadence over field-name uniformity.
- **Using `dict[str, PlatformConfigBase]` for CFG-02** (candidate (c)): breaks every existing
  `getattr(config.platforms, "amazon", None)`-style call site across 5+ files for a "just
  works" convenience that `extra="allow"` already provides at 1/10th the diff.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-plugin raw-dict-to-model coercion for CFG-02 | A bespoke `if isinstance(raw, dict): ...` block copy-pasted into every new community plugin's `setup()` | `RetailerPlugin.get_platform_config(model_cls)` (new shared helper, `core/plugin_base.py`) | Every plugin author would otherwise reinvent the same 6 lines; a shared helper keeps `ValidationError` behavior consistent across all future plugins |
| Legacy-key deprecation warnings | Ad-hoc `if "min_delay" in raw: print(...)` per model | Shared `_shim_legacy_delay_fields()` module function + the existing `warnings.warn(..., DeprecationWarning)` idiom already used by `AppConfig.warn_legacy_keys` | DRY across the 5 community models; matches the one deprecation-warning convention this codebase already has |

**Key insight:** this phase's entire risk surface is in getting the *derived-field* shim
exactly right (`delay_jitter = max_delay - min_delay`) and in the orchestrator's dispatch
mechanism, not in inventing new abstractions — every piece needed already has a precedent
elsewhere in this same file (`warn_legacy_keys`, `compute_delay`).

## Common Pitfalls

### Pitfall 1: `AliasChoices`/`validation_alias` looks sufficient but isn't
**What goes wrong:** A first pass at the shim might reach for `Field(validation_alias=
AliasChoices("delay_seconds", "min_delay"))` for both fields, assuming a simple rename covers
it.
**Why it happens:** `min_delay`→`delay_seconds` genuinely is a 1:1 rename and alias resolution
works fine for that half. `max_delay`→`delay_jitter` is not — the target value is `max_delay -
min_delay`, a function of two source fields, which no alias mechanism can express.
**How to avoid:** Use `model_validator(mode="before")` for the whole shim (both fields),
verified live against pydantic 2.13.3.
**Warning signs:** A `WalmartPlatformConfig(min_delay=8, max_delay=15)` construction that
produces `delay_jitter=15.0` (aliased straight from `max_delay`) instead of `delay_jitter=7.0`
(the derived width) — this is the tell that alias-only was used instead of derivation.

### Pitfall 2: `model_validator(mode="before")` clobbering explicit canonical values
**What goes wrong:** A naive shim applies the legacy mapping whenever *either* legacy key is
present, even if the caller ALSO explicitly set `delay_seconds`/`delay_jitter` — silently
overwriting the explicit canonical value with a value derived from unrelated legacy keys.
**Why it happens:** Easy to write `if "min_delay" in data: data["delay_seconds"] = ...`
without a companion "and canonical is absent" guard.
**How to avoid:** Guard with `has_legacy and not has_canonical` (verified live: explicit
canonical values win even when legacy keys are also present in the same dict).
**Warning signs:** A test asserting `WalmartPlatformConfig(delay_seconds=99, min_delay=1)`
produces `delay_seconds=1` instead of `99` — precedence is inverted.

### Pitfall 3: clamping negative derived jitter silently swallows validation errors
**What goes wrong:** Adding `max(max_delay - min_delay, 0.0)` inside the shim "to be safe"
actually removes the `ValidationError` that `test_negative_max_delay_raises_validation_error`
requires (a negative derived value would otherwise be caught by `Field(ge=0.0)` and no longer
is, once clamped to `0.0`).
**Why it happens:** Defensive clamping instinct conflicts with "fail loudly" being the correct
behavior here (matches the 7 existing platforms' existing validation-error tests).
**How to avoid:** Do not clamp. Let the raw derived value (which can be negative for an
inverted/typo'd legacy config) flow into `Field(..., ge=0.0)` and raise naturally.
**Warning signs:** `test_negative_max_delay_raises_validation_error` or
`test_negative_min_delay_raises_validation_error` silently starts passing for the wrong reason
(no exception raised at all, test's `pytest.raises` block never entered) — check these
specifically after implementing the shim.

### Pitfall 4: the SquareEnix "no underscore" convention is unrelated but easy to break by association
**What goes wrong:** While touching all 5 community models in the same pass, it's tempting to
"clean up" `squareenix` to `square_enix` for consistency.
**Why it happens:** The 5 models are being edited together for the delay-field rename; naming
drift creeps in.
**How to avoid:** `SquareEnixPlatformConfig`'s YAML key MUST remain `squareenix` (no
underscore) — it matches the plugin's `platform_key = "squareenix"` exactly
(`core/config_schema.py:122,148`). This is completely orthogonal to the delay-field rename;
touch only the delay fields on this model, nothing else.
**Warning signs:** `test_squareenix_platform_config_reachable` failing for a reason unrelated
to delay fields (YAML key mismatch) after the rename pass.

### Pitfall 5: `sample.config.yml` drift
**What goes wrong:** `sample.config.yml` documents `platforms.amazon.delay_seconds`/
`delay_jitter` already (canonical, unaffected) but has **no example block at all** for the 5
community platforms — a naive doc update might invent a `walmart:` example using the OLD
`min_delay`/`max_delay` names (now deprecated) instead of canonical names, or fail to mention
the back-compat shim at all.
**How to avoid:** Add a comment near the `platforms:` key noting canonical names apply to all
7 platforms and that `min_delay`/`max_delay` still load via a deprecated back-compat shim — no
new community-platform example block is strictly required (none exists today), but if one is
added, use canonical names.

### Pitfall 6: `_get_plugin_sleep`'s exception-swallowing `except Exception: return
poll_interval` can mask a shim bug
**What goes wrong:** If the field rename introduces an `AttributeError` somewhere upstream
(e.g. a stale reference to `.min_delay` left in test code or a helper), `_get_plugin_sleep`'s
blanket `except Exception` silently falls back to `poll_interval` rather than surfacing the
bug — a renamed-field regression could hide behind this catch-all and only show up as "jitter
isn't happening" rather than a loud test failure.
**How to avoid:** Rely on the explicit `getattr(..., None)` checks (not the `except Exception`)
to detect "field absent"; keep the outer `try/except` for genuinely unexpected errors only, and
make sure `test_jitter_in_range_for_walmart_config`-style tests assert the **actual jittered
range**, not just "no exception raised."

## Code Examples

### Full 5-model rename pattern (apply identically to Target/GameStop/SquareEnix/Newegg)

```python
# Source: this repo, core/config_schema.py (verified against installed pydantic 2.13.3)
def _shim_legacy_delay_fields(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    has_legacy = "min_delay" in data or "max_delay" in data
    has_canonical = "delay_seconds" in data or "delay_jitter" in data
    if has_legacy and not has_canonical:
        import warnings
        warnings.warn(
            "config.yml: 'min_delay'/'max_delay' are deprecated; use "
            "'delay_seconds'/'delay_jitter' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        data = dict(data)
        min_d = float(data.pop("min_delay", 8.0))
        max_d = float(data.pop("max_delay", 15.0))
        data["delay_seconds"] = min_d
        data["delay_jitter"] = max_d - min_d
    return data


class WalmartPlatformConfig(BaseModel):
    delay_seconds: float = Field(default=8.0, ge=0.0)
    delay_jitter: float = Field(default=7.0, ge=0.0)
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)
    session_persistence: bool = False

    @model_validator(mode="before")
    @classmethod
    def _legacy_delay_shim(cls, data):
        return _shim_legacy_delay_fields(data)
```

### CFG-02 fixture-plugin test pattern (mirrors existing `tmp_plugins_dir` fixture, `tests/conftest.py:102-122`)

```python
# Source: this repo's established registry-test pattern (tests/test_registry.py,
# tests/conftest.py:102-122), extended to prove CFG-02
def test_new_plugin_platform_section_validates_without_core_edits(tmp_path):
    plugin_code = (
        "from pydantic import BaseModel, Field\n"
        "from core.plugin_base import RetailerPlugin\n\n"
        "class CostcoPlatformConfig(BaseModel):\n"
        "    delay_seconds: float = Field(default=10.0, ge=0.0)\n"
        "    delay_jitter: float = Field(default=5.0, ge=0.0)\n\n"
        "class CostcoPlugin(RetailerPlugin):\n"
        "    domain_patterns = ['costco.com']\n"
        "    platform_key = 'costco'\n"
        "    async def check_availability(self, url):\n"
        "        return True\n"
        "    async def auto_buy(self, url):\n"
        "        return False\n"
    )
    (tmp_path / "shopbot_plugin_costco.py").write_text(plugin_code)

    from core.config_schema import AppConfig
    cfg = AppConfig(**{"platforms": {"costco": {"delay_seconds": 12.0}}})

    from core.registry import PluginRegistry
    registry = PluginRegistry(cfg, tmp_path)
    plugin = registry._all_plugins[0]

    import importlib
    costco_mod = importlib.import_module("shopbot_plugin_costco")
    parsed = plugin.get_platform_config(costco_mod.CostcoPlatformConfig)
    assert parsed.delay_seconds == 12.0          # explicit YAML value validated
    assert parsed.delay_jitter == 5.0            # default applied for unset field
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Wiring `_get_plugin_sleep` to read canonical `delay_seconds`/`delay_jitter` uniformly (Option A) is an acceptable, in-scope side effect for Amazon/BestBuy's orchestrator poll-cadence (changing it from a flat `poll_interval` fallback to a jittered `delay_seconds ± delay_jitter` range), rather than a "behavior-preserving" constraint violation. `[ASSUMED]` — this is a judgment call about the *intent* behind the hard constraint, not a verifiable fact. | CFG-01 primary finding | If wrong: the planner must instead implement Option B (hardcoded platform-key allowlist in `_get_plugin_sleep` to exclude amazon/bestbuy from the jitter branch), which preserves byte-identical Amazon/BestBuy cadence but reintroduces per-platform hardcoding in core orchestrator code — a design the phase otherwise tries to move away from (CFG-02). This must be confirmed with the user/planner before implementation; do not let a task silently pick one path. |
| A2 | Adding `Field(..., ge=0.0)` to Amazon/BestBuy's `delay_seconds`/`delay_jitter` (currently bare, unbounded floats) is safe and in-scope as a minor consistency fix. `[ASSUMED]` — no test currently exercises a negative value there, so this is inferred to be zero-risk, not proven risk-free by an exhaustive check of all deployed configs. | CFG-01 shim mechanism | Low risk: only rejects previously-nonsensical negative values; no valid existing config would be affected. |

## Open Questions

1. **Should Option A or Option B (Assumption A1) be implemented for `_get_plugin_sleep`?**
   - What we know: Option A satisfies "one canonical field name, one consumption mechanism"
     cleanly and matches the codebase's stated intent (`AppSettingsConfig` docstring). Option B
     preserves byte-identical Amazon/BestBuy behavior but requires hardcoding platform keys in
     core orchestrator code.
   - What's unclear: Whether "behavior-preserving... hard constraint" in the phase description
     was written with awareness that `delay_seconds`/`delay_jitter` are currently dead config,
     or under the (incorrect, per this research) assumption that they already drive Amazon/
     BestBuy's cadence today.
   - Recommendation: Default to Option A (simpler, no core hardcoding, matches documented
     intent) unless the planner/user explicitly requires byte-identical Amazon/BestBuy
     cadence, in which case use Option B's allowlist and accept the CFG-02 tension.

2. **Should the legacy-key `DeprecationWarning` be asserted by a new test, mirroring
   `test_legacy_key_warning` (`tests/test_config_schema.py:44-53`) for the existing
   `app.amz_email`-style shim?**
   - What we know: The codebase has exactly this precedent already; adding a parallel test for
     the delay-field shim is low-cost and consistent.
   - What's unclear: Not explicitly required by CONTEXT.md, but strongly implied by "the shim
     must be proven by a test."
   - Recommendation: Add it — cheap, consistent with existing test style.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 `[VERIFIED: local install]` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, line 30) |
| Quick run command | `pytest tests/test_config_schema.py tests/test_orchestrator_jitter.py -q` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CFG-01 | Legacy `min_delay`/`max_delay` config still loads via shim, mapped to canonical fields exactly | unit | `pytest tests/test_config_schema.py -k legacy_delay -x` | ❌ Wave 0 (new test) |
| CFG-01 | Canonical `delay_seconds`/`delay_jitter` config loads directly (no regression) | unit | `pytest tests/test_config_schema.py -k walmart_platform_fields -x` | ✅ existing, needs field-name update |
| CFG-01 | Effective delay distribution preserved for community plugins (uniform(min,max) == derived formula) | unit | `pytest tests/test_orchestrator_jitter.py -k jitter_in_range -x` | ✅ existing, needs field-name update |
| CFG-01 | Negative/inverted legacy values still raise `ValidationError` | unit | `pytest tests/test_config_schema.py -k negative_delay -x` | ✅ existing (`test_negative_min_delay_raises_validation_error`, `test_negative_max_delay_raises_validation_error`) |
| CFG-01 | Amazon/BestBuy cadence decision (Option A or B) is explicitly asserted, not left ambiguous | unit | `pytest tests/test_orchestrator_jitter.py -k amazon_shaped -x` | ✅ existing (`test_fallback_for_amazon_shaped_config`), must be rewritten per Assumption A1 resolution |
| CFG-02 | New undeclared platform section loads + validates with core schema untouched | unit/integration | `pytest tests/test_platform_config_extension.py -x` | ❌ Wave 0 (new test + new fixture, pattern shown in Code Examples) |
| CFG-02 | 7 existing platforms keep strict validation after `extra="allow"` added | unit | `pytest tests/test_config_schema.py -k negative_min_delay -x` | ✅ existing, should remain green unchanged |

### Sampling Rate
- **Per task commit:** `pytest tests/test_config_schema.py tests/test_orchestrator_jitter.py -q`
- **Per wave merge:** `pytest -q` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_config_schema.py` — add `test_legacy_delay_shim_maps_to_canonical` (proves
      `min_delay`/`max_delay` config produces the correct derived `delay_seconds`/
      `delay_jitter`) and `test_canonical_delay_precedence_over_legacy` (proves explicit
      canonical values are never clobbered) — covers CFG-01
- [ ] `tests/test_platform_config_extension.py` — new file, fixture plugin proving CFG-02
      (pattern given in Code Examples above)
- [ ] No new test framework install needed — pytest already configured and pinned

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Not touched by this phase |
| V3 Session Management | no | Not touched by this phase |
| V4 Access Control | no | Not touched by this phase |
| V5 Input Validation | yes | Pydantic `Field(..., ge=0.0)` constraints on all delay fields (existing pattern, extended to Amazon/BestBuy for consistency — Assumption A2); `model_validator(mode="before")` shim only reads/transforms known dict keys, never `eval`s or deserializes arbitrary types |
| V6 Cryptography | no | Not touched by this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Config injection via crafted YAML with unexpected types for `min_delay`/`max_delay` (e.g. a string or list) | Tampering | `float(data.pop("min_delay", 8.0))` in the shim raises `ValueError`/`TypeError` for non-numeric input before it reaches the model — surfaces as a config load failure at startup, not a silent misbehavior; this is unchanged from the existing per-field `Field(..., ge=0.0)` behavior for the 5 community models today |
| A malicious/careless new plugin declaring a `platforms.<key>` section with unbounded/unsanitized values (CFG-02) | Tampering | Not core's responsibility — the new plugin's own `model_cls(**raw)` call in `get_platform_config` applies whatever `Field` constraints the plugin author declared; core only guarantees passthrough, not validation, of undeclared sections (documented explicitly in the helper's docstring) |

## Sources

### Primary (HIGH confidence — read directly from this repository)
- `core/config_schema.py` — all platform config models, `PlatformsConfig`, `AppConfig`,
  existing `warn_legacy_keys`/`_LEGACY_KEYS` shim precedent
- `core/orchestrator.py` — `_get_plugin_sleep` (lines 292-312), `run_plugin` (lines 315-372,
  call sites at 343 and 372)
- `core/retry.py` — `compute_delay`/`RetryPolicy` (established base+jitter idiom, lines 35-44)
- `core/plugin_base.py` — `RetailerPlugin`, existing `getattr`-safe config-read idiom
  (`_session_enabled`, `_session_platform_key`)
- `core/registry.py` — `PluginRegistry`, `_discover_plugins` (construction-order evidence)
- `plugins/shopbot_plugin_amazon.py`, `plugins/shopbot_plugin_bestbuy.py`,
  `plugins/shopbot_plugin_walmart.py`, `plugins/shopbot_plugin_squareenix.py` — read in full
  or grepped for delay-field consumption (confirmed absent)
- `tests/test_orchestrator_jitter.py`, `tests/test_config_schema.py`, `tests/test_config.py`,
  `tests/conftest.py` — existing test patterns and fixtures
- `sample.config.yml` — current documented field names
- `.planning/phases/33-config-refactor/33-CONTEXT.md`, `.planning/REQUIREMENTS.md`,
  `.planning/STATE.md`, `.planning/config.json`, `./CLAUDE.md`

### Secondary (MEDIUM confidence)
None — all pydantic-behavior claims in this document were proven live against the installed
`pydantic==2.13.3` (matching `requirements.txt:7`) rather than sourced from training-data
recollection of pydantic v2 semantics; see the four verification transcripts embedded above.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- CFG-01 shim mechanics: HIGH — every code path and formula quoted above was read directly
  from the repository and the pydantic shim behavior was proven live against the installed
  version, not assumed from training data
- CFG-01 Amazon/BestBuy cadence resolution (Option A vs B): MEDIUM — the mechanics are HIGH
  confidence; the *recommendation* of Option A over Option B is a judgment call flagged
  explicitly as Assumption A1, requiring planner/human confirmation
- CFG-02 mechanism recommendation: HIGH — construction-order constraint and `extra="allow"`
  behavior were both verified directly against this repository's actual code and the
  installed pydantic version
- Regression surface: HIGH — enumerated via exhaustive repo-wide grep, not sampling

**Research date:** 2026-07-02
**Valid until:** No expiry driver — this is an internal refactor of already-pinned,
already-installed dependencies (`pydantic==2.13.3`, `pydantic-settings==2.14.2`); findings are
tied to the current repository state, not to an external ecosystem that could drift. Re-verify
only if `pyproject.toml`/`requirements.txt` pydantic pins change before this phase is
implemented.
