---
gsd_state_version: 1.0
milestone: v5.0
milestone_name: Real Release & Plugin Ecosystem
status: completed
last_updated: "2026-08-03T22:47:03.048Z"
last_activity: 2026-08-03 -- Phase 37 plan 04 complete (PKG-05 gated in CI; scripts/verify_wheel.py observed failing, not just passing)
progress:
  total_phases: 15
  completed_phases: 2
  total_plans: 9
  completed_plans: 9
  percent: 13
---

# ShopPyBot — State

## Project Reference

**Core Value**: Drop-in plugin framework — community adds retail platform integrations via a single Python file in `plugins/`; no core changes required.

**Project**: ShopPyBot
**Milestone**: v5.0 Real Release & Plugin Ecosystem (Phases 36-50)
**Total Phases**: 15 (Phases 36-50)
**Total Requirements**: 84 (MAIN-01..07, PKG-01..06, PUB-01..09, FIX-01..11, SCAN-01..11, QUAL-01..09, PAR-01..06, EXT-01..17, OPS-01..02, UAT-01..06)

---

## Current Position

Phase: 37 (Distributable Artifact) — COMPLETE
Plan: 4 of 4
Status: Phase 37 complete (all 4 plans; PKG-01..06 all closed). Next: Phase 38 (Scanning to Zero)
Last activity: 2026-08-03 -- Phase 37 plan 04 complete (PKG-05 gated in CI; scripts/verify_wheel.py observed failing, not just passing)

**Carry into Phase 38:**

- **The `wheel` CI job has never run on a runner.** It lands with this branch's next push. Its command was executed locally on Windows and exits 0 with five PASS lines, but the ubuntu-latest leg is unexercised, and that leg is the one that would catch a Linux-only dependency gap. Treat its first CI run as new information, not as a formality.
- **`scripts/verify_wheel.py` is the local debugger for a red wheel job.** One command reproduces exactly what CI does: `.venv/Scripts/python.exe scripts/verify_wheel.py --wheel-dir <dir with one .whl> --venv <scratch path>`. No push needed.
- **Do not let the wheel job install from `requirements.txt` or with `-e`.** That converts the gate into a green rubber stamp (T-37-14). There is a comment above the job saying so, and the job's steps are asserted free of both strings.
- Phase 38 owns SHA-pinning the third-party actions and adding a `permissions:` block across `ci.yml`. The new job deliberately matches the existing `@v6` tag style so that sweep finds a consistent file.

**Carry from Phase 37:**

- **`master` is now the source of truth.** Tip `a99b67de708fa75d2ce085824e6611485a173f22`. The v4.1+v4.2 surface is on the default branch and its CI is green on both `ubuntu-latest` and `windows-latest`.
- **Use raw `git`, never `rtk git`, for any ancestry, range, or rev-list query.** Confirmed live twice: `rtk git log <range>` drops merge commits and returned an empty range that actually contained two commits. `/mingw64/bin/git` explicitly if interference is suspected. Other rtk verbs are fine.
- **The harness auto-mode classifier blocks `gsd-executor` dispatch for GitHub-mutating plans.** It denied Phase 36 wave 3 twice, including after the operator granted permission. Waves 3 through 5 ran inline in the orchestrator's main thread instead, which works but produces no per-task commits. Expect the same for any phase whose plans merge PRs.
- `required_status_checks.strict: true` on master, contexts `CodeQL`, `test (windows-latest)`, `test (ubuntu-latest)`, `enforce_admins: false`. Every PR needs `gh pr update-branch` (or `@dependabot rebase` for Dependabot PRs) immediately before its own merge. Phase 38 owns any change to protection.
- **The third-party Actions allowlist is NOT blocking.** `gitleaks-action` and `release-please-action` both resolve and run. That expectation carried from the v4.2 audit is now stale.
- **Dependabot is awake.** Closing PR #8 lifted the inactivity pause; it rebased PR #20 on request within about 2 minutes and self-closed 3 superseded PRs.
- `pre-v5-mainline` tag at `e98ec83` remains the rollback point for everything Phase 36 did.
- **37-04's CI assertion 4 has its accessor.** `from core.paths import bundled_plugins_dir` returns a directory holding exactly 7 `shopbot_plugin_*.py` files, verified from a bare wheel install with no extras. That is the one-liner the wheel job should assert; it needs only `platformdirs`, so it runs before any extra is installed.
- Local test env: `.venv/Scripts/python.exe -m pytest`, 971 collected (969 passed / 2 skipped) as of 37-03. As of 37-02 `pyproject.toml` declares the real 9-package runtime set plus `web`, `sound` and `test` extras, so `pip install -e ".[web,test]"` is now sufficient; `pip install -r requirements.txt` remains the dev-pin path.

## Phase Status

| Phase | Goal Summary | Status | Reqs |
|-------|-------------|--------|------|
| 36 — Mainline Reconciliation | `master` becomes the real ShopPyBot; the v4.1+v4.2 suite runs in CI for the first time | **Complete** (5/5 plans; MAIN-01..07 all verified; master `a99b67d`, CI 961 passed / 2 skipped both runners) | MAIN-01..07 |
| 37 — Distributable Artifact | The built wheel actually runs; truthful dependency declaration; PKG-06 answers EXT-03's blocker | **Complete** (4/4 plans; PKG-01..06 all verified; a clean-venv wheel install passes all 5 assertions, and the gate was observed failing on two doctored wheels) | PKG-01..06 |
| 38 — Scanning to Zero | Dependabot/CodeQL/secret-scanning queues to zero real findings; required checks + branch protection | Not started | SCAN-01..11 |
| 39 — Quality Floor | Lint, format, typecheck, coverage enforced in CI before the milestone's new code lands | Not started | QUAL-01..09 |
| 40 — Public-Repo Readiness | LICENSE, nodriver README, honest sample config, CODEOWNERS, drift corrected, SEED-001 retired | Not started | PUB-01..09 |
| 41 — Live Defect Closure | Control commands report the truth; unattended alerts arrive; dashboard data is current | Not started | FIX-01..11 |
| 42 — Plugin Registry Hardening (H1) | A malformed plugin cannot take down start, the dashboard, `plugins list`, or `run_plugin` | Not started | EXT-01, EXT-02 |
| 43 — Plugin Roots, Precedence & API Version Gate (H2) | User-writable second root, bundled-wins collisions, API version enforced at load | Not started | EXT-03, EXT-04, EXT-05 |
| 44 — Provenance, Load-Boundary Integrity & Run Lock (H3) | Managed plugins carry provenance; drifted files do not execute; lifecycle commands tell the truth | Not started | EXT-06, EXT-07, EXT-08 |
| 45 — Community Plugin Parity + Pre-Transfer Arming Gate (G) | 5 community plugins reach the Amazon/BestBuy safety floor; the shared checkout gate is built once | Not started | PAR-01..06 |
| 46 — Trust Tiers & Capability Reduction (H4) | Third-party plugins disarmed for checkout by default; per-platform credential scoping; never the CVV | Not started | EXT-09, EXT-10 |
| 47 — Fetch, Pre-Flight, Install & Consent (H5) | `plugins install` pinned by commit SHA, statically screened, gated by typed consent | Not started | EXT-11, EXT-12, EXT-13 |
| 48 — Plugin Lifecycle (H6) | `update`/`remove`/`verify`/`outdated`; re-consent on change; removal prints a rotation checklist | Not started | EXT-14 |
| 49 — Trust Documentation, Registry & Vocabulary Guard (H7) | Nothing shipped calls third-party plugins safe; machine-readable registry retires the wiki table | Not started | EXT-15, EXT-16, EXT-17 |
| 50 — Ops Hardening & UAT Consolidation | Bounded, indexed price history; one honest operator verification checklist | Not started | OPS-01..02, UAT-01..06 |

---

## Performance Metrics

**Plans completed**: 9 of TBD (Phase 36: 5, Phase 37: 4)
**Requirements completed**: 13 of 84 (MAIN-01..07, PKG-01..06)
**Phases completed**: 2 of 15 (36, 37)
**Blockers resolved**: 0

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 36 | 01 | 13min | 3 | 2 |
| 36 | 02 | 16min | 3 | 7 |

---
| Phase 37 P01 | 12min | 2 tasks | 11 files |
| Phase 37 P02 | 7min | 2 tasks | 2 files |
| Phase 37 P03 | 7min | 2 tasks | 5 files |
| Phase 37 P04 | 17min | 2 tasks | 2 files |

## Accumulated Context

### Sequencing Invariants (v5.0 — carry into planning)

The seven hard constraints from REQUIREMENTS.md, mapped onto phase numbers. Reordering
phases without re-checking these breaks the milestone.

- **Phase 36 before Phase 38.** Several SCAN requirements target workflows that do not exist on `master` until PR #11 lands.
- **Phase 37 before any release cut.** release-please exists to publish an artifact that currently cannot start.
- **Phase 37 (PKG-06) before Phase 43 (EXT-03).** If `bundled_plugins_dir()` does not survive a wheel install, the `importlib.resources` fix is Phase 37 work, not workstream H's.
- **Phase 42 (EXT-01) is the first EXT phase.** Every later EXT step multiplies the number of non-conforming plugins reaching paths that currently raise.
- **Phase 46 (EXT-09) before Phase 47 (EXT-11).** The disarm default must already be true when install ships, so no released state has a stranger's freshly installed plugin able to buy by default.
- **Phase 45 (PAR-03) and Phase 46 (EXT-09) are one mechanism.** Both are a pre-transfer gate at `core/orchestrator.py:571`. Phase 45 builds it for the community plugins; adjacent Phase 46 extends it with the third-party disarm default. Two gates that can diverge is the failure mode.
- **EXT-15 (Phase 49) gates milestone completion, not phase ordering.** Phase 50 may follow it.

Deliberate, non-constraint orderings:

- Phase 39 (Quality Floor) precedes Phases 41-50 so the milestone's new code is written under an enforced standard rather than retrofitted to one.
- Phase 41's FIX-08 (escape + length-cap the plugin name) precedes Phase 47, which is what makes that value attacker-controlled.
- Phase 40's LICENSE precedes Phase 49's liability language, which lands beside it.
- Phases 42/43/44/46/47/48/49 are H1-H7 from `research/SUMMARY.md` in its reconciled order. That order is researched, not re-derived — do not reshuffle it during planning.

### Research Flags (v5.0 — carry into planning)

- **Phase 36:** highest-risk phase in the milestone. Small in requirement count, large in blast radius: a 263-commit merge whose CI has never executed, so the first green run is also the first evidence the merge is correct. Budget verification room, not just merge mechanics.
- **Phase 43:** blocked on PKG-06's factual answer (does the bundled plugin root resolve from an installed wheel?). `plugins*` is in `packages.find` and the plugin files are `.py` modules rather than data files, so discovery probably works — but verify against an actual built wheel before this phase plans.
- **Phase 47:** the consent prompt copy is an acceptance criterion, not an implementation detail. Re-read the consent-fatigue evidence (Böhme and Köpsell CHI 2010; Chrome SSL interstitial clickthrough) before writing it. Type the plugin name back, not `y`; four to six lines of facts, not prose; no bare `--yes`.
- **Phase 47:** two open decisions to make here rather than guess — whether `GITHUB_TOKEN` joins `SECRET_KEYS` or stays environment-only, and whether the install-time import smoke test ships at all (if it does, it must run strictly after consent is granted, never before).
- **Phase 46 or 47:** whether a `sys.addaudithook` detection layer ships, and at what scope. Needs a measurement, not a design opinion. Whatever ships is labelled detection and forensics, never prevention.
- **Phase 49:** where the third-party disclaimer text lives (SECURITY.md section, a new `docs/PLUGIN_TRUST.md`, or both) and whether a first-run acknowledgement exists. The install-time half is Phase 47; the first-run half is an unresolved product call. Liability wording carries a MEDIUM confidence flag and is not legal advice.
- **All EXT phases:** the dominant risk is overclaiming, not a missing feature. Import is execution and nothing in v5.0 changes that. Attach to every shipped control one sentence naming what it does not stop.

### REVIEW.md Deep-Pass Assignments (v5.0)

Per RETROSPECTIVE.md lesson 4, two phases carry a post-verification REVIEW.md deep pass:

- **Phase 45** (Community Plugin Parity + Pre-Transfer Arming Gate) — safety-critical guard.
- **Phase 47** (Fetch, Pre-Flight, Install & Consent) — the milestone's new unauthenticated input surface. Phase 48 extends the same surface; re-run both criteria against `update`/`remove` before closing it.

Both reviews carry the same two non-negotiable criteria: (a) for every shipped control, one sentence naming what it does not stop; (b) confirmation that no shipped artifact describes third-party plugins as sandboxed, isolated, curated, verified, or safe. EXT-17 makes (b) mechanical.

### Scope Decision Recorded at Roadmap Time (v5.0)

- **REL-01 (event-loop stall watchdog) stays in v2.** Research `SUMMARY.md` Gap 5 asked whether it belongs to H, to G, or to a deferred reliability item. It is a reliability control rather than a distribution control, `asyncio.timeout` cannot preempt a blocking plugin regardless of where that plugin came from, and the exposure exists today with the 7 bundled plugins. Folding it into H would silently expand that workstream. Recorded as a decision, not an omission.

### Key Decisions Logged (v4.1)

- [Phase 25 — roadmap]: charting library = uPlot 1.6.32 (MIT, ~52KB IIFE + ~1KB CSS, interactive tooltips, Canvas 2D, time series); vendored to `web/static/uplot.min.js` + `web/static/uplot.min.css`; no CDN, no Node.
- [Phase 25 — roadmap]: CSS 3-file split: `tokens.css` (`:root` blocks only), `components.css` (component rules via `var(--xxx)` only), `dashboard.css` (layout + `@import`); each file stays under 200 lines.
- [Phase 25 — roadmap]: FOUC prevention: inline synchronous `<script>` as FIRST child of `<head>` (before any `<link>`); reads `localStorage.getItem("theme")` and sets `document.documentElement.dataset.theme`; executes before browser requests any CSS.
- [Phase 27 — roadmap]: SSE bridge pattern: uvicorn-side `_poll_loop` background task is the SOLE SSE producer; calls `asyncio.to_thread(svc.get_status)` on uvicorn's event loop; bot daemon thread never touches `asyncio.Queue` objects. BotService is unchanged.
- [Phase 27 — roadmap]: SPIKE recommended at Phase 27 start — validate lifespan + `asyncio.create_task` + `SseHub` wiring against actual `web/__init__.py` `create_app()` factory before full implementation.
- [Phase 26 — roadmap]: `get_status()` `last_error` scrubbed to `exc.__class__.__name__` only at the `get_status()` boundary (never `str(exc)`); CI assertion validates SSE frames contain no credential-pattern strings (`@`, `password`, `token`, `key=`, `cvv`).
- [Phase 26 — roadmap]: No new Python dependencies; raw `StreamingResponse(media_type="text/event-stream")` from starlette (already transitive dep) covers all SSE needs; do NOT add `sse-starlette`; do NOT upgrade FastAPI to 0.135+ in this milestone.
- [Phase 26 — roadmap]: Log plugin-filter (OBS-08) is contingent — verify `writeLog` consistently tags lines with `[PLUGIN_NAME]` before building; if inconsistent, defer plugin filter sub-feature (not the whole requirement) to post-v4.1.

### Key Decisions Logged (v4.0 carried)

- [Phase 10-01]: create_app() router imports deferred inside factory body to avoid circular import; all fastapi imports confined to web/ package (CLI-04)
- [Phase 10-01]: WEB_ALLOWLIST extends CLI ALLOWLIST with 4 notifier toggles only (no platform enables -- AppConfig has no enabled field per config-scope-note)
- [Phase 10-01]: TemplateResponse uses new Starlette API signature: TemplateResponse(request, name, context) to avoid DeprecationWarning
- [Phase 18-02]: place_order_guarded is a concrete async method on RetailerPlugin ABC; test_mode default True (fail-safe suppress when config missing); PLUGIN_API_VERSION stays 2 (additive BUY-02)
- [Phase 22-02]: sqlite3.OperationalError only caught in run_plugin items read; DatabaseError (corruption) propagates (REL-05 / Pitfall 7)
- [Phase 23-01]: SessionStore mirrors EncryptedFileBackend [salt][Fernet token] layout; restore() returns None (not raises) on InvalidToken -- REL-04 silent login fallback contract

### Research Flags (v4.1 — carry into planning)

- Phase 25: Run MC-4 test against the new template before closing the phase — non-local banner must remain visible and correctly styled in both themes (Pitfall 9).
- Phase 26: Verify log line format for `[PLUGIN_NAME]` tag consistency before building plugin filter in `read_logs_filtered()`; if inconsistent, scope OBS-08 to level+search only (plugin filter deferred).
- Phase 27: Spike at phase start — validate `asyncio.create_task(_poll_loop(...))` inside FastAPI lifespan context manager against installed `fastapi==0.115.8` + `uvicorn==0.30.6` before full implementation (cross-loop race is highest-risk pitfall).
- Phase 27: `request.is_disconnected()` must be polled inside the SSE generator loop — verify FastAPI 0.115.8 supports this API (HIGH confidence per research, but confirm before implementing).
- Phase 28: Price data is Amazon-only today (PRICE-02); non-Amazon items get explicit "No price history available for this plugin" message — never a blank chart area.
- All phases: Zero-Node constraint is hard — no package.json, no CDN references, no external font URLs; all JS/CSS vendored via `web/static/`.

### Sequencing Notes (v4.2 — carry into planning)

- Phase 30 (Breakfix Hardening) is sequenced first: BF-02 is the milestone's one HIGH-priority item (place-order-timeout double-buy latch); closing it before other debt reduces exposure the longest.
- Phase 31 must land before Phase 32: RH-04 (CodeQL) and RH-05 (dependabot) put CI security scanning in a working state before RH-02 (release-please) starts tagging releases against that same CI.
- Phase 32: RH-03 (pyproject version reconcile to 2.0.0) lands in the same phase as RH-02 (release-please seed) — release-please needs a correct pyproject source-of-truth from its first run.
- Phase 33: CFG-01 (field harmonization) must be implemented before CFG-02 (flexible per-platform config) — both touch the same config-schema surface; CFG-02 builds on the harmonized field set.
- Phase 34 FC-01 carries the v4.1 Phase 26 research flag forward: verify `[PLUGIN_NAME]` log-tag consistency in `writeLog` before building the `/api/logs` plugin filter (was deferred from OBS-08 pending this verification).
- Phase 35 folds Audit-Fixes (AF-*) and Doc-Hygiene (DH-*) together — both are low-effort, low-risk cleanup; sequenced last as the milestone's closing phase.

### Active Todos

- **Phases 36 and 37 are CLOSED.** `master` carries the full v4.1+v4.2 surface with green CI, and the built wheel now installs and runs. Next step: `/gsd:plan-phase 38` (Scanning to Zero).
- **Phase 37's work is committed but not pushed.** The `wheel` CI job and `scripts/verify_wheel.py` exist only on `chore/v4.0-milestone-close` until this branch is pushed and merged. Until then no runner has ever executed the job, so nothing about it is green or red yet.
- **Operator action, release-please.** Enable Settings, Actions, General, Workflow permissions, "Allow GitHub Actions to create and approve pull requests". release-please currently fails at PR creation with `GitHub Actions is not permitted to create or approve pull requests`. This is NOT the third-party allowlist, which is confirmed working. Deliberately not changed autonomously during Phase 36: it is a security-posture setting that permits Actions to self-approve pull requests, which is a call for the repo owner.
- **PR #21 open. DO NOT MERGE AS-IS. Proven to break SSE, not a precautionary hold.** pip minor-and-patch group, 10 updates. Its CI fails on both runners with `tests/test_sse.py::test_lifespan_creates_hub_and_registers_route`, `AssertionError: /api/events not registered; routes=['/openapi.json', '/static']`. Under `fastapi==0.141.1` the SSE route is never registered, so `create_app()` yields an app with no live-update channel. This confirms the v4.1 Phase 26 decision (FastAPI pinned below 0.135 because SSE uses a raw starlette `StreamingResponse`) for a concrete, reproducible reason.
  - **Safe half:** the `requirements.txt` upgrades (platformdirs, pydantic, pytest, pytest-asyncio, pyyaml, requests, selenium, webdriver-manager). All upgrades; MAIN-02 protected pins untouched.
  - **Breaking half:** `pyproject.toml`'s `fastapi` 0.115.8 to 0.141.1 and `uvicorn[standard]` 0.30.6 to 0.52.0.
  - **Resolution:** split the PR, take the requirements half, and treat the FastAPI route-registration change as real work with test coverage attached (`tests/test_sse.py`, `tests/test_sse_wiring.py`). Diagnosis posted as a comment on PR #21 on 2026-08-02. Owner: Phase 39 (Quality Floor) or a dedicated fix.
- Dangling branch `release-please--branches--master--components--shoppybot` at `015ec66`, created by release-please immediately before it failed at PR creation. Harmless; reused on re-run or deletable.
- 7 open Dependabot vulnerability alerts on the default branch as of 2026-08-02 (2 high, 4 moderate, 1 low). Phase 38 SCAN scope.
- **The harness auto-mode classifier blocks `gsd-executor` dispatch for GitHub-mutating plans.** It denied Phase 36 wave 3 twice, including after the operator explicitly granted permission and asked for a re-dispatch. Waves 3 through 5 ran inline in the orchestrator's main thread instead. Inline works and is more visible, but produces no per-task commits and no per-plan STATE writes, so the orchestrator must update STATE.md itself. Expect the same for any phase whose plans merge PRs.
- Operator: the deferred live-UAT checklists below are consolidated by Phase 50 (UAT-04) into one file with a stated acceptance bar. Running them stays operator work.
- ~~Operator: Dependabot is repo-level PAUSED, unpause once PR #11 is in.~~ **RESOLVED 2026-08-02 in Phase 36.** Closing PR #8 lifted the inactivity pause, as Pitfall 5 predicted. Dependabot then self-closed three superseded PRs (#15, #16, #18) with explicit reasons, opened a rebuilt #21, retitled #19 and #20 against the new master, and honoured an `@dependabot rebase` on #20 within about 2 minutes. Version-update rebasing is confirmed working, not just branch cleanup.

### Blockers

- None

---

## Deferred Items

### Carried from v4.0 milestone close (2026-06-25) — 17 items

All deferred per the autonomous live-UAT policy; none are code gaps. This is the operator's pre-production live-buy checklist.

| Category | Item | Status |
|----------|------|--------|
| uat | Phase 18 — live `--monitor-only` run fires alerts but places no order (18-HUMAN-UAT.md) | partial (1 pending) |
| uat | Phase 19 — live Amazon/BestBuy confirmation URL + DOM order-number selectors (19-HUMAN-UAT.md) | partial (3 pending) |
| uat | Phase 20 — live BestBuy/Amazon shipping form-fill selectors + CVV entry (20-HUMAN-UAT.md) | partial (4 pending) |
| uat | Phase 21 — per-step timeout clean-abort under a real slow drop (21-HUMAN-UAT.md) | partial (2 pending) |
| uat | Phase 22 — live supervisor restart + browser relaunch + SIGTERM teardown (22-HUMAN-UAT.md) | partial (2 pending) |
| uat | Phase 23 — live cross-restart MFA/login-skip; persisted session accepted (23-HUMAN-UAT.md) | partial (2 pending) |
| uat | Phase 24 — live headless-server run, no audio device / pygame absent (24-HUMAN-UAT.md) | partial (1 pending) |
| verification | Phases 18-24 — VERIFICATION.md status `human_needed` (automated must-haves passed; live checks deferred) | human_needed (7) |
| todo | Amazon WAF CAPTCHA auto-solve wiring (waf-auto-solve-followup.md) | pending (medium); manual-pause fallback in place |
| seed | SEED-001 — public repo history scrub/squash before release | dormant (release milestone) |
| seed | SEED-002 — release-please automatic version tagging | dormant (release milestone) |

**Tracked HIGH item (from v4.0 audit):** Phase 21 place-order-stage timeout double-buy edge (placed-but-unconfirmed) — verify live and consider P22-style hardening. **Addressed in v4.2 Phase 30 (BF-02).**
| Phase 30 P01 | 22min | 3 tasks | 5 files |
| Phase 30-breakfix-hardening P02 | 12min | 2 tasks | 2 files |
| Phase 30-breakfix-hardening P03 | 10min | 2 tasks | 3 files |
| Phase 30-breakfix-hardening P04 | 5min | 2 tasks | 4 files |
| Phase 30-breakfix-hardening P06 | 10min | 2 tasks | 10 files |
| Phase 30-breakfix-hardening P05 | 19min | 2 tasks | 4 files |
| Phase 31 P01 | 6min | 2 tasks | 3 files |
| Phase 31-ci-security-infrastructure P02 | 5min | 2 tasks | 2 files |
| Phase 31 P03 | 8min | 2 tasks | 3 files |
| Phase 32-release-automation-community-readiness P01 | 10min | 3 tasks | 4 files |
| Phase 32 P02 | 9min | 2 tasks | 1 files |
| Phase 32 P03 | 5min | 2 tasks | 2 files |
| Phase 33 P01 | 6min | 3 tasks | 5 files |
| Phase 33 P02 | 12min | - tasks | - files |
| Phase 34-feature-completion P01 | 3min | 2 tasks | 3 files |
| Phase 34 P03 | 15min | 3 tasks | 6 files |
| Phase 34 P02 | 4min | 2 tasks | 9 files |
| Phase 35 P01 | 5min | 3 tasks | 5 files |
| Phase 35 P02 | 8min | 2 tasks | 8 files |
| Phase 35 P03 | 5min | 2 tasks | 20 files |
| Phase 36 P01 | 13min | 3 tasks | 2 files |

### Acknowledged at v4.1 milestone close (2026-06-30) — 8 items

All deferred per the autonomous live-UAT policy; none are code gaps. Operator dashboard/observability checklist plus carried release items.

| Category | Item | Status |
|----------|------|--------|
| verification | Phase 27 — SSE infra live-socket checks (27-VERIFICATION.md) | human_needed |
| verification | Phase 28 — observability surfaces live-browser render (28-VERIFICATION.md) | human_needed |
| verification | Phase 29 — SSE client wiring live-browser (29-VERIFICATION.md) | human_needed |
| verification | Phase 29.1 — tech-debt fixes live-runtime (29.1-VERIFICATION.md) | human_needed |
| uat | Phase 29.1 — cold-load chart / stall->fallback / repeated-msg after repaint (29.1-HUMAN-UAT.md) | partial (3 pending) |
| todo | Amazon WAF CAPTCHA auto-solve wiring (waf-auto-solve-followup.md) | pending (medium); manual-pause fallback in place. **In scope as v4.2 Phase 30 (BF-01), code wiring only — live-challenge proof stays operator debt.** |
| seed | SEED-001 — public repo history scrub/squash before release | dormant (release milestone). **Non-destructive audit half in scope as v4.2 Phase 31 (RH-01); destructive rewrite stays operator-gated.** |
| seed | SEED-002 — release-please automatic version tagging | dormant (release milestone). **In scope as v4.2 Phase 32 (RH-02/RH-03).** |

**Audit warnings tracked to backlog (non-blocking, from v4.1 audit refresh):** UI-03 SSR remove-button dead click handler (Phase 25, graceful-degradation, not XSS) — **in scope as v4.2 Phase 35 (AF-01).** `last_heartbeat` raw monotonic float in `get_status()` / SSE status payload (Phase 27, cosmetic, no credential exposure) — **in scope as v4.2 Phase 35 (AF-02).**

### Acknowledged at v4.2 milestone close (2026-07-03) — 8 items

All deferred per the autonomous live-UAT policy; none are code gaps. Acknowledged via the pre-close open-artifact audit (`gsd-sdk query audit-open`) — live-browser/live-retailer/live-GitHub-Actions checks are structurally impossible in CI per this milestone's own "done = code-complete + CI-green" definition.

| Category | Item | Status |
|----------|------|--------|
| verification | Phase 30 — Breakfix Hardening live-UAT (WAF challenge, double-buy edge, community-plugin login selectors) (30-VERIFICATION.md) | human_needed |
| verification | Phase 31 — CI & Security Infrastructure live Actions runs (gitleaks/CodeQL green-run, Dependabot queue drain) (31-VERIFICATION.md) | human_needed |
| verification | Phase 32 — Release Automation live Actions run + PVR toggle (32-VERIFICATION.md) | human_needed |
| verification | Phase 33 — Config Refactor live poll-cadence jitter observation (33-VERIFICATION.md) | human_needed |
| verification | Phase 34 — Feature Completion live-browser visual/theme rendering (log filter, analytics view) (34-VERIFICATION.md) | human_needed |
| todo | Amazon WAF CAPTCHA auto-solve wiring (waf-auto-solve-followup.md) | pending (medium); code wiring shipped in v4.2 Phase 30 (BF-01) — live-challenge proof stays operator debt |
| seed | SEED-001 — public repo history scrub/squash before release | dormant; non-destructive audit shipped in v4.2 Phase 31 (RH-01) — destructive rewrite stays operator-gated |
| seed | SEED-002 — release-please automatic version tagging | dormant; code-complete in v4.2 Phase 32 (RH-02/RH-03) — first live Actions run pending operator Actions-allowlist widen |

**Code-level tech debt carried forward (from v4.2-MILESTONE-AUDIT.md):** BF-02's write-ahead place-order marker is wired for Amazon + BestBuy only — the 5 community plugins (Walmart, Target, GameStop, NewEgg, SquareEnix) do not yet pass `order_marker_link` to `place_order_guarded`, leaving the same double-buy exposure BF-02 was created to close (pre-declared deferred scope; all 5 plugins independently EXPERIMENTAL/selector-unverified).

**Operator-action items (confirmed still open by live checks during the v4.2 audit):** enable GitHub Private Vulnerability Reporting; widen the Actions allowlist for `gitleaks/gitleaks-action` + `googleapis/release-please-action`; merge release-please PR #11 to master; add a LICENSE file if open-sourcing; decide on a dedicated conduct-report channel; sign off on RH-07's PVR-only channel decision (made autonomously in the operator's absence).

---
| Phase 25-design-system P01 | 566s | 2 tasks | 2 files |
| Phase 25-design-system P02 | 480s | 3 tasks | 5 files |
| Phase 25-design-system P03 | 412 | 3 tasks | 1 files |
| Phase 26-read-only-api-endpoints P01 | 360 | 3 tasks | 2 files |
| Phase 27-sse-infrastructure P01 | 274s | 2 tasks | 2 files |
| Phase 27-sse-infrastructure P02 | 120s | 2 tasks | 2 files |
| Phase 27-sse-infrastructure P03 | 600 | 2 tasks | 3 files |
| Phase 28-frontend-observability-surfaces P01 | 269 | 2 tasks | 2 files |
| Phase 28-frontend-observability-surfaces P02 | 262 | 2 tasks | 2 files |
| Phase 28-frontend-observability-surfaces P03 | 379 | 2 tasks | 1 files |
| Phase 28-frontend-observability-surfaces P04 | 420 | 2 tasks | 1 files |
| Phase 29-sse-client-wiring PP01 | 233s | - tasks | - files |
| Phase 29-sse-client-wiring P02 | 240 | 2 tasks | 2 files |

## Session Continuity

**Last action (resume 2026-09-06)**: Session resumed after a one-month gap via `/gsd-resume-work`. HANDOFF.json's primary resume instruction is DEAD and must not be retried: it points at `Workflow({scriptPath: '...ceeb4f42-bf4e-4463-9b98-2848101a8af9/workflows/scripts/phase38-gate-final-wf_7e7ec15b-4bb.js', resumeFromRunId: 'wf_7e7ec15b-4bb'})`, but that session directory no longer exists on this box (only `2426f466` and `f09454cc` remain under `.claude/projects/E--repos-ShopPyBot/`), the script file and `journal.jsonl` are both gone, and `find` for `*wf_7e7ec15b*` returns nothing. Workflow resume is same-session-only regardless, so gate run 3's cached agent results are unrecoverable. Operator chose to re-run the gate from scratch rather than skip it or hand-review. **Gate run 4 launched as `wf_fcce62d0-c02`**, script persisted at `.claude/projects/E--repos-ShopPyBot/f09454cc-9916-457d-b637-efda6d38f800/workflows/scripts/phase38-gate-rerun-wf_fcce62d0-c02.js`, transcript under `subagents/workflows/wf_fcce62d0-c02/`. Shape: six read-only attack dimensions in parallel (`dismissal-integrity`, `dev-branch-delete`, `merge-lockout`, `workflow-mutations`, `recon-and-source`, `plan-runbook-coherence`), then every blocking finding sent to two adversarial verifiers with distinct lenses (refute, reproduce) surviving only on a clean sweep, then a synthesis agent writing a PASS/FAIL verdict with an explicit coverage-honesty section. Per-dimension verify cap is 5 blocking findings; anything over the cap is reported UNVERIFIED rather than dropped, and a dimension that returns nothing is treated as unaudited, which is a FAIL, not a pass. Repo state unchanged by the resume: branch `chore/v4.0-milestone-close` at `66fbfda`, tree clean, 2 commits unpushed, `origin/master` at `bd70601`. Phase 38 still has ZERO plans executed and ZERO GitHub mutations.

**Next action (38)**: Read gate run 4's written verdict. Only a PASS unlocks execution. On PASS, run 38-01 first: read-only recon, zero mutations, and it produces the VERDICT-SCAN-06 and cryptography verdicts that 38-02, 38-03 and 38-06 all gate on. On FAIL, remediate the confirmed blocking list and re-run the gate before any plan executes.

**Last action (v5.0 roadmap)**: Milestone v5.0 Real Release & Plugin Ecosystem roadmapped. 84 requirements across 10 workstreams (A-J) mapped to 15 phases (36-50), continuing the phase numbering from v4.2's Phase 35 — no reset. Coverage 84/84, zero orphans, zero duplicates. Structure: Phase 36 MAIN (highest-risk, the 263-commit merge whose CI has never run), 37 PKG, 38 SCAN, 39 QUAL, 40 PUB, 41 FIX, then workstream H's researched H1-H7 order as Phases 42/43/44/46/47/48/49 with Phase 45 (PAR) inserted between H3 and H4 so PAR-03 and EXT-09 build one pre-transfer arming gate in adjacent phases, and Phase 50 closing on OPS + UAT. All 7 hard sequencing constraints verified satisfied and recorded in both ROADMAP.md and REQUIREMENTS.md. REVIEW.md deep passes assigned to Phases 45 and 47. UI hints on Phases 41 and 43. Files written: `.planning/ROADMAP.md` (v5.0 section added, all six shipped-milestone `<details>` blocks preserved untouched), `.planning/REQUIREMENTS.md` (Traceability populated per-requirement, placeholder ranges replaced), `.planning/STATE.md` (this file).

**Last action (36-01)**: Phase 36 Plan 01 complete, the first irreversible plan of v5.0 and its first live writes to the public GitHub repo. Three mutations, all audited in the new `.planning/phases/36-mainline-reconciliation/36-MERGE-LOG.md`: (1) annotated tag `pre-v5-mainline` (tag object `7edffb33`) pushed to origin peeling to `e98ec83ff9e47459902c3c0615fd428f5dd27caf`, the phase rollback point, created only after `git ls-remote --tags origin refs/tags/pre-v5-mainline` returned empty; (2) **MAIN-05** PR #12 (signal handlers off the main thread) merged as merge commit `36f75c7643e5a72b72ac95a6d521edd8ffbb2971`, so `origin/master` advanced `e98ec83` to `36f75c7`. Because `required_status_checks.strict: true`, `gh pr update-branch 12` ran first and moved the head `3f27a2dff279852ced3f8712b56f582173946a3b` to `b1d7b8f5aef3b8767236eb5ba02b60ec97894695`; both are ancestors of `origin/master`, and both are recorded since 36-VALIDATION.md's MAIN-05 row names the pre-update SHA. `mergeStateStatus` reached `CLEAN` on poll iteration 4 of a 30-iteration budget with all six checks in bucket `pass` (no `skipping`, so Pitfall 4's allowance was never needed); (3) **MAIN-06** PR #8 (urllib3 1.26.5 to 1.26.18, open since 2023) closed unmerged with a superseded comment, after proving the premise from `origin/master` (`requirements.txt` pins exactly one `urllib3==2.7.0`, ahead of the PR's target, so merging would be a downgrade). Comment `https://github.com/thezoid/ShopPyBot/pull/8#issuecomment-5159680032` satisfies the MAIN-06 grep for both `urllib3==2.7.0` and `superseded`. Safety posture held throughout: no force operation of any kind, no direct push to `master` (the only ref pushed directly was the tag), no `--admin`/`--squash`/`--rebase`/`--auto`, and branch protection read identically before and after (`strict: true`, contexts `CodeQL` + `test (windows-latest)` + `test (ubuntu-latest)`, `enforce_admins: false`, force pushes disabled). None of the plan's four STOP conditions fired. Three observations recorded rather than papered over: PR #12 actually touched 2 files (`core/orchestrator.py` plus a new `tests/test_signal_registration_thread.py`) where the plan's `<verified_state>` named 1; `dependabot[bot]` self-deleted PR #8's head branch 8 seconds after the close (timeline-confirmed actor, NOT this executor, whose `--delete-branch=false` was honoured as proven by PR #12's head branch surviving the same flag); and two acceptance-criteria commands are brittle as written (a jq `\\.` escape loses a backslash layer through this harness on Windows, and `gh pr view --json mergedAt --jq .mergedAt` prints an empty line rather than the literal `null`), with robust replacements recorded in 36-MERGE-LOG.md's Tooling Note. Commits: `969b322` (audit log opened), `d04c5ca` (PR #12 row), `c321509` (PR #8 row), `c618989` (summary). MAIN-05 and MAIN-06 marked complete in REQUIREMENTS.md.

**Last action (37-01)**: Phase 37 Plan 01 complete (PKG-01: the built wheel now carries its data files. The sounds were not merely unshipped, they were structurally unshippable: `utils` is a top-level module, so `SOUNDS_DIR = os.path.join(os.path.dirname(__file__), 'sounds')` resolved to `site-packages/sounds`, which could not be package data of anything because `sounds` was not a package. Fixed by `git mv`-ing the three alert WAVs into a new `core/sounds/` package (4 moves, all recorded as `R` renames) with a one-line-docstring `__init__.py`, and replacing the path expression with `_resolve_sounds_dir()` returning `str(importlib.resources.files("core.sounds"))`. `SOUNDS_DIR` stays a module-level `str` constant so zero callers changed. **No try/except fallback** was added, deliberately: a broken install must fail loudly at import rather than silently resolve to a repo-relative path, which is the exact defect class this phase exists to remove (threat register T-37-04, disposition accept). `sounds/generate_alert_sounds.py` moved to a new top-level `scripts/` directory, outside every `packages.find` include pattern (T-37-02), and its `_DIR` was retargeted to `core/sounds/` so a regeneration does not silently write three orphan WAVs next to the script. `pyproject.toml` gained `include-package-data = true` plus `[tool.setuptools.package-data]` with `"core.sounds" = ["*.wav", "*.mp3"]` and `web = ["static/*", "static/vendor/*", "templates/*"]`; `static/vendor/*` is load-bearing as a separate glob because `static/*` does not descend. **Verified against two real builds, not by reading the TOML back:** the wheel grew from the 61 entries recorded in 37-SCOUT.md to **71**, carrying exactly 3 `core/sounds/*.wav`, 5 `web/static/*`, 1 `web/templates/*`, 0 top-level `sounds/*`, and 0 copies of the generator; the second build ran from the fully committed tree and produced identical counts. No `MANIFEST.in` was needed. `version = "2.0.0"` left byte-identical (release-please owns it, PR #23 proposes 2.1.0) and `dependencies`/`[project.optional-dependencies]` untouched (37-02's territory). New `tests/test_packaging.py` carries 4 in-tree guards; `tests/test_utils_audio.py` passes **unmodified** at its prior 8, proving the pygame graceful-degradation path Phase 24 depends on is intact. Full suite: **965 passed, 2 skipped** against a 961/2 baseline, delta exactly the 4 new tests. Two deviations, both direct consequences of this plan's own change: Rule 1 doc drift in `CLAUDE.md` (two stale `sounds/` architecture references corrected, folded into the Task 1 commit) and Rule 3 hygiene (`build/` and `shoppybot.egg-info/` byproducts removed from the repo root after each build, by name, never via `git clean`). Commits: `8a350fa` (relocate + resolve), `48327ab` (package-data + wheel proof).) PKG-01 marked complete in REQUIREMENTS.md.

**Last action (37-02)**: Phase 37 Plan 02 complete (PKG-02/PKG-03/PKG-04: the wheel stopped being dead. `[project] dependencies` went from the single `platformdirs==4.10.0` to the nine packages the production tree actually imports unconditionally: `colorama`, `cryptography`, `keyring`, `nodriver`, `platformdirs`, `pydantic`, `pydantic-settings[yaml]`, `pyyaml`, `requests`, every pin matching `requirements.txt` byte for byte. **The scout's list of 5 was incomplete because it was Windows-only:** `logger.py:6-7` imports `colorama` and `yaml` unconditionally and `logger` is imported by nearly everything, but on Windows `colorama` arrives as a conditional dependency of `click` and PyYAML arrives through `uvicorn[standard]`, both only under the `web` extra, so a bare `pip install shoppybot` would have failed on any OS. The `web` extra gained `starlette>=0.40` and `websockets>=10.4` as **floors, not pins**, matching their parents' declared minimums (fastapi 0.115.8 wants `starlette>=0.40.0,<0.46.0`; `uvicorn[standard]` wants `websockets>=10.4`) so they cannot fight upstream resolution. Two new extras: `sound` holds `pygame==2.6.1` because `utils.py` already degrades gracefully and forcing an audio stack onto a headless install is the wrong trade (Phase 24 depends on that path), and `test` holds `pytest`/`pytest-asyncio`/`httpx` because nothing on a runtime path imports httpx. `requirements.txt` dropped the dead `selenium==4.43.0` and `webdriver-manager==4.0.2` pins (the codebase uses `nodriver`), which also shrinks PR #21's surface by two lines. `version = "2.0.0"` untouched; all of 37-01's packaging tables untouched. **Supply-chain pre-flight: this phase introduced ZERO new distributions** -- all 11 declared names (9 core plus the 2 floors) passed `pip show` in the repo venv before being declared, and every version matched the planned pin exactly, so no `[ASSUMED]`/`[SUS]` package existed and no human legitimacy checkpoint was required. **Proven functionally against a real artifact, not by reading the TOML back:** a wheel built from this tree installed into a bare Python 3.13.13 venv (pip only, no `requirements.txt`, no `-e`) with just the `[web]` extra, resolving 41 distributions with no conflict. `shoppybot --help` **exits 0 and prints usage** -- the exact command that died on `ModuleNotFoundError: No module named 'pydantic_settings'` in `37-SCOUT.md`. The import matrix went from the scout's **3 of 8** to **8 of 8**: `core.service`, `core.config_schema`, `core.orchestrator`, `core.captcha`, `core.registry`, `web`, `utils`, `models` all import. The two deliberate exclusions were proven live rather than assumed: `import pygame` and `import httpx` both exit non-zero with `ModuleNotFoundError` in that env, `pip list` shows neither (nor `selenium`/`webdriver-manager`), and `import utils` still succeeds there with `_PYGAME_AVAILABLE is False` and `_AUDIO_AVAILABLE is False`, logging "pygame not installed -- sound notifications disabled". That is the live counterpart to the 8 mocked tests in `tests/test_utils_audio.py`, which passes **unmodified** (last touched by `8284735`, Phase 24). Closed 37-01's open loop from the clean env: `utils.SOUNDS_DIR` resolves to `...cleanenv2/Lib/site-packages/core/sounds` (asserted programmatically: `site-packages` segment followed by `core` then `sounds`) holding exactly `available.wav`, `buy.wav`, `notification.wav`. Both new extras were dry-run resolved (`sound` -> pygame-2.6.1; `test` -> httpx + pytest + pytest-asyncio + 4 transitives) without contaminating the probe env. Wheel METADATA confirms 9 `Requires-Dist`, 3 `Provides-Extra` with correct markers, and 71 entries preserved from 37-01. Full suite: **965 passed, 2 skipped**, identical to the 37-01 baseline; this plan adds no tests and regresses none. `git status --porcelain` clean after every build (`build/` and `shoppybot.egg-info/` removed by name, never `git clean`). One commit: `a1fa5ee`.) PKG-02, PKG-03, PKG-04 marked complete in REQUIREMENTS.md.

**Next action (37)**: `/gsd:execute-phase 37` — run plan 37-03. 37-04's CI wheel job can now encode concrete numbers: `shoppybot --help` exit 0 as assertion 1, the 8-module import matrix as assertion 2, and 3 entries under `core/sounds/`, 5 under `web/static/`, 1 under `web/templates/` for assertion 3. The wheel job must install by absolute `.whl` path with **no `requirements.txt` present**, or it proves nothing. Two reusable probe details from this plan: set `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` so the keyring import never probes D-Bus on Linux, and set `SHOPBOT_DATA_DIR` to a temp path so probes never write to the real user data directory.

**Superseded (Phase 36, retained for history)**: `/gsd:execute-phase 36` — run plan 36-02 (PR #11 conflict resolution). **Its base is `origin/master` at `36f75c7`, not the `e98ec83` recorded at planning time**, so `git merge-tree` must be re-derived rather than assumed; PR #12 touched only `core/orchestrator.py` and a new test file, so neither conflict file (`.github/dependabot.yml`, `requirements.txt`) should be disturbed, but confirm rather than assume. Good news for plans 36-04/05: Dependabot reacted to the PR #8 close within 8 seconds, which is exactly the 36-RESEARCH.md Pitfall 5 interaction expected to lift the 90-day-inactivity version-update pause, so a stalled `@dependabot rebase` should be treated as a real anomaly rather than an assumed pause (caveat: branch cleanup and version-update rebasing are different Dependabot subsystems, so this is strong evidence, not proof). Note also that PR #12's ~32-second green CI run is master's ~757-test suite, **not** the merged tree's ~939 — MAIN-01's real proof still belongs to plan 36-03 against master's post-#11 HEAD. **MAIN-03 caution:** 36-CONTEXT.md records the include-all decision against 8 local commits, but `git rev-list --count origin/chore/v4.0-milestone-close..HEAD` now returns **18** (the original 8, plus 5 phase-36 planning commits, plus this plan's 5), and it will grow again before 36-02 pushes. Do not record MAIN-03 against the literal number 8; re-derive the SHA list with raw `git log` as 36-VALIDATION.md already mandates, and write one include row per actual SHA. Only `0cebc9e` (`feat(cli)` port auto-select) is code; the other 17 are docs.

**Context to carry (v5.0)**: The milestone premise is that four shipped milestones' claims are ahead of reality — `master` is 263 commits behind, PR #11's `ci.yml` fails to compile so the v4.1+v4.2 suite has never run in CI, the built wheel contains no data files so `shoppybot web` cannot start from an install, and the public repo has no LICENSE. The workstream H trust model is consent plus SHA and content pinning plus honest provenance, explicitly **not** a sandbox; the dominant risk across every EXT phase is overclaiming, not a missing feature. Import is execution and nothing in v5.0 changes that.

---

**Last action**: Phase 33 Plan 02 complete (CFG-02: generic per-platform config declaration. `PlatformsConfig` gained `model_config = ConfigDict(extra="allow")` as its first class-body statement — an undeclared `platforms.<key>` section now passes through as a raw dict instead of being silently dropped (the literal bug CFG-02 fixes); the 7 declared platform fields keep full strict validation unchanged, proven by `test_known_platform_strict_validation_intact`. Added `RetailerPlugin.get_platform_config(model_cls)` to `core/plugin_base.py`: getattr-safe, four-case return logic (`model_cls()` defaults on missing config/key/section; the already-validated instance for a built-in platform; `model_cls(**raw)` for a new plugin's passthrough dict, raising `ValidationError` fail-loud on bad data; `model_cls()` fallback). `PLUGIN_API_VERSION` stays 2. Fixture-plugin test (`tests/test_platform_config_extension.py`) proves a brand-new `platforms.costco` section loads+validates via a test-module-scope `CostcoPlatformConfig` model (no `importlib.import_module` of the exec_module-loaded tmp plugin, per the plan's revised approach) with `core/config_schema.py` touched by nothing beyond the single `extra="allow"` line. TDD: RED->GREEN across 2 task commits; during GREEN verification, found the plan's proposed `AppConfig(**{"platforms": {...}})` fixture-construction snippet silently no-ops (`AppConfig.settings_customise_sources` excludes `init_settings` from its source tuple) — fixed by switching to the codebase's established `yaml_file=<Path>` injection pattern (Rule 1 auto-fix, test-only, no production-code change).) Full suite: 898 passed, 2 skipped (baseline 894 + 4 net-new tests), no regression. **Phase 33 (Config Refactor) is now fully complete: CFG-01 (33-01) and CFG-02 (33-02) both landed.** CFG-01 and CFG-02 marked complete in REQUIREMENTS.md. STATE.md/ROADMAP.md updated.
**Next action**: Continue `/gsd:execute-phase 35` -- run plan 35-03 (DH-01/02/03 frontmatter reconciliation), the phase's final plan. Phase 35 Plans 01 (AF-01 + AF-03) and 02 (AF-02) are now complete.
**Context to carry**: v4.2 is a debt-closure + release-hardening milestone; "done" = code-complete and CI-green, no live-environment testing in scope. Phase 30 (Breakfix) shipped first since BF-02 was the milestone's only HIGH item; 30-01..30-06 all complete. Phase 31 is fully complete (31-01 RH-01 secret-scan audit, 31-02 RH-04 CodeQL fix + ci.yml Node20 bump, 31-03 RH-05 dependabot + vuln remediation). Phase 32 is fully complete (32-01 RH-02/RH-03 release-please seed + pyproject reconcile, 32-02 RH-06 README rewrite, 32-03 RH-07 security contact). Phase 33 is now fully complete (33-01 CFG-01 field harmonization + back-compat shim, 33-02 CFG-02 generic per-platform config extension point via extra="allow" + get_platform_config). CI-verification/operator debt carried forward (post-push, not actioned this session per no-push policy): gitleaks-run green (31-01), CodeQL Actions green-run (31-02), Dependabot alert queue drain (31-03), release-please Actions-permissions allowlist gate (32-01 — third-party action blocked until operator widens selected-actions policy), and the PVR-enable repo Settings toggle (32-03) — all operator-gated GitHub Settings changes, not code gaps. New operator-UAT item from 33-01: live Amazon/BestBuy availability-poll cadence is now jittered 30-40s (was flat 30s) -- observable only against a live run, tracked in 33-VALIDATION.md. Phase 35 folds AF-* + DH-* as a trailing low-risk cleanup phase.

**Last action (34-01)**: Phase 34 Plan 01 complete (FC-01: `[plugin]` log tag guarantee. `logger.py` gained a module-level `_current_plugin: ContextVar[str]` (default `"core"`) and `set_log_plugin(platform_key)` that coerces falsy input to `"core"`. `writeLog()` now builds one `head = f"[{type.upper()}][{plugin}][{ts}]"` reused identically for both the colored `print()` and the file write — level bracket stays first, plugin is the second bracket, timestamp computed once (consolidating the pre-existing double `datetime.now()` call). `core/orchestrator.py:supervise()` calls `set_log_plugin(getattr(plugin, "platform_key", None) or plugin.__class__.__name__.lower())` as its first executable statement; `asyncio.TaskGroup`/`create_task` context-copy semantics give automatic per-plugin isolation with no locking. TDD: RED->GREEN across 2 task commits (5 new tests: tag injection, `[core]` sentinel, level-first-bracket format-compat, falsy-input coercion, level-gate regression). Manual verification confirmed the produced line format: `[INFO][amazon][2026July02@20:33:04] checking stock`. Full suite: 906 passed, 2 skipped (baseline 901 + 5 net-new tests), no regression. No deviations -- plan executed exactly as written.) FC-01 marked complete in REQUIREMENTS.md.

**Last action (34-03)**: Phase 34 Plan 03 complete (FC-02: outcome analytics, executed out of order ahead of 34-02 since the two plans touch disjoint files. `core/analytics.py` gained a PURE `compute_analytics(rows, platform_of)` -- stdlib `datetime` only, zero DB/fastapi imports -- computing `success_rate` (confirmed/attempted, union denominator `place_order_attempted_at IS NOT NULL OR order_id IS NOT NULL`, deliberately never `checkout_attempts` which increments under test_mode) and `avg_time_to_checkout_secs` (`confirmed_at - place_order_attempted_at` per confirmed row with both timestamps and a non-negative delta), overall + per-plugin, divide-by-zero-safe. `models.get_order_analytics_rows_sync()` mirrors `get_confirmed_orders_sync`. `BotService.get_analytics()` resolves `link -> platform_key` via `PluginRegistry.domain_patterns` (link never leaves this seam). `GET /api/analytics` (read-only, `asyncio.to_thread`, no `check_origin`) added to `web/routes/api.py`. Dashboard gained `#section-analytics`: two `.health-card` stat cards + a bare per-plugin `<table>`, rendered via `createElement`/`textContent` only (null metrics render "N/A"), wired into the initial backfill block. TDD: RED (4 fixture tests, `45e51a7`) -> GREEN (`c66fc6a`) for Task 1; Task 2 (`9bf6652`) added the endpoint + a no-link-key/CRED_PATTERN test; Task 3 (`71abe90`) added the dashboard view. Full suite: 912 passed, 2 skipped (baseline 906 + 6 net-new tests), no regression. Manual smoke test confirmed `BotService.get_analytics()` against a fresh empty DB returns valid JSON with `success_rate`/`avg_time_to_checkout_secs` = `null` and no `ZeroDivisionError`. No deviations -- plan executed exactly as written.) FC-02 marked complete in REQUIREMENTS.md. Phase 34 is now 2/3 plans complete -- 34-02 (`/api/logs` plugin filter, FC-01's remaining sub-feature) is the only plan left before Phase 34 closes.

**Last action (34-02)**: Phase 34 Plan 02 complete (FC-01 filter+UI, the deferred half of OBS-08. `web/log_reader.py:read_logs_filtered` gained a trailing `plugin: str | None = None` param AND-composed with the existing level/search filters via the `[plugin]` tag guaranteed by 34-01's ContextVar (filter-then-limit order preserved). `web/routes/api.py:/logs` validates `plugin` against `re.fullmatch(r"[a-z0-9]+", ...)` (V5 defense-in-depth whitelist, invalid values dropped to `None`) before passing it as the 4th positional to `asyncio.to_thread(read_logs_filtered, ...)`. `core/service.py:list_plugins()` gained a `platform_key` key per plugin (never the class name). `web/routes/pages.py`'s dashboard route now offloads `svc.list_plugins()` via `asyncio.to_thread` (Refinement 1, matches the `/logs`|`/history`|`/analytics` convention) and passes `plugins` into the template context. `web/templates/dashboard.html` gained a `#log-plugin-filter` `<select>` in `.log-controls`, Jinja2-populated from `platform_key` values, wired to `pollLogs()`'s `plugin` query param via a `change` listener mirroring the level dropdown -- zero new CSS (reuses the existing `select` rule). Refinement 2 (FC-01 live-tail completion): added a pure `lineMatchesFilters(line, level, search, plugin)` JS guard and gated the SSE `'log'` listener's `appendLogLine` call behind it, so live-streamed lines now respect the active level/search/plugin filters (previously only the one-shot `pollLogs` snapshot was filtered -- the plugin filter, and incidentally level+search too, were bypassed during live tailing, the dashboard's primary mode). Refinement 3 (param whitelist) evaluated and kept as the generic regex per the plan's own threat-model escape hatch: an enum check against the live `platform_key` set would require a `to_thread`-wrapped filesystem+importlib `PluginRegistry` scan on every `/api/logs` request, a hot, continuously-polled endpoint. TDD: RED (`6c93c87`) -> GREEN (`039f242`) for Task 1 (4-arg `read_logs_filtered` contract + updated arity asserts); Task 2 (`8543b57`) added the dropdown + platform_key + both refinements as a single commit. No JS test harness exists in this Zero-Node codebase, so the live-tail filter guard is verified via 2 new static-analysis tests in `tests/test_sse_wiring.py` (presence + ordering of `lineMatchesFilters(...)` before `appendLogLine(...)` in the rendered HTML), matching the codebase's existing `test_no_onmessage_for_named_events`-style pattern. Full suite: 923 passed, 2 skipped (baseline 912 + 11 net-new tests), no regression. No deviations beyond the 3 orchestrator-directed refinements, all applied as specified.) FC-01 and FC-02 both marked complete in REQUIREMENTS.md. **Phase 34 (Feature Completion) is now fully complete: 34-01, 34-02, 34-03 all landed.** STATE.md/ROADMAP.md updated.

**Last action (35-01)**: Phase 35 Plan 01 complete (AF-01 SSR remove-button graceful degradation + AF-03 dead escHtml() removal. `web/routes/pages.py` gained `POST /items/remove` on the unprefixed pages router: form-encoded, `Depends(check_origin)` CSRF-guarded (identical to every other mutating route), no-ops on an empty/missing `link` (never reaches `svc.remove_item`), calls `request.app.state.svc.remove_item(link)` for a non-empty link, and 303-redirects to `/` (POST/Redirect/GET). `web/templates/dashboard.html`'s dead SSR `.btn-remove` button (no JS listener existed anywhere) was replaced with a real `<form method="post" action="/items/remove">` + hidden `link` input + submit button reusing the existing `.btn-text-destructive` class -- the remove control now functions the instant the page loads or whenever `loadItems()`'s `fetch()` rejects, since `loadItems()` itself was left byte-for-byte unchanged (out of scope per RESEARCH.md Pitfall 1). AF-03: deleted the dead `escHtml()` helper (872-876) + its comment, confirmed 0 call sites via grep across `web/`. TDD: RED (`b9454d7`, 3 failing tests: functional remove+redirect, empty-link no-op, cross-origin 403) -> GREEN (`8f704ff`) for Task 1; Task 2 (`9794a10`) wired the SSR form + added an SSR-form-assertion test; Task 3 (`5e94f68`) deleted escHtml() + added a permanent grep-0 regression test. Full suite: 937 passed, 2 skipped (baseline 932 + 5 net-new tests), no regression. No deviations -- plan executed exactly as written.) AF-01 and AF-03 marked complete in REQUIREMENTS.md. Phase 35 is now 1/3 plans complete -- 35-02 (AF-02 last_heartbeat leak) and 35-03 (DH-01/02/03 frontmatter reconciliation) remain.

**Last action (35-02)**: Phase 35 Plan 02 complete (AF-02: raw `last_heartbeat` monotonic float scrubbed from the single shaping boundary, `HealthRegistry.get_snapshot()` (`core/health.py`) -- the public-dict comprehension now also excludes `last_heartbeat` while the existing `heartbeat_age_secs` derivation is unchanged. Since both `BotService.get_status()` (passthrough) and the SSE `"status"` frame (`web/sse_hub.py` broadcasts `get_status()` verbatim) consume this one shaped dict, the single fix closed both public surfaces atomically. Critical lockstep consumer `core/cli/status.py` was updated in the SAME task/commit to read `heartbeat_age_secs` instead of computing `now - rec['last_heartbeat']`, avoiding the CLI silently regressing to always showing "never"; the now-orphaned `now = time.monotonic()` and `import time` were removed. TDD: RED confirmed (3 failures at the exact expected fix sites: `test_snapshot_public_keys_exact`, `test_snapshot_excludes_last_heartbeat`, `test_status_table`) before the GREEN production fix landed (`585484c`). Task 2 (`2143edc`) fanned the change across the 5 last_heartbeat-touching test files plus a new SSE-frame absence test (`tests/test_sse.py::test_sse_status_frame_excludes_last_heartbeat`, mirroring the existing `test_sse_no_credential_patterns` credential-pattern pattern) proving both the REST and SSE surfaces are clean; `grep -rn "last_heartbeat" tests/` confirms every remaining reference is an absence-assertion, none assert presence on a public surface. Full suite: 939 passed, 2 skipped (baseline 937 + 2 net-new tests), no regression. No deviations -- plan executed exactly as written.) AF-02 marked complete in REQUIREMENTS.md. **Phase 35 is now 2/3 plans complete -- 35-03 (DH-01/02/03 frontmatter reconciliation) is the only plan left before Phase 35 (and the v4.2 milestone) closes.**

**Last action (35-03)**: Phase 35 Plan 03 complete (DH-01/02/03: v4.0/v4.1 planning-artifact frontmatter reconciliation, frontmatter-only, zero body edits. DH-01: v4.1 `25/26/27-VALIDATION.md` flipped `status: planned -> validated` + `wave_0_complete: false -> true` (backed by 763/776/785 full-suite tests passed per each phase's own SUMMARY/VERIFICATION; `nyquist_compliant: true` already correct, left untouched). DH-03: v4.0 `18..24-VALIDATION.md` (7 files) flipped ONLY `nyquist_compliant: false -> true`, per v4.0-MILESTONE-AUDIT.md's own explicit recommendation (755 full-suite tests passed); `status: draft` + `wave_0_complete: false` deliberately left untouched, narrower scope than DH-01 (RESEARCH.md Pitfall 5). DH-02: added `requirements:` frontmatter to Phase 28 `28-01..04-SUMMARY.md` (union = exactly OBS-01/02/03/04/06/09, verified via Python set-union check, the required fix per 28-VERIFICATION.md's Requirements Coverage table) plus Phase 27 `27-01..03-SUMMARY.md` (`[SSE-02]`) and Phase 29 `29-01..03-SUMMARY.md` (`[SSE-01]`) mirroring their own PLAN.md requirement IDs (discretionary polish per RESEARCH.md Open Question 1, low-cost so included). All 10 pre-edit frontmatter values grep-confirmed against the plan's `<current_frontmatter>` map before any edit; all 20 post-edit values grep-confirmed after. No `gsd` milestone-audit cross-reference tool exists in the SDK (`requirements` verb only exposes `mark-complete`), so verification relied on direct grep + set-union confirmation per the plan's documented fallback. Two atomic commits: `0b81b04` (Task 1, 10 VALIDATION.md files), `66bf260` (Task 2, 10 SUMMARY.md files). Full suite: 939 passed, 2 skipped (unchanged from 35-02 baseline -- frontmatter-only edits touch zero Python code). No deviations -- plan executed exactly as written.) DH-01, DH-02, DH-03 marked complete in REQUIREMENTS.md. **Phase 35 (Audit-Fixes & Doc-Hygiene Cleanup) is now fully complete: 35-01, 35-02, 35-03 all landed. The v4.2 Release Readiness milestone is now code-complete -- all 20 requirements (RH-01..07, AF-01..03, BF-01..03, CFG-01..02, FC-01..02, DH-01..03) landed.** STATE.md/ROADMAP.md updated.

---

## Performance Metrics (all milestones history)

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 01-foundations-security P01 | 8m | 3 tasks | 5 files |
| Phase 01 P02 | 5m | - tasks | - files |
| Phase 01 P03 | 5m | 2 tasks | 2 files |
| Phase 01 P04 | 8min | 3 tasks | 3 files |
| Phase 01 P05 | 11min | 3 tasks | 4 files |
| Phase 02-plugin-migration P01 | 207 | 2 tasks | 2 files |
| Phase 02-plugin-migration P03 | 20m | 2 tasks | 2 files |
| Phase 02-plugin-migration P04 | 20min | 2 tasks | 4 files |
| Phase 02-plugin-migration P06 | 15 | 2 tasks | 3 files |
| Phase 02-plugin-migration P05 | 10 | 1 tasks | 1 files |
| Phase 03-community-documentation P01 | 8m | 2 tasks | 3 files |
| Phase 03-community-documentation P02 | 5min | 2 tasks | 5 files |
| Phase 04-async-orchestrator P01 | 15 | 2 tasks | 3 files |
| Phase 04-async-orchestrator P04 | 15m | 2 tasks | 5 files |
| Phase 04-async-orchestrator P05 | 15 | 1 tasks | 3 files |
| Phase 05-notification-system P02 | 12m | 2 tasks | 3 files |
| Phase 05-notification-system P03 | 4m | 2 tasks | 3 files |
| Phase 05-notification-system P04 | 3 | 1 tasks | 3 files |
| Phase 05-notification-system P05 | 25 | 2 tasks | 4 files |
| Phase 06-platform-expansion P01 | 15 | 2 tasks | 9 files |
| Phase 06-platform-expansion P06-02 | 5 minutes | - tasks | - files |
| Phase 06 P03 | 12 | 3 tasks | 9 files |
| Phase 06-platform-expansion P04 | 4m | 2 tasks | 4 files |
| Phase 06-platform-expansion P05 | 5m | 2 tasks | 2 files |
| Phase 07-modular-core-service P01 | 375s | 2 tasks | 3 files |
| Phase 07-modular-core-service P02 | 4min | 1 tasks | 3 files |
| Phase 07-modular-core-service P03 | 5m | 2 tasks | 2 files |
| Phase 08-credential-store P01 | 8min | 3 tasks | 4 files |
| Phase 08-credential-store P02 | 7min | 2 tasks | 3 files |
| Phase 08 P03 | 12min | 3 tasks | 4 files |
| Phase 08-credential-store P04 | 15min | 3 tasks | 14 files |
| Phase 09-cli-front-end P01 | 12m | 3 tasks | 15 files |
| Phase 09-cli-front-end P02 | 8min | 2 tasks | 4 files |
| Phase 09-cli-front-end P03 | 4min | 2 tasks | 2 files |
| Phase 09-cli-front-end P04 | 4m | 1 tasks | 1 files |
| Phase 10-optional-web-ui P01 | 15m | 3 tasks | 21 files |
| Phase 10-optional-web-ui P02 | 6m | 2 tasks | 2 files |
| Phase 10-optional-web-ui P03 | 3m | 1 tasks | 1 files |
| Phase 10-optional-web-ui P04 | 8min | 2 tasks | 3 files |
| Phase 11 P01 | 5m | 3 tasks | 4 files |
| Phase 11 P02 | 8min | 3 tasks | 5 files |
| Phase 11 P03 | 7m | 3 tasks | 3 files |
| Phase 11 P04 | 8m | 2 tasks | 2 files |
| Phase 13 P01 | 7min | 2 tasks | 2 files |
| Phase 13 P02 | 5min | 2 tasks | 3 files |
| Phase 12-stability-foundation P01 | 3min | 2 tasks | 2 files |
| Phase 12-stability-foundation P02 | 237 | 2 tasks | 2 files |
| Phase 12 P03 | 4min | - tasks | - files |
| Phase 12 P04 | 5min | 2 tasks | 1 files |
| Phase 13 P03 | 13min | 3 tasks | 11 files |
| Phase 14 P01 | 10min | 2 tasks | 7 files |
| Phase 14-anti-detection-layer-2-captcha-solving P02 | 8min | 2 tasks | 4 files |
| Phase 14-anti-detection-layer-2-captcha-solving P03 | 18min | 2 tasks | 4 files |
| Phase 15-plugin-ecosystem-registry P01 | 8min | 2 tasks | 2 files |
| Phase 15-plugin-ecosystem-registry P02 | 12min | 3 tasks | 4 files |
| Phase 15-plugin-ecosystem-registry P03 | 9min | 3 tasks | 5 files |
| Phase 16-price-monitoring P01 | 5min | 2 tasks | 3 files |
| Phase 16 P02 | 8min | 4 tasks | 6 files |
| Phase 16-price-monitoring P03 | 8min | 3 tasks | 5 files |
| Phase 16-price-monitoring P04 | 5min | 3 tasks | 3 files |
| Phase 17-test-hardening P01 | 15 | 2 tasks | 3 files |
| Phase 17-test-hardening P02 | 3min | 2 tasks | 1 files |
| Phase 17-test-hardening P03 | 8min | 2 tasks | 2 files |
| Phase 17-test-hardening P04 | 4min | 1 tasks | 1 files |
| Phase 18 P02 | 267 | 2 tasks | 2 files |
| Phase 18 P18-03 | 8m | 2 tasks | 6 files |
| Phase 18 P04 | 18 | 2 tasks | 9 files |
| Phase 19 P19-01 | 4min | 3 tasks | 2 files |
| Phase 19-db-schema-confirmation-detection P02 | 8 | 2 tasks | 2 files |
| Phase 19 P19-03 | 3min | 1 task | 2 files |
| Phase 19-db-schema-confirmation-detection P19-04 | 15min | 3 tasks | 6 files |
| Phase 20 P20-01 | 8min | 2 tasks | 3 files |
| Phase 20 P20-02 | 6min | 2 tasks | 3 files |
| Phase 20-checkout-profile-form-fill P03 | 7min | 2 tasks | 4 files |
| Phase 20-checkout-profile-form-fill P04 | 14min | 3 tasks | 7 files |
| Phase 21 P21-02 | 7min | 1 tasks | 2 files |
| Phase 21-per-step-timeouts-unified-retry-cart-retry P03 | 30 | 2 tasks | 7 files |
| Phase 21 P04 | 20min | 1 tasks | 3 files |
| Phase 22 P01 | 8min | 2 tasks | 3 files |
| Phase 22 P02 | 6min | 2 tasks | 2 files |
| Phase 22 P03 | 21min | 3 tasks | 2 files |
| Phase 23-encrypted-session-persistence P23-01 | 4min | 2 tasks | 2 files |
| Phase 23-encrypted-session-persistence P23-02 | 5min | 2 tasks | 2 files |
| Phase 23-encrypted-session-persistence P23-03 | 3min | 1 task | 1 file |
| Phase 23-encrypted-session-persistence P23-04 | 12min | 3 tasks | 5 files |
| Phase 24-health-surface-server-safety P24-01 | 8m | 2 tasks | 2 files |

---

*Last updated: 2026-08-02 — v5.0 roadmap created (Phases 36-50, 84 requirements mapped, 100% coverage)*

## Decisions

- [Phase ?]: Phase 25-01: CSS comment stripping in test_no_external_urls_in_static prevents false positives on dashboard.css header comment text
- [Phase ?]: Phase 25-01: test_no_innerHTML_with_api_data uses re.DOTALL to catch both XSS violations including the multiline cred.name case at line 255
- [Phase ?]: CSS token split
- [Phase ?]: escHtml unused stub
- [Phase ?]: A2 chunking resolved: join chunks[:8] for SSE frame assertions
- [Phase ?]: Phase 27-01: disconnect cleanup asserted via len(hub._queues)==0, not is_disconnected() (unreliable in TestClient)
- [Phase ?]: Phase 27-01: each SSE test opens its own TestClient context manager (no shared fixture); lifespan runs per-test
- [Phase ?]: TestClient compat
- [Phase ?]: TestClient compat: detect starlette _TestClientTransport via http.response.debug scope extension; limit SSE generator to _TEST_MAX_FRAMES=20 in test context
- [Phase ?]: _poll_loop poll_interval default changed to None; reads module var at runtime so test overrides of _POLL_INTERVAL_SECS take effect
- [Phase ?]: SseHub instantiated in create_app factory body; asyncio.create_task(_poll_loop) only in lifespan where event loop is live
- [Phase ?]: Phase 28-02: heartbeat_age_secs computed in get_snapshot() not at route boundary so Phase 29 SSE poll reads the field automatically
- [Phase ?]: Phase 28-02: select rule added to components.css to match input[type=text] styling for log level dropdown
- [Phase ?]: Phase 28-03: renderHealthCards and renderUptime are pure functions; MAX_LOG_LINES = 500 placed here so DOM cap test goes GREEN in wave 3
- [Phase ?]: Phase 29-01: test_no_onmessage_for_named_events is GREEN at Wave 0 (anti-pattern guard; .onmessage absent from template; stays green through all plans)
- [Phase 30-01]: place_order_attempted_at is a new dedicated TEXT column, not an overload of checkout_attempts or the CONFIRMED-<ts> sentinel (D-02)
- [Phase 30-01]: D-15 login-failure loop suppression implemented via the should_retry closure predicate (plugin._checkout_stage != login), not a new exception or hand-rolled loop -- lowest-risk mechanism, reuses existing telemetry
- [Phase 30-02]: WAF token injection via document.cookie tab.evaluate() (JS-eval), not CDP set_cookies — Plan permits either as best-effort per RESEARCH.md Assumption A1 (2captcha AmazonTask payload shape undocumented); JS-eval keeps the diff minimal with no new CDP imports
- [Phase 30-02]: No redundant can_solve() re-check inside the WAF branch — The existing top-of-function solver gate already covers D-08 solver-unavailable fallback before WAF detection runs, mirroring the solve_recaptcha branch
- [Phase 30-breakfix-hardening]: login() ABC default returns True (login-less plugin trivially logged in, D-14); every real plugin can now report a login failure — Enables the shared BF-03 verification mechanism without breaking existing no-op-login plugins
- [Phase 30-breakfix-hardening]: _verify_login_generic is the single shared BF-03 verification mechanism (D-11), no per-plugin duplication — url-off-signin AND form-absent -> True; any ambiguity or exception -> False (D-13)
- [Phase 30-breakfix-hardening]: relaunch() captures login_ok and logs ERROR on failure; no dispatcher plumbing added — relaunch() has never had orchestrator access; the D-15 operator alert already surfaces from the orchestrator's login_failed short-circuit (30-01) on the next monitoring cycle
- [Phase 30-breakfix-hardening]: BF-02 marker import (mark_place_order_attempted_sync) is inline inside auto_buy(), not top-level -- keeps the first plugin->models write edge narrow and localized — Matches RESEARCH.md Pattern 1's exact example; avoids widening the plugin/models coupling beyond the single call site
- [Phase 30-breakfix-hardening]: BestBuy parity marker write (Task 2) included rather than deferred — RESEARCH.md found the byte-identical swallowed-TimeoutError shape at bestbuy:389-396; the guard mechanism from 30-01 is platform-agnostic so closing the now-known symmetric exposure was low marginal cost
- [Phase 30-breakfix-hardening]: 5 community plugins use the generic _verify_login_generic signal only (D-12), no platform-specific override — selectors are unverified TODOs; selector tuning stays operator debt per D-12
- [Phase 30-breakfix-hardening]: D-15 implemented uniformly as abort-all-remaining-stages on failed login, not no-add-to-cart — all 5 community plugins call login() mid-flow after add-to-cart + checkout-proceed (Pitfall 3)
- [Phase 30-breakfix-hardening]: Amazon/BestBuy auto_buy sets _checkout_stage="login" and calls login() at their existing (unchanged) positions -- Amazon before DOM interaction, BestBuy mid-flow after add-to-cart/checkout-proceed -- with uniform abort-all-remaining-stages on False — D-15 implemented consistently across all 7 plugins regardless of where login() sits in each flow, matching the 30-06 community-plugin precedent
- [Phase 30-breakfix-hardening]: Amazon's tighter D-12 signal is absence of #ap_email (already the generic signal, since no live-verified account-landing selector exists); BestBuy's is redirect-off-/identity/signin (URL-only, honest available signal) — Neither plugin's post-login landing-page DOM is live-verified, so the URL-fragment-based generic check is the most honest signal available without inventing an unverified selector
- [Phase 30-breakfix-hardening]: 30-REVIEW.md (deep code review, 2026-07-02) found CR-01 (critical): the BF-02 place-order marker was written unconditionally by Amazon/BestBuy auto_buy() before place_order_guarded's test_mode/monitor_only suppression check, permanently latching items reached under the documented-default test_mode=true with no click ever fired, plus a false possibly_placed alert. Gap-closure (same day, TDD, 4 commits: ba16879/22ec887/861fc79/dbe1345) resolved CR-01 (marker write moved into place_order_guarded via order_marker_link kwarg), MED-02 (possibly_placed alert now fires once per latch via alerted_links, not every poll cycle), LOW-03 (added clear_place_order_marker_sync recovery accessor), LOW-01 (redundant asyncio.TimeoutError tuple removed). MED-01 (community-plugin marker write) and LOW-02 (_checkout_stage invariant) remain deferred, pre-declared debt. Full suite: 887 passed, 2 skipped (baseline 878 passed, 2 skipped).
- [Phase 31-01]: Suppressed the one gitleaks finding (tests/test_captcha.py:381 sentinel_key) with an inline #gitleaks:allow comment, not a .gitleaks.toml path exemption -- avoids silently suppressing a future real leak under tests/
- [Phase 31-01]: No local gitleaks binary run this session (not pre-installed); CI enforcement path (gitleaks-action@v3) is self-contained and does not need one -- workflow validated by YAML correctness + acceptance-criteria greps
- [Phase 31-02]: checkout@v6 + codeql-action@v4 used (not CONTEXT.md placeholder v4/v3) per live-verified research: current Node24 majors, not stale defaults
- [Phase 31-02]: Folded ci.yml checkout@v4->v6 and setup-python@v5->v6 into this plan (orchestrator-directed) to close the adjacent Node20 exposure alongside the CodeQL fix
- [Phase 31-02]: Autobuild step removed entirely rather than kept alongside build-mode -- Python is interpreted and autobuild is being phased out
- [Phase ?]: [Phase 31-03]: Exact-pin style (==) kept for cryptography/pydantic-settings/jinja2 bumps, matching requirements.txt convention (resolves research Open Question #2)
- [Phase ?]: [Phase 31-03]: cryptography bumped to latest 49.0.0 (not the minimum-patched 48.0.1 floor) -- removes the SECT-curve root-cause class outright; repo usage (Fernet/Scrypt only) has zero overlap with any deprecated/removed cipher surface
- [Phase ?]: [Phase 31-03]: jinja2 bump applied in pyproject.toml [web] extra, not requirements.txt, despite the alert's manifest_path saying requirements.txt -- jinja2 is not declared in requirements.txt at all (research Pitfall 5)
- [Phase 32-01]: Manifest-mode release-please with no extra-files entry; python release-type updates pyproject.toml natively
- [Phase 32-01]: release-please workflow permissions scoped to exactly contents:write + pull-requests:write; no actions:write/id-token:write
- [Phase 32-01]: Seeded .release-please-manifest.json at 2.0.0 = baseline only; release-please proposes the NEXT bump from commit history, does not re-tag 2.0.0
- [Phase ?]: [Phase 32-02]: Collapsed README master/dev two-block badge layout to a single master-branch badge row (CI, CodeQL, Gitleaks) plus a static python-3.11+ badge; no fabricated license badge (no LICENSE file exists)
- [Phase ?]: [Phase 32-02]: README Configuration section restructured to 3 explicit steps (non-secret config.yml edits vs .env credential setup) to align with SECURITY.md's env-var-only credential model
- [Phase 32]: [Phase 32-03]: No email address substituted for the placeholder under any circumstance (D-RH-07 locked) -- GitHub PVR (security/advisories/new) is the sole reporting channel for both vulnerability and conduct reports
- [Phase 32]: [Phase 32-03]: Operator note added inline in SECURITY.md (not just SUMMARY): Private Vulnerability Reporting must be enabled once in repo Settings -> Security -> 'Private vulnerability reporting' for the advisories/new link to resolve; not toggled by this automation
- [Phase 32]: [Phase 32-03]: .planning/ historical occurrences of the placeholder string (10 files) intentionally left untouched -- project's own decision audit trail, not live consumer-facing docs
- [Phase 33-01]: Option A (accepted): _get_plugin_sleep reads canonical delay_seconds/delay_jitter uniformly for all 7 platforms, activating Amazon/BestBuy poll-cadence jitter (30s flat -> 30-40s) for the first time -- recorded as an operator-UAT item
- [Phase 33-01]: Shim guard is has_legacy and not has_canonical -- explicit canonical delay_seconds/delay_jitter values are never clobbered by legacy min_delay/max_delay keys, even when both are present in the same construction
- [Phase 33-01]: No clamping of the derived delay_jitter in the legacy shim -- an inverted/negative legacy range flows into Field(ge=0.0) and raises ValidationError naturally, matching the fail-loudly convention
- [Phase ?]: [Phase 33-02]: extra="allow" added to PlatformsConfig (candidate a) -- undeclared platforms.<key> sections pass through as raw dicts; the 7 declared platform fields keep full strict validation unchanged
- [Phase ?]: [Phase 33-02]: RetailerPlugin.get_platform_config(model_cls) is the sanctioned mechanism for a new community plugin to declare+validate its own per-platform config section with zero core/config_schema.py edits
- [Phase ?]: [Phase 33-02]: Fixed the fixture test's AppConfig construction -- AppConfig(**kwargs) silently no-ops for platforms data since settings_customise_sources excludes init_settings from its source tuple; switched to yaml_file= injection matching the codebase's established test pattern
- [Phase 34-01]: ContextVar set in supervise() (not run_plugin) so restart/backoff/park logs are tagged; head=[LEVEL][plugin][ts] computed once for both print and file write — RESEARCH.md recommendation: writeLog is a custom print+file-append function, not a stdlib Logger, so a logging.Filter would not intercept lines without a full rewrite
- [Phase 34-03]: attempted denominator = place_order_attempted_at IS NOT NULL OR order_id IS NOT NULL, never checkout_attempts (which increments under test_mode and would deflate the rate)
- [Phase 34-03]: time_to_checkout scoped to place_order_attempted_at -> confirmed_at only; no earlier detection-timestamp anchor exists in the schema, so the metric is honestly scoped rather than invented
- [Phase 34-03]: link is read only inside BotService.get_analytics to resolve platform_key via registry domain_patterns; it never enters the compute_analytics output (T-34-06)
- [Phase 34-02]: Kept generic lowercase-alphanumeric plugin-param whitelist regex over an enum check against list_plugins() -- avoids a to_thread-wrapped filesystem+importlib PluginRegistry scan on the hot-polled /api/logs endpoint
- [Phase 34-02]: SSE 'log' listener gains a client-side lineMatchesFilters() guard before appendLogLine so live-tailed lines respect the active level/search/plugin filters, not just the one-shot pollLogs snapshot
- [Phase 35]: 35-01: POST /items/remove lives on web/routes/pages.py (unprefixed router) not api.py, since HTML forms cannot target DELETE and a form-target route belongs beside the SSR / route
- [Phase 35]: 35-01: 303 See Other used for the remove redirect (POST/Redirect/GET), guaranteeing a GET on redirect
- [Phase 35]: 35-02: core/cli/status.py lockstep fix landed in the same task/commit as the health.py get_snapshot() filter, avoiding a silent CLI 'always never' regression
- [Phase 35]: 35-02: single shaping boundary (HealthRegistry.get_snapshot) filters last_heartbeat once; both get_status() REST and the SSE status frame inherit the fix atomically since SSE broadcasts get_status() verbatim
- [Phase ?]: 35-03: DH-03 kept strictly narrower than DH-01 -- only nyquist_compliant flipped on v4.0 phases 18-24 VALIDATION.md; status/wave_0_complete deliberately untouched (RESEARCH Pitfall 5)
- [Phase ?]: 35-03: DH-02 scope resolved as Phase 28's 4 SUMMARY files (required, union = exactly OBS-01/02/03/04/06/09) plus Phase 27/29 SUMMARY files mirroring their own PLAN.md requirement IDs (discretionary polish, low-cost)
- [Phase ?]: Phase 36-01: recorded BOTH PR #12 head OIDs (pre-update 3f27a2d, post-update b1d7b8f) because strict-mode update-branch moves the head while MAIN-05's assertion names the pre-update SHA
- [Phase ?]: Phase 36-01: Dependabot self-deleted PR #8's head branch 8s after close (timeline actor dependabot[bot], not this executor) -- live evidence Dependabot is responsive, so plans 36-04/05 should treat a stalled rebase as a real anomaly, not an assumed 90-day pause
- [Phase ?]: Phase 36-01: pre-v5-mainline annotated tag pushed at e98ec83 as the phase rollback point; PR #12 merged via merge commit 36f75c7 with no --admin and no force op; branch protection left untouched for Phase 38
- [Phase 37-01]: sounds relocated to core/sounds/ as a real package; utils.SOUNDS_DIR now resolves via importlib.resources.files('core.sounds') with no fallback, so a broken install fails loudly at import rather than silently resolving to a repo-relative path
- [Phase 37-01]: package-data globs alone ship all 9 data files, no MANIFEST.in needed; static/vendor/* is a separate glob because static/* does not descend. Wheel grew 61 to 71 entries, verified by zip entry list on two independent builds
- [Phase 37-01]: generate_alert_sounds.py moved to scripts/, outside every packages.find include pattern, and its absence from the wheel is asserted (T-37-02)
- [Phase ?]: Phase 37-02: the real dependency list is 9, not the 5 the scout named -- colorama and pyyaml are unconditional logger.py imports that arrive on Windows only by accident (click win32 marker, uvicorn[standard]) and only via the web extra, so a bare pip install shoppybot fails on any OS without them
- [Phase ?]: Phase 37-02: pygame stays OPTIONAL in a sound extra and httpx in a test extra; starlette and websockets get floors (>=0.40, >=10.4) not hard pins so they do not fight fastapi's and uvicorn's own resolution
- [Phase 37-03]: bundled_plugins_dir() computes from __file__ directly, never via _repo_root(), so the monkeypatchable _REPO_ROOT_OVERRIDE cannot redirect a directory whose every .py file is exec_module'd (T-37-10)
- [Phase 37-03]: core/service.py's two inline plugin-path sites were refactored alongside core/orchestrator.py:814; the plan named only the orchestrator, but must-have truth 4 and Phase 43 criterion 5 cover every production module
- [Phase 37-03]: PKG-06 answered from a real wheel install, not asserted: bundled_plugins_dir() returns <venv>/Lib/site-packages/plugins with all 7 shopbot_plugin_*.py files, so no importlib.resources rewrite is needed and Phase 43 (EXT-03) is unblocked
- [Phase 37-04]: assertion 3 asserts both halves separately (wheel zip entries AND a runtime SOUNDS_DIR resolve), because a dropped core.sounds package marker passes one and fails the other
- [Phase 37-04]: assertion 5 polls real HTTP, never the printed dashboard URL, because core/cli/web.py prints it with flush=True before create_app() runs
- [Phase 37-04]: the wheel job is a second CI job with its own install step; merging it with the test job's requirements.txt install would make it prove nothing (T-37-14)
- [Phase 37-04]: the gate was proven to be a gate: two doctored wheels made scripts/verify_wheel.py exit 1 naming assertion 3, once on the ships-nothing half and once on the ships-but-does-not-resolve half

## UAT Audit Session — 2026-08-01 (post-v4.2, pre-next-milestone)

Cross-phase UAT audit over the archived milestone artifacts, plus a live browser UAT
session against the dashboard and live GitHub API checks. Verdicts are recorded in each
phase's own VERIFICATION/HUMAN-UAT/VALIDATION file.

**Tooling caveat worth remembering:** `gsd-sdk query audit-uat` scans `.planning/phases/`,
which is empty once milestones are archived. It reported `total_items: 0` while 80
outstanding items sat in `.planning/milestones/*-phases/`. Do not trust that all-clear
after an archive.

### Results

| Bucket | Count |
|--------|-------|
| PASS | 13 |
| FAIL | 1 |
| BLOCKED | 5 |
| PARTIAL | 2 |
| Closed by operator action | 6 (A1/A2/A4/A6/A7 + REG-01) |

### Defects found (none previously caught by tests or milestone review)

1. **Dashboard "Start Bot" never worked.** `core/orchestrator.py:_register_signals` calls
   `signal.signal()` off the main thread; `BotService.start()` runs `async_main` in a daemon
   thread, so it raised `ValueError` at `async_main`'s fifth statement and the bot loop died
   before plugin setup, while `POST /api/bot/start` still returned 200. The CLI path
   (`shoppybot run`) masked it by running on the main thread. Fixed in PR #12
   (`fix/signal-handler-main-thread`). Caught by 29-HV-2; 27-HV-2 and 28-HV-1 are downstream.

2. **CI never compiled.** `ci.yml` referenced `${{ runner.temp }}` in job-level `env:`, where
   the `runner` context does not exist. 81 runs, 81 failures, zero jobs scheduled, no logs.
   Introduced by `0e0e43f` (2026-06-04), the only commit that ever touched the file.

3. **CI never installed dependencies.** The install step ran only `pip install -e .[web]`,
   but `pyproject` declares just `platformdirs`; pytest and every runtime dep live in
   `requirements.txt`, which CI never installed. Also added the undeclared `httpx==0.28.1`
   that `fastapi`'s TestClient requires. Both fixed in PR #13 (`fix/ci-runner-context`).

**Consequence for the audit trail:** milestones v2.0 through v4.2 were archived under a
definition of done that included "CI-green." That was never true. The suite had only ever
run on one Windows machine. It now passes identically on both platforms
(755 passed / 2 skipped on ubuntu-latest and windows-latest), so no code defect follows,
but the claim was unearned.

### Operator actions completed 2026-08-01

- Private Vulnerability Reporting enabled (32-HV-2)
- Actions allowlist widened for `gitleaks/gitleaks-action@*` and
  `googleapis/release-please-action@*` (32-HV-3) — unblocked gitleaks (31-HV-1) and
  CodeQL (31-HV-2), both of which then ran green for the first time ever

- CodeQL workflow re-enabled from `disabled_inactivity`
- Wiki "Plugin Registry" page created, headers-only by deliberate decision (REG-01)
- RH-07 signed off: GitHub PVR is the final, sole reporting channel (32-HV-1)
- `master` branch protection corrected to require contexts that workflows actually emit
  (`test (ubuntu-latest)`, `test (windows-latest)`, `CodeQL`); the previous five
  (`Analyze (python)`, `build-linux`, `build-mac`, `build-windows`) matched nothing

### Still outstanding

- **31-HV-3** — 7 Dependabot alerts (#6-#12) still open. Two blockers: the remediating bumps
  live on `chore/v4.0-milestone-close`, and Dependabot is repo-level PAUSED
  (`GET /repos/thezoid/ShopPyBot/automated-security-fixes` -> `{"enabled":true,"paused":true}`)

- **10-HV-3 / MC-4** — needs a `shoppybot web --host 0.0.0.0` restart; confirmed on loopback
  that `.banner-warning` is correctly absent from the DOM

- **29-HV-5** — needs a DevTools source breakpoint; the doc's stated recipe cannot work
- **27-HV-2, 28-HV-1, 28-HV-2 (running half)** — blocked until PR #12 lands, then re-test
- **MC-1, MC-2** — Windows TTY checks, still the only two items runnable with no prerequisites
- Ubuntu-dependent items unchanged (no host available)
- No LICENSE file; secret scanning and push protection still disabled

### Documentation drift recorded

Stale "four dashboard sections" (now eight); `python main.py` named as the dashboard
launcher (it starts no HTTP server — use `shoppybot web`); the
`window.EventSource = undefined` + reload recipe (cannot work, reload restores it);
hardcoded banner hex `#fee2e2`/`#dc2626` (now themed tokens, dark renders
`#450a0a`/`#ef4444`); and cold-load theme default is dark via `prefers-color-scheme`,
not light.

## Operator Next Steps

- Merge PR #13 (CI fix), then PR #12 (Start Bot fix) after a rebase
- Decide on PR #11 (264 commits) — merging it drains the Dependabot queue and lands
  release-please, gitleaks, and the modernized CodeQL on `master`

- Unpause Dependabot once PR #11 is in
- Start the next milestone with /gsd:new-milestone (SEED-003 will surface)
