# Phase 16: Price Monitoring - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Add per-item price tracking, price-drop alerts (absolute target and percentage), and CLI price-history inspection. Bot records scraped prices each poll cycle in an append-only `price_history` SQLite table via an optional `get_price()` plugin ABC hook (default returns None = unsupported). Price-drop alerts fan out through the EXISTING notification dispatcher using a distinct `price_drop` notification_type with its own dedup columns. Users configure `target_price` and `price_drop_pct` per item; NULL/absent = monitoring off for that item. `shoppybot items price-history <name>` shows recent prices.

</domain>

<decisions>
## Implementation Decisions

### Money representation
- Store prices as **INTEGER cents** (e.g. 4999 = $49.99) in `price_history` and in the per-item config comparison logic. Avoids float rounding in target/percentage comparisons. `get_price()` parses scraped text to integer cents; CLI and alert payloads format back to `$X.XX` for display.
- Percentage-from-target and percentage-drop computations operate on integer cents.

### price_history schema (append-only)
- New `price_history` table: at minimum `id` (PK), item reference (item link/url FK or the existing item key), `price_cents INTEGER NOT NULL`, `currency TEXT NOT NULL DEFAULT 'USD'`, `scraped_at` timestamp. Append-only — NO update/purge in v3.0 (retention/auto-purge is explicitly deferred to v3.1+).
- Migration is **idempotent** on existing installs, following the existing `models.py` pattern (`PRAGMA table_info` guard + `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN`). Existing DBs upgrade cleanly with no data loss.

### Currency
- Store a `currency TEXT NOT NULL DEFAULT 'USD'` column on `price_history` so history is unambiguous and future-proof. Comparisons assume same-currency per item (USD default).

### get_price() ABC hook
- Optional method on the plugin ABC (`core/plugin_base.py`), DEFAULT returns `None` (unsupported) — non-breaking, no plugin ABC version bump that breaks loading. Called alongside the stock check each poll cycle; `None` → record nothing, no alert.

### Alerts (fan-out via existing dispatcher)
- Use the EXISTING notification dispatcher with a distinct `price_drop` notification_type. Dedup columns for price alerts are SEPARATE from the stock-alert dedup columns (`last_seen_available`/`last_notified`) — do not reuse them.
- Two triggers, both per-item, either may fire: (a) absolute `target_price` reached/below; (b) `price_drop_pct` — an N%+ drop from the last-seen price (per PRICE-05). A single price_drop alert per dedup window (don't double-fire when both conditions hold).
- Alert payload includes: current price, target price, and percentage from target (PRICE-04). Format money as `$X.XX`.

### CLI: `shoppybot items price-history <name>`
- New leaf under the existing `items` subparser group. Shows the last **10** recorded prices by default; accept `--limit N` to override. Plain aligned table (reuse Phase 15 CLI table style). No network call (reads `price_history`).

### Claude's Discretion
- Exact column names/types and FK strategy for `price_history`, the precise dedup-column design for price alerts, how `get_price()` integrates into the poll loop (orchestrator/plugin check path), price-text parsing into cents, and CLI table formatting — all at Claude's discretion, guided by `models.py`, the notification dispatcher, and `core/cli/items.py` conventions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `models.py` — WAL SQLite layer; `get_db_connection()` context manager; `initialize_db()` with the idempotent migration pattern (`PRAGMA table_info(items)` guard + `ALTER TABLE ADD COLUMN`). Mirror this for `price_history` creation + any item-config columns.
- Existing notification dispatcher (NOTIF-02 fan-out; item dedup via `last_seen_available`/`last_notified` in models.py `get_item_notification_state_sync`/`set_item_available_sync`) — extend with a `price_drop` type + separate dedup columns.
- `core/cli/items.py` + `core/cli/__init__.py` — the `items` subparser group to add the `price-history` leaf to (Phase 15 added `core/cli/plugins.py` as another mirror).
- `core/plugin_base.py` — ABC for the optional `get_price()` hook (Phase 15 added additive attrs without breaking loading; same approach).
- `core/orchestrator.py` / plugin `check_availability` poll path — where `get_price()` is called alongside the stock check each cycle.

### Established Patterns
- Idempotent migrations; per-item config in the `items` table; pytest under `tests/`; integer-based math for correctness. nodriver async plugins.
- Phases 13–15 added ABC members/attrs with no breaking change and no new dependency.

### Integration Points
- `get_price()` called in the poll cycle → record to `price_history` → evaluate triggers → dispatch `price_drop` via the existing dispatcher. Config `target_price` + `price_drop_pct` read per item (config schema + items table). CLI `items price-history` reads `price_history`.

</code_context>

<specifics>
## Specific Ideas

- Append-only history; NO purge/retention in v3.0 (deferred to v3.1+).
- Idempotent migration on existing installs (success criterion 2).
- price_drop dedup columns SEPARATE from stock dedup (success criterion 3).
- Payload includes current, target, and percentage-from-target (success criterion 4).
- NULL/absent target_price AND price_drop_pct = monitoring off for that item (success criterion 1).

</specifics>

<deferred>
## Deferred Ideas

- Price history retention / auto-purge — deferred to v3.1+ (Out of Scope v3.0).
- Price chart / sparkline on the web UI — v3.1+.
- Historical-low / average price display — v3.1+.
- Camelcamelcamel / third-party price-history API — Out of Scope.
- Separate price-monitoring poll schedule — share the existing stock-check poll cycle.
- Broad v3.0 test hardening — Phase 17.

</deferred>
