# Phase 18: Safety Gate + Config Foundation - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the central safety gate and config foundation that every downstream v4.0 phase depends on. Three deliverables:

1. A central **monitor-only run mode** (`--monitor-only` CLI flag and/or `debug.monitor_only: true`) enforced once at the orchestrator before `auto_buy`, so it applies uniformly to all plugins (BUY-01).
2. A single concrete **`place_order_guarded()`** method on the `RetailerPlugin` ABC that honors `test_mode`/`monitor_only`, closing the confirmed hole where 6 of 7 plugins ignore `test_mode` and could place a live order (BUY-02).
3. A **`CheckoutConfig`** sub-model in `AppConfig` providing `item_timeout_secs`, `step_timeout_secs`, `max_cart_retries`, `backoff_base`, `backoff_jitter`, and `alert_on_errors` so downstream phases (19/21/22/24) consume them without further schema changes.

Out of scope: confirmation detection (Phase 19), form-fill (Phase 20), the retry engine itself (Phase 21) — this phase only ships the config fields they will read.
</domain>

<decisions>
## Implementation Decisions

### Monitor-Only Enforcement
- Enforced at the orchestrator in `_check_and_buy`, before `_try_auto_buy` is called — single uniform gate covering all plugins (BUY-01).
- `monitor_only` and `test_mode` are two independent gates: `monitor_only` skips `auto_buy` entirely at the orchestrator; `test_mode` lets checkout/form-fill run but suppresses the final place-order click via `place_order_guarded()`. Either one blocks a live order.
- `--monitor-only` CLI flag forces `True`; when the flag is absent, fall back to the `debug.monitor_only` config value (CLI overrides config).
- Stock-availability alerts and notifications still fire in monitor-only mode — monitor-only means "checks + alerts, no buy".

### place_order_guarded() Contract
- Signature: `async def place_order_guarded(self, click_fn) -> bool` — takes the async place-order callable, invokes it only when allowed, returns `bool`.
- When suppressed (monitor_only or test_mode active): return `False` and log an INFO line "place-order suppressed (monitor_only/test_mode)". No exception raised.
- Concrete method on the `RetailerPlugin` ABC reading `self.config.debug` for `test_mode`/`monitor_only`. Plugins call it for the final place-order click. Additive — `PLUGIN_API_VERSION` stays 2 (no bump).
- Enforcement is dual: (a) a CI test constructs all 7 bundled plugins with `monitor_only=True` and asserts zero writes to the purchase write-queue (success criterion 2), and (b) a grep/AST assertion that no plugin clicks the place-order element outside `place_order_guarded()`.

### CheckoutConfig Schema
- Field defaults: `item_timeout_secs=120`, `step_timeout_secs=30`, `max_cart_retries=3`, `backoff_base=2.0`, `backoff_jitter=0.5`, `alert_on_errors=3`.
- New `CheckoutConfig(BaseModel)`; added to `AppConfig` as `checkout: CheckoutConfig = CheckoutConfig()` placed after `captcha`, mirroring the existing default-instance pattern.
- `monitor_only` lives in `DebugConfig` as `monitor_only: bool = False`, alongside the existing `test_mode` run-mode flag.
- Field validation: `ge` bounds following the `ProxyConfig` validator pattern (timeouts > 0, retries ≥ 0, backoff ≥ 0).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/plugin_base.py` — `RetailerPlugin` ABC (`PLUGIN_API_VERSION = 2`); abstract `check_availability`/`auto_buy`, concrete no-op defaults for `login`/`detect_captcha`/`get_price`. `__init__(self, config)` stores typed `AppConfig` on `self.config`. This is where `place_order_guarded()` is added.
- `core/config_schema.py` — `DebugConfig(BaseModel)` has `logging_level`, `test_mode: bool = True` (add `monitor_only` here). `AppConfig(BaseSettings)` composes sub-models with the `field: Model = Model()` default-instance pattern; `ProxyConfig` shows the `@field_validator` + `Field(..., ge=...)` bounds idiom to copy for `CheckoutConfig`.
- `core/orchestrator.py` — `_check_and_buy(plugin, name, link, auto_buy, write_queue, dispatcher)` calls `_try_auto_buy` only when `auto_buy` is truthy (line ~236); `_try_auto_buy` awaits `plugin.auto_buy(link)`. The monitor-only gate goes in `_check_and_buy` before the `_try_auto_buy` call.

### Established Patterns
- Pydantic v2 `BaseModel` sub-models for config sections; opt-in features disabled by default (`enabled: bool = False` pattern in `ProxyConfig`/`CaptchaConfig`).
- `extra="ignore"` on `AppConfig`; env vars override YAML via `settings_customise_sources`.
- Security posture: secrets never in config.yml; no plaintext on disk. `CheckoutConfig` holds only numeric tuning knobs, no secrets.

### Integration Points
- CLI flag parsing: `core/cli/run.py` (run subcommand) — add `--monitor-only`.
- Orchestrator gate: `core/orchestrator.py::_check_and_buy`.
- ABC method: `core/plugin_base.py::RetailerPlugin`.
- All 7 bundled plugins under `plugins/shopbot_plugin_*.py` must route their final place-order click through `place_order_guarded()`.
- Config: `core/config_schema.py` (`DebugConfig`, new `CheckoutConfig`, `AppConfig`).

</code_context>

<specifics>
## Specific Ideas

- The known defect this closes: BestBuy and 5 other plugins ignore `test_mode` and would click place-order in test mode. The CI assertion (7 plugins × monitor_only=True → zero purchase-queue writes) is the regression guard for that hole.
- Downstream consumers of `CheckoutConfig`: Phase 21 (`item_timeout_secs`, `step_timeout_secs`, `max_cart_retries`, `backoff_*`), Phase 22 (`alert_on_errors`), Phase 24 (`alert_on_errors`). Field set is fixed now to avoid later schema churn.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Confirmation detection, form-fill, the retry engine, and the supervisor are explicitly later phases (19-22).

</deferred>
