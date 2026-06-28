---
phase: 28
slug: frontend-observability-surfaces
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-27
validated: 2026-06-27
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

| Requirement | Plans | Wave | Test Type | Automated Test | Status |
|-------------|-------|------|-----------|----------------|--------|
| OBS-01 (health card scaffold) | 28-01/02/03 | 0 | static scaffold | `test_dashboard_renders_health_section` | ✅ green |
| OBS-02 (heartbeat_age_secs backend) | 28-02/03 | 0 | unit | `test_heartbeat_age_secs_fresh` · `test_heartbeat_age_secs_never` | ✅ green |
| OBS-02 (snapshot key guard) | 28-02 | 0 | unit | `test_snapshot_public_keys_exact` | ✅ green |
| OBS-03 (orders-confirmed counter) | 28-01/03 | 0 | static scaffold | covered by `test_dashboard_renders_health_section` | ✅ green |
| OBS-04 (buys table scaffold) | 28-04 | 0 | static scaffold | `test_dashboard_renders_buys_section` | ✅ green |
| OBS-05 (uPlot assets present) | 28-04 | 0 | static scaffold | `test_uplot_script_and_css_present` | ✅ green |
| OBS-06 (log viewer scaffold) | 28-02/04 | 0 | static scaffold | `test_dashboard_renders_log_viewer_section` | ✅ green |
| OBS-07 (500-line DOM cap constant) | 28-03/04 | 0 | static scaffold | `test_log_dom_cap_constant` | ✅ green |
| OBS-08 (search wiring) | Phase 26 + UI | 0 | (server-side: Phase 26) | n/a — UI wiring only | ✅ green |
| OBS-09 (uptime header slot) | 28-03 | 0 | static scaffold | `test_header_uptime_slot_present` | ✅ green |
| XSS guard (all OBS) | 28-01..04 | 0 | regression | `test_no_innerHTML_with_api_data` | ✅ green |
| Design tokens (all OBS) | 28-01..04 | 0 | regression | `test_no_hardcoded_hex_in_components` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Full suite: 793 passed, 2 skipped (per 28-VERIFICATION.md, 2026-06-27).*

---

## Wave 0 Requirements

- [x] `tests/test_health.py` — ADD: `heartbeat_age_secs` present in `get_snapshot()` output;
      computed as `monotonic()-last_heartbeat` (monkeypatch `time.monotonic`); `None` when
      `last_heartbeat == 0.0` (never heartbeated). Update `test_snapshot_public_keys_exact`
      to include the new key. → `test_heartbeat_age_secs_fresh/_never`, `test_snapshot_public_keys_exact` PASS.
- [x] `tests/test_observability_ui.py` — NEW: static-scaffold assertions on the server-rendered
      `GET /` dashboard HTML via TestClient: the new sections exist
      (`#section-health`, `#section-buys`, `#section-log-viewer`), the `#header-uptime` slot exists,
      the level filter + search + Follow controls exist, and the uPlot `<script>`/`<link>` are present.
      → 6 tests PASS.
- [x] XSS regression: the existing `test_no_innerHTML_with_api_data` must still pass — new JS
      render functions use createElement/textContent, never innerHTML on API data. → PASS.

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

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (or are explicit manual-UAT)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none — all automatable behavior covered)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-06-27

---

## Validation Audit 2026-06-27

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

State A audit. VALIDATION.md was plan-time template (Per-Task Map unpopulated). Cross-referenced
all 9 OBS requirements against `28-VERIFICATION.md` (9/9 verified) and the live test suite.
Every automatable behavior already has a green test (`test_health.py`, `test_observability_ui.py`,
plus the `test_no_innerHTML_with_api_data` / `test_no_hardcoded_hex_in_components` regression guards).
No MISSING gaps → auditor not spawned, no new test files generated. The 5 outstanding items are
inherent manual-UAT (live-browser JS visuals: color bands, uPlot canvas, scroll-follow, runtime
DOM render) — tracked as UAT debt per the autonomous live-UAT policy, not automatable headless.
