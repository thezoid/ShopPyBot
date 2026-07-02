# ShopPyBot — Project

## What This Is

A comprehensive, extensible shopping bot that monitors stock and auto-purchases items across multiple retail platforms. The core value is a **drop-in plugin framework** that lets the open source community add new platform integrations by dropping a single Python file into a `plugins/` directory — no core changes required.

## Context

Brownfield refactor of a working personal-use bot (Amazon + BestBuy). The existing sequential Selenium loop, SQLite tracking, and YAML config are proven but limited. This project evolves that foundation into a community-extensible platform.

Target user: technically capable individuals who want automated stock monitoring for limited-release items (collectibles, gaming hardware, etc.), and developers who want to contribute new retail platform integrations.

## Core Value

**The plugin framework.** Without it, this is just another private bot. With it, community contributors can extend coverage to any retail platform without touching core bot logic.

## Current State

**Shipped v4.1 Dashboard & Observability (2026-06-30).** The optional FastAPI web dashboard is rebuilt on a zero-Node vendored design system (3-file CSS split, light/dark with FOUC-safe inline theming, uPlot 1.6.32 vendored) and now surfaces live operational observability over a single `/api/events` SSE stream: per-plugin health cards (status / heartbeat-age / error+items counters / confirmed-orders), a confirmed-buys table, per-item price-history charts, a filterable color-coded log viewer with tail, and an uptime bar. Read-only REST endpoints (`/api/history`, `/api/price-history/{link_b64}`, filtered `/api/logs`) back the surfaces with every sync read wrapped in `asyncio.to_thread`, `last_error` scrubbed, and a credential-leak CI guard. The prior 2s poll is replaced by `EventSource` with a polling fallback and a Live/Reconnecting indicator. The CLI-default, localhost-bound, no-CDN, read-only-observability posture is unchanged.

v4.1: 6 phases (25-29 + inserted 29.1) / 20 plans, all complete. Full suite: 807 passed, 2 skipped. Audit status `tech_debt` (no blockers; 2 low-sev warnings + pre-accepted live-UAT debt).

**Built on v4.0 Win-the-Drop (2026-06-25):** verified-order checkout (monitor-only gate + `place_order_guarded()` ABC, order-confirmation capture, checkout profile + BestBuy/Amazon form-fill with CVV-at-runtime, one unified `RetryPolicy` with per-step timeouts and idempotent cart-retry, per-coroutine supervisor + browser relaunch + DB read isolation + SIGTERM/SIGINT teardown, Fernet session persistence, per-plugin health surface) over the v2.0 modular core (`BotService` behind a CLI-default front-end + optional FastAPI web UI; runtime `CredentialStore`, no plaintext on disk).

**Deferred (carried):** all live-environment UAT (v4.0 acquisition checks + v4.1 dashboard live-browser/socket checks) tracked in STATE.md → Deferred Items as the operator's pre-production checklist; Amazon WAF CAPTCHA auto-solve (manual-pause fallback); public-release hardening — git-history scrub/squash (SEED-001) + release-please tagging (SEED-002).

**Key constraints (held):** secrets never in config.yml/logs/SQLite plaintext; full card number / CVV never persisted to disk or logs (retailer-saved payment + CVV-at-runtime only); GUI optional, CLI default; the credential-managing web UI binds to localhost by default; zero-Node (no package.json/CDN/external fonts — vendored CSS/JS only); observability is read-only over `get_status()` + DB with no new secrets.

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

## Current Milestone: v4.2 Release Readiness

**Goal:** Close every outstanding code-actionable item — seeds, breakfixes, audit warnings, deferred sub-features, and release-hardening gaps — so the public repo reaches a stable, release-ready state. "Done" = code-complete and green in CI, pending only the live-environment operator UAT that is inherently untestable in CI.

**Target features:**
- **Release-Hardening** — SEED-001 non-destructive history/`.gitignore`/artifact secret audit; SEED-002 release-please automation seeded at product **v2.0.0** + `pyproject.toml` version reconcile; fix the silently-failing CodeQL scan (retired v1 actions); add `dependabot.yml` + remediate open vuln alerts; refresh the stale README; real maintainer security contact.
- **Audit-Fixes** — SSR remove-button graceful-degradation handler (UI-03); stop the raw `last_heartbeat` float leaking into `get_status()`/SSE; remove the dead `escHtml()` helper.
- **Breakfix** — Amazon WAF auto-solve plugin wiring (manual-pause fallback kept); HIGH place-order-timeout double-buy hardening; robust post-login DOM/URL verification.
- **Config-Refactor** — harmonize platform delay-config field names with back-compat; flexible per-platform config sections so plugins self-declare config.
- **Feature-Completion** — `[plugin]` log tags + `/api/logs` plugin filter (completes OBS-08); outcome analytics (success-rate / time-to-checkout) over BUY-04 order records.
- **Doc-Hygiene** — reconcile lagging v4.1 VALIDATION/SUMMARY frontmatter and v4.0 nyquist flags.

**Key context:** Debt-closure milestone scoped from an exhaustive automated inventory sweep (64 raw → 20 code-actionable). Live-environment UAT (Phases 18-24/27/28/29/29.1), ~37 community-plugin selector TODOs, remaining-5-retailer form-fill, and XL arms-race items (request/API mode, waiting-room survival, multi-account) remain tracked operator debt — explicitly out of scope per the "pending testing = done" definition. SEED-001 is split: the non-destructive audit/scan is in scope; the destructive history rewrite / force-push / secret rotation is an operator-gated one-time action.

## Future Candidate Directions

Candidates for later milestones (next milestone not yet scoped — run `/gsd:new-milestone`):
- **Public-release hardening** — git-history scrub/squash (SEED-001) + release-please version tagging (SEED-002); a dedicated release milestone.
- **Checkout form-fill for the remaining 5 retailers** (v4.0 covers BestBuy + Amazon).
- **Request/API-mode (hybrid) checkout** — faster than DOM but per-site reverse-engineering and an arms race.
- **Outcome analytics** (success rate, time-to-checkout) built on the BUY-04 order records.

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

### Active (v4.2 Release Readiness)

Scoped in `REQUIREMENTS.md` — 20 requirements across 6 categories:
- **RH-01..07** Release-Hardening (history/gitignore audit, release-please + version reconcile, CodeQL fix, dependabot + vuln review, README refresh, security contact)
- **AF-01..03** Audit-Fixes (SSR remove handler, last_heartbeat leak, dead escHtml)
- **BF-01..03** Breakfix (WAF wiring, place-order double-buy hardening [HIGH], post-login verification)
- **CFG-01..02** Config-Refactor (field harmonization, flexible per-platform config)
- **FC-01..02** Feature-Completion (plugin log tags + filter, outcome analytics)
- **DH-01..03** Doc-Hygiene (v4.1 VALIDATION/SUMMARY frontmatter, v4.0 nyquist flags)

### Deferred

- Request/API-mode (hybrid) checkout (XL arms-race) — follow-on after v4.0
- Virtual-waiting-room / queue survival: Queue-it, PerimeterX, Akamai, DataDome (XL) — follow-on
- Multi-account / multi-profile parallel attempts (XL, most ToS-hostile) — follow-on, opt-in if ever
- Amazon WAF CAPTCHA auto-solve — re-deferred (todo: `waf-auto-solve-followup`)
- Public-release hardening: git-history scrub/squash (SEED-001) + release-please tagging (SEED-002) — when a release milestone is scoped

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
*Last updated: 2026-07-02 — v4.2 Release Readiness scoped (debt-closure milestone, 20 requirements)*
