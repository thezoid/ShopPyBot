---
phase: 13-anti-detection-layer-1-fingerprint-proxy
plan: "03"
subsystem: core/service, core/orchestrator, core/registry, plugins
tags: [anti-detection, proxy, stealth, tdd, fingerprint, wiring]
dependency_graph:
  requires: [core.stealth (13-01), ProxyConfig (13-02)]
  provides: [proxy wiring end-to-end, stealth at every browser startup]
  affects: [all 8 plugins, core/orchestrator, core/registry, core/service]
tech_stack:
  added: []
  patterns:
    - Per-instance proxy scoping via registry.assign_proxy (getattr defaults, no ABC bump)
    - Fail-loud exhaustion gate before nodriver.start (Pitfall 2)
    - apply_stealth before first navigation (Pitfall 8)
    - Ban-detect body scan with pool.record_failure, restart-only rotation (ANTI-05)
    - Proxy + WebRTC args merged with existing UA args in Phase-6 plugins
key_files:
  created:
    - tests/test_proxy_wiring.py
  modified:
    - core/service.py
    - core/orchestrator.py
    - core/registry.py
    - plugins/shopbot_plugin_amazon.py
    - plugins/shopbot_plugin_bestbuy.py
    - plugins/shopbot_plugin_walmart.py
    - plugins/shopbot_plugin_target.py
    - plugins/shopbot_plugin_gamestop.py
    - plugins/shopbot_plugin_squareenix.py
    - plugins/shopbot_plugin_newegg.py
    - tests/conftest.py
decisions:
  - "service.py uses len(cfg.proxy.urls) for pool_size (avoids constructing a live pool at BotService init time; pool owned by async_main)"
  - "assign_proxy advances the pool index each call so consecutive calls yield distinct proxies (round-robin per-instance scoping)"
  - "Ban-detect in Amazon only (T-13-11 accepted for phase-6 plugins; BestBuy body scan deferred, same accept disposition)"
  - "conftest mock_nodriver_start fixture gets AsyncMock on main_tab.send (Rule 1 -- apply_stealth needs awaitable send)"
metrics:
  duration: "13 minutes"
  completed_date: "2026-06-09"
  tasks: 3
  files: 11
---

# Phase 13 Plan 03: Proxy + Stealth Wiring Summary

One-liner: Stealth applied at every browser startup and per-instance proxy assignment wired from registry through orchestrator into all 8 plugins, with fail-loud exhaustion guard and ban-detect failure recording.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | Failing proxy wiring tests | aa41ac3 | tests/test_proxy_wiring.py |
| GREEN | Wire stealth + proxy into all targets | 7fee8e7 | core/service.py, core/orchestrator.py, core/registry.py, 8 plugins, tests/conftest.py |

## Verification Results

- `python -m pytest tests/test_proxy_wiring.py -q`: 34 passed
- `python -m pytest -q`: 414 passed, 2 skipped (baseline 380 + 34 new; 0 regressions)
- `python -c "import core.plugin_base as p; assert p.PLUGIN_API_VERSION==2"`: OK
- `python -c "assert 'Proxy rotation: enabled, pool_size=' in open('core/service.py').read()"`: OK
- `core/registry.py` defines `def assign_proxy`
- `core/orchestrator.py` references `ProxyPool`

## TDD Gate Compliance

- RED gate: commit aa41ac3 -- 34 tests failing (PluginRegistry missing proxy_pool kwarg; service missing log line; plugin setup missing stealth/proxy)
- GREEN gate: commit 7fee8e7 -- all 34 tests pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] conftest mock_nodriver_start main_tab.send not AsyncMock**
- **Found during:** Task 2 (GREEN) full suite run -- 29 existing plugin tests failed
- **Issue:** `mock_nodriver_start` fixture returned `MagicMock()` for `browser`, whose `main_tab.send` was a plain `MagicMock`. After wiring, `apply_stealth` awaits `tab.send(cdp.page.enable())`, raising `TypeError: object MagicMock can't be used in 'await' expression` in all 29 existing plugin setup tests.
- **Fix:** Added `recorder.browser.main_tab = MagicMock(); recorder.browser.main_tab.send = AsyncMock()` to `mock_nodriver_start` fixture in `tests/conftest.py`.
- **Files modified:** `tests/conftest.py`
- **Commit:** 7fee8e7

**2. [Rule 1 - Bug] test_amazon_ban_signal_records_failure tab.find not mocked**
- **Found during:** Task 2 test authoring -- the test missed mocking `tab.find` which `detect_captcha` calls
- **Fix:** Added `tab.find = AsyncMock(return_value=None)` alongside `tab.select` in the ban-detect test.
- **Files modified:** `tests/test_proxy_wiring.py`
- **Commit:** 7fee8e7 (bundled with GREEN commit)

## Known Stubs

None. All proxy wiring paths are fully implemented and tested.

## Threat Flags

No new trust boundaries introduced beyond those in the plan threat model.

| Threat ID | Mitigation Status |
|-----------|------------------|
| T-13-09 | Mitigated: startup log uses len(urls) integer only; test asserts no credential substring |
| T-13-10 | Mitigated: fail-loud RuntimeError before nodriver.start when pool exhausted; test asserts start NOT called |
| T-13-07 | Mitigated: build_proxy_browser_args always appends disable_non_proxied_udp; per-plugin tests assert flag present |
| T-13-02 | Mitigated: all proxy-path excepts log exc.__class__.__name__ only |
| T-13-11 | Accepted: untrusted body spoof worst case is one extra record_failure; restart-only bounds blast radius |

## Self-Check: PASSED

- tests/test_proxy_wiring.py: FOUND
- core/service.py: FOUND (contains 'Proxy rotation: enabled, pool_size=')
- core/orchestrator.py: FOUND (contains 'ProxyPool')
- core/registry.py: FOUND (contains 'def assign_proxy')
- plugins/shopbot_plugin_amazon.py: FOUND
- plugins/shopbot_plugin_bestbuy.py: FOUND
- plugins/shopbot_plugin_walmart.py: FOUND
- plugins/shopbot_plugin_target.py: FOUND
- plugins/shopbot_plugin_gamestop.py: FOUND
- plugins/shopbot_plugin_squareenix.py: FOUND
- plugins/shopbot_plugin_newegg.py: FOUND
- tests/conftest.py: FOUND
- commit aa41ac3 (RED): FOUND
- commit 7fee8e7 (GREEN): FOUND
