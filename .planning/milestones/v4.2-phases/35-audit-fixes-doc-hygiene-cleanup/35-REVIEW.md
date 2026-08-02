---
phase: 35-audit-fixes-doc-hygiene-cleanup
reviewed: 2026-07-03T03:34:39Z
depth: deep
files_reviewed: 20
files_reviewed_list:
  - web/routes/pages.py
  - web/templates/dashboard.html
  - core/health.py
  - core/cli/status.py
  - tests/test_web_items.py
  - tests/test_web_security.py
  - tests/test_web_dashboard.py
  - tests/test_health.py
  - tests/test_cli_status.py
  - tests/test_service.py
  - tests/test_orchestrator.py
  - tests/test_sse.py
  - tests/test_web_controls.py
  - .planning/milestones/v4.0-phases/18-safety-gate-config-foundation/18-VALIDATION.md
  - .planning/milestones/v4.0-phases/19-db-schema-confirmation-detection/19-VALIDATION.md
  - .planning/milestones/v4.0-phases/20-checkout-profile-form-fill/20-VALIDATION.md
  - .planning/milestones/v4.0-phases/21-per-step-timeouts-unified-retry-cart-retry/21-VALIDATION.md
  - .planning/milestones/v4.0-phases/22-supervisor-browser-relaunch-server-safety/22-VALIDATION.md
  - .planning/milestones/v4.0-phases/23-encrypted-session-persistence/23-VALIDATION.md
  - .planning/milestones/v4.0-phases/24-health-surface-server-safety/24-VALIDATION.md
  - .planning/milestones/v4.1-phases/25-design-system/25-VALIDATION.md
  - .planning/milestones/v4.1-phases/26-read-only-api-endpoints/26-VALIDATION.md
  - .planning/milestones/v4.1-phases/27-sse-infrastructure/27-VALIDATION.md
  - .planning/milestones/v4.1-phases/27-sse-infrastructure/27-01-SUMMARY.md
  - .planning/milestones/v4.1-phases/27-sse-infrastructure/27-02-SUMMARY.md
  - .planning/milestones/v4.1-phases/27-sse-infrastructure/27-03-SUMMARY.md
  - .planning/milestones/v4.1-phases/28-frontend-observability-surfaces/28-01-SUMMARY.md
  - .planning/milestones/v4.1-phases/28-frontend-observability-surfaces/28-02-SUMMARY.md
  - .planning/milestones/v4.1-phases/28-frontend-observability-surfaces/28-03-SUMMARY.md
  - .planning/milestones/v4.1-phases/28-frontend-observability-surfaces/28-04-SUMMARY.md
  - .planning/milestones/v4.1-phases/29-sse-client-wiring/29-01-SUMMARY.md
  - .planning/milestones/v4.1-phases/29-sse-client-wiring/29-02-SUMMARY.md
  - .planning/milestones/v4.1-phases/29-sse-client-wiring/29-03-SUMMARY.md
findings:
  critical: 1
  warning: 0
  info: 2
  total: 3
status: resolved
resolution:
  date: 2026-07-02
  CR-01: resolved
  IN-01: acknowledged (intended AF-01 design, no action)
  IN-02: resolved
---

# Phase 35: Code Review Report

**Reviewed:** 2026-07-03T03:34:39Z
**Depth:** deep
**Files Reviewed:** 20 (code+tests) + 13 DH frontmatter files
**Status:** issues_found

## Summary

Reviewed AF-01 (`POST /items/remove`), AF-02 (`last_heartbeat` leak scrub), AF-03 (dead
`escHtml()` removal), and spot-checked the DH-01/02/03 frontmatter reconciliation. Traced
`web/routes/pages.py` -> `web/security.py::check_origin` -> `core/service.py::remove_item` ->
`models.py::remove_item_sync` -> `core/health.py::get_snapshot` -> `core/cli/status.py` and
`web/sse_hub.py`, cross-referenced every remaining `last_heartbeat`/`escHtml` reference in the
repo, and ran the full test suite (`939 passed, 2 skipped`) plus targeted exploit probes against
the new route.

**AF-01 (CSRF + input safety):** `check_origin` is correctly wired via `Depends()` and rejects
cross-origin POSTs (verified with a live repro, not just reading the test). The `link` field is
safely no-op'd when empty/missing, the DELETE is parameterized (`models.py:246`, no SQL
injection), and the redirect target is a hardcoded `"/"` (no open redirect). However, live probing
found a real crash: **posting `link` as a multipart file field instead of a plain text field
throws an unhandled `AttributeError` and returns a 500** — see CR-01. This is a genuine gap in
"does remove_item handle an arbitrary link safely (no crash)."

**AF-01 (graceful degradation):** Confirmed by tracing `loadItems()` (`dashboard.html:880-926`):
the `tbody.innerHTML = ''` wipe only happens *after* `await fetch(...)` and `await resp.json()`
both resolve successfully, and there is no `try/catch` around that fetch, so a genuine
`loadItems()` failure (network error, fetch rejection) leaves the SSR-rendered `<form>` rows
completely untouched. This matches the literal AF-01 requirement text ("graceful degradation if
the fetch fails"). Noted as IN-01 for future maintainers: on the *successful* JS path, `loadItems()`
still runs unconditionally on every page load and immediately replaces the SSR form with the old
JS-driven remove button (which POSTs `DELETE /api/items/{link_b64}` instead), so the SSR form is a
narrow fallback, not the steady-state UI — by design, but worth flagging as a quality note.

**AF-02:** `last_heartbeat` is stripped at the single `get_snapshot()` source
(`core/health.py:91-94`) and both downstream consumers were verified clean: `BotService.get_status()`
(`core/service.py:84`) calls `get_snapshot()` directly, and the SSE status frame
(`web/sse_hub.py` -> `svc.get_status()`) inherits the same clean shape — single source of truth,
no second leak path. `core/cli/status.py` lands the lockstep fix correctly: it now reads
`rec['heartbeat_age_secs']` guarded by an explicit `is not None` check (correctly handles the
`0.0`-age edge case, unlike the old truthy check), so a heartbeating plugin never renders "never."
Repo-wide grep confirms no other consumer of the raw field was missed.

**AF-03:** `escHtml` has zero remaining references anywhere under `web/` (grep-confirmed), and a
permanent regression test (`test_no_dead_eschtml_helper`) guards against reintroduction.

**DH (frontmatter):** All 20 changed `.planning/milestones/**` files are frontmatter-only diffs —
verified via `git diff`, no body-content lines touched. Spot-checked truthfulness: the
`nyquist_compliant: false -> true` flip for the 7 v4.0 phases is backed by
`v4.0-MILESTONE-AUDIT.md`'s own explicit recommendation; the `status: validated` /
`wave_0_complete: true` flips for phases 25/26/27 match the exact `763`/`776`/`785` full-suite
pass counts cited in each phase's own SUMMARY/VERIFICATION docs (grep-confirmed exact matches);
the Phase 28 `requirements:` unions (`OBS-01/02/03/04/06/09`) match exactly the OBS-IDs actually
referenced in each 28-0X-SUMMARY.md body. No fabrication found.

## Critical Issues

### CR-01: POST /items/remove crashes (500) on a non-string `link` form field

**File:** `web/routes/pages.py:41-44`
**Issue:** The route assumes `form.get("link")` is always `None` or a `str`:
```python
form = await request.form()
link = (form.get("link") or "").strip()
```
When a client sends the `link` field as a multipart *file* part (e.g. `files={'link': ('x.txt',
b'...', 'text/plain')}`) instead of a plain text field, Starlette's `FormData.get("link")` returns
an `UploadFile` object. Because `UploadFile` is truthy, `(form.get("link") or "")` evaluates to
the `UploadFile` itself, and `.strip()` then raises `AttributeError: 'UploadFile' object has no
attribute 'strip'`. This propagates as an unhandled exception through the ASGI stack, returning an
opaque `500 Internal Server Error` to the client. Reproduced live against the running app (not
just read from source):
```python
resp = client.post('/items/remove', files={'link': ('x.txt', b'not-a-real-link', 'text/plain')})
# -> 500 Internal Server Error
```
`check_origin` does not prevent this: the crash reproduces with **no `Origin` header at all**
(the same no-header pass-through condition legitimate same-origin browser form submissions rely
on), so any local process capable of sending an HTTP request to the dashboard port (curl, a
script, a misbehaving proxy) can trip this 500 with zero authentication. No data loss or injection
results (the parameterized `DELETE FROM items WHERE link=?` in `models.py:246` is never reached),
but it is an unhandled crash on externally-controlled input, which CLAUDE.md's "Validate all
external input server-side" and this review's own crash-classification rubric both treat as
Critical.
**Fix:** Validate the field is actually a string before calling `.strip()`:
```python
form = await request.form()
raw_link = form.get("link")
link = raw_link.strip() if isinstance(raw_link, str) else ""
if link:
    request.app.state.svc.remove_item(link)
return RedirectResponse(url="/", status_code=303)
```
Add a regression test mirroring `test_post_items_remove_form_empty_link_is_noop` that posts
`files={'link': (...)}` and asserts a 200/303 (not 500) with `remove_item` not called.

## Info

### IN-01: SSR remove form is a narrow fallback, not the steady-state UI (dual mutation pathways)

**File:** `web/templates/dashboard.html:94-97`, `:866-871`, `:880-926`
**Issue:** Two independent remove-item pathways now exist for the same table row: the SSR
`<form method="post" action="/items/remove">` (AF-01, hits `web/routes/pages.py`) and the original
JS `removeItem()` click handler (`dashboard.html:867-871`, hits `DELETE /api/items/{link_b64}` in
`web/routes/api.py`). `loadItems()` (called unconditionally on every page load, line 1072) always
wins the render race on any successful load and replaces the SSR rows — including the `<form>` —
with JS-rendered rows using the JS/DELETE pathway. The SSR form is therefore only ever "live" (a)
before the first `loadItems()` resolves, or (b) if `loadItems()`'s fetch genuinely fails. This
matches the literal AF-01 requirement text and is explicitly called out as an accepted, scoped
decision in `35-01-SUMMARY.md` ("No changes made to `loadItems()` itself — out of scope"). Flagging
only so a future engineer fixing a remove-item bug remembers there are two code paths
(`web/routes/pages.py::remove_item_form` and `web/routes/api.py::remove_item`) that must be kept
in sync, since a fix to one alone will silently miss the other.
**Fix:** No action required for this phase. Consider a follow-up note in `web/routes/api.py` and
`web/routes/pages.py` cross-referencing each other, or consolidating onto one code path in a
future phase if the duplication becomes a maintenance burden.

### IN-02: `.inline-remove-form` has no CSS rule

**File:** `web/templates/dashboard.html:94`
**Issue:** The new wrapper `<form class="inline-remove-form">` has no matching rule in
`web/static/dashboard.css` or `components.css` (grep-confirmed 0 matches). It renders with the
browser's default `<form>` block-level styling inside the table cell rather than any
project-defined inline layout. Purely cosmetic — no functional or accessibility impact observed —
but the class name implies a styling intent that was never implemented.
**Fix:** Either add a minimal `.inline-remove-form { display: inline; }` (or `contents`) rule to
`components.css` to match the previous bare-`<button>` layout, or drop the class if the default
rendering is visually acceptable (verify in-browser).

---

## Answers to explicit focus questions

- **Is `POST /items/remove` CSRF-protected + input-safe (no mass-delete/injection)?** CSRF: yes,
  `Depends(check_origin)` correctly rejects cross-origin requests (live-verified). Injection: yes,
  the DELETE is parameterized, and only ever deletes a row exactly matching the submitted `link`
  string (no wildcard/mass-delete surface — `link` column is unique by schema). Input-safe: **no**
  — CR-01 above shows an unhandled crash on a malformed (non-string) `link` field.
- **CLI lockstep correct (no "never")?** Yes — `core/cli/status.py` reads `heartbeat_age_secs` with
  an explicit `is not None` guard, verified by a live test assertion (`"never" not in out`) and
  code trace; the 0.0-age edge case is handled correctly (not misclassified as "never").
- **`last_heartbeat` gone from both surfaces?** Yes — stripped once at `get_snapshot()`
  (`core/health.py`), and both `get_status()` and the SSE status frame consume `get_snapshot()`
  directly; repo-wide grep found no other consumer.
- **`escHtml` fully gone?** Yes — zero references anywhere under `web/`, plus a permanent
  regression test.
- **DH frontmatter-only + truthful?** Yes — all 20 DH-touched files are frontmatter-only diffs
  (verified via `git diff`), and every flipped value cross-checked against its cited evidence
  (audit doc recommendation, exact SUMMARY/VERIFICATION test-count matches, exact OBS-ID unions)
  was found accurate with no fabrication.

---

## Resolution

**Resolved:** 2026-07-02

### CR-01: resolved

`POST /items/remove` now guards the form value with `isinstance(raw_link, str)`
before calling `.strip()`. A non-str `link` (e.g. a multipart file field, which
Starlette's `FormData.get()` returns as an `UploadFile`) is treated as empty
(no-op) instead of crashing; the route still returns its normal `303` redirect.
Valid link -> remove + 303, empty/missing link -> no-op + 303, and the existing
CSRF check (`check_origin`, cross-origin -> 403) are all unchanged. Covered by
`test_post_items_remove_form_file_link_no_crash` in `tests/test_web_items.py`
(TDD: written first, confirmed to reproduce the 500 against pre-fix code, then
confirmed green against the fix).

### IN-01: acknowledged (intended AF-01 design, no action)

Confirmed this is the documented, scoped behavior from `35-01-SUMMARY.md`
("No changes made to `loadItems()` itself — out of scope"): the SSR form is a
narrow fallback (pre-`loadItems()` paint, or fetch failure), not the
steady-state UI. No code change made. Left as a note for future maintainers
that `web/routes/pages.py::remove_item_form` and `web/routes/api.py::remove_item`
are two pathways that must be kept in sync.

### IN-02: resolved

Added a minimal `.inline-remove-form { display: inline; margin: 0; }` rule to
`web/static/components.css`, reusing the existing `.btn-text-destructive`
button styling/tokens (no new visual language introduced). Restores the prior
bare-button inline layout inside the table cell.

---

_Reviewed: 2026-07-03T03:34:39Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
