---
phase: 17
slug: test-hardening
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-09
---

# Phase 17 — Validation Strategy

> Per-phase validation contract. This phase IS test hardening — the deliverables are tests; validation is that they (a) pass, (b) execute the previously-uncovered target lines/branches, and (c) the full suite stays green.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio (asyncio_mode=auto) + pytest-cov 7.1.0 |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `python -m pytest -q <touched test file>` |
| **Full suite command** | `python -m pytest` |
| **Coverage check** | `python -m pytest --cov=core --cov=models --cov=plugins --cov=notifications --cov-report=term-missing` |
| **Estimated runtime** | ~40 seconds |

---

## Sampling Rate

- **After every task/plan:** run the touched `tests/test_*.py -q`
- **After the phase:** full `python -m pytest` + a `--cov` run; confirm the PR-01 migration path, captcha error branches, registry isolation branches, orchestrator price guards, and the `_handle_ban` 53→55 branch are now executed.
- **Before `/gsd:verify-work`:** full suite green; no new failures vs the 529-passed baseline (count rises with the ~19 new tests).

---

## Per-Task Verification Map

| Task | Plan | Wave | Requirement | Tests | Automated Command |
|------|------|------|-------------|-------|-------------------|
| 17-01-01 | 01 | 1 | STAB-03 | PX-01,02,03 | `pytest -q tests/test_proxy_config.py tests/test_stealth.py -k "proxyconfig_rejects_invalid_proxy_url or setup_proxy_auth_request_paused_continues or proxypool_empty_and_pool_level_methods"` |
| 17-01-02 | 01 | 1 | STAB-03 | PX-04,05,06 | `pytest -q tests/test_registry.py -k "plugins_for_items_dedups_and_skips_unmatched or setup_for_items_skips_plugin_on_setup_error or teardown_all_logs_and_continues_on_error"` |
| 17-02-01 | 02 | 1 | STAB-03 | CP-01,02,03 | `pytest -q tests/test_captcha.py -k "solve_recaptcha_poll_error_raises_runtimeerror or solve_recaptcha_exceeds_max_polls_raises_timeout or balance_check_error_response_disables_solver"` |
| 17-02-02 | 02 | 1 | STAB-03 | CP-04,05 | `pytest -q tests/test_captcha.py -k "solve_amazon_waf_success_returns_decoded_dict or solve_amazon_waf_non_json_token_falls_back_and_submit_error_raises"` |
| 17-03-01 | 03 | 1 | STAB-03 | PR-01,04 | `pytest -q tests/test_price_history.py -k "v2_schema_db_migrates_to_v3_in_place or price_config_and_alert_state_for_missing_item"` |
| 17-03-02 | 03 | 1 | STAB-03 | PR-02,03 + AB-01,02 | `pytest -q tests/test_price_alert.py -k "pct_helpers_guard_nonpositive_denominator or evaluate_price_triggers_skips_when_no_config or get_price_error_is_isolated_and_does_not_propagate or get_price_invoked_alongside_check_availability_sequencing"` |
| 17-04-01 | 04 | 1 | STAB-03 | AB-03,04 | `pytest -q tests/test_plugin_base.py -k "requires_captcha_and_easy_difficulty_overrides or handle_ban_records_failure_on_proxy_when_banned"` |

*Plans touch disjoint test files (no intra-wave overlap).*

---

## Wave 0 Requirements

*All target test files already exist; this phase EXTENDS them. No scaffolding. No new deps (pytest-cov already installed).*

---

## Manual-Only Verifications

*None — this is a pure test-authoring phase. All new tests are deterministic and CI-runnable. (Live-environment manual checks for the v3.0 FEATURES themselves remain tracked in the per-phase HUMAN-UAT files for phases 12-16; they are not in scope here.)*

---

## Validation Sign-Off

- [x] Each of the 4 STAB-03 criteria maps to named passing tests
- [x] The v2.0-schema migration fixture test (PR-01) exists and passes
- [x] Previously-uncovered target lines/branches are now executed (verified via --cov)
- [x] Full `python -m pytest` green; no regressions
- [x] No new dependency; no legacy/e2e tests added
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-09
