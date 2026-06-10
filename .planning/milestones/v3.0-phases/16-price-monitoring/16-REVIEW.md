---
phase: 16
slug: price-monitoring
status: resolved
reviewed_at: 2026-06-09
resolved_at: 2026-06-09
findings_total: 10
findings_fixed: 10
findings_deferred: 0
---

# Phase 16: Price Monitoring -- Code Review

## Status: Resolved

All 10 adversarially-confirmed findings addressed. Full test suite: 529 passed, 2 skipped.

## Findings Summary

| ID    | Severity | File(s) | Issue | Resolution |
|-------|----------|---------|-------|------------|
| C-01  | Critical | core/orchestrator.py | pct-drop trigger pre-rounded to 1 decimal, causing false positives (9.96% fired 10% threshold) | Fixed: _check_price_triggers uses integer-cent arithmetic `(prev-current)*100 >= threshold*prev`. _pct_drop_from_last retained for display only. Regression test added. |
| REL-01 | Critical | core/orchestrator.py | price append + trigger block not in try/except; DB exception escaped into TaskGroup, cancelling all sibling plugin tasks | Fixed: wrapped price block in dedicated try/except that logs class name only and continues. Regression test: DB raise does not propagate out of _check_and_buy. |
| K-01  | Quality | notifications/base.py, discord_notifier.py, email_notifier.py, sms_notifier.py, core/orchestrator.py, core/cli/items.py | `_cents_to_display` duplicated byte-for-byte across 3 notifiers, near-dup in orchestrator, inlined in cli/items.py | Fixed: single `cents_to_display(cents)` in notifications/base.py; all consumers import and use it. |
| K-02  | Quality | core/cli/items.py | `_format_price_history_table` untyped rows, magic r[0]/r[1]/r[2], docstring said `recorded_at` (column is `scraped_at`) | Fixed: `rows: list[tuple[int, str, str]]`, unpacked with names, docstring corrected. |
| K-03  | Quality | core/service.py | `get_price_history() -> list:` bare return type | Fixed: tightened to `-> list[tuple[int, str, str]]` matching get_price_history_sync. |
| T-01  | Test confidence | tests/test_price_alert.py | test_price_dedup_independent vacuous -- captured last_notified_before but never asserted unchanged | Fixed: set available=False to isolate price path; capture snapshot before cycle; assert stock dedup columns byte-identical after price_drop fires. |
| T-02  | Test confidence | tests/test_price_alert.py | pct-drop trigger never exercised end-to-end | Fixed: two integration tests added: (a) pct-drop-only seeds history cycle 1, fires once on 10% drop cycle 2, dedup blocks cycle 3; (b) absolute-target fires in a single cycle with no double-fire. |
| T-03  | Test confidence | tests/test_price_history.py | LIMIT + DESC order not behaviorally verified (only 1 row inserted) | Fixed: 3 rows with increasing scraped_at inserted; asserts limit=2 returns exactly 2 rows and rows[0] is newest. |
| T-04  | Test confidence | tests/test_price_alert.py, tests/test_price_payload.py, plugins/shopbot_plugin_amazon.py | None/0/negative price guards untested; `_parse_price_to_cents("-$5.00")` returned 500 (bug) | Fixed: _parse_price_to_cents rejects strings containing '-' before stripping. Orchestrator tests verify None and 0 from get_price skip append and triggers. Parser fixtures assert $0.00 and negative strings return None. |
| C-02  | Info | core/orchestrator.py | _pct_from_target display percentage could overstate discount (display-only, tied to C-01) | Fixed: added docstring note clarifying this is display-only; trigger decision uses integer-cent arithmetic (done in C-01). |

## Commit History

- `0cdf029` fix: C-01 pct-drop trigger uses integer-cent arithmetic to prevent false positives
- `99c5de5` fix: REL-01 isolate price-history block in try/except inside _check_and_buy
- `361aa3d` refactor: K-01 consolidate cents_to_display into notifications/base.py
- `8a31503` fix: K-02 type-annotate _format_price_history_table rows, fix docstring
- `8798099` fix: K-03 tighten get_price_history return type to list[tuple[int, str, str]]
- `51ad8e2` test: T-01 strengthen test_price_dedup_independent
- `52d9cf8` test: T-02 add pct-drop trigger end-to-end integration tests
- `0c3bade` test: T-03 verify get_price_history_sync LIMIT and DESC order behaviorally
- `9ce3d19` fix+test: T-04 None/0/negative price guards
- `5df702e` docs: C-02 note that _pct_from_target is display-only
