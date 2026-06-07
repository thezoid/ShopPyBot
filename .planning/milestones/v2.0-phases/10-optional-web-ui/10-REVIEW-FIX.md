---
phase: 10-optional-web-ui
fixed_at: 2026-06-04T18:45:00Z
review_path: .planning/phases/10-optional-web-ui/10-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 10: Code Review Fix Report

**Fixed at:** 2026-06-04T18:45:00Z
**Source review:** .planning/phases/10-optional-web-ui/10-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (CR-01, CR-02, CR-03, WR-01, WR-02, WR-03, WR-04, WR-05)
- Fixed: 8
- Skipped: 0

## Fixed Issues

### CR-01: Duplicate /credentials routes bypass the SECRET_KEYS allowlist

**Files modified:** `web/routes/api.py`
**Commit:** 0bdcced
**Applied fix:** Removed the duplicate GET/POST `/credentials` route handlers from
`api.py` entirely (lines 102-124 including the stale planning comments). The only
credential routes now served are the gated handlers in `web/routes/credentials.py`,
which enforce the `SECRET_KEYS` membership check and return 422 for unknown keys.

### CR-02: write_web_config corrupts config.yml for notifications.sound

**Files modified:** `web/config_web.py`
**Commit:** c5b49cc
**Applied fix:** Changed the `notifications.sound` entry in `WEB_ALLOWLIST` from a
3-tuple `("notifications", "sound", bool)` to a 2-tuple `("notifications", bool)`.
The 2-tuple branch now writes `data["notifications"]["sound"] = coerced` (scalar
bool), not the corrupting `{"sound": {"enabled": ...}}` nested object. The
discord/email/sms 3-tuple entries are unchanged.

### CR-03: check_origin accepts any loopback Origin even when server is non-local

**Files modified:** `web/security.py`
**Commit:** 1a23228
**Applied fix:** `check_origin` now computes `allowed = {server_host}` and only
expands it with `_LOCAL_HOSTS` when `is_localhost(server_host)` is true. For a
non-local bind, the loopback escape hatch is no longer granted; only the exact
server host is accepted.

### WR-01: bot/stop uses deprecated get_event_loop in an async context

**Files modified:** `web/routes/api.py`
**Commit:** 0bdcced
**Applied fix:** Replaced `asyncio.get_event_loop().run_in_executor(None, svc.stop)`
with `await asyncio.to_thread(svc.stop)` in the `bot_stop` handler.

### WR-02: add_item handler trusts client body with no validation

**Files modified:** `web/routes/api.py`
**Commit:** 0bdcced
**Applied fix:** `add_item` now validates `name` (required, stripped) and `link`
(required, stripped), returning 422 with a descriptive message on failure. `quantity`
is coerced via `int(...)` with a try/except, returning 422 on non-integer input.
`auto_buy` defaults to `False` if absent.

### WR-03: svc.start() blocks the event loop

**Files modified:** `web/routes/api.py`
**Commit:** 0bdcced
**Applied fix:** `bot_start` now calls `await asyncio.to_thread(svc.start)`,
matching the corrected stop path. The blocking 5-second `ready.wait()` inside
`svc.start()` is now off the event loop.

### WR-04: Dead unpacking line in write_web_config

**Files modified:** `web/config_web.py`
**Commit:** c5b49cc
**Applied fix:** Removed line 60 (`_, *path_parts, typ = entry if len(entry) == 3
else (*entry, str)`). The variables assigned were never used; the dead code also
obscured the CR-02 bug.

### WR-05: 2-tuple config write uses the full dotted key as the YAML leaf

**Files modified:** `web/config_web.py`
**Commit:** c5b49cc
**Applied fix:** Both the 2-tuple and 3-tuple write branches now derive the leaf as
`key.split(".")[-1]`. For existing 2-tuple keys (`test_mode`, `logging_level`) the
result is identical to before (no dot in key). For the newly-moved 2-tuple
`notifications.sound`, the leaf is correctly `sound` rather than
`notifications.sound`.

## Test commits

**Commit:** 4c46532 -- adds 6 new regression tests and updates all TestClient fixtures
to use `base_url="http://127.0.0.1:8000"` so the CR-03 same-origin guard passes for
localhost-bound test requests. Final suite: 328 passed, 0 failures.

**New tests added:**
- `test_web_credentials.py::test_post_credentials_unknown_key_returns_422_no_write` (CR-01)
- `test_web_config.py::test_sound_write_produces_scalar_bool_yaml` (CR-02, AppConfig round-trip)
- `test_web_security.py::test_csrf_loopback_origin_rejected_on_non_local_bind` (CR-03)
- `test_web_security.py::test_csrf_same_origin_accepted_on_non_local_bind` (CR-03)
- `test_web_items.py::test_post_item_missing_name_returns_422` (WR-02)
- `test_web_items.py::test_post_item_missing_link_returns_422` (WR-02)
- `test_web_items.py::test_post_item_bad_quantity_returns_422` (WR-02)

---

_Fixed: 2026-06-04T18:45:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
