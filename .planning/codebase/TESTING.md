# Testing Patterns

**Analysis Date:** 2026-04-19

## Test Framework

**Runner:**
- pytest (no pinned version in `requirements.txt`)
- Config: no `pytest.ini`, `pyproject.toml [tool.pytest]`, or `setup.cfg` — pytest runs with zero configuration
- Config file: none (bare `pytest` invocation in CI)

**Assertion Library:**
- pytest built-in `assert` statements only (no `unittest.TestCase`, no `assertpy`)

**Run Commands:**
```bash
pytest                  # Run all tests
pytest tests/           # Run tests directory explicitly
pytest -v               # Verbose output
pytest --tb=short       # Short traceback on failure
```

No coverage command is wired up in CI or locally.

## Test File Organization

**Location:** All test files in `tests/` directory at project root. Not co-located with source modules.

**Naming:**
- Files: `test_{module_name}.py` — e.g., `test_models.py` mirrors `models.py`
- Functions: `test_{what_is_verified}` — e.g., `test_add_items`, `test_update_item_purchased`, `test_load_config`, `test_make_tiny`

**Structure:**
```
tests/
├── __init__.py         # Empty file (zero bytes)
├── test_config.py      # Tests for config.py → load_config()
├── test_models.py      # Tests for models.py → initialize_db, add_items, get_items, update_item_purchased
└── test_utils.py       # Tests for utils.py → make_tiny()
```

**Not tested (zero coverage):**
- `amazon_bot.py` — all Selenium bot logic
- `bestbuy_bot.py` — all Selenium bot logic
- `logger.py` — writeLog function and all logging levels
- `main.py` — orchestration loop, get_chromedriver_path, make_tiny (duplicate defined here)

## Test Structure

**Suite Organization:**
```python
# Module-scoped fixture for shared setup/teardown (test_models.py)
@pytest.fixture(scope='module')
def setup_db():
    initialize_db(delete=True)
    items = [...]
    add_items(items)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_add_items(setup_db):
    items = get_items()
    assert len(items) == 2
    assert items[0][1] == "https://example.com/item1"

# Function-scoped fixture using tmp_path (test_config.py)
@pytest.fixture
def sample_config(tmp_path):
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content)
    return config_file

def test_load_config(sample_config):
    config = load_config(sample_config)
    assert config['app']['amz_email'] == "your_amazon_email@example.com"

# No fixture — direct call (test_utils.py)
def test_make_tiny():
    long_url = "https://www.example.com"
    short_url = make_tiny(long_url)
    assert short_url.startswith("http://tinyurl.com/")
```

**Patterns:**
- Fixtures handle setup and teardown via `yield`
- Teardown cleans up filesystem artifacts (removes SQLite DB file)
- Assertions use plain `assert` with direct value comparison
- No `pytest.raises` for exception testing present yet

## Mocking

**Framework:** None currently in use. No `unittest.mock`, `pytest-mock`, or `responses` library.

**Current approach:** Tests rely on real I/O:
- `test_models.py` creates an actual SQLite database file in `data/shop_py_bot.db` during test run
- `test_utils.py` makes a live HTTP request to `http://tinyurl.com/api-create.php`
- `test_config.py` writes a real YAML file via `tmp_path`

**What to mock when adding new tests:**
- `writeLog` — prevents config.yml read side-effect during unit tests; patch with `unittest.mock.patch('logger.writeLog')`
- `selenium.webdriver` — any bot function test must mock the driver to avoid requiring a real browser
- `requests.get` in `utils.make_tiny` — mock to avoid network calls in CI
- File system operations in `logger.writeLog` — mock `open` or redirect to `tmp_path`

**What NOT to mock:**
- SQLite operations in `test_models.py` — the real DB test is fast and validates actual SQL behavior
- `load_config` in `test_config.py` — the fixture provides a real temp file, which is the correct approach

## Fixtures and Factories

**Test Data:**

```python
# Inline tuple list (test_models.py pattern)
items = [
    ("Item 1", "https://example.com/item1", True, 1, False),
    ("Item 2", "https://example.com/item2", False, 2, False)
]

# Inline YAML string (test_config.py pattern)
config_content = """
app:
  amz_email: "your_amazon_email@example.com"
  ...
"""
```

**Location:** Test data is defined inline within fixtures. No separate fixtures file or `conftest.py` exists.

**`conftest.py`:** Not present. Shared fixtures should be added to `tests/conftest.py` when multiple test files need the same setup.

## Coverage

**Requirements:** None enforced. No `--cov` flag, no coverage threshold, no `.coveragerc`.

**Current coverage (estimated):**
- `models.py`: ~80% (4 of 4 public functions exercised, no error path tests)
- `config.py`: ~50% (happy path only, no missing-file or malformed-YAML tests)
- `utils.py`: ~25% (only `make_tiny` tested; `play_sound`, `play_notification_sound`, etc. untested)
- `amazon_bot.py`: 0%
- `bestbuy_bot.py`: 0%
- `logger.py`: 0%
- `main.py`: 0%

**View Coverage:**
```bash
pip install pytest-cov
pytest --cov=. --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- All current tests are unit-level: isolated module functions with controlled inputs
- Scope: individual DB operations, config loading, URL shortening

**Integration Tests:**
- `test_utils.py::test_make_tiny` is effectively an integration test — it hits the live TinyURL API
- No true integration tests for the bot-to-browser flow exist

**E2E Tests:**
- Not implemented. Selenium bot flows have no automated test coverage.
- Browser automation tests would require a headless Chrome environment and mock product pages or a local HTTP server.

## CI Integration

**Platforms tested:** Windows, Linux, macOS (three separate workflow files, identical steps)

**Workflow files:**
- `.github/workflows/app_windowsBuild.yml`
- `.github/workflows/app_linuxBuild.yml`
- `.github/workflows/app_macBuild.yml`

**CI sequence per platform:**
1. Checkout repository
2. Setup Python 3.9
3. Install `flake8`, `pytest`, then `requirements.txt`
4. Run flake8 (hard-fail on syntax/undefined-name errors only; all other violations are warnings)
5. Run `pytest` (bare, no flags)

**Triggers:** `push` and `pull_request` to `master` and `dev` branches.

**Security scanning:** CodeQL analysis runs on push/PR to `master`/`dev` and on a weekly schedule (Fridays at 05:23 UTC). Config: `.github/workflows/codeql-analysis.yml`.

**Known CI issues:**
- `test_utils.py::test_make_tiny` will fail in CI if TinyURL is unreachable — no retry or mock in place
- No `data/` directory is pre-created in CI; `initialize_db` in `test_models.py` creates `data/shop_py_bot.db` — this works only if the `data/` directory exists or `sqlite3.connect` creates it implicitly (it does not create parent dirs). This is a latent failure risk on clean CI runners.

## Common Patterns

**Async Testing:**
Not applicable — codebase is synchronous.

**Error Testing:**
Not currently practiced. Pattern to adopt:
```python
def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yml")
```

**Database Cleanup:**
```python
@pytest.fixture(scope='module')
def setup_db():
    initialize_db(delete=True)
    # ... setup ...
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
```

**Temp File Fixtures:**
```python
@pytest.fixture
def sample_config(tmp_path):
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content)
    return config_file
```

---

*Testing analysis: 2026-04-19*
