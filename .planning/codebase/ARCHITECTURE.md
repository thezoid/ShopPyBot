# Architecture

**Analysis Date:** 2026-04-19

## Pattern Overview

**Overall:** Single-process, sequential polling loop with domain-based routing

**Key Characteristics:**
- One shared Selenium ChromeDriver instance for the full lifetime of the process
- Blocking `while True` loop in `main.py` iterates all items on every cycle
- Domain string-match dispatch (`amazon.com` vs `bestbuy.com`) selects the handler module
- Config-seeded SQLite database tracks purchased state to prevent re-buys
- No concurrency — all item checks run serially in insertion order

## Layers

**Orchestrator:**
- Purpose: Bootstrap, driver lifecycle, item polling loop, domain routing
- Location: `main.py`
- Contains: `main()`, `get_chromedriver_path()`, `make_tiny()`, `load_config()`
- Depends on: all bot modules, `models`, `config`, `logger`, `utils`
- Used by: process entry point (`__main__`)

**Bot Modules:**
- Purpose: Retailer-specific availability check and purchase automation
- Location: `amazon_bot.py`, `bestbuy_bot.py`
- Contains: `check_*_item()`, `*_sign_in()`, `auto_buy_*_item()`, `detect_captcha()`
- Depends on: `logger`, `models` (for `update_item_purchased`), `utils`
- Used by: `main.py` loop

**Persistence Layer:**
- Purpose: SQLite CRUD for item tracking
- Location: `models.py`
- Database file: `data/shop_py_bot.db`
- Contains: `initialize_db()`, `add_items()`, `get_items()`, `update_item_purchased()`
- Depends on: `sqlite3` stdlib only
- Used by: `main.py` (read), `amazon_bot.py` (write after purchase)

**Configuration:**
- Purpose: Singleton YAML config loaded at import time
- Location: `config.py`
- Contains: `config` module-level dict (loaded once via `load_config()`)
- Depends on: `config.yml` present in the working directory
- Used by: `main.py`, `amazon_bot.py`, `logger.py`

**Logger:**
- Purpose: Leveled, colorized console output with daily rotating file output
- Location: `logger.py`
- Contains: `writeLog(message, type, writeToFile)`, `setup_logger()`
- Depends on: `colorama`, `config.yml` (re-reads on every call for log level)
- Used by: all modules

**Utilities:**
- Purpose: Audio alert playback
- Location: `utils.py`
- Contains: `play_sound()`, `play_notification_sound()`, `play_buy_sound()`, `play_available_sound()`
- Depends on: `pygame`, `sounds/` directory
- Used by: `main.py`, `amazon_bot.py`

## Data Flow

**Startup sequence:**

1. `main()` calls `load_config()` to read `config.yml`
2. `get_chromedriver_path()` resolves or downloads the ChromeDriver binary
3. Single `webdriver.Chrome` instance is created with anti-detection options
4. `initialize_db()` creates `data/shop_py_bot.db` if absent
5. `add_items()` seeds items from `config['available']['items']` — skips duplicates by `link` uniqueness constraint

**Per-cycle item check:**

1. `get_items()` fetches all rows from SQLite
2. For each item: skip if `purchased == True`
3. Domain match on `link` → dispatch to `check_amazon_item()` or `check_bestbuy_item()`
4. Amazon: navigate driver to URL, detect CAPTCHA (blocks on `input()` if found), check for `#add-to-cart-button` or `#buy-now-button`
5. BestBuy: navigate driver to URL, check for `.add-to-cart-button`
6. On availability: play sound, shorten URL via TinyURL API, log success
7. If `auto_buy == True`: call `auto_buy_*_item()` → sign in → set quantity → submit order → `update_item_purchased(link)`
8. If `auto_buy == False` and `open_browser == True`: open system browser to item URL

**Purchase flag write path:**

- Amazon: `update_item_purchased(item_url)` called inside `auto_buy_amazon_item()` after order confirm button click
- BestBuy: `update_item_purchased` is NOT called after BestBuy purchase (gap — see CONCERNS.md)

## Key Abstractions

**Item tuple:**
- Representation: `(name, link, auto_buy, quantity, purchased)` — unnamed tuple returned by `get_items()`
- Pattern: positional destructuring in `main.py` loop
- No dataclass or namedtuple wrapper

**Config dict:**
- Structure: nested YAML dict accessed by string key (`config['app']['amz_email']`)
- Loaded twice independently: once as module singleton in `config.py`, once via `load_config()` inside `main()` — both read the same file

## Entry Points

**Process entry:**
- Location: `main.py` lines 138–140
- Triggers: `python main.py`
- Responsibilities: instantiate logger, call `main()`

**`main()` function:**
- Location: `main.py` line 42
- Triggers: called by `__main__` block
- Responsibilities: full lifecycle — config, driver, DB seed, polling loop

## Error Handling

**Strategy:** Broad `except Exception as e` catch-and-log at each Selenium interaction boundary. Failures are logged and the item is skipped for the current cycle; the loop continues.

**Patterns:**
- Availability check failure returns `False` (item treated as unavailable)
- Auto-buy step failures return early without marking item purchased
- CAPTCHA detected: blocks process on `input()` prompt — requires human intervention
- MFA detected (Amazon): blocks on `input()` prompt

## Cross-Cutting Concerns

**Logging:** `writeLog()` in `logger.py` — re-reads `config.yml` on every call to determine log level. Color output via `colorama`. Daily log file in `logs/YYYY<Month>DD.log`.

**Validation:** No input validation beyond YAML parse. Item fields are trusted as-is from config.

**Authentication:** Credentials stored in `config.yml` (plaintext). Sign-in is performed lazily inside `auto_buy_*_item()` only when a purchase attempt is triggered.

---

*Architecture analysis: 2026-04-19*
