# Technology Stack

**Analysis Date:** 2026-04-19

## Languages

**Primary:**
- Python 3.8+ - All application logic, bot orchestration, data access

## Runtime

**Environment:**
- Python (CPython) 3.8+
- No `.python-version` file present; minimum version implied by f-string and walrus-operator usage patterns

**Package Manager:**
- pip
- Lockfile: Not present (requirements.txt lists packages without pinned versions)

## Frameworks

**Core:**
- None (plain Python scripts, no web framework)

**Testing:**
- pytest - Unit test runner; config: none (default discovery); tests in `tests/`

**Build/Dev:**
- None; run directly via `python main.py`

## Key Dependencies

**Browser Automation:**
- selenium (unpinned) - DOM interaction, element waits, form submission for Amazon and BestBuy
- webdriver-manager / webdriver_manager (listed twice in requirements.txt) - Auto-downloads compatible ChromeDriver; used in `main.py` via `ChromeDriverManager().install()`

**Configuration:**
- pyyaml (unpinned) - Parses `config.yml`; loaded at import time in `config.py` and on every `writeLog` call in `logger.py`

**Audio:**
- pygame (unpinned) - `pygame.mixer` plays `.mp3`/`.wav` notification sounds from `sounds/`

**HTTP:**
- requests (unpinned) - TinyURL shortener API call in `main.py:make_tiny()`
- urllib3 (unpinned) - Listed as dependency; used transitively by requests

**Logging/Output:**
- colorama (unpinned) - ANSI color codes in `logger.py:writeLog()` for terminal output

**Data Storage:**
- sqlite3 (stdlib) - Embedded database; no ORM; raw SQL in `models.py`

## Configuration

**Environment:**
- No environment variables used; all secrets stored in `config.yml` (plaintext)
- Required config file: `config.yml` (must exist at working directory; copied from `sample.config.yml`)

**Key config sections:**
- `selenium.driver_path` - Path to local ChromeDriver binary
- `app.amz_email`, `app.amz_pwd` - Amazon credentials
- `app.bb_email`, `app.bb_password`, `app.bb_cvv` - BestBuy credentials
- `app.open_browser` - Whether to open system browser on availability
- `debug.logging_level` - Integer 0-5 controlling log verbosity
- `debug.test_mode` - Boolean; skips final purchase click when true
- `available.items` - List of items to monitor (name, link, auto_buy, quantity)

**Build:**
- No build step; no Makefile, no setup.py, no pyproject.toml

## Platform Requirements

**Development:**
- Python 3.8+
- Google Chrome browser installed (ChromeDriver targets installed Chrome version)
- Audio output capable system (pygame mixer requires audio device)

**Production:**
- Same as development; intended to run as a foreground process on a desktop/server with Chrome installed
- SQLite database file written to `data/shop_py_bot.db` (directory must exist or be created at runtime)
- Log files written to `logs/` directory (auto-created by logger)

---

*Stack analysis: 2026-04-19*
