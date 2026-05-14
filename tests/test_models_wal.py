"""Phase 4 GREEN: tests for ASYNC-04 (WAL + busy_timeout + context manager).

Five assertions:
1. initialize_db persists journal_mode=wal (verified via a SECOND connection).
2. busy_timeout is applied on every _connect() (per-connection PRAGMA).
3. _connect() commits on success.
4. _connect() rolls back on exception.
5. Static guard: no raw sqlite3.connect() exists outside _connect().
"""
import ast
import sqlite3

import pytest

from models import (
    BUSY_TIMEOUT_MS,
    _connect,
    add_items,
    get_items,
    initialize_db,
)


def test_journalModeIsWal(tmpDbPath):
    initialize_db(delete=True)
    conn = sqlite3.connect(str(tmpDbPath), timeout=5.0)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        conn.close()
    assert mode.lower() == "wal", f"expected wal, got {mode!r}"


def test_busyTimeoutAppliedOnEveryConnect(tmpDbPath):
    initialize_db(delete=True)
    with _connect() as conn:
        ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert ms == BUSY_TIMEOUT_MS


def test_contextManagerCommitsOnSuccess(tmpDbPath):
    initialize_db(delete=True)
    add_items([("widget", "https://a.example", True, 1, False)])
    rows = get_items()
    assert rows == [("widget", "https://a.example", 1, 1, 0)]


def test_contextManagerRollsBackOnException(tmpDbPath):
    initialize_db(delete=True)
    add_items([("widget", "https://a.example", True, 1, False)])
    with pytest.raises(RuntimeError):
        with _connect() as conn:
            conn.execute(
                "UPDATE items SET purchased = 1 WHERE link = ?",
                ("https://a.example",),
            )
            raise RuntimeError("forced")
    rows = get_items()
    assert rows[0][4] == 0, "purchased flag must remain 0 after rollback"


def test_noRawConnectOutsideHelper():
    """Static guard: every sqlite3.connect call in models.py lives inside _connect."""
    src = open("models.py").read()
    tree = ast.parse(src)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "connect":
                if isinstance(func.value, ast.Name) and func.value.id == "sqlite3":
                    found.append(node.lineno)
    connectFunc = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_connect"
    )
    bodyLines = range(connectFunc.lineno, connectFunc.end_lineno + 1)
    for lineno in found:
        assert lineno in bodyLines, (
            f"Raw sqlite3.connect at line {lineno} is outside _connect()"
        )
    assert len(found) == 1, f"expected exactly one sqlite3.connect call, found {len(found)}"
