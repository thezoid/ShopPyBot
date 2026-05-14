---
phase: 04-async-orchestrator
plan: 02
type: execute
wave: 1
depends_on: ["01"]
files_modified:
  - models.py
  - tests/test_models_wal.py
autonomous: true
requirements:
  - ASYNC-04
tags:
  - python
  - sqlite
  - wal
  - models
  - concurrency

must_haves:
  truths:
    - "initialize_db() sets PRAGMA journal_mode = WAL exactly once and persists it via an immediate CREATE TABLE write"
    - "Every sqlite3.connect() in models.py applies PRAGMA busy_timeout = 5000 (per-connection PRAGMA, not init-only)"
    - "models.py exposes a private _connect() context manager that commits on success, rolls back on exception, and always closes the connection"
    - "All four public functions (initialize_db, add_items, update_item_purchased, get_items) route through _connect() — no raw sqlite3.connect() calls remain outside _connect"
    - "Each sqlite3.connect() also passes timeout=5.0 (Python-level wait, belt-and-suspenders alongside the PRAGMA)"
    - "Connections are not cached at module scope (Pitfall 8: SQLite connections cannot cross threads)"
    - "After WAL is set, a second connection observing PRAGMA journal_mode returns 'wal' (proves persistence per Pitfall 2)"
    - "All RED tests in tests/test_models_wal.py written in Plan 04-01 now PASS"
    - "Pre-existing Phase 1/2/3 test suite remains green (no regressions in add_items/get_items/update_item_purchased behavior)"
  artifacts:
    - path: "models.py"
      provides: "SQLite layer with WAL mode, per-connection busy_timeout, and connection context manager"
      contains: "journal_mode"
      min_lines: 50
    - path: "tests/test_models_wal.py"
      provides: "GREEN tests for ASYNC-04 (WAL persistence, busy_timeout per connect, context manager rollback)"
      min_lines: 50
  key_links:
    - from: "models._connect"
      to: "sqlite3.connect"
      via: "single chokepoint for connection creation; applies timeout and busy_timeout"
      pattern: "PRAGMA busy_timeout"
    - from: "models.initialize_db"
      to: "WAL persistence"
      via: "PRAGMA journal_mode = WAL followed by CREATE TABLE write"
      pattern: "journal_mode.*WAL"
---

<objective>
Refactor models.py to use SQLite WAL journal mode with a 5000ms busy_timeout applied per-connection, route every DB call through a single `_connect()` context manager, and flip the Plan 04-01 RED tests in tests/test_models_wal.py to GREEN. This satisfies ASYNC-04 and prepares the SQLite layer for the parallel writes that Wave 2's purchase_writer will perform.

Purpose: The current models.py opens raw `sqlite3.connect(DB_PATH)` four times with no WAL, no busy_timeout, and no rollback on exception. Under Phase 4's concurrent write path (purchase_writer running alongside the seeding/init path), this surfaces as `database is locked` errors. WAL mode allows readers to proceed while a writer holds the lock; busy_timeout makes the writer wait politely; context managers prevent partial writes from corrupting state.

Output: rewritten models.py (still under 300 lines, functions under 30 lines), GREEN tests in tests/test_models_wal.py, no regressions elsewhere.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/04-async-orchestrator/04-CONTEXT.md
@.planning/phases/04-async-orchestrator/04-RESEARCH.md
@.planning/phases/04-async-orchestrator/04-01-async-test-infra-PLAN.md
@models.py
@tests/test_models_wal.py
@tests/conftest.py
</context>

<interfaces>
Target `models.py` shape (see RESEARCH Pattern 4):

```python
"""SQLite layer (Phase 4: WAL + busy_timeout + context manager).

Connection rules:
- WAL mode is set ONCE in initialize_db() and persisted by an immediate write.
- busy_timeout is per-connection PRAGMA; applied inside _connect().
- Every public function uses `with _connect() as conn:` — no raw sqlite3.connect.
- Connections are NOT cached at module scope (Pitfall 8).
"""
import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

DB_PATH = os.path.join("data", "shop_py_bot.db")
BUSY_TIMEOUT_MS = 5000


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS};")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_db(delete: bool = False) -> None:
    if delete and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _connect() as conn:
        # WAL set FIRST then a CREATE TABLE write so SQLite persists the journal
        # mode change in the file header (Pitfall 2).
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                auto_buy BOOLEAN NOT NULL,
                quantity INTEGER NOT NULL,
                purchased BOOLEAN NOT NULL DEFAULT 0
            )"""
        )


def add_items(items) -> None:
    with _connect() as conn:
        for item in items:
            row = conn.execute(
                "SELECT COUNT(*) FROM items WHERE link = ?", (item[1],)
            ).fetchone()
            if row[0] == 0:
                conn.execute(
                    "INSERT INTO items (name, link, auto_buy, quantity, purchased) "
                    "VALUES (?, ?, ?, ?, ?)",
                    item,
                )


def update_item_purchased(link: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE items SET purchased = 1 WHERE link = ?", (link,))


def get_items():
    with _connect() as conn:
        return conn.execute(
            "SELECT name, link, auto_buy, quantity, purchased FROM items"
        ).fetchall()
```

The signature of every public function is unchanged. The behavior is unchanged for callers. The only observable changes are: WAL files appear in `data/`, `database is locked` errors no longer occur under parallel writes, and exceptions in the middle of `add_items` now leave the DB in a fully rolled-back state.

Target `tests/test_models_wal.py` GREEN tests (extend or replace the RED skeletons from Plan 04-01):

```python
"""Phase 4 GREEN: tests for ASYNC-04 (WAL + busy_timeout + context manager)."""
import sqlite3
import pytest

from models import initialize_db, add_items, update_item_purchased, get_items, _connect, BUSY_TIMEOUT_MS


def test_journalModeIsWal(tmpDbPath):
    initialize_db(delete=True)
    with sqlite3.connect(str(tmpDbPath), timeout=5.0) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_busyTimeoutAppliedOnEveryConnect(tmpDbPath):
    initialize_db(delete=True)
    # Open a fresh _connect and verify per-connection PRAGMA
    with _connect() as conn:
        ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert ms == BUSY_TIMEOUT_MS


def test_contextManagerCommitsOnSuccess(tmpDbPath):
    initialize_db(delete=True)
    add_items([("widget", "https://a.example", True, 1, False)])
    assert get_items() == [("widget", "https://a.example", 1, 1, 0)]


def test_contextManagerRollsBackOnException(tmpDbPath):
    initialize_db(delete=True)
    add_items([("widget", "https://a.example", True, 1, False)])
    with pytest.raises(RuntimeError):
        with _connect() as conn:
            conn.execute("UPDATE items SET purchased = 1 WHERE link = ?", ("https://a.example",))
            raise RuntimeError("forced")
    # Reopen and verify the UPDATE was rolled back
    rows = get_items()
    assert rows[0][4] == 0  # purchased flag still 0


def test_noRawConnectOutsideHelper():
    """Static guard: every sqlite3.connect call in models.py lives inside _connect."""
    import ast
    src = open("models.py").read()
    tree = ast.parse(src)
    # Find all Call(sqlite3.connect) nodes; their nearest enclosing FunctionDef must be _connect.
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "connect":
                if isinstance(func.value, ast.Name) and func.value.id == "sqlite3":
                    found.append(node.lineno)
    # Find _connect line range
    connect_func = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_connect"
    )
    body_lines = range(connect_func.lineno, connect_func.end_lineno + 1)
    for lineno in found:
        assert lineno in body_lines, (
            f"Raw sqlite3.connect at line {lineno} is outside _connect()"
        )
```

Test file uses the `tmpDbPath` fixture from Plan 04-01's conftest.
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Rewrite models.py with WAL + busy_timeout + _connect context manager</name>
  <files>models.py</files>
  <read_first>
    - models.py (current 59-line implementation; replace in full)
    - tests/test_models_wal.py (RED skeletons from Plan 04-01; these will be replaced/extended in Task 2)
    - .planning/phases/04-async-orchestrator/04-RESEARCH.md (Pattern 4; Pitfalls 2, 3, 8)
    - tests/conftest.py (tmpDbPath fixture uses monkeypatch on models.DB_PATH)
  </read_first>
  <behavior>
    - Public signatures preserved: initialize_db(delete=False), add_items(items), update_item_purchased(link), get_items().
    - `BUSY_TIMEOUT_MS = 5000` exported at module scope so tests can assert against it without hardcoding.
    - `_connect()` is the ONLY place `sqlite3.connect(...)` is called.
    - `initialize_db` creates the parent directory (`os.makedirs(..., exist_ok=True)`) before connecting, so first-run on a fresh checkout does not crash on missing `data/` dir.
    - All functions remain under 30 lines.
    - File total remains under 300 lines.
    - No dependency on any new external library — stdlib only.
  </behavior>
  <action>
    1. Replace the entire body of `models.py` with the target shape shown in <interfaces>. Preserve the module-level `DB_PATH` constant exactly (`os.path.join("data", "shop_py_bot.db")`) so existing tests that monkey-patch it still work.

    2. Use `@contextmanager` decorator from `contextlib`. The `_connect` function is private (leading underscore) but importable for tests (no `__all__` restriction in this module).

    3. WAL ordering matters (Pitfall 2): inside `initialize_db`, the PRAGMA must run BEFORE the CREATE TABLE so the CREATE acts as the persisting write. If you reverse them, the journal_mode change can be lost on empty-DB closes.

    4. busy_timeout site (Pitfall 3): apply the PRAGMA inside `_connect`, NOT inside `initialize_db`. Reason: busy_timeout is per-connection, not DB-file-persisted. Every connection must set it.

    5. Add the Python-level `timeout=5.0` kwarg on `sqlite3.connect(DB_PATH, timeout=5.0)` as belt-and-suspenders. The PRAGMA handles SQLite-level retries; the Python kwarg handles cases where the lock is held longer than 5 seconds (it then raises OperationalError after 5s).

    6. Do NOT cache the connection at module scope (Pitfall 8). Each `_connect()` call opens a fresh connection. This is essential for the Wave 2 purchase_writer task running in a different worker thread than the seed/init path.

    7. Verify `os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)` is called before opening the DB file. Without it, fresh checkouts fail on the first `sqlite3.connect`.

    8. Run `rtk pytest -q tests/test_models.py` (the existing Phase 1 test file, if present) and `rtk pytest -q` full suite. Both must pass.
  </action>
  <verify>
    <automated>python -c "import ast; t = ast.parse(open('models.py').read()); print('OK')"</automated>
    <automated>rtk grep -n "journal_mode\|busy_timeout\|_connect\|BUSY_TIMEOUT_MS" models.py</automated>
    <automated>rtk pytest -x -q tests/test_models.py 2>&1 | rtk grep -E "passed|failed"</automated>
    <automated>rtk pytest -x -q</automated>
  </verify>
  <acceptance_criteria>
    - models.py defines `BUSY_TIMEOUT_MS = 5000` at module scope
    - models.py exports `_connect` as a context manager
    - Every `sqlite3.connect(...)` call in models.py is inside `_connect`
    - `initialize_db` sets `PRAGMA journal_mode = WAL` followed by a CREATE TABLE write
    - `_connect` sets `PRAGMA busy_timeout = 5000` on every connection
    - All four public function signatures unchanged
    - models.py under 300 lines; all functions under 30 lines
    - Existing pytest suite green
  </acceptance_criteria>
  <done>models.py rewritten with WAL + busy_timeout + context manager; behavior-preserving for existing callers</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Flip tests/test_models_wal.py from RED to GREEN with full ASYNC-04 coverage</name>
  <files>tests/test_models_wal.py</files>
  <read_first>
    - tests/test_models_wal.py (RED skeleton from Plan 04-01)
    - models.py (GREEN after Task 1)
    - tests/conftest.py (tmpDbPath fixture)
    - .planning/phases/04-async-orchestrator/04-RESEARCH.md (Sample test patterns; Pitfalls 2, 3)
  </read_first>
  <behavior>
    - All five tests defined in <interfaces> live in tests/test_models_wal.py and PASS.
    - The static guard test (test_noRawConnectOutsideHelper) parses models.py and verifies no raw sqlite3.connect calls exist outside _connect.
    - The rollback test demonstrates that an exception inside `with _connect()` reverts uncommitted changes.
    - All tests use `tmpDbPath` to redirect DB_PATH so they do not touch the developer's actual data/shop_py_bot.db.
  </behavior>
  <action>
    1. Replace the contents of `tests/test_models_wal.py` (RED skeleton from Plan 04-01) with the GREEN test suite shown in <interfaces>. Preserve the RED-skeleton module docstring header but update the wording from "expected to FAIL" to "Phase 4 GREEN for ASYNC-04".

    2. Each test imports from `models` only — no other production module.

    3. The static guard test (test_noRawConnectOutsideHelper) walks the AST of models.py. If anyone re-introduces a raw `sqlite3.connect(...)` outside `_connect()` in a later phase, this test fails immediately.

    4. Run `rtk pytest -x -q tests/test_models_wal.py`. Expect all 5 tests PASS.

    5. Run `rtk pytest -x -q`. Full suite must stay green.

    6. Sanity check: `rtk find data -name "*.db-wal"` after running the suite — expected to find zero matches because `tmpDbPath` redirects everything to tmp_path. If a .db-wal appears under `data/`, a test leaked a DB write to the real path; investigate the missing monkeypatch.
  </action>
  <verify>
    <automated>rtk pytest -x -q tests/test_models_wal.py</automated>
    <automated>rtk pytest -x -q</automated>
    <automated>rtk find data -name "*.db-wal" 2>&1 | rtk grep -E "No such|^$"</automated>
  </verify>
  <acceptance_criteria>
    - tests/test_models_wal.py contains all 5 tests from <interfaces>
    - All 5 tests PASS
    - Static guard catches future re-introduction of raw sqlite3.connect outside _connect
    - Test runs do not pollute repo data/ directory with WAL files
    - Full suite green
    - ASYNC-04 fully satisfied
  </acceptance_criteria>
  <done>ASYNC-04 GREEN; SQLite layer ready for Wave 2 concurrent writes</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| concurrent writer + reader (Wave 2 surface) | purchase_writer task and seed/init path may interleave; WAL+busy_timeout must absorb the race |
| partial write on exception | A multi-statement add_items call must not leave half-inserted rows if one INSERT raises |
| stale WAL sidecar files | Crash mid-write leaves .db-wal; SQLite recovers on next connect; .gitignore prevents committing them |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-02-DB-LOCKED | Denial of Service | sqlite3.connect under concurrent write | mitigate | WAL allows readers during writer; busy_timeout=5000ms gives writer a polite retry window. Verified by test_busyTimeoutAppliedOnEveryConnect |
| T-04-02-PARTIAL-WRITE | Tampering | add_items multi-INSERT | mitigate | _connect context manager rolls back on exception; verified by test_contextManagerRollsBackOnException |
| T-04-02-WAL-NOT-PERSISTED | Tampering | initialize_db | mitigate | PRAGMA journal_mode=WAL followed immediately by CREATE TABLE write (Pitfall 2). Verified by test_journalModeIsWal opening a SECOND connection and reading the mode back |
| T-04-02-CROSS-THREAD-CONN | Information Disclosure / crash | module-scope connection cache | mitigate | _connect opens a fresh connection per call; no module-level cache. Static guard test_noRawConnectOutsideHelper blocks future regressions |
| T-04-02-WAL-COMMIT-LEAK | Information Disclosure | data/*.db-wal in git | mitigate | .gitignore patterns landed in Plan 04-01 Task 1 |
</threat_model>

<verification>
- `rtk grep -n "journal_mode\|busy_timeout\|_connect\|BUSY_TIMEOUT_MS" models.py` shows all four symbols
- `rtk pytest -x -q tests/test_models_wal.py` shows 5 passed
- `rtk pytest -x -q` full suite green
- `rtk find data -name "*.db-wal"` returns no matches after test run
- AST sanity: `python -c "import ast; ast.parse(open('models.py').read())"` exits 0
</verification>

<success_criteria>
- ASYNC-04 fully satisfied: WAL mode, busy_timeout=5000 per connection, context-manager-wrapped connection usage
- models.py public API unchanged from caller perspective
- 5 GREEN tests asserting WAL persistence, busy_timeout per connect, commit/rollback semantics, no raw sqlite3.connect outside _connect
- Pre-existing suite remains green
- Ready for Wave 2 purchase_writer to drive concurrent writes without `database is locked` errors
</success_criteria>

<output>
After completion, create `.planning/phases/04-async-orchestrator/04-02-SUMMARY.md`
</output>
