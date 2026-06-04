# ShopPyBot — Project

## What This Is

A comprehensive, extensible shopping bot that monitors stock and auto-purchases items across multiple retail platforms. The core value is a **drop-in plugin framework** that lets the open source community add new platform integrations by dropping a single Python file into a `plugins/` directory — no core changes required.

## Context

Brownfield refactor of a working personal-use bot (Amazon + BestBuy). The existing sequential Selenium loop, SQLite tracking, and YAML config are proven but limited. This project evolves that foundation into a community-extensible platform.

Target user: technically capable individuals who want automated stock monitoring for limited-release items (collectibles, gaming hardware, etc.), and developers who want to contribute new retail platform integrations.

## Core Value

**The plugin framework.** Without it, this is just another private bot. With it, community contributors can extend coverage to any retail platform without touching core bot logic.

## Current Milestone: v2.0 Modular Core + Cross-Platform UX

**Goal:** Refactor the v1 code into a clean reusable core library, add a dynamic cross-platform secure credential store, and add an optional local web UI, while keeping the CLI the default, all running on Ubuntu (desktop + headless) and Windows.

**Target features:**
- Modular core library: orchestrator/registry/config/plugins/notifications behind a stable API that both CLI and GUI consume (no logic duplicated in front-ends); installable package with a `shoppybot` entry point.
- Dynamic CredentialStore: one interface, runtime-selected backend (OS keyring → encrypted-file fallback for headless Ubuntu → env-var last resort); all secret reads routed through it; no plaintext secrets on disk.
- CLI front-end (default): thinned to call the core; a `setup` command to store/manage credentials + config cross-platform.
- Optional local web UI (FastAPI on localhost): manage items/config/credentials, start/stop the bot, view status/logs; an optional extra, CLI runs without it.
- Cross-platform: verified on Ubuntu and Windows.

**Key constraints:** preserve the v1 security posture (secrets never in config.yml/logs/SQLite plaintext); GUI optional, CLI default; the credential-managing web UI binds to localhost by default.

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

### Active

- [ ] Plugin interface ABC: `check_availability`, `auto_buy`, `login`, `detect_captcha`
- [ ] Auto-discover plugins from `plugins/` directory at startup
- [ ] Refactor Amazon module to implement plugin interface
- [ ] Refactor BestBuy module to implement plugin interface
- [ ] New platform: Walmart
- [ ] New platform: Target
- [ ] New platform: GameStop
- [ ] New platform: Square Enix Store
- [ ] New platform: NewEgg
- [ ] Async/parallel item checking (concurrent platform checks)
- [ ] Per-platform flat config sections (credentials, delays)
- [ ] Discord webhook notifications
- [ ] Email/SMTP notifications
- [ ] SMS/Twilio notifications
- [ ] Moderate anti-detection: per-platform configurable delays, rotating user agents, headless mode toggle
- [ ] Plugin contributor docs + GitHub wiki listing

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
*Last updated: 2026-04-19 after initialization*
