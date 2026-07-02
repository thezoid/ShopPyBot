# Requirements: ShopPyBot — v4.2 Release Readiness

**Defined:** 2026-07-02
**Core Value:** Drop-in plugin framework — community adds retail platform integrations via a single Python file in `plugins/`; no core changes required.

**Milestone intent:** Debt-closure + release-hardening. Close every code-actionable outstanding item (seeds, breakfixes, audit warnings, deferred sub-features, release-hardening gaps) surfaced by the 2026-07-02 inventory sweep (64 raw → 20 code-actionable). "Done" = code-complete and green in CI, pending only live-environment operator UAT (which is inherently untestable in CI and remains tracked debt).

## Milestone v4.2 Requirements

Each is code-actionable to a stable, CI-verifiable state without live retail testing.

### Release-Hardening

- [ ] **RH-01**: Repo git history and `.gitignore` are audited so no secret, populated `config.yml`, real `data/*.db`, or credential-store artifact is tracked (SEED-001 non-destructive prep; a clean `gitleaks`/`trufflehog` scan is the evidence)
- [ ] **RH-02**: release-please workflow + config tags releases and maintains `CHANGELOG.md` from conventional commits, seeded at product version **v2.0.0** (SEED-002)
- [ ] **RH-03**: `pyproject.toml` canonical version is reconciled to `2.0.0` so release-please (python type) has a correct source of truth
- [ ] **RH-04**: The CodeQL static-security-scan workflow runs successfully (retired `checkout@v2` / `codeql-action@v1` bumped to supported versions)
- [ ] **RH-05**: `.github/dependabot.yml` exists and open dependency vulnerability alerts are reviewed and remediated to a clean state
- [ ] **RH-06**: README accurately reflects shipped capabilities (7-platform ecosystem, web dashboard/observability, price monitoring, anti-detection, sessions), correct prereqs (Python 3.11+), correct install (`pip install -e .[web]` / `shoppybot`), working badges, and a real clone URL
- [ ] **RH-07**: `SECURITY.md` and `CODE_OF_CONDUCT.md` carry a real maintainer security contact in place of `SECURITY_CONTACT_PLACEHOLDER@example.com` (value operator-supplied)

### Audit-Fixes

- [ ] **AF-01**: Dashboard SSR items-table remove buttons remove an item without depending on the JS `loadItems()` render path (graceful degradation if the fetch fails)
- [ ] **AF-02**: `get_status()` and SSE status frames no longer expose the raw `last_heartbeat` monotonic float (only derived `heartbeat_age_secs`)
- [ ] **AF-03**: The dead `escHtml()` helper is removed from the dashboard frontend

### Breakfix

- [ ] **BF-01**: Amazon WAF challenge auto-solve is wired into the Amazon plugin via the existing 2captcha solver path, with the manual-pause fallback preserved (unit/integration-tested with mocked 2captcha; live-challenge proof stays operator debt)
- [ ] **BF-02** (HIGH): A place-order-stage timeout cannot cause a placed-but-unconfirmed double-buy on retry — an idempotency latch/guard around order placement, verified by injecting a timeout at that stage
- [ ] **BF-03**: Plugin login verifies success via expected post-login DOM/URL signals instead of assuming success (WR-03)

### Config-Refactor

- [ ] **CFG-01**: Platform delay-config field names are unified across all plugins (`delay_seconds/delay_jitter` vs `min_delay/max_delay`) with a back-compat shim for existing configs
- [ ] **CFG-02**: A plugin can declare its own per-platform config section without editing core schema (generic per-platform config in schema + loader)

### Feature-Completion

- [ ] **FC-01**: Log lines carry a `[plugin]` tag and `/api/logs` supports filtering by plugin (completes the deferred half of OBS-08)
- [ ] **FC-02**: Operator can view outcome analytics (success-rate, time-to-checkout) computed over existing BUY-04 verified-order records

### Doc-Hygiene

- [ ] **DH-01**: Lagging v4.1 VALIDATION.md status/wave frontmatter (phases 25/26/27) is reconciled to reflect the passing suites (`status: validated`, `wave_0_complete: true`)
- [ ] **DH-02**: v4.1 SUMMARY.md `requirements:` frontmatter is added (phases 27/28/29) so the audit 3-source cross-reference reports OBS-01/02/03/04/06/09 as VERIFIED
- [ ] **DH-03**: v4.0 phase VALIDATION.md `nyquist_compliant` flags are set true (phases 18-24) to match their passing suites

## Future Requirements

Deferred; tracked but not in this milestone's roadmap.

### Acquisition (arms-race)

- **ACQ-F1**: Request/API-mode (hybrid) checkout — per-site private-endpoint reverse-engineering (XL, live-only)
- **ACQ-F2**: Virtual-waiting-room / queue survival (Queue-it, PerimeterX, Akamai, DataDome) (XL, live-only)
- **ACQ-F3**: Multi-account / multi-profile parallel attempts (XL, most ToS-hostile)
- **ACQ-F4**: Checkout form-fill for the remaining 5 retailers (mechanical, but stable selectors need per-retailer live UAT)

## Out of Scope

Explicitly excluded from v4.2. "Done" is defined as stable-pending-testing, so all live-environment verification remains tracked operator debt, not milestone work.

| Feature | Reason |
|---------|--------|
| All Phase 18-24 live-UAT (monitor-only, confirmation selectors, form-fill, timeout abort, supervisor/relaunch/teardown, session accept, headless audio) | Only confirmable against a real retail drop / target server; not reproducible in CI |
| All Phase 27/28/29/29.1 live-UAT (SSE socket, browser render, EventSource-vs-poll, stall→fallback, cold-load chart) | Live browser + live socket only |
| Amazon WAF auto-solve live acceptance | Needs a real AWS-WAF challenge within the ~30s gokuProps freshness window (the code wiring is in scope as BF-01) |
| BF-02 place-order double-buy live proof | Idempotency guard is in scope; final edge-close needs a live slow-drop |
| ~37 community-plugin selector TODOs (Walmart, Target, GameStop, Newegg, Square Enix) + suspect BestBuy `.a-dropdown-prompt` | Selectors verifiable only against live storefronts |
| Destructive SEED-001 history rewrite / force-push / secret rotation / collaborator re-clone | Operator-gated one-time destructive action; requires explicit approval outside this milestone (RH-01 covers only the non-destructive audit) |
| Request/API mode, waiting-room survival, multi-account | XL arms-race, live-only, high-maintenance / ToS-hostile — deferred (see Future Requirements) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BF-01 | Phase 30 | Pending |
| BF-02 | Phase 30 | Pending |
| BF-03 | Phase 30 | Pending |
| RH-01 | Phase 31 | Pending |
| RH-04 | Phase 31 | Pending |
| RH-05 | Phase 31 | Pending |
| RH-02 | Phase 32 | Pending |
| RH-03 | Phase 32 | Pending |
| RH-06 | Phase 32 | Pending |
| RH-07 | Phase 32 | Pending |
| CFG-01 | Phase 33 | Pending |
| CFG-02 | Phase 33 | Pending |
| FC-01 | Phase 34 | Pending |
| FC-02 | Phase 34 | Pending |
| AF-01 | Phase 35 | Pending |
| AF-02 | Phase 35 | Pending |
| AF-03 | Phase 35 | Pending |
| DH-01 | Phase 35 | Pending |
| DH-02 | Phase 35 | Pending |
| DH-03 | Phase 35 | Pending |

**Coverage:**
- v4.2 requirements: 20 total
- Mapped to phases: 20/20 ✓
- Unmapped: 0

---
*Requirements defined: 2026-07-02*
*Last updated: 2026-07-02 — v4.2 roadmap created (Phases 30-35); traceability populated, 100% coverage*
