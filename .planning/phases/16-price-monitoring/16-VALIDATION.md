---
phase: 16
slug: price-monitoring
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| 16-01-01 | 01 | 1 | PRICE-02 | — | idempotent migration (run twice); parameterized SQL | unit | `python -m pytest tests/test_price_history.py -q` | ❌ W0 | ⬜ pending |

*Planner refines this map per task. Migration idempotency, integer-cents threshold/percentage math, get_price() text→cents parsing (fixtures), notification dispatch (capture), and the CLI (stdout) are all unit-testable without a live browser. Live Amazon price scrape is the only manual item.*

---

## Wave 0 Requirements

- [ ] `tests/test_price_history.py` / `tests/test_price_alert.py` / `tests/test_cli_price_history.py` — created as each plan's first task
- [ ] Migration-idempotency test runs `initialize_db()` twice (existing pattern); tests use `initialize_db(delete=True)`

*No new deps; pytest-asyncio installed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Amazon DOM price scrape end-to-end | PRICE-02 | Requires a real browser on a live Amazon product page | Run the bot on a real Amazon item, confirm a price row is recorded in price_history with the correct cents value |
| Live price-drop alert fan-out | PRICE-03 | Requires a real price drop + configured notifier channels | Set a target above current price, confirm a `price_drop` alert fans out once with current/target/pct payload |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
