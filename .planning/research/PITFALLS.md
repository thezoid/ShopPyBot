# Domain Pitfalls: ShopPyBot

**Domain:** Async retail shopping bot with open source plugin framework
**Researched:** 2026-04-19
**Sources:** Codebase audit (CONCERNS.md), WebSearch, official SQLite docs, Selenium issue tracker, Python packaging guide

---

## Critical Pitfalls

Mistakes that cause rewrites, permanent bans, or security incidents.

---

### Pitfall 1: navigator.webdriver Exposes Selenium to Amazon Immediately

**What goes wrong:**
Any Chrome instance launched with Selenium sets `navigator.webdriver = true` in the JavaScript environment. Amazon's bot detection (Imperva/PerimeterX) checks this flag as a first-pass filter. The current codebase also passes `--disable-web-security` (main.py line 62), which is an abnormal flag that no real browser uses and is trivially detectable in the browser's feature set. Combined with `HeadlessChrome` appearing in the User-Agent when headless mode is added, a stock Selenium setup is banned within a single session on Amazon.

**Why it happens:**
Selenium sets `navigator.webdriver` by design as a debugging signal. The `--disable-web-security` flag was likely added to work around a CORS issue and never removed. Headless mode appends `HeadlessChrome` to the UA string by default.

**Consequences:**
- CAPTCHA escalation on first or second request to Amazon product pages
- Silent redirect to a robot-check page that looks identical to a real page but never renders the buy buttons (causing the bot to loop forever reporting "unavailable")
- In severe cases, IP-level ban for the session

**Prevention:**
Minimum viable stealth for personal use requires three things applied before any `driver.get()`:

1. Remove `navigator.webdriver` via CDP (Chrome DevTools Protocol):
   ```python
   driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
       "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
   })
   ```
2. Set a real Chrome user-agent string that matches the installed Chrome version. Never leave `HeadlessChrome` in the UA string.
3. Remove `--disable-web-security` from Chrome options unconditionally.

**Detection (warning signs):**
- Bot consistently reports unavailable on items known to be in stock
- Amazon product pages load but no add-to-cart/buy-now button is ever found
- Selenium sessions receive CAPTCHA on every request regardless of delay

**Phase to address:** Plugin framework phase (Phase 1) — the `BasePlugin` interface should include a `configure_driver(options)` hook so each plugin can add platform-specific stealth arguments. Core driver setup must apply the CDP navigator.webdriver patch before any plugin uses the driver.

---

### Pitfall 2: Consistent Request Timing is a Bot Fingerprint

**What goes wrong:**
Polling every N seconds with the same interval is statistically impossible for a human. Anti-bot systems model inter-request timing distribution. A bot with a 30-second loop on 5 items produces a near-perfect sawtooth pattern across those item URLs that flags the account for review within hours. The current codebase has no jitter at all.

**Why it happens:**
`time.sleep(N)` feels correct for "check every 30 seconds" but produces machine-perfect regularity.

**Consequences:**
- Session-level soft ban (redirected to robot-check pages)
- Amazon order account flagged; subsequent legitimate purchases may be blocked

**Prevention:**
Use `time.sleep(base_delay + random.uniform(-jitter, jitter))` where jitter is 20-40% of base_delay. Configurable per-platform in config.yml under `platforms.amazon.delay_seconds` and `platforms.amazon.delay_jitter`. Never hard-code a fixed delay.

**Detection (warning signs):**
- Bot runs fine for first 1-2 hours then begins receiving CAPTCHAs on every request
- No change in stock status despite items known to be dropping

**Phase to address:** Config schema phase — per-platform delay and jitter must be first-class config fields, not optional afterthoughts.

---

### Pitfall 3: Single ChromeDriver Instance Across Async Workers Causes Crashes and Race Conditions

**What goes wrong:**
Selenium WebDriver instances are not thread-safe. A single `driver` object shared across async workers or threads will corrupt internal state when two coroutines issue concurrent `driver.get()` or `find_element()` calls. The resulting failure mode is non-deterministic: sometimes a `StaleElementReferenceException`, sometimes a silent page navigation that makes a different item's DOM visible to the wrong worker, sometimes a ChromeDriver crash that kills all workers.

**Why it happens:**
The current codebase uses one driver for everything (`main.py` lines 49-65). Adding `asyncio` or `ThreadPoolExecutor` without changing driver architecture will share this single instance.

**Consequences:**
- Workers checking BestBuy end up acting on Amazon's DOM, or vice versa
- ChromeDriver WebSocket connection drops under concurrent load (confirmed in SeleniumHQ/selenium issue #12751)
- "database is locked" cascades because a crashed worker leaves an open SQLite transaction

**Prevention:**
One driver instance per platform, not per item. Instantiate drivers in a platform-scoped context manager. Starting multiple instances simultaneously can cause port conflicts on the ChromeDriver debug port — stagger initialization with a 1-2 second delay between driver starts:
```python
async def start_platform_worker(plugin, config):
    await asyncio.sleep(worker_index * 1.5)  # stagger startup
    driver = create_driver(config)
    try:
        await plugin.run_loop(driver, config)
    finally:
        driver.quit()
```

**Detection (warning signs):**
- `StaleElementReferenceException` appearing in logs for items that haven't changed page
- ChromeDriver process exits unexpectedly during parallel runs
- Log messages from two different plugins interleaved with the wrong platform URL

**Phase to address:** Async refactor phase. This is the highest-risk architectural change in the project and must be validated with an integration test before adding more than two platform workers.

---

### Pitfall 4: SQLite "database is locked" Under Concurrent Workers

**What goes wrong:**
The current `models.py` opens a new `sqlite3.connect()` on every function call, performs the operation, and calls `conn.close()`. Under sequential operation this is fine. Under async workers with multiple platforms running simultaneously, two workers can call `update_item_purchased()` within milliseconds of each other. SQLite's default lock timeout is 5 seconds in rollback journal mode; in WAL mode, concurrent readers are fine but concurrent writers still serialize. With the GIL and Python threading, this produces intermittent `sqlite3.OperationalError: database is locked` exceptions that the current code does not handle — the exception propagates up and the purchased state is never written, causing duplicate purchase attempts on the next loop.

**Why it happens:**
Each function in `models.py` creates its own connection with no `check_same_thread` consideration and no `timeout` parameter. No `with` context manager is used, so an exception before `conn.close()` leaks the connection and holds the lock.

**Consequences:**
- Duplicate purchases: item is bought, `update_item_purchased()` throws, item is not marked purchased, bot buys it again on next loop
- BestBuy already has this bug (CONCERNS.md) — concurrent operation will make it worse
- Connection leak accumulates until OS-level file descriptor limit is hit

**Prevention:**
Three changes required together:

1. Enable WAL mode at DB initialization:
   ```python
   conn.execute("PRAGMA journal_mode=WAL")
   conn.execute("PRAGMA busy_timeout=5000")
   ```
2. Use context managers for all connections:
   ```python
   with sqlite3.connect(DB_PATH, timeout=10) as conn:
       conn.execute(...)
   ```
3. Funnel all writes through a single async-safe writer. The simplest approach: a dedicated write queue with an `asyncio.Queue` drained by one coroutine. Readers (checking purchased status) can use their own connections in WAL mode without contention.

**Detection (warning signs):**
- `sqlite3.OperationalError: database is locked` in logs during multi-platform runs
- Same item purchased more than once
- Bot log shows "ORDER PLACED" but item still appears as `purchased=0` in the DB

**Phase to address:** Async refactor phase, simultaneously with the driver-per-platform change. Do not introduce concurrency without fixing the DB write pattern first.

---

### Pitfall 5: Plugin Interface Breakage Kills Contributor Trust

**What goes wrong:**
If the `BasePlugin` ABC gains a new required abstract method between versions (e.g., adding `handle_rate_limit()` in a later phase), every existing plugin immediately raises `TypeError: Can't instantiate abstract class` at import time. Contributors who wrote a plugin for v1 find their plugin is broken on v2 with no migration path and no useful error message. This is the fastest way to kill community contribution.

**Why it happens:**
ABC enforces all abstract methods at instantiation. Adding a method to the ABC is a silent breaking change — Python will not warn the contributor when they write the plugin; it only fails at runtime.

**Consequences:**
- Community plugins break silently on update
- Contributors lose confidence in the stability of the API
- Maintainer spends time fielding "my plugin broke" issues rather than building features

**Prevention:**
Two rules:

1. **Provide default no-op implementations for any method that is not universally required.** `detect_captcha()` and `handle_rate_limit()` should have default implementations that return `None` or `False`. Only `check_availability()` and `auto_buy()` should be abstract (truly required by all plugins).

2. **Version the plugin interface explicitly.** Add a `PLUGIN_API_VERSION = 1` constant to the base class. The loader checks this version at import time and emits a clear warning (not an exception) if the plugin's declared version is older:
   ```python
   if getattr(plugin_cls, 'PLUGIN_API_VERSION', 0) < CURRENT_API_VERSION:
       log.warning(f"{plugin_cls.__name__} targets API v{...}, current is v{...}. Some features may not work.")
   ```

**Detection (warning signs):**
- Community issues titled "my plugin stopped working after update"
- `TypeError: Can't instantiate abstract class` in startup logs when loading plugins
- Contributors submitting PRs that pin to old versions of the bot

**Phase to address:** Plugin framework phase (Phase 1). The API contract must be finalized and versioned before any platform plugin is written. Changing it after three plugins exist is painful.

---

### Pitfall 6: CVV and Plaintext Credentials Committed to Public Repos

**What goes wrong:**
`config.yml` contains `amz_pwd`, `amz_email`, `bb_password`, and critically `bb_cvv`. When a contributor clones the repo, sets up their config, and then accidentally stages `config.yml` instead of `sample.config.yml` in a pull request, real credentials and a CVV hit the public GitHub history. A git history scan finds it within hours. Storing a CVV in any file also violates PCI-DSS regardless of whether it's ever committed.

**Why it happens:**
Flat YAML config is simple and beginner-accessible, but "never commit config.yml" is a rule that gets broken once per year by every project that uses it. The `.gitignore` provides no protection against an explicit `git add config.yml`.

**Consequences:**
- Compromised Amazon/BestBuy accounts
- Payment card fraud from exposed CVV
- For an open source project: public GitHub issue, maintainer liability questions, potential report to GitHub trust & safety

**Prevention:**
- CVV must never persist to disk. Prompt for it at runtime using `getpass.getpass("CVV: ")` and hold only in memory.
- Credentials should move to environment variables (`SHOPBOT_AMZ_EMAIL`, etc.) with `config.yml` holding only non-sensitive settings (URLs, delays, item list). The `sample.config.yml` should contain no credential fields at all — they belong in a `.env.example` file.
- Add a pre-commit hook that scans for `_pwd`, `_password`, `_cvv` patterns in YAML files and blocks the commit.

**Detection (warning signs):**
- Community contributor submits a PR with real email addresses in config
- GitHub secret scanning alerts (GitHub scans public repos for credential patterns)

**Phase to address:** Config schema phase — the credential storage model must be changed before the project goes public as open source. It cannot be deferred.

---

## Moderate Pitfalls

---

### Pitfall 7: Plugin Auto-Discovery Loads Untrusted Code Without Isolation

**What goes wrong:**
`importlib`-based auto-discovery from a `plugins/` folder executes arbitrary Python at import time. A malicious or buggy community plugin can call `os.system()`, corrupt `sys.modules`, or monkey-patch the `BasePlugin` class itself. There is no sandboxing. Additionally, if two plugins define a top-level name that collides (e.g., both define a `logger` variable in module scope), the second import silently overwrites the first in `sys.modules` depending on load order.

**Prevention:**
- Document clearly that plugins run with full host privileges — this sets contributor expectations and is honest about the threat model (personal-use tool, not a marketplace).
- Require plugins to follow a naming convention: `shopbot_plugin_{platform}.py`. Auto-discovery filters on this prefix, which prevents accidental loading of unrelated `.py` files dropped in the folder.
- Never auto-reload plugins at runtime without restarting the process (`importlib.reload()` on extension code produces unpredictable results with class identity).

**Phase to address:** Plugin framework phase. Document the security model in `CONTRIBUTING.md` before soliciting external plugins.

---

### Pitfall 8: Config Schema Evolution Silently Breaks Existing Installs

**What goes wrong:**
A user sets up ShopPyBot v1 with a `config.yml` that has `app.amz_email`. Phase 2 refactors to `platforms.amazon.email`. The bot starts, silently skips the old key (because `config.get('platforms', {}).get('amazon', {}).get('email')` returns `None`), and then either crashes on the first Amazon request or, worse, logs in as nobody and still attempts to purchase. Users report "it stopped working" with no useful error.

**Why it happens:**
YAML `dict.get()` with defaults returns `None` instead of raising on missing keys. There is no schema validation step at startup.

**Prevention:**
Add a config validation function that runs at startup and raises `SystemExit` with a clear migration message if required keys are missing. Use a simple explicit check (not a schema library like Pydantic unless already in the stack) that lists required fields by name and prints exactly which key is missing and what the new name is:
```python
def validate_config(config):
    required = [
        ('platforms.amazon.email', 'was: app.amz_email'),
        ('platforms.amazon.password', 'was: app.amz_pwd'),
    ]
    for path, migration_hint in required:
        if not _get_nested(config, path):
            raise SystemExit(f"Missing config key: {path} ({migration_hint})")
```

**Phase to address:** Config schema phase. Write the validator alongside the new schema, not after.

---

### Pitfall 9: Async + Blocking input() Calls Deadlock the Event Loop

**What goes wrong:**
The current codebase uses `input()` in three places for CAPTCHA, passkey dismissal, and MFA. `input()` is a blocking call. In an `asyncio` event loop, a blocking call in a coroutine starves every other coroutine until the human responds. With multiple platform workers running, one Amazon CAPTCHA pause causes BestBuy and Walmart workers to stop polling entirely — during which a Walmart drop could be missed.

**Why it happens:**
`input()` is the simplest way to pause for human input. It works fine in sequential code and feels harmless.

**Consequences:**
- All platform workers stall during any Amazon authentication event
- A drop on a non-Amazon platform is missed while the user is solving an Amazon CAPTCHA

**Prevention:**
Replace all `input()` blocking calls with a notification-then-wait pattern using asyncio-compatible primitives. Discord webhook or a simple HTTP POST can alert the user. The worker sets an `asyncio.Event` that it awaits; other workers continue. A separate signal handler or a dedicated endpoint sets the event when the user signals ready. For a simpler approach: move authentication to a pre-loop phase that completes before async workers start.

**Phase to address:** Async refactor phase. The blocking sign-in flow must be restructured before parallelism is introduced — it cannot be patched after.

---

### Pitfall 10: Unpinned Dependencies Break Community Installs

**What goes wrong:**
`requirements.txt` has no version pins. Selenium 4.x introduced major API changes from 3.x. PyYAML 5.1 changed the default `yaml.load()` behavior and introduced breaking loader requirements. `webdriver-manager` has had several API changes around ChromeDriver path resolution. A user who installs six months after a contributor tested will get different package versions and a broken bot with an inscrutable error.

**Prevention:**
Pin all dependencies to exact versions after a validated install: `pip freeze > requirements.txt`. Deduplicate the current duplicate entries (`selenium` appears twice, `pyyaml` appears twice, `webdriver-manager` has inconsistent casing). Add a minimum Python version declaration (`python_requires >= 3.10`).

**Phase to address:** Phase 1 housekeeping. Fix before any new code is written.

---

## Minor Pitfalls

---

### Pitfall 11: YAML Boolean Parsing Surprises

**What goes wrong:**
PyYAML (still on YAML 1.1 spec) treats `yes`, `no`, `on`, `off`, `true`, `false` as booleans. A config value like `mode: on` becomes Python `True`. A platform name like `store: yes` becomes `True`. This produces silent type errors when the code does string comparison (`if platform == "yes"`).

**Prevention:**
Always quote non-boolean string values in config. Document this in the sample config with a comment. The startup config validator should type-check fields where a boolean would be invalid.

**Phase to address:** Config schema phase.

---

### Pitfall 12: ChromeDriver Version Mismatch After Chrome Auto-Update

**What goes wrong:**
`webdriver-manager` auto-downloads a ChromeDriver version matching the installed Chrome at first run. Chrome updates silently in the background on Windows. After an update, ChromeDriver and Chrome versions diverge and Selenium throws `SessionNotCreatedException` with a confusing version mismatch message. Users file issues thinking the bot is broken.

**Prevention:**
Log the Chrome and ChromeDriver versions detected at startup. Add a clear error message that identifies a version mismatch explicitly rather than letting Selenium's raw exception surface. Pin ChromeDriver to match the Chrome major version explicitly rather than relying on auto-detection, or document the manual fix procedure prominently in the README.

**Phase to address:** Driver setup in Phase 1. Add to startup diagnostics.

---

### Pitfall 13: Open Source Legal Exposure from the BOTS Act

**What goes wrong:**
The Better Online Ticket Sales (BOTS) Act makes it a federal violation to use bots that circumvent security measures to enforce purchasing limits. While the act targets ticket scalping specifically, its language is broad enough to cover limited-release retail goods (GPU drops, gaming hardware, collectibles). Participating retailers (Best Buy, Walmart) have TOS clauses that explicitly prohibit automated purchasing. Publishing a bot that automates purchases and publicizing it as a tool to bypass purchase limits creates legal exposure for contributors.

**Why it happens:**
Most contributors believe "it's personal use, it's fine." The personal use defense does not protect the maintainer of a public repository that distributes the tool.

**Consequences:**
- DMCA-style TOS-violation takedown requests to GitHub (not common for non-scraping bots, but documented in github/dmca for Discord bots)
- Account termination of contributors' Amazon/BestBuy accounts if linked to bot activity
- For high-profile projects: cease-and-desist from a retailer's legal team

**Prevention:**
- Add a prominent disclaimer in `README.md` and `CONTRIBUTING.md`: "For personal use only. Users are responsible for compliance with their retailer's Terms of Service. The maintainers make no representations about the legality of this tool in your jurisdiction."
- Do not build or document features that explicitly help users circumvent per-customer purchase limits (e.g., multi-account rotation, order limit bypass).
- Keep the project framed as a stock notification tool with an optional manual purchase trigger — this is defensible. Framing it as an "auto-buy" bot is more exposed.

**Phase to address:** Before going public. Add disclaimer to README at project initialization.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Plugin framework (ABC definition) | Breaking interface changes when new methods are added | Default no-op implementations; PLUGIN_API_VERSION constant from day one |
| Plugin auto-discovery | Namespace collision if two plugins export same module-level name | Enforce `shopbot_plugin_{platform}.py` naming; never import `*` |
| Driver-per-platform async | ChromeDriver port conflicts on startup | Stagger driver initialization by 1.5s per worker |
| Async event loop | `input()` blocking halts all workers | Replace with `asyncio.Event` + notification before parallelism is introduced |
| Config schema refactor | Silent `None` for missing required keys | Startup validator with migration hints required before schema change ships |
| SQLite under concurrency | "database is locked" on concurrent `update_item_purchased()` calls | WAL mode + `busy_timeout` + single async write queue before concurrency is enabled |
| Amazon stealth | `navigator.webdriver` and `--disable-web-security` | CDP patch + UA normalization + remove debug flag in Phase 1 driver setup |
| Credentials | CVV persisted to disk, credentials in committed YAML | CVV via `getpass` at runtime; credentials via env vars only |
| Open source launch | Legal exposure from auto-buy framing | Disclaimer in README; personal-use framing; no limit-bypass features |
| Dependency management | Unpinned packages break installs | `pip freeze` pin before any community onboarding |

---

## Sources

- Codebase audit: `E:/repos/ShopPyBot/.planning/codebase/CONCERNS.md`
- SeleniumHQ issue #12751 (WebDriver crashes in multi-process parallel runs): https://github.com/SeleniumHQ/selenium/issues/12751
- Python Packaging Guide — Creating and discovering plugins: https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/
- SQLite concurrent writes — "database is locked" analysis: https://www.sqlitetutor.com/database-is-locked/
- SQLite WAL threading behavior: https://iifx.dev/en/articles/17373144
- Selenium bot detection — navigator.webdriver: https://www.zenrows.com/blog/navigator-webdriver
- undetected_chromedriver alternatives and detection surface: https://www.scrapingbee.com/blog/undetected-chromedriver-python-tutorial-avoiding-bot-detection/
- Headless Chrome detection (2024): https://deviceandbrowserinfo.com/learning_zone/articles/detecting-headless-chrome-selenium-2024
- Amazon scraping legality and TOS: https://www.scrapehero.com/is-scraping-amazon-legal/
- BOTS Act retail purchasing context: https://www.tidalmarket.com/blog/retail-botting-guide
- PyYAML 5.1 breaking changes: https://github.com/yaml/pyyaml/issues/265
- sys.modules reload dangers: https://justus.science/blog/sys-modules-is-dangerous/
- Charles Leifer — multi-threaded SQLite without OperationalErrors: https://charlesleifer.com/blog/multi-threaded-sqlite-without-the-operationalerrors/
