---
phase: 33-config-refactor
reviewed: 2026-07-02T00:00:00Z
depth: deep
files_reviewed: 7
files_reviewed_list:
  - core/config_schema.py
  - core/orchestrator.py
  - core/plugin_base.py
  - sample.config.yml
  - tests/test_config_schema.py
  - tests/test_orchestrator_jitter.py
  - tests/test_platform_config_extension.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: resolved
resolution:
  date: 2026-07-02
  WR-01: resolved
  WR-02: resolved
  WR-03: resolved
  IN-01: acknowledged-pre-existing (no action; documented CFG-02 tradeoff)
  IN-02: resolved
---

# Phase 33: Code Review Report

**Reviewed:** 2026-07-02T00:00:00Z
**Depth:** deep
**Files Reviewed:** 7
**Status:** resolved (see Resolution section at end)

## Summary

Reviewed the CFG-01/CFG-02 config refactor (219d9c2..HEAD): rename of 5 community
platform models' `min_delay`/`max_delay` to canonical `delay_seconds`/`delay_jitter`,
a `model_validator(mode="before")` back-compat shim, `PlatformsConfig(extra="allow")`
for undeclared platform passthrough, `_get_plugin_sleep` reading the canonical fields
uniformly for all 7 platforms, and the new `get_platform_config()` helper.

Core claims hold up under direct verification (manual repro scripts + the 41 existing/
added tests, all passing):

- **Shim does not clobber explicit canonical values.** `has_canonical` is checked
  before the legacy branch runs; verified with `WalmartPlatformConfig(min_delay=1,
  max_delay=2, delay_seconds=99, delay_jitter=55)` -> `delay_seconds=99.0,
  delay_jitter=55.0`.
- **`extra="allow"` does not weaken the 7 declared platforms.** `PlatformsConfig(**{"amazon":
  {"delay_seconds": -5}})` still raises `ValidationError`; an unknown key (e.g.
  `costco`) is stored as a completely unvalidated raw dict (`{'delay_seconds': -999,
  ...}` passes through with no error), which is CFG-02's documented, intentional
  tradeoff.
- **No platform left on a flat/non-jittered path.** `_get_plugin_sleep` reads
  `delay_seconds`/`delay_jitter` identically for all 7 models; the old code read
  `min_delay`/`max_delay` (attributes Amazon/BestBuy never had), so pre-refactor
  Amazon/BestBuy silently always hit the `poll_interval` fallback. That fallback
  branch is confirmed still reachable only for genuinely unknown/malformed platform
  configs, not for any of the 7 declared platforms.
- **No broken consumer from the rename.** Grepped `plugins/` for
  `min_delay|max_delay|delay_seconds|delay_jitter` — zero hits; no plugin code reads
  the old attribute names directly, so nothing outside `config_schema.py`/
  `orchestrator.py` depended on the pre-rename field names. `sample.config.yml`
  already used the canonical names for amazon/bestbuy and only gained an explanatory
  comment.

However, two edge cases produce a real behavior change that the "behavior-preserving"
framing does not fully cover (WR-01), and `get_platform_config()`'s 4th (undocumented)
branch can silently discard real user config (WR-02). Details below.

## Warnings

### WR-01: Inverted/asymmetric legacy delay ranges that used to load now hard-fail at startup

**File:** `core/config_schema.py:39-69` (`_shim_legacy_delay_fields`)
**Issue:** The pre-refactor community models validated `min_delay >= 0` and
`max_delay >= 0` independently — nothing ever required `max_delay >= min_delay`. The
old `_get_plugin_sleep` called `random.uniform(min_delay, max_delay)` directly, and
Python's `random.uniform(a, b)` tolerates `a > b` (returns a value in `[b, a]`), so an
inverted or asymmetric legacy config loaded and ran without error before this phase.

After the refactor, the shim derives `delay_jitter = max_delay - min_delay` and feeds
it into the canonical field's `Field(ge=0.0)` constraint. Any legacy config where
`max_delay < min_delay` (explicit inversion) — or even just `min_delay` alone set
higher than the shim's hardcoded fallback default of `15.0` for the missing
`max_delay` — now raises `ValidationError` and the bot refuses to start. Verified
directly:
```
>>> WalmartPlatformConfig(min_delay=20.0, max_delay=5.0)
ValidationError: delay_jitter Input should be greater than or equal to 0 (input_value=-15.0)
>>> WalmartPlatformConfig(min_delay=20.0)   # max_delay omitted, defaults to shim's 15.0
ValidationError: delay_jitter Input should be greater than or equal to 0 (input_value=-5.0)
```
This is a genuine startup-crashing regression for any existing user config with an
inverted/asymmetric legacy range (previously silently tolerated, now a hard failure),
and the error message references `delay_jitter` — a field name the user never set —
which will be confusing to anyone still on `min_delay`/`max_delay`. The task's own
scope note ("no delay VALUE changes for community plugins, behavior-preserving")
does not hold for this input shape.
**Fix:** Either (a) clamp the derived `delay_jitter` to `max(0.0, max_delay -
min_delay)` in the shim and log a warning instead of raising, since Python's
`random.uniform` already tolerated the inversion silently — matching legacy runtime
behavior instead of introducing a new hard failure; or (b), if fail-loud is truly
intended here, raise a clearer error that names the original `min_delay`/`max_delay`
values the user supplied (not just the derived `delay_jitter`), e.g.:
```python
if max_d < min_d:
    raise ValueError(
        f"config.yml: min_delay ({min_d}) must be <= max_delay ({max_d})"
    )
```
placed before the `Field(ge=0.0)` constraint is reached, so the error message points
back at the keys the user actually wrote.

### WR-02: `get_platform_config()` silently discards real config data on model_cls/platform_key mismatch

**File:** `core/plugin_base.py:290-299`
**Issue:** The docstring says `get_platform_config` "handles three cases uniformly,"
but the implementation has a fourth, undocumented branch: when `raw` is neither
`None`, an instance of `model_cls`, nor a `dict` (e.g. `raw` is a validated instance
of a *different* pydantic model — which happens whenever a plugin's `platform_key`
collides with one of the 7 built-in platform names but the plugin passes a different
`model_cls` than the one `PlatformsConfig` actually validated that section against),
the function falls through to `return model_cls()`, silently returning defaults and
discarding the user's actual configured values with no error, warning, or log line.

Verified directly: a config with `platforms.amazon.delay_seconds: 77.0` (user-set,
successfully loaded into `AppConfig`), then
`plugin.get_platform_config(SomeOtherModel)` (platform_key="amazon") returns
`SomeOtherModel(delay_seconds=999.0)` — `SomeOtherModel`'s own default, not the
user's 77.0, with no indication anything went wrong. This is currently unreachable
via any shipped plugin (`get_platform_config` is not yet called from any plugin file,
only from tests), so there is no live regression today, but it is a footgun baked
into the public API that directly contradicts the docstring's own "fail loudly,
matching the 7 existing platforms' behavior" claim — this branch is the one place
that does NOT fail loudly.
**Fix:** Update the docstring to describe the actual 4 branches, and make the
mismatch case fail loudly instead of silently defaulting:
```python
if isinstance(raw, BaseModel):
    raise TypeError(
        f"get_platform_config({model_cls.__name__}) called for platform_key="
        f"{key!r}, but that section already validated as {type(raw).__name__}"
    )
return model_cls()
```

### WR-03: Shim's hardcoded legacy defaults (8.0/15.0) are implicitly coupled to the 5 community models' Field defaults

**File:** `core/config_schema.py:65-66`
**Issue:** `_shim_legacy_delay_fields` hardcodes fallback values `8.0`/`15.0` for a
missing `min_delay`/`max_delay` key, matching the 5 community platform models'
declared `delay_seconds=8.0`/`delay_jitter=7.0` defaults (`8 + 7 = 15`, consistent
today). This is correct now, but the coupling is implicit and undocumented at the
shim call site — if a future change alters one of the 5 community models' `Field`
defaults (e.g. a platform-specific tuning pass) without updating the shared shim
function, the "only one legacy key present" edge case (see WR-01) would silently
start producing a different derived range than the model's own stated defaults, with
no test catching the drift since the shim's fallback constants live in one shared
function used by 5 otherwise-independent model classes.
**Fix:** Either add an inline comment at the hardcoded `8.0`/`15.0` literals noting
they must stay in sync with the 5 community models' `delay_seconds`/`delay_jitter`
field defaults, or (preferred) remove the coupling by only performing the legacy-key
transform when *both* `min_delay` and `max_delay` are present, and letting a
single-key-only legacy input fall through to field-level defaults for the other side
via the model's own `Field(default=...)` rather than the shim's separate hardcoded
constants.

## Info

### IN-01: Typo'd known-platform key (e.g. `amzon:`) silently falls back to defaults with no diagnostic

**File:** `core/config_schema.py:219-234` (`PlatformsConfig`)
**Issue:** Confirmed as intentional/documented behavior, not a new regression: this
was already true before this diff under the default `extra="ignore"` (unknown key
silently dropped) and remains true under the new `extra="allow"` (unknown key
silently stored, but nothing reads it). A user who typos `platforms.amzon:` instead
of `platforms.amazon:` gets zero errors and Amazon silently runs on all-default
timing/headless/user-agent settings — the typo section is retained as an inert raw
dict on the model but nothing surfaces it. No test covers this path either before or
after the refactor.
**Fix:** Not a blocker for this phase (matches the requested/accepted CFG-02
tradeoff). Consider, as a follow-up, a lightweight startup check in `AppConfig` that
warns when `PlatformsConfig`'s extra fields (`model_extra`) contain a key
close to one of the 7 known platform names (e.g. via `difflib.get_close_matches`),
to catch this class of typo without weakening `extra="allow"`.

### IN-02: `_shim_legacy_delay_fields` docstring claims "algebraically identical" without noting the fail-loud edge case it introduces

**File:** `core/config_schema.py:39-52`
**Issue:** The docstring states the shim is "behavior-preserving" and explains the
distribution equivalence, then separately notes it "does NOT clamp the derived
delay_jitter... raises ValidationError naturally" for inverted ranges — but doesn't
call out that this is a *new* failure mode relative to the pre-refactor
`random.uniform(min_delay, max_delay)` call, which tolerated inversion. See WR-01 for
the concrete repro; this entry is purely about the documentation gap making the
behavior change easy to miss in review.
**Fix:** Add one line to the docstring: "NOTE: unlike the legacy `random.uniform`
call, an inverted min>max range now raises ValidationError instead of silently
swapping bounds — this is a deliberate tightening, not a preserved behavior."

---

## Resolution

**Resolved:** 2026-07-02

### WR-01: resolved

`_shim_legacy_delay_fields` now raises a clear `ValueError` naming
`min_delay`/`max_delay` when a legacy config has `max_delay < min_delay`,
before the derived `delay_jitter` ever reaches the canonical field's
`Field(ge=0.0)` constraint. Fail-loud behavior for inverted ranges is kept
intentionally (option (b) from the fix suggestions; not clamped). Covered by
`test_legacy_delay_shim_inverted_range_raises_clear_error` in
`tests/test_config_schema.py`.

### WR-02: resolved

`get_platform_config`'s fourth branch (raw is a validated instance of a
different pydantic model) now raises `TypeError` naming the `platform_key`
and the unexpected type, instead of silently returning `model_cls()`
defaults. Docstring updated to document all four branches. `raw is None`
still returns defaults (a plugin with no matching section is valid). Covered
by `test_get_platform_config_mismatched_model_raises_type_error` in
`tests/test_platform_config_extension.py`.

### WR-03: resolved

Added an inline comment at the hardcoded `8.0`/`15.0` fallback literals in
`_shim_legacy_delay_fields` noting the coupling to the 5 community platform
models' `delay_seconds`/`delay_jitter` `Field` defaults, plus a drift-guard
assertion test (`test_shim_legacy_fallback_defaults_match_community_model_defaults`)
that fails loudly if a future tuning pass desyncs them.

### IN-01: acknowledged-pre-existing (no action)

Confirmed as intentional/documented CFG-02 tradeoff, not a regression from
this phase. No code change made. Left as a documented follow-up candidate
(startup `difflib.get_close_matches` typo warning) for a future phase.

### IN-02: resolved

Added a note to `_shim_legacy_delay_fields`'s docstring documenting the
deliberate new failure mode: unlike the legacy `random.uniform(min_delay,
max_delay)` call (which tolerated inversion), an inverted legacy range now
raises instead of silently swapping bounds.

**Verification:** Full test suite green, `901 passed, 2 skipped` (898
baseline + 3 new tests from this resolution pass).

---

_Reviewed: 2026-07-02T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
