---
phase: 35-audit-fixes-doc-hygiene-cleanup
verified: 2026-07-02T23:15:00Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
---

# Phase 35: Audit-Fixes & Doc-Hygiene Cleanup Verification Report

**Phase Goal:** The three outstanding low-severity audit warnings from the v4.1 close are resolved, and the v4.0/v4.1 planning-artifact frontmatter accurately reflects each phase's actual passing validation status.
**Verified:** 2026-07-02T23:15:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SSR items-table remove control removes an item independent of the JS `loadItems()` render path (AF-01) | VERIFIED | `web/templates/dashboard.html:94-97` renders a real `<form method="post" action="/items/remove">` with a hidden `link` input, unconditionally at page-render time (no JS listener gates it). `test_dashboard_ssr_remove_form_renders_independent_of_js` (test_web_dashboard.py:336) asserts the form is present and `class="btn-remove"` is gone. No JS `addEventListener` targets `.inline-remove-form` — confirmed by full grep of the inline `<script>` (only `#add-item-form` and `.btn-remove`'s former dynamic replacement listener at line 907 exist; neither intercepts this form). |
| 2 | `POST /items/remove` removes the posted item and redirects to a fresh dashboard (AF-01) | VERIFIED | `web/routes/pages.py:35-45`: `@router.post("/items/remove", dependencies=[Depends(check_origin)])` reads form data, calls `request.app.state.svc.remove_item(link)` for non-empty link, returns `RedirectResponse(url="/", status_code=303)`. `test_post_items_remove_form_calls_remove_item` (test_web_items.py:126) proves 303 + `Location: /` + `remove_item` called once with the raw link; `test_post_items_remove_form_empty_link_is_noop` proves the no-op path. |
| 3 | Cross-origin `POST /items/remove` is rejected (CSRF) (AF-01) | VERIFIED | Route is guarded by `Depends(check_origin)` (`web/security.py:34-55`), identical to every other mutating route. `test_csrf_rejected_items_remove` (test_web_security.py:82) asserts a `http://evil.com` origin returns 403 and `remove_item` is not called. |
| 4 | The dead `escHtml()` helper no longer exists anywhere in the dashboard frontend (AF-03) | VERIFIED | `grep -rn "escHtml" web/` returns 0 matches. `test_no_dead_eschtml_helper` (test_web_dashboard.py:356) is a permanent regression guard reading the template file and asserting the substring's absence. |
| 5 | Raw `last_heartbeat` absent from `get_status()['plugins'][name]` (AF-02) | VERIFIED | `core/health.py:91-93`: `get_snapshot()`'s public-dict comprehension excludes keys where `k.startswith("_")` OR `k == "last_heartbeat"`. `test_snapshot_excludes_last_heartbeat` (test_health.py:113) and `test_get_status_shape_with_registry` (test_service.py:83, explicit `assert "last_heartbeat" not in plugin_rec`) both confirm at the snapshot and service boundary. |
| 6 | Raw `last_heartbeat` absent from the SSE `"status"` frame (AF-02) | VERIFIED | `web/sse_hub.py` broadcasts `get_status()` verbatim (same dict, same fix applies atomically). `test_sse_status_frame_excludes_last_heartbeat` (test_sse.py:221) broadcasts a get_snapshot()-shaped payload through the real `_event_generator`/`SseHub` and asserts the serialized frame text lacks `last_heartbeat`. |
| 7 | `heartbeat_age_secs` still present on both surfaces (AF-02) | VERIFIED | Same tests as #5/#6 assert `heartbeat_age_secs` is present/not-None alongside the absence assertion; `core/health.py:94-97` derivation logic is untouched. |
| 8 | `shoppybot status` CLI table renders a real elapsed heartbeat age, no "never" regression (AF-02 lockstep) | VERIFIED | `core/cli/status.py:34` reads `rec['heartbeat_age_secs']` (not the removed raw field); `import time` and the orphaned `now = time.monotonic()` computation are both gone (grep-confirmed 0 matches for `last_heartbeat` in this file). `test_status_table` (test_cli_status.py:44) explicitly asserts `"never" not in out` for a heartbeating-plugin fixture supplying `heartbeat_age_secs: 5.3` — closes the exact stale-mock-masking trap RESEARCH.md flagged. |
| 9 | v4.1 VALIDATION.md (phases 25/26/27) reads `status: validated` + `wave_0_complete: true` (DH-01) | VERIFIED | Direct read of all 3 files' frontmatter: 25, 26, 27 all show `status: validated`, `wave_0_complete: true`, `nyquist_compliant: true` (unchanged, already correct). Backed by each phase's own suite-pass record (763/776/785 tests). |
| 10 | v4.0 VALIDATION.md (phases 18-24) reads `nyquist_compliant: true` (DH-03) | VERIFIED | Direct read of all 7 files: 18 through 24 all show `nyquist_compliant: true`; `status: draft` and `wave_0_complete: false` deliberately left untouched (narrower scope than DH-01, matches the plan's own constraint and v4.0-MILESTONE-AUDIT.md's explicit recommendation). |
| 11 | Phase 28 SUMMARY.md (28-01..04) carry `requirements:` whose union is exactly OBS-01/02/03/04/06/09 (DH-02) | VERIFIED | Direct grep: 28-01 `[OBS-01, OBS-03]`, 28-02 `[OBS-01, OBS-02, OBS-06]`, 28-03 `[OBS-01, OBS-02, OBS-03, OBS-09]`, 28-04 `[OBS-04, OBS-06]`. Set union = {OBS-01,02,03,04,06,09} — exactly the 6 target IDs. Phase 27/29 SUMMARY files also carry `requirements: [SSE-02]` / `[SSE-01]` respectively (discretionary polish honoring the literal "27/28/29" wording). |
| 12 | Every flipped flag reflects a suite that actually passed (no fabrication) | VERIFIED | Full suite re-run independently by this verifier (not taken from SUMMARY claims): `939 passed, 2 skipped` — matches the 35-02/35-03 SUMMARY.md's own claimed baseline exactly. DH evidence (763/776/785/755 historical suite-pass runs) is cited directly from each phase's own SUMMARY/VERIFICATION/MILESTONE-AUDIT documents per RESEARCH.md, not asserted from training knowledge. |
| 13 | Full test suite green, no regressions | VERIFIED | `.venv\Scripts\python.exe -m pytest -q` run directly by this verifier: `939 passed, 2 skipped, 14 warnings in 60.65s`. |

**Score:** 13/13 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `web/routes/pages.py` | Zero-JS `POST /items/remove` route guarded by `check_origin` | VERIFIED | Lines 35-45; `Depends(check_origin)`, form parsing, `svc.remove_item(link)`, 303 redirect |
| `web/templates/dashboard.html` | SSR remove control is a real HTML form POST; `escHtml()` removed | VERIFIED | Form at lines 94-97; `escHtml` grep-0 |
| `tests/test_web_items.py` | Functional test for form POST + no-op empty-link path | VERIFIED | 2 new tests, both pass |
| `tests/test_web_security.py` | Cross-origin 403 CSRF test for the new route | VERIFIED | `test_csrf_rejected_items_remove` passes |
| `tests/test_web_dashboard.py` | SSR-form assertion + escHtml grep-0 regression test | VERIFIED | Both tests present and passing |
| `core/health.py` | `get_snapshot()` excludes raw `last_heartbeat`, keeps `heartbeat_age_secs` | VERIFIED | Lines 91-97 |
| `core/cli/status.py` | Reads `heartbeat_age_secs`, no raw field, `import time` removed | VERIFIED | Line 34; grep-0 for `last_heartbeat`/`import time` |
| `tests/test_health.py`, `test_service.py`, `test_sse.py`, `test_orchestrator.py`, `test_cli_status.py`, `test_web_controls.py` | Absence/lockstep assertions on both public surfaces | VERIFIED | All present and passing |
| `.planning/milestones/v4.1-phases/{25,26,27}/{25,26,27}-VALIDATION.md` | `status: validated`, `wave_0_complete: true` | VERIFIED | Direct read confirms |
| `.planning/milestones/v4.0-phases/{18..24}/{18..24}-VALIDATION.md` | `nyquist_compliant: true` | VERIFIED | Direct read confirms, all 7 files |
| `.planning/milestones/v4.1-phases/28-.../28-{01..04}-SUMMARY.md` | `requirements:` union = 6 OBS IDs | VERIFIED | Direct read confirms |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `web/templates/dashboard.html` SSR form | `web/routes/pages.py POST /items/remove` | `action="/items/remove"` | WIRED | Form action matches route path exactly |
| `web/routes/pages.py POST /items/remove` | `core/service.py BotService.remove_item` | `request.app.state.svc.remove_item(link)` | WIRED | Confirmed by functional test asserting `mock_svc.remove_item.assert_called_once_with(...)` |
| `web/routes/pages.py POST /items/remove` | `web/security.py check_origin` | `Depends(check_origin)` | WIRED | Confirmed by cross-origin 403 test |
| `core/health.py get_snapshot()` | `BotService.get_status()` + `web/sse_hub.py` broadcast | single shaping boundary, passthrough | WIRED | Both surfaces proven clean by independent tests (test_service.py, test_sse.py) reading the same dict |
| `core/cli/status.py _format_status_table` | `get_status()['plugins'][name]['heartbeat_age_secs']` | direct dict read | WIRED | `test_status_table` asserts real age renders, not "never" |
| Phase 28 SUMMARY `requirements:` frontmatter | Milestone audit 3-source cross-reference | `requirements:` key read by audit tooling | WIRED | Union of the 4 files' lists verified programmatically to equal the 6 target OBS IDs; no milestone-audit re-run tool exists in the SDK, so verification is by direct set-union confirmation (documented limitation, consistent with 35-03-SUMMARY's own stated approach) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full regression suite | `.venv\Scripts\python.exe -m pytest -q` | `939 passed, 2 skipped, 14 warnings in 60.65s` | PASS |
| `escHtml` absent from `web/` | `grep -rn "escHtml" web/` | 0 matches | PASS |
| `last_heartbeat` absent from `core/cli/status.py` | `grep -n "last_heartbeat" core/cli/status.py` | 0 matches | PASS |
| `last_heartbeat` internal-only in `core/health.py` (state writes, not public surface) | `grep -n "last_heartbeat" core/health.py` | 3 matches, all internal (`_plugins` dict init/write, exclusion filter, internal read) | PASS (expected — internal state retained by design) |
| DH frontmatter direct reads (25/26/27, 18-24, 28-01..04) | `head`/`grep` on each target file | All match target values exactly | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|--------------|--------|----------|
| AF-01 | 35-01 | SSR remove works without JS | SATISFIED | Truths #1-3 |
| AF-02 | 35-02 | raw last_heartbeat absent from get_status + SSE | SATISFIED | Truths #5-8 |
| AF-03 | 35-01 | dead escHtml() removed | SATISFIED | Truth #4 |
| DH-01 | 35-03 | v4.1 VALIDATION 25/26/27 flags | SATISFIED | Truth #9 |
| DH-02 | 35-03 | Phase 28 SUMMARY requirements: → 6 OBS IDs VERIFIED | SATISFIED | Truth #11 |
| DH-03 | 35-03 | v4.0 VALIDATION 18-24 nyquist_compliant true | SATISFIED | Truth #10 |

No orphaned requirements — REQUIREMENTS.md's Phase 35 traceability table lists exactly AF-01/02/03, DH-01/02/03, all mapped to a plan's `requirements:` frontmatter, all marked `[x]` Complete.

### Anti-Patterns Found

None. Grep scan of all files modified by this phase (`web/routes/pages.py`, `web/templates/dashboard.html`, `core/health.py`, `core/cli/status.py`) for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` and informal stub phrasing (`placeholder`, `coming soon`, `not yet implemented`, `not available`) returned zero matches. No empty-implementation patterns (`return null`, `=> {}`, hardcoded-empty-props) found in the new route or the SSR form. Git working tree clean — all claimed commits (`b9454d7`, `8f704ff`, `9794a10`, `5e94f68`, `585484c`, `2143edc`, `0b81b04`, `66bf260`) present in `git log`.

### Human Verification Required

None required to reach `passed`. One optional supplementary check is available but not blocking:

**Note (not a gap):** `35-VALIDATION.md`'s own Manual-Only Verifications table lists an *optional* operator spot-check — disabling JS in a real browser, clicking Remove, and confirming the item disappears. This is explicitly marked optional in the phase's own validation strategy. The verifier judges this redundant with existing automated proof for the following reasons:
- FastAPI's `TestClient` (httpx-based) issues a real, unmodified HTTP POST with no JS execution at all — functionally equivalent to a JS-disabled browser's native form submission — and the functional test (`test_post_items_remove_form_calls_remove_item`) proves the full round trip (form submit → route → `remove_item` call → 303 redirect).
- The SSR-render test proves the `<form>` is present in the HTML unconditionally, with no JS gating its existence.
- A full grep of the dashboard's inline `<script>` confirms no `addEventListener` targets `.inline-remove-form` or intercepts its native submit behavior (no stray `preventDefault()` blocks it).
- This matches the project's own established pattern (per Phase 34's SUMMARY and prior MEMORY notes) of tracking live-environment browser confirmation as deferred operator UAT debt rather than a blocking gap, since the underlying mechanism is already proven end-to-end at the HTTP layer.

Recommended (non-blocking) manual spot-check for the operator's own confidence: disable JS in a browser, load the dashboard, click "Remove Item" on a tracked item, confirm the item is gone after the page reloads.

### Gaps Summary

No gaps. All 6 requirements (AF-01, AF-02, AF-03, DH-01, DH-02, DH-03) are code/test-verified against the live codebase, not just claimed in SUMMARY.md. The full regression suite (939 passed, 2 skipped) was re-run independently by this verifier and matches the executor's own claimed baseline. All DH frontmatter flips were confirmed by direct file reads, not trusted from SUMMARY prose. This is the final phase of the v4.2 Release Readiness milestone; all 20 milestone requirements are now code-complete.

---

_Verified: 2026-07-02T23:15:00Z_
_Verifier: Claude (gsd-verifier)_
