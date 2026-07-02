# ShopPyBot — Roadmap

## Project

**Core Value:** A drop-in plugin framework that lets the community add new retail platform integrations by placing a single Python file in `plugins/` — no core changes required.

---

## Milestones

- ✅ **v1 Open Source Launch** — Phases 1-6 (shipped 2026-06-03)
- ✅ **v2.0 Modular Core + Cross-Platform UX** — Phases 7-11 (shipped 2026-06-06)
- ✅ **v3.0 Resilience + Ecosystem** — Phases 12-17 (shipped 2026-06-10)
- ✅ **v4.0 Win-the-Drop (Acquisition Core + Reliability)** — Phases 18-24 (shipped 2026-06-25)
- ✅ **v4.1 Dashboard & Observability** — Phases 25-29.1 (shipped 2026-06-30)
- **v4.2 Release Readiness** — Phases 30-35 (active)

---

## Phases

<details>
<summary>✅ v1 Open Source Launch (Phases 1-6) — SHIPPED 2026-06-03</summary>

- [x] Phase 1: Foundations + Security (5/5 plans) — 2026-06-02
- [x] Phase 2: Plugin Migration (6/6 plans) — 2026-06-03
- [x] Phase 3: Community Documentation (2/2 plans) — 2026-06-03
- [x] Phase 4: Async Orchestrator (5/5 plans) — 2026-06-03
- [x] Phase 5: Notification System (5/5 plans) — 2026-06-03
- [x] Phase 6: Platform Expansion (5/5 plans) — 2026-06-03

Full phase detail archived at `.planning/milestones/v1-phases` (see also `milestones/`).

</details>

<details>
<summary>✅ v2.0 Modular Core + Cross-Platform UX (Phases 7-11) — SHIPPED 2026-06-06</summary>

- [x] Phase 7: Modular Core Service (3/3 plans) — 2026-06-04
- [x] Phase 8: Credential Store (4/4 plans) — 2026-06-04
- [x] Phase 9: CLI Front-End (4/4 plans) — 2026-06-04
- [x] Phase 10: Optional Web UI (4/4 plans) — 2026-06-04
- [x] Phase 11: Cross-Platform Verification (5/5 plans) — 2026-06-05

Full phase detail archived at `.planning/milestones/v2.0-ROADMAP.md`.
Audit: `.planning/milestones/v2.0-MILESTONE-AUDIT.md` (status: passed).

</details>

<details>
<summary>✅ v3.0 Resilience + Ecosystem (Phases 12-17) — SHIPPED 2026-06-10</summary>

- [x] Phase 12: Stability Foundation (4/4 plans) — 2026-06-09
- [x] Phase 13: Anti-Detection Layer 1 — Fingerprint + Proxy (3/3 plans) — 2026-06-09
- [x] Phase 14: Anti-Detection Layer 2 — CAPTCHA Solving (3/3 plans) — 2026-06-09
- [x] Phase 15: Plugin Ecosystem Registry (3/3 plans) — 2026-06-09
- [x] Phase 16: Price Monitoring (4/4 plans) — 2026-06-10
- [x] Phase 17: Test Hardening (4/4 plans) — 2026-06-10

Full phase detail archived at `.planning/milestones/v3.0-ROADMAP.md`.
Audit: `.planning/milestones/v3.0-MILESTONE-AUDIT.md`.

</details>

<details>
<summary>✅ v4.0 Win-the-Drop (Phases 18-24) — SHIPPED 2026-06-25</summary>

- [x] Phase 18: Safety Gate + Config Foundation (4/4 plans) — 2026-06-11
- [x] Phase 19: DB Schema + Confirmation Detection (4/4 plans) — 2026-06-11
- [x] Phase 20: Checkout Profile + Form-Fill (4/4 plans) — 2026-06-11
- [x] Phase 21: Per-Step Timeouts + Unified Retry + Cart-Retry (4/4 plans) — 2026-06-12
- [x] Phase 22: Supervisor + Browser Relaunch + Server Safety (4/4 plans) — 2026-06-12
- [x] Phase 23: Encrypted Session Persistence (4/4 plans) — 2026-06-12
- [x] Phase 24: Health Surface + Server Safety (5/5 plans) — 2026-06-12

Full phase detail archived at `.planning/milestones/v4.0-ROADMAP.md`.
Audit: `.planning/milestones/v4.0-MILESTONE-AUDIT.md` (status: tech_debt — pre-accepted live-UAT debt).

</details>

<details>
<summary>✅ v4.1 Dashboard & Observability (Phases 25-29.1) — SHIPPED 2026-06-30</summary>

- [x] Phase 25: Design System (3/3 plans) — 2026-06-25
- [x] Phase 26: Read-Only API Endpoints (3/3 plans) — 2026-06-27
- [x] Phase 27: SSE Infrastructure (3/3 plans) — 2026-06-27
- [x] Phase 28: Frontend Observability Surfaces (4/4 plans) — 2026-06-27
- [x] Phase 29: SSE Client Wiring (3/3 plans) — 2026-06-28
- [x] Phase 29.1: v4.1 Tech-Debt Cleanup — SSE stall fallback + uPlot load order + log-dup guard (4/4 plans, INSERTED) — 2026-06-30

Full phase detail archived at `.planning/milestones/v4.1-ROADMAP.md`.
Audit: `.planning/milestones/v4.1-MILESTONE-AUDIT.md` (status: tech_debt — 2 low-sev warnings + 16 pre-accepted live-UAT items, no blockers).

</details>

### v4.2 Release Readiness (Phases 30-35)

- [ ] **Phase 30: Breakfix Hardening** — Place-order double-buy latch (HIGH), Amazon WAF auto-solve wiring, post-login DOM/URL verification
- [ ] **Phase 31: CI & Security Infrastructure** — Non-destructive secret-scan audit, CodeQL workflow fix, dependabot + vulnerability remediation
- [ ] **Phase 32: Release Automation & Community Readiness** — release-please seeded at v2.0.0 + pyproject version reconcile, README refresh, real security contact
- [ ] **Phase 33: Config Refactor** — Delay-field name harmonization with back-compat, generic per-platform config declaration
- [ ] **Phase 34: Feature Completion** — `[plugin]` log tags + `/api/logs` filter, outcome analytics over verified-order records
- [ ] **Phase 35: Audit-Fixes & Doc-Hygiene Cleanup** — SSR remove-button fix, `last_heartbeat` leak fix, dead `escHtml()` removal, v4.0/v4.1 frontmatter reconciliation

---

## Phase Details

### Phase 30: Breakfix Hardening

**Goal**: An unattended run cannot double-buy on a place-order-stage timeout, Amazon WAF challenges are attempted via the existing 2captcha solver before falling back to manual pause, and plugin logins are only reported successful when real post-login signals confirm it.
**Depends on**: Nothing (first phase of v4.2; independent of the RH/AF/CFG/FC work streams)
**Requirements**: BF-01, BF-02, BF-03
**Success Criteria** (what must be TRUE):

  1. An idempotency latch/guard test that injects a timeout at the place-order stage proves no duplicate order is placed on retry (BF-02, HIGH).
  2. The Amazon plugin's WAF-challenge path calls the existing 2captcha solver when a challenge is detected, with the manual-pause fallback preserved when solving is unavailable or fails; unit/integration tests mock the 2captcha call and assert both paths (BF-01).
  3. Plugin login verification checks expected post-login DOM/URL signals instead of assuming success from a click; a test simulating a failed/ambiguous login asserts login is NOT reported as successful (BF-03).
  4. Full test suite is green with new/updated tests covering all three breakfixes.

**Plans**: 6 plans (3 waves)

- [x] 30-01-PLAN.md — BF-02 DB marker + orchestrator possibly-placed guard + BF-03 login-failure short-circuit (models.py, core/orchestrator.py) [wave 1]
- [x] 30-02-PLAN.md — BF-01 Amazon WAF auto-solve wiring + `_inject_waf_token` (plugins/shopbot_plugin_amazon.py) [wave 1]
- [x] 30-03-PLAN.md — BF-03 login()->bool ABC + `_verify_login_generic` + relaunch check (core/plugin_base.py) [wave 1]
- [x] 30-04-PLAN.md — BF-02 Amazon + BestBuy place-order marker writes (BestBuy task droppable) [wave 2]
- [x] 30-06-PLAN.md — BF-03 community login verification: Walmart/Target/GameStop/NewEgg/SquareEnix [wave 2]
- [x] 30-05-PLAN.md — BF-03 Amazon + BestBuy login verification + auto_buy abort [wave 3]

### Phase 31: CI & Security Infrastructure

**Goal**: The repo's CI actually scans for secrets and vulnerabilities and reports a clean, trustworthy result — no tracked secrets or credential artifacts, a green CodeQL run, and a clean dependabot alert queue.
**Depends on**: Nothing
**Requirements**: RH-01, RH-04, RH-05
**Success Criteria** (what must be TRUE):

  1. A gitleaks/trufflehog scan of the repo (history + working tree) reports zero findings, and `.gitignore` demonstrably excludes `config.yml`, `data/*.db`, and credential-store artifacts (RH-01).
  2. The CodeQL workflow runs to a green completion in Actions after retired `checkout@v2` / `codeql-action@v1` are bumped to currently-supported versions (RH-04).
  3. `.github/dependabot.yml` exists and is valid, and all currently-open dependency vulnerability alerts are reviewed and remediated (updated or explicitly dismissed with rationale) so the alert queue is clean (RH-05).

**Plans**: TBD

### Phase 32: Release Automation & Community Readiness

**Goal**: The repo is ready to cut its first public release — the version source of truth is consistent, release-please automates changelog/tagging from conventional commits, and the README/security docs are accurate for a new contributor or operator.
**Depends on**: Phase 31 (release-please should land against a CI pipeline with working CodeQL/dependabot signal)
**Requirements**: RH-02, RH-03, RH-06, RH-07
**Success Criteria** (what must be TRUE):

  1. `pyproject.toml`'s canonical version is reconciled to `2.0.0` (RH-03).
  2. The release-please workflow + config exist, target the `python` release-type, and are seeded from `2.0.0`; a dry-run / manifest confirms the seed and correct parsing of conventional-commit history (RH-02).
  3. README accurately documents the 7-platform ecosystem, web dashboard/observability, price monitoring, anti-detection, and session persistence; states the Python 3.11+ prereq; documents `pip install -e .[web]` / `shoppybot` install and run; badges resolve; the clone URL is the real repo (RH-06).
  4. `SECURITY.md` and `CODE_OF_CONDUCT.md` carry the operator-supplied real maintainer contact, with zero remaining `SECURITY_CONTACT_PLACEHOLDER@example.com` occurrences anywhere in the repo (RH-07).

**Plans**: TBD

### Phase 33: Config Refactor

**Goal**: Platform delay-config fields have one canonical name across every plugin — old configs still load via a back-compat shim — and a plugin can declare its own per-platform config section without any core schema edit.
**Depends on**: Nothing (CFG-01 must land before CFG-02 within this phase — shared config-schema surface)
**Requirements**: CFG-01, CFG-02
**Success Criteria** (what must be TRUE):

  1. All plugins read a single canonical delay-field naming scheme; a config using the legacy field names still loads correctly via a back-compat shim, proven by a test loading both old- and new-style config (CFG-01).
  2. A plugin can add a new, previously-undeclared per-platform config section (e.g. a test/fixture plugin) and have it load and validate with zero changes to the core config-schema file (CFG-02).
  3. The existing config-schema test suite plus new tests for both requirements are green.

**Plans**: TBD

### Phase 34: Feature Completion

**Goal**: An operator can filter dashboard/API logs by plugin and see success-rate + time-to-checkout analytics computed from existing verified-order records.
**Depends on**: Nothing (builds on existing v4.0 order records + v4.1 log/dashboard infrastructure)
**Requirements**: FC-01, FC-02
**Success Criteria** (what must be TRUE):

  1. Every log line written carries a `[plugin]` tag, and `/api/logs` accepts a plugin filter parameter that returns only matching lines (FC-01, completes OBS-08).
  2. An operator-facing analytics view/endpoint computes success-rate and time-to-checkout from existing confirmed-order (BUY-04) records, with correct output verified against a fixture set of orders (FC-02).
  3. New tests for both requirements are green.

**Plans**: TBD
**UI hint**: yes

### Phase 35: Audit-Fixes & Doc-Hygiene Cleanup

**Goal**: The three outstanding low-severity audit warnings from the v4.1 close are resolved, and the v4.0/v4.1 planning-artifact frontmatter accurately reflects each phase's actual passing validation status.
**Depends on**: Nothing (documentation + small frontend/backend cleanup; no feature coupling to other v4.2 phases)
**Requirements**: AF-01, AF-02, AF-03, DH-01, DH-02, DH-03
**Success Criteria** (what must be TRUE):

  1. The dashboard SSR items-table remove button removes an item even when the JS `loadItems()` fetch/render path fails — a test simulating a failed fetch confirms the SSR-rendered remove action still functions (AF-01).
  2. `get_status()` and SSE status frames no longer contain the raw `last_heartbeat` monotonic float; only `heartbeat_age_secs` is present — a test asserts the raw field's absence from both surfaces (AF-02).
  3. The dead `escHtml()` helper no longer exists anywhere in the dashboard frontend source (AF-03).
  4. v4.1 VALIDATION.md frontmatter for phases 25/26/27 reads `status: validated` / `wave_0_complete: true`, and v4.1 SUMMARY.md frontmatter for phases 27/28/29 carries `requirements:` so the audit 3-source cross-reference reports OBS-01/02/03/04/06/09 as VERIFIED (DH-01, DH-02).
  5. v4.0 phase VALIDATION.md `nyquist_compliant` flags read `true` for phases 18-24 (DH-03).

**Plans**: TBD
**UI hint**: yes

---

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1 Open Source Launch | 1-6 | 28/28 | ✅ Shipped | 2026-06-03 |
| v2.0 Modular Core + Cross-Platform UX | 7-11 | 20/20 | ✅ Shipped | 2026-06-06 |
| v3.0 Resilience + Ecosystem | 12-17 | 21/21 | ✅ Shipped | 2026-06-10 |
| v4.0 Win-the-Drop | 18-24 | 29/29 | ✅ Shipped | 2026-06-25 |
| v4.1 Dashboard & Observability | 25-29.1 | 20/20 | ✅ Shipped | 2026-06-30 |
| v4.2 Release Readiness | 30-35 | 0/TBD | 🚧 Active | - |

All requirements satisfied across v1 (44) + v2.0 (22) + v3.0 (18) + v4.0 (17) + v4.1 (16). v4.2 (20 requirements) roadmap created, not yet planned. Per-milestone requirement detail in `.planning/milestones/v*-REQUIREMENTS.md`.

---

*Last updated: 2026-07-02 — v4.2 Release Readiness roadmap created (Phases 30-35, 20 requirements mapped, 100% coverage). Ready for `/gsd:plan-phase 30`.*
