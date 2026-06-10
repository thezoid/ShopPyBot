# ShopPyBot — Project

## What This Is

A comprehensive, extensible shopping bot that monitors stock and auto-purchases items across multiple retail platforms. The core value is a **drop-in plugin framework** that lets the open source community add new platform integrations by dropping a single Python file into a `plugins/` directory — no core changes required.

## Context

Brownfield refactor of a working personal-use bot (Amazon + BestBuy). The existing sequential Selenium loop, SQLite tracking, and YAML config are proven but limited. This project evolves that foundation into a community-extensible platform.

Target user: technically capable individuals who want automated stock monitoring for limited-release items (collectibles, gaming hardware, etc.), and developers who want to contribute new retail platform integrations.

## Core Value

**The plugin framework.** Without it, this is just another private bot. With it, community contributors can extend coverage to any retail platform without touching core bot logic.

## Current State

**Shipped v3.0 Resilience + Ecosystem (2026-06-10).** Built on the v2.0 modular core (`BotService` API behind a CLI-default front-end plus an optional FastAPI web UI; runtime-selected `CredentialStore` with no plaintext on disk). v3.0 added anti-detection (JS stealth + proxy rotation with ban detection; opt-in 2captcha reCAPTCHA-v2 solving with balance check and spend cap), the plugin ecosystem (ABC `difficulty`/`requires_proxy`/`requires_captcha` attrs, `shoppybot plugins list`, a GitHub-wiki registry spec, contributor docs), and price monitoring (per-item target price, price history table, price-drop fan-out alerts, `items price-history` CLI).

v3.0: 6 phases (12-17) / 21 plans, all complete. Full suite: 548 passed, 2 skipped.

**Deferred (carried):** v2.0 live cross-OS/UI manual checks (keyring restart persistence, masked-TTY setup, web dashboard live render, 0.0.0.0 warning) tracked in STATE.md → Deferred Items; Amazon WAF CAPTCHA auto-solve deferred (degrades to manual pause).

**Key constraints (held):** secrets never in config.yml/logs/SQLite plaintext; GUI optional, CLI default; the credential-managing web UI binds to localhost by default.

## Current Milestone: v4.0 Win-the-Drop (Acquisition Core + Reliability)

**Goal:** Make ShopPyBot complete *verified* orders on limited-release drops, and survive multi-hour unattended runs without one fault taking everything down.

**Target features:**
- Acquisition Core: checkout profile (shipping/billing) + form-fill on 1-2 reliable retailers (BestBuy, Amazon); order-confirmation capture (mark `purchased` only on a real confirmation, not a button click); bounded retry-on-cart with backoff; per-item/per-step checkout time budget; a central monitor-only run mode that also closes the `test_mode` place-order hole (6 of 7 plugins).
- Always-On Reliability: per-coroutine supervision + backoff restart; browser-crash detection + relaunch; encrypted session/cookie persistence; DB read-path error isolation; per-item orchestrator timeout; structured health/heartbeat surface; one unified transient retry/backoff.
- Opportunistic server-safety: headless pygame import-crash guard; SIGTERM/SIGINT teardown bridge (stop orphaning Chrome).

**Deferred to follow-on:** request/API-mode checkout, virtual-waiting-room/queue survival (Queue-it/PerimeterX/Akamai/DataDome), multi-account/multi-profile parallel attempts, Amazon WAF auto-solve. All XL arms-race or ToS-hostile.

**Key constraints:** preserve the v2.0 security posture (no plaintext secrets, CLI default, web optional/localhost); payment via retailer-saved methods + CVV-at-runtime (never persist full card data, PCI); checkout work targets the `nodriver` plugin stack; continues phase numbering from 17.

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

### Active (v4.0 Win-the-Drop — Acquisition Core + Reliability)

- [ ] Acquisition: checkout profile (shipping/billing) + form-fill (BestBuy, Amazon)
- [ ] Acquisition: order-confirmation capture / verified purchase
- [ ] Acquisition: bounded retry-on-cart with backoff (idempotent, no double-buy)
- [ ] Acquisition: per-item/per-step checkout time budget
- [ ] Acquisition: central monitor-only run mode + close test_mode place-order hole
- [ ] Reliability: per-coroutine supervision + backoff restart
- [ ] Reliability: browser-crash detection + relaunch
- [ ] Reliability: encrypted session/cookie persistence
- [ ] Reliability: DB read-path error isolation
- [ ] Reliability: per-item orchestrator timeout
- [ ] Reliability: structured health/heartbeat surface

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
*Last updated: 2026-06-10 — v4.0 Win-the-Drop milestone started*
