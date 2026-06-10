# ShopPyBot — Roadmap

## Project

**Core Value:** A drop-in plugin framework that lets the community add new retail platform integrations by placing a single Python file in `plugins/` — no core changes required.

---

## Milestones

- ✅ **v1 Open Source Launch** — Phases 1-6 (shipped 2026-06-03)
- ✅ **v2.0 Modular Core + Cross-Platform UX** — Phases 7-11 (shipped 2026-06-06)
- **v3.0 Resilience + Ecosystem** — Phases 12-17 (COMPLETE 2026-06-10)

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

### v3.0 Resilience + Ecosystem (Phases 12-17)

- [x] **Phase 12: Stability Foundation** — Close v2.0 deferred cross-OS checks and resolve 4 audit tech-debt items to establish a clean test baseline before adding new features (completed 2026-06-09)
- [x] **Phase 13: Anti-Detection Layer 1 — Fingerprint + Proxy** — Apply JS fingerprint stealth patch and implement proxy rotation with ban detection and per-instance scoping
 (completed 2026-06-09)

- [x] **Phase 14: Anti-Detection Layer 2 — CAPTCHA Solving** — Integrate 2captcha opt-in solver with CredentialStore key, startup balance check, async executor wrapping, and spend cap (completed 2026-06-09)
- [x] **Phase 15: Plugin Ecosystem Registry** — Add difficulty/proxy/captcha class attrs to ABC, create GitHub wiki registry table, ship `shoppybot plugins list` command, and update contributor docs (completed 2026-06-09)
- [x] **Phase 16: Price Monitoring** — Per-item target price, append-only price history table, percentage-drop secondary trigger, fan-out price-drop alerts with separate dedup, and price-history CLI command (completed 2026-06-10)
- [x] **Phase 17: Test Hardening** — Unit and integration coverage for all v3.0 features (proxy config, CAPTCHA flow, price monitoring schema and threshold logic, plugin ABC additions) (completed 2026-06-10)

---

## Phase Details

### Phase 12: Stability Foundation

**Goal**: The v2.0 deferred debt and audit tech-debt are paid down before new features land, so the test suite is a reliable baseline
**Depends on**: Nothing — do first
**Requirements**: STAB-01, STAB-02
**Success Criteria** (what must be TRUE):

  1. All 4 deferred v2.0 cross-OS/UI manual checks (keyring restart survival, masked-TTY passphrase prompt, web dashboard render on Ubuntu, `0.0.0.0` bind warning) are executed and documented pass or fail, with any failures fixed
  2. Each of the 4 v2.0 audit tech-debt items has a targeted regression test that passes in CI
  3. No broad refactors occur: only the specific items in scope are changed

**Plans**: 4 plans

Plans:

- [x] 12-01-PLAN.md — TD-1: re-anchor logger logging_level read to core.paths.config_path() + regression test
- [x] 12-02-PLAN.md — TD-2/TD-3: harden SC1 secret-read guard (rglob) and separator guard (__file__-anchored)
- [x] 12-03-PLAN.md — TD-4 config write-seam regression test + accepted MOD-02 gap doc; MC-4 0.0.0.0 banner assertion
- [x] 12-04-PLAN.md — Execute and document MC-1..MC-4 deferred manual checks in docs/PLATFORMS.md

### Phase 13: Anti-Detection Layer 1 — Fingerprint + Proxy

**Goal**: Users can enable proxy rotation and the bot applies a JS fingerprint stealth patch at browser startup, measurably reducing Layer 2 bot signals
**Depends on**: Phase 12
**Requirements**: ANTI-08, ANTI-04, ANTI-05
**Success Criteria** (what must be TRUE):

  1. Bot applies `window.chrome`, `navigator.plugins`, `navigator.languages`, and screen-dimension patches via `core/stealth.py` at every browser startup with no plugin ABC version bump
  2. User can enable proxy rotation via an opt-in `proxy:` config section (disabled by default) listing `scheme://host:port` URLs; bot logs "Proxy rotation: enabled, pool_size=N" at startup
  3. Bot detects ban signals (HTTP 403/429/503, challenge-redirect, block-phrase body) and rotates to the next proxy, retiring a proxy after N consecutive failures for a configurable cooldown period
  4. WebRTC Chrome preferences are set at browser launch to prevent real-IP leaks through the proxy tunnel
  5. Each proxy is scoped to its plugin instance (`self._proxy`) and rotated only at browser restart, not mid-session

**Plans**: 3 plans

Plans:

- [x] 13-01-PLAN.md — core/stealth.py: STEALTH_JS + apply_stealth, ProxyPool (round-robin/retire/cooldown), proxy launch args + WebRTC flag, CDP Fetch auth, ban-signal detector (+ unit tests)
- [x] 13-02-PLAN.md — ProxyConfig schema (opt-in, disabled by default) + documented sample.config.yml proxy section
- [x] 13-03-PLAN.md — Wire stealth + proxy into BotService/orchestrator/registry and all 8 plugins; per-instance scoping, exact startup log, fail-loud on pool exhaustion, ban-detect recording

**UI hint**: no

### Phase 14: Anti-Detection Layer 2 — CAPTCHA Solving

**Goal**: Users who encounter reCAPTCHA v2 or Amazon WAF CAPTCHAs can opt into automated solving via 2captcha with full cost visibility and no credential plaintext exposure
**Depends on**: Phase 13 (fingerprint + proxy layer in place before adding CAPTCHA layer)
**Requirements**: ANTI-06, ANTI-07
**Success Criteria** (what must be TRUE):

  1. User can enable CAPTCHA solving via `captcha.enabled: true` in config; the 2captcha API key is stored exclusively in CredentialStore (`TWOCAPTCHA_API_KEY`), never in config.yml
  2. Bot checks 2captcha account balance at startup, logs a WARNING when balance is low, and skips solver use (falling back to manual pause) when balance is zero
  3. CAPTCHA solve calls use `run_in_executor` + `asyncio.timeout(120)` so other plugin poll tasks are not blocked during a solve
  4. A configurable `captcha.max_solves_per_run` limit prevents unbounded API charges; default config disables CAPTCHA solving

**Plans**: 3 plans

Plans:

- [x] 14-01-PLAN.md — Foundation: TWOCAPTCHA_API_KEY in SECRET_KEYS, CaptchaConfig, CaptchaSolver 2captcha v1 client (submit/poll/balance/cap)
- [x] 14-02-PLAN.md — Wiring: solver constructed fresh in async_main + startup balance check + registry.assign_solver (mirrors ProxyPool)
- [x] 14-03-PLAN.md — Plugin solve path: Amazon + BestBuy reCAPTCHA solve under run_in_executor+timeout(120) with manual-pause fallback; WAF deferred

### Phase 15: Plugin Ecosystem Registry

**Goal**: Community contributors have a discoverable registry with clear difficulty ratings, and users can inspect loaded plugins locally without a network call
**Depends on**: Phase 12
**Requirements**: REG-01, REG-02, REG-03, REG-04
**Success Criteria** (what must be TRUE):

  1. Plugin authors can declare `difficulty`, `requires_proxy`, and `requires_captcha` as class attributes on any plugin; existing plugins without these attrs continue to load with sensible defaults (non-breaking)
  2. The GitHub wiki registry table contains required fields for each community plugin: name, platform, domain patterns, maintainer, anti-detection difficulty, methods implemented, last-verified date, proxy-required, captcha-required
  3. Running `shoppybot plugins list` displays all locally loaded plugins with their declared domain patterns, difficulty, and proxy/captcha flags without making a network call
  4. CONTRIBUTING.md and the PR template require contributors to supply `difficulty`, `requires_proxy`, and `requires_captcha` for new plugin submissions

**Plans**: 3 plans

Plans:

- [x] 15-01-PLAN.md — REG-02: add difficulty/requires_proxy/requires_captcha class attrs + __init_subclass__ difficulty validation to RetailerPlugin ABC (non-breaking, PLUGIN_API_VERSION stays 2) + test_plugin_base.py assertions
- [x] 15-02-PLAN.md — REG-03: BotService.list_plugins() over registry._all_plugins + core/cli/plugins.py handler + plugins-list subparser with --json + no-network CLI tests
- [x] 15-03-PLAN.md — REG-01/REG-04: docs/PLUGIN_REGISTRY.md 9-field wiki SPEC + CONTRIBUTING.md/PR-template/PLUGIN_DEV.md attr requirements + tests/test_docs.py

### Phase 16: Price Monitoring

**Goal**: Users can track per-item prices, receive fan-out alerts when prices drop to target or by a configured percentage, and inspect price history from the CLI
**Depends on**: Phase 12
**Requirements**: PRICE-01, PRICE-02, PRICE-03, PRICE-04, PRICE-05, PRICE-06
**Success Criteria** (what must be TRUE):

  1. User can set `target_price` (absolute) and `price_drop_pct` (percentage) per item in config; NULL/absent means price monitoring is off for that item
  2. Bot records scraped prices in an append-only `price_history` SQLite table each poll cycle via an optional `get_price()` plugin ABC hook (default returns `None`); the DB migration is idempotent on existing installs
  3. Price-drop alerts are dispatched through the existing fan-out notification dispatcher using a distinct `price_drop` notification_type with dedup columns separate from stock alert columns
  4. Price alert payloads include the current price, target price, and percentage from target
  5. Running `shoppybot items price-history <name>` displays the last N recorded prices for that item

**Plans**: 4 plans

Plans:

- [x] 16-01-PLAN.md — Data layer: idempotent price_history table + 4 items columns + 8 parameterized price _sync functions + ItemConfig target_price/price_drop_pct (PRICE-01/02/05)
- [x] 16-02-PLAN.md — Plugin + notification contract: NotificationEvent price fields, default-None get_price() ABC hook, real Amazon get_price() + text→cents parser, price_drop notifier branches (PRICE-02/04)
- [x] 16-03-PLAN.md — Orchestrator wiring: _check_and_buy price path, both triggers with separate dedup, single price_drop dispatch, startup config seeding + BotService.get_price_history (PRICE-02/03/04/05)
- [x] 16-04-PLAN.md — CLI: shoppybot items price-history <name> leaf with --limit (default 10), $X.XX table, no network (PRICE-06)

**UI hint**: yes

### Phase 17: Test Hardening

**Goal**: Every new v3.0 feature has unit and integration coverage so regressions are caught by CI before they reach users
**Depends on**: Phases 13, 14, 15, 16 (tests validate the implemented features)
**Requirements**: STAB-03
**Success Criteria** (what must be TRUE):

  1. Unit tests cover proxy config parsing, ban-signal detection logic, per-instance proxy scoping, and cooldown/retire logic
  2. Unit tests cover CAPTCHA config parsing, balance-check behavior, executor wrapping, and spend-cap enforcement
  3. Unit tests cover price comparison threshold logic, `price_history` DB schema (including idempotent migration against a v2.0 DB fixture), and price-drop dedup separation from stock-alert dedup
  4. Integration tests cover the plugin ABC additions (`difficulty`, `requires_proxy`, `requires_captcha` defaults and overrides) and the `get_price()` hook being called alongside `check_availability`

**Plans**: 4 plans

Plans:

- [x] 17-01-PLAN.md — Proxy coverage: PX-01..PX-06 (config validator, fetch-handler tasks, ProxyPool edges, registry routing/lifecycle isolation)
- [x] 17-02-PLAN.md — CAPTCHA coverage: CP-01..CP-05 (poll/timeout errors, balance gate, solve_amazon_waf submit/poll/decode)
- [x] 17-03-PLAN.md — Price + get_price integration: PR-01..PR-04 + AB-01, AB-02 (v2.0-schema migration fixture, trigger guards, get_price-alongside-check_availability)
- [x] 17-04-PLAN.md — Plugin ABC: AB-03, AB-04 (metadata overrides + _handle_ban ban→proxy-cooldown bridge)

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Foundations + Security | v1 | 5/5 | Complete | 2026-06-02 |
| 2. Plugin Migration | v1 | 6/6 | Complete | 2026-06-03 |
| 3. Community Documentation | v1 | 2/2 | Complete | 2026-06-03 |
| 4. Async Orchestrator | v1 | 5/5 | Complete | 2026-06-03 |
| 5. Notification System | v1 | 5/5 | Complete | 2026-06-03 |
| 6. Platform Expansion | v1 | 5/5 | Complete | 2026-06-03 |
| 7. Modular Core Service | v2.0 | 3/3 | Complete | 2026-06-04 |
| 8. Credential Store | v2.0 | 4/4 | Complete | 2026-06-04 |
| 9. CLI Front-End | v2.0 | 4/4 | Complete | 2026-06-04 |
| 10. Optional Web UI | v2.0 | 4/4 | Complete | 2026-06-04 |
| 11. Cross-Platform Verification | v2.0 | 5/5 | Complete | 2026-06-05 |
| 12. Stability Foundation | v3.0 | 4/4 | Complete    | 2026-06-09 |
| 13. Anti-Detection Layer 1 — Fingerprint + Proxy | v3.0 | 3/3 | Complete    | 2026-06-09 |
| 14. Anti-Detection Layer 2 — CAPTCHA Solving | v3.0 | 3/3 | Complete    | 2026-06-09 |
| 15. Plugin Ecosystem Registry | v3.0 | 3/3 | Complete    | 2026-06-09 |
| 16. Price Monitoring | v3.0 | 4/4 | Complete    | 2026-06-10 |
| 17. Test Hardening | v3.0 | 4/4 | Complete    | 2026-06-10 |

All 66 v1+v2.0 requirements satisfied. v3.0: 18 requirements mapped across Phases 12-17.

---

*Last updated: 2026-06-10 — Phase 17 planned (4 plans, STAB-03 test hardening)*
