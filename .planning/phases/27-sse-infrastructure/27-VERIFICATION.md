---
phase: 27-sse-infrastructure
verified: 2026-06-27T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run `curl -N http://localhost:8000/api/events` against a live server and observe the stream"
    expected: "First bytes contain 'retry: 3000'; a data: frame arrives within ~1s; ': keep-alive' appears on idle after ~15s; stream remains open indefinitely"
    why_human: "TestClient uses an in-process transport that cannot exercise a real socket; live-socket keepalive interval and production frame rate require a running uvicorn process"
  - test: "Start the bot daemon, confirm `running: false` in the SSE stream, then call the start endpoint and observe the stream again"
    expected: "Within 1-2 seconds, a status frame with '\"running\": true' appears in the stream without any server restart"
    why_human: "Real bot daemon start/stop crosses the thread boundary; TestClient test drives _poll_loop directly with a mock, not the real bot thread"
  - test: "Kill the curl client mid-stream (Ctrl+C) and check the server log for the socket disconnect"
    expected: "Server logs no queue leak; a follow-up GET to /api/events works cleanly; real-socket disconnect path exercises the finally:unsubscribe via uvicorn's transport (not the in-process TestClient path)"
    why_human: "Real TCP-level disconnect cannot be exercised by TestClient; the test covers the hub._queues==0 assertion via _FakeRequest only"
---

# Phase 27: SSE Infrastructure Verification Report

**Phase Goal:** A single /api/events SSE endpoint delivers live status and log events to browser clients over a clean cross-thread bridge, handles client disconnect without leaking generators, and is validated in complete isolation before any browser involvement.
**Verified:** 2026-06-27
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | /api/events emits a data: frame ~every 1s (status) + ': keep-alive' comment on idle (~15s in prod) | VERIFIED (automated partial) | `test_sse_retry_line_and_keepalive` PASSES: stream opens with `retry: 3000`, idle queue produces `: keep-alive` at `keepalive_secs=0.01`; `_KEEPALIVE_SECS=15.0` in `web/sse_hub.py` is the production default; live-socket 15s interval requires human UAT |
| 2 | Client disconnect exits the generator cleanly via `finally:unsubscribe`; SseHub has zero queues after (`test_sse_disconnect_cleans_hub`) | VERIFIED | `test_sse_disconnect_cleans_hub` PASSES: `_FakeRequest(disconnect_after=1)` drives the disconnect path; `finally: hub.unsubscribe(queue)` at `web/routes/sse.py:83-84`; `len(hub._queues) == 0` asserted and confirmed |
| 3 | Bot start/stop flips `status.running` in the stream (`test_poll_loop_reflects_bot_running_flip`) | VERIFIED | `test_poll_loop_reflects_bot_running_flip` PASSES: real `_poll_loop` driven with `poll_interval=0.01`; `side_effect` flips `running` False->True; `'"running": true'` confirmed in stream frames |
| 4 | Stream opens with `retry: 3000` | VERIFIED | `test_sse_retry_line_and_keepalive` PASSES: `combined.startswith("retry: 3000")` asserted; `yield "retry: 3000\n\n"` at `web/routes/sse.py:72` is the first yield before the wait loop |

**Score:** 4/4 truths verified (automated). 3 human UAT items required for live-socket behavior.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `web/sse_hub.py` | SseHub class + _poll_loop + module-level constants | VERIFIED | 110 lines; `class SseHub`, `async def _poll_loop`, `_POLL_INTERVAL_SECS = 1.0`, `_KEEPALIVE_SECS = 15.0` all present |
| `web/routes/sse.py` | GET /api/events StreamingResponse + _event_generator | VERIFIED | 85 lines; `text/event-stream`, `StreamingResponse`, `_event_generator`, `finally: hub.unsubscribe(queue)` all present |
| `web/__init__.py` | lifespan + app.state.sse_hub + sse router | VERIFIED | `@asynccontextmanager async def lifespan`, `app.state.sse_hub = SseHub()` in factory body, `app.include_router(sse_router, prefix="/api")` all present |
| `web/log_reader.py` | `tail_log_lines(after_line)` function | VERIFIED | `def tail_log_lines` appended after `read_logs_filtered`; uses `_read_today_lines()`; rollover branch `if after_line > total: return lines, total` present |
| `tests/test_sse.py` | 6 isolation tests all GREEN | VERIFIED | 6/6 PASS: `test_sse_retry_line_and_keepalive`, `test_sse_status_frame_delivered`, `test_poll_loop_reflects_bot_running_flip`, `test_sse_disconnect_cleans_hub`, `test_sse_no_credential_patterns`, `test_lifespan_creates_hub_and_registers_route` |
| `tests/test_log_reader.py` | 3 tail_log_lines cursor tests all GREEN | VERIFIED | 3/3 PASS: cursor, no-new-lines, rollover tests |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `web/__init__.py::lifespan` | `_poll_loop` | `asyncio.create_task` inside lifespan function | VERIFIED | `asyncio.create_task(` at line 30 of `web/__init__.py`; confirmed inside the `lifespan` async generator, not in `create_app` factory body |
| `web/routes/sse.py::sse_events` | `app.state.sse_hub` | `request.app.state.sse_hub` | VERIFIED | `hub = request.app.state.sse_hub` at `web/routes/sse.py:32` |
| `web/routes/sse.py::_event_generator` | `hub.unsubscribe` | `finally:` block | VERIFIED | `finally: hub.unsubscribe(queue)` at `web/routes/sse.py:83-84`; runs on break, CancelledError, and generator close |
| `web/__init__.py::create_app` | sse router | `include_router(sse_router, prefix="/api")` | VERIFIED | `app.include_router(sse_router, prefix="/api")` at line 70 |
| `web/sse_hub.py::_poll_loop` | `svc.get_status` / `tail_log_lines` | `asyncio.to_thread` | VERIFIED | 2 calls to `asyncio.to_thread` in poll body (lines 97, 99); sole producer on uvicorn's loop |
| `web/sse_hub.py::SseHub.subscribe` | `asyncio.Queue(maxsize=100)` | bounded queue | VERIFIED | `asyncio.Queue(maxsize=100)` at line 37 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `web/routes/sse.py::_event_generator` | `frame` from `queue.get()` | `SseHub.broadcast` <- `_poll_loop` <- `svc.get_status()` + `tail_log_lines()` | Yes — `svc.get_status()` is the real `BotService.get_status()` in production; `tail_log_lines()` reads `core.paths.log_dir()` (CR-01 fix confirmed in `_read_today_lines`) | FLOWING |
| `web/sse_hub.py::_poll_loop` | `status` dict, `new_lines` list | `asyncio.to_thread(svc.get_status)`, `asyncio.to_thread(tail_log_lines, cursor)` | Yes — both are real calls wrapped in `to_thread`; mock only used in tests | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| SseHub subscribe/broadcast/unsubscribe round-trip | `python -c "import asyncio, web.sse_hub as h; hub=h.SseHub(); q=hub.subscribe(); hub.broadcast('status', {'running': True}); f=q.get_nowait(); print(f.startswith('event: status') and 'data:' in f); hub.unsubscribe(q); print(len(hub._queues)==0)"` | `True` / `True` | PASS |
| Module constants accessible and correct | `python -c "import web.sse_hub as h; print(h._POLL_INTERVAL_SECS, h._KEEPALIVE_SECS)"` | `1.0 15.0` | PASS |
| SSE test suite | `python -m pytest tests/test_sse.py tests/test_log_reader.py -q` | 9 passed, 0 failed | PASS |
| Full test suite | `python -m pytest -q` | 785 passed, 2 skipped | PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` files exist for this phase. Phase PLAN/SUMMARY/VALIDATION reference no explicit probes. Step 7c: SKIPPED (no probe scripts).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SSE-02 | 27-01, 27-02, 27-03 | SSE stream handles client disconnect/reconnect cleanly — keepalive heartbeat, automatic client reconnect, server-side generator cleanup on disconnect | SATISFIED | `finally: hub.unsubscribe(queue)` (disconnect cleanup); `retry: 3000` (client reconnect); `asyncio.wait_for` keepalive branch (keepalive heartbeat); all 4 ROADMAP success criteria exercised by passing tests |

No orphaned requirements: REQUIREMENTS.md traceability table maps SSE-02 to Phase 27 only, and all Phase 27 PLANs declare `requirements: [SSE-02]`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `web/sse_hub.py` | 89 | `str(exc)` appears in docstring comment ("never str(exc)") | Info | In docstring only; actual error branch at line 108 uses `exc.__class__.__name__`; no production impact |

No TBD, FIXME, or XXX debt markers found in any Phase 27 production files.

No test-harness detection in production code: `'http.response.debug'` and `_TEST_MAX_FRAMES` do NOT appear anywhere in `web/`. The SUMMARY.md described an intermediate fix that was superseded; the final implementation uses `max_frames: int | None = None` as a plain parameter (production default is `None` meaning infinite stream; tests pass an explicit bound). This is correct: no test-harness detection in production.

### Key Invariant Checks

**Bridge invariant — web/sse_hub.py imports nothing from core/ or orchestrator:**
Grep of `web/sse_hub.py` for `^(import|from) core` or `^(import|from) orchestrator` returns zero matches (only a docstring mention). VERIFIED.

**Production code has NO test-harness detection:**
Grep of entire `web/` for `http.response.debug` and `_TEST_MAX_FRAMES` returns zero matches. VERIFIED.

**create_app lifespan placement:**
`asyncio.create_task` is inside `lifespan` function body (line 30 of `web/__init__.py`); `app.state.sse_hub = SseHub()` is inside `create_app` factory body (line 56). SseHub exists synchronously before lifespan runs. VERIFIED.

**Bounded queue, drop-oldest:**
`asyncio.Queue(maxsize=100)` at `web/sse_hub.py:37`; `get_nowait()` on full queue before `put_nowait()` at lines 58-64; producer never blocks. VERIFIED.

**tail_log_lines uses core.paths.log_dir() (CR-01 fix):**
`_read_today_lines()` lazy-imports `from core.paths import log_dir` (line 16 of `web/log_reader.py`); not a hardcoded path. Log frames will be non-empty in production. VERIFIED.

**No new Python packages:**
`starlette`, `fastapi`, `httpx`, `anyio` were all pre-existing dependencies. Raw `starlette.responses.StreamingResponse` used with no new installs. VERIFIED.

**_poll_loop survives a get_status error:**
`except asyncio.CancelledError: raise` at line 102; `except Exception as exc:` at line 104 with `exc.__class__.__name__` logging; `str(exc)` absent from executable code. VERIFIED.

### Human Verification Required

#### 1. Live-socket keepalive timing

**Test:** Start the app with `python main.py --web` (or uvicorn directly), then run `curl -N http://localhost:8000/api/events` for at least 30 seconds.
**Expected:** `data:` frames arrive approximately every 1 second; `: keep-alive` comment lines appear approximately every 15 seconds during periods with no log writes.
**Why human:** TestClient uses an in-process transport that does not exercise real TCP keepalive timing. The production `_KEEPALIVE_SECS = 15.0` constant is correct but the actual 15s interval can only be confirmed against a running uvicorn process.

#### 2. Real bot daemon running-flip in the live stream

**Test:** With `curl -N http://localhost:8000/api/events` running, start and then stop the bot daemon via the web UI or CLI.
**Expected:** Within 1-2 seconds, a status frame with `"running": true` appears in the curl output when the bot starts; a frame with `"running": false` appears when it stops. The SSE stream stays open across both transitions.
**Why human:** The automated test (`test_poll_loop_reflects_bot_running_flip`) drives `_poll_loop` directly with a mock BotService, not the real bot daemon thread. The cross-thread bridge (bot thread writes HealthRegistry; `_poll_loop` on uvicorn's loop reads `svc.get_status()` via `asyncio.to_thread`) can only be validated end-to-end with a real running process.

#### 3. Real TCP disconnect cleanup

**Test:** Run `curl -N http://localhost:8000/api/events` for 5+ seconds, then kill it with Ctrl+C. Inspect the server log immediately after.
**Expected:** Server does not log queue growth errors; a subsequent `curl -N http://localhost:8000/api/events` connects cleanly. No "SSE poll error" log lines from a stale queue reference.
**Why human:** The automated `test_sse_disconnect_cleans_hub` test uses `_FakeRequest(disconnect_after=1)` — a simulated disconnect signal, not a real TCP FIN/RST. The `finally: hub.unsubscribe(queue)` path is verified by test, but the full uvicorn ASGI teardown path on real socket close requires a live server.

### Gaps Summary

No gaps blocking goal achievement. All four ROADMAP success criteria are verified by passing automated tests. Three human UAT items remain for live-socket behavior (timing, real bot thread, real TCP disconnect) — these are architectural limitations of the TestClient transport, not implementation defects.

---

_Verified: 2026-06-27_
_Verifier: Claude (gsd-verifier)_
