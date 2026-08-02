# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v4.0 — Win-the-Drop

**Shipped:** 2026-06-25
**Phases:** 7 (18-24) | **Plans:** 29 | **Suite:** 755 passed, 2 skipped

### What Was Built
- Safety gate: monitor-only mode + `place_order_guarded()` ABC closing the 6-of-7 `test_mode` place-order hole (P18).
- Verified checkout: order-confirmation detection + `order_id`/`confirmed_at`/`checkout_attempts` columns — `purchased` only on a real order number (P19).
- Checkout profile + BestBuy/Amazon form-fill, CVV-at-runtime, no card data persisted (P20).
- Unified `RetryPolicy` + per-step `asyncio.timeout()` + idempotent cart-retry (P21).
- Per-coroutine supervisor + browser relaunch + DB read isolation + per-item timeout + SIGTERM/SIGINT bridge (P22).
- Fernet-encrypted session persistence via raw CDP restore, bypassing the nodriver `set_all()` bug (P23).
- Health surface (`HealthRegistry`, `get_status`, `health_degraded` alert, `shoppybot status`) + headless pygame crash guard (P24).

### What Worked
- **Foundation phase first.** P18 (safety gate + `CheckoutConfig`) had "do first, all downstream depend on it" — every later phase could be built and tested with live orders suppressed by monitor-only. No phase risked a real purchase during development.
- **Single enforcement points.** One `place_order_guarded()` on the ABC (not per-plugin patches) and one `RetryPolicy` (not per-call-site loops) — both backed by CI guards (grep/AST) that fail the build on regression.
- **Idempotency designed before its consumer.** P19 added the `order_id` anchor; P21's cart-retry read it. Designing the anchor a phase ahead of the retry that needs it avoided a double-buy redesign.
- **Clean integration close.** Integration checker verified all 6 cross-phase seams with 0 blockers; PLUGIN_API_VERSION stayed 2 (all additions additive).

### What Was Inefficient
- **Live UAT can't run on the dev box.** 17 live-environment items (confirmation/form-fill/relaunch/SIGTERM/session/headless selectors + scenarios) accumulated as deferred debt. Correct per policy, but the real acceptance bar for an acquisition bot is a live drop, which CI/dev can't exercise.
- **STATE.md drifted stale.** It froze mid-Phase-23 (status "verifying", phase table showing 18-21 "Not started") while ROADMAP.md stayed authoritative. At milestone close this forced a desync diagnosis before any action was safe.
- **ROADMAP Phase Details not pruned at v3.0 close.** Archived v3.0 phases 12-17 left full detail in the live ROADMAP, so `roadmap.analyze` false-positived them as incomplete `no_directory` phases — which would have driven an autonomous run to "re-execute" already-shipped work.

### Patterns Established
- **Foundation-phase-first** for any milestone that touches a dangerous action (place-order): ship the gate before the feature.
- **Confirmed-outcome idempotency**: never treat a UI action as success; capture a retailer-side identifier and gate retries on it.
- **Security invariants as CI guards**: AST assertion (no CVV in `writeLog` args), grep assertion (no `for attempt in range(` outside `core/retry.py`), zero-write integration test under monitor-only.
- **Explicit UAT-debt ledger** in STATE.md Deferred Items — live checks that can't run in CI are tracked, not silently dropped.

### Key Lessons
1. **Prune ROADMAP "Phase Details" at every milestone close.** Leaving archived-milestone detail in the live ROADMAP desyncs `roadmap.analyze` and can mislead a future autonomous run. (Fixed this close: live ROADMAP now collapses to per-milestone `<details>` only.)
2. **Keep STATE.md in sync, or treat ROADMAP as the sole source of truth.** A stale STATE.md cost a diagnosis step at close. Prefer reconciling STATE at phase transitions.
3. **Design idempotency anchors one phase ahead of the retry that reads them** — it removes rework and closes the double-buy window by construction.

### Cost Observations
- Model mix: not tracked this milestone.
- Notable: milestone closed via `/gsd-autonomous` lifecycle tail after the phase work + audit were already complete; the run's main value was catching the ROADMAP/STATE desync before executing anything.

---

## Milestone: v4.1 — Dashboard & Observability

**Shipped:** 2026-06-30
**Phases:** 6 (25-29 + inserted 29.1) | **Plans:** 20 | **Suite:** 807 passed, 2 skipped

### What Was Built
- Zero-Node vendored design system: 3-file CSS split (tokens/components/dashboard), light/dark with FOUC-safe inline `<head>` theming, uPlot 1.6.32 vendored, `loadItems()`/`loadCredentials()` XSS fix (P25).
- Read-only observability REST endpoints (`/api/history`, `/api/price-history/{link_b64}`, filtered `/api/logs`), all `asyncio.to_thread`-wrapped, `last_error` scrubbed, credential-leak CI guard (P26).
- SSE infrastructure: single `/api/events` stream, uvicorn `_poll_loop` sole-producer cross-thread bridge, keepalive, disconnect cleanup, cursor log tail (P27).
- Four observability surfaces: per-plugin health cards, confirmed-buys table, per-item uPlot price charts with empty-state, filterable color-coded log viewer (follow + 500-cap), uptime bar (P28).
- SSE client wiring: `EventSource('/api/events')` replaces the 2s poll, named listeners, polling fallback, Live/Reconnecting indicator (P29); inserted 29.1 closed 3 audit warnings (uPlot load order, log-dedup, SSE stall watchdog + REST fallback).

### What Worked
- **Spike-first on the highest-risk phase.** P27 (SSE) was flagged highest-risk up front and validated the lifespan + `asyncio.create_task` + `SseHub` wiring before full build. The cross-loop race (the known pitfall) never materialized because the "uvicorn `_poll_loop` is the sole producer; bot thread never touches `asyncio.Queue`" rule was designed in, not retrofitted.
- **RED test scaffold per phase.** Each phase opened with a Wave 0 failing-test scaffold (TestClient static-template assertions for the frontend phases), so GREEN was a concrete target and regressions were guarded.
- **Audit-driven cleanup loop.** The 2026-06-28 audit surfaced 4 integration warnings; rather than ship them as raw debt, an inserted Phase 29.1 closed 3 of them with file:line-verified fixes and 5 new tests, and the milestone-close audit refresh confirmed it. The bot's own audit fed the next unit of work.
- **Zero-Node discipline held.** No package.json, no CDN, no external fonts; charting solved by vendoring a tiny MIT lib and raw `StreamingResponse` covered SSE with no new Python deps.

### What Was Inefficient
- **Inserted decimal phase had no top-level ROADMAP checkbox.** Phase 29.1 was complete on disk (4/4 plans + summaries) but `roadmap.analyze` reported `roadmap_complete:false` because the parser keys on a `- [x] ... Phase 29.1` list item the inserted section never got. An autonomous run would have tried to re-execute it; this close had to add the checkbox first.
- **SUMMARY `requirements` frontmatter missing on P27/28/29.** Those plan summaries omit the `requirements` field (P28 uses none; P27/29 use `dependency_graph`), so the milestone audit's 3-source cross-reference dropped 6 OBS reqs to "partial (manual-verify)" even though every one was VERIFIED in the phase VERIFICATION tables. A metadata gap created audit noise, not a delivery gap.
- **VALIDATION.md status fields lagged.** Phases 25/26/27 still carry `status: planned` / `wave_0_complete:false` despite GREEN suites; 28/29 needed an explicit post-exec flip. The nyquist flag was true, but the doc-status fields drifted from reality.
- **16 live-UAT items can't run in CI.** SSE/EventSource behavior and visual rendering need a real browser/live socket; correct to defer, but the true acceptance bar (live dashboard) is unexercised by automated tests.

### Patterns Established
- **Spike-first for the highest-risk infra phase**, with the concurrency invariant (single producer, no cross-thread queue access) designed before implementation.
- **Audit → insert cleanup phase → re-audit** as a closing loop: convert non-blocking audit warnings into a scoped decimal phase rather than shipping them as raw debt.
- **Static-template TestClient assertions** as the RED scaffold for no-Node frontend phases (assert on the served HTML/JS), keeping frontend behavior test-guarded without a browser.

### Key Lessons
1. **Give inserted decimal phases a top-level ROADMAP checkbox at insertion time** (`- [ ] **Phase N.M: ...**`), so `roadmap_complete` tracks them and a future autonomous run does not re-execute finished work.
2. **Put `requirements:` in every plan's SUMMARY frontmatter.** The milestone audit cross-references it as one of three sources; omitting it manufactures "partial" statuses for fully-delivered requirements.
3. **Flip VALIDATION.md status post-execution, not just the nyquist flag** — stale `status: planned` on a GREEN phase reads as incomplete to anyone (or any tool) scanning frontmatter.

### Cost Observations
- Model mix: not tracked this milestone.
- Notable: the close ran the audit refresh with two parallel subagents (integration checker + verification aggregator), then synthesized; faster than serial reading and kept the main context lean.

---

## Milestone: v4.2 — Release Readiness

**Shipped:** 2026-07-03
**Phases:** 6 (30-35) | **Plans:** 20 | **Tasks:** 45 | **Suite:** 940 passed, 2 skipped

### What Was Built
- Breakfix hardening: place-order-timeout double-buy latch (`_PossiblyPlaced` marker + guard, HIGH), Amazon WAF auto-solve via the existing 2captcha path with manual-pause fallback preserved, real post-login DOM/URL verification (`_verify_login_generic`) rolled out to all 7 plugins (P30).
- CI & security infrastructure: gitleaks secret-scan CI job + local guard test, repaired CodeQL workflow (retired Node16 actions bumped to `checkout@v6`/`codeql-action@v4`), `.github/dependabot.yml` + all 7 open vulnerability alerts remediated (P31).
- Release automation & community readiness: `pyproject.toml` reconciled to 2.0.0, release-please seeded (manifest-mode, python release-type), README rewritten, SECURITY.md/CODE_OF_CONDUCT.md routed through GitHub Private Vulnerability Reporting (P32).
- Config refactor: canonical `delay_seconds`/`delay_jitter` fields with a legacy back-compat shim; generic per-platform config extension point (`PlatformsConfig(extra="allow")` + `RetailerPlugin.get_platform_config()`) (P33).
- Feature completion: `[plugin]` log tag on every log line + `/api/logs` plugin filter (completes OBS-08); outcome analytics (success-rate, time-to-checkout) over confirmed-order records (P34).
- Audit-fixes & doc-hygiene: SSR remove-button graceful degradation, `last_heartbeat` leak scrubbed from `get_status()`/SSE, dead `escHtml()` removed, v4.0/v4.1 planning-artifact frontmatter reconciled (P35).

### What Worked
- **Deep code review after verification caught real bugs twice.** A dedicated REVIEW.md pass (distinct from VERIFICATION.md) found and the executor fixed a genuine CRITICAL regression in both P30 (BF-02's marker was originally written before the `test_mode`/monitor_only suppression check — would have permanently latched any item reached under the documented `test_mode:true` default) and P35 (`POST /items/remove` crashed with an unhandled 500 on a malformed multipart field). Both were confirmed fixed by the milestone audit, both covered by dedicated regression tests.
- **Single shared mechanisms held the line again.** `_verify_login_generic` (one login-verification path for all 7 plugins instead of 7 bespoke checks), the single `get_snapshot()` shaping boundary that fixed `last_heartbeat` for both `get_status()` and SSE atomically, and `get_platform_config()` as the one sanctioned per-plugin config-extension mechanism — DRY held under a milestone that touched every plugin file.
- **Debt-inventory-driven milestone scoping.** An exhaustive automated sweep (64 raw findings → 20 code-actionable requirements) converted a loose backlog of seeds/breakfixes/audit-warnings/deferred-subfeatures into a boundaried, closeable milestone with a clean "code-complete + CI-green, live-UAT stays operator debt" definition of done.
- **Sequencing by risk and dependency paid off.** BF-02 (the one HIGH item) shipped first in Phase 30 to close the longest-standing exposure earliest; Phase 31 (CI security) landed before Phase 32 (release-please) so release automation tagged against a working CI signal.

### What Was Inefficient
- **The milestone's own Nyquist frontmatter lag was not self-applied.** Phase 35 (DH-01/DH-03) reconciled stale `VALIDATION.md` flags for OLDER phases (v4.0 18-24, v4.1 25-27) — but the audit found all 6 of v4.2's own phase `VALIDATION.md` files still read `status:draft` / `nyquist_compliant:false` at audit time, the exact same staleness pattern the milestone itself was closing for others. Doc-hygiene work should include a final pass over the current milestone's own phases, not just older ones.
- **An autonomous policy decision (RH-07) needed explicit operator sign-off.** Resolving the security-contact requirement to "GitHub PVR only, no email" is a reasonable default, but it is a scope/policy call made in the operator's absence — surfaced correctly as tech debt by the audit, but a reminder that CLAUDE.md's approval-gate rule applies to policy substitutions, not just code changes.
- **Real residual risk was accepted, not just deferred, in one place.** BF-02's marker only covers Amazon + BestBuy this milestone; the 5 community plugins remain exposed to the identical double-buy mechanism the HIGH item was created to close. The scope cut was deliberate and pre-declared (all 5 plugins are independently EXPERIMENTAL/selector-unverified), but it is the one item in this milestone that reads as "should not stay open indefinitely" rather than ordinary live-UAT debt.

### Patterns Established
- **REVIEW.md as a mandatory post-verification step on safety/security-touching phases** — a second, adversarial read of the diff after VERIFICATION.md passes, specifically hunting for ordering bugs (guard-after-effect) and malformed-input crashes that fixture-driven tests don't naturally cover.
- **Inventory-sweep milestone scoping** for debt-closure milestones: enumerate everything outstanding across seeds/todos/audit-warnings/deferred-subfeatures first, then filter to what's CI-verifiable, before writing requirements.
- **Self-referential doc-hygiene check**: when a phase's job is to reconcile stale frontmatter, explicitly check whether the CURRENT milestone's own phases need the same fix, not only prior milestones'.

### Key Lessons
1. **Run a REVIEW.md-style deep code review after VERIFICATION.md on any phase touching a safety-critical guard or a new unauthenticated input surface** — it found 2 CRITICAL bugs this milestone that automated/fixture-driven verification missed.
2. **When closing a milestone whose own phases include doc-hygiene reconciliation, apply the same reconciliation to the current milestone's phases before calling it done** — otherwise the very next audit finds the milestone did not eat its own dog food.
3. **Flag autonomous-mode policy substitutions (not just code deviations) for explicit operator sign-off** — a working substitute (PVR instead of email) still represents a decision the operator did not make themselves.

### Cost Observations
- Model mix: not tracked this milestone.
- Notable: milestone scoped via an exhaustive automated inventory sweep (64 raw → 20 code-actionable) rather than fresh feature ideation — an efficient way to convert accumulated cross-milestone debt into a single boundaried, closeable unit of work.

---

## Cross-Milestone Trends

### Cumulative Quality

| Milestone | Tests (suite) | Notable |
|-----------|---------------|---------|
| v2.0 | 341 passed | Modular core + CredentialStore (no plaintext on disk) |
| v3.0 | 548 passed, 2 skipped | Anti-detection + ecosystem + price monitoring |
| v4.0 | 755 passed, 2 skipped | Verified checkout + always-on reliability |
| v4.1 | 807 passed, 2 skipped | Dashboard redesign + live SSE observability (zero-Node) |
| v4.2 | 940 passed, 2 skipped | Debt-closure + release-hardening (double-buy guard, CI security, release-please, config harmonization, log/analytics, audit-fixes) |

### Top Lessons (Verified Across Milestones)

1. Prune archived-milestone detail from the live ROADMAP at close — keeps `roadmap.analyze` accurate and ROADMAP constant-size.
2. Single enforcement points (one ABC gate, one RetryPolicy, one shared verification/shaping helper) backed by CI guards beat per-site patches for safety-critical invariants.
3. Keep planning-doc metadata in sync with reality at close: inserted decimal phases need a top-level ROADMAP checkbox, plan SUMMARYs need a `requirements:` field, and VALIDATION status must flip post-exec — including for the CURRENT milestone's own phases, not only older ones — or stale frontmatter misleads both humans and `roadmap.analyze`/audit tooling.
4. A post-verification deep code review (REVIEW.md) is worth running on any phase touching a safety-critical guard or new unauthenticated input surface — it has caught CRITICAL bugs (v4.2 P30, P35) that fixture-driven verification missed.
