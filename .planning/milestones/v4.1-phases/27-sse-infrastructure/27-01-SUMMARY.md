---
phase: 27-sse-infrastructure
plan: "01"
subsystem: tests
tags: [sse, tdd, red-spike, log-reader, wave-0]
dependency_graph:
  requires: []
  provides:
    - tests/test_sse.py
    - tests/test_log_reader.py
  affects:
    - web/sse_hub.py (Plan 02 must satisfy these tests)
    - web/routes/sse.py (Plan 02/03 must satisfy these tests)
    - web/log_reader.py (Plan 02 must add tail_log_lines)
tech_stack:
  added: []
  patterns:
    - "TestClient as context manager (lifespan pattern) for SSE streaming tests"
    - "httpx iter_text() join-window chunking pattern (A2 resolution)"
    - "Monkeypatch module-level constants with try/finally restore"
    - "top-level import for RED signal (ImportError IS the test)"
key_files:
  created:
    - tests/test_sse.py
    - tests/test_log_reader.py
  modified: []
decisions:
  - "A2 chunking: assert on ''.join(chunks[:8]) not chunks[0]; httpx may split a single SSE frame across multiple iter_text() reads"
  - "A3 disconnect: assert via len(app.state.sse_hub._queues)==0 after stream context exits, NOT is_disconnected() (unreliable in TestClient in-process transport)"
  - "No shared client fixture in test_sse.py; each test opens its own with TestClient(create_app(mock_svc)) as client: so lifespan runs"
  - "test_log_reader.py uses top-level import (from web.log_reader import tail_log_lines) so collection ImportError is the RED signal"
metrics:
  duration: "274s"
  completed_date: "2026-06-27"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
---

# Phase 27 Plan 01: SSE RED Spike Summary

Wave 0 RED scaffold: 6 SSE isolation tests + 3 tail_log_lines cursor tests, all failing on missing implementation (ModuleNotFoundError / ImportError), with clean collection and valid Python syntax.

## A2 Chunking Resolution

Open question A2 (httpx `iter_text()` SSE frame chunking) is resolved empirically: frame assertions use `"".join(chunks[:8])` rather than `chunks[0]`. The `_collect_chunks(resp, n=8)` helper collects up to 8 text chunks from `resp.iter_text()` and joins them into a single string for assertion. This is robust to httpx delivering one SSE frame across multiple reads, or delivering multiple frames in one read.

The `_CHUNK_WINDOW = 8` constant is defined at module level for easy adjustment if later implementation tests reveal a different chunk density.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RED test scaffold: tests/test_sse.py (6 isolation tests) | a455096 | tests/test_sse.py |
| 2 | RED test scaffold: tests/test_log_reader.py (tail_log_lines cursor) | 57c45fd | tests/test_log_reader.py |

## RED State Confirmation

- `python -m pytest tests/test_sse.py --collect-only -q`: 6 tests collected, 0 collection errors.
- `python -m pytest tests/test_sse.py -q`: 6 failed / 0 passed. Failures are `ModuleNotFoundError: No module named 'web.sse_hub'` (runtime, not collection).
- `python -m pytest tests/test_log_reader.py -q`: `ImportError: cannot import name 'tail_log_lines' from 'web.log_reader'` (collection-time, the intended RED signal).
- Both files: `python -c "import ast; ast.parse(...)"` exits 0 (valid Python syntax).

## tests/test_sse.py: 6 Tests

Each test uses its own `with TestClient(create_app(mock_svc)) as client:` block so the lifespan runs. Module-level constants `_POLL_INTERVAL_SECS` and `_KEEPALIVE_SECS` are patched in every test body with try/finally restore.

| Test | Criterion | Assertion |
|------|-----------|-----------|
| test_sse_retry_line_on_open | SSE-02 criterion 4 | `"retry: 3000" in "".join(chunks[:8])` |
| test_sse_status_frame_arrives | SSE-02 criterion 1 | `"event: status"` and `"data:"` in joined chunks |
| test_sse_keepalive_comment | SSE-02 criterion 1 keepalive | `": keep-alive"` in joined chunks (poll=60s, keepalive=0.05s) |
| test_sse_bot_start_stop_reflected | SSE-02 criterion 3 | `'"running": true'` in joined chunks after get_status flip |
| test_sse_disconnect_cleans_hub | SSE-02 criterion 2 | `len(client.app.state.sse_hub._queues) == 0` after stream context exits |
| test_sse_no_credential_patterns | SSE-03 carryover | No `password`/`key=`/`cvv` or email-like regex in joined chunks |

## tests/test_log_reader.py: 3 Tests

All use `monkeypatch.setattr("web.log_reader._read_today_lines", lambda: fake_lines)` for deterministic filesystem-free testing.

| Test | Assertion |
|------|-----------|
| test_tail_returns_new_lines_from_cursor | `tail_log_lines(2)` on 5-line file returns `(lines[2:], 5)` |
| test_tail_advances_cursor_no_new_lines | `tail_log_lines(5)` on 5-line file returns `([], 5)` |
| test_tail_rollover_resets_cursor | `tail_log_lines(10)` on 2-line file returns `(all_2_lines, 2)` (rollover reset) |

## Deviations from Plan

None. Plan executed exactly as written.

## Threat Flags

None. This plan creates only test files; no new network endpoints, auth paths, file access patterns, or schema changes were introduced.

## Known Stubs

None. Test files define no stub implementations.

## Self-Check: PASSED

- `tests/test_sse.py` exists: FOUND
- `tests/test_log_reader.py` exists: FOUND
- Commit a455096 exists: FOUND (`test(27-01): add RED SSE isolation spike tests/test_sse.py`)
- Commit 57c45fd exists: FOUND (`test(27-01): add RED tail_log_lines cursor tests tests/test_log_reader.py`)
- 6 tests collected (no import/syntax errors): CONFIRMED
- 6 tests fail at runtime (RED): CONFIRMED
- 3 log reader tests fail at collection via ImportError (RED): CONFIRMED
- `with TestClient(create_app(mock_svc)) as client:` appears 6 times in test_sse.py: CONFIRMED
- No `def client(` fixture in test_sse.py: CONFIRMED
- `_queues` assertion in disconnect test: CONFIRMED
- `_POLL_INTERVAL_SECS` and `_KEEPALIVE_SECS` monkeypatched with try/finally: CONFIRMED
- `from web.log_reader import tail_log_lines` at module top: CONFIRMED
- `_read_today_lines` monkeypatched in all 3 log reader tests: CONFIRMED
