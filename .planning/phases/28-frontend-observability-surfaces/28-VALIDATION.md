---
phase: 28
slug: frontend-observability-surfaces
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-27
---

# Phase 28 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (TestClient for server-rendered scaffolding + backend; JS rendering is manual UAT) |
| **Config file** | pytest (project root) |
| **Quick run command** | `pytest tests/test_health.py tests/test_observability_ui.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the touched test file
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd:verify-work`:** Full suite green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| (populated during planning) | | | OBS-01..09 | unit + static scaffold | `pytest tests/test_health.py tests/test_observability_ui.py -q` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_health.py` — ADD: `heartbeat_age_secs` present in `get_snapshot()` output;
      computed as `monotonic()-last_heartbeat` (monkeypatch `time.monotonic`); `None` when
      `last_heartbeat == 0.0` (never heartbeated). Update `test_snapshot_public_keys_exact`
      to include the new key.
- [ ] `tests/test_observability_ui.py` — NEW: static-scaffold assertions on the server-rendered
      `GET /` dashboard HTML via TestClient: the new sections exist
      (`#section-health`, `#section-buys`, `#section-log-viewer`), the `#header-uptime` slot exists,
      the level filter + search + Follow controls exist, and the uPlot `<script>`/`<link>` are present.
- [ ] XSS regression: the existing `test_no_innerHTML_with_api_data` must still pass — new JS
      render functions use createElement/textContent, never innerHTML on API data.

*What is AUTOMATED: heartbeat_age_secs backend computation, snapshot-keys guard, static HTML
scaffolding presence, the no-innerHTML guard. What is MANUAL UAT: actual uPlot chart rendering,
empty-state message display, log-level color coding, Follow/pause-on-scroll behavior, and the
heartbeat color bands — these are JS-driven visual behaviors not assertable headless.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Health card color bands render (<30 green/30-60 amber/>60 red) | OBS-01/02 | JS + live status; visual | Run web mode with an active plugin; watch a card age through the bands |
| uPlot price chart renders; non-Amazon shows empty message | OBS-05 | Canvas render; visual | Open dashboard with an Amazon item (chart) and a non-Amazon item (empty message) |
| Log viewer color + level filter + Follow/pause-on-scroll + 500 cap | OBS-06/07 | JS scroll behavior; visual | Generate logs; filter by level; toggle Follow; scroll up (pauses); confirm ≤500 lines |
| Confirmed-buys table populates / empty row | OBS-04 | JS fetch render | Dashboard with and without confirmed orders |
| Uptime appears in header | OBS-09 | JS fetch render | Start bot; confirm header shows humanized uptime |

*Backend + static scaffolding are automated; the JS-rendered visuals are operator UAT (deferred
as UAT debt per the autonomous live-UAT policy).*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (or are explicit manual-UAT)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
