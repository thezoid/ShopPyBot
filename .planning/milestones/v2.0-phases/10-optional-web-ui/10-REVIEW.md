---
phase: 10-optional-web-ui
reviewed: 2026-06-04T00:00:00Z
depth: standard
iteration: 2
files_reviewed: 6
files_reviewed_list:
  - web/__init__.py
  - web/security.py
  - web/config_web.py
  - web/routes/api.py
  - web/routes/credentials.py
  - core/config_schema.py
findings:
  critical: 1
  warning: 1
  info: 1
  total: 3
status: issues_found
---

# Phase 10: Code Review Report (Iteration 2)

**Reviewed:** 2026-06-04
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Re-review of the fix+re-review loop. All eight prior findings (CR-01, CR-02, CR-03,
WR-01 through WR-05) were verified as correctly fixed against the live code, with
behavioral checks (config round-trip, origin matrix, deprecation-warning scan, full
328+ test suite). One NEW BLOCKER was discovered: the credentials POST handler still
dereferences `body["value"]` directly, so a valid key with a missing value field raises
an unhandled `KeyError` and returns HTTP 500. This is the same input-validation gap class
that WR-02 closed for the items route, but it was never applied to `credentials.py`. One
new WARNING (negative/zero quantity accepted by `add_item`) is a residual of the WR-02
fix's narrow scope.

### Prior findings: verification results

- **CR-01 (credential allowlist bypass) — VERIFIED FIXED.** `web/routes/api.py` defines
  only `/status`, `/logs`, `/bot/start`, `/bot/stop`, `/items` (GET/POST), and
  `/items/{link_b64}` (DELETE). No GET/POST `/credentials` remain (the only "credentials"
  token in the file is the module docstring). The sole credential route is
  `web/routes/credentials.py`, which gates POST on `key not in _creds.SECRET_KEYS` and
  returns 422 with no store write for unknown keys. Confirmed end to end.
- **CR-02 (config.yml corruption) — VERIFIED FIXED.** `notifications.sound` is now a
  2-tuple `("notifications", bool)` (`web/config_web.py:20`); the write path emits the
  scalar `{"notifications": {"sound": true}}` while discord/email/sms stay nested under
  `<channel>.enabled`. Round-trip executed: written YAML loads through `AppConfig` with no
  `ValidationError` (`sound=True`, `discord.enabled=False`).
- **CR-03 (CSRF/Origin gap) — VERIFIED FIXED.** `check_origin` builds `allowed =
  {server_host}` and only unions `_LOCAL_HOSTS` when `is_localhost(server_host)`. Matrix
  confirmed: non-local bind + loopback origin → 403; non-local bind + same origin → allow;
  loopback bind + localhost/127.0.0.1 origins → allow (interchangeable); loopback bind +
  cross origin → 403; missing Origin → allow. A `0.0.0.0` bind is treated non-local, so it
  also rejects loopback origins (correct).
- **WR-01 / WR-03 — VERIFIED FIXED.** Both `bot_start` and `bot_stop` use
  `await asyncio.to_thread(svc.start/stop)`. No `get_event_loop` or `run_in_executor`
  remain anywhere under `web/`. Full suite emits no `DeprecationWarning` for event-loop
  access.
- **WR-02 — PARTIALLY FIXED.** `add_item` now validates name/link (422) and coerces
  quantity via `int(...)` with try/except (422 on non-int). Residual: negative/zero
  quantities pass (see WR-01 below).
- **WR-04 / WR-05 — VERIFIED FIXED.** The dead unpacking line is gone; both write branches
  derive the leaf as `key.split(".")[-1]` (`web/config_web.py:69,79,83`).

## Critical Issues

### CR-01: set_credential dereferences body["value"] -> unhandled KeyError -> HTTP 500

**File:** `web/routes/credentials.py:43`
**Issue:** The POST handler validates `key` against `SECRET_KEYS` (good), but then reads
the value with a hard subscript:

```python
_creds.get_store().set(key, body["value"])
```

A request with a valid key but no `value` field (`{"key": "AMZ_EMAIL"}`) raises
`KeyError: 'value'`, which FastAPI surfaces as an unhandled HTTP 500 with a stack trace in
the server log. Reproduced live against the running app: the request 500s. This is the
identical input-validation defect class that WR-02 fixed for the items route, but the fix
was never propagated to the credentials route. CLAUDE.md requires all external input to be
validated server-side; here a malformed-but-origin-valid body crashes the handler instead
of returning a clean 4xx, and a same-origin script error (e.g. a field rename) becomes a
500 rather than a recoverable validation error. It also does not reject a non-string or
empty value before writing it into the secret store.
**Fix:** Validate `value` presence/type the same way `key` is validated, returning 422
with no store write and no echo of the value:

```python
body = await request.json()
key = body.get("key")
if key not in _creds.SECRET_KEYS:
    return JSONResponse({"status": "error", "detail": "unknown key"}, status_code=422)
value = body.get("value")
if not isinstance(value, str) or value == "":
    return JSONResponse({"status": "error", "detail": "value required"}, status_code=422)
_creds.get_store().set(key, value)
return JSONResponse({"status": "ok"})
```

## Warnings

### WR-01: add_item accepts non-positive quantity (negative/zero stored unchecked)

**File:** `web/routes/api.py:93-101`
**Issue:** The WR-02 fix validates name/link and that quantity is an integer, but does not
enforce that quantity is positive. Confirmed live: `quantity: -5` and `quantity: 0` both
return 200 and store the row. An `ItemConfig.quantity` is intended as a positive count
(default 1); a zero/negative quantity is a meaningless tracked row that the bot loop may
mishandle during an auto-buy. The CLI/credentials/config routes validate ranges
(`logging_level` 0-5); the items route should bound quantity similarly. `int(True)` also
coerces a JSON boolean to 1 silently, but that is benign.
**Fix:** Reject non-positive quantity with 422:

```python
try:
    quantity = int(body.get("quantity", 1))
except (TypeError, ValueError):
    return JSONResponse({"status": "error", "detail": "quantity must be an integer"}, status_code=422)
if quantity < 1:
    return JSONResponse({"status": "error", "detail": "quantity must be >= 1"}, status_code=422)
```

## Info

### IN-01: check_origin still treats a missing Origin header as same-origin

**File:** `web/security.py:46-47`
**Issue:** Unchanged from iteration 1 and acceptable for the localhost threat model: a
request with no `Origin` header is allowed (returns early). Any non-browser local client
(curl, local malware) that omits Origin bypasses the CSRF guard entirely. The dashboard's
own `fetch()` calls send Origin, so legitimate browser traffic is unaffected. Documented
as a known limitation, not a regression; no token-based defense is required for the
loopback deployment posture. No change required for v1.

_Reviewed: 2026-06-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Iteration: 2_
