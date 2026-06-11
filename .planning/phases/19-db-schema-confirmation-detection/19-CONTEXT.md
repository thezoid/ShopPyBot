# Phase 19: DB Schema + Confirmation Detection - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Purchases are recorded only when the bot has verified a real order number from the retailer's confirmation page, never on a button click alone (BUY-03). Each checkout outcome is recorded with the captured order id and a timestamp, providing the idempotency anchor for retry (Phase 21) and a basis for future analytics (BUY-04).

Deliverables:
1. Idempotent `ALTER TABLE` migration adding `order_id TEXT`, `confirmed_at TEXT`, `checkout_attempts INTEGER DEFAULT 0` to the `items` table.
2. `core/confirmation.py` with `detect_order_confirmation(tab, platform)` returning an order id (or None) via a URL-first / DOM-backup signal with a settle delay.
3. Orchestrator wiring: after `auto_buy()` returns True, detect confirmation; enqueue `("confirmed", link, order_id, ts)` only on a non-None order id; on no detection, WARN and fall back to the legacy `purchased` write tag.

Out of scope: the retry loop and `checkout_attempts` increment (Phase 21), form-fill (Phase 20).
</domain>

<decisions>
## Implementation Decisions

### Confirmation Detection Contract
- New `core/confirmation.py` with `async def detect_order_confirmation(tab, platform) -> str | None` returning the captured order id or None. The orchestrator calls it after `auto_buy()` returns True.
- Add a plugin hook `get_active_tab()` (default returns the plugin's current `self.driver`/tab) so the orchestrator can hand the live page to the detector. `auto_buy()` signature stays `-> bool` (unchanged).
- Signal precedence: URL match first (HIGH confidence — Amazon `/gp/buy/thankyou`, BestBuy `/checkout/r/thank-you`), then a DOM order-number selector as backup. Apply a settle delay before reading.
- Settle delay is a constant (~3s) in `confirmation.py`, NOT a new `CheckoutConfig` field (the CheckoutConfig field set was fixed in Phase 18 to avoid schema churn).

### DB Schema & Write Semantics
- Add `order_id TEXT`, `confirmed_at TEXT`, `checkout_attempts INTEGER DEFAULT 0` via idempotent `ALTER TABLE` in `models.py`, mirroring the v3.0 price-column migration pattern; existing DBs migrate losslessly.
- New write-queue tag `("confirmed", link, order_id, ts)` dispatched in `_dispatch_write` to a new `update_item_confirmed_sync(link, order_id, ts)` that sets `purchased=1`, `order_id`, and `confirmed_at` together. The legacy `("purchased", link)` tag is retained for the fallback path.
- When confirmation is NOT detected: log a WARNING and fall back to the legacy `purchased` write tag (BUY-03 criterion 3 — no silent failure; the confirmation path itself introduces no double-buy risk).
- `checkout_attempts` column is added with `DEFAULT 0` now but is NOT incremented in Phase 19. The increment strategy (per-`auto_buy`-entry vs per-cart-add vs confirmed-only) is owned by Phase 21 (retry). This resolves the carry-forward research flag by deferring the increment semantics to where the retry logic lives.

### Per-Retailer Specifics
- Confirmation detection is implemented for Amazon and BestBuy now (the checkout-capable plugins per v4.0 scope). The other 5 plugins return None → legacy `purchased` fallback.
- Per-platform URL patterns and DOM order-number selectors are hardcoded in a map in `core/confirmation.py`. URL patterns are HIGH confidence; DOM selectors are MEDIUM confidence and flagged for live UAT.
- order_id capture: if the URL matches but no DOM order id is extractable, the URL match alone counts as a confirmed order and `order_id` is set to a `"CONFIRMED-<ts>"` sentinel with a WARNING logged (so `purchased` is still written on a real confirmation). If a DOM/URL order id is available, use it.
- Live verification of the DOM selectors (and the URL patterns under a real `test_mode` buy) is UAT debt — hardcode best-confidence values from research now, defer live verification per the autonomous-run policy.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `models.py` — `items` table created at lines ~39-45 (`purchased BOOLEAN NOT NULL DEFAULT 0`); idempotent `ALTER TABLE items ADD COLUMN ...` migrations at lines ~55-71 (the price columns: `target_price`, `price_drop_pct`, `price_alert_armed`, `price_last_notified`) are the exact pattern to mirror for the 3 new columns. `update_item_purchased_sync(link)` sets `purchased=1`. `price_history` table created at ~74 shows append-only table creation.
- `core/orchestrator.py` — `_try_auto_buy` (lines ~182-193) awaits `plugin.auto_buy(link)` and on success enqueues `("purchased", link)`. `_dispatch_write` (lines ~247-275) routes typed tuples; add a `("confirmed", ...)` branch here. `_check_and_buy` gates auto_buy.
- `core/plugin_base.py` — `RetailerPlugin` ABC; `self.driver` set by `setup()`. Add the `get_active_tab()` default hook here (additive, no PLUGIN_API_VERSION bump — same pattern as `get_price`).

### Established Patterns
- Idempotent SQLite migrations via `ALTER TABLE ... ADD COLUMN` guarded for re-run safety; per-column sync functions; `run_in_executor` for DB calls from async.
- Write serialization through a single `_write_queue_drain` consumer; all writes are typed tuples dispatched in `_dispatch_write`.
- Additive ABC hooks with no-op/None defaults (e.g., `get_price` returns None) so existing plugins are non-breaking.

### Integration Points
- Migration: `models.py` `initialize_db` ALTER block.
- New module: `core/confirmation.py`.
- Orchestrator: `_try_auto_buy` (call detector after success), `_dispatch_write` (new `("confirmed", ...)` tag).
- ABC: `core/plugin_base.py` `get_active_tab()`.
- Plugins: Amazon + BestBuy expose their confirmation page via `get_active_tab()`.

</code_context>

<specifics>
## Specific Ideas

- RESEARCH flag (from ROADMAP): Amazon `/gp/buy/thankyou` and BestBuy `/checkout/r/thank-you` URL patterns are HIGH confidence; backup DOM selectors (`#confirmedOrderId`, `.thank-you-order-number` or similar) are MEDIUM confidence and require live UAT on a `test_mode` buy before being trusted as the sole signal. plan-phase research should confirm the exact selector strings against current retailer markup where possible.
- The `order_id` column is the idempotency anchor Phase 21's cart-retry will read before re-attempting (BUY-05) — its presence and population on confirmed orders is the cross-phase contract.

</specifics>

<deferred>
## Deferred Ideas

- `checkout_attempts` increment strategy → Phase 21 (retry).
- Outcome analytics (success rate, time-to-checkout) on the BUY-04 records → future milestone (already in REQUIREMENTS Deferred).
- Live `test_mode` UAT of confirmation selectors → UAT debt (tracked, not blocking).

</deferred>
