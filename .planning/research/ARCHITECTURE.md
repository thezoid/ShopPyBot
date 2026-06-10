# Architecture Research

**Domain:** Python shopping bot — asyncio/nodriver plugin framework, v4.0 acquisition + reliability integration
**Researched:** 2026-06-10 (v4.0 Win-the-Drop integration analysis; supersedes v3.0 research)
**Confidence:** HIGH (all integration points derived from direct source reads; no inference from training data)

---

## v4.0 Scope

Two feature clusters integrate into the shipped v3.0 architecture:

1. **Acquisition Core** — checkout profile/form-fill, order-confirmation capture, idempotent retry-on-cart, per-step/per-item time budget, central monitor-only safety gate
2. **Always-On Reliability** — per-coroutine supervision + backoff restart, browser-crash detection + relaunch, encrypted session/cookie persistence, DB read-path error isolation, per-item asyncio timeout, structured health/heartbeat surface

---

## Existing Architecture (v3.0 Baseline)

```
BotService (core/service.py)
  |-- background daemon thread owns its own asyncio event loop
  |-- get_status() -> {"running": bool}   <-- extend for health surface
  +-- async_main (core/orchestrator.py)
       |-- PluginRegistry (core/registry.py)
       |    |-- _discover_plugins(): importlib scan of plugins/shopbot_plugin_*.py
       |    |-- _all_plugins: eager list; no browser yet
       |    |-- _active_plugins: post-setup; one Browser per plugin instance
       |    +-- RetailerPlugin ABC (core/plugin_base.py)
       |         |-- setup() / teardown()
       |         |-- check_availability(url) -> bool   [abstract]
       |         |-- auto_buy(url) -> bool             [abstract]
       |         |-- get_price(url) -> int | None      [concrete, returns None]
       |         |-- login() / detect_captcha()        [no-op defaults]
       |         +-- plugins/shopbot_plugin_*.py       [7 concrete plugins]
       |
       |-- write_queue (asyncio.Queue)
       |    +-- _write_queue_drain task  ->  models.py (SQLite WAL CRUD)
       |
       |-- run_plugin() per active plugin  [long-lived poll coroutine]
       |    +-- _check_and_buy()  ->  _try_auto_buy()  ->  plugin.auto_buy()
       |
       +-- NotificationDispatcher (notifications/dispatcher.py)
            +-- fan-out: SoundNotifier, DiscordNotifier, EmailNotifier, SmsNotifier

core/config_schema.py   -- Pydantic AppConfig; debug.test_mode; no checkout/profile section yet
core/credentials.py     -- CredentialStore (keyring / encrypted-file / env-var); SECRET_KEYS list
core/stealth.py         -- STEALTH_JS, apply_stealth, ProxyPool, setup_proxy_auth
models.py               -- SQLite WAL: items + price_history tables; all writes via write_queue
```

Key constraints that drive all integration decisions below:

- `RetailerPlugin.setup()` is the only place browser args are set. Any relaunch must reproduce the full setup sequence (stealth injection, proxy auth, login).
- The write-queue is the **sole write path** to SQLite. Any new write (order confirmation, session flush) must go through it or through a dedicated drain, never direct.
- `debug.test_mode` is the existing config flag for purchase suppression. Only `AmazonPlugin.auto_buy()` reads it; the other 6 plugins bypass it entirely. This is the critical safety hole v4.0 must close.
- `BotService.get_status()` currently returns only `{"running": bool}`. The health surface expands this dict.
- `CredentialStore.SECRET_KEYS` is the authoritative list; new secrets (checkout profile fields) must be added.

---

## v4.0 Component Map: New vs Modified

### New Modules

| Module | Placement | Responsibility |
|--------|-----------|----------------|
| `core/checkout_profile.py` | New module | `CheckoutProfile` dataclass; load from CredentialStore; no plaintext in config or DB |
| `core/confirmation.py` | New module | `detect_order_confirmation(tab, platform) -> str | None`; per-platform selector map; returns order_id or None |
| `core/supervisor.py` | New module | `supervise(coro, name, max_retries, backoff)` async wrapper; replaces bare task creation in orchestrator |
| `core/health.py` | New module | `HealthRegistry`; per-plugin heartbeat dict; queryable via `BotService.get_status()` |
| `core/session_store.py` | New module | Fernet-encrypted JSON cookie persistence; reuses `EncryptedFileBackend` pattern from `credentials.py` |
| `core/retry.py` | New module | `RetryPolicy` dataclass + `with_retry(coro, policy)` async helper; one unified backoff implementation |

### Modified Modules

| Module | What Changes | Why |
|--------|-------------|-----|
| `core/orchestrator.py` | Replace bare `tg.create_task` with `supervisor`; add per-item `asyncio.timeout`; wrap DB reads in try/except; thread heartbeat updates through `HealthRegistry` | Supervision, timeout, read isolation, heartbeat |
| `core/plugin_base.py` | Add `monitor_only` property (reads `AppConfig.debug.monitor_only`); add `place_order_guarded()` default that checks `monitor_only` before calling the plugin's actual place-order DOM click | Central safety gate — the ABC intercepts all plugins, not per-plugin code |
| `core/service.py` | Expand `get_status()` to pull from `HealthRegistry`; accept `monitor_only` param on `start()` | Health surface, monitor-only control |
| `core/config_schema.py` | Add `DebugConfig.monitor_only: bool = True`; add `CheckoutConfig` sub-model (per-step timeout, max cart retries, item budget); add `CheckoutConfig` to `AppConfig` | Config-driven gates and budgets |
| `core/credentials.py` | Add checkout profile keys to `SECRET_KEYS`: `CHECKOUT_FIRST_NAME`, `CHECKOUT_LAST_NAME`, `CHECKOUT_ADDRESS_LINE1`, `CHECKOUT_ADDRESS_LINE2`, `CHECKOUT_CITY`, `CHECKOUT_STATE`, `CHECKOUT_ZIP`, `CHECKOUT_COUNTRY`, `CHECKOUT_PHONE` (9 keys; no card numbers; CVV already threaded) | Secure profile storage |
| `models.py` | Add columns to `items` table: `order_id TEXT`, `confirmed_at TEXT`, `checkout_attempts INTEGER DEFAULT 0`; add new write-queue tag `confirmed` | Verified purchase tracking, retry idempotency |
| `plugins/shopbot_plugin_amazon.py` | Remove inline `test_mode` check; delegate to `place_order_guarded()` from ABC; add confirmation detection call after place-order | Centralize safety gate; verified purchase |
| `plugins/shopbot_plugin_bestbuy.py` | Same: delegate to `place_order_guarded()`; add confirmation detection | Same |
| 5 remaining plugins | Same: delegate to `place_order_guarded()` | Close the 6-of-7 safety hole |

---

## Feature-to-Component Placement

### Acquisition Core

**Checkout profile / form-fill**

- Where: `core/checkout_profile.py` (new) + `core/credentials.py` (modified SECRET_KEYS)
- `CheckoutProfile` is a frozen dataclass with typed fields: `first_name`, `last_name`, `address_line1`, `address_line2`, `city`, `state`, `zip_code`, `country`, `phone`. No card data.
- Loaded via `CheckoutProfile.from_store(get_store())` at plugin setup time. Values come exclusively from the CredentialStore; never from config.yml or models.
- Plugins that implement form-fill call `self._profile.fill_shipping_form(tab)` — a method on `CheckoutProfile` that takes a nodriver tab and performs the DOM writes. This keeps the selector logic in the profile helper, not scattered across 7 plugin files.

**Order confirmation capture**

- Where: `core/confirmation.py` (new)
- `detect_order_confirmation(tab, platform: str) -> str | None` tries a platform-keyed selector map (e.g. Amazon: `#confirmedOrderId`, BestBuy: `.order-confirmation-number`) and returns an order ID string or None.
- Called inside each plugin's `auto_buy()` AFTER the place-order click. The orchestrator only enqueues the `("confirmed", link, order_id, ts)` write-queue tuple when this returns a non-None value.
- This is the gate: `purchased=1` is set only on confirmed orders. Returning True from `auto_buy()` without a confirmed order_id logs a warning but does NOT mark purchased.
- Must come before retry logic in the build order to avoid double-buy on retry.

**Idempotent retry-on-cart**

- Where: `core/retry.py` (new) + orchestrator `_try_auto_buy` (modified)
- `RetryPolicy(max_attempts: int, backoff_base: float, jitter: float)` dataclass.
- `with_retry(coro, policy)` async helper: catches the specific "not in cart" / "cart expired" exception class (raised by the plugin), backs off, and re-calls. Does NOT retry on a confirmed order_id (idempotency: checks `items.order_id IS NOT NULL` via the write-queue drain before any retry).
- Max cart attempts is configurable via `CheckoutConfig.max_cart_retries` in config.yml (default: 3).

**Per-step / per-item checkout time budget**

- Where: `core/config_schema.py` (new `CheckoutConfig` model) + orchestrator `_check_and_buy` (modified)
- `CheckoutConfig.item_timeout_secs: int = 120` wraps the entire `_check_and_buy` call with `asyncio.timeout(item_timeout_secs)`.
- `CheckoutConfig.step_timeout_secs: int = 15` is passed to each `tab.select(selector, timeout=step_timeout_secs)` call inside plugins. Plugins currently hardcode `timeout=10`; step_timeout is the config-driven replacement.
- Both settings live in `AppConfig.checkout` (new sub-model, alongside the existing `debug`, `proxy`, `captcha` sub-models).

**Central monitor-only safety gate**

- Where: `core/plugin_base.py` (modified ABC) + `core/config_schema.py` (modified `DebugConfig`)
- Problem: `debug.test_mode` is only read by `AmazonPlugin.auto_buy()`. The other 6 plugins call their place-order selector click unconditionally.
- Solution: add `DebugConfig.monitor_only: bool = True` (default True for safety). Add `RetailerPlugin.place_order_guarded(tab, selector: str) -> bool` as a concrete method on the ABC. This method:
  1. Checks `self.config.debug.monitor_only` (not `test_mode`; the two are separate: `test_mode` is Amazon-legacy, `monitor_only` is the universal v4.0 gate).
  2. If `monitor_only=True`: logs "MONITOR-ONLY: skipping place-order click" and returns False.
  3. If `monitor_only=False`: performs the click and returns True.
- All 7 plugins replace their direct `await place_order.click()` call with `await self.place_order_guarded(tab, selector)`.
- `test_mode` in AmazonPlugin is deprecated in the same pass: Amazon reads `monitor_only` going forward; `test_mode` stays in config for backward compat but Amazon stops reading it for the purchase gate.
- `BotService.start(monitor_only: bool = True)` passes the value into `AppConfig` before calling `async_main`, so the CLI/web UI can override it without editing config.yml.

---

### Always-On Reliability

**Per-coroutine supervision + backoff restart**

- Where: `core/supervisor.py` (new) + `core/orchestrator.py` (modified)
- `supervise(coro_factory, name, policy: RetryPolicy)` is an async wrapper that:
  1. Runs `coro_factory()` inside `asyncio.shield` to prevent TaskGroup cancellation on a single plugin crash.
  2. On exception: logs the error with class name and plugin name, waits `policy.backoff_base * 2^attempt + jitter` seconds, then calls `coro_factory()` again up to `policy.max_attempts` times.
  3. After exhausting retries: marks the plugin as DEAD in `HealthRegistry`, logs ERROR, and returns without raising (the TaskGroup continues running other plugins).
- The orchestrator replaces `tg.create_task(run_plugin(...))` with `tg.create_task(supervise(lambda: run_plugin(...), name, policy))`.
- This is the key constraint: `asyncio.TaskGroup` propagates the FIRST unhandled exception to all sibling tasks, tearing down the whole group. The supervisor absorbs exceptions before they reach the TaskGroup boundary.

**Browser-crash detection + relaunch**

- Where: `core/supervisor.py` (new) + `core/plugin_base.py` (modified)
- Browser crash manifests as `nodriver` raising on `tab.evaluate()` or `driver.get()` with a connection error. The supervisor catches this class of exception specifically.
- On crash detection: the supervisor calls `plugin.relaunch()` — a new concrete method on the ABC that:
  1. Calls `plugin.teardown()` (best-effort; ignores errors).
  2. Re-runs `registry.assign_proxy(plugin)` and `registry.assign_solver(plugin)` to refresh the proxy assignment.
  3. Calls `plugin.setup()` (re-creates the Browser, re-applies stealth, re-registers proxy auth).
  4. Calls `plugin.login()` to re-authenticate.
  5. Calls `session_store.restore(plugin)` if a session file exists (restore cookies before login to minimize re-auth friction).
- The relaunch sequence order is: teardown → assign_proxy → setup (creates browser, applies stealth) → setup_proxy_auth → restore_session → login.
- `plugin.relaunch()` is a concrete ABC method. Plugins override only if their relaunch needs custom steps (e.g. Amazon passkey re-dismissal).

**Encrypted session/cookie persistence**

- Where: `core/session_store.py` (new)
- Pattern mirrors `EncryptedFileBackend` in `credentials.py`: Fernet + scrypt KDF, atomic write via `tempfile.mkstemp + os.replace`.
- `SessionStore.save(plugin_name: str, cookies: list[dict]) -> None` serializes cookie dicts to JSON, encrypts, writes to `data/sessions/{plugin_name}.bin`.
- `SessionStore.restore(tab, plugin_name: str) -> bool` decrypts and injects cookies via `tab.send(cdp.network.set_cookies(...))`. Returns True if file existed, False otherwise.
- Called in the plugin's `setup()` after stealth injection (before first navigation). Also called after relaunch.
- The passphrase is the same `SHOPBOT_STORE_PASSPHRASE` env var already used by `EncryptedFileBackend` — no new secret.
- Sessions are **never** written to DB or logged. The `data/sessions/` directory is gitignored.
- Must come before relaunch in the build order: relaunch calls `restore_session`.

**DB read-path error isolation**

- Where: `core/orchestrator.py` (modified `_check_and_buy` and `run_plugin`)
- Currently `get_items_sync` is called via `run_in_executor` inside `run_plugin`. If it raises (corrupted DB, locked file), the exception bubbles to the TaskGroup and kills the whole run.
- Fix: wrap the `run_in_executor(None, get_items_sync)` call in try/except inside `run_plugin`. On failure: log ERROR with the exception class, skip this poll cycle, continue the `while True` loop. Do not re-raise.
- Same isolation applied to all other `run_in_executor` DB reads in `_check_and_buy` (`get_item_notification_state_sync`, `get_last_price_sync`, `get_item_price_config_sync`).
- Write-queue drain already has this isolation (the `except Exception` in `_write_queue_drain`). The read path does not.

**Per-item asyncio timeout**

- Where: `core/orchestrator.py` (modified `_check_and_buy`) + `core/config_schema.py` (modified `CheckoutConfig`)
- Wrap the `await _check_and_buy(...)` call inside `run_plugin` with `async with asyncio.timeout(cfg.checkout.item_timeout_secs)`. On `TimeoutError`: log WARNING with item name and elapsed seconds, continue loop.
- The existing `asyncio.wait_for(event.wait(), timeout=300)` in `_wait_user_action` is a different guard (manual intervention wait). Both coexist; the outer item timeout is the hard ceiling.

**Structured health/heartbeat surface**

- Where: `core/health.py` (new) + `core/service.py` (modified `get_status`) + `core/orchestrator.py` (modified)
- `HealthRegistry` is a thread-safe dict wrapper: `{plugin_name: HealthEntry}`.
- `HealthEntry` fields: `status: Literal["starting", "running", "crashed", "dead", "relaunching"]`, `last_heartbeat: float` (monotonic), `consecutive_errors: int`, `last_error: str | None`, `items_checked: int`, `orders_confirmed: int`.
- Orchestrator updates `HealthRegistry` at: poll cycle start (heartbeat timestamp), after each successful `check_availability` call (items_checked++), after confirmed order (orders_confirmed++), on exception in supervisor (consecutive_errors++, status="crashed"), after relaunch (status="relaunching"), after relaunch success (status="running").
- `BotService.get_status()` returns: `{"running": bool, "plugins": {name: entry_dict}, "uptime_secs": float}`.
- Notifications dispatcher already fans out events for `detected` and `purchased` actions. Add `health_degraded` event type for when `consecutive_errors` exceeds a threshold (configurable via `CheckoutConfig.alert_on_errors: int = 5`).
- The health dict is queried by the FastAPI web UI (`GET /status`) and the existing notification dispatcher without new IPC — `BotService.get_status()` is thread-safe because `HealthRegistry` uses a `threading.Lock`.

---

## Data Flow: v4.0 Acquisition Path

```
run_plugin (per plugin coroutine, supervised)
  |
  +-- asyncio.timeout(item_timeout_secs)
  |     |
  |     +-- _check_and_buy(plugin, name, link, auto_buy, write_queue)
  |           |
  |           +-- plugin.check_availability(link) -> bool
  |           |     [on crash: supervisor catches, relaunch, retry]
  |           |
  |           +-- [available=True, auto_buy=True]
  |                 |
  |                 +-- _try_auto_buy_with_retry(plugin, name, link, write_queue, policy)
  |                       |
  |                       +-- [attempt loop, max_cart_retries]
  |                       |     |
  |                       |     +-- checkout_profile.fill_shipping_form(tab)
  |                       |     +-- plugin.place_order_guarded(tab, selector)
  |                       |     |     [if monitor_only=True: log, return False, no retry]
  |                       |     +-- confirmation.detect_order_confirmation(tab, platform)
  |                       |     |     [returns order_id or None]
  |                       |     +-- [order_id is not None]:
  |                       |           write_queue.put(("confirmed", link, order_id, ts))
  |                       |           -> models: purchased=1, order_id, confirmed_at
  |                       |           dispatcher.notify("purchased")
  |                       |     +-- [order_id is None, attempt < max_cart_retries]:
  |                       |           backoff sleep, retry from cart step
  |                       |
  |                       +-- [all attempts exhausted]: log WARNING, return False
  |
  +-- [TimeoutError]: log WARNING, continue loop

write_queue (asyncio.Queue, drained by _write_queue_drain)
  +-- ("purchased", link)                  -- legacy, still valid
  +-- ("confirmed", link, order_id, ts)    -- new v4.0 tag
  +-- ("set_available", link, ts)          -- existing
  +-- ("clear_available", link)            -- existing
```

---

## Data Flow: v4.0 Reliability Path

```
async_main
  |
  +-- _staggered_setup (unchanged; adds session restore per plugin after setup)
  |     +-- plugin.setup()
  |     +-- session_store.restore(tab, plugin_name)   [new step]
  |     +-- plugin.login()
  |
  +-- asyncio.TaskGroup
       |
       +-- _write_queue_drain (unchanged)
       |
       +-- supervise(lambda: run_plugin(plugin, ...), name, policy)  [wraps each plugin]
             |
             +-- run_plugin [while True loop]
             |     +-- DB read isolation (try/except around all run_in_executor reads)
             |     +-- heartbeat update at top of each cycle
             |
             +-- [exception in run_plugin]:
                   supervisor catches
                   |
                   +-- [connection/crash exception]: plugin.relaunch()
                   |     +-- plugin.teardown()
                   |     +-- registry.assign_proxy(plugin)
                   |     +-- plugin.setup()  [new browser, stealth, proxy auth]
                   |     +-- session_store.restore(tab, plugin_name)
                   |     +-- plugin.login()
                   |     +-- health.update(plugin_name, status="relaunching")
                   |
                   +-- [other exception]: backoff, retry run_plugin
                   |
                   +-- [retries exhausted]: health.update(status="dead"), return
```

---

## Schema Changes (models.py)

```sql
-- Idempotent ALTER TABLE additions (same pattern as v3.0 price columns)
ALTER TABLE items ADD COLUMN order_id TEXT;
ALTER TABLE items ADD COLUMN confirmed_at TEXT;
ALTER TABLE items ADD COLUMN checkout_attempts INTEGER NOT NULL DEFAULT 0;
```

New write-queue tags handled by `_dispatch_write`:

| Tag | Tuple shape | Model operation |
|-----|------------|-----------------|
| `confirmed` | `("confirmed", link, order_id, ts)` | `UPDATE items SET purchased=1, order_id=?, confirmed_at=? WHERE link=?`; increments `checkout_attempts` |
| existing `purchased` | `("purchased", link)` | unchanged; still valid for legacy test paths |

The `purchased` write-queue path is NOT removed. It stays as the write path when `auto_buy()` succeeds but confirmation detection fails (e.g. confirmation page loads too slowly). In that case a WARNING is logged: "purchase click succeeded but confirmation not detected — marking purchased without order_id".

---

## Config Schema Changes (config_schema.py)

```python
class CheckoutConfig(BaseModel):
    item_timeout_secs: int = 120       # outer asyncio.timeout per item
    step_timeout_secs: int = 15        # tab.select timeout per DOM step
    max_cart_retries: int = 3          # retry-on-cart attempts
    backoff_base: float = 2.0          # seconds; doubles per attempt
    backoff_jitter: float = 1.0        # random uniform [0, jitter] added
    alert_on_errors: int = 5           # consecutive errors before health alert

class DebugConfig(BaseModel):
    logging_level: int = 5
    test_mode: bool = True             # Amazon legacy; kept for compat
    monitor_only: bool = True          # v4.0 universal safety gate (default safe)

# AppConfig gains:
checkout: CheckoutConfig = CheckoutConfig()
```

New `SECRET_KEYS` additions (9 keys; no card numbers; PCI constraint preserved):

```python
"CHECKOUT_FIRST_NAME", "CHECKOUT_LAST_NAME",
"CHECKOUT_ADDRESS_LINE1", "CHECKOUT_ADDRESS_LINE2",
"CHECKOUT_CITY", "CHECKOUT_STATE", "CHECKOUT_ZIP",
"CHECKOUT_COUNTRY", "CHECKOUT_PHONE",
```

---

## Architectural Patterns

### Pattern 1: ABC Concrete Method as Cross-Cutting Gate

`RetailerPlugin.place_order_guarded()` is a concrete method on the ABC that all 7 plugins call instead of a direct `.click()`. This is the only design that closes the 6-of-7 safety hole without editing each plugin independently. The alternative (per-plugin `if self.config.debug.monitor_only: return False`) would require 7 edit points and would break again on every new community plugin.

```python
# core/plugin_base.py (addition to RetailerPlugin)
async def place_order_guarded(self, tab, selector: str) -> bool:
    """Click the place-order button unless monitor_only is active.

    All 7 plugins replace their direct await place_order.click() with this.
    Returns True if click was performed, False if suppressed.
    """
    monitor_only = getattr(getattr(self.config, "debug", None), "monitor_only", True)
    if monitor_only:
        writeLog(
            f"[{self.__class__.__name__}] MONITOR-ONLY: skipping place-order click",
            "INFO",
        )
        return False
    element = await tab.select(selector, timeout=15)
    if not element:
        return False
    await element.click()
    return True
```

### Pattern 2: Supervisor-Wrapped Coroutine Factory

The orchestrator passes a factory (not the coroutine itself) to the supervisor so the supervisor can create a fresh coroutine on each restart attempt. Passing the coroutine directly would fail on the second attempt because a consumed coroutine cannot be re-awaited.

```python
# core/orchestrator.py (modified tg.create_task call)
tg.create_task(
    supervise(
        coro_factory=lambda: run_plugin(plugin, write_queue, poll_interval, dispatcher),
        name=f"poll-{plugin.__class__.__name__}",
        policy=RetryPolicy(max_attempts=5, backoff_base=2.0, jitter=1.0),
        health=health_registry,
    ),
    name=f"supervised-{plugin.__class__.__name__}",
)
```

### Pattern 3: Confirmation-Before-Purchased Write

The orchestrator must NOT enqueue `("purchased", link)` until `detect_order_confirmation()` returns. The existing `_try_auto_buy` returns True immediately after `place_order.click()` without waiting for confirmation. The v4.0 path changes this:

```
auto_buy(url) -> bool
  [does DOM interactions up to and including place_order_guarded]
  [does NOT call confirmation detection -- that stays in orchestrator]
  returns True = "place-order click was performed and not suppressed"

_try_auto_buy_with_retry (orchestrator):
  success = await plugin.auto_buy(link)
  if not success:
      return
  order_id = await confirmation.detect_order_confirmation(tab, plugin_name)
  if order_id:
      write_queue.put(("confirmed", link, order_id, ts))
  else:
      writeLog("WARNING: place-order succeeded but confirmation not detected", "WARNING")
      write_queue.put(("purchased", link))   # fallback; no order_id persisted
```

This preserves backward compatibility: a plugin that cannot return the browser tab (e.g. opens a new window) still falls back to the legacy `purchased` write.

### Pattern 4: Reuse EncryptedFileBackend for Session Store

`core/session_store.py` does not re-implement encryption. It instantiates `EncryptedFileBackend` with the same `SHOPBOT_STORE_PASSPHRASE` and a per-plugin path. This avoids a second KDF implementation and reuses the already-tested atomic write logic.

---

## Anti-Patterns

### Anti-Pattern 1: Per-Plugin monitor_only Check

**What people do:** Copy the Amazon `test_mode` pattern into each of the 6 other plugins, adding `if self.config.debug.monitor_only: return False` at the top of each `auto_buy()`.

**Why it's wrong:** Every new community plugin written without this check bypasses the gate. The ABC concrete-method approach makes the safe path the default path.

**Do this instead:** `place_order_guarded()` on the ABC. Plugins that never reach a place-order step (monitor-only retailers) don't need to call it.

### Anti-Pattern 2: Direct DB Writes from Plugin Code

**What people do:** Call `update_item_purchased_sync(link)` directly inside `auto_buy()` after confirmation is detected.

**Why it's wrong:** Breaks the write-queue serialization guarantee (ASYNC-05). Two plugins buying the same item (if items overlap) could interleave writes. The write-queue is a single-consumer asyncio.Queue; that guarantee is voided by any out-of-band write.

**Do this instead:** Return True from `auto_buy()` and let the orchestrator enqueue `("confirmed", ...)`. The confirmation detection also runs in the orchestrator, not in the plugin.

### Anti-Pattern 3: Tearing Down the TaskGroup on Crash

**What people do:** Let an exception from a crashed plugin bubble through `run_plugin` up to the TaskGroup. `asyncio.TaskGroup` cancels all sibling tasks on the first unhandled exception.

**Why it's wrong:** One BestBuy browser crash at 3am kills Amazon, Walmart, and all other plugins. The `except*` handler in `async_main` only catches `KeyboardInterrupt`, not plugin crashes.

**Do this instead:** The supervisor absorbs exceptions before the TaskGroup boundary. Each plugin's crash is isolated to that plugin's supervised coroutine.

### Anti-Pattern 4: Re-Creating the TaskGroup After a Crash

**What people do:** Catch the TaskGroup exception, tear everything down, and restart `async_main` from scratch.

**Why it's wrong:** A full restart re-runs `_staggered_setup` (re-launches all browsers with 1.5s stagger), taking 10+ seconds during a drop. The supervisor's per-coroutine restart leaves all other plugins running while only the crashed one relaunches.

**Do this instead:** The supervisor restarts only the failed plugin's coroutine. The TaskGroup and all other coroutines remain unaffected.

---

## Build Order (Dependency-Ordered)

Dependencies drive the order. Each phase listed below is a candidate for a planning phase in the roadmap:

**Phase A: Safety Gate + Config Foundation**
- Add `DebugConfig.monitor_only` and `CheckoutConfig` to `config_schema.py`
- Add `place_order_guarded()` concrete method to `RetailerPlugin` ABC
- Update all 7 plugins to call `place_order_guarded()` (remove per-plugin `test_mode` checks from Amazon; no-op change for the other 6 since they previously had no gate)
- Add `checkout` sub-model to `AppConfig`
- Result: monitor-only gate is live for all plugins; config foundation exists for all downstream work
- No downstream dependencies; this is the safest change to ship first

**Phase B: DB Schema + Write-Queue Tag**
- Add `order_id`, `confirmed_at`, `checkout_attempts` columns to `items` table (idempotent ALTER TABLE)
- Add `confirmed` tag handling to `_dispatch_write` in orchestrator
- Result: DB can receive confirmed-order writes; write-queue drain handles the new tag
- Required before confirmation detection can persist anything

**Phase C: Confirmation Detection**
- Build `core/confirmation.py` with per-platform selector map (Amazon, BestBuy first; others stub)
- Wire confirmation call into orchestrator `_try_auto_buy` path
- Result: confirmed purchases write `order_id` + `confirmed_at`; unconfirmed purchases fall back to legacy `purchased` write with WARNING log
- Must come before retry logic (confirmation is the idempotency check that prevents double-buy on retry)

**Phase D: Checkout Profile + Form-Fill**
- Add 9 checkout keys to `SECRET_KEYS` in `credentials.py`
- Build `core/checkout_profile.py` with `CheckoutProfile` dataclass and `fill_shipping_form(tab)` method
- Implement form-fill in BestBuy plugin first (most reliable selector history); Amazon second
- Add `shoppybot setup checkout-profile` CLI command to populate keys interactively
- Result: form-fill works for BestBuy and Amazon; other plugins stub

**Phase E: Retry-on-Cart**
- Build `core/retry.py` with `RetryPolicy` and `with_retry`
- Wire into `_try_auto_buy` in orchestrator (replaces single-attempt call)
- Idempotency check: reads `items.order_id IS NOT NULL` before any retry attempt
- Result: transient cart failures retry with backoff without double-buying

**Phase F: Encrypted Session Persistence**
- Build `core/session_store.py` (reuses `EncryptedFileBackend` pattern)
- Add `session_store.save()` call at end of successful `login()` in Amazon and BestBuy plugins
- Add `session_store.restore()` call in `_staggered_setup` after `plugin.setup()` and before `plugin.login()`
- Result: sessions survive restarts; login frequency reduced
- Must come before relaunch implementation (relaunch calls restore)

**Phase G: Supervisor + Browser Relaunch**
- Build `core/supervisor.py`
- Add `plugin.relaunch()` concrete method to ABC
- Replace bare `tg.create_task(run_plugin(...))` with `tg.create_task(supervise(...))` in orchestrator
- Add DB read isolation (try/except around all `run_in_executor` read calls in orchestrator)
- Add per-item `asyncio.timeout` wrapping `_check_and_buy` call in `run_plugin`
- Result: crashes are isolated; auto-relaunch preserves session; DB read errors are non-fatal

**Phase H: Health Surface**
- Build `core/health.py` with `HealthRegistry` and `HealthEntry`
- Thread heartbeat updates through supervisor and orchestrator
- Expand `BotService.get_status()` to return plugin health dict
- Wire `health_degraded` event type to notification dispatcher
- Update FastAPI `/status` endpoint to surface the expanded dict
- Result: queryable health; degraded-plugin alerts via existing notification channels

---

## Integration Points Summary

| Feature | Touches ABC | Touches Orchestrator | New Module | Modified Config |
|---------|-------------|---------------------|------------|-----------------|
| monitor_only gate | YES (`place_order_guarded`) | NO | NO | `DebugConfig.monitor_only` |
| Checkout profile | NO (injected at plugin level) | NO | `checkout_profile.py` | `SECRET_KEYS` +9 |
| Confirmation detection | NO (called from orchestrator) | YES (`_try_auto_buy`) | `confirmation.py` | NO |
| Retry-on-cart | NO | YES (`_try_auto_buy`) | `retry.py` | `CheckoutConfig` |
| Time budgets | NO | YES (wraps `_check_and_buy`) | NO | `CheckoutConfig` |
| Session persistence | YES (`relaunch`) | partial (restore in setup) | `session_store.py` | NO |
| Supervision | NO | YES (replaces `tg.create_task`) | `supervisor.py` | NO |
| Browser relaunch | YES (`relaunch()`) | called from supervisor | NO | NO |
| DB read isolation | NO | YES (try/except on reads) | NO | NO |
| Per-item timeout | NO | YES (wraps `_check_and_buy`) | NO | `CheckoutConfig` |
| Health surface | NO | YES (heartbeat updates) | `health.py` | `CheckoutConfig.alert_on_errors` |

---

## Sources

- Source reads: `core/service.py`, `core/orchestrator.py`, `core/registry.py`, `core/plugin_base.py`, `core/credentials.py`, `core/stealth.py`, `core/config_schema.py`, `models.py`, `plugins/shopbot_plugin_amazon.py`, `plugins/shopbot_plugin_bestbuy.py`, `plugins/shopbot_plugin_walmart.py`, `plugins/shopbot_plugin_target.py`, `plugins/shopbot_plugin_gamestop.py`
- All integration points derived from direct source reads; no inference from training data
- asyncio.TaskGroup exception propagation behavior: Python 3.11 docs (exception group semantics)
- Fernet/scrypt pattern: `core/credentials.py` `EncryptedFileBackend` (HIGH confidence, read directly)

---

*Architecture research for: ShopPyBot v4.0 Win-the-Drop — asyncio/nodriver acquisition + reliability integration*
*Researched: 2026-06-10*
