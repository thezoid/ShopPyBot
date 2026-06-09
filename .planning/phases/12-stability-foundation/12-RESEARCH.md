# Phase 12: Stability Foundation - Research

**Researched:** 2026-06-09
**Domain:** Python / pytest / cross-OS manual verification
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None — all implementation choices are at Claude's discretion.

### Claude's Discretion
All implementation choices. Use the ROADMAP success criteria, requirements STAB-01 and
STAB-02, the v2.0 milestone audit findings, and existing codebase test conventions to guide
decisions. Hard constraint from success criteria: no broad refactors — change only the
specific items in scope.

### Deferred Ideas (OUT OF SCOPE)
None — infrastructure phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STAB-01 | All 4 deferred v2.0 cross-OS/UI manual checks executed and documented pass/fail, with any failures fixed | Checks fully enumerated in PLATFORMS.md; code paths identified below |
| STAB-02 | The 4 v2.0 audit tech-debt items resolved with a targeted regression test each (no broad refactors) | All 4 items extracted verbatim from v2.0-MILESTONE-AUDIT.md frontmatter; test patterns identified |
</phase_requirements>

## Summary

Phase 12 closes two categories of deferred work left over from the v2.0 milestone.

The first category (STAB-01) is four manual cross-OS checks that cannot run in CI
because they require real hardware: keyring secret surviving a process restart, masked-TTY
input via `getpass`, the web dashboard rendering live in a browser, and the
`0.0.0.0` bind-warning banner. All four are documented in `docs/PLATFORMS.md` with
exact repro steps. On this Windows dev machine only a subset can be verified; the Ubuntu
variants require a second machine or VM. The checks must be documented pass/fail even when
they cannot be automated, with any failures fixed in code.

The second category (STAB-02) is four non-blocking tech-debt items recorded in the
`v2.0-MILESTONE-AUDIT.md` frontmatter under `tech_debt`. Each gets exactly one targeted
regression test: (1) `logger.py:10` `_CONFIG_PATH` still points at the repo-root
`config.yml`, not `core.paths.config_path()`, so a migrated install silently ignores its
`logging_level` setting; (2) the SC1 grep guard in `test_no_env_secret_reads.py` scans
`core/*.py` with `glob("*.py")` and misses `core/cli/*.py`; (3) the separator guard in
`test_paths.py` scans only CWD-relative `Path("core")`, breaking for non-root runs;
(4) `web/routes/credentials.py` and `web/config_web.py` write secrets/config directly
via `get_store()` / `_DEFAULT_YAML_PATH` rather than through a `BotService` API, which
is within the letter of MOD-02 but leaves BotService as not the single write seam.

**Primary recommendation:** Implement four targeted regression tests (one per tech-debt
item) and document all four manual checks. Fix any manual checks that fail. No refactoring
beyond what each specific item requires.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tech-debt regression tests | Test layer | — | Pure pytest additions; no production code change unless a fix is needed |
| logger _CONFIG_PATH fix | Core module (logger.py) | — | `logger.py` is a top-level module; change is one line |
| SC1 guard coverage fix | Test layer (test_no_env_secret_reads.py) | — | Guard is a test-only artifact; fix the glob pattern |
| test_paths separator guard fix | Test layer (test_paths.py) | — | Fix the Path construction from CWD-relative to `__file__`-anchored |
| Web write-seam documentation | Documentation / test | — | Debt item accepted within MOD-02 letter; regression test documents the accepted gap |
| Manual check execution | Human/dev environment | CI (automated subset) | Requires real hardware for Ubuntu and restart survival checks |

## The 4 v2.0 Audit Tech-Debt Items (STAB-02)

Source: `.planning/milestones/v2.0-MILESTONE-AUDIT.md` frontmatter `tech_debt[0].items`,
verified by reading the file directly. [VERIFIED: codebase grep]

### TD-1: logger.py `_CONFIG_PATH` not re-anchored to `core.paths.config_path()`

**File:** `logger.py:10`
**Exact quote from audit:** "logger.py:10 _CONFIG_PATH still repo-root-relative, not
core.paths.config_path(); after migration the migrated config.yml's logging_level has no
effect (accepted out-of-scope per Phase 11-02). XPLAT-01 partial."

**What the code does now:**
```python
# logger.py:10
_CONFIG_PATH: Path = Path(__file__).parent / "config.yml"
```
This resolves to the repo root `config.yml`. After `migrate_legacy_paths()` runs, the user's
`config.yml` moves to `%LOCALAPPDATA%\shoppybot\config.yml` (Windows) or
`~/.local/share/shoppybot/config.yml` (Ubuntu). The repo-root file is gone; `_load_logging_level()`
catches `FileNotFoundError` and silently defaults to level 5, ignoring the migrated config.

**Fix:** Change `_CONFIG_PATH` to use `core.paths.config_path()` at call time (not at
import time, to avoid circular import during test collection). The simplest safe approach:
make `_load_logging_level()` call `core.paths.config_path()` lazily inside the function.

**Regression test target:** A test that monkeypatches `SHOPBOT_DATA_DIR` to a temp dir
containing a `config.yml` with a specific `logging_level`, then imports/reloads `logger`
and asserts `_LOGGING_LEVEL` equals the configured value (not the default 5).

**Caution:** `_LOGGING_LEVEL` is cached at import time (`logger.py:20`). The test must
reload the module after setting the env override, or call `_load_logging_level()` directly.
The existing `test_logger.py::test_no_config_reread` test confirms the cache-at-import
invariant must be preserved.

### TD-2: SC1 guard scans `core/*.py` non-recursively — `core/cli/*.py` not covered

**File:** `tests/test_no_env_secret_reads.py:45`
**Exact quote from audit:** "tests/test_no_env_secret_reads.py:45 SC1 guard scans core/
non-recursively (glob('*.py')) — core/cli/*.py not covered. No active violation; coverage
gap only. CRED-01."

**What the code does now:**
```python
# test_no_env_secret_reads.py:45
for py_file in sorted(scan_dir.glob("*.py")):
```
`glob("*.py")` on a directory does not recurse into subdirectories. `core/cli/` has five
files (`__init__.py`, `config_cmd.py`, `items.py`, `run.py`, `setup.py`, `web.py`) that
are not scanned. If a future commit adds a raw `os.environ` read to any of them, the guard
will not catch it.

**Fix:** Change `scan_dir.glob("*.py")` to `scan_dir.rglob("*.py")` for the `core/`
directory entry. The other directories (`plugins/`, `notifications/`) have no subdirectories
currently, but switching all three to `rglob` is safe and future-proofs them.

**Regression test:** The fix IS the regression test — the modified guard test itself proves
the coverage gap is closed. A companion test should verify the guard actually catches a
violation planted in a `core/cli/` file (or assert that a known-clean `core/cli/setup.py`
is included in the scan). The simplest verifiable regression test: assert that
`core/cli/config_cmd.py` appears in the set of files scanned by the guard.

### TD-3: `test_paths.py` separator guard uses CWD-relative `Path("core")`

**File:** `tests/test_paths.py:58`
**Exact quote from audit:** "tests/test_paths.py separator guard checks only 'data/'/'logs/'
string patterns, not backslash literals or os.sep; uses CWD-relative Path('core').
Fragile for local non-root runs."

**What the code does now:**
```python
# test_paths.py:58
src_files = list(Path("core").rglob("*.py")) + [
    Path("logger.py"),
    Path("models.py"),
    Path("utils.py"),
]
```
`Path("core")` resolves relative to the process CWD, which is the repo root when pytest
runs normally. But if pytest is invoked from a subdirectory (e.g., `cd tests && pytest`),
`Path("core")` resolves to `tests/core/` which does not exist, yielding an empty list —
the guard silently passes with zero files checked.

**Fix:** Anchor with `Path(__file__).parent.parent / "core"` (and similarly for the
other three top-level files). This makes the guard repo-root-absolute regardless of CWD.

**Regression test:** The fix IS the regression test — the hardened test itself verifies
the guard runs correctly. A companion assertion should check `len(src_files) > 0` and
that a known file (e.g., `core/paths.py`) is included in the scan list. This proves the
list is never silently empty.

### TD-4: Web credential/config write paths bypass BotService (accepted design gap)

**Files:** `web/routes/credentials.py`, `web/config_web.py`
**Exact quote from audit:** "web/routes/credentials.py + web/config_web.py write
secrets/config via get_store()/_DEFAULT_YAML_PATH directly rather than through BotService
(BotService exposes no credential/config write API). Within letter of MOD-02 (not
DB/registry/orchestrator), but BotService is not the single write seam for these."

**What the code does now:**
- `web/routes/credentials.py:49`: `_creds.get_store().set(key, value)` — direct
- `web/config_web.py:72`: `_DEFAULT_YAML_PATH.read_text(...)` and `_atomic_yaml_write(...)` — direct

BotService has no `set_credential()` or `write_config()` methods. The audit accepted this
as within the letter of MOD-02, which scopes BotService to DB/registry/orchestrator
operations, not arbitrary config/credential writes.

**Fix approach for Phase 12:** Do NOT add a BotService write API (that would be a
refactor beyond scope). Instead, add a regression test that asserts the write paths work
correctly as-is, and document the accepted gap with a code comment referencing the
v2.0 audit decision. This satisfies STAB-02 ("resolved with a targeted regression test")
without violating the no-broad-refactors constraint.

**Regression test:** A test asserting that `POST /api/credentials` with a valid key/value
calls `get_store().set(key, value)` and returns `{"status": "ok"}`. This can be a small
addition to `tests/test_web_credentials.py` (check if it already covers `set_credential`)
or a standalone test. Similarly, assert `write_web_config` writes to `_DEFAULT_YAML_PATH`
atomically for a known allowlist key. The test documents the accepted design gap.

## The 4 Deferred Manual Checks (STAB-01)

Source: `docs/PLATFORMS.md` "Phase 8/9/10 Deferred Live Checks" sections, and
`.planning/STATE.md` "Deferred Items" table. [VERIFIED: codebase read]

### MC-1: Keyring secret survives process restart (Phase 8 deferred)

**Code path:** `core/credentials.py` `KeyringBackend.set()` / `KeyringBackend.get()` /
`_build_store()` auto-detection. Relevant env: Windows Credential Manager (this dev
machine) or GNOME Keyring (Ubuntu desktop).

**Repro steps (from PLATFORMS.md):**
1. `shoppybot setup` — complete credential entry with keyring backend.
2. Exit process completely.
3. Unset all credential env vars (`$env:BB_EMAIL`, etc.).
4. `shoppybot config show` or `shoppybot items list` — must not prompt for credentials.

**Can this be automated?** No. Restart survival is inherently cross-process. CI uses
`PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` which disables the real keyring.
This must be a manual check.

**Platform scope on this machine:** Windows only (keyring backend). Ubuntu headless
variant (encrypted-file + `SHOPBOT_STORE_PASSPHRASE` restart check) requires a second
machine or VM.

**Expected outcomes to document:**
- Windows: keyring stores secret; retrieved without env var after restart. Pass/Fail.
- Ubuntu headless: encrypted-file backend; secret retrieved after restart with passphrase
  env var set. Pass/Fail (requires Ubuntu machine).

### MC-2: Masked-TTY setup entry (Phase 9 deferred)

**Code path:** `core/cli/setup.py:_prompt_secret()` which calls `getpass.getpass()`.
`getpass` suppresses echo on real TTYs. On Windows PowerShell it works natively; on
Ubuntu it uses termios. The test suite mocks `getpass.getpass` so CI never exercises
the real TTY path.

**Repro steps (from PLATFORMS.md):**
1. Open a fresh terminal (PowerShell on Windows; bash on Ubuntu).
2. `shoppybot setup`.
3. At each credential prompt: type a value and verify no characters are echoed.
4. At confirmation prompt: verify only the key name is shown, not the entered value.

**Can this be automated?** The no-echo behavior requires a real TTY — automated tests
use `getpass.GetPassWarning` or mock `stdin`. The existing `test_cli_setup.py` covers
the mock path. This check confirms the live TTY path on real terminals.

**Platform scope on this machine:** Windows PowerShell (directly runnable). Ubuntu
variants require a second machine.

### MC-3: Web dashboard live render, Start/Stop, log polling (Phase 10 deferred)

**Code path:** `shoppybot web` -> `core/cli/web.py:handle_web()` -> uvicorn serves
`web/create_app()` -> dashboard template at `web/templates/dashboard.html`. Log polling
uses a live `GET /api/logs` endpoint (`web/log_reader.py`). Start/Stop uses
`POST /api/controls/start` and `/stop`.

**Repro steps (from PLATFORMS.md):**
1. `shoppybot web` — must start without error.
2. Open `http://localhost:8000` in a browser.
3. Verify: items list section, config section, Start/Stop buttons visible.
4. Click Start Bot / Stop Bot — verify live state change.
5. In a separate terminal run `shoppybot run` — observe log panel updates without page reload.

**Can this be automated?** The FastAPI TestClient covers HTML rendering and section
presence (already done in `test_web_dashboard.py`). The live polling and browser-rendered
Start/Stop require a real browser session — Playwright or manual. Given scope constraint
(no broad changes), manual verification is appropriate here.

**Platform scope on this machine:** Windows (directly runnable). Ubuntu
`shoppybot web` is the same code path; the Ubuntu browser render check requires Ubuntu.

### MC-4: `0.0.0.0` bind warning banner (Phase 10 deferred)

**Code path:** `core/cli/web.py:handle_web()` line 33-39 — when `is_non_local` is True,
a WARNING is printed to stderr. Additionally `app.state.is_non_local = True` is passed
to `create_app()`, which the dashboard template uses to render a warning banner.

**Existing test coverage:** `test_web_security.py::test_non_local_host_warning` already
covers the `WARNING` stderr print. `test_web_security.py::test_non_local_banner_flag`
covers `app.state.is_non_local = True`. The dashboard template rendering the banner
when `is_non_local` is True is covered structurally by `TestClient`.

**Repro steps (from PLATFORMS.md):**
1. `shoppybot web --host 0.0.0.0`
2. Open `http://localhost:8000` in a browser.
3. Verify a warning banner is visible.

**Can this be automated?** Largely yes — the `TestClient` fixture can assert the banner
HTML is present when `is_non_local=True`. The existing `test_web_dashboard.py` does NOT
currently assert the banner text. A targeted regression test can cover this. The live
browser render of the banner on `0.0.0.0` is a manual confirm.

## Existing Test Conventions

Source: direct codebase read. [VERIFIED: codebase read]

### Test infrastructure

- **Framework:** pytest 8.3.4 with `asyncio_mode = "auto"` (no decorators needed for
  `async def test_` functions).
- **Config file:** `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`.
- **Quick run:** `pytest --tb=short -q` (completes in ~20s, 354 passed, 2 skipped baseline).
- **Full suite:** `pytest` (same — no separate full/quick split currently).

### DB setup/teardown

- `conftest.py:tmp_data_dir` fixture: monkeypatches `SHOPBOT_DATA_DIR` env and
  `models.DB_PATH` attribute to a `tmp_path` subdir. Tests call `initialize_db()` explicitly
  when they need a seeded DB.
- `initialize_db(delete=True)` wipes and recreates; `initialize_db()` (default `delete=False`)
  is idempotent (`CREATE TABLE IF NOT EXISTS`).
- The `test_fresh_install.py` pattern (subprocess invocation with a clean temp dir and
  no pre-seeded DB) is the correct approach for entry-point regression tests.

### Mocking keyring

- `conftest.py:isolated_keyring` fixture: swaps OS keyring with `_DictKeyring` (in-memory
  `KeyringBackend` subclass). Skips if keyring not installed.
- `conftest.py:reset_credential_store` fixture: restores `core.credentials._store` singleton
  between tests to prevent bleed.

### Mocking nodriver/browser

- `conftest.py:fake_browser` and `conftest.py:mock_nodriver_start`: patch `nodriver.start`
  to never launch Chrome.

### Module reload pattern (for logger tests)

- `logger._LOGGING_LEVEL` is set at import time. Tests that need a different level must
  either reload the module (using `importlib.reload`) or call `logger._load_logging_level()`
  directly (the helper is module-level and callable).
- Existing pattern in `test_config.py` uses `importlib.reload` + `monkeypatch.chdir`.

### SC1 / guard tests

- Pattern: collect files with `glob`/`rglob`, iterate lines, assert no violations list.
- Tests are self-contained; no fixtures needed.
- Exception sites documented inline with comments.

### Web tests

- `pytest.importorskip("fastapi")` at top of every web test file — skips cleanly if
  fastapi not installed.
- `TestClient` from `fastapi.testclient` wraps `create_app(mock_svc)`.
- `mock_svc` is a `MagicMock()` with explicit `get_status` and `list_items` return values.

## Architecture Patterns

### No new abstractions

All four regression tests are targeted, minimal additions:
- TD-1: add one test to `tests/test_logger.py` (or a new `tests/test_logger_config_path.py`
  if the logger fix requires module reload complexity that would clutter the existing file).
- TD-2: modify `tests/test_no_env_secret_reads.py` — change `glob` to `rglob` and add an
  assertion that `core/cli/*.py` files are in the scanned set.
- TD-3: modify `tests/test_paths.py` — anchor `Path("core")` to `__file__`-relative and
  add a `len(src_files) > 0` guard.
- TD-4: add one or two test cases to `tests/test_web_credentials.py` and/or
  `tests/test_web_config.py` documenting the accepted write-seam design.

### Manual check documentation

The STAB-01 checks are documented in `docs/PLATFORMS.md`. The plan should include tasks to:
1. Execute each check on this Windows machine and record pass/fail inline.
2. For Ubuntu checks that cannot be done on this machine, document "not verified — requires
   Ubuntu" with the check number.
3. Fix any failures found (code change + test if applicable).

### logger fix pattern

Two valid options:

**Option A (minimal):** Change `_load_logging_level` to call `core.paths.config_path()` at
call time rather than using the module-level `_CONFIG_PATH` constant. Import `core.paths`
lazily inside the function (already done for `log_dir` in `writeLog`).

```python
def _load_logging_level() -> int:
    from core.paths import config_path as _config_path
    try:
        with open(_config_path(), 'r') as file:
            ...
```

**Option B (simpler but changes module API):** Delete `_CONFIG_PATH` constant entirely.
Risk: nothing outside `logger.py` imports `_CONFIG_PATH` (it's private), so removal is safe.

Option A is preferred — it keeps `_CONFIG_PATH` for any tooling that inspects it, and the
lazy import pattern is already established in this codebase.

**Important:** `_LOGGING_LEVEL = _load_logging_level()` runs at import time (line 20). After
the fix, the first import of `logger` in any process will call `config_path()`, which reads
`SHOPBOT_DATA_DIR`. This is safe because `migrate_legacy_paths()` runs before any logger
call in `core/service.py:main()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Module reload in tests | Custom reimport machinery | `importlib.reload(logger)` | Standard library, already used elsewhere in the test suite |
| Subprocess invocation for entry-point tests | Custom process manager | `subprocess.run(...)` as in `test_fresh_install.py` | Established pattern; already works |
| TTY masking | Custom echo suppression | `getpass.getpass()` (already in setup.py) | OS-native, cross-platform |

## Common Pitfalls

### Pitfall 1: logger module reload order

**What goes wrong:** Calling `importlib.reload(logger)` after monkeypatching
`SHOPBOT_DATA_DIR` may not produce the expected `_LOGGING_LEVEL` if `core.paths` was
already imported and cached `_env_override()` returned stale data.

**Why it happens:** `core.paths._env_override()` is called fresh on every `data_dir()` /
`config_path()` call (re-reads `os.environ` each time). So as long as the monkeypatch is
applied before the reload, the config path resolves correctly.

**How to avoid:** Apply `monkeypatch.setenv("SHOPBOT_DATA_DIR", ...)` before calling
`importlib.reload(logger)`. Do NOT call `config_path()` before the monkeypatch.

### Pitfall 2: SC1 rglob adds `__pycache__` .py files

**What goes wrong:** `rglob("*.py")` on `core/` will find `core/__pycache__/*.pyc` — no,
actually `.pyc` files don't match `*.py`. But `__pycache__` subdirs may contain no `.py`
files. No real risk here — rglob is safe.

**How to avoid:** No action needed. `*.py` glob never matches `.pyc`.

### Pitfall 3: test_paths separator guard silently empty list

**What goes wrong:** If the anchor is wrong (e.g., still CWD-relative after "fix"), the
guard silently passes with zero files checked.

**How to avoid:** Add `assert len(src_files) > 0, "separator guard scanned zero files"` as
the first assertion in `test_no_hardcoded_separators`. This turns a silent false-pass into
a loud failure.

### Pitfall 4: Manual check MC-3 (web live) requires uvicorn running — not TestClient

**What goes wrong:** Using `TestClient` for the Start/Stop / live-log-polling checks gives
false confidence. `TestClient` wraps the ASGI app in-process; actual browser polling and
WebSocket behavior differ.

**How to avoid:** The manual check requires a real browser + `shoppybot web` process. The
automated regression test (TD-4 banner test) is a `TestClient` HTML assertion only; it
does not replace the manual check.

### Pitfall 5: 0.0.0.0 banner — template must actually use `is_non_local`

**What goes wrong:** `test_non_local_banner_flag` confirms `app.state.is_non_local = True`
is set, but if the dashboard template doesn't read it, the banner never renders.

**How to avoid:** The regression test for MC-4 must assert banner HTML text is present in
the `TestClient` response when `create_app(svc, is_non_local=True)` is used. Read the
template to confirm the Jinja2 variable name before writing the test.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest --tb=short -q` |
| Full suite command | `pytest` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| STAB-02/TD-1 | logger reads logging_level from migrated config path | unit | `pytest tests/test_logger.py -x` | Partial (existing file; new test case needed) |
| STAB-02/TD-2 | SC1 guard covers core/cli/*.py | unit (guard) | `pytest tests/test_no_env_secret_reads.py -x` | Partial (existing file; fix + companion assertion needed) |
| STAB-02/TD-3 | separator guard uses absolute path, never silently empty | unit (guard) | `pytest tests/test_paths.py -x` | Partial (existing file; fix + guard assertion needed) |
| STAB-02/TD-4 | web credential/config write routes work correctly | unit | `pytest tests/test_web_credentials.py tests/test_web_config.py -x` | Partial (check existing coverage; add if gaps) |
| STAB-01/MC-4 | 0.0.0.0 banner renders in HTML when is_non_local=True | unit | `pytest tests/test_web_dashboard.py -x` | Partial (existing file; new assertion needed) |
| STAB-01/MC-1..3 | cross-OS live checks | manual only | — | docs/PLATFORMS.md |

### Sampling Rate

- Per task commit: `pytest --tb=short -q` (full suite, ~20s)
- Per wave merge: `pytest` (same)
- Phase gate: full suite green (354+ passed, 0 failed) before `/gsd:verify-work`

### Wave 0 Gaps

None — existing test infrastructure covers all phase requirements. New test cases are
additions to existing files, not new files (except possibly a
`tests/test_logger_config_path.py` if the reload complexity warrants isolation).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pytest | test execution | Yes | 8.3.4 | — |
| Python | all | Yes | 3.13.13 | — |
| fastapi + uvicorn | web check tests, MC-3/MC-4 | Yes | fastapi 0.115.8 | pytest.importorskip skips gracefully |
| keyring | MC-1, isolated_keyring fixture | Yes | installed (Windows Credential Manager) | NullKeyring in CI |
| Real browser | MC-3 live render | Yes (Windows) | Chrome/Edge | Manual-only; no automation needed |
| Ubuntu machine | MC-1 (headless), MC-2 (Ubuntu TTY), MC-3 (Ubuntu render) | No | — | Document as "not verified — requires Ubuntu hardware" |

**Missing dependencies with no fallback:**
- Ubuntu hardware for the Ubuntu-variant manual checks. These must be marked "pending
  Ubuntu access" in the PLATFORMS.md documentation update.

**Missing dependencies with fallback:**
- None that block the automated regression tests.

## Security Domain

Security enforcement is enabled. Phase 12 is a test/debt-paydown phase with no new
production features. The one production code change (logger `_CONFIG_PATH` fix) introduces
no new security surface.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | — |
| V3 Session Management | No | — |
| V4 Access Control | No | — |
| V5 Input Validation | No | — |
| V6 Cryptography | No | — |

No new credential handling, input processing, or cryptographic operations are introduced.

## State of the Art

No library upgrades or framework changes in scope. All existing pinned versions remain:
`pytest 8.3.4`, `fastapi 0.115.8`, `platformdirs 4.10.0`, `keyring` (current install).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | — | — | — |

**All claims in this research were verified against the actual codebase files or the
v2.0-MILESTONE-AUDIT.md artifact. No assumed claims.**

## Open Questions (RESOLVED)

1. **TD-4 regression test: does `test_web_credentials.py` already cover the `set_credential` POST?**
   - What we know: file exists; covers credential listing and CSRF
   - What's unclear: whether `POST /credentials` with a valid key/value is already tested
   - **RESOLVED (read `tests/test_web_credentials.py` at plan time):** YES — already covered,
     unconditionally. `test_post_credentials_calls_store_set` (line 64) patches
     `core.credentials.get_store`, POSTs `/credentials` with `{"key": "AMZ_EMAIL", "value":
     "test@example.com"}`, and asserts `mock_store.set.assert_called_once_with("AMZ_EMAIL",
     "test@example.com")`. Companion tests `test_post_credentials_returns_ok_status`,
     `test_post_credentials_secret_not_in_response`, and the 422 no-write guards
     (`test_post_credentials_unknown_key_returns_422_no_write` etc.) round out the credential write
     seam. Therefore the credential half of TD-4 needs NO new test — Plan 12-03 names
     `test_post_credentials_calls_store_set` as the satisfying artifact (does not re-add it) and adds
     only the remaining CONFIG-seam regression test (`write_web_config` -> `_DEFAULT_YAML_PATH`).

2. **MC-4 banner template variable: what is the exact Jinja2 conditional in `dashboard.html`?**
   - What we know: `app.state.is_non_local` is passed to the template context as `is_non_local`
   - What's unclear: the exact HTML/class name of the banner element to assert in the test
   - **RESOLVED (confirmed at plan time, recorded in Plan 12-03 `<interfaces>`):** the conditional is
     `{% if is_non_local %}` wrapping a `<div class="banner-warning">` whose copy includes the
     assertable substring "reachable beyond localhost". Plan 12-03 Task 2 asserts that substring is
     present when `create_app(mock_svc, is_non_local=True)` and absent when `is_non_local=False`
     (proving the gate, per Pitfall 5).

3. **Ubuntu checks: is WSL2 acceptable for Ubuntu manual checks?**
   - What we know: WSL2 provides an Ubuntu environment on this Windows machine
   - What's unclear: whether the user has WSL2 / Ubuntu available
   - **RESOLVED (planning decision):** STILL ENVIRONMENT-DEPENDENT — confirmed at execution time, not
     plan time. Plan 12-04 handles this deterministically: Ubuntu variants are run only if WSL2 / an
     Ubuntu host is available at the Task 1 checkpoint; otherwise the corresponding cells are recorded
     as "pending Ubuntu access" (never silently skipped, never marked PASS unless actually run). No
     code or plan change depends on the answer — the documentation outcome is well-defined either way.

## Sources

### Primary (HIGH confidence)
- `.planning/milestones/v2.0-MILESTONE-AUDIT.md` — exact 4 tech-debt items from frontmatter
- `docs/PLATFORMS.md` — exact 4 deferred manual check repro steps
- `tests/test_no_env_secret_reads.py` — SC1 guard current implementation
- `tests/test_paths.py` — separator guard current implementation
- `logger.py:1-20` — `_CONFIG_PATH` definition and `_load_logging_level` implementation
- `tests/conftest.py` — all test fixtures and patterns
- `pyproject.toml` — pytest configuration and asyncio_mode
- `core/service.py` — `main()` entry point with `initialize_db()` call (audit fix confirmed)
- `web/routes/credentials.py`, `web/config_web.py` — write path implementations (TD-4)
- `core/cli/web.py` — `0.0.0.0` warning logic (MC-4)
- `tests/test_web_security.py` — existing coverage of non-local warning

## Metadata

**Confidence breakdown:**
- Tech-debt item identification: HIGH — extracted verbatim from audit artifact
- Code path identification: HIGH — verified by reading actual source files
- Test pattern recommendations: HIGH — derived from existing test conventions in the same codebase
- Manual check scope: HIGH — documented in PLATFORMS.md with exact repro steps
- Ubuntu availability: LOW — assumed unavailable; WSL2 as fallback is unconfirmed

**Research date:** 2026-06-09
**Valid until:** Stable — no fast-moving dependencies; valid until source files change
