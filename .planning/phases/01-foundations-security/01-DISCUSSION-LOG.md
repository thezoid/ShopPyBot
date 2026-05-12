# Phase 1: Foundations + Security - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 01-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 01-foundations-security
**Areas discussed:** Driver type in ABC, Selenium drop scope, CVV/cred prompt UX, Config migration policy
**Areas where Claude defaulted:** Pydantic strictness + env var naming

---

## Driver type in ABC

### Q1: Driver parameter in the plugin ABC signature?

| Option | Description | Selected |
|--------|-------------|----------|
| D. Drop param, use self.driver | CORE-01 signature becomes `auto_buy(self, url, config)` and `login(self, config)`. Plugin owns its driver. | yes |
| B. Typed Protocol adapter | Define a minimal `PluginDriver` Protocol (get, find, click, quit). Plugin holds self.driver but ABC method accepts the Protocol. | |
| C. Concrete nodriver.Browser | Type as `nodriver.Browser`. Honest, full IDE support, locks framework to nodriver permanently. | |
| A. driver: Any | Duck-typed. Maximum flexibility, no IDE help, no contract enforcement. | |

**User's choice:** D
**Notes:** Cleanest given the locked "plugin owns its driver in __init__" decision. Driver Protocol abstraction noted as deferred for `PLUGIN_API_VERSION = 2`.

### Q2: How does the plugin get config and construct its driver?

| Option | Description | Selected |
|--------|-------------|----------|
| `__init__(self, platform_config)` | Plugin receives only its own platform block. Constructs self.driver inside __init__. | yes |
| `__init__(self, app_config)` | Plugin receives full AppConfig and reaches into its own section. Cross-platform reads possible. | |
| `__init__(self) + async setup()` | Two-phase init for async-native driver lifecycle. | |

**User's choice:** `__init__(self, platform_config)`
**Notes:** No global config import in plugins. Async two-phase setup deferred to Phase 4 review if nodriver requires it.

---

## Selenium drop scope

### Q1: When does Selenium get dropped?

| Option | Description | Selected |
|--------|-------------|----------|
| B. Defer to Phase 2 | Phase 1 keeps Selenium runnable, applies stealth via Selenium. Phase 2 swaps to nodriver atomically with ABC migration. | yes |
| A. Gut Selenium in Phase 1 | Delete selenium/amazon_bot.py/bestbuy_bot.py and build nodriver factory. Bot does not run end-to-end until Phase 2. | |
| C. Dual-track | Both libs available, driver factory selects per-plugin. | |

**User's choice:** B
**Notes:** Keeps the published codebase runnable end-to-end after Phase 1 ships. Open-sourcing a non-runnable codebase looks abandoned. Tradeoff: Selenium-specific stealth code in Phase 1 will be replaced in Phase 2 (acceptable).

---

## CVV/cred prompt UX

### Q1: When does the CVV prompt fire?

| Option | Description | Selected |
|--------|-------------|----------|
| Once at startup, per platform | Iterate enabled platforms with auto_buy:true, getpass each CVV upfront. Held in memory. Fail-fast. | yes |
| Lazy, on first auto-buy attempt | Bot starts immediately; prompts CVV when stock detected. Risk: prompt arrives at random hours. | |
| Per-purchase event | Prompt every single purchase. Highest friction, best for shared workstations. | |

**User's choice:** Once at startup, per platform
**Notes:** Prevents the "missed buy window because user was away when prompt fired" failure mode.

### Q2: Non-TTY behavior (running under systemd, cron, container)?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard fail + opt-in env var escape | Non-TTY refuses to start; opt-in via `SHOPBOT_ALLOW_CVV_ENV=true` reads `SHOPBOT_<PLATFORM>_CVV`. | yes |
| Hard fail only | Non-TTY = abort. No env var fallback. Most secure. | |
| Silent downgrade to check-only | Log warning, run check-only. User may not notice auto-buy disabled. | |

**User's choice:** Hard fail + opt-in env var escape
**Notes:** Documented in SEC-06 README disclaimer as "trusted infrastructure only" with `/proc/<pid>/environ` exposure warning.

---

## Config migration policy

### Q1: Old config.yml schema migration policy?

| Option | Description | Selected |
|--------|-------------|----------|
| B. Warn + halt with instructions | Detect old keys, print migration block, exit non-zero. No shim. | yes |
| C. Auto-rewrite with .bak backup | Generate new config.yml from old, save .bak, exit 1 asking review. | |
| A. Warn + back-compat shim | Silently remap old keys and keep running. Friction-free upgrade BUT cannot forward credential fields without violating SEC-01. | |

**User's choice:** B
**Notes:** Back-compat shim explicitly rejected because forwarding old credential fields from `config.yml` defeats SEC-01 (env vars only).

---

## Claude's Discretion

These were not asked of the user; the planner has flexibility:
- Exact wording of Pydantic validation error messages (CORE-05).
- Internal module layout (`core/` package vs flat root) — defer to PATTERNS analysis during planning.
- Logger singleton implementation pattern for INFRA-02.
- Whether `requirements.txt` adds hash pins beyond version pins (INFRA-01).
- `getpass` KeyboardInterrupt behavior at the prompt.

## Pydantic strictness + env var naming (Claude default — not discussed)

User selected "Claude decides" upfront. Defaults applied:
- `extra="forbid"` (unknown keys produce Pydantic validation error).
- Nested env var convention `SHOPBOT_PLATFORMS__AMAZON__EMAIL` per pydantic-settings `env_nested_delimiter="__"`.
- CVV opt-in env vars use a flat name (`SHOPBOT_AMAZON_CVV`) since CVV is runtime-only and not part of the config schema.

## Deferred Ideas

- Driver Protocol abstraction (`PluginDriver`) — `PLUGIN_API_VERSION = 2`.
- Auto-migration of old config.yml — revisit only if manual migration painful.
- Two-phase async `__init__` + `setup()` — Phase 4 review if nodriver requires it.
- Per-purchase CVV prompting — revisit on user request.
- Pre-commit hook scanning for `_pwd` / `_cvv` patterns — INFRA backlog.
