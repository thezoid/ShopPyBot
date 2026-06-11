# Phase 18: Safety Gate + Config Foundation - Research

**Researched:** 2026-06-11
**Domain:** Python async plugin safety gate, Pydantic v2 config schema, argparse CLI wiring
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Monitor-only gate enforced at the orchestrator in `_check_and_buy`, before `_try_auto_buy` is called.
- `monitor_only` and `test_mode` are two independent gates: `monitor_only` skips `auto_buy` entirely at the orchestrator; `test_mode` lets checkout/form-fill run but suppresses the final place-order click via `place_order_guarded()`. Either one blocks a live order.
- `--monitor-only` CLI flag forces `True`; when the flag is absent, fall back to the `debug.monitor_only` config value (CLI overrides config).
- Stock-availability alerts and notifications still fire in monitor-only mode.
- Signature: `async def place_order_guarded(self, click_fn) -> bool`; invokes click_fn only when allowed; returns `False` + logs INFO "place-order suppressed (monitor_only/test_mode)" when suppressed; no exception.
- Concrete method on `RetailerPlugin` ABC reading `self.config.debug` for `test_mode`/`monitor_only`. Additive -- `PLUGIN_API_VERSION` stays 2.
- Enforcement: (a) CI test 7 plugins x monitor_only=True -> zero purchase-queue writes; (b) grep/AST assertion no plugin clicks place-order outside the guard.
- `CheckoutConfig` field defaults: `item_timeout_secs=120`, `step_timeout_secs=30`, `max_cart_retries=3`, `backoff_base=2.0`, `backoff_jitter=0.5`, `alert_on_errors=3`.
- New `CheckoutConfig(BaseModel)`; added to `AppConfig` as `checkout: CheckoutConfig = CheckoutConfig()` placed after `captcha`.
- `monitor_only: bool = False` added to `DebugConfig`, alongside existing `test_mode`.
- Field validation: `ge` bounds following the `ProxyConfig` validator pattern.

### Claude's Discretion
- None specified.

### Deferred Ideas (OUT OF SCOPE)
- None -- discussion stayed within phase scope. Confirmation detection, form-fill, the retry engine, and the supervisor are explicitly later phases (19-22).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUY-01 | Monitor-only mode: config flag and/or `--monitor-only` CLI flag; checks + alerts but never places an order; enforced once at the orchestrator before `auto_buy`. | Orchestrator gate location confirmed at `_check_and_buy` line 236; CLI wiring pattern confirmed from existing `test_mode` / argparse patterns. |
| BUY-02 | `place_order_guarded()` concrete ABC method; all 7 bundled plugins route their final place-order click through it; closes the 6-of-7 `test_mode` gap. | All 7 plugins read, exact place-order click locations confirmed; Amazon is the only plugin with a partial `test_mode` guard today (lines 412-425); BestBuy and 5 others have no guard. |
</phase_requirements>

## Summary

Phase 18 delivers three tightly coupled deliverables that form the safety foundation for all subsequent v4.0 checkout phases. All critical implementation details were confirmed by direct codebase read -- no assumptions required for the core deliverables.

The orchestrator gate is a one-liner insert at `orchestrator.py` line 236 (the `if auto_buy:` branch): add `if plugin.config.debug.monitor_only: return` before the existing `await _try_auto_buy` call. The `test_mode` suppression path is different in kind: it lives inside each plugin's `auto_buy` body, and the guard method `place_order_guarded()` on the ABC centralizes that. Today, only `AmazonPlugin.auto_buy` checks `test_mode` before the final click (lines 412-425); `BestBuyPlugin` and the other 5 plugins have no guard at all.

The CLI wiring follows the exact pattern already used for `test_mode` + CVV gate in `handle_run`. A new `--monitor-only` flag on the `run` subparser sets `cfg.debug.monitor_only = True` before handing off to `svc.run(cvv)`. Because `AppConfig` is already constructed by `BotService.__init__`, the flag must mutate `cfg.debug.monitor_only` directly on the already-constructed config object rather than re-constructing AppConfig.

`CheckoutConfig` slots after `captcha` in `AppConfig` following the established default-instance pattern (`checkout: CheckoutConfig = CheckoutConfig()`). All field types are numeric scalars with `ge` bounds, directly mirroring `ProxyConfig`'s `@field_validator` + `Field(..., ge=...)` idiom.

**Primary recommendation:** Implement in three sequential waves: (1) config schema changes (`DebugConfig`, `CheckoutConfig`, `AppConfig`), (2) ABC `place_order_guarded()` + orchestrator gate + CLI flag, (3) reroute all 7 plugins + CI enforcement tests.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Monitor-only enforcement | API / Backend (orchestrator) | -- | Single gate in `_check_and_buy`; no per-plugin logic needed for BUY-01 |
| `place_order_guarded()` | API / Backend (ABC) | Plugin tier (call site) | ABC owns the guard logic; plugins call it for the final DOM click |
| `--monitor-only` CLI flag | CLI | Backend (AppConfig) | CLI parses the flag, mutates config before handing to BotService |
| `CheckoutConfig` schema | Config / Backend | -- | Pydantic model; no UI or CLI exposure in this phase |
| CI enforcement test | Test infrastructure | -- | pytest with asyncio_mode=auto; no UI required |

## Standard Stack

### Core (all already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic v2 | `pydantic-settings[yaml]==2.14.0` (pinned) | `CheckoutConfig(BaseModel)` + field validators | Already used for all config sub-models |
| pydantic-settings | same as above | `AppConfig(BaseSettings)` wiring | Already in use; `settings_customise_sources` pattern established |
| argparse | stdlib | `--monitor-only` flag on `run` subparser | Already used for all CLI args |
| pytest + pytest-asyncio | installed, `asyncio_mode=auto` | CI enforcement tests | Existing test infrastructure; no new deps needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unittest.mock` | stdlib | `AsyncMock`, `MagicMock` for plugin stubs | Existing pattern in all plugin tests |

### Alternatives Considered
None -- all tooling is already present and pinned.

## Package Legitimacy Audit

No new packages are installed in this phase. All work uses the existing pinned dependency set.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
CLI argv
  |
  v
argparse (core/cli/__init__.py: build_parser)
  --monitor-only flag -> run_p.add_argument(...)
  |
  v
handle_run (core/cli/run.py)
  reads args.monitor_only
  mutates cfg.debug.monitor_only = True if flag set
  |
  v
BotService.run(cvv) -> asyncio.run(async_main(cfg, cvv))
  |
  v
async_main -> run_plugin -> _check_and_buy
                              |
                              +-- monitor_only gate (NEW)
                              |     if plugin.config.debug.monitor_only: return
                              |     [alerts already fired above this point]
                              |
                              +-- if auto_buy: _try_auto_buy -> plugin.auto_buy()
                                                                     |
                                                                     v
                                                              place_order_guarded(click_fn)
                                                              [NEW: reads self.config.debug]
                                                              if monitor_only OR test_mode:
                                                                  log INFO, return False
                                                              else:
                                                                  await click_fn()
                                                                  return True
```

### Recommended Project Structure

No new directories needed. All changes are in-place edits to existing files:

```
core/
├── config_schema.py     # DebugConfig + CheckoutConfig + AppConfig wiring
├── plugin_base.py       # place_order_guarded() concrete method
├── orchestrator.py      # monitor_only gate in _check_and_buy
└── cli/
    ├── __init__.py      # --monitor-only on run subparser
    └── run.py           # handle_run: read args.monitor_only, mutate config
plugins/
├── shopbot_plugin_amazon.py      # reroute final click through place_order_guarded
├── shopbot_plugin_bestbuy.py     # same
├── shopbot_plugin_walmart.py     # same
├── shopbot_plugin_target.py      # same
├── shopbot_plugin_gamestop.py    # same
├── shopbot_plugin_newegg.py      # same
└── shopbot_plugin_squareenix.py  # same
tests/
└── test_safety_gate.py  # new: 7-plugin monitor_only CI test + AST grep assertion
```

### Pattern 1: CheckoutConfig -- Pydantic v2 ge bounds (mirrors ProxyConfig)

**What:** A new `BaseModel` subclass using `Field(default=..., ge=N)` for numeric tuning fields.
**When to use:** Any config section holding only numeric scalars with lower bounds.

```python
# Source: verified from core/config_schema.py ProxyConfig (lines 233-260)
class CheckoutConfig(BaseModel):
    item_timeout_secs: int = Field(default=120, ge=1)
    step_timeout_secs: int = Field(default=30, ge=1)
    max_cart_retries: int = Field(default=3, ge=0)
    backoff_base: float = Field(default=2.0, ge=0.0)
    backoff_jitter: float = Field(default=0.5, ge=0.0)
    alert_on_errors: int = Field(default=3, ge=0)
```

NOTE: `ProxyConfig` uses `@field_validator` for URL structure (complex validation). `CheckoutConfig` fields are all numeric scalars -- `Field(ge=N)` alone is sufficient; no `@field_validator` needed.

### Pattern 2: Orchestrator monitor-only gate (single-line insert)

**What:** Guard in `_check_and_buy` before `_try_auto_buy`; reads `plugin.config.debug.monitor_only`.
**When to use:** BUY-01 gate point.

```python
# Source: verified from core/orchestrator.py lines 236-237
# BEFORE (existing):
    if auto_buy:
        await _try_auto_buy(plugin, name, link, write_queue, dispatcher)

# AFTER (phase 18 change):
    if auto_buy:
        if plugin.config.debug.monitor_only:
            writeLog(
                f"[{plugin.__class__.__name__}] monitor-only: skipping auto_buy for {name}",
                "INFO",
            )
            return
        await _try_auto_buy(plugin, name, link, write_queue, dispatcher)
```

### Pattern 3: place_order_guarded() on RetailerPlugin ABC

**What:** Concrete async method reads `self.config.debug` to decide whether to invoke `click_fn`.
**When to use:** All 7 plugins replace their final `place_order.click()` call.

```python
# Source: verified from core/plugin_base.py; self.config is AppConfig (line 39)
async def place_order_guarded(self, click_fn) -> bool:
    """Invoke click_fn only when test_mode and monitor_only are both False.

    Returns True when the click fires, False when suppressed.
    Never raises. PLUGIN_API_VERSION stays 2 (additive concrete method).
    """
    debug = getattr(self.config, "debug", None) if self.config else None
    test_mode = getattr(debug, "test_mode", True)
    monitor_only = getattr(debug, "monitor_only", False)
    if test_mode or monitor_only:
        writeLog(
            "place-order suppressed (monitor_only/test_mode)",
            "INFO",
        )
        return False
    await click_fn()
    return True
```

### Pattern 4: CLI flag wiring (mirrors existing test_mode pattern)

**What:** Add `--monitor-only` to the `run` subparser; mutate `cfg.debug.monitor_only` in `handle_run`.
**When to use:** BUY-01 CLI integration.

```python
# In core/cli/__init__.py build_parser():
run_p.add_argument(
    "--monitor-only",
    action="store_true",
    default=False,
    dest="monitor_only",
    help="Run in monitor-only mode: check availability and alert but never place orders.",
)

# In core/cli/run.py handle_run():
if args.monitor_only:
    cfg.debug.monitor_only = True
```

**Key constraint:** `cfg` is obtained via `svc.get_config()` which returns the already-constructed `AppConfig` instance. Mutating `cfg.debug.monitor_only` directly is correct and consistent with how the CVV gate reads `cfg.debug.test_mode` today (line 22 of `handle_run`).

### Anti-Patterns to Avoid

- **Raising an exception from `place_order_guarded` when suppressed:** The contract is `return False` + INFO log, no exception. Exceptions break the buy-result flow.
- **Bumping `PLUGIN_API_VERSION`:** This is additive (concrete method with default behavior); the version stays 2.
- **Re-constructing `AppConfig` in `handle_run` to apply the CLI flag:** AppConfig is already constructed inside `BotService.__init__`; mutate `cfg.debug.monitor_only` on the existing instance.
- **Putting the monitor-only gate inside `_try_auto_buy`:** The gate belongs in `_check_and_buy` so it fires before `_try_auto_buy` is even called, and the INFO log can include the item name.
- **Applying `place_order_guarded` to intermediate DOM clicks (add-to-cart, checkout):** The guard wraps only the final irreversible place-order click, not earlier steps.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Numeric field bounds in config | Custom validator class | `Field(ge=N)` in Pydantic v2 | Pydantic handles at model instantiation; already used in `ProxyConfig` |
| Async test for 7 plugins | Custom test runner | pytest + `asyncio_mode=auto` | Already configured in `pyproject.toml`; `fake_plugin` fixture already exists |
| AST parse to find direct `.click()` calls on place-order | Custom AST walker | `grep` + regex over plugin source | Phase requirement says grep/AST; grep is sufficient for the enforcement test |

## Per-Plugin Place-Order Trigger Map

This is the critical deliverable for the planner. Each plugin's final place-order DOM click is enumerated below, confirmed by direct file read.

### AmazonPlugin (`plugins/shopbot_plugin_amazon.py`)
- **Method:** `auto_buy` (line 357)
- **Trigger location:** Lines 406-425
- **Selector:** `#submitOrderButtonId` (line 407)
- **Current guard:** PARTIAL -- has a `test_mode` check at lines 412-425 that skips the click in test mode; returns `False` in test mode, `True` after click in live mode.
- **What changes:** Replace the existing `if not test_mode: await place_order.click()` block (lines 412-415) with `return await self.place_order_guarded(place_order.click)`. The existing `test_pause_event` wait at lines 421-425 in test mode is replaced by the guard's INFO log.
- **Note:** The test-mode pause+wait_user_action at lines 393-398 (before the buy-now click) is separate from the place-order guard and is NOT changed in this phase.

### BestBuyPlugin (`plugins/shopbot_plugin_bestbuy.py`)
- **Method:** `auto_buy` (line 249)
- **Trigger location:** Lines 304-311
- **Selector:** `.button--place-order` (line 304)
- **Current guard:** NONE -- `place_order.click()` at line 308 fires unconditionally regardless of `test_mode`. This is the confirmed gap (BUY-02).
- **What changes:** Replace `await place_order.click()` (line 308) with `return await self.place_order_guarded(place_order.click)`. Remove the hardcoded `return True` at line 310 (guard's return value replaces it).

### WalmartPlugin (`plugins/shopbot_plugin_walmart.py`)
- **Method:** `auto_buy` (line 148)
- **Trigger location:** Lines 189-195
- **Selector:** `[data-testid="place-order-button"]` (line 189)
- **Current guard:** NONE -- `await place_order.click()` at line 192 fires unconditionally.
- **What changes:** Replace `await place_order.click()` (line 192) and the following `return True` (line 195) with `return await self.place_order_guarded(place_order.click)`.

### TargetPlugin (`plugins/shopbot_plugin_target.py`)
- **Method:** `auto_buy` (line 150)
- **Trigger location:** Lines 191-198
- **Selector:** `[data-test="placeOrder"]` (line 191)
- **Current guard:** NONE -- `await place_order.click()` at line 195 fires unconditionally.
- **What changes:** Replace `await place_order.click()` (line 195) and the following `return True` (line 197) with `return await self.place_order_guarded(place_order.click)`.

### GameStopPlugin (`plugins/shopbot_plugin_gamestop.py`)
- **Method:** `auto_buy` (line 150)
- **Trigger location:** Lines 190-199
- **Selector:** `button.place-order` (line 192)
- **Current guard:** NONE -- `await place_order.click()` at line 196 fires unconditionally.
- **What changes:** Replace `await place_order.click()` (line 196) and the following `return True` (line 198) with `return await self.place_order_guarded(place_order.click)`.

### NeweggPlugin (`plugins/shopbot_plugin_newegg.py`)
- **Method:** `auto_buy` (line 163)
- **Trigger location:** Lines 205-215
- **Selector:** `.btn-primary.btn-wide` first, then text-find "Place Order" (lines 206-208)
- **Current guard:** NONE -- `await place_order.click()` at line 212 fires unconditionally.
- **What changes:** Replace `await place_order.click()` (line 212) and the following `return True` (line 214) with `return await self.place_order_guarded(place_order.click)`.

### SquareEnixPlugin (`plugins/shopbot_plugin_squareenix.py`)
- **Method:** `auto_buy` (line 154)
- **Trigger location:** Lines 196-206
- **Selector:** `[data-testid="place-order-button"]` first, then text-find "Place Order" (lines 197-199)
- **Current guard:** NONE -- `await place_order.click()` at line 203 fires unconditionally.
- **What changes:** Replace `await place_order.click()` (line 203) and the following `return True` (line 205) with `return await self.place_order_guarded(place_order.click)`.

### Summary Table

| Plugin | File | Method | Place-Order Selector | Guard Today | Action |
|--------|------|--------|---------------------|-------------|--------|
| Amazon | shopbot_plugin_amazon.py | auto_buy L357 | `#submitOrderButtonId` L407 | Partial (test_mode only, L412-425) | Replace conditional block with `place_order_guarded` |
| BestBuy | shopbot_plugin_bestbuy.py | auto_buy L249 | `.button--place-order` L304 | NONE (confirmed gap) | Add `place_order_guarded` |
| Walmart | shopbot_plugin_walmart.py | auto_buy L148 | `[data-testid="place-order-button"]` L189 | NONE | Add `place_order_guarded` |
| Target | shopbot_plugin_target.py | auto_buy L150 | `[data-test="placeOrder"]` L191 | NONE | Add `place_order_guarded` |
| GameStop | shopbot_plugin_gamestop.py | auto_buy L150 | `button.place-order` L192 | NONE | Add `place_order_guarded` |
| Newegg | shopbot_plugin_newegg.py | auto_buy L163 | `.btn-primary.btn-wide` / "Place Order" L206-208 | NONE | Add `place_order_guarded` |
| SquareEnix | shopbot_plugin_squareenix.py | auto_buy L154 | `[data-testid="place-order-button"]` / "Place Order" L197-199 | NONE | Add `place_order_guarded` |

## Common Pitfalls

### Pitfall 1: `place_order_guarded` must be `async` (all plugins are async)
**What goes wrong:** Defining `place_order_guarded` as a sync method causes `await self.place_order_guarded(...)` to fail with `TypeError: object bool can't be used in 'await' expression`.
**Why it happens:** All plugin methods that browser-interact are `async def`; `click_fn` is a coroutine callable (nodriver element `.click()` is async).
**How to avoid:** Define as `async def place_order_guarded(self, click_fn) -> bool` on the ABC. The `await click_fn()` inside it awaits the element's async click.
**Warning signs:** `TypeError` on `await self.place_order_guarded(...)` in tests.

### Pitfall 2: Amazon's existing test-mode branch has additional logic that must not be silently dropped
**What goes wrong:** Amazon's `auto_buy` has a `test_pause_event` wait at lines 421-425 inside the current test-mode path. Simply wrapping the click is correct; the wait-for-user logic disappears. This is intentional -- `place_order_guarded` replaces the ad-hoc gate -- but must be explicitly noted so the planner doesn't try to preserve the old pause behavior.
**How to avoid:** Replace lines 412-425 entirely with `return await self.place_order_guarded(place_order.click)`. Do not try to keep the `test_pause_event` wait inside the new guard.

### Pitfall 3: `DebugConfig` is a plain `BaseModel`, not `BaseSettings`; mutation after construction works
**What goes wrong:** Confusion about whether `cfg.debug.monitor_only = True` in `handle_run` is valid (AppConfig uses `BaseSettings` but sub-models are plain `BaseModel`, which is mutable by default in pydantic v2).
**How to avoid:** Pydantic v2 `BaseModel` instances are mutable by default (no `model_config` frozen). Direct attribute assignment works. Confirmed pattern: `cfg.debug.test_mode` is already read this way in `handle_run` (line 22).

### Pitfall 4: The `write_queue` purchase path is the correct enforcement point for the CI test
**What goes wrong:** Testing "zero purchase-queue writes" by checking `update_item_purchased_sync` directly misses the write-queue abstraction. The orchestrator enqueues `("purchased", link)` tuples; the drain task calls the DB function.
**How to avoid:** The CI test must mock `write_queue` (an `asyncio.Queue`) and assert `write_queue.put_nowait` / `queue.put` was never called with a `("purchased", ...)` tuple. The existing `test_orchestrator.py` uses the write-queue pattern correctly.

### Pitfall 5: `AppConfig` `extra="ignore"` does not affect sub-model fields
**What goes wrong:** Adding `checkout` to `AppConfig` but forgetting to add `checkout: CheckoutConfig = CheckoutConfig()` as a declared field; the YAML key would be silently ignored.
**How to avoid:** Declare the field explicitly. Confirmed pattern: all existing sub-models (`debug`, `available`, `proxy`, `captcha`, etc.) are declared as class attributes.

### Pitfall 6: `DebugConfig.monitor_only` default should be `False` (not `True`)
**What goes wrong:** STATE.md line 120 contains an inconsistency: it says "DebugConfig.monitor_only defaults to True (safe default)" but CONTEXT.md (the locked decision source) says `monitor_only: bool = False`. CONTEXT.md overrides STATE.md on this point.
**How to avoid:** Use `monitor_only: bool = False`. The "safe default" in STATE.md referred to a design consideration that was resolved in the discussion phase; CONTEXT.md is the final answer.

### Pitfall 7: The CLI config ALLOWLIST (`config_cmd.py`) needs updating
**What goes wrong:** `shoppybot config set monitor_only true` fails with "unknown key" unless `monitor_only` is added to the `ALLOWLIST` dict in `core/cli/config_cmd.py`.
**How to avoid:** Add `"monitor_only": ("debug", bool)` to the `ALLOWLIST`. This mirrors the existing `"test_mode": ("debug", bool)` entry (lines 18-20 of `config_cmd.py`).

## Code Examples

### CheckoutConfig in AppConfig (after captcha)

```python
# Source: verified from core/config_schema.py lines 263-281 (AppConfig field order)
class AppConfig(BaseSettings):
    ...
    proxy: ProxyConfig = ProxyConfig()
    captcha: CaptchaConfig = CaptchaConfig()
    checkout: CheckoutConfig = CheckoutConfig()   # NEW: placed after captcha
```

### DebugConfig with monitor_only

```python
# Source: verified from core/config_schema.py lines 61-63
class DebugConfig(BaseModel):
    logging_level: int = 5
    test_mode: bool = True
    monitor_only: bool = False   # NEW
```

### handle_run with monitor_only flag

```python
# Source: verified from core/cli/run.py (full file read)
def handle_run(args, svc) -> int:
    cfg = svc.get_config()
    if getattr(args, "monitor_only", False):
        cfg.debug.monitor_only = True
    needs_cvv = (
        not cfg.debug.test_mode
        and not cfg.debug.monitor_only   # monitor-only also skips CVV prompt
        and any(
            "bestbuy.com" in item.link and item.auto_buy
            for item in cfg.available.items
        )
    )
    ...
```

Note: The CVV gate should also short-circuit on `monitor_only` since no checkout will run.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-plugin ad-hoc `test_mode` guard (Amazon only; 6 plugins unguarded) | `place_order_guarded()` on ABC (all plugins uniformly guarded) | Phase 18 | Future plugins get the guard automatically |
| No monitor-only run mode | `--monitor-only` CLI + `debug.monitor_only` config | Phase 18 | Operators can safely run in stock-alert-only mode |

**Deprecated/outdated:**
- Amazon's inline `if not test_mode: await place_order.click()` block (lines 412-425): replaced by `place_order_guarded`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pydantic v2 `BaseModel` sub-models are mutable by default (no `model_config` frozen), so `cfg.debug.monitor_only = True` is valid in `handle_run`. | Pattern 4 / Pitfall 3 | If models are frozen, direct mutation raises; would need `cfg = cfg.model_copy(update={...})` instead. | 

**Confidence note:** A1 is effectively `[VERIFIED]` by existing codebase patterns -- `cfg.debug.test_mode` is read as a mutable attribute in `handle_run` and multiple test files construct `cfg` with `MagicMock()` and set attributes directly. No `model_config` with `frozen=True` is present in `DebugConfig`.

## Open Questions

1. **Amazon test-mode pause behavior after `place_order_guarded` replaces lines 412-425**
   - What we know: The current Amazon `auto_buy` pauses with `_wait_user_action(test_pause_event)` in test mode (lines 421-425), letting the operator see the order review page.
   - What's unclear: Is this interactive pause valuable in test mode, or is the INFO log from `place_order_guarded` sufficient?
   - Recommendation: The CONTEXT.md locks `place_order_guarded` to return False + INFO log only (no exception, no interactive pause). Drop the pause. If it's needed later, it can be added as a separate test-mode hook.

2. **`needs_cvv` guard in `handle_run`: should `monitor_only` short-circuit the CVV prompt?**
   - What we know: CVV is only needed for BestBuy auto_buy in non-test mode. If monitor_only=True, `_try_auto_buy` never fires, so the CVV is never used.
   - What's unclear: Whether the planner wants the CVV prompt skipped silently or left unchanged (it's harmless to collect an unused CVV).
   - Recommendation: Add `not cfg.debug.monitor_only` to the `needs_cvv` guard for correctness and UX clarity. This is a small addition that prevents a confusing CVV prompt in monitor-only runs.

## Environment Availability

Step 2.6: SKIPPED (no external dependencies -- all work is code edits and schema additions to the existing Python package; no new tools, services, or runtimes required).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_safety_gate.py -x` |
| Full suite command | `pytest` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUY-01 | `--monitor-only` flag causes `_check_and_buy` to skip `_try_auto_buy` | unit | `pytest tests/test_safety_gate.py::test_monitor_only_skips_auto_buy -x` | Wave 0 |
| BUY-01 | `debug.monitor_only: true` config path also skips auto_buy | unit | `pytest tests/test_safety_gate.py::test_monitor_only_config_skips_auto_buy -x` | Wave 0 |
| BUY-01 | Stock alert (`detected` event) still fires in monitor-only mode | unit | `pytest tests/test_safety_gate.py::test_monitor_only_fires_alert -x` | Wave 0 |
| BUY-01 | `--monitor-only` CLI flag sets `cfg.debug.monitor_only=True` | unit | `pytest tests/test_cli_run.py -x` (extend existing) | Extend existing |
| BUY-02 | All 7 plugins with `monitor_only=True` produce zero `("purchased", ...)` writes to write_queue | integration | `pytest tests/test_safety_gate.py::test_all_plugins_monitor_only_no_purchase_write -x` | Wave 0 |
| BUY-02 | `place_order_guarded` returns False + logs INFO when `test_mode=True` | unit | `pytest tests/test_plugin_base.py::test_place_order_guarded_suppressed_test_mode -x` | Extend existing |
| BUY-02 | `place_order_guarded` returns False + logs INFO when `monitor_only=True` | unit | `pytest tests/test_plugin_base.py::test_place_order_guarded_suppressed_monitor_only -x` | Extend existing |
| BUY-02 | `place_order_guarded` calls click_fn and returns True when both flags False | unit | `pytest tests/test_plugin_base.py::test_place_order_guarded_allows_click -x` | Extend existing |
| BUY-02 | No plugin clicks place-order outside `place_order_guarded` (grep assertion) | static | `pytest tests/test_safety_gate.py::test_no_raw_place_order_click_in_plugins -x` | Wave 0 |
| BUY-02 | `CheckoutConfig` fields exist with correct defaults and `ge` bounds | unit | `pytest tests/test_config_schema.py -x` (extend existing) | Extend existing |

### Key Test Design: 7-Plugin Monitor-Only CI Test

The critical BUY-02 integration test constructs all 7 plugins with `monitor_only=True` in their config, calls `auto_buy()` on each with a mocked browser (using the existing `fake_browser` fixture pattern), and asserts the `write_queue` never receives a `("purchased", ...)` tuple.

```python
# Sketch of test_all_plugins_monitor_only_no_purchase_write
@pytest.mark.asyncio
async def test_all_plugins_monitor_only_no_purchase_write(fake_browser):
    """BUY-02: all 7 plugins with monitor_only=True produce zero purchase-queue writes."""
    import asyncio
    from unittest.mock import MagicMock, AsyncMock

    write_queue = asyncio.Queue()

    plugin_paths = [
        "shopbot_plugin_amazon", "shopbot_plugin_bestbuy", "shopbot_plugin_walmart",
        "shopbot_plugin_target", "shopbot_plugin_gamestop", "shopbot_plugin_newegg",
        "shopbot_plugin_squareenix",
    ]
    for plugin_name in plugin_paths:
        cfg = MagicMock()
        cfg.debug.monitor_only = True
        cfg.debug.test_mode = False  # test_mode=False to isolate monitor_only gate
        cfg.available.items = []
        # ... load plugin class via importlib, construct, attach fake_browser
        # ... call _check_and_buy or auto_buy through orchestrator
    
    assert write_queue.empty(), "No purchase writes expected with monitor_only=True"
```

The actual test can go through either `_check_and_buy` (tests the orchestrator BUY-01 gate) or directly call `auto_buy` and assert `place_order_guarded` returns False (tests BUY-02). Both should be present.

### Grep/AST Enforcement Test Design

```python
# Sketch of test_no_raw_place_order_click_in_plugins
def test_no_raw_place_order_click_in_plugins():
    """BUY-02: no plugin auto_buy method calls .click() on a place-order element
    outside of place_order_guarded()."""
    import re
    from pathlib import Path
    
    plugins_dir = Path(__file__).parent.parent / "plugins"
    place_order_selectors = [
        "#submitOrderButtonId",
        ".button--place-order",
        "place-order-button",
        "placeOrder",
        "place-order",
        "Place Order",
    ]
    for plugin_file in plugins_dir.glob("shopbot_plugin_*.py"):
        source = plugin_file.read_text()
        # Must contain place_order_guarded if it has auto_buy
        if "auto_buy" not in source:
            continue
        for selector in place_order_selectors:
            if selector in source:
                assert "place_order_guarded" in source, (
                    f"{plugin_file.name} contains place-order selector "
                    f"{selector!r} but does not use place_order_guarded()"
                )
```

### Sampling Rate
- **Per task commit:** `pytest tests/test_config_schema.py tests/test_plugin_base.py tests/test_safety_gate.py -x`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_safety_gate.py` -- covers BUY-01 orchestrator gate + BUY-02 7-plugin integration + grep assertion
- [ ] Extend `tests/test_plugin_base.py` -- `place_order_guarded` unit tests (3 cases: suppressed by test_mode, suppressed by monitor_only, allowed)
- [ ] Extend `tests/test_config_schema.py` -- `CheckoutConfig` defaults + ge bounds
- [ ] Extend `tests/test_cli_run.py` -- `--monitor-only` flag sets `cfg.debug.monitor_only=True`

*(No new framework install required -- pytest + pytest-asyncio already installed and configured)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | -- |
| V3 Session Management | no | -- |
| V4 Access Control | yes | monitor_only gate prevents unintended order placement |
| V5 Input Validation | yes | `ge` validators on `CheckoutConfig` numeric fields |
| V6 Cryptography | no | `CheckoutConfig` holds only tuning knobs, no secrets |

### Known Threat Patterns for Phase 18 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Plugin bypasses `place_order_guarded` via direct `.click()` call | Tampering | grep/AST CI assertion (BUY-02 enforcement) |
| `monitor_only` flag ignored if CLI doesn't mutate config | Tampering | Unit test asserts `cfg.debug.monitor_only=True` after `--monitor-only` parse |
| `CheckoutConfig` numeric field accepts negative timeout | Tampering/DoS | `Field(ge=1)` on timeout fields; `Field(ge=0)` on retry/backoff fields |
| `monitor_only: bool` default `True` accidentally set | Tampering | Default is `False` per CONTEXT.md; test asserts `AppConfig().debug.monitor_only is False` |

## Sources

### Primary (HIGH confidence)
- `core/plugin_base.py` -- RetailerPlugin ABC: `__init__`, existing concrete methods, PLUGIN_API_VERSION; all confirmed by direct read
- `core/config_schema.py` -- DebugConfig, ProxyConfig validator idiom, AppConfig field order; confirmed by direct read
- `core/orchestrator.py` -- `_check_and_buy` structure (lines 196-237), `_try_auto_buy` call point; confirmed by direct read
- `core/cli/__init__.py` -- `build_parser()`, run subparser; confirmed by direct read
- `core/cli/run.py` -- `handle_run`, CVV gate, `cfg.debug.test_mode` access pattern; confirmed by direct read
- `core/cli/config_cmd.py` -- ALLOWLIST pattern for `test_mode`; confirmed by direct read
- All 7 plugin files -- per-plugin auto_buy method, place-order selector, line numbers; confirmed by direct read
- `tests/conftest.py` -- `fake_browser`, `fake_plugin`, `mock_nodriver_start` fixtures; confirmed by direct read
- `pyproject.toml` -- pytest config (`asyncio_mode=auto`); confirmed by direct read

### Secondary (MEDIUM confidence)
- None required -- all claims are directly verified from codebase.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new packages; existing pinned deps confirmed
- Architecture: HIGH -- all 7 plugins read, exact line numbers confirmed, patterns verified from live code
- Pitfalls: HIGH -- derived from direct inspection of existing patterns and the specific Amazon partial-guard behavior
- Per-plugin trigger map: HIGH -- confirmed by direct file read, not inference

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 (stable Python/Pydantic codebase; 30-day window appropriate)
