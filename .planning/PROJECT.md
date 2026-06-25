# ShopPyBot — Project

## What This Is

A comprehensive, extensible shopping bot that monitors stock and auto-purchases items across multiple retail platforms. The core value is a **drop-in plugin framework** that lets the open source community add new platform integrations by dropping a single Python file into a `plugins/` directory — no core changes required.

## Context

Brownfield refactor of a working personal-use bot (Amazon + BestBuy). The existing sequential Selenium loop, SQLite tracking, and YAML config are proven but limited. This project evolves that foundation into a community-extensible platform.

Target user: technically capable individuals who want automated stock monitoring for limited-release items (collectibles, gaming hardware, etc.), and developers who want to contribute new retail platform integrations.

## Core Value

**The plugin framework.** Without it, this is just another private bot. With it, community contributors can extend coverage to any retail platform without touching core bot logic.

## Current State

**Shipped v4.0 Win-the-Drop — Acquisition Core + Reliability (2026-06-25).** Built on the v3.0 resilience/ecosystem layer and the v2.0 modular core (`BotService` API behind a CLI-default front-end plus an optional FastAPI web UI; runtime-selected `CredentialStore` with no plaintext on disk). v4.0 makes the bot complete *verified* orders on limited-release drops and survive multi-hour unattended runs: a central monitor-only gate + `place_order_guarded()` ABC closing the 6-of-7 `test_mode` hole; order-confirmation detection (`purchased` only on a real order number); checkout profile + BestBuy/Amazon form-fill with CVV-at-runtime; one unified `RetryPolicy` with per-step timeouts and idempotent cart-retry; per-coroutine supervisor with browser relaunch, DB read isolation, per-item timeout, and a SIGTERM/SIGINT teardown bridge; Fernet-encrypted session persistence; and a per-plugin health surface (`get_status`, `health_degraded` alert, `shoppybot status`) plus a headless pygame import-crash guard.

v4.0: 7 phases (18-24) / 29 plans, all complete. Full suite: 755 passed, 2 skipped. Audit status `tech_debt` (no blockers; pre-accepted live-UAT debt).

**Deferred (carried):** all live-environment UAT (monitor-only/confirmation/form-fill/relaunch/SIGTERM/session/headless) tracked in STATE.md → Deferred Items as the operator's pre-production live-buy checklist; Amazon WAF CAPTCHA auto-solve (manual-pause fallback); public-release hardening — git-history scrub/squash (SEED-001) + release-please tagging (SEED-002).

**Key constraints (held):** secrets never in config.yml/logs/SQLite plaintext; full card number / CVV never persisted to disk or logs (retailer-saved payment + CVV-at-runtime only); GUI optional, CLI default; the credential-managing web UI binds to localhost by default.

## Current Milestone: v4.1 Dashboard & Observability

**Goal:** Redesign the optional FastAPI web dashboard with a polished zero-dependency design system and surface rich live operational observability over SSE — without breaking the CLI-default, localhost-bound, no-Node posture.

**Target features:**
- Polished vendored design system (tokens, components, light/dark) via the frontend-design skill — no Node/CDN/external fonts
- Live per-plugin health cards (status / heartbeat / last-check / degraded) from `get_status()` + `HealthRegistry`
- Run history + recent confirmed buys (order_id, confirmed_at — BUY-04 records)
- Price-history charts (per-item, from the `price_history` table)
- Better log viewer (filter by level/plugin, search, tail)
- SSE push for live status/log/health updates (replaces the 2s poll)

**Constraints (held):** CLI default; web optional + localhost bind + CSRF + non-local warning; zero-Node (no package.json/CDN/external fonts — vendored CSS only); observability is read-only over `BotService.get_status()` + DB, no new secrets.

**Research flags:** charts must be dependency-free (vendored tiny lib or hand-rolled SVG/canvas); price data is Amazon-only today (PRICE-02) so charts stay sparse for other plugins.

## Future Candidate Directions (post-v4.1)

**Active milestone:** v4.1 Dashboard & Observability (scoped 2026-06-25; phases continue from 24). Remaining candidates for later milestones:
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

### Active (v4.1 Dashboard & Observability)

_Requirements defined in `.planning/REQUIREMENTS.md` (mapped by the roadmap). Focus: dashboard redesign (vendored design system) + live observability — per-plugin health cards, run/buy history, price-history charts, better log viewer, SSE push._

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
*Last updated: 2026-06-25 — v4.1 Dashboard & Observability milestone started*
