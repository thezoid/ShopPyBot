# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```sh
# Setup
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate      # macOS/Linux
pip install -r requirements.txt

# Run
python main.py

# Tests
pytest                         # all tests
pytest tests/test_models.py    # single file
pytest tests/test_models.py::test_add_items  # single test
```

## Architecture

Single-process bot with a blocking `while True` loop in `main.py`. One shared Selenium ChromeDriver instance navigates all items sequentially.

**Flow:**
1. `main.py` loads `config.yml`, initializes ChromeDriver, seeds SQLite DB from config items
2. Loop iterates `get_items()` from DB, routes by URL domain to Amazon or BestBuy checker
3. On availability: plays sound, optionally calls auto-buy, marks purchased in DB via `update_item_purchased()`

**Module responsibilities:**
- `config.py` — singleton `config` dict loaded from `config.yml` at import time
- `models.py` — SQLite CRUD for items tracking (`data/shop_py_bot.db`); `purchased` flag prevents re-buying
- `logger.py` — custom `writeLog(message, type)` with colorama colors + file output to `logs/YYYYMONTHDD.log`; verbosity controlled by `debug.logging_level` (0–5) in config
- `amazon_bot.py` — `check_amazon_item()` (DOM button presence), `amz_sign_in()` (manual OTP step required), `auto_buy_amazon_item()`
- `bestbuy_bot.py` — `check_bestbuy_item()`, `bb_sign_in()`, `auto_buy_bestbuy_item()`
- `utils.py` — pygame sound playback; looks for `sounds/{name}.mp3` then `.wav`

## Config

`config.yml` (gitignored) drives all behavior. Copy from `sample.config.yml`.

Key fields:
- `selenium.driver_path` — path to chromedriver; auto-downloads via webdriver_manager if missing
- `debug.test_mode: true` — skips final purchase click (safe for testing)
- `debug.logging_level` — 0=ALWAYS only, 5=TRACE (default 5)
- `available.items[]` — each item needs `name`, `link`, `auto_buy`, `quantity`
- `app.open_browser` — opens system browser when item found but `auto_buy` is false

## SQLite DB

Created at `data/shop_py_bot.db` on first run. Items are inserted by URL (unique constraint); already-purchased items are skipped each loop. `initialize_db(delete=True)` wipes and recreates (used in tests).

## Sounds

`sounds/` directory. Three named files: `notification`, `buy`, `available`. Replace `.mp3` files with same-name files (`.mp3` or `.wav`) to change sounds.

## Amazon-specific

Amazon sign-in requires manual passkey dismissal and OTP entry — the bot pauses and prompts via `input()`. CAPTCHA detection pauses the loop and waits for manual solve.
