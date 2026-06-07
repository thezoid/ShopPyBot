# Feature Research — v3.0 Resilience + Ecosystem

**Domain:** Community-extensible retail stock-checkout bot (Python / nodriver)
**Researched:** 2026-06-06
**Milestone scope:** NEW v3.0 features only. Existing v2.0 features are not re-researched.
**Confidence:** HIGH (proxy/CAPTCHA), MEDIUM (fingerprint resilience, price monitoring), HIGH (plugin registry)

---

## Context: What Already Exists (Do Not Re-Research)

The following are shipped and stable. Requirements for v3.0 must build on top of them without breaking them.

| System | Key facts relevant to v3.0 |
|--------|---------------------------|
| Plugin ABC (`RetailerPlugin`) | `async check_availability`, `auto_buy`, `login`, `detect_captcha`, `setup`, `teardown`; `domain_patterns` class attr; `PLUGIN_API_VERSION = 2` |
| Config schema (`AppConfig`) | Pydantic/YAML; per-platform section under `platforms.<name>` with `min_delay`, `max_delay`, `headless`, `user_agents`; `notifications.*` section for fan-out; `credentials.backend` for store selection |
| Notification system | Fan-out dispatcher; per-channel failure isolation; per-item `last_notified` dedup in SQLite; SMS is opt-in with env-var gate |
| SQLite schema | `items` table with `name`, `link`, `auto_buy`, `quantity`, `purchased`, `last_notified`; WAL mode + busy timeout |
| CredentialStore | keyring / encrypted-file / env-var; all secrets route through it; no plaintext on disk |
| Anti-detection (current) | Per-platform jitter delays, UA rotation, `navigator.webdriver` hidden via CDP, headless toggle |
| Platforms covered | Amazon, BestBuy, Walmart, Target, GameStop, Square Enix, NewEgg |
| Anti-detection difficulty per platform | Amazon: Medium, BestBuy: Medium, Walmart: High (HUMAN/PerimeterX), Target: High (Akamai), GameStop: Medium, NewEgg: Low-Medium, Square Enix: Low |

---

## Feature Area 1: Anti-Detection Hardening

### 1a. Proxy Rotation

**How it works in real scraping tools:**
Proxy rotation injects a different outbound IP address per request or per session. Two session models exist:
- Per-request rotation: new IP on every HTTP request. Maximizes IP diversity but breaks session state (login cookies, cart state). Retail checkout flows CANNOT use per-request rotation.
- Sticky session: same IP held for a logical session (one product page visit through checkout, or one full poll cycle). Provider appends a session token to the proxy auth username (e.g., `user-session-abc123:pass@host:port`). Sticky sessions are required for authenticated flows.

Proxy types, relevant to retail:
- Datacenter: fast, cheap (~$0.01-$0.05/GB), easy to fingerprint as non-residential. Blocked by Walmart/HUMAN and Target/Akamai almost immediately.
- Residential: real ISP IPs, hard to block. Significantly higher cost (~$5-15/GB). Required for Walmart, Target, useful for BestBuy Akamai.
- ISP proxies: datacenter speed + residential IP reputation. Good middle ground for retail.

**Ban/block detection signals:**
- HTTP 403, 429, 503 response codes
- Redirect to CAPTCHA or challenge page (URL contains `/challenge`, `/robot`, `/sorry`)
- Response body contains known block phrases ("Access Denied", "blocked", "are you a robot")
- Zero or near-zero page content length on a normally-large page

**Failure handling pattern:**
1. Attempt request through proxy
2. On block signal: mark proxy as penalized, rotate to next in pool
3. After N failures on a proxy: retire it from rotation for a cooldown period
4. When pool is exhausted: fall back to no-proxy (direct connection) or raise alert

**Config shape (what existing tools use):**

```yaml
proxy:
  enabled: false          # opt-in; disabled by default
  mode: sticky            # sticky | per_request
  session_ttl: 300        # seconds before rotating sticky session (0 = never rotate within check)
  proxies:
    - url: "http://user:pass@host:port"
    - url: "socks5://user:pass@host:port"
  ban_status_codes: [403, 429, 503]
  max_failures_before_retire: 3
  cooldown_seconds: 600
```

Integration with existing config: add `proxy:` as a top-level config section (parallel to `platforms:`, `notifications:`). Per-platform override is a v3.1 concern, not MVP.

**Dependency on existing features:** None structural. The proxy URL is passed to the nodriver `Browser` constructor as a launch argument (`--proxy-server=<url>`). Credential (proxy username/password) can be stored in CredentialStore if needed, but plain proxy URLs in config.yml are acceptable since they are not account credentials.

### Table Stakes vs Differentiators vs Anti-Features — Proxy Rotation

| Feature | Category | Complexity | Notes |
|---------|----------|------------|-------|
| Sticky-session proxy per check cycle | Table stakes | LOW | Required for authenticated checkout flows; per-request breaks login state |
| Configurable proxy list in config.yml | Table stakes | LOW | Simple YAML list of `scheme://user:pass@host:port` URLs |
| Ban signal detection (status codes + body patterns) | Table stakes | LOW | Without it, proxy rotation silently uses blocked proxies |
| Automatic rotation on ban detection | Table stakes | LOW | Core value; rotating blind is pointless |
| Cooldown/retry before retiring a proxy | Differentiator | LOW-MED | Avoids burning the pool on transient errors |
| Residential vs datacenter documentation per platform | Differentiator | LOW | Guidance in PLATFORMS.md; no code complexity |
| Per-platform proxy override | Anti-feature | MED | Over-engineering; single pool serves all platforms for personal use |
| Proxy health monitoring dashboard | Anti-feature | HIGH | Out of scope; CLI log output is sufficient |
| Proxy pool auto-replenishment from provider API | Anti-feature | HIGH | Paid service dependency + maintenance; users supply their own list |
| SOCKS5 authentication in Chrome flags | Differentiator | LOW | Chrome supports `--proxy-server=socks5://` natively; worth documenting |

### 1b. CAPTCHA Solving

**How it works in real tools:**

CAPTCHA solving services (2captcha, CapSolver, AntiCaptcha) expose an async submit/poll flow:
1. Bot extracts CAPTCHA parameters from the page (sitekey, page URL, type)
2. Bot submits task to service API; receives a task ID immediately
3. Bot polls the result endpoint every 5-10 seconds (polling below 5s is rate-limited by 2captcha)
4. Service returns a token (reCAPTCHA: `g-recaptcha-response` form field value, or similar)
5. Bot injects the token into the page form and submits

For Selenium/nodriver this means the bot pauses the checkout flow, calls the external service, waits (typically 30-120 seconds for human workers; faster for AI solvers), then resumes.

**CAPTCHA types by platform (v3.0 targets):**

| Platform | CAPTCHA Type | 2captcha cost/1000 | Notes |
|----------|-------------|-------------------|-------|
| Amazon | Amazon WAF Captcha (image-based), reCAPTCHA v2 (intermittent) | $1.45 (WAF), $1.00 (reCAPTCHA v2) | Triggered on login and high-frequency polling; not every session |
| BestBuy | Akamai Bot Manager (no classic CAPTCHA challenge; uses behavioral fingerprinting) | N/A — behavioral, not solvable with token service | Akamai blocks at TLS/behavior level before a CAPTCHA is shown |
| Walmart | HUMAN Security / PerimeterX (no traditional CAPTCHA; behavioral + fingerprint) | N/A | Same as Akamai — CAPTCHA solving services do not address this |
| Target | Akamai (same as BestBuy) | N/A | |
| GameStop | reCAPTCHA v2 on checkout | $1.00/1000 | Triggered at checkout more reliably than stock check |
| NewEgg | reCAPTCHA v2 (intermittent) | $1.00/1000 | Lower frequency |
| Square Enix | Standard image CAPTCHA or minimal protection | $0.50-$1.00/1000 | Low frequency |

Key insight: Walmart and Target use behavioral bot managers (HUMAN/PerimeterX/Akamai), not traditional CAPTCHAs. CAPTCHA solving services do not help with these platforms. Proxy rotation + fingerprint hardening is the only lever for them.

**Cost model for personal use:** At $1.00/1000 for reCAPTCHA v2, a personal user who hits 10 CAPTCHAs per day would spend ~$3/month. The cost is acceptable but must be opt-in (same gate pattern as SMS/Twilio).

**Async flow in Python (2captcha-python library):**

The `AsyncTwoCaptcha` class wraps submit + poll in a single `await solver.recaptcha(sitekey=..., url=...)` call. Default polling interval is 10 seconds, `recaptchaTimeout` defaults to 600s. The library handles retries internally. The API key is a secret and must route through CredentialStore (key: `TWOCAPTCHA_API_KEY`).

### Table Stakes vs Differentiators vs Anti-Features — CAPTCHA Solving

| Feature | Category | Complexity | Notes |
|---------|----------|------------|-------|
| Opt-in only with explicit config flag (`captcha_solver.enabled: false`) | Table stakes | LOW | Same pattern as SMS; accidental charges must be impossible |
| API key stored in CredentialStore (not config.yml) | Table stakes | LOW | CRED-06 invariant; `TWOCAPTCHA_API_KEY` env/keyring key |
| reCAPTCHA v2 solving (GameStop, NewEgg, intermittent Amazon) | Table stakes | LOW-MED | Highest-value type for this platform set |
| Amazon WAF Captcha solving | Differentiator | LOW-MED | Type already supported by 2captcha; adds Amazon checkout success rate |
| Async submit/poll with configurable timeout | Table stakes | LOW | Use `AsyncTwoCaptcha`; integrate as `await` in plugin `detect_captcha` flow |
| Balance check at startup (warn if balance low, skip if zero) | Differentiator | LOW | `await solver.balance()` call at bot start; prevents silent failures |
| Per-solve cost logging (DEBUG level) | Differentiator | LOW | Transparency; helps user track spend |
| Cloudflare Turnstile solving | Anti-feature | MED | $1.45/1000; Turnstile is behavioral, solve success rate is lower; not on target platforms |
| HUMAN/PerimeterX CAPTCHA solving | Anti-feature | HIGH | These are not traditional CAPTCHAs; no solve service addresses them reliably |
| Self-hosted CAPTCHA solver (e.g., ohmycaptcha) | Anti-feature | HIGH | Operational complexity far exceeds value for personal use |
| Solve-result injection into DOM for Selenium | Table stakes | LOW | Standard pattern: `driver.execute_script("document.getElementById('g-recaptcha-response').innerHTML='...'")` |

**Dependency on existing features:**
- `detect_captcha()` method in plugin ABC: already exists as a hook; solver integrates here
- CredentialStore: API key flows through it
- Notification dedup: CAPTCHA solve events do not need dedup (they are transient, not per-restock)

### 1c. Fingerprint Resilience

**What matters for personal-use personal-volume bots:**

Browser fingerprinting works at several layers:
- Layer 1 (basic, already patched): `navigator.webdriver = true`, Selenium UA string. The existing CDP patch + UA rotation already address this.
- Layer 2 (medium difficulty): Chrome automation flags in `navigator.plugins`, `window.chrome` object absence, `navigator.languages` mismatch, screen resolution / color depth anomalies.
- Layer 3 (advanced): Canvas fingerprint, WebGL renderer/vendor, AudioContext, font enumeration, timing attacks. These require patched Chromium builds or significant JS injection.
- Layer 4 (behavioral): Mouse movement patterns, click timing, scroll velocity, keystroke cadence. Only addressable with human simulation or ML-based movement generation.

**undetected-chromedriver vs selenium-stealth vs nodriver:**
- `undetected-chromedriver`: patches Layer 1 + parts of Layer 2 (webdriver flag, some Chrome properties). Last PyPI release early 2024; successor is `nodriver`. The existing codebase already migrated to nodriver per the v2.0 plugin base (`setup()` creates a nodriver Browser). So undetected-chromedriver is not an option to add; nodriver is already in use.
- `selenium-stealth`: a Selenium plugin that injects JS patches for Layer 2 signals (window.chrome, navigator.plugins, navigator.languages, WebGL). Not compatible with nodriver (nodriver is not Selenium).
- `nodriver` (already in use): suppresses some basic bot signals by default. Does not patch Canvas/WebGL.
- `playwright-stealth` / `rebrowser-playwright`: not applicable (project uses nodriver/Chrome, not Playwright).

**What is worth doing for personal-use at low poll volume:**

| Signal | Worth Patching | Effort | Impact |
|--------|---------------|--------|--------|
| `navigator.webdriver` | Already done (CDP patch) | Done | High |
| UA rotation | Already done | Done | High |
| `window.chrome` object | YES | LOW | Medium for BestBuy/Akamai |
| `navigator.plugins` (non-empty) | YES | LOW | Medium |
| `navigator.languages` consistent with UA | YES | LOW | Low-Medium |
| Screen dimensions consistent with headless | YES | LOW | Low-Medium |
| Canvas fingerprint | NO | HIGH | Arms race; requires patched Chromium |
| WebGL renderer spoofing | NO | HIGH | Same; diminishing returns for personal use |
| Behavioral mouse simulation | NO | VERY HIGH | Over-engineering for personal-use volume |
| TLS fingerprint (JA3) | NO | VERY HIGH | Requires custom TLS stack; out of scope |

The practical answer for personal use: inject a JS stealth patch bundle at `Browser.setup()` time, covering `window.chrome`, `navigator.plugins`, `navigator.languages`, and permission query behavior. These are the signals that Akamai and BestBuy/GameStop check first. Canvas/WebGL/behavioral simulation is explicitly an anti-feature at this scale.

### Table Stakes vs Differentiators vs Anti-Features — Fingerprint Resilience

| Feature | Category | Complexity | Notes |
|---------|----------|------------|-------|
| JS stealth patch at browser startup (window.chrome, navigator.plugins, navigator.languages) | Table stakes | LOW | One `page.evaluate()` call in plugin `setup()`; covers Layer 2 signals |
| Consistent screen resolution in headless mode (non-zero `window.outerWidth`) | Table stakes | LOW | Browser launch arg; fixes a known headless tell |
| Permission query behavior normalization | Differentiator | LOW | Prevents fingerprint via `navigator.permissions.query({name:'notifications'})` |
| Canvas fingerprint spoofing | Anti-feature | HIGH | Requires patched Chromium; arms race; not worth it for personal use |
| WebGL renderer spoofing | Anti-feature | HIGH | Same reason |
| Behavioral mouse simulation / human-like click timing | Anti-feature | VERY HIGH | Over-engineering for personal-use poll frequency |
| TLS/JA3 fingerprint evasion | Anti-feature | VERY HIGH | Requires custom TLS stack; out of scope entirely |
| Plugin-level `stealth_level` config knob | Anti-feature | MED | Unnecessary abstraction; one sensible default serves all platforms |

**Dependency on existing features:** The nodriver `Browser` is already constructed in `plugin.setup()`. The stealth patch is added there without ABC changes. No plugin API version bump needed if implemented as a shared utility in `core/stealth.py` called from each plugin's `setup()`.

---

## Feature Area 2: Plugin Ecosystem Registry

**How registries work in comparable open-source tools:**

The GitHub wiki is the standard approach for community plugin directories at this scale (not PyPI, not a separate registry service). Examples: Obsidian plugin registry (GitHub repo), Drone CI plugin registry (GitHub wiki markdown table), Homebridge plugin registry (npm + GitHub but that is PyPI-scale). For a project at ShopPyBot's community size, a wiki markdown table is exactly right.

**What a useful per-plugin wiki entry contains (from studying comparable registries):**

| Field | Why It Matters | Required vs Optional |
|-------|---------------|---------------------|
| Plugin name | Unique identifier for discovery | Required |
| Platform / retailer covered | Primary lookup key | Required |
| Domain pattern(s) | What URLs match; avoids duplicate effort | Required |
| Maintainer (GitHub handle) | Who to contact for issues | Required |
| Anti-detection difficulty (Low/Medium/High/Extreme) | Manages user expectations; prevents frustrated issues | Required |
| Methods implemented | Which ABC methods are non-no-op (check_availability, auto_buy, login) | Required |
| Last verified working date | Bots break when sites change; staleness signal | Required |
| Known limitations | Checkout blocked, CAPTCHA type required, headless issues | Required |
| Proxy required | Whether the platform requires residential proxy for reliable operation | Required |
| CAPTCHA solver required | Whether it requires CAPTCHA service integration | Required |
| Link to plugin file or PR | For installation | Required |
| Notes | Anything else | Optional |

**Anti-detection difficulty rating definitions:**

| Rating | Meaning | Examples |
|--------|---------|---------|
| Low | Standard Selenium with UA rotation works reliably | Square Enix, NewEgg |
| Medium | Requires jitter delays + nodriver stealth patch; occasional CAPTCHA solve needed | Amazon, BestBuy, GameStop |
| High | Requires residential proxy + stealth patch; checkout unreliable without CAPTCHA solver | Walmart, Target |
| Extreme | Behavioral bot manager blocks all automated traffic; only API-based checking viable | Ticketmaster, Shopify stores with Kasada |

**Auto-generated vs manual:** The "last verified working" date and status must be manually maintained — no CI can verify a real retail checkout. The table structure is manual. The contributor onboarding doc can pre-fill required fields via a wiki page template (GitHub wiki supports page templates via the `_Footer` / sidebar convention). Full automation is an anti-feature at this scale.

**Plugin discovery/listing command:**

A `shoppybot plugins` CLI subcommand that lists all loaded plugins (already auto-discovered from `plugins/`) with their `domain_patterns` and the difficulty rating declared as a class attribute. This provides local discoverability without requiring a network call to the wiki.

### Table Stakes vs Differentiators vs Anti-Features — Plugin Registry

| Feature | Category | Complexity | Notes |
|---------|----------|------------|-------|
| GitHub wiki markdown table with required fields (name, platform, difficulty, maintainer, last-verified, methods) | Table stakes | LOW | A markdown table; maintainable by any contributor via wiki PR |
| Anti-detection difficulty rating (Low/Medium/High/Extreme) with defined criteria | Table stakes | LOW | Documented in PLUGIN_DEV.md; declared as `difficulty: str` class attr on plugin |
| `proxy_required` and `captcha_required` flags per plugin entry | Table stakes | LOW | Critical for user expectation-setting when these are new v3.0 features |
| `last_verified` date per plugin entry | Table stakes | LOW | Retail sites change frequently; staleness signal prevents wasted user time |
| `shoppybot plugins list` CLI command | Differentiator | LOW | Lists loaded plugins + their declared attributes (difficulty, domains) without wiki lookup |
| Plugin submission checklist update (add difficulty, proxy_required, captcha_required) | Table stakes | LOW | Update CONTRIBUTING.md + PR template to require these new fields |
| Auto-generated registry from CI | Anti-feature | MED | CI cannot verify real-world working status; manual beats automation here |
| Plugin version pinning / compatibility matrix | Anti-feature | HIGH | Over-engineering for this community size; PLUGIN_API_VERSION already gates incompatibility |
| Plugin marketplace / ratings system | Anti-feature | HIGH | GitHub stars on the main repo is sufficient signal; separate ratings UI is overkill |
| Automated plugin health testing against live retail | Anti-feature | VERY HIGH | Legal/TOS risk; operational cost; impractical to run in CI |

**Dependency on existing features:**
- Plugin ABC already has `domain_patterns` class attribute; add `difficulty` and `requires_proxy`, `requires_captcha` class attributes to the ABC (defaulting to sensible values). This is a non-breaking addition.
- CONTRIBUTING.md and PR template (DOCS-01/02) already exist; update them rather than create new docs.

---

## Feature Area 3: Price Monitoring

**How it works in real tools:**

Price monitoring is a separate concern from stock availability, but they share the same polling loop and page navigation. The standard pattern:

1. Plugin scrapes current price from the product page alongside the stock check (same page visit, no extra request)
2. Price is written to a `price_history` table with `(item_id, price, scraped_at)` — append-only, keyed by item + timestamp
3. On each check: compare current price against user's configured `target_price`; also compare against previous price snapshot for drop detection
4. Notification triggers:
   - Price-drop alert: current price dropped below `target_price` threshold
   - Price-below-absolute: current price is at or below an absolute value (e.g., "alert me if this drops below $299")
   - Both can coexist; they are different notification payloads

**Target-price threshold semantics (two models):**

| Model | Trigger | Config field | Example |
|-------|---------|-------------|---------|
| Absolute threshold | `current_price <= target_price` | `target_price: 299.99` | "Alert when below $300" |
| Percentage drop | `(current - previous) / previous <= -drop_pct` | `price_drop_pct: 10` | "Alert on 10%+ drop from last seen" |

Both models are useful. Absolute is simpler and covers the primary use case (waiting for a sale). Percentage drop is secondary. Both should be supported but the absolute threshold is the MVP.

**Price history retention:**
- Append-only SQLite table: no retention limit in MVP. A personal user monitoring 10 items at 30-second intervals generates ~2,880 rows/day/item, ~1M rows/year. SQLite handles this fine.
- If storage concerns arise, a simple `VACUUM` job after deleting rows older than 90 days is sufficient. This is a v3.1 concern.

**SQLite schema addition:**

```sql
-- New table alongside existing `items` table
CREATE TABLE price_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    price      REAL NOT NULL,
    scraped_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_price_history_item_scraped ON price_history (item_id, scraped_at DESC);
```

The `items` table gains one new column: `target_price REAL DEFAULT NULL`. NULL means price monitoring is off for that item.

**Integration with existing dedup:**

Price-drop alerts use the SAME fan-out dispatcher and dedup mechanism as stock alerts, with a distinct `notification_type = 'price_drop'` to prevent stock-alert dedup from suppressing price alerts and vice versa. The `last_notified` column in SQLite tracks per-item per-type timestamps.

**Plugin API surface change:**

The plugin ABC gains an optional `get_price(url: str) -> float | None` method (default returns `None` = price monitoring not supported for this plugin). This is a non-breaking addition (default implementation in base class). The orchestrator calls it alongside `check_availability` on each poll cycle.

**Config per-item addition:**

```yaml
available:
  items:
    - name: "PS5 Console"
      link: "https://www.amazon.com/dp/..."
      auto_buy: false
      quantity: 1
      target_price: 449.99    # new: alert when price drops to/below this
```

### Table Stakes vs Differentiators vs Anti-Features — Price Monitoring

| Feature | Category | Complexity | Notes |
|---------|----------|------------|-------|
| Per-item `target_price` in config (absolute threshold) | Table stakes | LOW | One new YAML field on `ItemConfig`; NULL = disabled |
| Price-drop alert via existing notification dispatcher | Table stakes | LOW | Reuse fan-out + dedup; new `notification_type` discriminator |
| `price_history` table (append-only SQLite) | Table stakes | LOW | Two new SQL statements; `item_id` FK to existing `items` table |
| `get_price()` hook on plugin ABC (returns `float | None`, default `None`) | Table stakes | LOW | Non-breaking optional method; only plugins that implement it get price tracking |
| Price in notification payload (show current price, target price, % from target) | Table stakes | LOW | Notification payload enrichment; no arch change |
| Separate dedup key for price alerts vs stock alerts | Table stakes | LOW | `notification_type` column on `last_notified` or separate tracking dict |
| Percentage drop threshold (`price_drop_pct`) per item | Differentiator | LOW | Secondary trigger; complements absolute threshold |
| `shoppybot items price-history <name>` CLI command (last N prices) | Differentiator | LOW-MED | Useful for user to see trend; reads `price_history` table |
| Price chart / sparkline in web UI | Differentiator | MED | Optional; only if web UI is updated; defer to later |
| Price history retention / auto-purge | Differentiator | LOW | `DELETE FROM price_history WHERE scraped_at < datetime('now', '-90 days')` on startup |
| Historical low / average display | Differentiator | LOW | Single aggregate query on `price_history`; useful in CLI or web UI |
| Price monitoring as a separate polling schedule (different from stock check interval) | Anti-feature | MED | Over-complicates the orchestrator; share the stock-check poll cycle |
| Price prediction / trend modeling | Anti-feature | HIGH | Requires training data; outside scope |
| Camelcamelcamel / third-party price history API integration | Anti-feature | MED | External dependency; Amazon-only; breaks personal-use simplicity |
| Price monitoring plugin type (separate ABC from retail plugin) | Anti-feature | MED | Unnecessary split; price is a capability of a retail plugin, not a separate plugin class |

**Dependency on existing features:**
- `ItemConfig` in `config_schema.py`: add `target_price: float | None = None`
- SQLite models: new `price_history` table + `target_price` column on `items`
- Notification dispatcher: add `notification_type` parameter to fan-out call; update dedup logic
- Plugin ABC: add `get_price()` default method
- Orchestrator: call `get_price()` alongside `check_availability()`; write result to `price_history`; check threshold; dispatch alert if triggered

---

## Feature Area 4: Stability / Polish

### 4a. Deferred v2.0 Cross-OS Manual Checks

These are not feature development — they are verification tasks. They close documented gaps in `docs/PLATFORMS.md` and `.planning/STATE.md`.

| Check | What It Verifies | Complexity |
|-------|-----------------|------------|
| OS keyring restart survival (Windows Credential Manager) | `CredentialStore` keyring backend survives process restart | LOW — run + restart |
| Masked-TTY passphrase prompt on Ubuntu | `getpass.getpass()` works in SSH terminal for encrypted-file store | LOW — SSH test |
| Web UI dashboard render on real Ubuntu | FastAPI + Jinja2 renders correctly on Ubuntu Python | LOW — `shoppybot web` + browser |
| Web UI `0.0.0.0` bind warning on Ubuntu | Security warning displays when non-localhost bind is used | LOW — config tweak |

### 4b. Test Hardening

Deferred v2.0 audit tech-debt items require targeted fixes, not broad refactors. Scope is: fix the 4 audit items documented in the v2.0 STATE.md, add regression tests for each.

### Table Stakes vs Differentiators vs Anti-Features — Stability

| Feature | Category | Complexity | Notes |
|---------|----------|------------|-------|
| Close all 4 deferred manual checks (document pass/fail, fix any failures) | Table stakes | LOW | Not feature development; verification + documentation |
| Fix 4 v2.0 audit tech-debt items + regression tests | Table stakes | LOW-MED | Scope to the specific items; no broad refactors |
| Test coverage for new v3.0 features (proxy rotation, CAPTCHA solving, price monitoring) | Table stakes | MED | Unit tests for config parsing, DB schema, price comparison logic; integration tests for plugin ABC additions |
| Test parallelism / CI speed improvements | Differentiator | LOW-MED | Only if CI is measurably slow; YAGNI until proven needed |
| End-to-end retail checkout tests in CI | Anti-feature | VERY HIGH | Legal/TOS risk; cannot run against live retail in CI |

---

## Feature Dependencies

```
Proxy Rotation
  requires: config_schema.py ProxyConfig section
  requires: plugin setup() passes proxy arg to Browser launch
  enhances: CAPTCHA Solving (proxy + CAPTCHA together raise success rate on Walmart/Target)
  note: Walmart/Target improvement requires BOTH proxy + stealth, not just one

CAPTCHA Solving
  requires: CredentialStore (TWOCAPTCHA_API_KEY)
  requires: detect_captcha() plugin hook (already exists)
  requires: opt-in config flag (captcha_solver.enabled: false)
  integrates: existing notification dispatcher (optional: "CAPTCHA solved" log entry)

Fingerprint Resilience (JS stealth patch)
  requires: nodriver Browser already constructed in plugin setup() (already exists)
  provides: core/stealth.py shared utility
  no ABC version bump needed

Plugin Registry
  requires: plugin ABC additions (difficulty, requires_proxy, requires_captcha class attrs)
  requires: CONTRIBUTING.md + PR template update
  provides: shoppybot plugins list CLI subcommand

Price Monitoring
  requires: ItemConfig.target_price field (config_schema.py)
  requires: price_history SQLite table (models.py)
  requires: get_price() on plugin ABC (non-breaking default)
  requires: notification_type discriminator in fan-out dispatcher
  enhances: web UI (optional; price chart on item detail page)

Stability / Polish
  no new feature dependencies
  must not break: CredentialStore, plugin ABC, BotService API
```

---

## Prioritization Matrix

| Feature | User Value | Implementation Cost | Dependency Risk | Priority |
|---------|------------|---------------------|-----------------|----------|
| JS stealth patch (fingerprint Layer 2) | HIGH — immediate improvement on BestBuy/GameStop | LOW | LOW (no ABC change) | P1 |
| Proxy rotation (config + rotation logic) | HIGH — unlocks Walmart/Target success | MEDIUM | LOW-MED (config schema addition) | P1 |
| CAPTCHA solving (reCAPTCHA v2, Amazon WAF) | HIGH — removes manual intervention on GameStop/Amazon | MEDIUM | MED (CredentialStore + async flow) | P1 |
| Plugin registry (wiki table + difficulty ratings) | HIGH — community ecosystem value | LOW | LOW (docs only + minor ABC attr) | P1 |
| `shoppybot plugins list` CLI | MEDIUM — nice discoverability | LOW | LOW | P2 |
| Price monitoring (target_price threshold + history) | HIGH — new use case, highly requested | MEDIUM | MED (schema change + dispatcher update) | P1 |
| Price history CLI command | LOW-MED | LOW | LOW | P2 |
| Stability / deferred v2.0 checks | HIGH — closes known gaps | LOW | LOW | P1 (do first, unblocks testing) |
| Balance check at startup (CAPTCHA solver) | MEDIUM | LOW | LOW | P2 |
| Percentage drop threshold | LOW-MED | LOW | LOW | P2 |

---

## Anti-Feature Summary (Scope Control)

The following are explicitly out of scope for v3.0 and should be rejected if raised during requirements:

| Anti-Feature | Why Excluded |
|-------------|--------------|
| Canvas / WebGL / AudioContext fingerprint spoofing | Requires patched Chromium; arms-race maintenance; personal-use volume does not justify it |
| Behavioral mouse simulation | VERY HIGH effort; unproven benefit at personal-use poll frequency |
| TLS/JA3 fingerprint evasion | Custom TLS stack required; entirely out of scope |
| Per-platform proxy pool override | Over-engineering; single global pool serves all platforms |
| Proxy pool auto-replenishment from provider API | External paid dependency maintenance |
| HUMAN/PerimeterX/Akamai CAPTCHA solving | These are behavioral managers, not token-based CAPTCHAs; no solve service addresses them |
| Cloudflare Turnstile solving | Higher cost, lower success rate; Turnstile not on current target platform set |
| Self-hosted CAPTCHA solver | Operational overhead exceeds value |
| Plugin marketplace / ratings system | GitHub wiki table is sufficient for this community size |
| Auto-generated plugin health testing against live retail | Legal/TOS risk; impractical in CI |
| Price prediction / trend modeling | No training data; different problem domain |
| Camelcamelcamel / third-party price API integration | External dependency; Amazon-only; breaks tool simplicity |
| Separate price-monitoring polling schedule | Over-complicates orchestrator; share the stock poll cycle |
| End-to-end retail checkout tests in CI | Legal/TOS risk; impractical |

---

## Sources

- [2captcha Python package README](https://github.com/2captcha/2captcha-python) — async solve flow, supported CAPTCHA types, timeout/polling config
- [2captcha Pricing](https://2captcha.com/pricing) — per-type cost per 1000 solves
- [ScrapingBee Rotating Proxies Guide](https://www.scrapingbee.com/blog/rotating-proxies/) — per-request vs sticky session guidance, residential vs datacenter for e-commerce
- [Scrapfly Price Tracker Guide](https://scrapfly.io/blog/posts/how-to-build-a-price-tracker-in-python) — SQLite schema (products + prices), percentage threshold logic, append-only pattern
- [Rebrowser Undetected Chromedriver Guide](https://rebrowser.net/blog/undetected-chromedriver-the-ultimate-guide-to-bypassing-bot-detection) — fingerprint signals patched, maintenance status, nodriver as successor
- [DEV.to Proxy Rotation 2026 Guide](https://dev.to/agenthustler/proxy-rotation-for-web-scraping-in-2026-the-complete-guide-with-code-23d) — ban detection patterns, cooldown strategy
- [DEV.to CAPTCHA Bypass Techniques](https://dev.to/markus009/python-web-scraping-practical-ways-to-bypass-anti-bot-protection-proxy-rotation-captcha-services-4lm) — CAPTCHA service integration patterns
- [Dolphin Anty CAPTCHA Service Comparison](https://dolphin-anty.com/blog/en/comparison-of-captcha-solving-services/) — service comparison, cost structure
- Existing codebase: `core/plugin_base.py`, `core/config_schema.py` — current plugin ABC and config schema shapes that v3.0 must extend without breaking

---

*Feature research for: ShopPyBot v3.0 Resilience + Ecosystem*
*Researched: 2026-06-06*
