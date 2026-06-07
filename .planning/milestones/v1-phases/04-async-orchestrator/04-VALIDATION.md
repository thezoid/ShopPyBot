---
phase: 4
slug: async-orchestrator
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-03
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.4 + pytest-asyncio 1.3.0 (asyncio_mode=auto) |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/Scripts/python.exe -m pytest tests/ -q` |
| **Full suite command** | `.venv/Scripts/python.exe -m pytest tests/ -q` |
| **Estimated runtime** | ~3s unit; concurrency/lock checks use short simulated runs, not the 60-min live soak |

## Sampling Rate

- After every task commit: quick run
- After every wave: full suite
- Before verify-work: full suite green
- Max feedback latency: ~5s

## Per-Requirement Verification Map

| Requirement | Test Type | Approach | Live? |
|-------------|-----------|----------|-------|
| ASYNC-01 (TaskGroup concurrency) | unit + manual | Unit: orchestrator runs N fake-plugin coroutines concurrently (assert overlapping start order, not serial); manual: live 2-platform run shows interleaved log timestamps | partial |
| ASYNC-02 (1.5s startup stagger) | unit | Assert orchestrator awaits >=1.5s between successive plugin setup() calls (patch sleep, assert call spacing/order) | no |
| ASYNC-03 (no input(), asyncio.Event) | unit + static | `grep -rn "input(" plugins/ core/ main.py` returns no async-path hits; unit: a paused plugin resumes when its Event is set by the listener shim | no |
| ASYNC-04 (WAL + busy_timeout + ctx mgrs) | unit | Assert connection PRAGMAs (journal_mode=wal, busy_timeout=5000); assert connections opened via context manager; grep no leaked connect() without `with` | no |
| ASYNC-05 (single write queue) | unit | Enqueue many concurrent update_item_purchased requests; assert the single writer task serializes them and all succeed | no (simulated) |
| SC4 (zero "database is locked", 60+ min) | manual/stress | Short parallel-write stress test (many concurrent writers in a loop) as a proxy; full 60-min soak is manual | partial |

## Wave 0 Requirements

- [ ] `tests/conftest.py` — add a fake-plugin fixture (async, configurable check/buy results) + a fake stdin/Event shim for the listener.
- [ ] Confirm `pytest-asyncio` async fixtures work (already used in Phase 2; add to requirements.txt if missing per research Open Question 3).
- [ ] `poll_interval` config: add `poll_interval: int = 30` to AppConfig (research Open Question 1) — covered by a config-schema test.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Instructions |
|----------|-------------|------------|--------------|
| Overlapping live polling of 2 platforms | SC1 | Needs 2 live browsers | Run with Amazon+BestBuy items; confirm interleaved check log timestamps |
| 3+ plugin startup with no port conflict | SC2 | Needs 3 live browsers | Configure 3 plugins; confirm staggered driver-init logs >=1.5s apart, no CDP port error |
| 60+ min zero-lock soak | SC4 | Long duration | Run 2 platforms 60+ min; grep logs for "database is locked" (expect none) |
| CAPTCHA Event resolution | ASYNC-03 | Live CAPTCHA + Enter | Trigger CAPTCHA; confirm alert + only that plugin pauses; Enter resumes it |

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependency
- [ ] No 3 consecutive tasks without automated verify
- [ ] Wave 0 covers fake-plugin + Event + poll_interval
- [ ] No watch-mode flags
- [ ] nyquist_compliant: true set when complete

**Approval:** pending
