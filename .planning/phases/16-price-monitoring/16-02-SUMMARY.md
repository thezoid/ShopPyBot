---
phase: 16-price-monitoring
plan: "02"
subsystem: notifications, plugin-abc, amazon-plugin
tags: [price-monitoring, notification-event, plugin-abc, amazon, tdd]
dependency_graph:
  requires: []
  provides:
    - NotificationEvent price fields (price_cents, target_price_cents, pct_from_target)
    - get_price() ABC hook with default-None on RetailerPlugin
    - AmazonPlugin._parse_price_to_cents + get_price() real implementation
    - _build_email_body() / _build_sms_body() helpers
    - price_drop formatting branches in Discord/Email/SMS notifiers
  affects:
    - notifications/base.py
    - core/plugin_base.py
    - plugins/shopbot_plugin_amazon.py
    - notifications/discord_notifier.py
    - notifications/email_notifier.py
    - notifications/sms_notifier.py
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN per plan task sequence
    - re.sub strip + round(float*100) for price-string parsing (no eval/exec)
    - _cents_to_display() helper per-notifier (inline per-file style, no shared helper)
    - action == "price_drop" branch guards all price formatting
key_files:
  created:
    - tests/test_price_payload.py
  modified:
    - notifications/base.py
    - core/plugin_base.py
    - plugins/shopbot_plugin_amazon.py
    - notifications/discord_notifier.py
    - notifications/email_notifier.py
    - notifications/sms_notifier.py
decisions:
  - _cents_to_display defined once per notifier file (inline style), not in a shared
    helper module; follows existing per-file convention and avoids a new abstraction
    with only one use case per file.
  - _build_email_body() and _build_sms_body() extracted as module-level helpers
    (testable without running SMTP/Twilio); send() delegates to them.
  - get_price() is a concrete (non-abstract) default on RetailerPlugin; PLUGIN_API_VERSION
    stays 2 per locked CONTEXT.md decision (additive non-breaking).
  - AmazonPlugin.get_price() tries three CSS selectors in order; first non-empty
    element.text that _parse_price_to_cents accepts is returned; any exception
    logs class name only and returns None (T-16-DOS accept, T-16-LEAK mitigated).
  - Selector list (.a-price .a-offscreen, #corePrice_feature_div .a-offscreen,
    #priceblock_ourprice) is site-specific; documented as maintenance-required in SUMMARY.
metrics:
  duration: 8min
  completed: 2026-06-09
  tasks: 4
  files: 6
---

# Phase 16 Plan 02: Price Payload + Plugin Hook Summary

NotificationEvent extended with optional price fields, ABC get_price() hook added
with default None, Amazon implements real DOM price scraping with a fixture-tested
text-to-cents parser, and all three network notifiers format price_drop payloads
with current/target/percentage.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 (RED) | Failing parser/event/notifier tests | RED commit | tests/test_price_payload.py |
| 2 | NotificationEvent price fields + get_price() ABC | feat commit | notifications/base.py, core/plugin_base.py |
| 3 | Amazon get_price() + _parse_price_to_cents | feat commit | plugins/shopbot_plugin_amazon.py |
| 4 | price_drop branch in Discord/Email/SMS | feat commit | notifications/discord_notifier.py, email_notifier.py, sms_notifier.py |

## Deviations from Plan

None. Plan executed exactly as written.

## TDD Gate Compliance

RED commit: `test(16-02): add failing tests for price payload RED phase`
GREEN commits: tasks 2, 3, 4 each a `feat(16-02)` commit after the RED gate.
Gate sequence satisfied.

## Known Stubs

None. All implemented fields are wired and tested.

## Threat Surface Scan

| Flag | File | Description |
|------|------|-------------|
| threat_flag: input-validation | plugins/shopbot_plugin_amazon.py | _parse_price_to_cents mitigates T-16-PRICESTR: re.sub strip + finite/positive guard, no eval/exec |

No new unmitigated surface introduced. T-16-PRICESTR, T-16-DOS, and T-16-LEAK all mitigated as planned.

## Verification

- `python -m pytest tests/test_price_payload.py -q`: 6 passed
- `python -m pytest -q`: 507 passed, 2 skipped (baseline was 501 passed, 2 skipped)
- `PLUGIN_API_VERSION` in core/plugin_base.py: still = 2
- No eval/exec in plugins/shopbot_plugin_amazon.py on scraped text

## Self-Check: PASSED

- tests/test_price_payload.py: FOUND
- notifications/base.py has price_cents field: FOUND
- core/plugin_base.py has get_price(): FOUND
- plugins/shopbot_plugin_amazon.py has _parse_price_to_cents: FOUND
- All 4 task commits present in git log
