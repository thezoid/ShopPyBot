# Codebase Structure

**Analysis Date:** 2026-04-19

## Directory Layout

```
ShopPyBot/
├── main.py               # Process entry, polling loop, domain routing
├── amazon_bot.py         # Amazon availability check and purchase automation
├── bestbuy_bot.py        # BestBuy availability check and purchase automation
├── models.py             # SQLite CRUD (items table)
├── config.py             # Singleton YAML config loaded at import
├── logger.py             # Leveled colorized logger with file output
├── utils.py              # Audio alert helpers (pygame)
├── sample.config.yml     # Config template — copy to config.yml
├── config.yml            # Runtime config (gitignored, contains credentials)
├── requirements.txt      # Python dependencies
├── CLAUDE.md             # Project-level Claude instructions
├── readme.md             # Project documentation
├── refactor.md           # Developer notes on planned refactors
├── sounds/               # Audio files for alerts
│   ├── notification.mp3  # Played on CAPTCHA / manual-action prompts
│   ├── available.mp3     # Played when item becomes available
│   └── buy.mp3           # Played after successful purchase
├── data/                 # Runtime data (gitignored)
│   └── shop_py_bot.db    # SQLite database
├── logs/                 # Daily log files (gitignored)
│   └── YYYY<Month>DD.log # One file per day, appended by writeLog()
├── tests/                # Unit test suite
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_models.py
│   └── test_utils.py
└── _deprecated/          # Legacy code, not in active use
    ├── bot.py
    ├── bot-availCheck.py
    ├── installDependencies.ps1
    ├── linkProcessor/
    └── settings.json
```

## Directory Purposes

**Root (source files):**
- Purpose: All active Python source lives flat in the project root — no `src/` subdirectory
- Key files: `main.py`, `amazon_bot.py`, `bestbuy_bot.py`, `models.py`, `config.py`, `logger.py`, `utils.py`

**`sounds/`:**
- Purpose: Static audio assets for user alerts
- Contains: `.mp3` and `.wav` files; `utils.py` tries `.mp3` first, falls back to `.wav`
- Key files: `notification.mp3`, `available.mp3`, `buy.mp3`

**`data/`:**
- Purpose: Runtime SQLite database storage
- Generated: Yes (created by `initialize_db()` on first run)
- Committed: No (gitignored)

**`logs/`:**
- Purpose: Daily append-only log files written by `writeLog()`
- Generated: Yes (created on first log write if absent)
- Committed: No (gitignored)
- Naming: `YYYY<Month>DD.log` (e.g., `2026April19.log`) — uses `strftime('%Y%B%d')`

**`tests/`:**
- Purpose: Unit tests using Python's `unittest`
- Contains: test files for config loading, DB model operations, and utility functions
- Key files: `test_config.py`, `test_models.py`, `test_utils.py`

**`_deprecated/`:**
- Purpose: Archived earlier iterations of the bot — not imported or executed
- Generated: No
- Committed: Yes (historical reference)

## Key File Locations

**Entry Point:**
- `main.py` line 138: `if __name__ == "__main__":` block

**Configuration Template:**
- `sample.config.yml`: source-controlled template; copy to `config.yml` before running

**Database Schema:**
- `models.py` lines 6–22: `initialize_db()` defines the `items` table DDL

**Domain Routing:**
- `main.py` lines 92–136: `if "amazon.com" in link` / `elif "bestbuy.com" in link` dispatch

**Audio Assets:**
- `sounds/`: referenced by `utils.py` via `SOUNDS_DIR = os.path.join(os.path.dirname(__file__), 'sounds')`

## Naming Conventions

**Files:**
- Flat snake_case modules: `amazon_bot.py`, `bestbuy_bot.py`, `models.py`
- Bot modules suffixed `_bot`: signals retailer-specific automation

**Functions:**
- Verb-prefixed snake_case: `check_amazon_item`, `auto_buy_bestbuy_item`, `initialize_db`, `add_items`, `get_items`, `update_item_purchased`
- Sound helpers prefixed `play_`: `play_notification_sound`, `play_buy_sound`, `play_available_sound`

**Variables:**
- snake_case throughout
- Config dict keys use snake_case strings: `amz_email`, `bb_password`, `auto_buy`

**Log level strings:**
- UPPER CASE string literals: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"SUCCESS"`, `"TRACE"`, `"ALWAYS"`

## Where to Add New Code

**New retailer support:**
- Create `<retailer>_bot.py` in the project root following the pattern of `amazon_bot.py`
- Export: `check_<retailer>_item(driver, url)` → `bool`, `auto_buy_<retailer>_item(driver, url, config, quantity, test_mode)` → `None`
- Add domain routing branch in `main.py` lines 92–136 (`elif "<domain>" in link:`)
- No other files require modification

**New config key:**
- Add to `sample.config.yml` with a placeholder value
- Access via `config['section']['key']` anywhere after `from config import config`

**New audio alert:**
- Drop `.mp3` (or `.wav`) into `sounds/`
- Add a `play_<name>_sound()` wrapper in `utils.py` calling `play_sound("<name>")`
- Import and call in the appropriate location in `main.py` or a bot module

**New utility helper:**
- Add to `utils.py` if general-purpose
- Add directly to the relevant `*_bot.py` module if retailer-specific

**New test:**
- Add to `tests/test_<module>.py` following the existing `unittest.TestCase` pattern
- Run with: `python -m pytest tests/` or `python -m unittest discover tests/`

## Special Directories

**`data/`:**
- Purpose: Holds `shop_py_bot.db` SQLite file
- Generated: Yes — `initialize_db()` creates `data/` if absent and creates the DB
- Committed: No

**`logs/`:**
- Purpose: Daily log output from `writeLog()`
- Generated: Yes — created on first write by `logger.py`
- Committed: No

**`_deprecated/`:**
- Purpose: Archived pre-refactor code for historical reference
- Generated: No
- Committed: Yes — do not import or extend anything in this directory

---

*Structure analysis: 2026-04-19*
