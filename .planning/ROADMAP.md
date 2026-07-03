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
- ✅ **v4.2 Release Readiness** — Phases 30-35 (shipped 2026-07-03)

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

<details>
<summary>✅ v4.2 Release Readiness (Phases 30-35) — SHIPPED 2026-07-03</summary>

- [x] Phase 30: Breakfix Hardening (6/6 plans) — 2026-07-02
- [x] Phase 31: CI & Security Infrastructure (3/3 plans) — 2026-07-02
- [x] Phase 32: Release Automation & Community Readiness (3/3 plans) — 2026-07-02
- [x] Phase 33: Config Refactor (2/2 plans) — 2026-07-02
- [x] Phase 34: Feature Completion (3/3 plans) — 2026-07-03
- [x] Phase 35: Audit-Fixes & Doc-Hygiene Cleanup (3/3 plans) — 2026-07-03

Full phase detail archived at `.planning/milestones/v4.2-ROADMAP.md`.
Audit: `.planning/milestones/v4.2-MILESTONE-AUDIT.md` (status: tech_debt — 20/20 requirements satisfied, no blockers; BF-02 5-plugin propagation gap + operator-gated GitHub Settings items tracked as debt).

</details>

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1 Open Source Launch | 1-6 | 28/28 | ✅ Shipped | 2026-06-03 |
| v2.0 Modular Core + Cross-Platform UX | 7-11 | 20/20 | ✅ Shipped | 2026-06-06 |
| v3.0 Resilience + Ecosystem | 12-17 | 21/21 | ✅ Shipped | 2026-06-10 |
| v4.0 Win-the-Drop | 18-24 | 29/29 | ✅ Shipped | 2026-06-25 |
| v4.1 Dashboard & Observability | 25-29.1 | 20/20 | ✅ Shipped | 2026-06-30 |
| v4.2 Release Readiness | 30-35 | 20/20 | ✅ Shipped | 2026-07-03 |

All requirements satisfied across v1 (44) + v2.0 (22) + v3.0 (18) + v4.0 (17) + v4.1 (16) + v4.2 (20). Per-milestone requirement detail in `.planning/milestones/v*-REQUIREMENTS.md`.

---

*Last updated: 2026-07-03 — v4.2 Release Readiness milestone shipped (Phases 30-35, 20 requirements, 45 tasks); archived to `.planning/milestones/v4.2-ROADMAP.md`. Next: `/gsd:new-milestone`.*
