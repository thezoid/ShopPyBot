# Coding Conventions

**Analysis Date:** 2026-04-19

## Naming Patterns

**Files:**
- Flat snake_case module names: `amazon_bot.py`, `bestbuy_bot.py`, `logger.py`, `utils.py`, `models.py`, `config.py`, `main.py`
- No sub-packages; all modules live at the project root
- Test files mirror module names: `tests/test_models.py`, `tests/test_config.py`, `tests/test_utils.py`

**Functions:**
- snake_case throughout: `check_amazon_item`, `auto_buy_amazon_item`, `initialize_db`, `add_items`, `get_items`, `update_item_purchased`, `play_sound`, `load_config`
- Verb-first naming: `check_`, `auto_buy_`, `initialize_`, `add_`, `get_`, `update_`, `play_`, `load_`, `detect_`
- Exception: `writeLog` uses camelCase (legacy inconsistency — new logging calls must use this name as-is since it is the single logging entry point)

**Variables:**
- snake_case for locals and module-level: `driver_path`, `add_to_cart_button`, `quantity_dropdown`, `short_url`, `log_dir`
- camelCase appears in a few local vars inside `main.py` (`chromeOptions`) — avoid repeating this pattern

**Constants:**
- UPPER_SNAKE_CASE: `DB_PATH` in `models.py`, `SOUNDS_DIR` in `utils.py`

**Parameters:**
- Descriptive snake_case: `item_url`, `write_to_file`, `test_mode`

## Code Style

**Formatting:**
- No formatter config file present (no `.prettierrc`, `pyproject.toml` formatter section, or `black` config)
- Max line length: 127 characters (enforced by flake8 in CI — see `.github/workflows/`)
- Indentation: 4 spaces (standard Python); `main.py` uses 5-space indent in `main()` — inconsistency, do not repeat

**Linting:**
- Tool: `flake8` (run in CI only, no local config file)
- Hard-fail rules: `E9` (syntax errors), `F63` (invalid `*` usage), `F7` (syntax errors), `F82` (undefined names)
- Soft-warn rules: all others with `--exit-zero --max-complexity=10 --max-line-length=127`
- No `setup.cfg`, `.flake8`, or `tox.ini` — flake8 flags are defined only in workflow YAML files

## Import Organization

**Order (observed pattern):**
1. Standard library (`os`, `sys`, `sqlite3`, `time`, `datetime`)
2. Third-party (`selenium`, `yaml`, `pygame`, `colorama`, `requests`)
3. Local modules (`from logger import writeLog`, `from models import ...`, `from config import config`)

**No path aliases** — all local imports are bare module names relative to project root.

**Duplicate imports present in `requirements.txt`** (`selenium` and `pyyaml` each listed twice) — do not add further duplicates.

## Error Handling

**Patterns:**
- All Selenium interactions wrapped in `try/except Exception as e`
- On failure: call `writeLog(f"Error ...: {e}", "ERROR")` then `return` (or `return False`)
- Bare `except:` blocks used in two places in `amazon_bot.py` (`detect_captcha`, `amz_sign_in`) — new code must use `except Exception as e` instead
- Do not silently swallow exceptions; always log before returning

**Example (correct pattern):**
```python
try:
    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "some-id"))
    )
except Exception as e:
    writeLog(f"Error finding element: {e}", "ERROR")
    return False
```

## Logging

**Entry point:** `writeLog(message: str, type: str, writeTofile: bool = True)` defined in `logger.py`

**Log levels (numeric priority, lower = more important):**
| Type | Color | Level |
|------|-------|-------|
| ALWAYS | Cyan | 0 |
| ERROR | Red | 1 |
| WARNING | Yellow | 2 |
| SUCCESS | Green | 2 |
| INFO | White | 3 |
| DEBUG | Blue | 4 |
| TRACE | Magenta | 5 |

**Usage rules:**
- Use `"DEBUG"` at function entry: `writeLog(f"Entering {function_name} for ...", "DEBUG")`
- Use `"INFO"` for routine status updates during a flow
- Use `"SUCCESS"` only on confirmed positive outcomes (item available, order placed)
- Use `"WARNING"` for recoverable issues (CAPTCHA detected, element not found but execution continues)
- Use `"ERROR"` in every `except` block before returning
- Never call `print()` directly for application output — use `writeLog`
- `writeTofile=True` by default; only pass `False` when file output is explicitly undesirable

**Level controlled by:** `config.yml` → `debug.logging_level` (integer 0–5). `writeLog` reads config on every call (no caching — performance concern, see CONCERNS.md).

## Comments

**When to comment:**
- Inline comments explain non-obvious intent: `# stop the build if there are Python syntax errors or undefined names`
- Short inline notes for multi-step Selenium flows: `# Check if the user is already signed in`
- No docstrings present anywhere in the codebase — add docstrings to new public functions

**Style:**
- `# Comment` with a space after `#`
- Comments describe intent ("why"), not mechanics ("what")

## Function Design

**Size:** Most functions are 10–30 lines. `auto_buy_amazon_item` at ~70 lines is the longest and is a known concern.

**Parameters:** Positional only; no keyword-only args or dataclass inputs. Config dict passed whole (`config`) rather than extracting only needed values.

**Return values:**
- Boolean functions return `True`/`False` explicitly (`check_amazon_item`, `check_bestbuy_item`, `detect_captcha`)
- Void functions return `None` implicitly or via bare `return` after error
- No use of exceptions for control flow — callers check return values

## Module Design

**Exports:** No `__all__` defined in any module. Everything is importable by name.

**Barrel files:** No `__init__.py` at root; `tests/__init__.py` is empty (zero bytes).

**Module-level side effects:**
- `config.py` calls `load_config()` at import time — config is loaded as a module-level singleton (`config = load_config()`)
- `utils.py` calls `initialize_pygame()` at import time
- Both patterns mean importing these modules has side effects; avoid adding more module-level execution

---

*Convention analysis: 2026-04-19*
