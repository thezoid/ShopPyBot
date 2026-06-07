# Domain Pitfalls: ShopPyBot v3.0 Resilience + Ecosystem

**Domain:** Async nodriver/asyncio checkout bot adding proxy rotation, CAPTCHA solving,
fingerprint resilience, price monitoring, and a plugin ecosystem registry to an existing
modular core with CredentialStore.
**Researched:** 2026-06-06
**Supersedes:** v1 PITFALLS.md (v1/v2 pitfalls are resolved; this document covers v3.0
feature additions only)
**Overall Confidence:** HIGH for proxy/nodriver quirks, fingerprint, and security pitfalls
(verified against official GitHub issues and community post-mortems). MEDIUM for legal risk
(based on published legal analyses; jurisdiction-dependent).

---

## 1. Proxy Rotation Pitfalls

### 1.1 Authenticated Proxy Support Is Broken in Nodriver (Critical)

**What goes wrong:** Nodriver cannot pass `username:password` credentials via the standard
`--proxy-server=host:port` Chrome argument. Chrome ignores credentials in that arg. The
only working paths are (a) a Chrome extension that intercepts auth via
`Fetch.continueWithAuth` over CDP, or (b) IP-allowlisted proxies that require no
credentials at all. Developers copy a proxy URL from their provider dashboard, add it to
config, the bot silently connects direct, and the real IP appears in the retailer's logs
on every request.

**Warning Sign:** Proxy provider dashboard shows zero inbound traffic while the bot is
running; or the target site's fingerprint response logs the ISP IP, not the proxy exit IP.

**Prevention:** Build and gate-test authenticated proxy support via CDP
`Fetch.continueWithAuth` before accepting proxy config from users. Alternatively, document
that only IP-allowlisted proxies are supported in v3.0 and defer auth proxy support to a
later phase with an explicit GitHub issue. Never silently fall back to direct connection:
if proxy config is present but connection fails auth, raise a clear startup error.

**Phase:** Anti-Detection Hardening (proxy rotation)

**Sources:** GitHub Discussion #1798 and Issue #1903, ultrafunkamsterdam/undetected-chromedriver;
TufayelLUS/Python-nodriver-use-all-type-proxy (extension workaround reference)

---

### 1.2 WebRTC Leaks Real IP Through a Proxied Browser Session (Critical)

**What goes wrong:** Chrome's WebRTC stack uses STUN to discover local and public IP
addresses, bypassing the proxy tunnel entirely. Retailer fingerprinting layers cross-check
the HTTP-visible proxy IP against the WebRTC-visible IP. If they differ, the session is
flagged. Disabling WebRTC via Chrome preferences is not the nodriver default and must be
set explicitly at browser launch.

**Warning Sign:** An IP-check test page loaded through the proxied browser returns the
real ISP IP; or bot sessions are flagged immediately despite all HTTP traffic routing
through the proxy.

**Prevention:** At browser launch in `plugin.setup()`, inject Chrome preferences:
`webrtc.ip_handling_policy = disable_non_proxied_udp`,
`webrtc.multiple_routes_enabled = false`, `webrtc.nonproxied_udp_enabled = false`.
Write an integration test that confirms the STUN-visible IP is absent or matches the
proxy exit node when the browser is launched with proxy config active.

**Phase:** Anti-Detection Hardening (proxy rotation)

**Sources:** undetected-chromedriver Issues #228 and #309 (WebRTC leak reports with
mitigation code)

---

### 1.3 DNS Leaks Even When WebRTC Is Disabled (Moderate)

**What goes wrong:** If the system DNS resolver is queried directly instead of routing
through the proxy tunnel, DNS requests for retailer domains reveal which sites the bot is
hitting to the ISP. HTTP proxies cannot tunnel DNS; only SOCKS5 can. Nodriver spawns
Chrome with the OS DNS resolver by default.

**Warning Sign:** A DNS-leak test page shows the real ISP nameserver, not the proxy's
nameserver.

**Prevention:** Use SOCKS5 proxies for production proxy rotation, not HTTP proxies. When
using SOCKS5, verify Chrome's `--host-resolver-rules` or remote-DNS option is set. Document
this requirement in the proxy rotation config comment block so users understand that HTTP
proxies are insufficient for anonymity.

**Phase:** Anti-Detection Hardening (proxy rotation)

---

### 1.4 Dead Proxy Detected Only After Mid-Checkout Failure (Moderate)

**What goes wrong:** The proxy pool selects a proxy that has gone offline. The browser
hangs mid-checkout, after the cart add but before the order placement. Without pre-flight
health checking, a dead proxy can abort an auto-buy sequence in a state where the item is
in the cart but no purchase confirmation is received. The write-queue pair
`set_available` / `purchased` in orchestrator.py requires `auto_buy()` to return `True`
before writing `purchased=1`; a hard connection error before that return leaves the item
marked available but not purchased, and the next poll cycle attempts the buy again.

**Warning Sign:** Intermittent `TimeoutError` or `ConnectionResetError` mid-checkout with
no "Marked purchased" log entry; duplicate auto-buy attempts for the same item.

**Prevention:** Add an async health-check coroutine that does a lightweight HTTP HEAD to a
reliable non-retailer URL through each proxy before injecting it into a browser session.
Skip dead proxies without attempting checkout. Confirm that the write-queue behavior
correctly handles aborted checkouts: `purchased=1` must only be written when `auto_buy()`
returns `True`, not on exception paths.

**Phase:** Anti-Detection Hardening (proxy rotation); touches orchestrator.py write-queue
integration

---

### 1.5 Datacenter Proxy Subnet Bans Poison the Entire Pool (Moderate)

**What goes wrong:** Amazon, Walmart, and BestBuy maintain ASN and subnet blocklists.
A /24 block (256 IPs) can be banned together when one proxy from that block is reported as
abusive. Buying 100 datacenter proxies from one provider often means they share overlapping
/24 subnets; one abuse report bans 50-200 proxies simultaneously. Users with cheap
datacenter proxy pools find 100% of proxies blocked on first use against Amazon or Walmart.

**Warning Sign:** All proxies in the pool return immediate CAPTCHA challenges or 503
responses from the first request; no proxy shows a clean session on the target retailer.

**Prevention:** In the plugin registry difficulty ratings, document that datacenter proxies
are classified as HIGH detection risk for Amazon, Walmart, and BestBuy. Recommend
residential or mobile proxies for these platforms. The proxy rotation config schema should
accept a `proxy_type` field (datacenter / residential / mobile) and log a WARNING at
startup when datacenter proxies are configured for a platform with a known high-detection
rating.

**Phase:** Plugin Ecosystem (difficulty ratings) and Anti-Detection Hardening (config schema)

---

### 1.6 Proxy State Scoped at Module Level Instead of Per Plugin Instance (Moderate)

**What goes wrong:** A module-level "current proxy" singleton shared across all plugin
instances would assign the same proxy IP to all platform workers simultaneously. Amazon
and BestBuy would be accessed from the same IP, creating cross-retailer tracking correlation
and defeating per-platform isolation. Additionally, one plugin rotating away from a proxy
mid-session while another is using it would break the active session.

**Warning Sign:** Log shows the same proxy IP used by all plugins in a single poll cycle;
retailer detection rate does not decrease after enabling proxy rotation.

**Prevention:** Proxy selection must be per plugin instance, stored as `self._proxy` on
the plugin, assigned in `setup()` and reused for the lifetime of that browser session. The
proxy rotator must provide a per-call `get_next_proxy(platform_key)` function that draws
from a pool — never a module-level current-proxy variable. Rotate proxy only at browser
restart (teardown + setup), not mid-session.

**Phase:** Anti-Detection Hardening (proxy rotation)

---

## 2. CAPTCHA-Solving Integration Pitfalls

### 2.1 No Spend Cap Causes Unbounded API Charges (Critical)

**What goes wrong:** CAPTCHA-service pricing is per-solve (typically $0.001 to $3.00
depending on CAPTCHA type; image CAPTCHAs are cheap, Cloudflare Turnstile is expensive).
During a high-demand drop event, retailers may serve CAPTCHAs on every page load. Without
a per-run or per-day cap, a weekend bot session can generate thousands of solve requests
and a significant unexpected bill before the user notices. There is no built-in spend limit
in the 2captcha or anticaptcha Python SDKs.

**Warning Sign:** CAPTCHA service account balance drops by more than a few dollars per day
without a corresponding increase in confirmed purchases; bot log shows repeated CAPTCHA
detection cycles for the same item.

**Prevention:** Add `captcha.max_solves_per_run` (integer) and `captcha.max_cost_usd_per_day`
(float, optional) to the Pydantic config schema. Track solve count in memory per run. On
exceeding the limit, log a CRITICAL message and disable CAPTCHA solving for that session,
falling back to the existing manual pause pattern (asyncio.Event + stdin listener).
Document the default limit in `sample.config.yml` with a comment explaining the cost risk.

**Phase:** Anti-Detection Hardening (CAPTCHA integration)

---

### 2.2 CAPTCHA API Key Stored as Plaintext in config.yml (Critical — Security)

**What goes wrong:** Every CAPTCHA service tutorial and README example shows the API key
as a string in code or config. A contributor who follows these tutorials puts the key in
`config.yml` under something like `captcha.api_key`. The existing config schema uses
`extra="ignore"`, so a plain string under an undeclared key is silently dropped and the
user does not even realize the key is not being read. Or worse, the user adds a declared
key, the key is read, and then they accidentally commit config.yml because it now contains
"just config, not credentials."

**Warning Sign:** `grep -r "2captcha\|anticaptcha\|capsolver" config.yml` returns a value;
or git history shows config.yml changes that include an API key string.

**Prevention:** Add `CAPTCHA_API_KEY` to `SECRET_KEYS` in `core/credentials.py` before
writing any CAPTCHA integration code. Route all CAPTCHA client construction through
`get_store().get("CAPTCHA_API_KEY")`. The Pydantic config schema should have a
`captcha.enabled: bool` field but no `captcha.api_key` field. Add a startup assertion in
`BotService` that checks the CAPTCHA API key is not present in `config.yml` when
`captcha.enabled: true`. Update `SECURITY.md` and `CONTRIBUTING.md` to list
`CAPTCHA_API_KEY` alongside retailer passwords as a never-commit secret.

**Phase:** Anti-Detection Hardening (CAPTCHA integration); CredentialStore integration
(Phase 8 precedent already established)

---

### 2.3 Blocking SDK Solve Call Stalls the asyncio Event Loop (Moderate)

**What goes wrong:** The 2captcha-python and python-anticaptcha SDKs use blocking HTTP
polling internally. Calling the sync solve method directly inside an async coroutine blocks
the event loop for the entire solve duration (typically 15-120 seconds for complex
CAPTCHAs). In the existing `asyncio.TaskGroup` structure in `orchestrator.py`, this blocks
all plugin poll tasks for the duration. BestBuy, Walmart, and other platform workers stop
polling entirely while Amazon's CAPTCHA is being solved.

**Warning Sign:** All plugin poll tasks stop producing log output simultaneously when one
plugin enters CAPTCHA solving; log resumes for all plugins only after the solve completes
or times out.

**Prevention:** Wrap all blocking CAPTCHA SDK calls with
`await asyncio.get_running_loop().run_in_executor(None, solve_fn)`. Enforce a hard
`asyncio.timeout(120)` context manager (available in Python 3.11+, already the project's
minimum) around the executor call. Verify with a unit test that other plugin tasks
continue to fire while a mock executor-based CAPTCHA solve is pending.

**Phase:** Anti-Detection Hardening (CAPTCHA integration)

---

### 2.4 CAPTCHA Solved but Session Still Gets Blocked (Moderate)

**What goes wrong:** Modern retailer bot-detection systems (Akamai Bot Manager,
PerimeterX/HUMAN Security, DataDome) analyze 200+ behavioral signals per session. Passing
the CAPTCHA token clears one signal but does not clear a session fingerprinted as
headless, lacking normal mouse movement, or having mismatched TLS behavior. After a
successful CAPTCHA solve, the next page request is still challenged or returns incorrect
inventory silently (e.g., always shows out-of-stock for a bot session).

**Warning Sign:** The CAPTCHA service returns a token and marks the solve successful, but
the subsequent page load still shows a CAPTCHA page or permanently "unavailable" for
all items; purchase conversion rate remains near 0 despite successful solves.

**Prevention:** Treat CAPTCHA solving as one layer in a multi-layer anti-detection stack,
not a standalone fix. Document in `PLUGIN_DEV.md` and in the plugin registry difficulty
ratings that CAPTCHA solving alone will not bypass retailers using behavioral session
analysis. When a solve token is submitted but the next request still fails, log the
failure distinctly from a solve failure so the cause is diagnosable.

**Phase:** Anti-Detection Hardening (documentation); Plugin Ecosystem (difficulty ratings)

---

### 2.5 No Timeout on the CAPTCHA Poll Loop Causes Hung Plugin Tasks (Moderate)

**What goes wrong:** If the CAPTCHA service is degraded or no human solver picks up the
task, the poll loop waits indefinitely. In the asyncio.TaskGroup model, a hung task does
not block other tasks, but it consumes a thread in the executor pool and prevents the
plugin from resuming normal polling. Under the existing `run_in_executor` pattern, thread
pool exhaustion is a risk if multiple plugin instances each have a hung CAPTCHA solve
simultaneously.

**Warning Sign:** `run_plugin` task for one platform stops producing log output; thread
count in the process climbs over time; other platforms continue normally.

**Prevention:** Wrap the executor call in `asyncio.timeout(120)`. On timeout, log a WARNING
and resume normal polling without marking the CAPTCHA as solved. Expose the timeout as a
config field (`captcha.solve_timeout_seconds`, default 120). Document that increasing this
value has a proportional impact on executor thread consumption.

**Phase:** Anti-Detection Hardening (CAPTCHA integration)

---

## 3. Fingerprint Resilience Pitfalls

### 3.1 Aggressive Fingerprint Spoofing Hurts More Than It Helps (Critical)

**What goes wrong:** Adding canvas noise overrides, AudioContext spoofing, font
enumeration blocking, and custom TLS fingerprints introduces internal signal inconsistencies.
Nodriver already applies a baseline CDP patch to hide `navigator.webdriver` (SEC-04,
already shipped). Layering additional overrides creates mismatches: canvas claims one GPU
renderer, WebGL reports a different one, audio fingerprint is inconsistent with the
claimed hardware profile. Modern ML-based detection engines (Cloudflare, PerimeterX)
specifically look for this cross-signal inconsistency pattern. Additionally, fingerprints
that change on every run are a bot signature: a real user's hardware does not change
between requests.

**Warning Sign:** Detection rate increases after adding fingerprint overrides; the bot gets
fewer successful checks post-spoofing than it did with vanilla nodriver.

**Prevention:** Extend nodriver's own approach: apply overrides only for surfaces with
confirmed detection evidence and maintain deterministic (per-session-instance, not
per-request) values. Seed a random profile offset once in `plugin.setup()` and reuse it
for the life of that browser instance. Do not override AudioContext, font enumeration, or
TLS unless a controlled A/B test on a specific retailer shows measurable improvement.
Test any fingerprint change against a fingerprinting test site (e.g., bot.sannysoft.com,
CreepJS) in headful mode before deploying.

**Phase:** Anti-Detection Hardening (fingerprint resilience)

**Sources:** NoDriver Issue #2153 (static fingerprints on every run); zendriver Issue #108
(canvas + font fingerprints unchanged); castle.io evolution of anti-detect frameworks

---

### 3.2 Firefox / Safari UAs in the Rotation Pool Produce Detectable Inconsistency (Moderate)

**What goes wrong:** The existing UA rotation pool in `config_schema.py` (`DEFAULT_USER_AGENTS`)
includes a Firefox UA entry. The bot uses nodriver, which is Chrome-based. A Firefox UA
string combined with Chrome's WebGL renderer, V8 JavaScript engine, and Chrome-only APIs
(`chrome.runtime`, etc.) is trivially detectable as spoofed. Platforms using behavioral
detection ban sessions with UA-vs-API inconsistency immediately.

**Warning Sign:** Detection rate is higher when Firefox UAs appear in the rotation than
when only Chrome UAs are used; sessions with Firefox UA strings are consistently blocked
before any page content is checked.

**Prevention:** Restrict `DEFAULT_USER_AGENTS` to Chrome-only UA strings matching the
installed Chrome major version. Add a startup warning (not an error, to avoid breaking
existing user configs) if a non-Chrome UA is present in the configured `user_agents` list
for a nodriver-backed platform. Document the Chrome-only requirement in `PLUGIN_DEV.md`.

**Phase:** Anti-Detection Hardening (fingerprint resilience); also a config schema
validation update

---

### 3.3 Custom CDP Overrides May Undo Nodriver's Own Patches (Moderate)

**What goes wrong:** Nodriver applies its own runtime CDP overrides during session
initialization. Adding additional `page.evaluate()` or `Runtime.callFunctionOn` overrides
after `setup()` completes may partially conflict with nodriver's patches depending on
script injection order. The result is a partially-patched browser that passes neither
automated stealth checks nor natural-browser fingerprint analysis.

**Warning Sign:** CreepJS score worsens (detects more anomalies) after adding custom
fingerprint overrides compared to vanilla nodriver in a controlled test.

**Prevention:** Apply custom fingerprint overrides only via the nodriver `setup()` hook
before the first page navigation, not after. Treat nodriver's existing patches as the floor.
Add a standard integration test run (headful, against bot.sannysoft.com) for any new
fingerprint override before merging.

**Phase:** Anti-Detection Hardening (fingerprint resilience)

---

## 4. Price Monitoring Pitfalls

### 4.1 Price Selectors Break on the Next Retailer Frontend Deploy (Critical)

**What goes wrong:** A CSS or XPath selector targeting the price element stops working
after the retailer's next A/B test or frontend deployment (typically every 2-6 weeks for
major retailers). A broken selector either returns `None` (no price recorded) or matches
a different element (wrong price value written to history). Both cases produce misleading
data or false price-drop alerts without any error surfacing to the user.

**Warning Sign:** Price history shows `None` or `0.00` for all items after a specific
date; or history shows wildly incorrect values (e.g., $1.00 for a $400 GPU).

**Prevention:** Use a three-layer extraction cascade in order of stability:
(1) JSON-LD `Product/Offer` structured data (most stable; retailer-maintained for SEO),
(2) OpenGraph `og:price:amount` meta tag, (3) CSS selector as last resort.
Store the raw price text string alongside the parsed float in the DB schema (a
`price_raw_text TEXT` column) to enable debugging without re-scraping. If all three layers
return None, log a WARNING and skip the price write for that cycle rather than writing
`None` or `0.00`.

**Phase:** Price Monitoring (new phase)

**Sources:** HasData/ecommerce-price-scraper extraction cascade pattern;
42signals.com universal price tracker architecture

---

### 4.2 Currency and Locale Parsing Produces Silent Wrong Numbers (Critical)

**What goes wrong:** A community-contributed plugin for a European retailer returns
`"1.234,56"` as the price string (German locale: dot as thousands separator, comma as
decimal). Naive `float("1.234,56")` raises `ValueError`, or the code strips non-numeric
characters and returns `123456.0` instead of `1234.56`, or `1.234` (truncated). If a
target price is set to `1200.00`, a false price-drop alert fires immediately on every poll.

**Warning Sign:** Price-drop alerts fire for items whose price has not changed; price
history shows values 10x or 100x too large or too small; items from non-US-locale plugins
consistently show incorrect prices.

**Prevention:** Normalize all price strings through a single shared utility function before
parsing. Handle both `1,234.56` (en-US) and `1.234,56` (de-DE) formats. The `babel`
library provides locale-aware number parsing and is the recommended approach (HIGH
confidence: official Babel docs). Log the raw price string and parsed float together on
each extraction so mismatches are visible in the log at DEBUG level. Reject ambiguous
strings that cannot be parsed with a deterministic locale with a WARNING log, not a
silent zero.

**Phase:** Price Monitoring (new phase)

---

### 4.3 False Price-Drop Alerts From Temporary Retailer Price Fluctuations (Moderate)

**What goes wrong:** Retailers serve dynamic prices that fluctuate by cents between poll
cycles (A/B test pricing, membership price variants, rounding differences across regions).
An edge-trigger alert that fires whenever price crosses the target threshold fires multiple
times per hour for the same item. Users receiving repeated notifications for the same
non-actionable price fluctuation disable all notifications to stop the spam.

**Warning Sign:** Discord or email channel receives multiple price-drop alerts per hour for
the same item; price history shows rapid oscillation of $0.01-$1.00 around the target
value.

**Prevention:** Apply hysteresis: a price-drop alert fires only when price drops below
`target_price * (1.0 - hysteresis_ratio)` (default 0.01, i.e., 1%). The alert does not
re-arm until price rises back above `target_price * (1.0 + hysteresis_ratio)`. This
mirrors the existing stock dedup pattern (`set_available`/`clear_available` edge-pair in
orchestrator.py).

**Integration pitfall:** The current `last_seen_available` and `last_notified` columns in
the items table track stock state for the existing edge-trigger dedup. Price alert state
must use separate columns (`price_alert_armed INTEGER DEFAULT 0`,
`price_last_notified TEXT`). Do not reuse `last_notified` for both stock and price alerts:
a price notification would suppress the next stock-available notification for the same
item.

**Phase:** Price Monitoring (new phase); coordinate with orchestrator.py write-queue
(price writes must go through the same queue per ASYNC-05)

---

### 4.4 Price History Schema Added Without DB Migration Guard (Moderate)

**What goes wrong:** `models.py`'s `initialize_db()` uses idempotent `ALTER TABLE ... ADD COLUMN`
with existence checks (as seen in the existing `last_seen_available` and `last_notified`
additions). New price-monitoring columns added without following this pattern cause
`OperationalError: duplicate column name` on startup for all existing deployments. Users
then follow troubleshooting docs that say to re-initialize the DB, which calls
`initialize_db(delete=True)` and wipes all purchase history and availability state.

**Warning Sign:** Bot crashes on startup with `OperationalError` after updating to the
price-monitoring version; or user reports losing their purchase history after following
troubleshooting steps.

**Prevention:** Follow the existing idempotent column-addition pattern in `initialize_db`
for every new price-monitoring column: read `PRAGMA table_info(items)` first, add each
column only if absent. Add a CI test that runs `initialize_db()` against a pre-existing
DB fixture (created by the v2.0 schema) and confirms it does not raise and does not lose
existing rows.

**Phase:** Price Monitoring (new phase); also Stability (CI migration test)

---

## 5. Plugin Ecosystem Pitfalls

### 5.1 GitHub Wiki Diverges from the Codebase Plugin API (Moderate)

**What goes wrong:** The GitHub wiki for the plugin registry is a separate git repository
not covered by CI. When `PLUGIN_API_VERSION` bumps (already at v2, bumped during v2.0
migration), wiki entries that describe the v1 method signatures remain stale. Contributors
read the wiki, implement a v1-style plugin, and it fails to load with a confusing error.
The wiki cannot be linted, tested, or linked to a specific commit.

**Warning Sign:** Community issues reporting that the wiki example code does not work with
the current version; plugins submitted that implement the old `__init__(self, driver, config)`
signature from the v1 interface.

**Prevention:** Use the wiki only as a plugin directory listing (name, URL, platform,
difficulty rating). All API contract documentation must live in the repository under
`plugins/PLUGIN_DEV.md` (already exists, already versioned with the code). Wiki entries
link to the canonical repo doc; they do not duplicate it. Add a CI assertion that
`PLUGIN_API_VERSION` in `plugin_base.py` matches the version documented in
`plugins/PLUGIN_DEV.md`.

**Phase:** Plugin Ecosystem (new phase)

---

### 5.2 Community Plugins Run In-Process with Full CredentialStore Access (Critical — Security)

**What goes wrong:** The plugin framework loads any `shopbot_plugin_*.py` file from
`plugins/` via `importlib` at startup. A community plugin has direct access to the entire
process memory, including the initialized `CredentialStore` singleton via `get_store()`.
A malicious plugin could call `get_store().get("AMZ_PASSWORD")`, read `creds.bin` directly,
intercept OTP inputs via the stdin listener, or make unauthorized purchases using the
already-logged-in browser session.

The supply-chain risk is real and growing: third-party involvement in security breaches
grew from 9% to 48% between 2022 and 2025 (Unit42). A 2.2M-install VS Code extension was
briefly backdoored in 2026 to harvest credentials. Community plugins in a `.py` file
drop-in model present an identical attack surface.

**Warning Sign:** A plugin PR with code that calls `get_store()`, accesses `data/creds.bin`,
makes outbound HTTP requests to non-retailer domains, or reads environment variables beyond
the platform's own credentials.

**Prevention:**
- Add explicitly to the PR review checklist (DOCS-05, already in the repo): "Reviewer
  must confirm: no calls to `get_store()` directly; no reads from `data/` directory; no
  outbound connections to non-retailer domains; no access to `os.environ` beyond what the
  plugin's declared platform requires."
- Add to `SECURITY.md`: "Community plugins run in-process with access to all credentials.
  Review plugin source code before installing. The maintainers do not audit submitted
  plugins for malicious behavior automatically."
- Never auto-merge plugin PRs; require human code review for all files in `plugins/`.
- Future hardening option (not in scope for v3.0, but document it): a platform-scoped
  CredentialStore view that exposes only the keys prefixed with the plugin's declared
  platform name.

**Phase:** Plugin Ecosystem (new phase); security documentation update

**Sources:** Unit42/Paloalto GitHub Actions supply chain attack analysis; CISA alert
2026-05-28 on Nx Console VS Code extension compromise

---

### 5.3 Difficulty Ratings That Encourage ToS Bypass Escalation (Legal / Ethical)

**What goes wrong:** A plugin registry that rates platforms by "anti-detection difficulty"
implicitly frames higher difficulty as a technical challenge to overcome. Contributors who
want a "hard" project build plugins for the most aggressively protected platforms (Walmart
PerimeterX, Target Akamai). The difficulty ratings become a leaderboard for bypass
techniques, and the project accrues legal and reputational risk from encouraging increasingly
aggressive circumvention.

**Warning Sign:** Plugin PR submissions for Walmart or Target that include CAPTCHA-bypass
automation, session spoofing, or multi-account rotation without any ToS compliance
disclaimer.

**Prevention:** Rename the rating dimension to "detection risk + ToS violation severity"
rather than just "anti-detection difficulty." The rating must include an explicit ToS
violation severity tag (Low / Medium / High) alongside the technical difficulty. High-risk
plugin registry entries must display a mandatory disclaimer: "Using this plugin violates
[Platform]'s Terms of Service and may result in account suspension." Add this requirement
to the plugin submission checklist in `CONTRIBUTING.md`.

**Phase:** Plugin Ecosystem (new phase)

---

## 6. Legal, Ethical, and Security Risks

### 6.1 Auto-Buy + Proxy Rotation Violates Retailer ToS and CFAA Risk (Legal Risk)

**Risk level:** MEDIUM (civil ToS consequences near-certain; criminal CFAA risk low for
personal use but exists when technical access controls are bypassed)

**What goes wrong:** Amazon, BestBuy, Walmart, Target, and GameStop all prohibit automated
purchasing bots and proxy rotation in their Terms of Service. Using rotating proxies to
bypass IP-rate limits or geo-blocking constitutes circumventing a technical access control,
which strengthens CFAA claims beyond a simple ToS violation. Courts have generally
distinguished between ToS-only violations (civil) and technical access control bypass
(potentially CFAA). Using CAPTCHA bypass services alongside proxy rotation places the
usage in the latter category.

Practical consequences: account permanent ban (including affiliated accounts and payment
methods), order cancellation, and for commercial/resale use: cease-and-desist.

**Prevention in code:**
- Keep the existing `SECURITY.md` ToS disclaimer and expand it to name proxy rotation and
  CAPTCHA bypass explicitly as features that violate retailer ToS.
- The plugin registry difficulty rating must state "violates [Platform] ToS" as a mandatory
  field, not optional metadata.
- Add a one-time startup acknowledgment (stored as a flag in CredentialStore or as a
  plaintext marker file, not config.yml) for any session that enables proxy rotation or
  CAPTCHA solving: "You have enabled features that violate your retailer's Terms of Service.
  Proceed at your own risk."
- Do not market or document the tool as a means of resale arbitrage.

**Phase:** Plugin Ecosystem (registry docs) and Anti-Detection Hardening (startup
acknowledgment)

---

### 6.2 CAPTCHA Bypass Raises DMCA Section 1201 Exposure (Legal Risk)

**Risk level:** LOW-to-MEDIUM (courts are increasingly applying DMCA §1201 to bot
circumvention; personal-use mitigation exists but is untested for CAPTCHA specifically)

**What goes wrong:** CAPTCHA bypass services violate the Terms of Service of every major
CAPTCHA provider (Google reCAPTCHA, hCaptcha, Cloudflare Turnstile). Using them to
circumvent retailer-deployed CAPTCHAs may constitute circumvention of a technological
protection measure under DMCA Section 1201. Recent litigation (Reddit v. unnamed parties,
2025-2026) invokes DMCA §1201 alongside CFAA in web-scraping contexts, suggesting
increased prosecutorial interest in this theory.

**Prevention in code:**
- CAPTCHA solving must be disabled in the default configuration (`captcha.enabled: false`).
- The `sample.config.yml` comment block for the captcha section must state: "Enabling
  CAPTCHA solving likely violates the ToS of the CAPTCHA provider and may violate DMCA
  Section 1201. Users enable this feature at their own legal risk."
- `SECURITY.md` must include CAPTCHA bypass in the known legal risks section.

**Phase:** Anti-Detection Hardening (CAPTCHA integration); Plugin Ecosystem docs

---

### 6.3 Residential Proxy Provider May Source IPs Without Consent (Legal Risk — MEDIUM confidence)

**Risk level:** LOW for users of legitimate providers; MEDIUM if provider sourcing is
opaque

**What goes wrong:** Some residential proxy providers source their IP pool through app SDK
bundles that grant proxy rights via buried, ignored ToS. The FBI has flagged such networks
as potentially enabling unauthorized access to devices. Using such a provider makes the bot
operator a downstream participant. This risk is difficult to verify without reading the
provider's consent model documentation.

**Prevention:** In the proxy rotation documentation and plugin registry anti-detection
section, list evaluation criteria for proxy provider legitimacy: (1) transparent,
informed-consent model for IP contributors, (2) published audit or compliance report,
(3) clear opt-in mechanism for contributors rather than opt-out or implicit consent via
app install. Do not name or recommend specific providers without reviewing their current
consent documentation. Flag providers whose consent model cannot be verified as HIGH risk.

**Phase:** Plugin Ecosystem (proxy documentation)

---

### 6.4 Proxy Credentials and CAPTCHA API Key Are High-Value Monetizable Secrets (Security)

**Risk:** A CAPTCHA API key with a loaded balance or proxy credentials with unlimited
bandwidth are targets for theft. A log line that includes `str(exc)` where the exception
message contains a URL with embedded credentials, or a config file that includes the
API key, exposes it. The existing `dispatcher.py` pattern logs only `exc.__class__.__name__`
to avoid this. The new proxy and CAPTCHA modules must follow the same discipline.

**Prevention:**
- Add `CAPTCHA_API_KEY`, `PROXY_USERNAME`, and `PROXY_PASSWORD` to `SECRET_KEYS` in
  `core/credentials.py` before any proxy or CAPTCHA code is written. This is the same
  extension point used for all v2.0 secrets.
- Audit all logging paths in proxy and CAPTCHA modules: never pass `str(exc)` or
  `repr(exc)` to `writeLog()` when those exceptions may contain credential strings (e.g.,
  a `ConnectionError` from an auth proxy includes the proxy URL with embedded credentials).
  Log only `exc.__class__.__name__`.
- The existing `CRED-06` test (asserts no secret plaintext in config.yml, logs, SQLite)
  must be extended to cover `CAPTCHA_API_KEY`, `PROXY_USERNAME`, `PROXY_PASSWORD` before
  these features ship.

**Phase:** Anti-Detection Hardening (both CAPTCHA and proxy); must be addressed in Phase
requirements before any implementation begins

---

### 6.5 Web UI Credential Exposure Amplified by New High-Value Secret Types (Security)

**What goes wrong:** The existing web UI localhost-bind requirement (GUI-06, Phase 10) was
designed to protect retailer passwords. The v3.0 additions introduce proxy credentials and
CAPTCHA API keys, which are arguably more sensitive (financial cost if leaked, not just
account ban). If a user overrides the localhost bind (explicit opt-in with warning, as
implemented), those credentials are now exposed to the local network.

**Warning Sign:** The non-localhost bind warning text still references only "retailer
credentials" and does not mention proxy or CAPTCHA API credentials.

**Prevention:** Update the non-localhost bind warning text to enumerate all credential
types now managed by the web UI, including proxy credentials and CAPTCHA API keys.
This is a one-line update to the warning message but is easy to miss.

**Phase:** Stability / security hardening in v3.0

---

## 7. Integration Pitfalls with Existing System

### 7.1 Config Schema Extension Without Pydantic Model Causes Silent Ignore (Moderate)

**What goes wrong:** AppConfig uses `extra="ignore"` on all Pydantic models. Adding proxy
rotation and CAPTCHA config keys to `config.yml` without adding corresponding Pydantic
model fields causes those keys to be silently discarded at startup. The bot runs without
proxy rotation or CAPTCHA because the config was never read, and there is no error or
warning. Users spend hours debugging why proxy rotation has no effect.

**Warning Sign:** User sets `proxy.enabled: true` in config.yml; no proxy-related log
entries appear at startup; bot uses direct connection.

**Prevention:** Every new config section (proxy, captcha, price monitoring) must have a
corresponding Pydantic model added to `config_schema.py` before the feature is implemented.
Add a startup log line that explicitly confirms the proxy and CAPTCHA config state:
"Proxy rotation: disabled" or "Proxy rotation: enabled, pool_size=N". This makes the active
configuration unambiguously visible without requiring the user to diff the schema.

**Note:** The existing naming inconsistency between `delay_seconds`/`delay_jitter`
(Amazon/BestBuy legacy fields) and `min_delay`/`max_delay` (Phase 6 platform fields) is
pre-existing tech debt. V3.0 new platform config fields should use `min_delay`/`max_delay`
for consistency with the Phase 6 majority; do not introduce a third naming scheme.

**Phase:** Anti-Detection Hardening (config schema); also Stability (harmonize delay field
naming as part of the audit tech-debt items)

---

### 7.2 Price Alert Dedup Must Not Conflict with Stock Alert Dedup (Moderate)

**What goes wrong:** Both stock availability (existing) and price-drop alerts (new) need
per-item state in the `items` table. The existing `last_seen_available` (INTEGER) and
`last_notified` (TEXT) columns track stock state for the edge-trigger dedup in
`orchestrator.py` and `models.py`. Reusing `last_notified` for price alerts would cause
a price notification to suppress the next stock-available notification for the same item
(or vice versa): the `get_item_notification_state_sync` function reads `last_notified` to
determine dedup state, and conflating the two events breaks both.

**Prevention:** Add dedicated columns for price state: `current_price REAL`,
`price_last_notified TEXT`, `price_alert_armed INTEGER DEFAULT 0`. Do not modify the
semantics of `last_seen_available` or `last_notified`. Add a parallel
`get_item_price_state_sync(link)` function that reads only the price columns. All price
writes must go through the existing `write_queue` drain in `orchestrator.py` to respect
ASYNC-05 (single async write queue serializes all DB writes).

**Phase:** Price Monitoring (new phase); coordinate with orchestrator.py write-queue

---

### 7.3 CredentialStore Not Initialized Before CAPTCHA/Proxy Code Calls get_store() (Moderate)

**What goes wrong:** `get_store()` in `core/credentials.py` returns a fresh `EnvVarBackend`
if called before `init_store(cfg)` runs in `BotService.__init__`. If proxy or CAPTCHA
initialization code calls `get_store()` at import time or inside a plugin's `__init__`
method, the CredentialStore singleton has not been set, the key falls back to env-var
lookup, and keyring or encrypted-file backends are bypassed silently.

**Warning Sign:** CAPTCHA or proxy credentials work when set as environment variables but
not when stored via the keyring or encrypted-file backend; the startup log shows
"env-var backend active" for a user who has configured keyring.

**Prevention:** Never call `get_store()` in module-level code or in `__init__` methods.
Call it only inside `setup()` or async methods that run after `BotService.__init__` has
completed `init_store(cfg)`. Add this rule explicitly to `PLUGIN_DEV.md` with the
rationale: `get_store()` returns `EnvVarBackend` by default if called before
`init_store()`, which silently bypasses the configured backend.

**Phase:** Anti-Detection Hardening (applies to both proxy and CAPTCHA); Plugin Ecosystem
docs

---

## 8. Phase-Specific Warning Matrix

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Proxy config schema | Silent extra="ignore" drops proxy keys | Add Pydantic proxy model before writing any proxy code (7.1) |
| Proxy auth in nodriver | Auth proxy silently falls back to direct | CDP auth intercept or IP-allowlist only; fail loudly if proxy config present but connection is direct (1.1) |
| Proxy WebRTC | Real IP leaks via WebRTC STUN bypass | Inject three WebRTC Chrome prefs in setup() (1.2) |
| Proxy dead detection | Aborted checkout, item left in ambiguous state | Health-check before checkout; purchased=1 only on confirmed True return (1.4) |
| Proxy datacenter | Entire pool banned via subnet | Document residential requirement for high-detection platforms (1.5) |
| Proxy per-instance scope | Module-level proxy shared across plugins | Store as self._proxy on each plugin instance (1.6) |
| CAPTCHA API key | Key committed to config.yml | Add to SECRET_KEYS before any implementation; no captcha.api_key field in schema (2.2) |
| CAPTCHA solve call | Blocks event loop, freezes all plugins | run_in_executor + asyncio.timeout(120) mandatory (2.3) |
| CAPTCHA cost | Unbounded spend during high-CAPTCHA events | max_solves_per_run config field; default CAPTCHA disabled (2.1) |
| CAPTCHA post-solve still blocked | Misdiagnosed as solve failure | Log solve-success-but-page-still-blocked distinctly (2.4) |
| Fingerprint spoofing | Cross-signal inconsistency detected by ML | Deterministic per-session noise; don't override beyond navigator.webdriver (3.1) |
| UA pool Firefox entries | UA-vs-API mismatch flagged instantly | Chrome-only UAs; startup warning for non-Chrome UA in nodriver plugin (3.2) |
| Fingerprint override order | Undoes nodriver's own patches | Apply in setup() only, test against CreepJS before merging (3.3) |
| Price selector breakage | Wrong/null price after retailer frontend deploy | JSON-LD > OG > CSS cascade; store raw_price_text (4.1) |
| Price locale parsing | Silent 10x-wrong number from non-US format | Babel locale-aware parsing; log raw + parsed (4.2) |
| Price vs stock dedup collision | Price notification suppresses stock alert | Dedicated price columns; parallel get_item_price_state_sync (7.2) |
| Price DB migration | OperationalError on existing installs | Idempotent ALTER TABLE with PRAGMA table_info check; CI migration fixture test (4.4) |
| Wiki staleness | Wiki describes v1 API after v2 bump | Wiki = directory listing only; API docs in PLUGIN_DEV.md (5.1) |
| Community plugin trust | Malicious .py reads CredentialStore | PR checklist; SECURITY.md disclosure; no auto-merge (5.2) |
| Difficulty ratings framing | Encourages ToS bypass escalation | Rename to "detection risk + ToS violation severity"; mandatory ToS disclaimer per plugin (5.3) |
| CAPTCHA legal risk | DMCA §1201 exposure | Opt-in only; disabled by default; explicit disclaimer in config comment and SECURITY.md (6.2) |
| Proxy/CAPTCHA secret logging | str(exc) leaks API key or proxy URL | Log only exc.__class__.__name__; extend CRED-06 test to new secret keys (6.4) |
| CredentialStore timing | get_store() called before init_store() | Only call get_store() inside setup() or async methods; document in PLUGIN_DEV.md (7.3) |

---

## Sources

- GitHub Issue #228 (WebRTC leak with proxies in undetected-chromedriver):
  https://github.com/ultrafunkamsterdam/undetected-chromedriver/issues/228
- GitHub Issue #309 (WebRTC IP leak on UC):
  https://github.com/ultrafunkamsterdam/undetected-chromedriver/issues/309
- GitHub Discussion #1798 (nodriver proxy with authentication):
  https://github.com/ultrafunkamsterdam/undetected-chromedriver/discussions/1798
- GitHub Issue #1903 (SOCKS5 proxy auth in nodriver):
  https://github.com/ultrafunkamsterdam/undetected-chromedriver/issues/1903
- GitHub Issue #2153 (same fingerprints on every nodriver run):
  https://github.com/ultrafunkamsterdam/undetected-chromedriver/issues/2153
- zendriver Issue #108 (canvas + font fingerprints unchanged):
  https://github.com/cdpdriver/zendriver/issues/108
- castle.io: From Puppeteer stealth to nodriver — anti-detect framework evolution:
  https://blog.castle.io/from-puppeteer-stealth-to-nodriver-how-anti-detect-frameworks-evolved-to-evade-bot-detection/
- ProxyWay (Amazon proxy subnet ban behavior):
  https://proxyway.com/best/amazon-proxy
- DataDome (detecting CAPTCHA farm solves vs legitimate human solves):
  https://datadome.co/guides/captcha/how-to-detect-captcha-farms-and-block-captcha-bots/
- 2captcha-python official SDK (polling interval, async pattern):
  https://github.com/2captcha/2captcha-python
- HasData/ecommerce-price-scraper (JSON-LD > OG > CSS extraction cascade):
  https://github.com/HasData/ecommerce-price-scraper
- QuinnEmanuel LLP: Legal landscape of web scraping (CFAA, ToS, DMCA §1201):
  https://www.quinnemanuel.com/the-firm/publications/the-legal-landscape-of-web-scraping/
- Tendem.ai: CFAA vs ToS violation distinction in scraping case law:
  https://tendem.ai/blog/is-web-scraping-legal-compliance-overview
- Unit42/Paloalto: GitHub Actions supply chain attack (plugin trust boundary):
  https://unit42.paloaltonetworks.com/github-actions-supply-chain-attack/
- CISA alert 2026-05-28 (Nx Console VS Code extension compromise):
  https://www.cisa.gov/news-events/alerts/2026/05/28/supply-chain-compromises-impact-nx-console-and-github-repositories
- SuperFastPython: asyncio.timeout() best practices (Python 3.11+):
  https://superfastpython.com/asyncio-timeout-best-practices/
