# ShopPyBot — Requirements

**Current Milestone:** v3.0 Resilience + Ecosystem
**Defined:** 2026-06-07

Prior milestone requirements (v1 44 + v2.0 22 = 66, all satisfied) are archived at
`.planning/milestones/v2.0-REQUIREMENTS.md`. This file scopes v3.0 only.

---

## v3.0 Requirements (Active — Resilience + Ecosystem)

### Anti-Detection Hardening

- [x] **ANTI-04**: User can enable proxy rotation via an opt-in `proxy:` config section (disabled by default) with a configurable pool of `scheme://user:pass@host:port` URLs, using sticky sessions that hold one IP per check cycle.
- [x] **ANTI-05**: Bot detects ban signals (HTTP 403/429/503, challenge-redirect, block-phrase body) and automatically rotates to the next proxy, retiring a proxy for a cooldown period after N consecutive failures.
- [ ] **ANTI-06**: User can enable CAPTCHA solving (reCAPTCHA v2 and Amazon WAF) via 2captcha through an opt-in `captcha_solver:` flag, with the API key stored in CredentialStore (`TWOCAPTCHA_API_KEY`), never in config.yml.
  - **Phase 14 scope (user decision 2026-06-09):** reCAPTCHA v2 auto-solving delivered end-to-end. Amazon WAF auto-solving DEFERRED to a tracked follow-up (`.planning/todos/pending/waf-auto-solve-followup.md`) — WAF gracefully falls back to manual pause this phase; `solve_amazon_waf()` API stub retained. Config section unified as `captcha:` (per Phase 14 CONTEXT).
- [ ] **ANTI-07**: Bot checks the CAPTCHA-solver account balance at startup, warns when balance is low, and skips solver use when balance is zero.
- [x] **ANTI-08**: Bot applies a JS fingerprint stealth patch at browser startup (`window.chrome`, `navigator.plugins`, `navigator.languages`, consistent screen dimensions) via a shared `core/stealth.py` utility, with no plugin ABC version bump.

### Plugin Ecosystem

- [ ] **REG-01**: Maintainers can list community plugins in a GitHub wiki registry table with required fields: name, platform, domain patterns, maintainer, anti-detection difficulty, methods implemented, last-verified date, proxy-required, captcha-required.
- [ ] **REG-02**: Plugin authors can declare `difficulty`, `requires_proxy`, and `requires_captcha` as class attributes on a plugin (non-breaking additions to the ABC with sensible defaults).
- [ ] **REG-03**: User can run `shoppybot plugins list` to see all locally loaded plugins with their declared domain patterns, difficulty, and proxy/captcha requirements (no network call).
- [ ] **REG-04**: Contributors are guided to supply the new registry fields via updated CONTRIBUTING.md and the PR template (difficulty, requires_proxy, requires_captcha).

### Price Monitoring

- [ ] **PRICE-01**: User can set a per-item absolute `target_price` in config (NULL/absent = price monitoring off for that item).
- [ ] **PRICE-02**: Bot records scraped prices in an append-only `price_history` SQLite table via an optional `get_price()` plugin ABC hook (default returns `None` = unsupported), called alongside the stock check each poll cycle.
- [ ] **PRICE-03**: User receives price-drop alerts through the existing fan-out notification dispatcher using a distinct `price_drop` notification_type with dedup separate from stock alerts.
- [ ] **PRICE-04**: Price alert payloads include the current price, the target price, and the percentage from target.
- [ ] **PRICE-05**: User can set a per-item `price_drop_pct` threshold as a secondary trigger (alert on an N%+ drop from the last-seen price) alongside the absolute target.
- [ ] **PRICE-06**: User can run `shoppybot items price-history <name>` to view the last N recorded prices for an item.

### Stability / Polish

- [x] **STAB-01**: All 4 deferred v2.0 cross-OS/UI manual checks are executed and documented pass/fail (keyring restart survival, masked-TTY passphrase prompt, web dashboard render on Ubuntu, `0.0.0.0` bind warning), with any failures fixed.
- [x] **STAB-02**: The 4 v2.0 audit tech-debt items are resolved with a targeted regression test for each (no broad refactors).
- [ ] **STAB-03**: New v3.0 features (proxy rotation, CAPTCHA solving, price monitoring) have unit coverage for config parsing, DB schema, and threshold/comparison logic plus integration coverage for the plugin ABC additions.

---

## Future Requirements (Deferred to v3.1+)

- Per-platform proxy override (single global pool serves all platforms in v3.0).
- Price history retention / auto-purge (`DELETE ... WHERE scraped_at < -90 days` + VACUUM).
- Price chart / sparkline on the web UI item detail page.
- Historical-low / average price display.

---

## Out of Scope (v3.0)

- Canvas / WebGL / AudioContext fingerprint spoofing — requires patched Chromium; arms-race maintenance unjustified at personal-use volume.
- Behavioral mouse simulation / human-like click timing — very high effort, unproven benefit at this poll frequency.
- TLS / JA3 fingerprint evasion — requires a custom TLS stack.
- Proxy pool auto-replenishment from a provider API — external paid dependency maintenance.
- HUMAN / PerimeterX / Akamai "CAPTCHA" solving — these are behavioral bot managers, not token CAPTCHAs; no solve service addresses them (proxy + stealth is the only lever).
- Cloudflare Turnstile solving — higher cost, lower success, not on the target platform set.
- Self-hosted CAPTCHA solver — operational overhead exceeds value.
- Plugin marketplace / ratings system — GitHub wiki table + repo stars suffice at this community size.
- Auto-generated plugin health testing against live retail — legal/TOS risk; impractical in CI.
- Price prediction / trend modeling — no training data; different problem domain.
- Camelcamelcamel / third-party price-history API integration — external Amazon-only dependency.
- Separate price-monitoring polling schedule — share the existing stock-check poll cycle.
- End-to-end retail checkout tests in CI — legal/TOS risk; impractical.

---

## Traceability

| Requirement | Phase |
|-------------|-------|
| ANTI-04 | Phase 13 |
| ANTI-05 | Phase 13 |
| ANTI-06 | Phase 14 |
| ANTI-07 | Phase 14 |
| ANTI-08 | Phase 13 |
| REG-01 | Phase 15 |
| REG-02 | Phase 15 |
| REG-03 | Phase 15 |
| REG-04 | Phase 15 |
| PRICE-01 | Phase 16 |
| PRICE-02 | Phase 16 |
| PRICE-03 | Phase 16 |
| PRICE-04 | Phase 16 |
| PRICE-05 | Phase 16 |
| PRICE-06 | Phase 16 |
| STAB-01 | Phase 12 |
| STAB-02 | Phase 12 |
| STAB-03 | Phase 17 |
