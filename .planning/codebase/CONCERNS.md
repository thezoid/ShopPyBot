# Codebase Concerns

**Analysis Date:** 2026-04-19

## Tech Debt

**Duplicate requirements.txt entries:**
- Issue: `selenium` listed twice (lines 2, 5), `pyyaml` listed twice (lines 4, 6), `webdriver_manager` listed twice (lines 3, 11 — different casing). pip may resolve silently or install conflicting versions.
- Files: `requirements.txt`
- Impact: Inconsistent installs, confusion over canonical package name (`webdriver-manager` vs `webdriver_manager`)
- Fix approach: Deduplicate and standardize to hyphenated names matching PyPI canonical names

**config.py singleton vs main.py re-load:**
- Issue: `config.py` loads `config.yml` at import time and exposes a module-level `config` object. `main.py` defines and calls its own `load_config()` independently, creating two separate config loads and a shadowed local `config` variable that hides the imported singleton.
- Files: `config.py` (line 7), `main.py` (lines 38-44)
- Impact: Any runtime change to config between startup and loop execution could diverge. The local shadow makes it unclear which config is authoritative inside `main()`. Bot module functions that receive `config` as a parameter get the `main.py` copy, not the singleton.
- Fix approach: Remove `load_config()` from `main.py` and use the singleton from `config.py` consistently throughout

**logger.py reads config.yml on every log call:**
- Issue: `writeLog()` calls `load_settings()` which opens and parses `config.yml` via `yaml.safe_load()` on every invocation. The main loop calls `writeLog` dozens of times per iteration.
- Files: `logger.py` (lines 7-9, 15-17)
- Impact: Disk I/O and YAML parse overhead on every log statement — significant in a tight polling loop
- Fix approach: Load settings once at module import or accept logging level as a parameter; use a cached value

**No retry or backoff on failed page loads:**
- Issue: If `driver.get(url)` fails or a `WebDriverWait` times out, the exception is caught and logged but the item is skipped entirely for that iteration with no retry.
- Files: `amazon_bot.py` (lines 19-54), `bestbuy_bot.py` (lines 7-25), `main.py` (lines 85-136)
- Impact: Transient network errors or slow page loads cause missed detection windows, particularly for high-demand item drops
- Fix approach: Wrap page load and button detection in a retry loop with exponential backoff (max 3 attempts)

**No headless browser support:**
- Issue: Chrome is always launched in visible mode. There is no `--headless` argument in the options setup despite headless being an initial refactor goal.
- Files: `main.py` (lines 49-65)
- Impact: Bot cannot run in server or background environments without a display. Headed Chrome also makes automation more detectable.
- Fix approach: Add `headless` flag to `config.yml` and conditionally apply `--headless=new` Chrome argument

**Sequential item checking, no concurrency:**
- Issue: Items are checked one at a time in a `for` loop inside `while True`. Each item check blocks on `WebDriverWait` calls (up to 10s per element, multiple per item).
- Files: `main.py` (lines 85-136)
- Impact: With multiple items, total loop time scales linearly. A slow or unavailable site delays checks for all subsequent items in the list.
- Fix approach: Introduce threading or `concurrent.futures.ThreadPoolExecutor` per item, or use separate driver instances per retailer

**BestBuy quantity selector uses wrong CSS class:**
- Issue: `auto_buy_bestbuy_item` waits for `.a-dropdown-prompt` to set quantity — this is an Amazon CSS class, not a BestBuy class. BestBuy uses a different quantity UI.
- Files: `bestbuy_bot.py` (lines 52-60)
- Impact: Quantity selection will always fail silently on BestBuy auto-buy; the except block only logs the error and does not halt the purchase, meaning it may attempt checkout with wrong quantity
- Fix approach: Identify and use the correct BestBuy quantity selector; add explicit failure exit if quantity cannot be set

**BestBuy auto-buy missing purchased state update:**
- Issue: `auto_buy_bestbuy_item` does not call `update_item_purchased()` after a successful order. Amazon's flow calls it correctly.
- Files: `bestbuy_bot.py` (lines 40-73), `models.py` (lines 39-48)
- Impact: After a successful BestBuy purchase, the item remains `purchased=0` in the database and the bot will attempt to buy it again on the next loop iteration
- Fix approach: Call `update_item_purchased(item_url)` inside `auto_buy_bestbuy_item` on confirmed order placement, mirroring the Amazon pattern

## Known Bugs

**BestBuy button detection returns False on timeout (not unavailability):**
- Symptoms: `check_bestbuy_item` raises `TimeoutException` when the page is slow or the button class changes, catches it as a generic exception, and returns `False` — same as "not available"
- Files: `bestbuy_bot.py` (lines 7-25)
- Trigger: Slow BestBuy page load or any DOM change to `add-to-cart-button` class
- Workaround: None — check logs for ERROR lines to distinguish from genuine unavailability

**Amazon check_amazon_item calls detect_captcha after driver.get, but main loop also calls detect_captcha before check_amazon_item:**
- Symptoms: Double CAPTCHA check per Amazon item; if CAPTCHA appears between the two checks, only one `input()` pause fires but the page state may be inconsistent
- Files: `amazon_bot.py` (lines 19-27), `main.py` (lines 95-98)
- Trigger: CAPTCHA served by Amazon on initial page load
- Workaround: Manual observation required

## Security Considerations

**Credentials stored in plaintext config.yml:**
- Risk: `amz_email`, `amz_pwd`, `bb_email`, `bb_password`, and `bb_cvv` are stored in plaintext YAML. If `config.yml` is committed or shared, credentials are fully exposed.
- Files: `config.py`, `main.py`, `amazon_bot.py`, `bestbuy_bot.py`, `sample.config.yml`
- Current mitigation: `sample.config.yml` uses placeholder strings; `.gitignore` presumably excludes `config.yml` (not verified)
- Recommendations: Load credentials from environment variables or a secrets manager; never include real credentials in any committed file

**CVV stored in config:**
- Risk: Storing a payment CVV in a config file violates PCI-DSS guidelines and is a significant security risk.
- Files: `config.py`, `bestbuy_bot.py` (line 40), `sample.config.yml`
- Current mitigation: None beyond file-level access control
- Recommendations: Prompt for CVV at runtime via `getpass` rather than persisting it

**stdout/stderr suppressed during driver init:**
- Risk: `sys.stdout` and `sys.stderr` are redirected to `/dev/null` during Chrome startup. Any exception or crash during this window produces no output and is silently lost.
- Files: `main.py` (lines 68-75)
- Current mitigation: Streams are restored immediately after driver init
- Recommendations: Use `subprocess` DEVNULL or Chrome's `--log-level=3` argument instead of suppressing Python streams

## Performance Bottlenecks

**YAML file read on every writeLog call:**
- Problem: Each `writeLog()` call opens, reads, and parses `config.yml` to get `logging_level`
- Files: `logger.py` (lines 7-9, 15-17)
- Cause: No caching; `load_settings()` is called inline inside `writeLog`
- Improvement path: Cache the logging level at module load; reload only on SIGHUP or explicit request

**Log file opened and closed on every writeLog call:**
- Problem: When `writeTofile=True`, a new file handle is opened, written, and closed for each log entry
- Files: `logger.py` (lines 31-37)
- Cause: No persistent file handler; uses ad-hoc `open()` per call
- Improvement path: Use Python's `logging.FileHandler` with the existing `logging` import, which buffers and keeps the handle open

**Sequential WebDriverWait calls in check_amazon_item:**
- Problem: `check_amazon_item` waits up to 10 seconds for `add-to-cart-button`, then another 10 seconds for `buy-now-button`, sequentially — up to 20 seconds per Amazon item when unavailable
- Files: `amazon_bot.py` (lines 29-43)
- Cause: Two separate `WebDriverWait` blocks with no short-circuit
- Improvement path: Use a single wait with a combined XPath or `EC.any_of` condition

## Fragile Areas

**Amazon sign-in flow requires manual intervention:**
- Files: `amazon_bot.py` (lines 56-121)
- Why fragile: Two `input()` blocking calls — one for passkey dismissal (line 89), one for OTP/MFA (line 115). The bot fully halts and will miss item availability during these pauses. There is no timeout; the loop waits indefinitely.
- Safe modification: Do not remove the `input()` calls without a UI/notification replacement. Any change here must handle the case where sign-in is not required.
- Test coverage: No tests exist for `amz_sign_in`

**CAPTCHA detection halts the entire poll loop:**
- Files: `main.py` (lines 95-98), `amazon_bot.py` (lines 24-27)
- Why fragile: `input()` is called inside the item iteration loop. All other items stop being checked while waiting for manual CAPTCHA solve.
- Safe modification: Extract CAPTCHA handling to a pre-loop step or use a notification + callback rather than blocking `input()`
- Test coverage: No tests for `detect_captcha`

**models.py has no connection pooling or context managers:**
- Files: `models.py`
- Why fragile: Each function opens and closes its own SQLite connection. If a function raises before `conn.close()`, the connection leaks. No `with` statement or context manager is used.
- Safe modification: Use `with sqlite3.connect(DB_PATH) as conn:` pattern for automatic commit/rollback and connection cleanup
- Test coverage: `tests/test_models.py` exists but scope is unknown

**`--disable-web-security` Chrome flag in use:**
- Files: `main.py` (line 62)
- Why fragile: This flag disables same-origin policy in Chrome. It is intended for debugging only and can cause unpredictable behavior on live sites.
- Safe modification: Remove this flag unless a specific cross-origin requirement is confirmed

## Scaling Limits

**Single Chrome driver instance for all retailers:**
- Current capacity: One browser window handles all items sequentially
- Limit: Cannot parallelize retailer checks; adding more items linearly increases loop duration
- Scaling path: Instantiate one driver per retailer or per item using threading

**SQLite for persistence:**
- Current capacity: Adequate for small item lists (< 1000 rows)
- Limit: SQLite has write serialization limitations; not suitable if concurrency is added
- Scaling path: Migrate to PostgreSQL or another RDBMS if threading is introduced

## Dependencies at Risk

**webdriver_manager (inconsistent naming in requirements.txt):**
- Risk: Listed as both `webdriver-manager` (line 3) and `webdriver_manager` (line 11). These resolve to the same package but the inconsistency suggests the file is not maintained carefully.
- Impact: pip install may warn or install redundantly
- Migration plan: Remove duplicate, standardize to `webdriver-manager`

**No pinned versions in requirements.txt:**
- Risk: All dependencies use unpinned (latest) versions. A breaking change in `selenium`, `pyyaml`, or `pygame` will break the bot on next install with no warning.
- Impact: Reproducibility is zero; CI and new installs may break at any time
- Migration plan: Pin to exact versions using `pip freeze > requirements.txt` after validating a working install

## Missing Critical Features

**No headless mode:**
- Problem: Bot requires a visible display to run
- Blocks: Server deployment, unattended background execution, Docker containerization

**No async or multi-threaded item checking:**
- Problem: All checks are sequential and blocking
- Blocks: Timely detection when monitoring more than 2-3 items; any retailer slowdown cascades to all items

**No notification channel beyond sound alerts:**
- Problem: `play_notification_sound()` and `play_available_sound()` require audio output. No push notification, email, SMS, or webhook is implemented.
- Blocks: Remote/server operation where audio output is unavailable

## Test Coverage Gaps

**No tests for amazon_bot.py:**
- What's not tested: `detect_captcha`, `check_amazon_item`, `amz_sign_in`, `auto_buy_amazon_item`
- Files: `amazon_bot.py` — no corresponding test file exists
- Risk: Core purchase logic is entirely untested; regressions in DOM selectors will go undetected
- Priority: High

**No tests for bestbuy_bot.py:**
- What's not tested: `check_bestbuy_item`, `bb_sign_in`, `auto_buy_bestbuy_item`
- Files: `bestbuy_bot.py` — no corresponding test file exists
- Risk: BestBuy auto-buy bugs (wrong quantity selector, missing purchased update) have no safety net
- Priority: High

**No tests for logger.py:**
- What's not tested: `writeLog` behavior at each log level, file write behavior, config reload side effects
- Files: `logger.py` — no corresponding test file exists
- Risk: Performance regression (e.g., config reload frequency) cannot be caught by CI
- Priority: Medium

**No tests for main.py loop logic:**
- What's not tested: Item routing (amazon vs bestbuy vs unsupported), purchased item skip, test_mode flag behavior
- Files: `main.py` — no corresponding test file exists
- Risk: Behavioral changes to the main loop are unverifiable without manual runs
- Priority: High

**No integration or end-to-end tests:**
- What's not tested: Full flow from item config → availability check → purchase attempt
- Files: `tests/` directory contains only unit stubs
- Risk: Component interaction bugs (e.g., config shadow in main, purchased state not set for BestBuy) are invisible to the test suite
- Priority: High

---

*Concerns audit: 2026-04-19*
