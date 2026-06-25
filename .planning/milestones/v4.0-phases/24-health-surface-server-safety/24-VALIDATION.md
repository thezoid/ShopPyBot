---
phase: 24
slug: health-surface-server-safety
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-12
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (asyncio_mode=auto) |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `pytest tests/test_health.py tests/test_cli_status.py tests/test_service.py tests/test_utils_audio.py` |
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
| health-registry | REL-07 | HealthRegistry record/read: heartbeat, consecutive_errors, items_checked, orders_confirmed, status transitions; snapshot is JSON-safe | unit | `pytest tests/test_health.py` | ⬜ pending |
| get-status | REL-07 | get_status() returns {running, uptime_secs, plugins:{name:{status,last_heartbeat,consecutive_errors,items_checked,orders_confirmed}}}; cheap/non-blocking | unit | `pytest tests/test_service.py` | ⬜ pending |
| orchestrator-hooks | REL-07 | run_plugin bumps heartbeat+items_checked; supervise sets status; orders_confirmed on confirmed order | unit | `pytest tests/test_supervisor.py tests/test_orchestrator.py` | ⬜ pending |
| health-degraded | REL-07 | fires ONCE when consecutive_errors crosses threshold (armed); re-arms on recovery; distinct from parked; via dispatcher | unit | `pytest tests/test_health.py tests/test_supervisor.py` | ⬜ pending |
| cli-status | REL-07 | shoppybot status prints per-plugin table; --json raw; no network | unit | `pytest tests/test_cli_status.py` | ⬜ pending |
| pygame-guard | SRV-01 | import succeeds when mixer.init raises pygame.error; play_sound no-ops silently when _AUDIO_AVAILABLE False | unit | `pytest tests/test_utils_audio.py` | ⬜ pending |
| status-json | REL-07 | get_status() dict JSON-serializes (web /status) | unit | `pytest tests/test_service.py` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_health.py` — new: HealthRegistry + health_degraded fire-once/rearm
- [ ] `tests/test_cli_status.py` — new: status table + --json (mirror test_cli_plugins.py)
- [ ] `tests/test_utils_audio.py` — new: pygame guard (mock mixer.init raising pygame.error → import ok, play no-op)
- [ ] Existing service/orchestrator/supervisor test fixtures (conftest.py)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Headless server run with no audio device | SRV-01 | Requires a real no-audio host (CI/server) to confirm pygame degrades to no-op and the bot runs unattended | Deferred as UAT debt: run on a headless host with no audio; confirm import + run succeed, no pygame crash, alerts log instead of play |

*All in-process behaviors have automated verification (mock pygame.error, mock plugin health).*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
