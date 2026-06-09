---
phase: 16
slug: price-monitoring
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-09
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (+ pytest-asyncio, installed) |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `python -m pytest -q <touched test file>` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~40 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task's targeted `pytest -q <file>`
- **After every plan wave:** Run `python -m pytest`
- **Before `/gsd:verify-work`:** Full suite green (no new failures vs Phase 15 baseline of 493 passed, 2 skipped)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | PRICE-01, PRICE-02, PRICE-05 | T-16-sql | idempotent migration; parameterized SQL | unit | `python -m pytest tests/test_price_history.py -q` | ✅ | ⬜ pending |
| 16-01-02 | 01 | 1 | PRICE-01, PRICE-02, PRICE-05 | T-16-sql | _sync fns parameterized; integer cents | unit | `python -m pytest tests/test_price_history.py -q` | ✅ | ⬜ pending |
| 16-02-01 | 02 | 1 | PRICE-02, PRICE-04 | — | NotificationEvent price fields backward-compat | unit | `python -m pytest tests/test_price_payload.py -q` | ✅ | ⬜ pending |
| 16-02-02 | 02 | 1 | PRICE-02, PRICE-04 | — | get_price() default None (non-breaking) | unit | `python -m pytest tests/test_price_payload.py::test_event_optional_price_fields_default_none tests/test_price_payload.py::test_get_price_default_none -q` | ✅ | ⬜ pending |
| 16-02-03 | 02 | 1 | PRICE-02 | T-16-parse | text→cents parse guards garbage; Amazon DOM | unit | `python -m pytest tests/test_price_payload.py::test_parse_price_to_cents_fixtures tests/test_price_payload.py::test_amazon_get_price_parses_dom -q` | ✅ | ⬜ pending |
| 16-02-04 | 02 | 1 | PRICE-04 | — | price_drop payload per channel ($X.XX) | unit | `python -m pytest tests/test_price_payload.py::test_discord_price_drop_payload tests/test_price_payload.py::test_email_sms_price_drop_format -q` | ✅ | ⬜ pending |
| 16-03-01 | 03 | 2 | PRICE-02, PRICE-03, PRICE-04, PRICE-05 | — | both triggers; separate dedup; single alert | unit | `python -m pytest tests/test_price_alert.py -q` | ✅ | ⬜ pending |
| 16-03-02 | 03 | 2 | PRICE-02, PRICE-03, PRICE-04, PRICE-05 | — | read prev price before append; dispatch once | unit | `python -m pytest tests/test_price_alert.py -q` | ✅ | ⬜ pending |
| 16-03-03 | 03 | 2 | PRICE-01, PRICE-06 | T-16-sql | seed config parameterized; history accessor | unit | `python -m pytest tests/test_price_alert.py::test_seed_writes_price_config tests/test_price_alert.py::test_get_price_history_accessor -q` | ✅ | ⬜ pending |
| 16-04-01 | 04 | 3 | PRICE-06 | — | RED stub (CLI) | unit | `python -m pytest tests/test_cli_price_history.py -q` | ✅ | ⬜ pending |
| 16-04-02 | 04 | 3 | PRICE-06 | — | price-history table $X.XX; missing item handled | unit | `python -m pytest tests/test_cli_price_history.py::test_cli_price_history tests/test_cli_price_history.py::test_cli_price_history_no_item -q` | ✅ | ⬜ pending |
| 16-04-03 | 04 | 3 | PRICE-06 | — | --limit default 10; no network | unit | `python -m pytest tests/test_cli_price_history.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Test files (`test_price_history.py`, `test_price_payload.py`, `test_price_alert.py`, `test_cli_price_history.py`) created as each plan's first task. Migration-idempotency test runs `initialize_db()` twice; tests use `initialize_db(delete=True)`. No new deps; pytest-asyncio installed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Amazon DOM price scrape end-to-end | PRICE-02 | Requires a real browser on a live Amazon product page | Run the bot on a real Amazon item; confirm a price row records in price_history with the correct cents value |
| Live price-drop alert fan-out | PRICE-03 | Requires a real price drop + configured notifier channels | Set a target above current price; confirm a single `price_drop` alert fans out with current/target/pct payload |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-09
