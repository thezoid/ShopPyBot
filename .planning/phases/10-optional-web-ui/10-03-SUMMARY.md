---
phase: 10-optional-web-ui
plan: "03"
subsystem: web-ui
tags: [fastapi, credentials, security, sc3, csrf, gui-03]
dependency_graph:
  requires: [web/__init__.py, web/security.py, core/credentials.py]
  provides: [web/routes/credentials.py]
  affects: []
tech_stack:
  added: []
  patterns: [get-store-module-import, csrf-depends, status-only-response]
key_files:
  created: []
  modified:
    - web/routes/credentials.py
decisions:
  - "Import core.credentials as a module (import core.credentials as _creds) rather than binding get_store locally; test patches on core.credentials.get_store resolve at call time"
  - "Secret value never appears in any response branch: 200 ok, 422 error, or 403 forbidden"
  - "key not in SECRET_KEYS gate returns 422 with no echo of the submitted value (T-10-11)"
metrics:
  duration: "3m"
  completed: "2026-06-04"
  tasks: 1
  files: 1
requirements: [GUI-03]
---

# Phase 10 Plan 03: Credential Routes (SC3 No-Secret-Leak) Summary

Credential GET+POST routes implemented with zero secret exposure: GET returns name+is_set per SECRET_KEY, POST stores via CredentialStore.set and returns status only -- submitted value absent from all response branches.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Credentials GET (name+is_set) and POST (set, status-only) | 2361f21 | web/routes/credentials.py |

## What Was Built

**GET /api/credentials:** Returns `{"credentials": [{"name": k, "is_set": store.get(k) is not None}]}` for every key in `SECRET_KEYS`. No `value` field present on any entry (SC3 / T-10-08).

**POST /api/credentials:** Origin-checked via `Depends(check_origin)` (403 on cross-origin, T-10-10). Validates `key in SECRET_KEYS`; unknown key returns 422 `{"status":"error","detail":"unknown key"}` with no echo of the submitted value (T-10-11). Valid key calls `get_store().set(key, value)` and returns `{"status":"ok"}` only. The secret value never appears in any response body or log line.

**Module import pattern:** `import core.credentials as _creds` rather than `from core.credentials import get_store`. This ensures `patch("core.credentials.get_store")` in tests resolves the correct reference at call time -- the module attribute is looked up per-call, not bound once at import.

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None beyond what the plan's threat model already covers.

## Self-Check: PASSED

Files exist:
- web/routes/credentials.py: FOUND

Commits exist:
- 2361f21: FOUND

Full suite: 320 passed, 1 xpassed, 0 failed.
