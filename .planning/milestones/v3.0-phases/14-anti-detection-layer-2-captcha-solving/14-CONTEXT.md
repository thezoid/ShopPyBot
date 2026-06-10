# Phase 14: Anti-Detection Layer 2 — CAPTCHA Solving - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Add opt-in automated CAPTCHA solving (reCAPTCHA v2 and Amazon WAF) via the 2captcha service, with full cost visibility and no API-key plaintext exposure. Disabled by default. Integrates with the existing `detect_captcha` hook and manual-pause fallback in the plugins. Builds on Phase 13's anti-detection layer.

</domain>

<decisions>
## Implementation Decisions

### 2captcha Integration
- Hand-rolled client using the already-pinned `requests==2.33.1` (NO new dependency). The 2captcha submit/poll protocol runs inside `run_in_executor` with `asyncio.timeout(120)` so other plugin poll tasks are not blocked during a solve (success criterion 3).
- **Automated solve scope (user decision 2026-06-09): reCAPTCHA v2 only this phase.** Amazon WAF auto-solve is DEFERRED to a tracked follow-up because its token-injection path is site-specific and unverified (research LOW-confidence). The WAF path gracefully falls back to the existing manual pause (never a silent skip). A `solve_amazon_waf()` API stub is created as the future contract. ANTI-06 is narrowed accordingly for Phase 14; see `.planning/todos/pending/waf-auto-solve-followup.md`.

### Credentials & Config
- The 2captcha API key lives EXCLUSIVELY in CredentialStore under `TWOCAPTCHA_API_KEY` — never in config.yml, never logged.
- Single unified `captcha:` config section (reconciles the roadmap's mixed `captcha_solver.enabled` / `captcha.max_solves_per_run` phrasing):
  - `captcha.enabled: bool = False` (disabled by default — success criterion 4)
  - `captcha.max_solves_per_run: int` — caps unbounded API charges
  - `captcha.low_balance_threshold: float = 1.00` (USD) — configurable

### Balance & Cost Visibility
- At startup, check the 2captcha account balance. Log a WARNING when balance < `low_balance_threshold` ($1.00 default).
- When balance is zero, SKIP solver use entirely and fall back to manual pause (success criterion 2).
- `max_solves_per_run` enforces a hard per-run cap on solve attempts to bound cost.

### Failure / Timeout / Cap Fallback
- On any solve failure, the 120s timeout, zero balance, or hitting `max_solves_per_run`: fall back to the EXISTING manual-pause behavior (operator solves in-browser, presses Enter) — never a silent skip. Reuse the current `detect_captcha` pause path; do not duplicate it.

### Claude's Discretion
- Internal module structure (e.g. `core/captcha.py` or similar), exact class/function names, how the solver client is constructed and passed to plugins (mirror how Phase 13's ProxyPool flows via orchestrator/registry), 2captcha endpoint/polling-interval details, and exact config field validation — all at Claude's discretion, guided by RESEARCH, codebase conventions, and the Phase 13 stealth/proxy wiring pattern.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `detect_captcha()` already exists on the plugin ABC and in plugins (e.g. `plugins/shopbot_plugin_amazon.py:85`); the manual-pause prompt ("CAPTCHA detected... Solve it in the browser, then press Enter") is the existing fallback to reuse.
- `core/credentials.py` / CredentialStore — the secure store for `TWOCAPTCHA_API_KEY` (Phase 13 used it for proxy-cred handling patterns).
- `core/orchestrator.py`, `core/registry.py`, `core/service.py` — Phase 13's ProxyPool wiring is the analog for injecting a shared solver into plugins at setup; the orchestrator forbids `input()` in its module (ASYNC-03) — keep the manual pause where it already lives.
- `requests==2.33.1` already pinned — use it inside `run_in_executor`.

### Established Patterns
- nodriver async; `run_in_executor` + `asyncio.timeout` pattern (Phase 13 used asyncio.create_task discipline). pytest + pytest-asyncio; mock `requests` / 2captcha HTTP in unit tests (no live API calls in CI).
- No plugin ABC version bump precedent (Phase 13 added concrete helpers without bumping PLUGIN_API_VERSION).

### Integration Points
- Solver constructed from `cfg.captcha` + CredentialStore key, passed through orchestrator to plugins (mirror ProxyPool flow). Plugin `detect_captcha`/CAPTCHA-handling path calls the solver, falling back to manual pause.

</code_context>

<specifics>
## Specific Ideas

- Default config disables CAPTCHA solving (success criterion 4).
- API key NEVER in config.yml and NEVER logged (success criterion 1).
- Balance check at startup with low-balance WARNING and zero-balance skip→manual (success criterion 2).
- `run_in_executor` + `asyncio.timeout(120)` so solves don't block other poll tasks (success criterion 3).

</specifics>

<deferred>
## Deferred Ideas

- Plugin ecosystem registry — Phase 15.
- Price monitoring — Phase 16.
- Broad v3.0 test hardening — Phase 17.

</deferred>
