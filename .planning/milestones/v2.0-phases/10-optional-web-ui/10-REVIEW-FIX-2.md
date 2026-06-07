---
phase: 10-optional-web-ui
fixed_at: 2026-06-04T00:00:00Z
review_path: .planning/phases/10-optional-web-ui/10-REVIEW.md
iteration: 2
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 10: Code Review Fix Report (Iteration 2)

**Fixed at:** 2026-06-04
**Source review:** .planning/phases/10-optional-web-ui/10-REVIEW.md
**Iteration:** 2

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### CR-01-new: set_credential dereferences body["value"] without validation

**Files modified:** `web/routes/credentials.py`, `tests/test_web_credentials.py`
**Commit:** 68e2200
**Applied fix:** Added `value = body.get("value")` followed by an `isinstance(value, str) or value == ""` guard that returns 422 with `{"status": "error", "detail": "value required"}` before the store write. Value is never echoed in any response branch. Four regression tests added: missing value field returns 422 with no store write, empty string value returns 422 with no store write, response body never contains the probed secret value, and existing happy-path tests remain green.

### WR-01-new: add_item accepts non-positive quantity (zero and negative stored unchecked)

**Files modified:** `web/routes/api.py`, `tests/test_web_items.py`
**Commit:** 6f2a443
**Applied fix:** Added `if quantity < 1: return JSONResponse({"status": "error", "detail": "quantity must be >= 1"}, status_code=422)` immediately after the existing int-coercion try/except block. Three regression tests added: quantity 0 returns 422 with no add_item call, quantity -5 returns 422 with no add_item call, omitted quantity defaults to 1 and calls add_item correctly.

## Verification

Full suite: `python -m pytest -q` from repo root passed 335 tests (329 pre-existing + 6 new), 0 failures, 1 xpassed (pre-existing), 2 warnings (pre-existing, unrelated to these changes).

---

_Fixed: 2026-06-04_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
