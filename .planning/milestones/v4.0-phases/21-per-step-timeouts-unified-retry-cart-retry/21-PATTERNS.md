# Phase 21: Per-Step Timeouts + Unified Retry + Cart-Retry - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 8 (2 new, 6 modified)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `core/retry.py` | utility | transform | `core/stealth.py` (_ProxyEntry dataclass + pure helpers) | role-match |
| `models.py` | model | CRUD | `models.py` get_item_notification_state_sync / update_item_purchased_sync (same file, additive) | exact |
| `core/orchestrator.py` | orchestrator | request-response | `core/orchestrator.py` _try_auto_buy + _check_and_buy (same file, additive wrapper) | exact |
| `core/plugin_base.py` | base class | — | `core/plugin_base.py` __init__ attrs (self.driver, self._checkout_profile) | exact |
| `plugins/shopbot_plugin_amazon.py` | plugin | request-response | `plugins/shopbot_plugin_amazon.py` asyncio.timeout(120) captcha block (lines 172-178) | exact |
| `plugins/shopbot_plugin_bestbuy.py` | plugin | request-response | `plugins/shopbot_plugin_bestbuy.py` asyncio.timeout(120) captcha block (lines 116-122) | exact |
| `tests/test_retry.py` | test | — | `tests/test_no_cvv_in_logs.py` AST walk structure | role-match |
| `tests/test_cart_retry.py` | test | — | `tests/test_orchestrator.py` + `tests/test_confirmation.py` async unit patterns | role-match |

---

## Pattern Assignments

### `core/retry.py` (utility, transform)

**Analog:** `core/stealth.py` lines 151-162 (dataclass) + `core/confirmation.py` lines 1-11 (module header)

**Module header pattern** (`core/confirmation.py` lines 1-11):
```python
"""<one-line purpose sentence>.

No plugin or models imports -- this module only depends on <stdlib>.
"""
from __future__ import annotations

import <stdlib>
from dataclasses import dataclass
```

**Dataclass pattern** (`core/stealth.py` lines 151-157):
```python
@dataclass
class _ProxyEntry:
    """Single proxy slot with failure tracking and cooldown state."""
    url: str               # full URL including creds; NEVER log this field
    host_port: str         # host:port only; safe to log
    username: str
```

Mirrored structure for `RetryPolicy`:
```python
@dataclass
class RetryPolicy:
    max_attempts: int
    backoff_base: float
    backoff_jitter: float
```

**Injectable-rng pattern** (no existing analog -- new for deterministic tests):
- `compute_delay(attempt, policy, rng=random)` -- default `rng` is the `random` module; tests pass `random.Random(42)`.
- `attempt` is 0-indexed: `backoff_base**0 == 1.0` at first attempt.

**with_retry loop constraint:** The `for attempt in range(policy.max_attempts)` loop is ONLY allowed in `core/retry.py`. All other files call `with_retry(...)`. This is enforced by the CI AST assertion in `tests/test_no_retry_loops.py`.

---

### `models.py` (model, CRUD -- additive helpers)

**Analog A: `get_item_notification_state_sync`** (lines 141-150) -- exact template for `get_item_order_state_sync`:

```python
# models.py lines 141-150
def get_item_notification_state_sync(link: str) -> tuple[bool, str | None]:
    """Return (last_seen_available as bool, last_notified) for dedup checks (NOTIF-02)."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT last_seen_available, last_notified FROM items WHERE link=?",
            (link,),
        ).fetchone()
    if row is None:
        return False, None
    return bool(row[0]), row[1]
```

New helper copies this exactly, changing columns to `purchased, order_id` and docstring to reference BUY-05.

**Analog B: `update_item_purchased_sync`** (lines 101-104) -- exact template for `increment_checkout_attempts_sync`:

```python
# models.py lines 101-104
def update_item_purchased_sync(link):
    """Set purchased=1 for the item with the given link."""
    with get_db_connection() as conn:
        conn.execute("UPDATE items SET purchased=1 WHERE link=?", (link,))
```

New helper changes body to `"UPDATE items SET checkout_attempts = checkout_attempts + 1 WHERE link=?"`.

**Analog C: `update_item_confirmed_sync`** (lines 107-117) -- shows that multi-column UPDATE and the `order_id` column already exist; confirms `get_item_order_state_sync` can SELECT `purchased, order_id` without schema changes.

---

### `core/orchestrator.py` (orchestrator -- additive wrapper)

**Analog: existing `_try_auto_buy`** (lines 183-222) -- shown as the BEFORE state and the seam for extraction.

**Before (lines 183-222 -- full current function):**
```python
async def _try_auto_buy(plugin, name, link, write_queue, dispatcher) -> None:
    from core.confirmation import detect_order_confirmation
    try:
        success = await plugin.auto_buy(link)
    except Exception as exc:
        writeLog(f"[{plugin.__class__.__name__}] auto_buy error: {exc}", "ERROR")
        return
    if not success:
        return
    # ... dispatcher.notify, get_active_tab, detect_order_confirmation ...
    if order_id is not None:
        await write_queue.put(("confirmed", link, order_id, ts))
    else:
        await write_queue.put(("purchased", link))
```

**Extraction target:** A new `_attempt_buy(plugin, link) -> tuple[bool, str | None]` pulls out the `auto_buy` call + `detect_order_confirmation` call and returns `(success, order_id)` with NO enqueue. The `write_queue.put()` calls remain in a thin wrapper OUTSIDE the retry loop (invariant WR-02 preserved).

**run_in_executor pattern** (`core/orchestrator.py` line 251):
```python
# Line 251 -- the pattern for DB reads inside async functions
was_available, _ = await loop.run_in_executor(None, get_item_notification_state_sync, link)
```

New DB reads use: `loop = asyncio.get_running_loop()` then `await loop.run_in_executor(None, get_item_order_state_sync, link)`.

**Imports addition:** `get_item_order_state_sync` and `increment_checkout_attempts_sync` added to the `from models import (...)` block at lines 26-39. `from core.retry import RetryPolicy, with_retry` added to module-level imports.

**Cart-retry call site** (`core/orchestrator.py` line 273):
```python
# Line 273 -- current call; cart-retry wrapper replaces this
await _try_auto_buy(plugin, name, link, write_queue, dispatcher)
```

---

### `core/plugin_base.py` (base class -- one-line addition)

**Analog: existing `__init__` attributes** (lines 39-47):
```python
def __init__(self, config) -> None:
    self.config = config   # typed AppConfig passed by registry
    self.driver = None     # set by setup(); never in __init__ (nodriver constraint)
    self._checkout_profile = None  # BUY-07: loaded by setup()
```

**Addition:** `self._checkout_stage: str = ""` added as fourth attribute with inline comment:
```python
self._checkout_stage: str = ""  # BUY-06: set before each DOM stage; readable on CancelledError
```

Follow the same inline-comment style as `self.driver = None` (one-liner explanation, no blank lines between attrs).

---

### `plugins/shopbot_plugin_amazon.py` (plugin -- per-step timeouts, 6 stages)

**Analog: captcha timeout block** (lines 172-178):
```python
# Amazon lines 172-178 -- exact idiom to mirror per DOM step
loop = asyncio.get_running_loop()
try:
    async with asyncio.timeout(120):
        token = await loop.run_in_executor(
            None, solver.solve_recaptcha, sitekey, pageurl
        )
except (asyncio.TimeoutError, Exception) as exc:
    _log.warning("CAPTCHA solve failed: %s", exc.__class__.__name__)
```

**Per-stage pattern to use (no run_in_executor -- pure nodriver awaits):**
```python
self._checkout_stage = "navigate"
async with asyncio.timeout(step_timeout_secs):
    tab = await self.driver.get(url)
```

The `step_timeout_secs` value comes from `self.config.checkout.step_timeout_secs` (already in `CheckoutConfig`). The outer `except Exception` in `auto_buy` catches `asyncio.TimeoutError` (Python 3.11: `TimeoutError` subclasses `Exception`) and returns `False` after logging `self._checkout_stage`.

**6 stages and their current line anchors (from RESEARCH.md verified map):**

| Stage | Current Line | Action |
|---|---|---|
| `"navigate"` | ~386 | `tab = await self.driver.get(url)` |
| `"quantity-select"` | ~397-408 | dropdown click + quantity select |
| `"buy-now"` | ~418-424 | `#buy-now-button` select + click |
| `"place-order-select"` | ~426-430 | `#submitOrderButtonId` select |
| `"cvv-entry"` | ~432-439 | `#addCreditCardCvvInput` send_keys |
| `"place-order"` | ~442 | `place_order_guarded(place_order.click)` |

`test-pause` (~410-415) is a user-action gate (`_wait_user_action`); do NOT wrap in `asyncio.timeout`.

---

### `plugins/shopbot_plugin_bestbuy.py` (plugin -- per-step timeouts, 8 stages)

**Analog: captcha timeout block** (lines 116-122):
```python
# BestBuy lines 116-122 -- same idiom as Amazon
loop = asyncio.get_running_loop()
try:
    async with asyncio.timeout(120):
        token = await loop.run_in_executor(
            None, solver.solve_recaptcha, sitekey, pageurl
        )
except (asyncio.TimeoutError, Exception) as exc:
    _log.warning("BestBuy CAPTCHA solve failed: %s", exc.__class__.__name__)
```

**8 stages and their current line anchors (from RESEARCH.md verified map):**

| Stage | Current Line | Action |
|---|---|---|
| `"navigate"` | ~292 | `tab = await self.driver.get(url)` |
| `"add-to-cart"` | ~294-299 | `.add-to-cart-button` select + click |
| `"cart-navigate"` | ~301 | `self.driver.get("https://www.bestbuy.com/cart")` |
| `"quantity-select"` | ~303-320 | dropdown + quantity select |
| `"checkout-proceed"` | ~322-327 | `.checkout-buttons__checkout` select + click |
| `"address-fill"` | ~332-358 | `_fill_field` loop for 7 fields |
| `"cvv-entry"` | ~360-364 | `#credit-card-cvv` send_keys |
| `"place-order"` | ~366-371 | `.button--place-order` + `place_order_guarded` |

`login()` at ~330 is a user-action gate; do NOT wrap in `asyncio.timeout`.

---

### `tests/test_retry.py` + `tests/test_no_retry_loops.py` (tests)

**Analog: `tests/test_no_cvv_in_logs.py`** (full file, lines 1-83)

**AST walk structure to copy** (lines 27-83):
```python
# test_no_cvv_in_logs.py lines 27-43 -- file list + existence guard
repo_root = Path(__file__).parent.parent
checkout_files = [
    repo_root / "plugins" / "shopbot_plugin_bestbuy.py",
    ...
]
for path in checkout_files:
    assert path.is_file(), (
        f"CVV log scan target not found: {path} -- check for path drift"
    )

# lines 45-83 -- ast.walk + violation accumulation + assert
violations: list[str] = []
for path in checkout_files:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        ...
assert not violations, "violation description:\n" + "\n".join(violations)
```

**Adapted AST walk for `test_no_retry_loops.py`:**
- Scan dirs: `core/`, `plugins/`, plus `models.py` and `main.py` directly.
- Exclude: `core/retry.py` (the one permitted location).
- Walk for `ast.For` nodes where `node.target` is `ast.Name` with `id == "attempt"` AND `node.iter` is `ast.Call` to `range`.
- Violation format: `f"{path.name}:{node.lineno}"`.

**pytest-asyncio pattern** (from `tests/test_orchestrator.py` / `tests/test_confirmation.py`):
```python
import pytest

@pytest.mark.asyncio
async def test_with_retry_max_attempts():
    ...
```

Config already sets `asyncio_mode = "auto"` in `pyproject.toml` so `@pytest.mark.asyncio` decorator is optional but conventional in this codebase.

---

## Shared Patterns

### DB read via run_in_executor
**Source:** `core/orchestrator.py` line 251
**Apply to:** `core/orchestrator.py` cart-retry pre-attempt idempotency check
```python
loop = asyncio.get_running_loop()
purchased, order_id = await loop.run_in_executor(None, get_item_order_state_sync, link)
```

### asyncio.timeout context manager
**Source:** `plugins/shopbot_plugin_amazon.py` lines 172-178; `plugins/shopbot_plugin_bestbuy.py` lines 116-122
**Apply to:** All 6 Amazon DOM stages, all 8 BestBuy DOM stages
```python
self._checkout_stage = "<stage-name>"
async with asyncio.timeout(step_timeout_secs):
    <await nodriver_call>
```
Set `_checkout_stage` BEFORE the context manager so it is readable even when timeout fires.

### get_db_connection() context manager
**Source:** `models.py` lines 10-30
**Apply to:** Both new models helpers (`get_item_order_state_sync`, `increment_checkout_attempts_sync`)
```python
with get_db_connection() as conn:
    row = conn.execute("SELECT ...", (link,)).fetchone()
```

### writeLog error pattern
**Source:** `core/orchestrator.py` lines 194-196
**Apply to:** Stage-timeout error path in both plugins; cart-retry abort log in orchestrator
```python
except Exception as exc:
    writeLog(f"[ClassName] auto_buy error: {exc}", "ERROR")
    return
```

---

## No Analog Found

All files have analogs. No entries in this section.

---

## Metadata

**Analog search scope:** `core/`, `plugins/`, `models.py`, `tests/`
**Files scanned:** 14 source files read, 3 grep passes
**Pattern extraction date:** 2026-06-11
