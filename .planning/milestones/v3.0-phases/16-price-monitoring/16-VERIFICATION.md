---
phase: 16-price-monitoring
verified: 2026-06-09T00:00:00Z
status: human_needed
score: 14/14
overrides_applied: 0
human_verification:
  - test: "Trigger a live Amazon price scrape"
    expected: "AmazonPlugin.get_price() loads a real Amazon product URL, selects a price element via one of the three CSS selectors, returns a non-None integer cents value, and that value is inserted into the price_history table"
    why_human: "No live browser in this environment; nodriver requires a running Chrome subprocess"
  - test: "Trigger a live price-drop fan-out alert"
    expected: "Set target_price in config below current Amazon price; run one poll cycle; confirm a price_drop NotificationEvent is dispatched to every configured channel (Discord/Email/SMS) and the price_alert_armed column is set to 1 in the items table"
    why_human: "Requires a real Amazon item, configured notifier channels, and a running bot process"
---

# Phase 16: Price Monitoring -- Verification Report

**Phase Goal:** Users can track per-item prices, receive fan-out alerts when prices drop to target or by a configured percentage, and inspect price history from the CLI.
**Verified:** 2026-06-09
**Status:** human_needed (all automated checks pass; 2 live-scrape behaviors require human testing)
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | initialize_db() creates an append-only price_history table and adds four new items columns without data loss on existing DBs | VERIFIED | `models.py` lines 62-81: idempotent PRAGMA-guard ALTERs for `target_price`, `price_drop_pct`, `price_alert_armed`, `price_last_notified`; `CREATE TABLE IF NOT EXISTS price_history`. Tests `test_price_history_table_created`, `test_items_price_columns_added`, `test_migration_idempotent` all pass. |
| 2  | Running initialize_db() twice does not raise or duplicate any column | VERIFIED | Migration reuses the existing `existing` set guard; `test_migration_idempotent` asserts each new column count == 1 after two calls. Suite: 529 passed. |
| 3  | A per-item target_price (cents) and price_drop_pct can be set in config and seeded into items table; NULL/absent = monitoring off | VERIFIED | `ItemConfig` in `core/config_schema.py` lines 52-53 declares both optional fields. `main.py` lines 42-43 iterate config items and call `update_item_price_config_sync`. `test_seed_writes_price_config` passes. |
| 4  | The last recorded price for an item can be read before the current price is appended | VERIFIED | `_check_and_buy` in `core/orchestrator.py` lines 215-217: `get_last_price_sync` called before `append_price_history_sync` inside the same try block. `test_last_price_read_before_append` uses spy ordering assertion to confirm call order. Passes. |
| 5  | NotificationEvent carries optional price_cents, target_price_cents, pct_from_target fields without breaking any existing event construction | VERIFIED | `notifications/base.py` lines 47-49: three fields with `= None` defaults appended after `action`. `test_event_optional_price_fields_default_none` passes (existing positional and keyword constructions tested). Full suite no regression. |
| 6  | Every plugin has a get_price() hook that defaults to None (non-breaking; PLUGIN_API_VERSION stays 2) | VERIFIED | `core/plugin_base.py` line 71: `async def get_price(self, url: str) -> int \| None: return None` (concrete, not abstract). `PLUGIN_API_VERSION = 2` confirmed on line 6. `test_get_price_default_none` passes. |
| 7  | The Amazon plugin parses a live DOM price string into integer cents, returning None on malformed/missing price (no crash) | VERIFIED (automated parser; live DOM is human-check) | `_parse_price_to_cents` in `plugins/shopbot_plugin_amazon.py` lines 34-56: strips non-numeric chars, rejects `-`, empty, non-finite, <= 0. `AmazonPlugin.get_price` lines 223-244 wraps body in try/except returning None on any exception. `test_parse_price_to_cents_fixtures` and `test_amazon_get_price_parses_dom` pass. T-04 regression: `$0.00` and negative strings return None. Live DOM scrape flagged for human verification. |
| 8  | Discord/Email/SMS notifiers include current price, target price, and percentage when action == price_drop | VERIFIED | `notifications/discord_notifier.py` lines 36-52: conditional `price_drop` block adds three embed fields. `notifications/email_notifier.py` lines 35-39: appends price lines to body. `notifications/sms_notifier.py` lines 36-41: appends price/target/pct to base string. `test_discord_price_drop_payload` and `test_email_sms_price_drop_format` pass. |
| 9  | Each poll cycle the orchestrator calls get_price() after a successful check_availability and records non-None prices to price_history | VERIFIED | `_check_and_buy` lines 206-220: separate try/except calls `plugin.get_price(link)` only after `check_availability` succeeds (early return at line 203 on exception). Guard `price_cents is not None and price_cents > 0` before append. REL-01 fix: price block is in its own try/except (line 213-220). `test_price_history_db_error_does_not_propagate` passes. |
| 10 | Absolute target_price reached/below OR price_drop_pct drop from the last-seen price fires a single price_drop alert per dedup window | VERIFIED | `_check_price_triggers` lines 81-100: integer-cent arithmetic for pct check (C-01 fix). `_evaluate_price_triggers` lines 119-142: armed check gates re-dispatch; `clear_price_alert_armed_sync` on recovery. `test_price_alert_dedup_fires_once`, `test_price_alert_disarms_on_recovery`, `test_pct_drop_trigger_end_to_end`, `test_pct_drop_trigger_with_absolute_target` all pass. |
| 11 | Price alerts use price_alert_armed/price_last_notified and never touch stock dedup columns; alert disarms when price recovers | VERIFIED | `set_price_alert_armed_sync` in `models.py` lines 207-211 updates only `price_alert_armed` and `price_last_notified`. `test_price_dedup_independent_from_stock_dedup` (models level) and `test_price_dedup_independent` (orchestrator level) both pass. |
| 12 | Per-item target_price/price_drop_pct from config are seeded into the items table at startup | VERIFIED | `main.py` lines 40-43: explicit loop over `cfg.available.items` calling `update_item_price_config_sync(item.link, item.target_price, item.price_drop_pct)`. `test_seed_writes_price_config` passes. |
| 13 | Running `shoppybot items price-history <name>` prints the last N recorded prices as a plain aligned table with $X.XX prices; default limit 10, --limit N overrides | VERIFIED | `handle_items_price_history` in `core/cli/items.py` line 84-87 calls `svc.get_price_history(args.name, args.limit)`. `_format_price_history_table` lines 60-81 formats each row as `$X.XX`. `ph_p` in `core/cli/__init__.py` lines 92-100 wires `name` positional arg and `--limit` with `default=10`. All four CLI tests pass. |
| 14 | An unknown item name prints a clear no-history message and exits 0; the command makes no network call | VERIFIED | `_format_price_history_table` returns `f"No price history recorded for: {name}"` when rows is empty. `test_cli_price_history_no_item` and `test_cli_price_history_no_network` pass (no `run`/`start` called on the mock). |

**Score:** 14/14 truths verified (2 include live-behavior sub-checks delegated to human)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `models.py` | price_history table, append/read functions, price-alert dedup functions, price-config update function | VERIFIED | Lines 33-81 migration; lines 149-248 eight `_sync` functions. All SQL uses `?` placeholders -- no f-string or `%` interpolation found in any SQL literal. |
| `core/config_schema.py` | ItemConfig.target_price and ItemConfig.price_drop_pct optional fields | VERIFIED | Lines 52-53 in `ItemConfig`. Both `Optional[int]` and `Optional[float]` with `= None` defaults. |
| `tests/test_price_history.py` | Migration idempotency + models function unit tests | VERIFIED | 9 tests (8 original + T-03 limit/order regression). All pass. |
| `notifications/base.py` | NotificationEvent three optional price fields (default None); shared cents_to_display helper | VERIFIED | Lines 13-17 `cents_to_display`; lines 47-49 three `= None` dataclass fields. |
| `core/plugin_base.py` | get_price() default-None ABC hook | VERIFIED | Lines 71-78 concrete `async def get_price` returning None. |
| `plugins/shopbot_plugin_amazon.py` | real get_price() + _parse_price_to_cents text parser | VERIFIED | Lines 34-56 parser function; lines 223-244 `get_price` override. |
| `tests/test_price_payload.py` | parser fixtures + event field + notifier price_drop branch tests | VERIFIED | 6 tests. All pass. |
| `core/orchestrator.py` | _check_and_buy price path, _evaluate_price_triggers, _check_price_triggers, _build_price_drop_event | VERIFIED | Lines 57-220. C-01 (integer-cent arithmetic) and REL-01 (isolated try/except) fixes present. |
| `core/service.py` | config seeding via update_item_price_config_sync + get_price_history accessor | VERIFIED | Lines 76-87 `get_price_history`; `update_item_price_config_sync` imported on line 23 (seeding in main.py, not service.py -- correct single source of truth). |
| `tests/test_price_alert.py` | trigger math + dedup + dispatch capture tests | VERIFIED | 13 tests including C-01 boundary regression, REL-01 regression, T-02 pct-drop integration, T-04 None/zero guards. All pass. |
| `core/cli/items.py` | handle_items_price_history + _format_price_history_table | VERIFIED | Lines 60-87. K-01 fix: imports `cents_to_display` from `notifications.base`. K-02 fix: typed rows. |
| `core/cli/__init__.py` | price-history subparser leaf under items_sub with name + --limit | VERIFIED | Lines 92-100. |
| `tests/test_cli_price_history.py` | CLI stdout + limit + no-item tests | VERIFIED | 4 tests. All pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `models.initialize_db` | items table + price_history table | PRAGMA table_info guard + CREATE TABLE IF NOT EXISTS | VERIFIED | `models.py` lines 48-81 |
| `ItemConfig` | items table | `update_item_price_config_sync` at startup in main.py | VERIFIED | `main.py` lines 42-43 |
| `AmazonPlugin.get_price` | `_parse_price_to_cents` | DOM price text → integer cents | VERIFIED | `plugins/shopbot_plugin_amazon.py` lines 238 |
| `NotificationEvent` | discord/email/sms notifiers | `action == price_drop` branch reads price fields | VERIFIED | All three notifiers confirmed |
| `_check_and_buy` | `append_price_history_sync` + `_evaluate_price_triggers` | get_price call; read last price before append | VERIFIED | `core/orchestrator.py` lines 206-220 |
| `_evaluate_price_triggers` | `dispatcher.notify(price_drop event)` | armed check via `get_price_alert_state_sync`; set after | VERIFIED | `core/orchestrator.py` lines 119-142 |
| `config seeding` | items table | `update_item_price_config_sync` per config item at startup | VERIFIED | `main.py` lines 42-43 |
| `handle_items_price_history` | `BotService.get_price_history` | `svc.get_price_history(args.name, args.limit)` | VERIFIED | `core/cli/items.py` line 86 |
| `items_sub price-history parser` | `handle_items_price_history` | `ph_p.set_defaults(func=handle_items_price_history)` | VERIFIED | `core/cli/__init__.py` line 100 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `_check_and_buy` | `price_cents` | `plugin.get_price(link)` (awaited, wrapped in try/except) | Yes -- routed to `append_price_history_sync` then `_evaluate_price_triggers` | FLOWING |
| `handle_items_price_history` | `rows` | `svc.get_price_history(args.name, args.limit)` → `get_price_history_sync(link, limit)` → DB SELECT | Yes -- parameterized SELECT, returns real rows | FLOWING |
| `_evaluate_price_triggers` | `item_row` | `get_item_price_config_sync(link)` → DB SELECT target_price/price_drop_pct | Yes -- returns actual configured values or (None, None) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All phase test files pass | `python -m pytest tests/test_price_history.py tests/test_price_payload.py tests/test_price_alert.py tests/test_cli_price_history.py -q` | 36 passed | PASS |
| Full suite no regression | `python -m pytest -q` | 529 passed, 2 skipped | PASS |
| PLUGIN_API_VERSION unchanged | `grep PLUGIN_API_VERSION core/plugin_base.py` | `PLUGIN_API_VERSION = 2` | PASS |
| No SQL string interpolation in models | `grep "f\".*SELECT\|f\".*INSERT\|f\".*UPDATE" models.py` | 0 matches | PASS |
| No TBD/FIXME/XXX debt markers in phase files | `grep "TBD\|FIXME\|XXX" <phase-modified files>` | 0 matches | PASS |

### Probe Execution

No probe scripts declared for this phase; `scripts/*/tests/probe-*.sh` pattern not applicable.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PRICE-01 | Plan 01 | Per-item absolute target_price in config; NULL = monitoring off | SATISFIED | `ItemConfig.target_price: Optional[int] = None`; `update_item_price_config_sync`; items column `target_price INTEGER` |
| PRICE-02 | Plans 01, 02, 03 | get_price() plugin hook (default None); prices recorded to append-only price_history table each poll cycle | SATISFIED (automated); live DOM scrape = human | `RetailerPlugin.get_price` default None; `AmazonPlugin.get_price` real implementation; orchestrator calls it each cycle; `append_price_history_sync` writes to `price_history` |
| PRICE-03 | Plan 03 | Fan-out price_drop alerts via existing dispatcher; dedup separate from stock alerts | SATISFIED | `_evaluate_price_triggers` uses `price_alert_armed`/`price_last_notified` only; dispatches via `NotificationDispatcher`; independence asserted by tests |
| PRICE-04 | Plans 02, 03 | Alert payloads include current price, target price, and percentage from target | SATISFIED | `NotificationEvent` price fields; `_build_price_drop_event` populates all three; Discord/Email/SMS formatters render them |
| PRICE-05 | Plans 01, 03 | price_drop_pct secondary trigger: N%+ drop from last-seen price | SATISFIED | `price_drop_pct REAL` column; `_check_price_triggers` integer-cent arithmetic (C-01 fix); pct-drop end-to-end integration tests pass |
| PRICE-06 | Plan 04 | `shoppybot items price-history <name>` shows last N prices, default 10, --limit N | SATISFIED | CLI wired and fully tested; `_format_price_history_table` renders $X.XX table; no-item message; no network call |

No orphaned requirements: REQUIREMENTS.md maps PRICE-01 through PRICE-06 exclusively to Phase 16, and all six are covered by the four plans above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | -- | No TBD/FIXME/XXX markers; no stub returns; no hardcoded empty data paths | -- | -- |

Notable quality items from the REVIEW (all resolved):
- C-01: pct-drop trigger false positive (rounded float compared to threshold) -- fixed with integer-cent arithmetic; regression test present
- REL-01: price block not isolated in try/except -- fixed; regression test present
- K-01: `_cents_to_display` duplicated -- consolidated into `notifications/base.py:cents_to_display`
- T-04: `_parse_price_to_cents("-$5.00")` returned 500 instead of None -- fixed with `-` prefix guard; regression tests added

### Human Verification Required

#### 1. Live Amazon DOM Price Scrape

**Test:** Configure a real Amazon product URL in `config.yml` under `available.items`. Start the bot (`shoppybot run` with a real Chrome install). Observe log output for a `[AmazonPlugin] get_price` call. Check `data/shop_py_bot.db` via `shoppybot items price-history <name>`.
**Expected:** A row appears in the price_history table with a plausible integer-cents value (e.g. 4999 for $49.99). No error logged from get_price path.
**Why human:** Requires a live Chrome subprocess via nodriver, a real Amazon product URL, and a non-headless or headless Chrome installation. Not runnable in this verification environment.

#### 2. Live Price-Drop Fan-Out Alert

**Test:** Set `target_price` in `config.yml` to a value above the current live Amazon price for a tracked item (so the absolute trigger fires on the next poll). Enable at least one notifier channel (Discord webhook, email, or SMS). Run one poll cycle.
**Expected:** One `price_drop` notification is delivered to each enabled channel with current price, target price, and percentage. The `price_alert_armed` column in `items` is set to 1 after the cycle. A second poll cycle with the same low price does NOT re-send.
**Why human:** Requires configured notifier credentials, a live Amazon price below the configured target, and a real poll loop execution.

### Gaps Summary

No gaps. All 14 automated must-haves are VERIFIED. The two human verification items are live-behavior checks that cannot be automated without a running Chrome subprocess and configured notifier credentials. They do not indicate missing code -- the implementation is complete and all code paths are unit-tested.

---

_Verified: 2026-06-09_
_Verifier: Claude (gsd-verifier)_
