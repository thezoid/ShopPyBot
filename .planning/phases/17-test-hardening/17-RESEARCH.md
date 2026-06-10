# Phase 17: Test Hardening - Research (Coverage Gap Report)

**Produced:** 2026-06-09 via parallel coverage-gap analysis (4 criterion analysts + completeness critic), grounded in the live `pytest-cov --cov-report=term-missing` (and `--cov-branch`) report. Baseline: 529 passed, 2 skipped, ~75% total / 84-100% on v3.0 modules.

This report enumerates the concrete missing tests for STAB-03. Every entry targets a genuinely uncovered line/branch (verified) and is deterministic + CI-safe (no live browser/network/2captcha/proxy/Amazon) and in-scope (no legacy v1/v2 plugin bodies, no e2e checkout).

## Missing Tests (19, deduped)

### Criterion 1 — Proxy (config parsing, ban-signal detection, per-instance scoping, cooldown/retire)

| ID | test_file | test_name | Closes | Pri |
|----|-----------|-----------|--------|-----|
| PX-01 | tests/test_proxy_config.py | test_proxyconfig_rejects_invalid_proxy_url | config_schema.py:256-257 url validator rejection (schemeless / portless / hostname-only) + positive control | high |
| PX-02 | tests/test_stealth.py | test_setup_proxy_auth_request_paused_continues | stealth.py:303-307 `_on_request_paused` create_task(continue_request) + _live_tasks | high |
| PX-03 | tests/test_stealth.py | test_proxypool_empty_and_pool_level_methods | stealth.py:222 `__len__`, 231 current()→None, 243 advance()→None, 257 pool.record_success | medium |
| PX-04 | tests/test_registry.py | test_plugins_for_items_dedups_and_skips_unmatched | registry.py:120 _route_all no-match, 129-136 plugins_for_items id()-dedup + skip | high |
| PX-05 | tests/test_registry.py | test_setup_for_items_skips_plugin_on_setup_error | registry.py:158-159 setup failure isolation (WARNING + skip, no abort) | medium |
| PX-06 | tests/test_registry.py | test_teardown_all_logs_and_continues_on_error | registry.py:169-170 teardown error isolation | medium |

### Criterion 2 — CAPTCHA (config parsing, balance-check, executor wrapping, spend-cap)

| ID | test_file | test_name | Closes | Pri |
|----|-----------|-----------|--------|-----|
| CP-01 | tests/test_captcha.py | test_solve_recaptcha_poll_error_raises_runtimeerror | captcha.py:72 poll-error (non NOT_READY) → RuntimeError; _solve_count still consumed | high |
| CP-02 | tests/test_captcha.py | test_solve_recaptcha_exceeds_max_polls_raises_timeout | captcha.py:74 TimeoutError after _MAX_POLLS; assert get.call_count == _MAX_POLLS | high |
| CP-03 | tests/test_captcha.py | test_balance_check_error_response_disables_solver | captcha.py:89 generic ERROR_ balance → RuntimeError → balance_ok False; key never logged | high |
| CP-04 | tests/test_captcha.py | test_solve_amazon_waf_success_returns_decoded_dict | captcha.py:179,180-198,201 WAF submit+poll+json.loads happy path; _solve_count increments | high |
| CP-05 | tests/test_captcha.py | test_solve_amazon_waf_non_json_token_falls_back_and_submit_error_raises | captcha.py:202-203 non-JSON fallback, 195-196 submit-error raise | medium |

### Criterion 3 — Price (threshold logic, price_history schema + v2.0-DB migration, dedup separation)

| ID | test_file | test_name | Closes | Pri |
|----|-----------|-----------|--------|-----|
| PR-01 | tests/test_price_history.py | test_v2_schema_db_migrates_to_v3_in_place | **models.py:48-81 ALTER branch against a hand-built v2.0 items table (no v3.0 cols, no price_history) + legacy row survives + idempotent 2nd run.** THE criterion-required migration fixture. | high |
| PR-02 | tests/test_price_alert.py | test_pct_helpers_guard_nonpositive_denominator | orchestrator.py:70,77 `<=0` denominator guards → 0.0 | medium |
| PR-03 | tests/test_price_alert.py | test_evaluate_price_triggers_skips_when_no_config | orchestrator.py:123 item_row None, 126 both-None config early returns (no alert, no arming) | medium |
| PR-04 | tests/test_price_history.py | test_price_config_and_alert_state_for_missing_item | models.py:198 get_price_alert_state row-None, 246 get_item_price_config row-None | medium |

### Criterion 4 — Plugin ABC additions + get_price() alongside check_availability

| ID | test_file | test_name | Closes | Pri |
|----|-----------|-----------|--------|-----|
| AB-01 | tests/test_price_alert.py | test_get_price_error_is_isolated_and_does_not_propagate | orchestrator.py:209-210 get_price exception caught/logged, cycle continues, availability path still runs | high |
| AB-02 | tests/test_price_alert.py | test_get_price_invoked_alongside_check_availability_sequencing | get_price runs even when available False; skipped when check_availability raises (early return before get_price) | medium |
| AB-03 | tests/test_plugin_base.py | test_requires_captcha_and_easy_difficulty_overrides | plugin_base requires_captcha=True + difficulty='easy' override permutation (do NOT re-assert get_price default — already covered) | low |
| AB-04 | tests/test_plugin_base.py | test_handle_ban_records_failure_on_proxy_when_banned | **plugin_base.py branch 53→55: `_handle_ban` ban phrase → pool.record_failure(proxy); benign→no call; no-proxy-configured safe path.** The bridge from ban-detection to per-instance proxy scoping/cooldown (critic G-01). | high |

## Plan Grouping (by test file — no intra-wave collision)

- **17-01 Proxy:** PX-01..PX-06 (test_proxy_config.py, test_stealth.py, test_registry.py)
- **17-02 CAPTCHA:** CP-01..CP-05 (test_captcha.py)
- **17-03 Price:** PR-01..PR-04 + AB-01, AB-02 (test_price_history.py, test_price_alert.py)
- **17-04 Plugin ABC:** AB-03, AB-04 (test_plugin_base.py)

These four plans touch disjoint test files → safe to wave together (executed sequentially since worktrees disabled).

## Validation Architecture

- **Framework:** pytest 7.x + pytest-asyncio (asyncio_mode=auto) + pytest-cov 7.1.0 — all installed, no new deps.
- **Sampling:** after each plan, run the touched `tests/test_*.py -q`; after the phase, run the full `python -m pytest` and a focused `--cov` on the v3.0 modules to confirm the targeted lines/branches are now hit.
- **Determinism:** every new test mocks the boundary (nodriver tab/CDP via MagicMock+AsyncMock, `requests` via patch, `time.sleep` no-op for captcha polls, raw sqlite3 for the v2.0 fixture under the tmp_data_dir DB redirect). No network, no browser, no real services.
- **Done = green suite + each of the 4 criteria mapped to named passing tests + the previously-uncovered target lines/branches now executed.**

## Open Questions (RESOLVED)

- The v2.0-schema migration fixture test (criterion 3) did NOT exist — RESOLVED: PR-01 builds it (the analysts proposed it twice identically; implement ONCE).
- AB-04 (_handle_ban bridge) was missed by the per-criterion analysts — RESOLVED: added from the completeness critic; it is the most material STAB-03.1 sub-requirement gap.
