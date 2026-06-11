---
phase: 19-db-schema-confirmation-detection
verified: 2026-06-11T12:00:00Z
status: human_needed
score: 14/14
overrides_applied: 0
human_verification:
  - test: "Run the bot in test_mode against a real Amazon account and complete the buy flow; confirm the confirmation page URL contains /gp/buy/thankyou and that order_id is captured (not a sentinel)."
    expected: "DB row has purchased=1, order_id matching actual Amazon order number (XXX-XXXXXXX), confirmed_at set."
    why_human: "DOM selector #confirmedOrderId and URL query param orderID require a live Amazon session. FakeTab tests confirm the detection logic but not that Amazon's actual page renders the expected elements."
  - test: "Run the bot in test_mode against a real BestBuy account and complete the buy flow; confirm .thank-you-order-number selector is populated on the real thank-you page."
    expected: "DB row has purchased=1, order_id containing a BestBuy order number (BBY01-xxx), confirmed_at set."
    why_human: "DOM selector .thank-you-order-number is tagged MEDIUM confidence in _PLATFORM_MAP. Live page structure not yet verified."
  - test: "Trigger an Amazon checkout where payment fails but the browser redirects to /gp/buy/thankyou anyway (thankyou-on-payment-failure path). Verify sentinel handling."
    expected: "DB row has purchased=1, order_id starting with 'CONFIRMED-' (sentinel), confirmed_at set. Phase 21 must not treat this as a confirmed idempotency key."
    why_human: "Payment-failure sentinel risk documented in _CONFIRMED_SENTINEL_PREFIX docstring and REVIEW.md WR-01. Cannot be reproduced without a real checkout that fails at payment."
---

# Phase 19: DB Schema + Confirmation Detection — Verification Report

**Phase Goal:** Purchases are only recorded when the bot has verified a real order number from the retailer's confirmation page, never on a button click alone.
**Verified:** 2026-06-11T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | items table has order_id TEXT, confirmed_at TEXT, checkout_attempts INTEGER NOT NULL DEFAULT 0 | VERIFIED | models.py lines 73-80: three idempotent ALTER guards; checkout_attempts declared NOT NULL DEFAULT 0 |
| 2 | v3.0-schema DB migrates losslessly (no DROP/recreate) | VERIFIED | test_migration_on_legacy_schema: bare v3.0 items table gains all 3 columns via initialize_db(); PASSING |
| 3 | Re-running initialize_db() on already-migrated DB does not error or duplicate columns | VERIFIED | test_migration_idempotent_confirmation: column count == 1 for each after two initialize_db() calls; PASSING |
| 4 | update_item_confirmed_sync sets purchased=1, order_id, confirmed_at together | VERIFIED | models.py lines 107-117: single parameterized UPDATE; test_update_item_confirmed PASSING |
| 5 | detect_order_confirmation(tab, platform) exists in core/confirmation.py | VERIFIED | core/confirmation.py lines 113-151: async def, returns str or None |
| 6 | Amazon orderID parsed from URL query param before any DOM read | VERIFIED | _extract_order_id tries url_query_params loop before selectors loop; test_url_match_url_param PASSING |
| 7 | URL match + no order_id returns CONFIRMED- sentinel + WARNING logged | VERIFIED | confirmation.py lines 145-151; test_url_match_dom_miss_returns_sentinel PASSING |
| 8 | URL mismatch and unknown platform return None | VERIFIED | test_url_no_match, test_unknown_platform PASSING |
| 9 | Orchestrator calls detect_order_confirmation after auto_buy True | VERIFIED | orchestrator.py lines 203-213: tab = plugin.get_active_tab(); await detect_order_confirmation(tab, platform) |
| 10 | Non-None order_id enqueues exactly one ("confirmed", link, order_id, ts) 4-tuple | VERIFIED | test_orchestrator_confirmed_path, test_no_double_buy_single_put PASSING; q.qsize() == 1 asserted |
| 11 | None order_id logs WARNING and enqueues exactly one legacy ("purchased", link) | VERIFIED | test_orchestrator_fallback_path PASSING; WARNING captured; q.qsize() == 1 asserted |
| 12 | ("confirmed",...) dispatch routes to update_item_confirmed_sync via run_in_executor | VERIFIED | orchestrator.py lines 296-299; test_dispatch_confirmed_tag PASSING: purchased=1, order_id, confirmed_at all set |
| 13 | Amazon and BestBuy store self._last_tab before place_order_guarded; override get_active_tab() | VERIFIED | amazon.py line 421: self._last_tab = tab before place_order_guarded; bestbuy.py line 315 same; both define get_active_tab() returning getattr(self, "_last_tab", None) or getattr(self.driver, "main_tab", None) |
| 14 | auto_buy True + detection raises -> legacy purchased enqueued once (no double-buy, no zero-enqueue) | VERIFIED | _try_auto_buy has split try blocks (WR-02 fix); test_no_double_buy_on_confirmation_detection_error PASSING |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `models.py` | 3 idempotent ALTER TABLE column additions + update_item_confirmed_sync | VERIFIED | Lines 72-80 (columns), 107-117 (writer) |
| `core/confirmation.py` | detect_order_confirmation + _extract_order_id + _PLATFORM_MAP + _SETTLE_SECS + _CONFIRMED_SENTINEL_PREFIX | VERIFIED | All five present; _CONFIRMED_SENTINEL_PREFIX = "CONFIRMED-" constant at line 32 |
| `core/plugin_base.py` | get_active_tab() concrete sync default on RetailerPlugin ABC | VERIFIED | Lines 81-88: def get_active_tab returning getattr(self.driver, "main_tab", None); PLUGIN_API_VERSION stays 2 |
| `core/orchestrator.py` | _try_auto_buy confirmation wiring + _dispatch_write ("confirmed",...) branch + update_item_confirmed_sync import | VERIFIED | Lines 26-39 (import), 183-222 (_try_auto_buy), 296-299 (_dispatch_write confirmed branch) |
| `plugins/shopbot_plugin_amazon.py` | self._last_tab = tab before place_order_guarded + get_active_tab() override + getattr-safe test_mode | VERIFIED | Line 421 (_last_tab), line 427-429 (get_active_tab), lines 400-401 (getattr pattern for test_mode — CR-01 fix) |
| `plugins/shopbot_plugin_bestbuy.py` | self._last_tab = tab before place_order_guarded + get_active_tab() override + monitor_only entry guard | VERIFIED | Line 315 (_last_tab), lines 321-323 (get_active_tab), lines 260-263 (monitor_only guard — WR-03 fix) |
| `tests/test_models.py` | 4 migration + writer tests | VERIFIED | test_confirmation_columns_added, test_migration_on_legacy_schema, test_migration_idempotent_confirmation, test_update_item_confirmed — all PASSING |
| `tests/test_confirmation.py` | FakeTab-driven unit coverage (6 + CR-02 regression test) | VERIFIED | 7 tests total; test_extract_order_id_uses_settled_url_snapshot covers CR-02 stale-URL race fix — all PASSING |
| `tests/test_orchestrator.py` | confirmed-path, fallback-path, dispatch-tag, single-put, detection-error coverage | VERIFIED | 5 new tests (test_orchestrator_confirmed_path, test_orchestrator_fallback_path, test_dispatch_confirmed_tag, test_no_double_buy_single_put, test_no_double_buy_on_confirmation_detection_error) — all PASSING |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| _try_auto_buy | detect_order_confirmation | plugin.get_active_tab() then await detect_order_confirmation(tab, platform) | WIRED | orchestrator.py lines 203-213 |
| _dispatch_write ("confirmed",...) | update_item_confirmed_sync | loop.run_in_executor(None, update_item_confirmed_sync, link, order_id, ts) | WIRED | orchestrator.py lines 297-298 |
| Amazon/BestBuy auto_buy | get_active_tab() | self._last_tab = tab before place_order_guarded; override returns _last_tab or main_tab | WIRED | amazon.py 421/429, bestbuy.py 315/323 |
| models.py initialize_db() | items table | ALTER TABLE items ADD COLUMN guarded by PRAGMA table_info existing set | WIRED | models.py lines 48-80 |
| update_item_confirmed_sync | items table | parameterized UPDATE SET purchased=1, order_id=?, confirmed_at=? WHERE link=? | WIRED | models.py lines 113-116 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| _dispatch_write | order_id, ts from ("confirmed",...) tuple | detect_order_confirmation return value (URL query param or DOM) | Yes — URL param or DOM text from live retailer page | FLOWING |
| update_item_confirmed_sync | order_id, confirmed_at, link | caller-supplied via parameterized UPDATE | Yes — parameterized, no string interpolation | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full targeted test suite (37 tests) | pytest tests/test_models.py tests/test_confirmation.py tests/test_orchestrator.py | 37 passed, 0 failed | PASS |
| Full suite regression (599 tests) | pytest -q | 599 passed, 2 skipped, 0 failed | PASS |
| checkout_attempts not incremented anywhere | grep checkout_attempts models.py core/ plugins/ | Only in ALTER TABLE statement (line 79) and docstring (line 111) | PASS |
| write_queue.put() not inside asyncio.timeout | grep asyncio.timeout orchestrator.py | Only asyncio.wait_for in shutdown flush (line 434), not in _try_auto_buy | PASS |
| CONFIRMED_SENTINEL_PREFIX constant exists | grep _CONFIRMED_SENTINEL_PREFIX confirmation.py | Defined at line 32; used at line 148 and 151 | PASS |

### Probe Execution

No probe scripts declared or found for this phase. SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BUY-03 | 19-02, 19-03, 19-04 | Orchestrator verifies placed order via confirmation URL + order-number signal; purchased written only on confirmed order | SATISFIED | detect_order_confirmation wired in _try_auto_buy; legacy fallback on None; WARNING logged; no double-buy |
| BUY-04 | 19-01 | Bot records checkout outcome with order_id and timestamp | SATISFIED | order_id TEXT, confirmed_at TEXT columns; update_item_confirmed_sync sets all three together |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| plugins/shopbot_plugin_bestbuy.py | 276 | TODO comment (pre-existing from Phase 18, commit f772479) | Info | Not introduced by Phase 19; concerns cart quantity selector correctness — UAT debt pre-existing |
| core/confirmation.py | 25 | "XXX-XXXXXXX" string in comment | Info | Amazon order ID format documentation, not a debt marker — false positive from scanner |

No TBD, FIXME, or unresolved XXX debt markers introduced by Phase 19.

### Human Verification Required

#### 1. Amazon Live Confirmation URL and DOM Selector

**Test:** Run the bot in test_mode=false against a real Amazon account on an available in-stock item with auto_buy=true. Monitor DB after the buy flow completes.
**Expected:** Row has purchased=1; order_id matches the Amazon order number visible on the confirmation page (format XXX-XXXXXXX, not a CONFIRMED- sentinel); confirmed_at is a UTC ISO timestamp.
**Why human:** URL query param orderID and DOM selector #confirmedOrderId require a live Amazon checkout session. FakeTab tests confirm parsing logic but not that Amazon currently renders these values on the actual confirmation page.

#### 2. BestBuy Live Confirmation DOM Selector

**Test:** Run the bot against a real BestBuy account on an available item with auto_buy=true. Monitor DB row after completion.
**Expected:** Row has purchased=1; order_id matches BestBuy order number (BBY01-xxx format or equivalent); not a sentinel.
**Why human:** DOM selector .thank-you-order-number is marked MEDIUM confidence / UAT debt in _PLATFORM_MAP. Live page structure not verified.

#### 3. Amazon Payment-Failure Sentinel Risk (UAT debt)

**Test:** Trigger an Amazon buy flow where payment fails but the page still redirects to /gp/buy/thankyou. Inspect the DB row after the flow.
**Expected:** Row has purchased=1; order_id starts with "CONFIRMED-" (sentinel); Phase 21 must not use this as a confirmed idempotency key.
**Why human:** Sentinel written on a real confirmation failure cannot be reproduced without a live account where payment deliberately fails. The _CONFIRMED_SENTINEL_PREFIX constant and its docstring document this risk for Phase 21.

### Gaps Summary

No gaps. All 14 must-have truths are verified. All post-review fixes (CR-01 getattr-safe test_mode, CR-02 current_url snapshot, WR-01 sentinel constant, WR-02 split try blocks, WR-03 BestBuy monitor_only guard) are present in the codebase and covered by regression tests. The test suite is fully green (599/599 + 2 intentional skips).

Three human verification items represent UAT debt on live confirmation DOM selectors and the payment-failure sentinel path — these are explicitly noted as live-environment checks in REQUIREMENTS.md "Out of Scope" and cannot be automated without a live retail session.

---

_Verified: 2026-06-11T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
