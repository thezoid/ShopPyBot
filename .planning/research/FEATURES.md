# Feature Landscape

**Domain:** Community-extensible retail stock monitoring and auto-checkout bot (Python/Selenium)
**Researched:** 2026-04-19
**Comparable projects studied:** streetmerchant, StockAlertBot (Prince25), bird-bot, PhoenixBot, BestBuy-Walmart-Automated-Checkout-Bot

---

## Table Stakes

Features users expect. Missing any of these makes the bot feel broken or unusable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Stock availability check per item URL | The entire reason the bot exists | Low | Already working for Amazon, BestBuy |
| Continuous polling loop | One-shot checks are useless; items restock fast | Low | Already implemented; needs async upgrade |
| Configurable check interval | Without it, bots hammer retail sites and get blocked immediately | Low | Must be per-platform; global default acceptable |
| Duplicate-purchase prevention | Users expect never to be charged twice for the same item | Low | Already working (SQLite purchased flag) |
| Test mode / dry run | Users will not trust a bot that can spend real money without a safe trial | Low | Already implemented; must be preserved in refactor |
| Sound/audio alert on stock detection | Immediate sensory alert so user knows without watching terminal | Low | Already implemented (pygame); keep as default alert |
| Structured logging with file output | Support and debugging are impossible without it | Low | Already implemented (writeLog); keep pattern |
| Per-item auto-buy toggle | Not every item in the list warrants auto-purchase | Low | Already in config; must survive plugin refactor |
| CAPTCHA detection with manual fallback | Amazon and BestBuy trigger CAPTCHAs; silent failure is worse | Med | Already partially implemented; must generalize per plugin |
| Safe credential storage (config, not code) | Users will not run a bot that embeds their passwords | Low | Already in config.yml; needs env var support |
| ChromeDriver auto-management | Users should not manually match driver versions to Chrome | Low | Already via webdriver_manager |

---

## Differentiators

Features that separate a good bot from a disposable script. Not universally expected, but valued by the target audience.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Drop-in plugin framework (ABC interface) | Any developer can add a new retailer by dropping one .py file into plugins/ | Med | Core differentiator; defines the project's identity |
| Plugin auto-discovery at startup | Zero config for adding a plugin; importlib scans plugins/ on boot | Low | importlib.import_module over directory scan; no entry_points needed at this scale |
| Plugin contributor template (example_plugin.py) | Lowers barrier to first contribution dramatically | Low | Single file with all four methods stubbed, docstrings, inline comments |
| Async / parallel platform checking | Sequential loop across 7+ platforms is too slow; items sell out in seconds | Med | asyncio or ThreadPoolExecutor; critical for multi-platform usefulness |
| Discord webhook notifications | Discord is the dominant channel for limited-release communities; zero signup friction | Low | HTTP POST; no bot token required; just a webhook URL |
| Email/SMTP notifications | Broadest reach; accessible to non-Discord users | Low | smtplib; already in Python stdlib |
| SMS / Twilio notifications | Push to phone is highest urgency signal | Low | Twilio Python SDK; requires account |
| Per-platform configurable delays with jitter | Mimics human browsing rhythm; avoids rate-limit triggers per site | Low-Med | Random jitter on top of base delay; per-platform in config |
| Headless mode toggle | Lets bot run on headless servers (Linux VPS) without display | Low | Already partially present; needs to be surfaced to config |
| Rotating user agents | Basic browser fingerprint variation; reduces bot signature consistency | Low | Maintain a static list of current Chrome UAs; rotate per session |
| Open browser on detection (monitor mode) | Users who distrust auto-buy can monitor and click manually | Low | Already implemented; surface as first-class config flag |
| GitHub wiki plugin registry | Community discoverability for third-party plugins without PyPI overhead | Low | Markdown table in wiki; PR-based submissions |
| Per-item quantity cap | Prevents accidental over-purchasing during a restock window | Low | Already in config; must be enforced in plugin interface contract |
| Notification payload with item name, URL, timestamp | Alert messages with context are more actionable than "ITEM IN STOCK" | Low | Standardize notification schema in core; plugins provide item metadata |

---

## Anti-Features

Things to deliberately not build. Each one either adds disproportionate complexity, creates a maintenance burden, or contradicts the project's scope.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| GUI / web dashboard | PyQt5 or web UI adds a full dependency stack; target users are CLI-comfortable | Keep CLI + config.yml; log output is sufficient feedback |
| PyPI package per plugin | Forces contributors through packaging workflow; kills contribution rate | Drop-in plugins/ directory with GitHub wiki registry |
| Proxy rotation / residential proxies | Requires paid proxy services; arms-race maintenance; out of v1 scope per PROJECT.md | Configurable delays + user agent rotation covers the moderate anti-detection goal |
| Browser fingerprint spoofing (full) | Canvas hash, WebGL, AudioContext spoofing requires patched Chromium builds; arms-race maintenance | Use undetected-chromedriver or selenium-stealth as optional drop-in; do not build custom spoofing |
| Price monitoring / price drop alerts | Different use case (patience vs. urgency); bloats plugin interface | Keep scope to stock availability; price is an optional plugin-level field, not core |
| Automatic CAPTCHA solving (3rd-party API) | 2captcha/Anti-Captcha costs money per solve; adds external dependency | Detect CAPTCHA, pause, prompt user to solve manually; this is the correct tradeoff |
| Multi-account purchase splitting | Requires managing multiple credentials per platform; ToS violation territory | Single account per platform; quantity cap handles volume |
| Inter-plugin communication / plugin dependencies | Plugins talking to each other creates hidden coupling; cited explicitly as an anti-pattern in plugin architecture literature | Core orchestrates everything; plugins are isolated; no plugin-to-plugin calls |
| "AI-powered" stock prediction | No training data or signal source exists for restock prediction on arbitrary retail SKUs | React to live availability; do not predict |
| Webhook/notification plugins (separate from retail plugins) | Two plugin types with different contracts multiplies framework complexity | Bake three notification channels (Discord, email, SMS) into core; community can PR new ones directly |

---

## Plugin Contributor Experience

What a good contribution workflow looks like for the plugin framework specifically.

### Minimum viable contributor path

A contributor should be able to go from zero to a working plugin in under an hour. The friction points to eliminate:

1. **No discovery friction** — `plugins/` is auto-scanned; no registration step, no config edit required to load a new plugin.
2. **No interface guesswork** — `example_plugin.py` in the repo root of `plugins/` is a fully-stubbed, commented reference implementation. Every method has a docstring explaining what it must return and what it receives.
3. **No test setup friction** — A `tests/plugins/test_example_plugin.py` fixture demonstrates how to test each interface method with a mock driver. Contributors copy and adapt it.
4. **Clear contract** — The ABC defines exactly four methods with explicit signatures, return types, and docstrings. `auto_buy` is allowed to return `NotImplemented` / raise `NotImplementedError` if the platform does not support auto-checkout (monitoring-only plugins are valid).
5. **Single PR workflow** — Contribute the plugin .py file; optionally submit a PR to add it to the GitHub wiki registry table.

### Contributor documentation requirements

| Doc | Content | Where |
|-----|---------|--------|
| `plugins/PLUGIN_DEV.md` | Interface contract, method signatures, what each method must/must not do, return type conventions, config key naming convention | plugins/ directory |
| `example_plugin.py` | Fully stubbed implementation with inline comments; covers happy path and stub for CAPTCHA | plugins/ directory |
| `CONTRIBUTING.md` | Dev environment setup, how to run tests, PR checklist, code style | repo root |
| GitHub wiki "Plugin Registry" page | Markdown table: plugin name, author, platforms, link, status | wiki |

### Plugin interface contract (what the ABC must enforce)

| Method | Must Return | Notes |
|--------|-------------|-------|
| `check_availability(driver, url) -> bool` | `True` if item is in stock, `False` otherwise | Raise on network error; do not swallow |
| `auto_buy(driver, url, config, quantity, test_mode) -> bool` | `True` if purchase completed, `False` if skipped/failed | Raise `NotImplementedError` if platform does not support auto-buy |
| `login(driver, config) -> None` | None | Called once at session start; raise on auth failure |
| `detect_captcha(driver) -> bool` | `True` if CAPTCHA is present | Core will pause and prompt user if this returns True |

---

## Notification Patterns

What works for stock alert bots specifically (informed by streetmerchant, StockAlertBot, community practice).

### Channel priority by urgency

| Channel | Latency | Urgency | Setup Friction | Recommended |
|---------|---------|---------|---------------|-------------|
| Sound alert | <1s | Highest (if at PC) | Zero | Yes — keep as primary |
| Discord webhook | <500ms | High | Minimal (one URL) | Yes — highest community adoption |
| SMS / Twilio | 1-5s | High (mobile push) | Moderate (account + API keys) | Yes |
| Email / SMTP | 5-30s | Medium | Low (any email) | Yes |
| Open browser tab | Instant | Low (requires action) | Zero | Yes — monitor mode |

### Notification payload standard

Every notification, regardless of channel, should include:
- Item name
- Retailer / platform name
- Direct URL (shortened via TinyURL or raw)
- Timestamp
- Whether auto-buy was attempted and the outcome

### What to avoid in notifications

- **Notification spam**: Alert once per restock event, not once per poll cycle. Track "last notified" state per item to suppress duplicate alerts.
- **Silent success**: If auto-buy succeeds, send a purchase-confirmed notification distinct from the availability alert.
- **Silent failure**: If auto-buy fails (CAPTCHA, session expired, out of stock by checkout time), send a failure alert so the user can act manually.

---

## Anti-Detection — What Retail Platforms Do and Standard Defenses

### What retail sites deploy

| Platform | Known Protections | Difficulty |
|----------|-------------------|------------|
| Amazon | CAPTCHA (intermittent, not always triggered), session cookies, behavior analysis | Medium — CAPTCHA is the main blocker; DOM-based check is reliable |
| BestBuy | Akamai Bot Manager, rate limiting on add-to-cart | Medium — checkout flow is fragile; delays required |
| Walmart | PerimeterX (now HUMAN Security), aggressive fingerprinting | High — most consistently blocks headless Selenium |
| Target | Akamai, requires real login session; blocks headless | High — headless is unreliable; real browser profile helps |
| GameStop | CAPTCHA on checkout, proxy blocking | Medium — availability check works; checkout unreliable |
| NewEgg | Moderate bot detection | Low-Medium — historically more permissive |
| Square Enix Store | Standard CloudFlare or minimal protection | Low — limited-release items, not a high-traffic target |

### Standard defenses (in scope for this project)

| Defense | Implementation | Complexity | Covers |
|---------|---------------|------------|--------|
| Random delays with jitter | `time.sleep(base + random.uniform(0, jitter))` per config | Low | All platforms |
| Rotating user agents | Static list of current Chrome UA strings; rotate per session | Low | All platforms |
| `--disable-blink-features=AutomationControlled` | Chrome flag; already in codebase | Low | Basic navigator.webdriver detection |
| Headless mode toggle | `--headless=new` Chrome flag; surfaced to config | Low | Server deployments |
| CAPTCHA detection + manual pause | Plugin contract method; pause loop and prompt user | Low-Med | Amazon, GameStop |
| Session persistence (profile dir) | `user-data-dir` Chrome flag per platform config | Med | Avoids repeated login challenges |

### Out of scope (explicitly deferred)

- `undetected-chromedriver` / `selenium-stealth` drop-in: Valid option for plugin authors; do not mandate in core. The arms race makes it a plugin-level concern, not a framework guarantee.
- Proxy rotation: Requires paid services; out of v1 scope.
- Full browser fingerprint spoofing (Canvas, WebGL, AudioContext): Requires patched Chromium; maintenance burden exceeds value for personal-use bot.

---

## MVP Recommendation

Prioritize (ordered by dependency and risk):

1. Plugin ABC interface + auto-discovery — everything else is unshippable without this
2. Amazon and BestBuy refactored to implement the interface — validates the contract with working code
3. Async parallel checking — required before adding 5 more platforms; sequential is too slow
4. Discord webhook + Email notifications — covers 95% of community notification needs; SMS is Phase 2
5. Per-platform config (delays, credentials) — needed before new platforms can be configured safely
6. Walmart plugin — highest community demand after Amazon/BestBuy
7. example_plugin.py + PLUGIN_DEV.md — must ship before community contributions are possible

Defer to later phases:
- Target and GameStop plugins — high anti-detection difficulty increases risk of unstable implementations
- Square Enix and NewEgg plugins — lower priority; less community demand for these specific stores
- SMS/Twilio — valid feature, but Discord + email covers the urgent use case first
- GitHub wiki plugin registry — publish after at least one community plugin exists to validate the workflow

---

## Sources

- [streetmerchant notification reference](https://www.jef.buzz/streetmerchant/reference/notification/) — comprehensive notification provider inventory (Discord, Slack, Telegram, Twilio, NTFY, Pushover, email)
- [StockAlertBot (Prince25/StockAlertBot)](https://github.com/Prince25/StockAlertBot) — multi-retailer Python bot with multi-channel notifications; reference for feature completeness
- [PhoenixBot (Strip3s/PhoenixBot)](https://github.com/Strip3s/PhoenixBot) — covers Walmart, BestBuy, GameStop, Target; validates PyQt5 GUI as an anti-feature for this project
- [bird-bot (natewong1313)](https://github.com/natewong1313/bird-bot) — Walmart/BestBuy; archived 2021; GUI-first approach confirms CLI is the right choice
- [How to Build Plugin Systems in Python (OneUptime, 2026)](https://oneuptime.com/blog/post/2026-01-30-python-plugin-systems/view) — plugin isolation principle; no plugin-to-plugin communication
- [Bypassing PerimeterX and Akamai 2024](https://proxycove.com/en/blog/bypass-perimeterx-akamai-detection) — Walmart/Target protection stack confirmation
- [undetected-chromedriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver) — arms-race nature of open-source bypass tools; justifies keeping advanced anti-detection out of core
- [How to Bypass Bot Detection in 2025 (ScraperAPI)](https://www.scraperapi.com/web-scraping/how-to-bypass-bot-detection/) — user agent consistency with client-hint headers; behavioral jitter necessity
- [GameStop Stellar guide](https://guides.stellaraio.com/stellar/retailers/gamestop) — proxy blocking, CAPTCHA difficulty confirmation for GameStop
- [Exponential backoff and jitter (OpenAI cookbook)](https://developers.openai.com/cookbook/examples/how_to_handle_rate_limits) — delay strategy with jitter for rate-limit avoidance
- [Python ABC documentation](https://docs.python.org/3/library/abc.html) — interface enforcement at class creation time
- [Writing plugins in Python (desc0n0cid0)](https://desc0n0cid0.blogspot.com/2017/06/writing-plugins-in-python.html) — importlib-based plugin discovery pattern
