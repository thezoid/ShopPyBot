---
phase: 18-safety-gate-config-foundation
verified: 2026-06-11T00:00:00Z
status: human_needed
score: 7/7 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run `python main.py --monitor-only` (or `python -m core.cli run --monitor-only`) against a live retailer with auto_buy enabled and an in-stock item"
    expected: "Bot detects availability, fires a stock-alert notification, but never progresses to checkout or places any order. No 'purchased' row is written to the DB."
    why_human: "Cannot execute a live browser session against a real retailer in CI on this Windows dev box. End-to-end browser launch, nodriver, and live retail sites are required. This is explicitly documented in the phase instructions as UAT debt."
---

# Phase 18: Safety Gate + Config Foundation Verification Report

**Phase Goal:** Every plugin routes its final place-order action through an ABC-enforced gate that honors monitor-only mode, so no plugin (current or future) can place a live order when monitoring is active.
**Verified:** 2026-06-11
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | `monitor_only` enforced ONCE at orchestrator in `_check_and_buy`, before `_try_auto_buy` | VERIFIED | `orchestrator.py:237-244`: reads `debug_cfg.monitor_only`, logs and returns before calling `_try_auto_buy`. `_try_auto_buy` itself has no gate -- the gate is strictly upstream. |
| 2  | Stock-alert notifications still fire under monitor_only (availability detected before the gate) | VERIFIED | `orchestrator.py:224-229`: `dispatcher.notify(detected)` and `write_queue.put(set_available)` both execute before the `auto_buy` gate block at line 236. |
| 3  | `--monitor-only` CLI flag wired: sets `cfg.debug.monitor_only = True` before `svc.run()` | VERIFIED | `core/cli/run.py:21-28`: `if getattr(args, "monitor_only", False): cfg.debug.monitor_only = True`. |
| 4  | `debug.monitor_only` config field exists with default `False` | VERIFIED | `core/config_schema.py:64`: `monitor_only: bool = False  # BUY-01` inside `DebugConfig`. |
| 5  | `place_order_guarded()` is a concrete async method on `RetailerPlugin` ABC | VERIFIED | `core/plugin_base.py:81-103`: full implementation with `getattr` fail-safe, `writeLog`, and `await click_fn()`. Not abstract. `PLUGIN_API_VERSION` comment confirms additive-safe. |
| 6  | All 7 bundled plugins route their final place-order click through `place_order_guarded` | VERIFIED | Amazon (`plugin_base.py:420`): `return await self.place_order_guarded(place_order.click)`. BestBuy (`line 308`): same. Walmart (`line 193`): same. Target (`line 195`): same. GameStop (`line 196`): same. NewEgg (`line 212`): same. SquareEnix (`line 203`): same. Every `auto_buy` method ends with `place_order_guarded`. |
| 7  | `CheckoutConfig` in `AppConfig` has all 6 required fields with `ge` bounds | VERIFIED | `core/config_schema.py:264-272`: `item_timeout_secs(ge=1)`, `step_timeout_secs(ge=1)`, `max_cart_retries(ge=0)`, `backoff_base(ge=0.0)`, `backoff_jitter(ge=0.0)`, `alert_on_errors(ge=0)`. All 6 present. `AppConfig.checkout` field at line 294 wires it. |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/plugin_base.py` | `place_order_guarded` concrete method on ABC | VERIFIED | Lines 81-103; fail-safe on missing `config.debug` uses `True` default (CR-01 post-review fix confirmed at line 98). |
| `core/config_schema.py` | `DebugConfig.monitor_only` field; `CheckoutConfig` with 6 fields | VERIFIED | Lines 64 and 264-272 respectively. |
| `core/orchestrator.py` | Gate in `_check_and_buy` before `_try_auto_buy` | VERIFIED | Lines 237-244. |
| `core/cli/run.py` | `--monitor-only` flag mutates config before `svc.run()` | VERIFIED | Lines 21-28. |
| `core/cli/config_cmd.py` | `monitor_only` in ALLOWLIST for `config set` | VERIFIED | Line 20: `"monitor_only": ("debug", bool)`. |
| `plugins/shopbot_plugin_amazon.py` | Routes through `place_order_guarded` | VERIFIED | Line 420. Also has defence-in-depth early return at line 371-373 (monitor_only check at `auto_buy` entry). |
| `plugins/shopbot_plugin_bestbuy.py` | Routes through `place_order_guarded`; prior unconditional-click gap closed | VERIFIED | Line 308. Prior gap (unconditional `.click()` on `.button--place-order`) is replaced. No raw `.click()` on place-order selectors found by static grep test. |
| `plugins/shopbot_plugin_walmart.py` | Routes through `place_order_guarded` | VERIFIED | Line 193. |
| `plugins/shopbot_plugin_target.py` | Routes through `place_order_guarded` | VERIFIED | Line 195. |
| `plugins/shopbot_plugin_gamestop.py` | Routes through `place_order_guarded` | VERIFIED | Line 196. |
| `plugins/shopbot_plugin_newegg.py` | Routes through `place_order_guarded` | VERIFIED | Line 212. |
| `plugins/shopbot_plugin_squareenix.py` | Routes through `place_order_guarded` | VERIFIED | Line 203. |
| `tests/test_safety_gate.py` | CI test loading all 7 real plugins with monitor_only=True; asserts zero purchase-queue writes | VERIFIED | 3 tests: T-18-10 (static grep, 2-tier), T-18-11 (7-plugin mock), orchestrator cross-check. All 3 PASS (confirmed by live test run). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| CLI `--monitor-only` flag | `cfg.debug.monitor_only = True` | `run.py:21-28` | WIRED | Mutation on live config reference before `svc.run()`. |
| `_check_and_buy` | Orchestrator gate blocks `_try_auto_buy` | `orchestrator.py:237-244` | WIRED | `getattr(debug_cfg, "monitor_only", False)` -- returns early, `_try_auto_buy` never called. |
| All 7 `auto_buy` methods | `place_order_guarded` | `place_order.click` passed as callable | WIRED | Every plugin's final place-order DOM element is passed into `place_order_guarded` rather than called directly. |
| `place_order_guarded` | Fail-safe for missing/None config | `getattr` chain with `True` defaults | WIRED | `debug = getattr(self.config, "debug", None) if self.config else None`; `monitor_only = getattr(debug, "monitor_only", True)` -- CR-01 post-review fix confirmed at line 98. |
| `CheckoutConfig` | `AppConfig` | `checkout: CheckoutConfig = CheckoutConfig()` at line 294 | WIRED | Field is present and initialized. |

### Data-Flow Trace (Level 4)

Not applicable. This phase delivers configuration schema, an ABC method, and an orchestrator gate -- no dynamic-data-rendering components.

### Behavioral Spot-Checks (Step 7b)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 3-test suite: static grep, 7-plugin mock, orchestrator cross-check | `pytest tests/test_safety_gate.py -v` | `3 passed, 1 warning in 7.12s` | PASS |
| `monitor_only` field accessible on default config | Python inline | `DebugConfig().monitor_only == False` confirmed by schema read | PASS |
| `CheckoutConfig` all 6 fields with ge bounds | Schema read | All 6 confirmed at lines 264-272 | PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| BUY-01 | monitor-only mode enforced once at orchestrator; config flag; CLI flag; stock alerts unaffected | SATISFIED | `DebugConfig.monitor_only`, `run.py` CLI wiring, `orchestrator.py:237-244` gate, notifications fire before gate. |
| BUY-02 | `place_order_guarded` concrete method on ABC; all 7 plugins route through it; BestBuy gap closed | SATISFIED | `plugin_base.py:81-103`; all 7 plugin files verified individually; CI test T-18-10 static grep confirms no raw click on place-order selectors. |

Both requirements marked Complete in REQUIREMENTS.md traceability table (lines 66-67).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `plugins/shopbot_plugin_bestbuy.py` | 269 | `# TODO: verify ".a-dropdown-prompt" is correct for BestBuy cart` | Info | Selector correctness UAT debt; does not affect safety gate. No issue/PR reference, but this is a pre-existing selector question about quantity dropdown, not the place-order path. |
| Multiple plugin files | Various | `# TODO: verify selectors against live <retailer>` | Info | Availability and checkout selector accuracy UAT debt. Pre-existing, selector-only scope; all place-order paths are guarded regardless of selector accuracy. |

No `TBD`, `FIXME`, or `XXX` markers found in phase-modified files. All `TODO` markers are scoped to unverified selectors (not safety-gate logic) and are pre-existing known limitations documented in the plugins. No blockers.

### Human Verification Required

#### 1. Live `--monitor-only` end-to-end run

**Test:** Start the bot with `--monitor-only` against a live retailer (BestBuy or Amazon recommended) that has an in-stock item with `auto_buy: true` configured.
**Expected:** Bot detects the item as available, fires a stock-alert notification (Discord/email/sound as configured), logs "monitor-only: skipping auto_buy", and writes no "purchased" row to `data/shop_py_bot.db`. Browser does not navigate to checkout.
**Why human:** Requires a live browser session (nodriver/Chrome), a real retailer URL with an in-stock item, and credentials. Cannot run headlessly in CI on this Windows dev box. End-to-end retail checkout testing is explicitly Out of Scope for CI per REQUIREMENTS.md.

### Gaps Summary

No gaps. All 7 must-have truths are verified against the actual source code. The sole remaining item is the live `--monitor-only` UAT run, which is recorded as human verification debt per the phase instructions.

---

_Verified: 2026-06-11_
_Verifier: Claude (gsd-verifier)_
