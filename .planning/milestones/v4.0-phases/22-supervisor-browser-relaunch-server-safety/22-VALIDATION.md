---
phase: 22
slug: supervisor-browser-relaunch-server-safety
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-12
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (asyncio_mode=auto) |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `pytest tests/test_supervisor.py tests/test_relaunch.py tests/test_orchestrator.py tests/test_signal_bridge.py` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~30-60 seconds |

---

## Sampling Rate

- **After every task commit:** Run touched test files
- **After every plan wave:** Run `pytest`
- **Before verify:** Full suite green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task | Requirement | Secure Behavior | Test Type | Command | Status |
|------|-------------|-----------------|-----------|---------|--------|
| supervise | REL-01 | one plugin raising Exception is absorbed; other plugins keep running (TaskGroup not cancelled); CancelledError still propagates | unit | `pytest tests/test_supervisor.py` | ⬜ pending |
| failure-budget | REL-02 | N failures (alert_on_errors) within window → plugin parked, no further restart, dispatcher notified | unit | `pytest tests/test_supervisor.py` | ⬜ pending |
| relaunch | REL-03 | relaunch() runs teardown→assign_proxy→setup(apply_stealth called)→restore_session→login in order; browser-dead exc triggers it | unit | `pytest tests/test_relaunch.py` | ⬜ pending |
| restore-stub | REL-03 | restore_session() no-op returns False; additive, PLUGIN_API_VERSION stays 2 | unit | `pytest tests/test_plugin_base.py` | ⬜ pending |
| read-isolation | REL-05 | sqlite3.OperationalError on a DB read → cycle skipped + logged, loop not crashed | unit | `pytest tests/test_orchestrator.py` | ⬜ pending |
| per-item-timeout | REL-06 | item check/buy under asyncio.timeout(item_timeout_secs); timeout → continue next item; write_queue.put outside timeout | unit | `pytest tests/test_orchestrator.py` | ⬜ pending |
| signal-bridge | SRV-02 | add_signal_handler (POSIX) / signal.signal (Windows) → cooperative teardown; NotImplementedError fallback exercised | unit | `pytest tests/test_signal_bridge.py` | ⬜ pending |
| queue-flush | SRV-02 | remaining write-queue items drained before teardown_all (manual drain, no join hang) | unit | `pytest tests/test_orchestrator.py` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_supervisor.py` — new: crash-isolation + failure-budget park + notify
- [ ] `tests/test_relaunch.py` — new: relaunch sequence order + apply_stealth + browser-dead detection
- [ ] `tests/test_signal_bridge.py` — new: POSIX/Windows signal → teardown
- [ ] Existing fake-plugin/fake-browser fixtures (conftest.py); a fake plugin that can be made to raise

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live supervisor restart + browser relaunch after a real Chrome crash | REL-01/REL-03 | Requires killing a live Chrome process mid-run | Deferred as UAT debt: run the bot, kill the Chrome process for one plugin, confirm that plugin relaunches (stealth re-applied, login re-run) and others keep polling |
| SIGTERM/SIGINT clean teardown on the target server OS | SRV-02 | Requires a real signal to a running process (container/systemd) | Deferred as UAT debt: send SIGTERM, confirm write-queue flushed + browsers torn down, no orphaned Chrome |

*All in-process behaviors have automated verification (with mocked browser-death exceptions and signals).*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
