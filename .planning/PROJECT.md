# ShopPyBot — Project

## What This Is

A comprehensive, extensible shopping bot that monitors stock and auto-purchases items across multiple retail platforms. The core value is a **drop-in plugin framework** that lets the open source community add new platform integrations by dropping a single Python file into a `plugins/` directory — no core changes required.

## Context

Brownfield refactor of a working personal-use bot (Amazon + BestBuy). The existing sequential Selenium loop, SQLite tracking, and YAML config are proven but limited. This project evolves that foundation into a community-extensible platform.

Target user: technically capable individuals who want automated stock monitoring for limited-release items (collectibles, gaming hardware, etc.), and developers who want to contribute new retail platform integrations.

## Core Value

**The plugin framework.** Without it, this is just another private bot. With it, community contributors can extend coverage to any retail platform without touching core bot logic.

## Current State

**Shipped v2.0 Modular Core + Cross-Platform UX (2026-06-06).** The v1 code is refactored into a reusable core library: all bot logic lives behind a single `BotService` API consumed by both the CLI (default) and an optional FastAPI web UI. A runtime-selected `CredentialStore` (OS keyring → encrypted-file → env-var) centralizes secret access with no plaintext on disk. The package installs via pip with a `shoppybot` console entry point; `python main.py` remains a thin shim. Paths resolve per-OS through `core/paths.py`; a CI matrix (ubuntu-latest + windows-latest, Python 3.13) plus `docs/PLATFORMS.md` document the cross-platform verification.

11 phases / 48 plans, all complete. 66/66 requirements satisfied (44 v1 + 22 v2.0). Full suite: 354 passed, 2 skipped.

**Deferred:** live cross-OS/UI manual checks (keyring restart, masked-TTY, dashboard render, 0.0.0.0 warning) documented in `docs/PLATFORMS.md` and tracked in STATE.md → Deferred Items; run `/gsd:verify-work` on real Ubuntu/Windows to close.

**Next milestone goals:** TBD (run `/gsd:new-milestone`). Candidates from the deferred v2 backlog: GitHub wiki plugin registry, proxy rotation, CAPTCHA solving, price-drop alerts.

**Key constraints (held):** secrets never in config.yml/logs/SQLite plaintext; GUI optional, CLI default; the credential-managing web UI binds to localhost by default.

## Current Milestone: v3.0 Resilience + Ecosystem

**Goal:** Raise real-world buy success on bot-protected platforms, grow the contributor ecosystem, add price-aware tracking, and pay down v2.0 deferred debt.

**Target features:**
- Anti-detection hardening — proxy rotation, CAPTCHA-solving integration, stronger fingerprint resilience.
- Plugin ecosystem — GitHub wiki plugin registry with anti-detection difficulty ratings, plugin discovery/listing, contributor onboarding.
- Price monitoring — per-item target price, price-drop alerts, and price history alongside existing stock alerts.
- Stability / polish — close v2.0 deferred manual cross-OS/UI checks, resolve the 4 audit tech-debt items, harden tests.

**Key constraints:** preserve the v2.0 security posture (no plaintext secrets, CLI default, web optional/localhost); new deps (proxy lib, CAPTCHA SDK) require package-legitimacy review; continues phase numbering from 11.

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

### Active (v3.0 Resilience + Ecosystem)

- [ ] Anti-detection: proxy rotation
- [ ] Anti-detection: CAPTCHA-solving integration
- [ ] Anti-detection: stronger fingerprint resilience
- [ ] Plugin ecosystem: GitHub wiki plugin registry + difficulty ratings
- [ ] Plugin ecosystem: plugin discovery/listing + contributor onboarding
- [ ] Price monitoring: per-item target price + price-drop alerts + price history
- [ ] Stability: close v2.0 deferred cross-OS/UI manual checks
- [ ] Stability: resolve v2.0 audit tech-debt + test hardening

### Deferred

- (Refined into v3.0 Active above.)

### Out of Scope

- PyPI package per plugin — adds packaging overhead; plugins/ folder achieves discoverability more simply
- Proxy rotation / browser fingerprint spoofing — advanced anti-detection is out of scope
- Price monitoring / price drop alerts — stock availability is the core use case
- (v2.0 update) GUI / web dashboard is NO LONGER out of scope: v2.0 adds an OPTIONAL local web UI over the modular core; the CLI remains the default and the GUI is never required.

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
*Last updated: 2026-06-06 — v3.0 Resilience + Ecosystem milestone started*
