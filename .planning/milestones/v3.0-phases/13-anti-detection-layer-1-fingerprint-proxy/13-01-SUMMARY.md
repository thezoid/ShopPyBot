---
phase: 13-anti-detection-layer-1-fingerprint-proxy
plan: "01"
subsystem: core/stealth
tags: [anti-detection, fingerprint, proxy, stealth, tdd]
dependency_graph:
  requires: []
  provides: [core.stealth, ProxyPool, apply_stealth, build_proxy_browser_args, setup_proxy_auth]
  affects: [core/plugin_base.py consumers, Plan 03 plugin wiring]
tech_stack:
  added: []
  patterns:
    - CDP addScriptToEvaluateOnNewDocument for fingerprint injection
    - ProxyPool round-robin with retire/cooldown dataclass state machine
    - CDP Fetch.enable + add_handler ordering for authenticated proxy
    - asyncio.create_task in event handlers to prevent receive-loop deadlock
key_files:
  created:
    - core/stealth.py
    - tests/test_stealth.py
  modified: []
decisions:
  - "_parse_proxy_url uses stdlib urlparse only; host_port separated at construction (T-13-01)"
  - "setup_proxy_auth no-op on empty username; add_handler before fetch.enable enforced (Pitfall 4)"
  - "build_proxy_browser_args returns [] for None entry (proxy disabled); host_port only, never entry.url"
  - "ProxyPool.advance() returns None when all retired; caller must fail loudly (Pitfall 2)"
  - "time.monotonic used for cooldown timestamps; module-level time patched in tests"
metrics:
  duration: "7 minutes"
  completed_date: "2026-06-09"
  tasks: 2
  files: 2
---

# Phase 13 Plan 01: Stealth Core and Proxy Pool Summary

One-liner: CDP fingerprint JS injector with 4 browser-stealth patches plus a round-robin proxy pool with retire/cooldown and ban detection, tested entirely via AsyncMock without a live browser.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wave 0 -- failing test suite (RED) | dde3402 | tests/test_stealth.py |
| 2 | Implement core/stealth.py (GREEN) | c757514 | core/stealth.py |

## Verification Results

- `python -m pytest tests/test_stealth.py -q`: 17 passed
- `python -m pytest -q`: 376 passed, 2 skipped (baseline 359 + 17 new; 0 regressions)
- `core/stealth.py` line count: 262 lines (limit 300)
- All 8 symbols exported: STEALTH_JS, apply_stealth, _ProxyEntry, ProxyPool, _parse_proxy_url, _is_ban_response, build_proxy_browser_args, setup_proxy_auth
- No log/print referencing proxy entry.url (security assertion passed)
- requirements.txt unchanged (no new runtime dependency)

## TDD Gate Compliance

- RED gate: commit dde3402 -- test stub fails at import of core.stealth (ModuleNotFoundError confirmed)
- GREEN gate: commit c757514 -- all 17 tests pass after implementation

## Deviations from Plan

None. Plan executed exactly as written.

## Known Stubs

None. All exported functions are fully implemented.

## Threat Flags

No new trust boundaries introduced beyond those in the plan threat model.

| Threat ID | Mitigation Status |
|-----------|------------------|
| T-13-01 | Mitigated: host_port stored separately; build_proxy_browser_args uses host_port only; test asserts no credential in args |
| T-13-02 | Mitigated: no log/print referencing entry.url or str(exc) in stealth.py |
| T-13-03 | Mitigated: stdlib urlparse used exclusively in _parse_proxy_url |
| T-13-07 | Mitigated: --force-webrtc-ip-handling-policy=disable_non_proxied_udp always present in build_proxy_browser_args when entry is not None |
| T-13-08 | Mitigated: asyncio.create_task wraps all tab.send calls in Fetch handlers; add_handler before fetch.enable enforced and test-asserted |

## Self-Check: PASSED

- core/stealth.py: FOUND
- tests/test_stealth.py: FOUND
- commit dde3402: FOUND
- commit c757514: FOUND
