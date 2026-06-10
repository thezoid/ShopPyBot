# Phase 16: Price Monitoring - Research

**Researched:** 2026-06-09
**Domain:** SQLite schema extension, plugin ABC, async poll loop, notification dispatch, CLI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Store prices as INTEGER cents (e.g. 4999 = $49.99). Avoids float rounding.
- `price_history` table: `id` PK, item reference, `price_cents INTEGER NOT NULL`, `currency TEXT NOT NULL DEFAULT 'USD'`, `scraped_at` timestamp. Append-only, no purge in v3.0.
- Migration idempotent: `PRAGMA table_info` guard + `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN`, following existing `models.py` pattern.
- `get_price()` on plugin ABC: default returns `None` (unsupported), non-breaking, no PLUGIN_API_VERSION bump.
- Alerts via the EXISTING `NotificationDispatcher` with a distinct `price_drop` notification_type. Dedup columns for price alerts are SEPARATE from `last_seen_available`/`last_notified`. Two triggers (absolute target, percentage drop), single alert per dedup window when both hold.
- Alert payload includes: current price, target price, percentage from target, formatted as `$X.XX`.
- CLI: `shoppybot items price-history <name>` — last 10 by default, `--limit N`, plain aligned table, no network.

### Claude's Discretion

- Exact column names/types and FK strategy for `price_history`, the precise dedup-column design for price alerts, how `get_price()` integrates into the poll loop (orchestrator/plugin check path), price-text parsing into cents, and CLI table formatting — guided by `models.py`, the notification dispatcher, and `core/cli/items.py` conventions.

### Deferred Ideas (OUT OF SCOPE)

- Price history retention/auto-purge (v3.1+)
- Price chart/sparkline on web UI (v3.1+)
- Historical-low/average price display (v3.1+)
- Camelcamelcamel / third-party price-history API
- Separate price-monitoring poll schedule

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PRICE-01 | Per-item absolute `target_price` in config; NULL/absent = monitoring off | ItemConfig Pydantic field (optional int); items table column |
| PRICE-02 | Append-only `price_history` table via optional `get_price()` ABC hook (default None), called each poll cycle | ABC additive method; `_check_and_buy` extension in orchestrator |
| PRICE-03 | Price-drop alerts via existing dispatcher, distinct `price_drop` notification_type, separate dedup | `NotificationDispatcher.notify()` + new dedup cols in items table |
| PRICE-04 | Payload includes current price, target price, percentage from target | `NotificationEvent.action` extended or new field; see payload design below |
| PRICE-05 | Per-item `price_drop_pct` secondary trigger (N%+ drop from last-seen price) | ItemConfig field + items table column + comparison logic |
| PRICE-06 | `shoppybot items price-history <name>` — last N recorded prices | New argparse leaf under `items_sub`; new `handle_items_price_history` in `core/cli/items.py` |

</phase_requirements>

---

## Summary

Phase 16 adds price tracking as a thin layer over the existing async orchestrator, SQLite models, and notification dispatcher. No new external dependencies are needed. Every integration point is fully understood from the codebase read.

The dispatcher fan-out (`notifications/dispatcher.py: NotificationDispatcher.notify()`) already handles arbitrary `NotificationEvent` values; the only extension needed is routing the `price_drop` action in the `SoundNotifier` fallback path (it naturally falls through to `play_notification_sound()` — no code change required there). The dedup problem is the most nuanced part: stock-alert dedup lives in `items.last_seen_available` / `items.last_notified`; price-alert dedup requires two new items columns (`price_alert_armed`, `price_last_notified`) that must never be touched by the stock-alert path.

`get_price()` is an optional ABC method (default `None`) called alongside `check_availability` inside `_check_and_buy` in `orchestrator.py`. When it returns a non-None value, the orchestrator records to `price_history` and evaluates both triggers. The entire price path is a pure additive extension to `_check_and_buy` — no existing logic changes.

**Primary recommendation:** Add `get_price()` as a concrete no-op default (returns `None`) on `RetailerPlugin`, extend `_check_and_buy` to call it and handle the result, add `price_history` table + new dedup columns via the standard idempotent migration pattern, extend `ItemConfig` with optional `target_price`/`price_drop_pct`, add `handle_items_price_history` to `core/cli/items.py`, and wire the subparser leaf in `core/cli/__init__.py`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Price scraping | Plugin (per-platform) | — | Only the plugin knows its DOM structure |
| Price recording | models.py (SQLite) | orchestrator (caller) | Single DB write path via run_in_executor |
| Trigger evaluation | orchestrator (_check_and_buy) | — | Same layer that owns stock-alert logic |
| Alert dispatch | notifications/dispatcher.py | — | Reuse existing fan-out; no new channel |
| Dedup state | models.py (items table cols) | — | Follows stock-alert dedup pattern exactly |
| CLI price-history read | core/cli/items.py | core/service.py (BotService) | MOD-02: CLI handlers only call BotService |
| Config schema | core/config_schema.py (ItemConfig) | — | Per-item optional fields, Pydantic Optional[int] |

---

## Standard Stack

### Core (all already installed — no new dependencies)

| Library | Purpose | Source |
|---------|---------|--------|
| `sqlite3` (stdlib) | `price_history` table, dedup column updates | Already in models.py [VERIFIED: codebase] |
| `pydantic` | `ItemConfig` field additions (`target_price`, `price_drop_pct`) | Already in core/config_schema.py [VERIFIED: codebase] |
| `asyncio` | Poll-loop integration, `run_in_executor` for DB writes | Already in orchestrator.py [VERIFIED: codebase] |
| `notifications/dispatcher.py` | Fan-out to all registered notifiers | Already exists [VERIFIED: codebase] |
| `argparse` | `items price-history` CLI leaf | Already used in core/cli/__init__.py [VERIFIED: codebase] |

**No new packages to install for this phase.** [VERIFIED: codebase — zero new imports required outside stdlib and already-pinned deps]

---

## Package Legitimacy Audit

No external packages are added in this phase. All code uses stdlib, pydantic (already installed), and internal project modules.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
config.yml
  └─ available.items[].target_price (Optional[int] cents)
  └─ available.items[].price_drop_pct (Optional[float])
          |
          v
  ItemConfig (core/config_schema.py)
          |
          v (seeded into items table by main.py / service startup)
  items table
    ├─ target_price INTEGER (NULL = monitoring off)
    ├─ price_drop_pct REAL   (NULL = monitoring off)
    ├─ price_alert_armed INTEGER DEFAULT 0   [new dedup col]
    └─ price_last_notified TEXT              [new dedup col]
          |
          v (each poll cycle)
  orchestrator._check_and_buy()
    ├─ check_availability()  [existing stock path, unchanged]
    └─ get_price()           [new optional ABC hook, default None]
          |
       price_cents returned
          |
          ├─> models.append_price_history(link, price_cents)
          |         |
          |   price_history table
          |   (id, item_link, price_cents, currency, scraped_at)
          |
          └─> _evaluate_price_triggers(link, price_cents, target_price, price_drop_pct)
                    |
               trigger fired?
                    |
                    v
          models.get_price_alert_state(link)   [reads price_alert_armed, price_last_notified]
               not armed -> dispatcher.notify(price_drop event)
                            models.set_price_alert_armed(link, ts)
               armed -> skip (dedup suppresses re-fire)
                    |
          [when price rises above target / no longer triggered]
          models.clear_price_alert_armed(link)

CLI path (no network):
  shoppybot items price-history <name>
    └─> BotService.get_price_history(name, limit)
          └─> models.get_price_history_sync(link, limit)
                └─> SELECT ... FROM price_history WHERE item_link=? ORDER BY scraped_at DESC LIMIT ?
```

### Recommended Project Structure (additive changes only)

```
models.py                        # price_history table, append_price_history, dedup fns
core/config_schema.py            # ItemConfig: target_price, price_drop_pct
core/plugin_base.py              # get_price() default None method
core/orchestrator.py             # _check_and_buy: get_price() call + price path
core/service.py                  # get_price_history() accessor for CLI
core/cli/items.py                # handle_items_price_history, _format_price_history_table
core/cli/__init__.py             # price-history subparser leaf under items_sub
tests/test_price_monitoring.py   # new test file for all PRICE-xx requirements
```

---

## Exact Integration Points

### 1. models.py — idempotent migration pattern [VERIFIED: codebase]

The existing pattern (lines 48-60 of models.py) is:

```python
existing = {
    row[1]
    for row in conn.execute("PRAGMA table_info(items)").fetchall()
}
if "last_seen_available" not in existing:
    conn.execute(
        "ALTER TABLE items ADD COLUMN last_seen_available INTEGER NOT NULL DEFAULT 0"
    )
if "last_notified" not in existing:
    conn.execute("ALTER TABLE items ADD COLUMN last_notified TEXT")
```

Mirror this exactly for the four new items columns and the new `price_history` table. All inside `initialize_db()`, which is called at every startup and in tests via `initialize_db(delete=True)`.

**New items table columns (added via ALTER TABLE guard):**

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `target_price` | `INTEGER` | `NULL` | Absolute cents target; NULL = off |
| `price_drop_pct` | `REAL` | `NULL` | % drop from last-seen; NULL = off |
| `price_alert_armed` | `INTEGER NOT NULL DEFAULT 0` | 0 | 1 = alert already sent this window |
| `price_last_notified` | `TEXT` | `NULL` | ISO-8601 timestamp of last price alert |

**New price_history table (CREATE TABLE IF NOT EXISTS):**

```python
conn.execute('''
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY,
        item_link TEXT NOT NULL,
        price_cents INTEGER NOT NULL,
        currency TEXT NOT NULL DEFAULT 'USD',
        scraped_at TEXT NOT NULL
    )
''')
```

`item_link` is the natural FK (matches `items.link`). No SQLite foreign key enforcement needed (existing pattern never uses FOREIGN KEY constraints). `scraped_at` stored as ISO-8601 TEXT (matches existing `last_notified` pattern).

**New models functions:**

```python
def append_price_history_sync(link: str, price_cents: int, scraped_at: str, currency: str = 'USD') -> None
def get_price_history_sync(link: str, limit: int = 10) -> list[tuple]
    # SELECT id, price_cents, currency, scraped_at FROM price_history
    # WHERE item_link=? ORDER BY scraped_at DESC LIMIT ?
def get_price_alert_state_sync(link: str) -> tuple[bool, str | None]
    # returns (price_alert_armed as bool, price_last_notified)
def set_price_alert_armed_sync(link: str, notified_at: str) -> None
    # UPDATE items SET price_alert_armed=1, price_last_notified=? WHERE link=?
def clear_price_alert_armed_sync(link: str) -> None
    # UPDATE items SET price_alert_armed=0 WHERE link=?
```

All use `get_db_connection()` context manager with parameterized SQL. Mirror existing `_sync` suffix convention. Add legacy aliases without `_sync` suffix if needed by existing callers (none yet for new functions, so skip).

### 2. core/config_schema.py — ItemConfig extension [VERIFIED: codebase]

Current `ItemConfig` (lines 46-50):

```python
class ItemConfig(BaseModel):
    name: str
    link: str
    auto_buy: bool = False
    quantity: int = 1
```

Add:

```python
from typing import Optional

class ItemConfig(BaseModel):
    name: str
    link: str
    auto_buy: bool = False
    quantity: int = 1
    target_price: Optional[int] = None    # cents; NULL = monitoring off (PRICE-01)
    price_drop_pct: Optional[float] = None  # e.g. 10.0 = alert on 10%+ drop (PRICE-05)
```

`target_price` is `Optional[int]` (cents) matching the INTEGER cents decision. `price_drop_pct` is `Optional[float]` (percentage, e.g. 10.0 for 10%). The config seeding path (wherever `ItemConfig` data flows into the `items` table at startup) must also write these columns. Currently `add_items_sync` inserts a 5-tuple `(name, link, auto_buy, quantity, purchased)`. That INSERT must be extended to include the two new columns, or a separate UPDATE can set them after insertion; the simplest approach is to add them to the INSERT tuple, guarding with `OR IGNORE` on duplicate links.

**Per-item config seeding strategy:**

The `items` table is seeded from config at startup via `add_items_sync`. Since `target_price` and `price_drop_pct` are per-item config (not discovered at runtime), they should be written to the items table so the orchestrator can read them without parsing the full config each cycle. The seeding function signature becomes:

```python
def add_items_sync(items):  # item tuple gains 2 extra fields
    # (name, link, auto_buy, quantity, purchased, target_price, price_drop_pct)
```

However, changing the tuple shape is a breaking change to existing callers (tests, `BotService.add_item`). The safe approach is: keep the existing `add_items_sync` signature intact, and add a separate `update_item_price_config_sync(link, target_price, price_drop_pct)` called after seeding. Alternatively, extend `add_items_sync` to accept an optional 7-tuple (with a positional default guard). The planner must choose one; the separate-update approach is safer and does not touch existing tests.

### 3. core/plugin_base.py — get_price() hook [VERIFIED: codebase]

Current ABC has `check_availability` and `auto_buy` as `@abstractmethod`. All other methods (`login`, `detect_captcha`, `setup`, `teardown`) have working defaults. Phase 15 added `difficulty`/`requires_proxy`/`requires_captcha` as class attributes with defaults — non-breaking.

Add `get_price()` as a **concrete default** (not abstract) returning `None`:

```python
async def get_price(self, url: str) -> int | None:
    """Return the current item price as integer cents, or None if unsupported.

    Default returns None (price monitoring unsupported for this plugin).
    PLUGIN_API_VERSION stays 2 -- additive non-abstract method (PRICE-02).
    """
    return None
```

This is non-breaking: existing plugins that do not override it return `None`, and the orchestrator treats `None` as "skip recording". No `PLUGIN_API_VERSION` bump.

**PRICE-02 clarification:** The requirement says "optional `get_price()` plugin ABC hook (default returns `None` = unsupported), called alongside the stock check each poll cycle." This means ALL plugins implement the ABC (inheriting the default), satisfying PRICE-02. At least one plugin optionally overriding it is NOT required this phase — the default-None-across-the-board state satisfies the requirement. Amazon `get_price()` may be optionally implemented as a stretch goal but is not a hard requirement for PRICE-02 closure.

### 4. core/orchestrator.py — poll cycle extension [VERIFIED: codebase]

The integration point is `_check_and_buy` (lines 102-126). The price path must be added after the stock check block but within the same try/except, using `run_in_executor` for all DB writes.

The current `_check_and_buy` flow:
1. `available = await plugin.check_availability(link)` — may raise, caught by outer try/except
2. Read `was_available, _` via `run_in_executor(get_item_notification_state_sync, link)`
3. If available and not was_available: dispatch "detected" event, enqueue `set_available`
4. If not available and was_available: enqueue `clear_available`, return
5. If not available: return
6. If auto_buy: call `_try_auto_buy`

**Price path insertion point:** After step 2 (after we know `available`), call `get_price()` unconditionally. Record if non-None. Evaluate triggers. This happens regardless of availability state.

However, `get_price()` is only meaningful when the page was actually loaded (i.e., when `check_availability` did not raise). It should be called inside the try block after `check_availability` succeeds:

```python
async def _check_and_buy(plugin, name, link, auto_buy, write_queue, dispatcher=None):
    loop = asyncio.get_running_loop()
    try:
        available = await plugin.check_availability(link)
    except Exception as exc:
        writeLog(f"[{plugin.__class__.__name__}] check error: {exc}", "ERROR")
        return

    # Price monitoring path (PRICE-02): call get_price alongside stock check
    price_cents = None
    try:
        price_cents = await plugin.get_price(link)
    except Exception as exc:
        writeLog(f"[{plugin.__class__.__name__}] get_price error: {exc.__class__.__name__}", "ERROR")

    if price_cents is not None:
        now_iso = datetime.now(timezone.utc).isoformat()
        await loop.run_in_executor(None, append_price_history_sync, link, price_cents, now_iso)
        await _evaluate_price_triggers(plugin, name, link, price_cents, write_queue, dispatcher, loop)

    # ... existing stock-alert path unchanged below ...
```

`_evaluate_price_triggers` is a new helper in `orchestrator.py` (under 30 lines):

```python
async def _evaluate_price_triggers(plugin, name, link, price_cents, write_queue, dispatcher, loop):
    """Check absolute target and percentage-drop triggers; dispatch price_drop if armed."""
    # Read per-item config from items table
    item_row = await loop.run_in_executor(None, get_item_price_config_sync, link)
    if item_row is None:
        return
    target_price, price_drop_pct = item_row  # may be None
    
    triggered = _check_price_triggers(price_cents, target_price, price_drop_pct, link, loop)
    if not triggered:
        # Clear armed state if price recovered above target
        await loop.run_in_executor(None, clear_price_alert_armed_sync, link)
        return
    
    armed, _ = await loop.run_in_executor(None, get_price_alert_state_sync, link)
    if armed:
        return  # dedup: already notified this window
    
    if dispatcher is not None:
        event = _build_price_drop_event(name, link, plugin.__class__.__name__, price_cents, target_price)
        await dispatcher.notify(event)
    
    now_iso = datetime.now(timezone.utc).isoformat()
    await loop.run_in_executor(None, set_price_alert_armed_sync, link, now_iso)
```

Note: this is 23 lines, within the 30-line function limit. The trigger math helper can be a pure function (no async, no DB):

```python
def _check_price_triggers(price_cents: int, target_price: int | None, price_drop_pct: float | None, ...) -> bool:
    """Return True if absolute target OR percentage-drop trigger fires."""
    if target_price is not None and price_cents <= target_price:
        return True
    if price_drop_pct is not None:
        # Compare against last recorded price (read from price_history, or skip if no history)
        # ... see pitfall below on last-seen price source
        pass
    return False
```

**PRICE-05 last-seen price source:** The percentage-drop trigger compares against the last-seen price. This must come from `price_history` (the most recent prior row), not from a separate column, to keep the schema minimal. Add `get_last_price_sync(link) -> int | None` to models.py:

```python
def get_last_price_sync(link: str) -> int | None:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT price_cents FROM price_history WHERE item_link=? ORDER BY scraped_at DESC LIMIT 1",
            (link,)
        ).fetchone()
    return row[0] if row else None
```

The trigger then reads the PREVIOUS price (before appending the current one) to compute the drop. Call order in orchestrator: read last price BEFORE appending, then append, then evaluate.

### 5. NotificationEvent — price_drop action [VERIFIED: codebase]

`NotificationEvent` (notifications/base.py) is a dataclass with `action: str`. The dispatcher routes by action string. `SoundNotifier` dispatches: `"detected"` and `"purchased"` are handled; anything else falls through to `play_notification_sound()`. So `action="price_drop"` automatically plays the notification sound — no changes to any notifier.

**However**, PRICE-04 requires the payload to include current price, target price, and percentage from target. `NotificationEvent` has no fields for these. Two options:

Option A (recommended): Add optional extra fields to `NotificationEvent` for backward compat:

```python
@dataclass
class NotificationEvent:
    item_name: str
    item_url: str
    platform: str
    timestamp: datetime
    action: str
    # PRICE-04: optional price context; None for non-price events
    price_cents: int | None = None
    target_price_cents: int | None = None
    pct_from_target: float | None = None
```

All existing notifiers only read `item_name`, `item_url`, `platform`, `timestamp`, `action` — the new fields are additive and non-breaking.

Option B: Encode the price context in a rich `action` string (e.g., `"price_drop:4999:5999:16.7"`) and have the price-drop notifier path parse it. This is fragile and couples payload format to string parsing.

**Recommendation: Option A.** The planner should add three `Optional` dataclass fields to `NotificationEvent` with defaults of `None`. All existing tests pass unchanged because Python dataclasses with defaults are backward-compatible.

`DiscordNotifier`, `EmailNotifier`, and `SmsNotifier` will need a branch for `action == "price_drop"` to include price fields in their formatted output. For the scope of Phase 16, the minimum viable path is: include the price data in the event, and update notifier `_build_*_payload` functions to format price fields when `price_cents is not None`. This is straightforward.

**Build helper in orchestrator:**

```python
def _build_price_drop_event(name, link, plugin_name, price_cents, target_price):
    pct = None
    if target_price and target_price > 0:
        pct = round((target_price - price_cents) / target_price * 100, 1)
    return NotificationEvent(
        item_name=name,
        item_url=link,
        platform=plugin_name,
        timestamp=datetime.now(timezone.utc),
        action="price_drop",
        price_cents=price_cents,
        target_price_cents=target_price,
        pct_from_target=pct,
    )
```

### 6. core/cli/items.py + core/cli/__init__.py — price-history CLI [VERIFIED: codebase]

**Pattern to mirror:** `core/cli/plugins.py` (`handle_plugins_list`) reads from `BotService` and formats a table. `core/cli/items.py` already has `_format_items_table` as a model for the formatting helper.

**BotService extension** (core/service.py): add one read-only accessor:

```python
def get_price_history(self, name: str, limit: int = 10) -> list[tuple]:
    """Return last N price_history rows for the named item (no bot start required)."""
    rows = get_items_sync()
    match = next((r for r in rows if r[0] == name), None)
    if match is None:
        return []
    link = match[1]
    return get_price_history_sync(link, limit)
```

**Handler in core/cli/items.py:**

```python
def _format_price_history_table(name: str, rows: list) -> str:
    """Return aligned table of (price_cents, currency, scraped_at) rows.

    Formats price_cents as $X.XX for display. Returns no-history message when empty.
    """
    if not rows:
        return f"No price history recorded for: {name}"
    headers = ("Price", "Currency", "Recorded At")
    data = [
        (f"${r[0] / 100:.2f}", r[1], r[2])
        for r in rows
    ]
    widths = [
        max(len(h), max(len(row[i]) for row in data))
        for i, h in enumerate(headers)
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers), "  ".join("-" * w for w in widths)]
    for row in data:
        lines.append(fmt.format(*row))
    return "\n".join(lines)


def handle_items_price_history(args, svc: BotService) -> int:
    """Print price history for the named item."""
    rows = svc.get_price_history(args.name, args.limit)
    print(_format_price_history_table(args.name, rows))
    return 0
```

**Subparser leaf in core/cli/__init__.py:**

The `items_sub` subparser group already has `list`, `add`, `remove`. Add after `remove_p`:

```python
ph_p = items_sub.add_parser("price-history", help="Show recorded price history for an item.")
ph_p.add_argument("name", help="Item name.")
ph_p.add_argument(
    "--limit",
    type=int,
    default=10,
    help="Number of recent prices to show (default: 10).",
)
ph_p.set_defaults(func=handle_items_price_history)
```

Import `handle_items_price_history` at the top of `core/cli/__init__.py` (same import line as the other `handle_items_*` functions).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fan-out to all notification channels | Custom routing | `NotificationDispatcher.notify()` (already exists) | Isolation, error handling, ordering all handled |
| DB write serialization | Thread locks | `write_queue` + `run_in_executor` (existing ASYNC-05 pattern) | TaskGroup concurrency requires the queue |
| Idempotent migration | Custom migration runner | `PRAGMA table_info` + `CREATE TABLE IF NOT EXISTS` | Already in models.py; proven pattern |
| Price string parsing | Hand-rolled regex | `re.sub(r'[^\d.]', '', price_text)` then `round(float(...) * 100)` | Simple enough; don't add a library |
| Aligned CLI table | Rich/tabulate | `_format_items_table` clone in `core/cli/items.py` | Already established pattern; no new dep |

---

## Common Pitfalls

### Pitfall 1: Reusing stock-alert dedup columns for price alerts

**What goes wrong:** Writing `last_notified` for a price alert clears the stock-alert cooldown, causing a double-fire or missed stock notification.
**Why it happens:** Both alerts share the same item row; `last_notified` looks like the right place.
**How to avoid:** Use `price_alert_armed` and `price_last_notified` exclusively for price alerts. Stock columns (`last_seen_available`, `last_notified`) must never be touched by the price path.
**Warning sign:** A test that inserts a stock alert and then fires a price alert and checks stock dedup state.

### Pitfall 2: Calling get_price() when check_availability raised

**What goes wrong:** `get_price()` is called even when the page load failed (browser exception in check_availability), returning garbage or raising.
**Why it happens:** Inserting the price call unconditionally after the outer try.
**How to avoid:** Only call `get_price()` inside a separate try/except AFTER `check_availability` has returned without raising. If `check_availability` raises, `return` before reaching the price path (current code already does this).

### Pitfall 3: Percentage-drop trigger uses the price just recorded (same cycle)

**What goes wrong:** Reading `price_history` AFTER appending the current price gives the same value as the current price (no drop detected).
**Why it happens:** Query order: append then read last.
**How to avoid:** Read the previous last price BEFORE appending the current one. The orchestrator must call `get_last_price_sync(link)` before `append_price_history_sync(link, ...)`.

### Pitfall 4: Integer overflow / cents arithmetic with NULL

**What goes wrong:** `price_cents <= target_price` when `target_price` is `None` raises `TypeError: '<=' not supported between instances of 'int' and 'NoneType'`.
**How to avoid:** Guard both triggers with `if target_price is not None` and `if price_drop_pct is not None` before any comparison.

### Pitfall 5: Arming price_alert but never clearing it (price stays low forever)

**What goes wrong:** Once `price_alert_armed=1`, the user never gets a second alert even after the price recovers and drops again.
**Why it happens:** `clear_price_alert_armed` is only called on a disarm condition that never triggers.
**How to avoid:** In `_evaluate_price_triggers`, when the trigger does NOT fire (price is above target/threshold), call `clear_price_alert_armed_sync(link)`. This resets the window so the next drop fires again.

### Pitfall 6: NotificationEvent dataclass field ordering breaks existing construction

**What goes wrong:** Adding required (non-default) fields to `NotificationEvent` breaks every existing `NotificationEvent(...)` call throughout the codebase (orchestrator, tests).
**Why it happens:** Python dataclasses require fields without defaults to come before fields with defaults.
**How to avoid:** All three new fields (`price_cents`, `target_price_cents`, `pct_from_target`) must have `= None` defaults and be appended after the existing five fields.

### Pitfall 7: items table seed doesn't propagate target_price from config

**What goes wrong:** `target_price` and `price_drop_pct` are in `ItemConfig` but never written to the `items` table, so the orchestrator reads `NULL` from the DB and never evaluates triggers.
**Why it happens:** `add_items_sync` inserts only the original 5-tuple fields; the new config fields are silently dropped.
**How to avoid:** After `add_items_sync` seeds items, call `update_item_price_config_sync(link, target_price, price_drop_pct)` for every item in `config.available.items`. This can live in `BotService.__init__` or in the startup path of `main.py`. The UPDATE is idempotent (NULL overwrites NULL if config value is None).

### Pitfall 8: price-history CLI resolves name case-sensitively

**What goes wrong:** User types `shoppybot items price-history "My Item"` but the DB stored it as `"my item"`, returning "No price history".
**How to avoid:** Use `WHERE LOWER(name)=LOWER(?)` in the lookup, or document that names are case-sensitive and match config exactly. The simpler approach (and consistent with existing `items list`) is case-sensitive exact match with a clear error message.

---

## Code Examples

### Idempotent migration in initialize_db() [VERIFIED: models.py lines 48-60]

```python
# In initialize_db(), after CREATE TABLE IF NOT EXISTS items:
existing_items = {
    row[1]
    for row in conn.execute("PRAGMA table_info(items)").fetchall()
}
if "target_price" not in existing_items:
    conn.execute("ALTER TABLE items ADD COLUMN target_price INTEGER")
if "price_drop_pct" not in existing_items:
    conn.execute("ALTER TABLE items ADD COLUMN price_drop_pct REAL")
if "price_alert_armed" not in existing_items:
    conn.execute(
        "ALTER TABLE items ADD COLUMN price_alert_armed INTEGER NOT NULL DEFAULT 0"
    )
if "price_last_notified" not in existing_items:
    conn.execute("ALTER TABLE items ADD COLUMN price_last_notified TEXT")

# CREATE TABLE IF NOT EXISTS for price_history (no PRAGMA needed -- new table)
conn.execute('''
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY,
        item_link TEXT NOT NULL,
        price_cents INTEGER NOT NULL,
        currency TEXT NOT NULL DEFAULT 'USD',
        scraped_at TEXT NOT NULL
    )
''')
```

### Parameterized DB writes [VERIFIED: models.py pattern]

```python
def append_price_history_sync(link: str, price_cents: int, scraped_at: str, currency: str = 'USD') -> None:
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO price_history (item_link, price_cents, currency, scraped_at) VALUES (?, ?, ?, ?)",
            (link, price_cents, currency, scraped_at),
        )
```

### Integer cents formatting for display

```python
def _cents_to_display(cents: int) -> str:
    return f"${cents / 100:.2f}"

# 4999 -> "$49.99"
# 100  -> "$1.00"
```

### Percentage-from-target calculation (integer arithmetic)

```python
def _pct_from_target(price_cents: int, target_cents: int) -> float:
    """Return positive float: how far price is below target as a percentage.

    Returns 0.0 when price >= target (no drop from target).
    """
    if target_cents <= 0:
        return 0.0
    return max(0.0, round((target_cents - price_cents) / target_cents * 100, 1))

# _pct_from_target(4500, 5000) -> 10.0  (10% below target)
# _pct_from_target(5500, 5000) -> 0.0   (price above target)
```

### Percentage-drop from last-seen price

```python
def _pct_drop_from_last(current_cents: int, last_cents: int) -> float:
    """Return percentage drop from last_cents to current_cents.

    Positive means price decreased. Returns 0.0 if current >= last.
    """
    if last_cents <= 0:
        return 0.0
    return max(0.0, round((last_cents - current_cents) / last_cents * 100, 1))

# _pct_drop_from_last(4500, 5000) -> 10.0  (10% cheaper than last seen)
# _pct_drop_from_last(5500, 5000) -> 0.0   (price went up)
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| N/A (new feature) | Append-only price_history per locked decision | No purge this phase; v3.1+ adds retention |
| N/A | Integer cents throughout | No float rounding edge cases |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `get_price()` returning `None` across all plugins fully satisfies PRICE-02 (no plugin must implement it this phase) | Integration Points §3 | Planner might schedule Amazon price scraping as a required task; confirm with user if unclear |
| A2 | `NotificationEvent` dataclass fields are added as Optional with defaults (Option A) | Integration Points §5 | If a field-ordering issue exists in the dataclass serialization, all existing event tests break |
| A3 | `price_alert_armed` disarms when price recovers (call `clear_price_alert_armed` on non-trigger) | Integration Points §4 | If not cleared, users never get a second alert after price recovers and drops again |
| A4 | Name-based item lookup in `get_price_history` uses exact case-sensitive match | Integration Points §6 | Users whose config name case doesn't match stored row get empty results |

---

## Open Questions (RESOLVED)

> RESOLVED 2026-06-09: Q1 → implement Amazon real get_price() (user decision, CONTEXT.md). Q2 → separate `update_item_price_config_sync` seed. Q3 → single `price_drop` alert per dedup window. All three are locked in 16-CONTEXT.md and implemented by the plans.

1. **Does PRICE-02 require at least one plugin to implement get_price() this phase?**
   - What we know: The requirement says "optional ABC hook (default returns None = unsupported)." No concrete plugin is named.
   - What's unclear: Whether "called alongside the stock check each poll cycle" implies it must return a real price for at least one platform to be considered done.
   - Recommendation: Default-None across all plugins satisfies the letter of PRICE-02. If the user wants end-to-end price recording for Amazon as part of this phase (as a stretch goal), plan it as an optional task in the last plan wave.

2. **Should target_price / price_drop_pct in config seed the items table, or be read from config on every cycle?**
   - What we know: Existing per-item data (auto_buy, quantity) lives in the items table and is seeded from config at startup.
   - Recommendation: Seed into items table (consistent with existing pattern). This allows the orchestrator to read from DB without parsing the full config each cycle. Add `update_item_price_config_sync` called from the startup seed path.

3. **When both absolute-target AND percentage-drop trigger fire in the same cycle, should the payload reflect both conditions?**
   - What we know: CONTEXT.md says "A single price_drop alert per dedup window (don't double-fire when both conditions hold)."
   - Recommendation: Fire one alert. Payload includes current price and target price (from absolute trigger). If only percentage-drop triggered, `target_price_cents` in the event can be `None`. The `pct_from_target` field reflects the percentage relative to `target_price` when available, otherwise percentage drop from last-seen.

---

## Environment Availability

Step 2.6: SKIPPED (no external tools or services required — all changes are to Python source files and SQLite schema; SQLite is stdlib).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio |
| Config | `pyproject.toml [tool.pytest.ini_options]` — `asyncio_mode = "auto"` |
| Quick run command | `pytest tests/test_price_monitoring.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PRICE-01 | `target_price=None` disables monitoring; `target_price=4999` enables | unit | `pytest tests/test_price_monitoring.py::test_target_price_null_disables -x` | No — Wave 0 |
| PRICE-02 | `initialize_db()` creates `price_history` table; `append_price_history_sync` inserts rows | unit | `pytest tests/test_price_monitoring.py::test_price_history_table_created -x` | No — Wave 0 |
| PRICE-02 | `initialize_db()` called twice (migration idempotency) does not raise or duplicate columns | unit | `pytest tests/test_price_monitoring.py::test_migration_idempotent -x` | No — Wave 0 |
| PRICE-02 | `get_price()` default returns None; non-None triggers `append_price_history_sync` in orchestrator | unit | `pytest tests/test_price_monitoring.py::test_get_price_default_none -x` | No — Wave 0 |
| PRICE-03 | `price_alert_armed` starts 0; fires dispatcher on first trigger; does not re-fire while armed | unit | `pytest tests/test_price_monitoring.py::test_price_alert_dedup -x` | No — Wave 0 |
| PRICE-03 | Price dedup columns (`price_alert_armed`, `price_last_notified`) are independent of stock dedup (`last_seen_available`, `last_notified`) | unit | `pytest tests/test_price_monitoring.py::test_price_dedup_independent_from_stock_dedup -x` | No — Wave 0 |
| PRICE-04 | Alert event has `price_cents`, `target_price_cents`, `pct_from_target` populated correctly | unit | `pytest tests/test_price_monitoring.py::test_price_drop_event_payload -x` | No — Wave 0 |
| PRICE-04 | `_cents_to_display(4999)` returns `"$49.99"` | unit | `pytest tests/test_price_monitoring.py::test_cents_to_display -x` | No — Wave 0 |
| PRICE-05 | `_pct_drop_from_last(4500, 5000)` returns `10.0`; below `price_drop_pct=10.0` fires trigger | unit | `pytest tests/test_price_monitoring.py::test_pct_drop_trigger -x` | No — Wave 0 |
| PRICE-05 | `_pct_drop_from_last(5500, 5000)` returns `0.0` (no drop — price went up) | unit | `pytest tests/test_price_monitoring.py::test_pct_drop_no_trigger_on_increase -x` | No — Wave 0 |
| PRICE-06 | `main(["items", "price-history", "Widget"])` prints table with `$X.XX` and recorded-at column | unit | `pytest tests/test_price_monitoring.py::test_cli_price_history -x` | No — Wave 0 |
| PRICE-06 | `main(["items", "price-history", "Unknown"])` prints no-history message, exits 0 | unit | `pytest tests/test_price_monitoring.py::test_cli_price_history_no_item -x` | No — Wave 0 |
| PRICE-06 | `--limit 3` returns at most 3 rows | unit | `pytest tests/test_price_monitoring.py::test_cli_price_history_limit -x` | No — Wave 0 |

### Key Test Patterns (from existing test infrastructure)

**Migration idempotency (mirror test_migration.py pattern):**
```python
def test_migration_idempotent(tmp_data_dir):
    from models import initialize_db
    initialize_db(delete=True)   # fresh DB
    initialize_db()              # second call must not raise or duplicate columns
    # Verify via PRAGMA table_info that each column appears exactly once
    import sqlite3, models
    conn = sqlite3.connect(models.DB_PATH)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()]
    conn.close()
    assert cols.count("price_alert_armed") == 1
    assert cols.count("target_price") == 1
```

**Dispatcher capture (mirror test_notifications.py pattern):**
```python
async def test_price_alert_dispatched(fake_notifier, tmp_data_dir):
    from notifications.dispatcher import NotificationDispatcher
    notifier = fake_notifier()
    dispatcher = NotificationDispatcher([notifier])
    # Trigger via _evaluate_price_triggers with mocked DB state
    # Assert notifier.events[0].action == "price_drop"
    # Assert notifier.events[0].price_cents == expected
```

**Integer cents threshold math:**
```python
def test_cents_to_display():
    assert _cents_to_display(4999) == "$49.99"
    assert _cents_to_display(100) == "$1.00"
    assert _cents_to_display(0) == "$0.00"

def test_pct_from_target():
    assert _pct_from_target(4500, 5000) == 10.0
    assert _pct_from_target(5000, 5000) == 0.0   # at target, not below
    assert _pct_from_target(5500, 5000) == 0.0   # above target

def test_pct_drop_from_last():
    assert _pct_drop_from_last(4500, 5000) == 10.0
    assert _pct_drop_from_last(5000, 5000) == 0.0
    assert _pct_drop_from_last(5500, 5000) == 0.0
```

**CLI stdout (mirror test_cli_items.py pattern):**
```python
def test_cli_price_history(capsys, tmp_data_dir):
    from core.service import main
    from unittest.mock import MagicMock, patch

    mock_svc = MagicMock()
    mock_svc.get_price_history.return_value = [
        (4999, "USD", "2026-06-09T12:00:00+00:00"),
    ]
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["items", "price-history", "Widget"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "$49.99" in out
    assert "USD" in out
```

### Sampling Rate
- Per task commit: `pytest tests/test_price_monitoring.py -x`
- Per wave merge: `pytest tests/ -x`
- Phase gate: full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_price_monitoring.py` — all PRICE-xx tests (new file)
- [ ] No new conftest fixtures needed — `tmp_data_dir`, `fake_notifier`, `notification_event` all exist in `tests/conftest.py`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | `price_cents` must be positive integer; `price_drop_pct` must be non-negative float |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Price string injection (malformed DOM text) | Tampering | Strip non-numeric chars before float conversion; validate range before storing |
| SQL injection via item_link | Tampering | Parameterized queries (all models.py functions use `?` placeholders) — already enforced |
| Negative price_cents stored | Tampering | Guard: `if price_cents is not None and price_cents > 0` before recording |

---

## Sources

### Primary (HIGH confidence)
- `E:\repos\ShopPyBot\models.py` — exact migration pattern, dedup column names, get_db_connection, initialize_db [VERIFIED: codebase]
- `E:\repos\ShopPyBot\core\config_schema.py` — ItemConfig fields, AppConfig structure [VERIFIED: codebase]
- `E:\repos\ShopPyBot\core\plugin_base.py` — RetailerPlugin ABC, existing non-abstract defaults, PLUGIN_API_VERSION [VERIFIED: codebase]
- `E:\repos\ShopPyBot\core\orchestrator.py` — _check_and_buy, run_in_executor pattern, write_queue, dispatcher.notify call [VERIFIED: codebase]
- `E:\repos\ShopPyBot\notifications\base.py` — NotificationEvent dataclass, Notifier ABC [VERIFIED: codebase]
- `E:\repos\ShopPyBot\notifications\dispatcher.py` — NotificationDispatcher.notify, fan-out isolation [VERIFIED: codebase]
- `E:\repos\ShopPyBot\notifications\sound_notifier.py` — action dispatch; price_drop falls to play_notification_sound [VERIFIED: codebase]
- `E:\repos\ShopPyBot\core\cli\items.py` — _format_items_table pattern, handle_items_* dispatch contract [VERIFIED: codebase]
- `E:\repos\ShopPyBot\core\cli\__init__.py` — items_sub subparser structure, _require_subcommand, dispatch to func [VERIFIED: codebase]
- `E:\repos\ShopPyBot\core\cli\plugins.py` — mirror model for price-history handler [VERIFIED: codebase]
- `E:\repos\ShopPyBot\core\service.py` — BotService accessor pattern (list_items, list_plugins) [VERIFIED: codebase]
- `E:\repos\ShopPyBot\tests\conftest.py` — tmp_data_dir, fake_notifier, notification_event fixtures [VERIFIED: codebase]
- `E:\repos\ShopPyBot\tests\test_notifications.py` — dispatcher test patterns to mirror [VERIFIED: codebase]
- `E:\repos\ShopPyBot\tests\test_cli_items.py` — CLI test patterns (capsys, patch BotService, SystemExit) [VERIFIED: codebase]
- `E:\repos\ShopPyBot\pyproject.toml` — asyncio_mode=auto, no external deps [VERIFIED: codebase]

---

## Metadata

**Confidence breakdown:**
- Integration points (models, dispatcher, orchestrator, CLI): HIGH — read directly from source files
- Schema design (column names, types): HIGH — mirrors existing proven pattern exactly
- Test patterns: HIGH — mirrors existing test files
- PRICE-02 get_price() scope (no plugin required): MEDIUM — deduced from requirement text; marked as assumption A1

**Research date:** 2026-06-09
**Valid until:** 90 days (stable codebase, no external deps)
