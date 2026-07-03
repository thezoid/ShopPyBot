# Phase 35: Audit-Fixes & Doc-Hygiene Cleanup - Research

**Researched:** 2026-07-02
**Domain:** FastAPI/Jinja2 SSR graceful degradation, in-process health-state surface hygiene, dead-code removal, GSD planning-artifact frontmatter reconciliation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**AF-01 SSR remove-button graceful degradation**
- The dashboard SSR items-table remove button must remove an item even when the JS `loadItems()` fetch/render path fails. **Mechanism (Claude's discretion):** make the SSR-rendered remove action a real server-side action (an HTML form POST to a remove route, or a link that hits a remove endpoint) so it works without the JS render path, degrading gracefully. **RESEARCH:** locate the current SSR items-table + remove button + the JS loadItems() path; determine whether a remove endpoint already exists to POST to, or one must be added (prefer reusing an existing remove route). Zero-Node.
- **Test:** simulate a failed `loadItems()` fetch and confirm the SSR-rendered remove action still functions (removes the item).

**AF-02 remove raw last_heartbeat**
- `get_status()` and the SSE status frames must NOT contain the raw `last_heartbeat` monotonic float; only the derived `heartbeat_age_secs` (already computed in v4.1 Phase 28-02). **RESEARCH:** find where `last_heartbeat` is put into the get_status() dict / status payload and remove it, keeping `heartbeat_age_secs`. Confirm nothing downstream (dashboard JS, SSE consumers) depends on the raw field.
- **Test:** assert the raw `last_heartbeat` field is ABSENT from both the get_status() output and the SSE status frame; `heartbeat_age_secs` still present.

**AF-03 remove dead escHtml()**
- Delete the dead `escHtml()` helper from the dashboard frontend source. **RESEARCH:** confirm it is genuinely dead (zero call sites) before removing. **Test/verify:** grep confirms `escHtml` no longer exists anywhere in the dashboard frontend.

**DH-01/02/03 frontmatter reconciliation (mechanical, MUST reflect actual status)**
- **DH-01:** v4.1 VALIDATION.md frontmatter for phases 25/26/27 → `status: validated`, `wave_0_complete: true`.
- **DH-02:** v4.1 SUMMARY.md frontmatter for phases 27/28/29 → add `requirements:` listing the phase's requirement IDs so the audit 3-source cross-reference reports OBS-01/02/03/04/06/09 as VERIFIED.
- **DH-03:** v4.0 VALIDATION.md `nyquist_compliant` → `true` for phases 18-24.
- **HARD CONSTRAINT:** these flags may only be flipped to reflect what ACTUALLY passed. **RESEARCH/VERIFY:** confirm each phase's suite actually passed (the milestone history + green test suites indicate they did) before flipping. Do NOT fabricate — the frontmatter merely lagged the real passing status. If any phase did NOT actually pass, leave its flag and flag the discrepancy.
- **RESEARCH:** locate the exact file paths (these v4.0/v4.1 artifacts may live under `.planning/phases/` or an archived milestones directory) and the exact requirement IDs to add for DH-02.

### Claude's Discretion
- AF-01 mechanism: HTML form POST vs. link-to-GET-endpoint. **Research recommendation: HTML form POST** (see Architecture Patterns).
- Exact wording/placement of any code comments explaining the fixes.

### Deferred Ideas (OUT OF SCOPE)
- Broader doc overhaul beyond the specified frontmatter reconciliation.
- Rewriting historical planning-artifact bodies.
- STATE.md schema drift (custom `Last action`/`Next action` fields not SDK-verb-parseable) — surfaced in CONTEXT.md as "worth surfacing, not necessarily in scope"; NOT touched by this research's recommendations (see Open Questions).
- Stale project `CLAUDE.md` architecture section (still describes pre-refactor `amazon_bot.py`/`bestbuy_bot.py`) — same treatment, NOT touched (see Open Questions).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AF-01 | Dashboard SSR items-table remove buttons remove an item without depending on the JS `loadItems()` render path | Exact dead-button location identified (`web/templates/dashboard.html:93-96`); confirmed no zero-JS remove route exists; new `POST /items/remove` route designed with exact file/line targets and CSRF pattern to reuse |
| AF-02 | `get_status()` and SSE status frames no longer expose the raw `last_heartbeat` monotonic float | Single source-of-truth fix site identified (`core/health.py:91`); both consumer surfaces confirmed to share this one payload; CLI regression risk found and mitigated (`core/cli/status.py:36`); full consumer/test inventory enumerated |
| AF-03 | The dead `escHtml()` helper is removed from the dashboard frontend | Confirmed zero call sites via full-`web/` grep; exact deletion lines identified (`dashboard.html:871-876`) |
| DH-01 | v4.1 VALIDATION.md status/wave frontmatter (phases 25/26/27) reconciled | Exact file paths + current frontmatter read; suite-pass evidence cited per phase (763/776/785 tests green) |
| DH-02 | v4.1 SUMMARY.md `requirements:` frontmatter added (phases 27/28/29) so OBS-01/02/03/04/06/09 report VERIFIED | Audit's own cross-reference table shows the real gap is 100% Phase 28 (28-01..28-04 SUMMARY.md); exact per-plan requirement-ID mapping sourced from `28-VERIFICATION.md`; discrepancy vs. CONTEXT.md's literal "27/28/29" phrasing flagged as an Open Question |
| DH-03 | v4.0 phase VALIDATION.md `nyquist_compliant` flags set true (phases 18-24) | All 7 files' current frontmatter confirmed `false`; v4.0-MILESTONE-AUDIT.md itself explicitly recommends this exact flip with suite-pass evidence (755 tests green) |
</phase_requirements>

## Summary

This is a mechanical cleanup phase touching six independent, low-risk items: three code-level audit-warning fixes (AF-01/02/03) and three planning-artifact frontmatter reconciliations (DH-01/02/03). No new dependencies, no architectural changes, no new endpoints beyond one small zero-JS form-POST route.

All three AF items were fully traced to exact file:line locations. AF-01's dead SSR remove button (`dashboard.html:93-96`, class `btn-remove`, no listener anywhere in the inline `<script>`) needs a real HTML-form-based remove path since HTML forms cannot issue `DELETE` (the existing route is `DELETE /api/items/{link_b64}`, JS-only). AF-02's raw `last_heartbeat` leak has exactly ONE source (`core/health.py:91`, `HealthRegistry.get_snapshot()`'s public-key filter) that feeds BOTH `get_status()` and the SSE status frame identically (`web/sse_hub.py:97-98` broadcasts `svc.get_status()` verbatim) — but research surfaced a real regression risk not mentioned in CONTEXT.md: `core/cli/status.py:36` reads the raw field directly and will silently degrade to always showing "never" once it disappears, unless also updated to read `heartbeat_age_secs`. AF-03's `escHtml()` (`dashboard.html:871-876`) is confirmed to have zero call sites anywhere in `web/`.

All three DH items were verified against real frontmatter and real suite-pass evidence (never fabricated): DH-01's three phases (25/26/27) show green full-suite runs (763/776/785 passed) in their own SUMMARY.md/VERIFICATION.md files. DH-03's evidence is the strongest of all six items — the v4.0 milestone's own published audit document explicitly states the flag lag is cosmetic and recommends the exact flip this phase performs, citing a 755-passed full-suite run. DH-02 surfaced an important scope discrepancy: CONTEXT.md/REQUIREMENTS.md say "phases 27/28/29," but the v4.1 audit's own Requirements Coverage table shows all six target requirement IDs (OBS-01/02/03/04/06/09) belong exclusively to Phase 28 — Phase 27 and 29 already register "yes" in the audit via Phase 29.1's summaries. This is flagged as an Open Question with a recommended minimal-and-correct fix scope.

**Primary recommendation:** Fix AF-01/02/03 as isolated, independently-testable code changes reusing existing patterns (`check_origin` CSRF dependency, `HealthRegistry` snapshot filter, static grep-0 regression tests). For DH-01/02/03, edit ONLY the specific frontmatter keys named in each locked decision — leave every artifact body untouched — and treat DH-02's phase scope as Phase 28 (required) with 27/29 mirroring as optional discretionary polish, per the Open Questions section.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SSR remove-button graceful degradation (AF-01) | Frontend Server (SSR / Jinja2) | API / Backend (new route) | The fix is a server-rendered HTML form posting to a new backend mutation route; no browser-only JS logic is added |
| Zero-JS remove mutation | API / Backend | — | `POST /items/remove` is a state-changing route, same tier as the existing `DELETE /api/items/{link_b64}` |
| Raw heartbeat float scrub (AF-02) | API / Backend | — | `HealthRegistry.get_snapshot()` is the single backend data-shaping boundary consumed by both the REST `get_status()` route and the SSE producer; fixing it there fixes both surfaces atomically |
| CLI status table rendering | CLI (separate presentation layer) | — | `core/cli/status.py` independently formats the SAME `get_status()` dict for a terminal table; must be updated in lockstep with the AF-02 backend change or it silently regresses |
| Dead JS helper removal (AF-03) | Browser / Client | — | `escHtml()` lives entirely in the inline `<script>` of `dashboard.html`; pure client-side dead code |
| Planning-artifact frontmatter (DH-01/02/03) | N/A (docs, not runtime tiers) | — | `.planning/` YAML frontmatter is build/process metadata, not part of the running application in any tier |

## Project Constraints (from CLAUDE.md)

Two CLAUDE.md files govern this repo: the project's own `E:\repos\ShopPyBot\CLAUDE.md` and the user's global `C:\Users\brand\.claude\CLAUDE.md`. Directives relevant to this phase:

- **Approval gates:** Global CLAUDE.md requires showing a files table + commit message + explicit "yes" before any `git commit`/`push`. The phase orchestrator (not this research agent) owns commits; this RESEARCH.md itself will be committed by the orchestrator per the standard GSD flow — no additional gate needed here, but the **executor** must respect the gate for AF/DH code commits if running interactively (the project's `MEMORY.md` autonomous-commit override applies for autonomous GSD runs).
- **Never push directly; never mention Claude as a contributor.** Applies to all commits this phase produces.
- **No em dashes, no horizontal rules, no emojis** in any output/commit messages/docs produced by this phase's execution.
- **Naming:** camelCase for JS variables/functions (already followed in `dashboard.html`); Python files in this repo use snake_case per existing convention (`core/health.py`, `core/cli/status.py`) — follow existing per-language convention, not a blanket camelCase rule.
- **Functions under 30 lines, files under 300 lines, nesting depth max 3.** The new `POST /items/remove` route handler must stay small (existing routes in `web/routes/api.py` are 5-15 lines each — match that).
- **Do not add dependencies unless necessary.** This phase adds zero new dependencies (no new packages needed for any of the six items).
- **Validate all external input server-side.** The new `POST /items/remove` route must validate/guard the `link` form field the same way `DELETE /api/items/{link_b64}` and `POST /api/items` already do (reuse `check_origin` CSRF Depends; treat missing/empty `link` as a no-op or 422, matching `add_item`'s validation style).
- **Only do what is explicitly requested. Do not expand scope.** DH-02's phase-list discrepancy and the STATE.md/CLAUDE.md drift noted in CONTEXT.md's `<specifics>` are surfaced as Open Questions, NOT auto-fixed, per this rule.
- **Never rewrite history / never force-push.** Not applicable here (no destructive git operations needed), but stated for completeness given DH work touches many files across `.planning/`.
- Project's own `CLAUDE.md` documents a pre-refactor `amazon_bot.py`/`bestbuy_bot.py` architecture that no longer matches the current plugin-based codebase (confirmed stale — the live code uses `plugins/` + `core/orchestrator.py`, not `amazon_bot.py`). This is flagged per CONTEXT.md's request but is explicitly OUT of this phase's scope (see Open Questions).

## Standard Stack

No new libraries, frameworks, or dependencies are required for any of the six requirements. This phase exclusively modifies existing first-party code (`core/health.py`, `core/cli/status.py`, `web/routes/pages.py`, `web/templates/dashboard.html`) and existing planning-artifact YAML frontmatter. `pyproject.toml`/`requirements.txt` are untouched.

### Alternatives Considered (AF-01 mechanism only)

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| HTML `<form method="post">` to a new backend route | A plain `<a href="/items/remove?link=...">` GET link | GET-triggered mutations violate HTTP semantics (GET must be safe/idempotent-cacheable) and are prefetch/crawler-unsafe; rejected |
| A new dedicated `POST /items/remove` route | Reusing the existing `DELETE /api/items/{link_b64}` route | HTML forms only support `GET`/`POST` natively — cannot target a `DELETE` route without JS (`fetch`/XHR), which defeats the entire purpose of AF-01's graceful-degradation requirement; a new POST route is required |
| Redirect-after-POST (303) | Re-render the dashboard template directly from the POST handler | 303-redirect-to-GET is the standard POST/Redirect/GET pattern (avoids form-resubmission-on-refresh warnings); matches user expectation of "click remove, land back on a fresh dashboard" |

## Package Legitimacy Audit

**Not applicable.** This phase installs zero external packages (confirmed: no new imports beyond stdlib/already-present `fastapi`/`starlette` symbols already used elsewhere in `web/routes/`). The Package Legitimacy Gate protocol is skipped per its own "whenever this phase installs external packages" trigger condition — it does not apply here.

## Architecture Patterns

### System Architecture Diagram (AF-01 + AF-02 data flow)

```
Browser (no JS / JS-failed)                Browser (JS working)
        |                                          |
        v                                          v
  <form method="post"                    fetch DELETE /api/items/{b64}
   action="/items/remove">                         |
        |                                          v
        v                                   removeItem(link) in dashboard.html
  POST /items/remove  <-- NEW (AF-01)              |
   (web/routes/pages.py)                           v
        |                                   DELETE /api/items/{link_b64}
        v                                   (web/routes/api.py:139-147, existing)
  check_origin() CSRF guard                        |
        |                                          v
        v                                   svc.remove_item(link)
  svc.remove_item(link)  <---------------- (core/service.py:185, SAME call both paths)
        |
        v
  RedirectResponse("/", 303)
        |
        v
  Browser re-GETs "/" -> fresh SSR render (item gone)


Health/status data flow (AF-02):

  HealthRegistry._plugins[name]["last_heartbeat"]   (internal state, monotonic float, UNCHANGED)
        |
        v
  HealthRegistry.get_snapshot()  <-- FIX HERE (core/health.py:91)
        |  strips "_"-prefixed keys AND now also strips "last_heartbeat"
        |  still computes+keeps "heartbeat_age_secs" (unchanged, core/health.py:92-95)
        v
  BotService.get_status()["plugins"]  (core/service.py:84, passthrough, no change needed)
        |
        +----------------------------------+
        v                                  v
  GET /api/status (JSON, web/routes/api.py:36)   _poll_loop -> hub.broadcast("status", status)
        |                                  (web/sse_hub.py:97-98, SAME dict object, no change needed)
        v                                  v
  dashboard.html JS reads only              GET /api/events SSE "status" frame
  rec.heartbeat_age_secs (already,          (web/routes/sse.py, same payload serialized)
  lines 307-308 -- no change needed)

  SEPARATE CONSUMER (not part of the above chain, must be updated in lockstep):
  core/cli/status.py:36 reads rec['last_heartbeat'] directly from the SAME
  BotService.get_status()["plugins"] dict for the `shoppybot status` text table.
  MUST switch to rec['heartbeat_age_secs'] or the CLI silently shows "never" always.
```

### Recommended Project Structure

No new files/folders needed. All edits land in existing files:

```
core/
├── health.py              # AF-02: get_snapshot() public-key filter (line 91)
└── cli/
    └── status.py           # AF-02: _format_status_table() heartbeat column (line 36)
web/
├── routes/
│   └── pages.py            # AF-01: new POST /items/remove route
└── templates/
    └── dashboard.html      # AF-01: SSR remove button -> form; AF-03: delete escHtml()
tests/
├── test_web_dashboard.py   # AF-01 SSR-form assertion; AF-03 grep-0 regression test
├── test_web_items.py       # AF-01 POST /items/remove functional test
├── test_web_security.py    # AF-01 CSRF-rejection test for the new route
├── test_health.py          # AF-02 snapshot-key tests (2 updates + 1 new)
├── test_sse.py              # AF-02 new SSE-frame absence test
├── test_service.py          # AF-02 get_status() shape test update
├── test_orchestrator.py     # AF-02 assertion update
├── test_cli_status.py       # AF-02 fixture + CLI-table assertion update
└── test_web_controls.py     # AF-02 fixture cleanup (optional, non-breaking)
```

### Pattern 1: Zero-JS mutation route (AF-01)

**What:** A `POST` route outside the `/api/*` JSON surface that accepts `application/x-www-form-urlencoded` form data and returns an HTTP redirect, matching how the rest of the app structures its two route "tiers" (`web/routes/api.py` = JSON-only per its own docstring; `web/routes/pages.py` = the one router registered WITHOUT the `/api` prefix in `web/__init__.py:66-70`, making it the natural home for an HTML-form-target route).

**When to use:** Any time a feature must work with JavaScript disabled or after a fetch failure — the graceful-degradation pattern this codebase already partially uses (SSR item rows render server-side first; JS enhances afterward via `loadItems()`).

**Example:**
```python
# Source: web/routes/pages.py (existing file, add alongside the "/" route)
from fastapi.responses import RedirectResponse
from web.security import check_origin
from fastapi import Depends

@router.post("/items/remove", dependencies=[Depends(check_origin)])
async def remove_item_form(request: Request):
    """Zero-JS SSR remove action (AF-01): HTML forms cannot issue DELETE,
    so this POST route mirrors DELETE /api/items/{link_b64}'s effect via
    the same BotService.remove_item() call, then redirects back to '/'.
    """
    form = await request.form()
    link = (form.get("link") or "").strip()
    if link:
        request.app.state.svc.remove_item(link)
    return RedirectResponse(url="/", status_code=303)
```

```html
<!-- Source: web/templates/dashboard.html -- replaces the dead button at lines 93-96 -->
<td>
  <form method="post" action="/items/remove" class="inline-remove-form">
    <input type="hidden" name="link" value="{{ item[1] }}">
    <button class="btn-text-destructive" type="submit">Remove Item</button>
  </form>
</td>
```

Note: `loadItems()` (dashboard.html:885-931) unconditionally runs on page load and, on fetch SUCCESS, replaces `#items-tbody` with its own JS-rendered rows (which use the existing `fetch(... DELETE ...)` path via `removeItem()`). This is intentional layered enhancement: the SSR form-based row is what's visible and functional the instant the page loads or whenever `loadItems()`'s `fetch()` call itself throws (network failure) — `loadItems()` has no try/catch around its initial `await fetch(...)`, so a genuine fetch rejection leaves the SSR tbody (and its working `<form>`) untouched. See Pitfall 1 for the narrower case (non-2xx JSON response) that is NOT covered by this and is out of AF-01's stated scope.

### Pattern 2: Single-source health snapshot filtering (AF-02)

**What:** `HealthRegistry.get_snapshot()` (`core/health.py:78-97`) is the ONE place that shapes the public/browser-facing per-plugin dict from the internal `_plugins` store. Both `BotService.get_status()` (`core/service.py:84`, direct passthrough) and the SSE producer (`web/sse_hub.py:97-98`, broadcasts the SAME `get_status()` dict verbatim as the `"status"` event) consume this one shaped dict — there is no route-level or SSE-level reshaping anywhere. This is the credential-scrub pattern already established for `last_error` (`core/health.py:43-47`, "SSE-03: store the exception CLASS NAME only... never str(exc)").

**When to use:** Any time a field must be excluded from (or transformed for) every browser-facing surface at once — filter once at the `get_snapshot()` boundary, not per-route.

**Example:**
```python
# Source: core/health.py:88-97 (current) -> fix
def get_snapshot(self) -> dict[str, dict]:
    now = time.monotonic()
    result = {}
    for name, rec in self._plugins.items():
        public = {
            k: v for k, v in rec.items()
            if not k.startswith("_") and k != "last_heartbeat"   # AF-02: exclude raw float
        }
        lhb = rec["last_heartbeat"]   # internal read only, never re-added to `public`
        public["heartbeat_age_secs"] = (
            None if lhb == 0.0 else round(now - lhb, 1)
        )
        result[name] = public
    return result
```

```python
# Source: core/cli/status.py:30-42 (current) -> fix (AF-02 lockstep consumer update)
# BEFORE (line 36):
    (f"{now - rec['last_heartbeat']:.1f}s ago" if rec.get("last_heartbeat", 0.0) > 0.0 else "never"),
# AFTER:
    (f"{rec['heartbeat_age_secs']}s ago" if rec.get("heartbeat_age_secs") is not None else "never"),
```
The `now = time.monotonic()` computation (line 31) and its only use-site (former line 36) both go away together; `import time` (line 13) becomes unused and must be removed too (its ONLY use in the file was this computation).

### Anti-Patterns to Avoid
- **Re-filtering `last_heartbeat` at each route/consumer instead of the single `get_snapshot()` source:** would require three separate edits (REST route, SSE producer, CLI) instead of one, and risks the exact "one surface fixed, another still leaks" bug this audit warning already describes.
- **Deleting `escHtml()`'s surrounding comment but leaving the function, or vice versa:** the comment at `dashboard.html:871` explicitly documents the function as unused; both lines 871-876 form one atomic dead-code block and should be removed together.
- **Using a GET link for the remove action:** violates HTTP method safety semantics (browser prefetching / crawlers could trigger deletions); use POST.
- **Rewriting VALIDATION.md/SUMMARY.md body prose while touching frontmatter:** the HARD CONSTRAINT and CONTEXT.md's deferred-scope note both explicitly forbid this — frontmatter keys only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSRF protection for the new POST route | A new origin-check mechanism | `web.security.check_origin` via `Depends(check_origin)` | Already implements the exact localhost-aware, non-local-bind-aware origin allowlist logic (`web/security.py:34-55`) that every other mutating route (`add_item`, `remove_item`, `bot_start`, `bot_stop`) already uses; proven by `tests/test_web_security.py` |
| Post-redirect response | Manually setting `Response(status_code=303, headers={"Location": "/"})` | `fastapi.responses.RedirectResponse(url="/", status_code=303)` | Standard FastAPI/Starlette helper already imported elsewhere in the codebase's route modules (`JSONResponse` pattern is identical) |
| Item removal logic | Direct SQL/`models.remove_item_sync` call from the route | `request.app.state.svc.remove_item(link)` (existing `BotService` method, `core/service.py:185`) | MOD-02 architectural rule (already enforced by `tests/test_web_mod02.py`): web routes never import `models` directly, only `BotService` |
| Heartbeat staleness math | A new "age" computation in the CLI or a new route | The already-derived `heartbeat_age_secs` (`core/health.py:92-95`, added in v4.1 Phase 28-02) | It is the exact value AF-02 says to KEEP; recomputing it elsewhere would duplicate the `time.monotonic()` delta logic that already exists in one place |

**Key insight:** Every one of AF-01/02/03's fixes is a "use the pattern that already exists elsewhere in this codebase" fix, not a new pattern. This phase should introduce zero new architectural concepts.

## Common Pitfalls

### Pitfall 1: `loadItems()` non-2xx-but-valid-JSON response still wipes the SSR tbody
**What goes wrong:** `loadItems()` (`dashboard.html:885-896`) has no try/catch. A genuine network failure (fetch() promise rejection) throws before `tbody.innerHTML = ''` executes, so the SSR-rendered rows (including the new form-based remove button) survive untouched — this is the exact scenario AF-01's "simulate a failed loadItems() fetch" test should target. However, if the fetch SUCCEEDS with a non-2xx status but a parseable JSON body, `resp.json()` does not throw, and execution proceeds to `tbody.innerHTML = ''`, wiping the SSR rows even though no real data arrived (falls through to the "No items tracked yet" empty-state branch).
**Why it happens:** The function was never written with a try/catch; this predates Phase 35 and is not one of the three audit warnings.
**How to avoid:** Design the AF-01 test around a true `fetch()` rejection (the audit's own wording: "graceful-degradation gap... dead if `loadItems()` fetch fails" — matches this case exactly), not a non-2xx HTTP response. Do NOT expand scope to add a try/catch to `loadItems()` itself — that is a separate, unrequested robustness fix (flag if discovered as a "nice to have" during planning, but AF-01's locked decision is narrowly about the remove button, not `loadItems()`'s error handling).
**Warning signs:** A test that mocks `fetch` to resolve with `{ok: false}` and a JSON error body will NOT reproduce the graceful-degradation scenario — it will instead reproduce the (out-of-scope) tbody-wipe bug.

### Pitfall 2: AF-02 breaks the CLI status table if `core/cli/status.py` is not updated in lockstep
**What goes wrong:** `core/cli/status.py:36` reads `rec['last_heartbeat']` directly from the same `get_status()`/`get_snapshot()` dict that AF-02 modifies. If only `core/health.py` is fixed, `rec.get("last_heartbeat", 0.0)` silently defaults to `0.0` for every plugin (the key is gone), so the CLI's `shoppybot status` (non-JSON, human-readable table) column "Last Heartbeat" will ALWAYS print `"never"` even while the bot is actively running and heartbeating — a real functional regression, not just a display nit.
**Why it happens:** CONTEXT.md's AF-02 decision text only mentions "dashboard JS, SSE consumers" as things to confirm are unaffected; the CLI is a third, independent consumer of the exact same dict that was not explicitly named.
**How to avoid:** `core/cli/status.py:36` MUST be updated in the same task/commit as `core/health.py`'s fix, switching to `rec['heartbeat_age_secs']`. `tests/test_cli_status.py`'s `_STATUS_PAYLOAD` mock fixture (currently hardcodes `"last_heartbeat": 100.0`) must also be updated to supply `"heartbeat_age_secs"` instead, and the table-rendering test should assert the rendered output is NOT `"never"` when a non-null age is supplied (this closes the "test still green even though CLI is broken" trap, since a hardcoded mock would otherwise mask the regression).
**Warning signs:** `tests/test_cli_status.py::test_status_table` continuing to pass after the AF-02 change with no assertion change is a red flag — it means the mock fixture is masking a real behavior change.

### Pitfall 3: `test_snapshot_public_keys_exact` and `test_heartbeat_sets_last_heartbeat` will fail (correctly) and need explicit updates, not silent breakage
**What goes wrong:** `tests/test_health.py:101-110` (`test_snapshot_public_keys_exact`) hard-codes the full expected key set INCLUDING `"last_heartbeat"`; `tests/test_health.py:18-22` (`test_heartbeat_sets_last_heartbeat`) asserts `snap["PluginA"]["last_heartbeat"] > 0.0` directly against the public snapshot. Both will go RED the moment `get_snapshot()` is fixed, by design — but the fix must also touch these two tests plus add a new explicit test proving the key's absence (satisfying CONTEXT.md's literal test requirement), not just patch them to stop failing.
**Why it happens:** These tests currently double as both "internal state was mutated" checks (which should use `reg._plugins[...]` or `heartbeat_age_secs` instead) and "snapshot shape" checks.
**How to avoid:** Update `test_snapshot_public_keys_exact`'s `expected_keys` set to remove `"last_heartbeat"`; update `test_heartbeat_sets_last_heartbeat` to assert `heartbeat_age_secs is not None` post-heartbeat (or rename/repurpose it); ADD a new `test_snapshot_excludes_last_heartbeat` asserting `"last_heartbeat" not in snap["PluginA"]` for a clean, permanent regression guard. Also update `tests/test_service.py:83-90` (`test_get_status_shape_with_registry`, remove `"last_heartbeat"` from the key tuple + add an explicit absence assertion) and `tests/test_orchestrator.py:1295` (change `assert snap[plugin_name]["last_heartbeat"] > 0.0` to `assert snap[plugin_name]["heartbeat_age_secs"] is not None`).
**Warning signs:** None of these four files appear in a diff alongside the `core/health.py` change — that means the AF-02 task is incomplete.

### Pitfall 4: DH-02's CONTEXT.md phase list ("27/28/29") does not match the audit's actual gap (Phase 28 only)
**What goes wrong:** Blindly adding `requirements:` frontmatter to Phase 27's and Phase 29's OWN `SUMMARY.md` files (27-01/02/03-SUMMARY.md, 29-01/02/03-SUMMARY.md) does no harm, but it is NOT what makes "the audit 3-source cross-reference report OBS-01/02/03/04/06/09 as VERIFIED" — those six requirement IDs are, per the v4.1 audit's own Requirements Coverage table AND `REQUIREMENTS.md`'s traceability table, ALL exclusively Phase 28 requirements. Phase 27 (SSE-02) and Phase 29 (SSE-01) already show "yes" in the audit's SUMMARY-frontmatter column, satisfied by Phase 29.1's summaries (`29.1-04-SUMMARY.md` has `requirements-completed: [SSE-01, SSE-02]` — note the DIFFERENT key name, `requirements-completed:`, vs. the established `requirements:` convention used elsewhere).
**Why it happens:** CONTEXT.md's DH-02 decision text and `REQUIREMENTS.md`'s DH-02 row both loosely say "phases 27/28/29" (likely describing the SSE/observability phase GROUP informally), while the audit's own footnote (`v4.1-MILESTONE-AUDIT.md` line 89-92) is precise: "*OBS-01/02/03/04/06/09: Phase 28 SUMMARY frontmatter (28-01..28-04) carries no `requirements` field."
**How to avoid:** See Open Questions for the recommended resolution. Do NOT silently narrow OR silently expand the locked decision's scope without flagging it to the user/planner — this research surfaces the discrepancy explicitly rather than resolving it unilaterally.
**Warning signs:** A DH-02 plan that edits 27-0X/29-0X SUMMARY.md files but does NOT touch 28-01..28-04 SUMMARY.md files will fail to change the audit's actual verdict for OBS-01/02/03/04/06/09 (they will still show "no*" in a future audit re-run, since the fix must land in Phase 28's own files).

### Pitfall 5: DH-03's scope is narrower than DH-01's — only `nyquist_compliant`, not `status`/`wave_0_complete`
**What goes wrong:** All seven v4.0 phase VALIDATION.md files (18-24) currently show `status: draft` in addition to `nyquist_compliant: false` and `wave_0_complete: false`. It would be easy to over-reach and "fix" all three fields by analogy with DH-01 (which DOES flip `status` and `wave_0_complete` for phases 25/26/27). DH-03's locked decision and `REQUIREMENTS.md` wording are both explicit and narrower: "v4.0 phase VALIDATION.md `nyquist_compliant` flags are set true (phases 18-24)" — no mention of `status` or `wave_0_complete`.
**Why it happens:** DH-01 and DH-03 look superficially similar (both are VALIDATION.md frontmatter flips) but were scoped differently by the user/roadmap.
**How to avoid:** Edit ONLY the `nyquist_compliant: false` -> `nyquist_compliant: true` line in each of the 7 v4.0 files. Leave `status: draft` and `wave_0_complete: false` untouched unless the planner/user explicitly expands scope (flag if it seems like an oversight, per "adjacent issues... offer options" from the global CLAUDE.md, but do not silently expand).
**Warning signs:** A DH-03 diff touching more than one line per file (the `nyquist_compliant` line) is over-scoped relative to the locked decision.

### Pitfall 6: Editing frontmatter without breaking YAML frontmatter delimiters
**What goes wrong:** All ten target files (3 v4.1 VALIDATION.md + 4 v4.1 SUMMARY.md + wait, only Phase 28's 4 + 7 v4.0 VALIDATION.md = 14 total files across DH-01/02/03) use standard `---\n...\n---\n` YAML frontmatter blocks. A find-and-replace on a bare value like `false` (for `nyquist_compliant: false`) risks accidentally matching an unrelated `false` elsewhere in the same frontmatter block (e.g., some VALIDATION.md files may have other boolean fields).
**Why it happens:** Naive string replacement instead of targeted key-value editing.
**How to avoid:** Match on the full `key: value` pair (e.g., `nyquist_compliant: false` -> `nyquist_compliant: true`), not a bare value, and verify via a post-edit `grep` that exactly one line changed per file and the YAML still parses (frontmatter delimiters `---` unchanged, no stray whitespace).

## Code Examples

### AF-01: Current dead SSR remove button (to be replaced)
```html
<!-- Source: web/templates/dashboard.html:88-97 (current) -->
<tr data-link="{{ item[1] | urlencode }}">
  <td>{{ item[0] }}</td>
  <td>{{ item[1] }}</td>
  <td>{{ "Yes" if item[2] else "No" }}</td>
  <td>{{ item[3] }}</td>
  <td>
    <button class="btn-remove btn-text-destructive" type="button"
            data-link="{{ item[1] }}">Remove Item</button>
  </td>
</tr>
```
No `.btn-remove` selector or listener exists anywhere in the inline `<script>` block (verified: full read of `dashboard.html`'s `<script>` section, only `loadItems()`'s dynamically `createElement`'d buttons at line 908-912 get `addEventListener`). This confirms the exact v4.1 audit Warning A / UI-03 finding verbatim.

### AF-01: Existing remove route (JS path, reference — unchanged)
```python
# Source: web/routes/api.py:139-147 (existing, unchanged by this phase)
@router.delete("/items/{link_b64}", dependencies=[Depends(check_origin)])
async def remove_item(link_b64: str, request: Request):
    """Remove a tracked item by base64-encoded URL."""
    try:
        link = base64.urlsafe_b64decode(link_b64.encode()).decode()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid link encoding")
    request.app.state.svc.remove_item(link)
    return JSONResponse({"status": "ok"})
```

### AF-01: Test pattern to reuse (existing convention)
```python
# Source: tests/test_web_items.py:48-57 (existing pattern to mirror for the new route)
def test_delete_item_calls_remove_item(mock_svc, client):
    """DELETE /api/items/{b64} calls svc.remove_item with decoded URL."""
    link = "https://ex.com/w"
    b64 = base64.urlsafe_b64encode(link.encode()).decode()
    resp = client.delete(
        f"/api/items/{b64}",
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert resp.status_code == 200
    mock_svc.remove_item.assert_called_once_with(link)

# Recommended new test (AF-01), same file, form-encoded data via TestClient's `data=` kwarg:
def test_post_items_remove_form_calls_remove_item(mock_svc, client):
    """POST /items/remove (form-encoded, no JS) calls svc.remove_item and redirects to /."""
    resp = client.post(
        "/items/remove",
        data={"link": "https://ex.com/w"},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    mock_svc.remove_item.assert_called_once_with("https://ex.com/w")
```

### AF-01: CSRF test pattern to reuse (existing convention)
```python
# Source: tests/test_web_security.py:63-75 (existing pattern to mirror)
def test_csrf_rejected():
    """POST /api/items with a non-local origin returns 403."""
    resp = client.post(
        "/api/items",
        json={...},
        headers={"origin": "http://evil.com"},
    )
    assert resp.status_code == 403

# Recommended new test (AF-01): identical shape, POST /items/remove, cross-origin -> 403
```

### AF-02: SSE frame test pattern to reuse (existing convention)
```python
# Source: tests/test_sse.py:186-213 (existing pattern to mirror for AF-02's "SSE frame" surface)
def test_sse_no_credential_patterns():
    """A status frame carrying a scrubbed last_error (class name only) leaks no credentials."""
    from web.routes.sse import _event_generator
    from web.sse_hub import SseHub
    hub = SseHub()
    async def run():
        gen = _event_generator(_FakeRequest(), hub, keepalive_secs=5.0, max_frames=2)
        # ... hub.broadcast("status", {...}) then advance the generator ...
    frame = asyncio.run(run())
    low = frame.lower()
    for pattern in CRED_PATTERNS:
        assert pattern not in low, f"credential pattern {pattern!r} in SSE frame: {frame!r}"

# Recommended new test (AF-02), same file: broadcast a real HealthRegistry.get_snapshot()-shaped
# status payload and assert "last_heartbeat" absent from the frame text, "heartbeat_age_secs" present.
```

### AF-03: Dead code to remove
```javascript
// Source: web/templates/dashboard.html:871-876 (delete both lines/blocks together)
// --- escHtml helper (for unavoidable SVG string interpolation; unused in Phase 25) ---
function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
```
Confirmed via `Grep` across the entire `web/` directory: only the definition itself matches `escHtml` (2 lines: the comment at 871, the `function escHtml` declaration at 872); zero call sites anywhere.

Recommended new regression test:
```python
# Source pattern: tests/test_web_dashboard.py (existing file, add alongside test_no_innerHTML_with_api_data)
def test_no_dead_eschtml_helper(client):
    """AF-03 regression guard: escHtml() must never reappear in dashboard.html."""
    import pathlib
    html = (pathlib.Path(__file__).parent.parent / "web" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    assert "escHtml" not in html
```

## State of the Art

Not applicable in the usual "old library API vs. new library API" sense — this phase touches only first-party code and planning-artifact metadata, no third-party API surfaces. The one relevant "old vs. new" distinction is internal to the project's own GSD planning-artifact conventions:

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| No `requirements:` frontmatter key in `SUMMARY.md` (Phase 27/28/29's own summaries) | `requirements: [REQ-ID, ...]` flat YAML list (established in Phase 25/26 SUMMARY.md and universally in all PLAN.md files) | Convention appears from Phase 25 onward but was inconsistently applied to Phase 27/28/29's SUMMARY.md files specifically | DH-02 closes this specific gap for Phase 28 (the audit-flagged one) |
| `requirements-completed: [...]` (Phase 29.1's own convention, a DIFFERENT key name) | `requirements: [...]` (majority convention) | Phase 29.1 introduced its own key name independently | Not this phase's concern to reconcile (Phase 29.1's files are not named in any DH-01/02/03 locked decision) — noted for awareness only |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The new `POST /items/remove` route should live in `web/routes/pages.py` (unprefixed router) rather than `web/routes/api.py` (JSON-only per its own docstring) | Architecture Patterns, Pattern 1 | Low — purely organizational; functionally the route works identically regardless of which router file it lives in, since Jinja2Templates import is not strictly required by the new route itself. If the planner prefers `api.py` for route-discoverability reasons, that is a reasonable alternative — flagged as Claude's Discretion in CONTEXT.md. |
| A2 | A 303 (`See Other`) redirect status is preferred over 302 for the POST-then-GET pattern | Architecture Patterns | Low — both 302 and 303 are widely browser-supported for this pattern in practice; 303 is the technically correct HTTP-spec choice (guarantees GET on redirect) |
| A3 | `check_origin` (existing CSRF dependency) works unmodified for a native HTML form POST (not just `fetch`-issued requests) | Don't Hand-Roll | Low — `check_origin` only inspects the `Origin` request header and `request.url.hostname`, both of which are present on native browser form submissions in current browsers; already covered by the existing `test_web_security.py` test suite's assumptions about POST requests generally |

**All AF-01/02/03 code-location and consumer-inventory claims are `[VERIFIED: codebase]`** (confirmed via direct `Read`/`Grep` of the live source, not training-data assumption). **All DH-01/02/03 file-path and current-frontmatter claims are `[VERIFIED: codebase]`** (confirmed via direct `Read` of the actual files at the paths cited). **All suite-pass evidence claims are `[VERIFIED: codebase]`** (quoted directly from the phases' own SUMMARY.md/VERIFICATION.md/MILESTONE-AUDIT.md files, not asserted from training knowledge).

## Open Questions

1. **DH-02 phase-scope discrepancy: "27/28/29" (CONTEXT.md/REQUIREMENTS.md) vs. "28 only" (audit's own evidence)**
   - What we know: The v4.1 audit's Requirements Coverage table and footnote are unambiguous — OBS-01/02/03/04/06/09 are ALL Phase 28 requirements (per `REQUIREMENTS.md`'s own traceability table: `OBS-01..04, OBS-06, OBS-09 -> Phase 28`). Phase 27 (SSE-02) and Phase 29 (SSE-01) already show "yes" for SUMMARY-frontmatter coverage in the audit, satisfied by Phase 29.1's `requirements-completed:` key in `29.1-04-SUMMARY.md`.
   - What's unclear: Whether CONTEXT.md's "phases 27/28/29" phrasing was (a) an informal shorthand for "the SSE/observability phase group" that the planner should interpret narrowly as "wherever the actual gap is" (i.e., Phase 28), or (b) a deliberate, broader ask to also backfill Phase 27's and Phase 29's OWN summaries for consistency even though the audit doesn't currently flag them.
   - Recommendation: Treat Phase 28's four SUMMARY.md files (28-01 through 28-04) as the REQUIRED fix — this is what the locked decision's own success criterion ("the audit 3-source cross-reference reports OBS-01/02/03/04/06/09 as VERIFIED") actually depends on, using this exact mapping sourced from `28-VERIFICATION.md`'s Requirements Coverage table:
     - `28-01-SUMMARY.md` -> add `requirements: [OBS-01, OBS-03]`
     - `28-02-SUMMARY.md` -> add `requirements: [OBS-01, OBS-02, OBS-06]`
     - `28-03-SUMMARY.md` -> add `requirements: [OBS-01, OBS-02, OBS-03, OBS-09]`
     - `28-04-SUMMARY.md` -> add `requirements: [OBS-04, OBS-06]`
     (OBS-05 and OBS-07 are intentionally excluded — already "yes" via Phase 29.1; OBS-08 is intentionally excluded — it is Phase 26's requirement, not Phase 28's.)
     Treat mirroring `requirements: [SSE-02]` into `27-01/02/03-SUMMARY.md` and `requirements: [SSE-01]` into `29-01/02/03-SUMMARY.md` as OPTIONAL discretionary polish (harmless, matches their own PLAN.md files' existing `requirements:` frontmatter, closes a real-but-not-audit-flagged inconsistency) — recommend including it if low-cost, but it is not required to satisfy the locked decision's stated success criterion.

2. **STATE.md schema drift and stale project CLAUDE.md (surfaced by CONTEXT.md, explicitly out of scope)**
   - What we know: CONTEXT.md's `<specifics>` section explicitly asks research to "note if either is cheaply reconcilable within the DH spirit, but do NOT expand scope beyond AF/DH without flagging." `STATE.md` does use custom `**Last action**:`/`**Next action**:` prose fields (confirmed via direct read) rather than a machine-parseable schema; the project's own `CLAUDE.md` architecture section does describe a pre-refactor `amazon_bot.py`/`bestbuy_bot.py` structure that no longer matches the live plugin-based codebase (confirmed stale).
   - What's unclear: Whether either is "cheap" enough to fold into this phase without violating "only do what is explicitly requested."
   - Recommendation: Do NOT include either fix in this phase's plan. Both are outside DH-01/02/03's literal scope (neither is a VALIDATION.md/SUMMARY.md frontmatter field) and outside AF-01/02/03's literal scope (neither is one of the three named audit warnings). Surface both to the user as candidate follow-up items for a future phase or as a standalone quick-fix, per CONTEXT.md's own instruction to flag rather than silently act.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (FastAPI TestClient for web routes) |
| Config file | pytest (project root); web tests in `tests/test_web_*.py` |
| Quick run command | `pytest tests/test_web_dashboard.py tests/test_web_items.py tests/test_web_security.py tests/test_health.py tests/test_sse.py tests/test_service.py tests/test_orchestrator.py tests/test_cli_status.py -q` |
| Full suite command | `pytest -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AF-01 | SSR items-table shows a real `<form>`-based remove action (not a dead `<button>`) | unit (SSR HTML assertion) | `pytest tests/test_web_dashboard.py -k ssr_remove -q` | New test, file exists |
| AF-01 | `POST /items/remove` calls `svc.remove_item(link)` and 303-redirects to `/` | unit (TestClient) | `pytest tests/test_web_items.py -k remove_form -q` | New test, file exists |
| AF-01 | Cross-origin `POST /items/remove` returns 403 (CSRF) | unit (TestClient) | `pytest tests/test_web_security.py -k items_remove -q` | New test, file exists |
| AF-02 | `HealthRegistry.get_snapshot()` excludes `last_heartbeat`, keeps `heartbeat_age_secs` | unit | `pytest tests/test_health.py -k "excludes_last_heartbeat or public_keys_exact" -q` | Updated + new test, file exists |
| AF-02 | `BotService.get_status()["plugins"][name]` excludes `last_heartbeat` | unit | `pytest tests/test_service.py -k get_status_shape -q` | Updated test, file exists |
| AF-02 | SSE `"status"` frame text excludes `last_heartbeat`, includes `heartbeat_age_secs` | unit (SSE generator) | `pytest tests/test_sse.py -k excludes_last_heartbeat -q` | New test, file exists |
| AF-02 | `shoppybot status` CLI table renders a real elapsed-time value (not always "never") | unit | `pytest tests/test_cli_status.py -k status_table -q` | Updated test, file exists |
| AF-02 | `run_plugin`'s post-cycle health assertion uses `heartbeat_age_secs`, not raw float | unit | `pytest tests/test_orchestrator.py -k heartbeat -q` | Updated test, file exists |
| AF-03 | `escHtml` string absent from `dashboard.html` (0 occurrences) | unit (file grep) | `pytest tests/test_web_dashboard.py -k dead_eschtml -q` | New test, file exists |
| DH-01/02/03 | Frontmatter keys match target values; YAML still parses | manual/scripted grep (no pytest — these are `.planning/` docs, not code) | `grep -c "status: validated" .../25-VALIDATION.md` (and equivalents per file) | N/A (doc edit, not code) |

### Sampling Rate
- **Per task commit:** Quick run command scoped to touched test files
- **Per wave merge:** `pytest -q` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`; for DH-01/02/03, a manual/scripted grep pass over all 14 target `.planning/` files confirming exact frontmatter values (no pytest coverage applies to doc-only edits)

### Wave 0 Gaps
- None for AF-01/02/03 — all target test files (`tests/test_web_dashboard.py`, `tests/test_web_items.py`, `tests/test_web_security.py`, `tests/test_health.py`, `tests/test_sse.py`, `tests/test_service.py`, `tests/test_orchestrator.py`, `tests/test_cli_status.py`, `tests/test_web_controls.py`) already exist with established, mirror-able patterns (TestClient fixtures, CSRF-rejection pattern, SSE-frame credential-pattern test, snapshot-key-exact test). No new test framework or fixture infrastructure is needed.
- DH-01/02/03 have no pytest coverage by design (planning-artifact YAML, not application code) — verification is a direct grep/read pass over the 14 target files, which the executor performs directly rather than via an automated test suite.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Localhost-bound single-operator tool; no auth system exists or is touched by this phase |
| V3 Session Management | No | Not touched |
| V4 Access Control | No | Not touched |
| V5 Input Validation | Yes | New `POST /items/remove` form field `link` must be validated the same way `add_item` validates its `link` field (non-empty check; `BotService.remove_item` is a no-op-safe query against SQLite regardless of malformed input, matching the existing `DELETE /api/items/{link_b64}` route's permissive behavior) |
| V6 Cryptography | No | Not touched |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-site form submission triggering item removal (CSRF) | Tampering | `Depends(check_origin)` on the new `POST /items/remove` route, identical to every other mutating route in this codebase |
| Information disclosure via internal timing data (`last_heartbeat` monotonic float) | Information Disclosure | This is precisely what AF-02 remediates — a low-severity, non-credential cosmetic leak per the audit's own characterization ("Frontend ignores it; no credentials or sensitive data exposed") |
| Stored/reflected XSS via the new hidden form field's `link` value | Tampering / Information Disclosure | Jinja2's default autoescaping (already relied upon by the existing unescaped `{{ item[1] }}` interpolation at `dashboard.html:90`) escapes the value when rendered into the `value="..."` HTML attribute; no new escaping mechanism needed |

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `E:\repos\ShopPyBot\web\templates\dashboard.html` (full read) — SSR remove button, `loadItems()`, `escHtml()`, SSE wiring, `renderHealthCards()`
- `E:\repos\ShopPyBot\web\routes\api.py`, `pages.py`, `sse.py`, `E:\repos\ShopPyBot\web\security.py`, `E:\repos\ShopPyBot\web\sse_hub.py`, `E:\repos\ShopPyBot\web\__init__.py` (full reads) — route registration, CSRF pattern, SSE producer chain
- `E:\repos\ShopPyBot\core\health.py`, `core\service.py`, `core\cli\status.py` (full reads) — `last_heartbeat`/`heartbeat_age_secs` single-source-of-truth chain
- `E:\repos\ShopPyBot\tests\test_health.py`, `test_service.py`, `test_orchestrator.py`, `test_cli_status.py`, `test_web_controls.py`, `test_web_items.py`, `test_web_security.py`, `test_web_dashboard.py`, `test_sse.py` (full/targeted reads) — full consumer/test inventory for AF-02, existing test-pattern conventions for AF-01/02/03
- `E:\repos\ShopPyBot\.planning\milestones\v4.1-phases\{25,26,27}-*\{25,26,27}-VALIDATION.md`, `-VERIFICATION.md`, `-03-SUMMARY.md` (full/targeted reads) — DH-01 current frontmatter + suite-pass evidence
- `E:\repos\ShopPyBot\.planning\milestones\v4.1-phases\28-frontend-observability-surfaces\28-{01,02,03,04}-SUMMARY.md`, `28-{01,02,03,04}-PLAN.md`, `28-VERIFICATION.md` (full reads) — DH-02 requirement-ID mapping
- `E:\repos\ShopPyBot\.planning\milestones\v4.1-phases\27-sse-infrastructure\27-{01,02,03}-PLAN.md`, `29-sse-client-wiring\29-{01,02,03}-PLAN.md`, `29.1-.../29.1-{02,04}-SUMMARY.md` (grep + targeted reads) — DH-02 scope-discrepancy evidence
- `E:\repos\ShopPyBot\.planning\milestones\v4.1-MILESTONE-AUDIT.md`, `v4.1-REQUIREMENTS.md` (full reads) — DH-02's authoritative Requirements Coverage cross-reference table
- `E:\repos\ShopPyBot\.planning\milestones\v4.0-phases\{18..24}-*\{18..24}-VALIDATION.md` (full frontmatter reads, all 7) — DH-03 current frontmatter
- `E:\repos\ShopPyBot\.planning\milestones\v4.0-MILESTONE-AUDIT.md` (full read) — DH-03's authoritative suite-pass + explicit flag-flip recommendation
- `E:\repos\ShopPyBot\.planning\REQUIREMENTS.md`, `STATE.md`, `.planning\config.json` (full reads) — phase requirement IDs, milestone context, `nyquist_validation: true`
- `E:\repos\ShopPyBot\.planning\phases\35-audit-fixes-doc-hygiene-cleanup\35-CONTEXT.md` (full read) — locked decisions
- `E:\repos\ShopPyBot\CLAUDE.md` (full read) — project constraints (noted stale architecture section)

No Context7/WebFetch/WebSearch lookups were needed — this phase is 100% first-party codebase and planning-artifact work with zero external library surface.

## Metadata

**Confidence breakdown:**
- AF-01/02/03 code locations and fix design: HIGH — every claim directly verified via `Read`/`Grep` against live source, cross-checked against existing tested patterns in the same codebase
- DH-01/03 frontmatter + suite-pass evidence: HIGH — current frontmatter directly read; suite-pass evidence quoted verbatim from the phases' own SUMMARY.md/VERIFICATION.md/MILESTONE-AUDIT.md documents (first-party, not inferred)
- DH-02 requirement-ID mapping: HIGH for the mapping itself (sourced directly from `28-VERIFICATION.md`'s Requirements Coverage table); MEDIUM for the "which phases to edit" scope question, explicitly flagged as an Open Question requiring planner/user resolution rather than treated as settled

**Research date:** 2026-07-02
**Valid until:** No expiry concern — this research is scoped to the current, static state of this specific commit's codebase and planning artifacts, not to any external/versioned dependency. Re-verify only if the underlying files change before planning begins.
