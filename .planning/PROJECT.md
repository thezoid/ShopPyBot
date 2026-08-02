# ShopPyBot — Project

## What This Is

A comprehensive, extensible shopping bot that monitors stock and auto-purchases items across multiple retail platforms. The core value is a **drop-in plugin framework** that lets the open source community add new platform integrations by dropping a single Python file into a `plugins/` directory — no core changes required.

## Context

Brownfield refactor of a working personal-use bot (Amazon + BestBuy). The existing sequential Selenium loop, SQLite tracking, and YAML config are proven but limited. This project evolves that foundation into a community-extensible platform.

Target user: technically capable individuals who want automated stock monitoring for limited-release items (collectibles, gaming hardware, etc.), and developers who want to contribute new retail platform integrations.

## Core Value

**The plugin framework.** Without it, this is just another private bot. With it, community contributors can extend coverage to any retail platform without touching core bot logic.

## Current State

**Shipped v4.2 Release Readiness (2026-07-03).** A debt-closure + release-hardening milestone: an unattended run can no longer double-buy on a place-order-stage timeout (write-ahead DB marker + `_PossiblyPlaced` guard, Amazon + BestBuy), Amazon WAF challenges are attempted via the existing 2captcha solver before falling back to manual pause, and all 7 plugins now verify login via real post-login DOM/URL signals instead of assuming success from a click. CI runs a real gitleaks secret scan and a repaired CodeQL workflow, `.github/dependabot.yml` is in place with all 7 open vulnerability alerts remediated, `pyproject.toml` is reconciled to `2.0.0`, and release-please is seeded and wired for conventional-commit changelog/tagging. README is rewritten for the current 7-platform architecture and SECURITY.md/CODE_OF_CONDUCT.md route through GitHub Private Vulnerability Reporting. Platform delay-config fields are harmonized (`delay_seconds`/`delay_jitter`) with a back-compat shim, and a plugin can now self-declare its own config section with zero core schema edits. The dashboard gained a per-plugin log filter and outcome analytics (success-rate, time-to-checkout). Three outstanding v4.1 audit warnings (SSR remove-button, `last_heartbeat` leak, dead `escHtml()`) and stale v4.0/v4.1 doc frontmatter are resolved.

v4.2: 6 phases (30-35) / 20 plans / 45 tasks, all complete. Full suite: 940 passed, 2 skipped. Audit status `tech_debt` (no blockers): one code-level gap (BF-02 marker not yet propagated to the 5 community plugins) plus a set of operator-gated GitHub Settings actions outstanding — enable Private Vulnerability Reporting, widen the Actions allowlist for `gitleaks`/`release-please`, merge release-please PR #11 to master, and add a LICENSE file if open-sourcing.

**Built on v4.1 Dashboard & Observability (2026-06-30):** zero-Node vendored dashboard redesign (3-file CSS split, light/dark, FOUC-safe) surfacing live operational observability over a single `/api/events` SSE stream (health cards, confirmed-buys table, price-history charts, filterable log viewer, uptime bar), backed by read-only REST endpoints with credential-leak CI guards — over the v4.0 Win-the-Drop acquisition/reliability core and the v2.0 modular `BotService`.

**Deferred (carried):** all live-environment UAT (v4.0 acquisition checks, v4.1 dashboard live-browser/socket checks, v4.2 WAF/double-buy/CI-Actions live checks) tracked in STATE.md → Deferred Items as the operator's pre-production + release checklist; the 5-community-plugin BF-02 marker propagation gap; the destructive half of SEED-001 (public-repo history scrub/squash) stays operator-gated.

**Correction recorded 2026-08-02:** everything described above as "shipped" for v4.1 and v4.2 is shipped *on a branch*, not on `master`. A full-repo sweep found the default branch 263 commits behind, PR #11 hard-blocked because its `ci.yml` fails to compile (so the v4.1+v4.2 suite has never run in CI), the built wheel missing every data file (`shoppybot web` cannot start from an installed wheel), and no LICENSE on a public repo. Milestone v5.0 exists to make the mainline and the published artifact match these claims.

**Key constraints (held):** secrets never in config.yml/logs/SQLite plaintext; full card number / CVV never persisted to disk or logs (retailer-saved payment + CVV-at-runtime only); GUI optional, CLI default; the credential-managing web UI binds to localhost by default; zero-Node (no package.json/CDN/external fonts — vendored CSS/JS only); observability is read-only over `get_status()` + DB with no new secrets.

<details>
<summary>Shipped: v4.2 Release Readiness — 2026-07-03</summary>

**Goal:** Close every outstanding code-actionable item — seeds, breakfixes, audit warnings, deferred sub-features, and release-hardening gaps — so the public repo reaches a stable, release-ready state.

**Delivered features:**
- Breakfix hardening (P30): place-order-timeout double-buy latch (HIGH), Amazon WAF auto-solve via 2captcha with manual-pause fallback preserved, real post-login DOM/URL verification (`_verify_login_generic`) across all 7 plugins.
- CI & security infrastructure (P31): gitleaks secret-scan CI job + local guard test, repaired CodeQL workflow (checkout@v6/codeql-action@v4), `.github/dependabot.yml` + all 7 open vulnerability alerts remediated.
- Release automation & community readiness (P32): `pyproject.toml` reconciled to 2.0.0, release-please seeded (manifest-mode, python release-type), README rewritten, SECURITY.md/CODE_OF_CONDUCT.md routed through GitHub Private Vulnerability Reporting.
- Config refactor (P33): canonical `delay_seconds`/`delay_jitter` fields with legacy back-compat shim; generic per-platform config extension point (`PlatformsConfig(extra="allow")` + `RetailerPlugin.get_platform_config()`).
- Feature completion (P34): `[plugin]` log tag on every log line + `/api/logs` plugin filter (completes OBS-08); outcome analytics (success-rate, time-to-checkout) over confirmed-order records.
- Audit-fixes & doc-hygiene (P35): SSR remove-button graceful degradation, `last_heartbeat` leak scrubbed from `get_status()`/SSE, dead `escHtml()` removed, v4.0/v4.1 planning-artifact frontmatter reconciled.

**Constraints held:** CLI default; web optional + localhost bind + CSRF + non-local warning; zero-Node; observability read-only over `BotService.get_status()` + DB, no new secrets; no plaintext secrets, no full card/CVV persistence.

</details>

<details>
<summary>Shipped: v4.1 Dashboard & Observability — 2026-06-30</summary>

**Goal:** Redesign the optional FastAPI web dashboard with a polished zero-dependency design system and surface rich live operational observability over SSE, without breaking the CLI-default, localhost-bound, no-Node posture.

**Delivered features:**
- Vendored zero-Node design system (3-file CSS split: tokens/components/dashboard; light/dark with FOUC-safe inline theming; uPlot 1.6.32 vendored, no CDN/fonts; `loadItems()`/`loadCredentials()` XSS vector fixed).
- Read-only observability REST endpoints (`/api/history`, `/api/price-history/{link_b64}`, filtered `/api/logs`), all `asyncio.to_thread`-wrapped; `last_error` scrubbed; credential-leak CI guard.
- SSE infrastructure: single `/api/events` stream, uvicorn `_poll_loop` sole-producer cross-thread bridge, keepalive, clean disconnect, cursor log tail.
- Four observability surfaces: per-plugin health cards, confirmed-buys table, per-item price-history charts (empty-state), filterable color-coded log viewer (follow + 500-line cap), uptime bar.
- SSE client wiring: `EventSource('/api/events')` replaces the 2s poll, named listeners, polling fallback, Live/Reconnecting indicator; inserted 29.1 cleanup closed 3 audit warnings (uPlot load order, log-dedup, SSE stall watchdog + REST fallback).

**Constraints held:** CLI default; web optional + localhost bind + CSRF + non-local warning; zero-Node (no package.json/CDN/external fonts); observability read-only over `BotService.get_status()` + DB, no new secrets.

</details>

## Current Milestone: v5.0 Real Release & Plugin Ecosystem

**Goal:** Make the default branch, the published artifact, and the public repo actually be what four shipped milestones already claim, then open the plugin framework to third parties with a trust model that survives the fact that importing a plugin is executing it.

**Premise (established by the 2026-08-02 sweep, 221 evidenced findings):** `master` is 263 commits behind. Every v4.1 and v4.2 artifact — the dashboard, gitleaks, release-please — exists only on the unmerged `chore/v4.0-milestone-close` branch. The default branch is still v4.0, PR #11's test suite has never run in CI (its branch `ci.yml` references `${{ runner.temp }}` in a job-level `env:` and fails to compile), and the built wheel contains zero data files, so `shoppybot web` cannot start on any non-editable install. The claims are ahead of the reality; this milestone closes that gap.

**Target features:**
- **A. Mainline reconciliation** — fix the branch `ci.yml` compile bug, resolve PR #11 without dropping `httpx`, triage the 4 local commits absent from the PR, land #11 → #12 → Dependabot PRs in dependency order, close the stale #8.
- **B. Distributable artifact** — package-data and a truthful dependency declaration in `pyproject.toml`; installing the wheel must launch `shoppybot web` and play sounds.
- **C. Public-repo readiness** — LICENSE, delete `_deprecated/`, README rewritten for nodriver (not Selenium), `sample.config.yml` rebuilt to include `monitor_only` and every current section, CODEOWNERS, documentation drift.
- **D. Live defect closure** — `/api/bot/start` fire-and-forget reporting, stdin listener EOF spin / None-stdin / executor occupancy, `/api/config` applying to the running process, Discord empty-`url` embeds on `plugin_parked` + `health_degraded`, browser preflight diagnosis, `/api/history` one-shot staleness.
- **E. Scanning to zero** — 7 open Dependabot alerts, 5 real CodeQL alerts, `ci.yml` permissions block, remove the disabled CodeQL workflow, gitleaks as a required check, branch-protection hardening.
- **F. Quality floor** — linter, formatter, and typechecker adopted and wired into CI (none exist today, so CLAUDE.md's own standards are unenforced), coverage measurement, bare-except sites, dead code.
- **G. Community plugin parity** — BF-02 place-order marker on the 5 community plugins, per-step timeouts, `monitor_only` entry guard, confirmation-tab capture.
- **H. Plugin ecosystem (SEED-003)** — user-writable plugin directory, install provenance, machine-readable registry, `PLUGIN_API_VERSION` enforcement, install-time consent gate, capability limits, third-party liability disclaimer, and `install`/`update`/`remove` CLI.
- **I. Ops hardening** — `price_history` index and retention policy.
- **J. UAT repair and triage** — fix the 2 physically impossible test recipes, re-run the 8 items PR #11/#12 unblock, and triage the 61 live-environment items against a stated acceptance bar.

**Seeds in scope:** SEED-002 (release-please has never executed — register it on master and cut a real release), SEED-001 (retire the destructive history rewrite as a recorded decision: gitleaks across 964 commits found only a test-fixture false positive; keep the LICENSE and public-launch half), SEED-003 (full plugin ecosystem, 16 verified gaps).

**Sequencing constraints:** A gates E. B gates SEED-002 being worth running. H is the only workstream needing a genuine design pass. Per RETROSPECTIVE.md lesson 4, G and H both warrant a post-verification REVIEW.md deep-review pass — G touches a safety-critical guard, H adds a new unauthenticated input surface.

## Future Candidate Directions

Candidates for milestones after v5.0:
- **Checkout form-fill for the remaining 5 retailers** (v4.0 covers BestBuy + Amazon; v5.0 workstream G brings them to safety parity, not checkout parity).
- **Order-confirmation detection for the 5 community plugins** — currently Amazon/BestBuy only; every community plugin falls through the detector.
- **Request/API-mode (hybrid) checkout** — faster than DOM but per-site reverse-engineering and an arms race.
- **Live-environment UAT execution** — v5.0 workstream J triages and repairs the checklist; actually running the ~61 live-retail/live-host items remains operator work gated on a funded 2captcha balance, an Ubuntu host, and a real drop.
- **Process isolation for third-party plugins** — the real fix for the SEED-003 blast-radius problem, and by far the most expensive; v5.0 ships consent plus capability limits instead.

<details>
<summary>Shipped: v4.0 Win-the-Drop (Acquisition Core + Reliability) — 2026-06-25</summary>

**Goal:** Make ShopPyBot complete *verified* orders on limited-release drops, and survive multi-hour unattended runs without one fault taking everything down.

**Delivered features:**
- Acquisition Core: checkout profile (shipping/billing) + form-fill on BestBuy + Amazon; order-confirmation capture (mark `purchased` only on a real confirmation, not a button click); bounded retry-on-cart with backoff; per-item/per-step checkout time budget; a central monitor-only run mode that also closes the `test_mode` place-order hole (6 of 7 plugins).
- Always-On Reliability: per-coroutine supervision + backoff restart; browser-crash detection + relaunch; encrypted session/cookie persistence; DB read-path error isolation; per-item orchestrator timeout; structured health/heartbeat surface; one unified transient retry/backoff (`RetryPolicy`).
- Opportunistic server-safety: headless pygame import-crash guard; SIGTERM/SIGINT teardown bridge (stop orphaning Chrome).

**Constraints held:** v2.0 security posture (no plaintext secrets, CLI default, web optional/localhost); payment via retailer-saved methods + CVV-at-runtime (never persist full card data, PCI); checkout work targets the `nodriver` plugin stack.

</details>

## Requirements

### Validated (existing, working)

- ✓ Amazon stock availability check (DOM button detection)
- ✓ Amazon auto-buy flow (quantity → buy-now → place order)
- ✓ BestBuy stock availability check
- ✓ BestBuy auto-buy flow (add-to-cart → checkout → CVV → place order)
- ✓ SQLite purchased tracking (prevents re-buying)
- ✓ Config-driven item list (config.yml)
- ✓ Sound notifications (mp3/wav via pygame)
- ✓ Custom colored logging with file output (writeLog)
- ✓ Test mode (skips final purchase click)
- ✓ ChromeDriver auto-download (webdriver_manager)

### Validated (shipped v1 + v2.0)

- ✓ Plugin interface ABC + auto-discovery from `plugins/` — v1 (Phases 1-2)
- ✓ Amazon + BestBuy migrated to plugin interface — v1 (Phase 2)
- ✓ New platforms: Walmart, Target, GameStop, Square Enix, NewEgg — v1 (Phase 6)
- ✓ Async/parallel item checking (concurrent platform checks) — v1 (Phase 4)
- ✓ Per-platform flat config sections + moderate anti-detection (delays, UA rotation, headless toggle) — v1 (Phases 1, 6)
- ✓ Discord / Email-SMTP / SMS-Twilio notifications, fan-out dispatcher with dedup — v1 (Phase 5)
- ✓ Plugin contributor docs (CONTRIBUTING.md, PLUGIN_DEV.md, SECURITY.md, templates) — v1 (Phase 3)
- ✓ Modular `BotService` core + installable package + `shoppybot` entry point — v2.0 (Phase 7)
- ✓ Dynamic `CredentialStore` (keyring / encrypted-file / env-var), no plaintext on disk — v2.0 (Phase 8)
- ✓ CLI front-end (run/setup/items/config) over the core — v2.0 (Phase 9)
- ✓ Optional FastAPI local web UI (items/config/credentials/control) — v2.0 (Phase 10)
- ✓ Cross-platform per-OS paths + CI matrix + PLATFORMS.md — v2.0 (Phase 11)

### Validated (shipped v3.0 Resilience + Ecosystem)

- ✓ Anti-detection: JS stealth + proxy rotation with ban detection — v3.0 (Phase 13)
- ✓ Anti-detection: 2captcha opt-in reCAPTCHA-v2 solving (balance check, spend cap, async executor) — v3.0 (Phase 14)
- ✓ Plugin ecosystem: ABC difficulty/requires_proxy/requires_captcha attrs, `plugins list` CLI, wiki registry spec, contributor docs — v3.0 (Phase 15)
- ✓ Price monitoring: per-item target price, price history table, price-drop fan-out alerts, price-history CLI — v3.0 (Phase 16)
- ✓ Stability: v2.0 audit tech-debt resolved + test hardening (548 tests) — v3.0 (Phases 12, 17)

### Validated (shipped v4.0 Win-the-Drop — Acquisition Core + Reliability)

- ✓ Acquisition: checkout profile (shipping/billing) + form-fill (BestBuy, Amazon) — v4.0 (Phase 20)
- ✓ Acquisition: order-confirmation capture / verified purchase — v4.0 (Phase 19)
- ✓ Acquisition: bounded retry-on-cart with backoff (idempotent, no double-buy) — v4.0 (Phase 21)
- ✓ Acquisition: per-item/per-step checkout time budget — v4.0 (Phases 21, 22)
- ✓ Acquisition: central monitor-only run mode + close test_mode place-order hole — v4.0 (Phase 18)
- ✓ Reliability: per-coroutine supervision + backoff restart — v4.0 (Phase 22)
- ✓ Reliability: browser-crash detection + relaunch — v4.0 (Phase 22)
- ✓ Reliability: encrypted session/cookie persistence — v4.0 (Phase 23)
- ✓ Reliability: DB read-path error isolation — v4.0 (Phase 22)
- ✓ Reliability: per-item orchestrator timeout — v4.0 (Phase 22)
- ✓ Reliability: structured health/heartbeat surface — v4.0 (Phase 24)
- ✓ Reliability: unified RetryPolicy (one backoff source) — v4.0 (Phase 21)
- ✓ Server-safety: headless pygame import-crash guard + SIGTERM/SIGINT teardown bridge — v4.0 (Phases 24, 22)

### Validated (shipped v4.1 Dashboard & Observability)

- ✓ Redesigned dashboard on a vendored zero-Node design system (tokens/components, light/dark, FOUC-safe) — v4.1 (Phase 25)
- ✓ Read-only observability REST endpoints (history, price-history, filtered logs), to_thread-wrapped + credential-scrubbed — v4.1 (Phase 26)
- ✓ SSE infrastructure: single /api/events stream, uvicorn sole-producer bridge, keepalive, disconnect cleanup — v4.1 (Phase 27)
- ✓ Live observability surfaces: per-plugin health cards, confirmed-buys table, price-history charts, filterable log viewer, uptime bar — v4.1 (Phase 28)
- ✓ SSE client wiring: EventSource replaces polling, fallback, Live/Reconnecting indicator — v4.1 (Phases 29, 29.1)

### Validated (shipped v4.2 Release Readiness)

- ✓ Place-order-timeout double-buy idempotency guard (write-ahead DB marker + `_PossiblyPlaced` sentinel), Amazon + BestBuy — v4.2 (Phase 30, BF-02, HIGH)
- ✓ Amazon WAF auto-solve wired to the existing 2captcha solver, manual-pause fallback preserved — v4.2 (Phase 30, BF-01)
- ✓ Plugin login verified via real post-login DOM/URL signals across all 7 plugins — v4.2 (Phase 30, BF-03)
- ✓ Non-destructive secret-scan audit (gitleaks CI job + local guard) — v4.2 (Phase 31, RH-01)
- ✓ CodeQL workflow repaired (retired Node16 actions bumped) — v4.2 (Phase 31, RH-04)
- ✓ `.github/dependabot.yml` + all open dependency vulnerability alerts remediated — v4.2 (Phase 31, RH-05)
- ✓ `pyproject.toml` version reconciled to `2.0.0` + release-please seeded (python release-type) — v4.2 (Phase 32, RH-02, RH-03)
- ✓ README rewritten for the current 7-platform architecture, install, and badges — v4.2 (Phase 32, RH-06)
- ✓ Real maintainer security contact via GitHub Private Vulnerability Reporting, placeholder removed — v4.2 (Phase 32, RH-07)
- ✓ Platform delay-config fields harmonized (`delay_seconds`/`delay_jitter`) with legacy back-compat shim — v4.2 (Phase 33, CFG-01)
- ✓ Generic per-platform config extension point (`extra="allow"` + `get_platform_config()`), zero core schema edits — v4.2 (Phase 33, CFG-02)
- ✓ `[plugin]` log tag on every line + `/api/logs` plugin filter (completes OBS-08) — v4.2 (Phase 34, FC-01)
- ✓ Outcome analytics (success-rate, time-to-checkout) over confirmed-order records — v4.2 (Phase 34, FC-02)
- ✓ SSR items-table remove button works without JS — v4.2 (Phase 35, AF-01)
- ✓ Raw `last_heartbeat` scrubbed from `get_status()`/SSE — v4.2 (Phase 35, AF-02)
- ✓ Dead `escHtml()` helper removed — v4.2 (Phase 35, AF-03)
- ✓ v4.0/v4.1 planning-artifact frontmatter reconciled to match passing validation status — v4.2 (Phase 35, DH-01/02/03)

### Active

Milestone v5.0 Real Release & Plugin Ecosystem — workstreams A-J (see Current Milestone above). REQ-IDs assigned in `.planning/REQUIREMENTS.md`.

### Deferred

- Request/API-mode (hybrid) checkout (XL arms-race) — follow-on after v4.0
- Virtual-waiting-room / queue survival: Queue-it, PerimeterX, Akamai, DataDome (XL) — follow-on
- Multi-account / multi-profile parallel attempts (XL, most ToS-hostile) — follow-on, opt-in if ever
- Amazon WAF CAPTCHA live-challenge acceptance — code wiring shipped v4.2 (BF-01); live-challenge proof against a real AWS-WAF challenge stays operator debt
- BF-02 marker propagation to the 5 community plugins (Walmart, Target, GameStop, NewEgg, SquareEnix) — mechanical follow-up, closes the residual double-buy exposure
- Destructive public-repo history scrub/squash (SEED-001 remainder) — operator-gated one-time action, when ready to make the repo public. Non-destructive audit shipped v4.2 (RH-01); SEED-002 release-please tagging is code-complete (v4.2), pending first live Actions run

### Out of Scope

- PyPI package per plugin — adds packaging overhead; plugins/ folder achieves discoverability more simply
- (v2.0) GUI / web dashboard is NOT out of scope: an OPTIONAL local web UI exists over the modular core; the CLI remains default and the GUI is never required.
- (v3.0 update) Proxy rotation, fingerprint resilience, CAPTCHA solving, and price monitoring are no longer out of scope: shipped in v3.0.
- (v4.0) Acquisition arms-race tactics — request/API-mode checkout, virtual-waiting-room survival, multi-account farming — deferred and uncommitted; ToS-hostile and high-maintenance.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Drop-in .py file plugins | Zero config for contributors; auto-discovered at startup | Chosen |
| plugins/ folder + GitHub wiki | Simple PR workflow; no PyPI packaging burden on contributors | Chosen |
| Async/parallel checking | Sequential loop too slow for 7+ platforms; async enables concurrent checks | Chosen |
| Moderate anti-detection | Personal use; advanced stealth is over-engineering for this audience | Chosen |
| Flat per-platform config | `platforms: amazon: {email, pwd}` — readable, no repetition per item | Chosen |
| All 4 plugin methods required | Consistent interface makes the framework predictable; auto_buy can be a no-op | Chosen |
| (v2.0) Modular core + thin front-ends | CLI and optional GUI both call one core service; no logic duplicated in front-ends | Chosen |
| (v2.0) Dynamic CredentialStore | OS keyring with encrypted-file fallback for headless Ubuntu, env-var last resort; secrets never plaintext on disk | Chosen |
| (v2.0) Local web UI via FastAPI | Most portable across Ubuntu/Windows, clean core/UI separation, optional extra; binds localhost by default | Chosen |
| (v2.0 reversal) No secrets in SQLite | Storing creds in the local DB is plaintext-on-disk, weaker than env/keyring; rejected in favor of CredentialStore | Chosen |
| (v4.0) Single `place_order_guarded()` gate on the ABC | One enforcement point honors monitor-only/`test_mode` for all 7 plugins; closed the confirmed 6-of-7 hole instead of patching each plugin | ✓ Good |
| (v4.0) `purchased` only on a confirmed order number | A button click is not a purchase; confirmation-URL + order-id capture is the idempotency anchor that prevents double-buy on retry | ✓ Good |
| (v4.0) One unified `RetryPolicy` | Supervisor-restart and cart-retry share one backoff module so the two retry concepts cannot diverge or compound into a runaway loop | ✓ Good |
| (v4.0) Retailer-saved payment + CVV-at-runtime | Never persist full card/PAN (PCI scope); CVV via `getpass`, never logged; AST CI assertion guards against leaks | ✓ Good |
| (v4.0) Live-environment UAT deferred as tracked debt | Live retail checkout is ToS/legal risk in CI; confirmation/form-fill selectors verified by manual UAT, tracked in STATE.md Deferred Items | — Pending (operator live-buy checklist) |
| (v4.1) uPlot vendored, no CDN/Node | Zero-Node is a hard constraint; uPlot is MIT, ~52KB, Canvas, dependency-free — vendored under web/static | ✓ Good |
| (v4.1) 3-file CSS split (tokens/components/dashboard) | Token-only component rules keep theming maintainable and FOUC-safe; each file under 200 lines | ✓ Good |
| (v4.1) uvicorn _poll_loop is the SOLE SSE producer | Bot daemon thread never touches asyncio.Queue; avoids the cross-loop race that is the highest-risk SSE pitfall | ✓ Good |
| (v4.1) No new Python deps for SSE | Raw starlette StreamingResponse(text/event-stream) covers all needs; no sse-starlette, no FastAPI upgrade | ✓ Good |
| (v4.1) Live-browser/socket UAT deferred as tracked debt | SSE/EventSource and visual rendering need a real browser/live socket; all automated assertions GREEN, live checks tracked in STATE.md | — Pending (operator dashboard checklist) |
| (v4.2) BF-02 write-ahead DB marker + `_PossiblyPlaced` sentinel | Makes the place-order stage non-retryable once clicked, reusing the existing orchestrator alert pattern instead of a new state machine | ✓ Good |
| (v4.2) `_verify_login_generic` shared login-verification mechanism | One verification mechanism for all 7 plugins avoids per-plugin duplication; honest URL/DOM-absence signal even without live-verified selectors | ✓ Good |
| (v4.2) Amazon WAF auto-solve reuses the existing 2captcha solver path | No new CAPTCHA integration; fails safe to the pre-existing manual-pause fallback on any non-success path | ✓ Good |
| (v4.2) `PlatformsConfig(extra="allow")` + `get_platform_config()` extension point | Lets any plugin self-declare its own config section with zero core `config_schema.py` edits; the 7 built-in platforms keep full strict validation | ✓ Good |
| (v4.2) Canonical `delay_seconds`/`delay_jitter` with legacy back-compat shim | Unifies platform delay-config naming without breaking existing configs; activated Amazon/BestBuy poll jitter for the first time | ✓ Good |
| (v4.2) RH-07 resolved to GitHub Private Vulnerability Reporting only, no published email | PVR is GitHub-native and audit-logged; avoids publishing a personal maintainer address | — Pending (operator sign-off; decision made autonomously in operator's absence) |
| (v4.2) BF-02 marker propagation scoped to Amazon + BestBuy only this milestone | The 5 community plugins are independently EXPERIMENTAL/selector-unverified, lowering real-world exposure; deliberate scope cut, not a miss | ⚠️ Revisit (residual double-buy risk identical in mechanism to the closed bug) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-02 — milestone v5.0 Real Release & Plugin Ecosystem scoped from a 221-finding full-repo sweep (PRs, security/quality scans, outstanding UAT, seed gaps, defect re-verification) plus an adversarial completeness pass*
