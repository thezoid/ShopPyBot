---
phase: 13-anti-detection-layer-1-fingerprint-proxy
verified: 2026-06-09T12:00:00Z
status: human_needed
score: 5/5
overrides_applied: 0
human_verification:
  - test: "Open a real browser session with a proxy configured and navigate to a product page on Amazon or BestBuy. Check the nodriver tab's CDP targets to confirm stealth patches are applied (navigator.plugins.length > 0, window.chrome defined) using a fingerprinting probe such as CreepJS."
    expected: "window.chrome is defined (not undefined), navigator.plugins has 3 entries, navigator.languages is ['en-US','en'], screen.width/height are 1920/1080 or plausible non-zero values. The fingerprint probe shows reduced Layer 2 bot signals compared to a vanilla headless session."
    why_human: "Fingerprint signal quality (ANTI-08) requires a live browser against a real or emulated fingerprint probe. No in-process test can verify what a real fingerprinting service detects. CreepJS or Bot-Sanity require a real browser run."
  - test: "Configure two proxies in config.yml (proxy.enabled=true), run the bot against an item URL, manually trigger a 403/429 ban condition on one proxy (or mock via mitmproxy), and confirm the bot records the failure and the second proxy is used on the next restart."
    expected: "First proxy accumulates failures up to max_failures and enters cooldown. Second proxy is assigned on the next staggered setup cycle. Log shows 'Proxy rotation: enabled, pool_size=2' at startup (no credentials). The real IP is not visible when using a proxy (check via whatismyip endpoint)."
    why_human: "Live proxy rotation (ANTI-04/ANTI-05) requires a real proxy server and a ban endpoint. The ban-detect unit tests verify the record_failure call path, but confirming actual rotation and IP hiding requires a live proxy tunnel. No CI-safe substitute exists."
---

# Phase 13: Anti-Detection Layer 1 — Fingerprint + Proxy Verification Report

**Phase Goal:** Users can enable proxy rotation and the bot applies a JS fingerprint stealth patch at browser startup, measurably reducing Layer 2 bot signals.
**Verified:** 2026-06-09T12:00:00Z
**Status:** human_needed
**Re-verification:** No (initial verification)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Bot applies window.chrome, navigator.plugins, navigator.languages, and screen-dimension patches via core/stealth.py at every browser startup with no plugin ABC version bump | VERIFIED | STEALTH_JS contains all 4 patches (lines 31-81 of core/stealth.py). apply_stealth wired in all 7 plugin setup() methods via import and await before first navigation. PLUGIN_API_VERSION = 2 unchanged in core/plugin_base.py. 59/59 stealth + proxy tests pass. |
| 2 | User can enable proxy rotation via an opt-in proxy: config section (disabled by default) listing scheme://host:port URLs; bot logs 'Proxy rotation: enabled, pool_size=N' at startup | VERIFIED | ProxyConfig(enabled=False) is the default in core/config_schema.py line 227. sample.config.yml has proxy: section with enabled: false and placeholder-only example URLs. Exact literal "Proxy rotation: enabled, pool_size=" present in core/service.py line 46. test_proxy_startup_log_no_credentials and test_proxy_disabled_no_log both pass. |
| 3 | Bot detects ban signals (HTTP 403/429/503, challenge-redirect, block-phrase body) and rotates to the next proxy, retiring a proxy after N consecutive failures for a configurable cooldown period | VERIFIED | _is_ban_response in core/stealth.py checks {403,429,503} and 6 body phrases (8 KB cap, WR-04 fix). All 7 plugins call self._handle_ban(body_text) in check_availability. _handle_ban is in RetailerPlugin ABC (core/plugin_base.py lines 21-33) -- shared helper added to satisfy CR-02. record_failure/cooldown state machine in _ProxyEntry tested by test_proxypool_retires_after_max_failures and test_proxypool_cooldown_reentry. |
| 4 | WebRTC Chrome preferences are set at browser launch to prevent real-IP leaks through the proxy tunnel | VERIFIED | build_proxy_browser_args always appends "--force-webrtc-ip-handling-policy=disable_non_proxied_udp" when entry is not None (core/stealth.py line 276). test_build_proxy_browser_args_includes_webrtc asserts the flag is present. Per-plugin proxy tests assert the flag appears in browser_args when proxy is assigned. |
| 5 | Each proxy is scoped to its plugin instance (self._proxy) and rotated only at browser restart, not mid-session | VERIFIED | registry.assign_proxy() sets plugin._proxy before each plugin.setup() in _staggered_setup (orchestrator.py line 186). Per-plugin tests assert distinct host_ports per plugin instance. ban-detect path calls pool.record_failure but does NOT call teardown or setup -- rotation is restart-only. test_registry_assign_proxy_distinct_per_plugin and test_amazon_ban_signal_records_failure pass. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/stealth.py` | STEALTH_JS, apply_stealth, _ProxyEntry, ProxyPool, _parse_proxy_url, _is_ban_response, build_proxy_browser_args, setup_proxy_auth | VERIFIED | All 8 symbols exported. File is 325 lines (exceeds 300-line CLAUDE.md cap by 25 lines; body is 82-line STEALTH_JS constant that cannot be split -- see note below). |
| `tests/test_stealth.py` | 18+ named unit tests for all stealth symbols | VERIFIED | 19 named test functions present covering all plan-required behaviors. All pass. |
| `core/config_schema.py` | ProxyConfig nested under AppConfig | VERIFIED | class ProxyConfig at line 219, AppConfig.proxy field at line 266. field_validator for URL format (WR-05 fix) present. |
| `sample.config.yml` | Documented, disabled-by-default proxy: section | VERIFIED | proxy: section with enabled: false, placeholder example, max_failures, cooldown_secs, credential-safety comment. |
| `tests/test_proxy_config.py` | 4 unit tests for proxy config parsing | VERIFIED | test_proxyconfig_defaults, test_proxyconfig_parses_from_yaml, test_proxyconfig_urls_with_creds_parse, test_appconfig_has_proxy_field all pass. |
| `core/service.py` | Exact "Proxy rotation: enabled, pool_size=N" startup log | VERIFIED | Literal present at line 46. |
| `core/orchestrator.py` | ProxyPool construction from cfg.proxy + pass to registry + assign in _staggered_setup | VERIFIED | async_main builds proxy_pool at lines 226-232; passes to PluginRegistry at line 233; _staggered_setup calls registry.assign_proxy(plugin) at line 186. |
| `core/registry.py` | proxy_pool param + assign_proxy() helper | VERIFIED | __init__ accepts proxy_pool=None (line 67); assign_proxy defined at lines 74-90. WR-03 addressed: assign_proxy NOT called in setup_for_items (docstring explicitly documents caller responsibility). |
| `tests/test_proxy_wiring.py` | Coverage for all Plan 03 behaviors | VERIFIED | 29 test functions covering service log, registry assign, per-plugin stealth/proxy/auth/fail-loud for all 7 plugins. All pass. |
| `plugins/shopbot_plugin_amazon.py` | apply_stealth, proxy args, WebRTC, ban-detect | VERIFIED | apply_stealth at line 72 (before first get). _handle_ban at line 114. fail-loud guard at lines 57-59. build_proxy_browser_args at line 68. |
| `plugins/shopbot_plugin_bestbuy.py` | apply_stealth, proxy args, WebRTC, ban-detect | VERIFIED | apply_stealth at line 57. _handle_ban at line 81 (CR-02 fix). fail-loud guard at lines 42-44. build_proxy_browser_args at line 53. |
| `plugins/shopbot_plugin_walmart.py` | apply_stealth, proxy merged with UA, ban-detect | VERIFIED | apply_stealth at line 75. _handle_ban at line 98. build_proxy_browser_args merged into UA args at line 68. |
| `plugins/shopbot_plugin_target.py` | Same pattern as walmart | VERIFIED | apply_stealth at line 77. _handle_ban at line 100. build_proxy_browser_args merged at line 70. |
| `plugins/shopbot_plugin_gamestop.py` | Same pattern as walmart | VERIFIED | apply_stealth at line 77. _handle_ban at line 100. Confirmed by grep. |
| `plugins/shopbot_plugin_squareenix.py` | Same pattern as walmart | VERIFIED | apply_stealth at line 78. _handle_ban at line 101. Confirmed by grep. |
| `plugins/shopbot_plugin_newegg.py` | Same pattern as walmart | VERIFIED | apply_stealth at line 76. _handle_ban at line 99. Confirmed by grep. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| apply_stealth | cdp.page.add_script_to_evaluate_on_new_document | tab.send | WIRED | core/stealth.py line 92: `await tab.send(cdp.page.add_script_to_evaluate_on_new_document(STEALTH_JS))` |
| _ProxyEntry.record_failure | retired_until cooldown timestamp | time.monotonic() + cooldown | WIRED | core/stealth.py line 170: `self.retired_until = time.monotonic() + cooldown_secs` |
| build_proxy_browser_args | WebRTC leak prevention flag | browser_args list | WIRED | core/stealth.py line 276: "--force-webrtc-ip-handling-policy=disable_non_proxied_udp" always present when entry is not None |
| core/orchestrator.py async_main | ProxyPool.from_urls(cfg.proxy.urls) | cfg.proxy.enabled gate | WIRED | orchestrator.py lines 226-232: gate on cfg.proxy.enabled, then from_urls |
| registry.assign_proxy / _staggered_setup | plugin._proxy = pool.advance() | per-instance assignment before plugin.setup() | WIRED | orchestrator.py line 186: registry.assign_proxy(plugin) before plugin.setup(); registry.py line 90: plugin._proxy = self._proxy_pool.advance() |
| plugin.setup() | apply_stealth(self.driver.main_tab) | after nodriver.start() | WIRED | All 7 plugins: apply_stealth called on self.driver.main_tab immediately after nodriver.start() completes |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| core/stealth.py apply_stealth | STEALTH_JS | module constant | Yes (inline IIFE, not dynamic) | FLOWING |
| ProxyPool | cfg.proxy.urls | AppConfig parsed from config.yml via Pydantic/YAML | Yes (YAML-sourced list) | FLOWING |
| BotService startup log | len(cfg.proxy.urls) | AppConfig.proxy.urls (counted, not logged) | Yes (integer count only) | FLOWING |
| Plugin ban detection | body_text from tab.evaluate | Live page DOM text | Yes (live CDP evaluation) | FLOWING (requires live browser -- see human verification) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| PLUGIN_API_VERSION unchanged at 2 | `python -c "import core.plugin_base as p; assert p.PLUGIN_API_VERSION==2; print('OK')"` | OK | PASS |
| Exact startup log literal in service.py | `python -c "assert 'Proxy rotation: enabled, pool_size=' in open('core/service.py').read(); print('OK')"` | OK | PASS |
| sample.config.yml proxy.enabled defaults false | `python -c "import yaml; d=yaml.safe_load(open('sample.config.yml')); assert d.get('proxy',{}).get('enabled') is False; print('OK')"` | OK | PASS |
| Full test suite | `python -m pytest -q` | 419 passed, 2 skipped | PASS |
| Stealth + proxy tests targeted | `python -m pytest tests/test_stealth.py tests/test_proxy_wiring.py tests/test_proxy_config.py -q` | 59 passed | PASS |

### Probe Execution

Step 7c: SKIPPED -- no `scripts/*/tests/probe-*.sh` files exist in this repository. No probes were declared in any PLAN or SUMMARY for this phase.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| ANTI-04 | 13-01, 13-02, 13-03 | Opt-in proxy rotation, sticky per-instance sessions, configurable pool URLs | SATISFIED | ProxyConfig in config_schema.py; ProxyPool in stealth.py; per-plugin _proxy assignment in registry; WebRTC flag in build_proxy_browser_args; startup log in service.py |
| ANTI-05 | 13-01, 13-03 | Ban signal detection (403/429/503, block-phrase body), proxy rotation, retire/cooldown | SATISFIED | _is_ban_response in stealth.py (8 KB cap); _handle_ban in plugin_base.py (shared, all 7 plugins); record_failure/cooldown in _ProxyEntry; pool exhaustion = None + fail-loud in all plugin setup() |
| ANTI-08 | 13-01, 13-03 | JS fingerprint stealth patch at browser startup, no ABC bump | SATISFIED | STEALTH_JS with 4 patches; apply_stealth wired in all 7 plugin setup() methods before first navigation; PLUGIN_API_VERSION = 2 unchanged |

No orphaned requirements: all 3 phase requirements (ANTI-04, ANTI-05, ANTI-08) are satisfied. REQUIREMENTS.md marks them [x].

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| core/stealth.py | whole file | File is 325 lines, exceeds 300-line CLAUDE.md cap | Info | 25-line overage is attributable to the 82-line STEALTH_JS constant (verbatim JS IIFE that cannot be meaningfully split) plus CR-04 fix adding _live_tasks set and task-retention scaffolding. The logical code is well under the cap. No actionable debt marker. |
| core/service.py | 20 | Dead import: `from core.stealth import ProxyPool` (ProxyPool not used in service.py) | Info | IN-02 from REVIEW.md; acknowledged; not a correctness issue. Pool construction lives in orchestrator.py as designed. |
| plugins/shopbot_plugin_bestbuy.py | 147 | TODO comment: `.a-dropdown-prompt` selector validation | Info | Pre-existing from Phase 1 UAT; out of scope for this phase. Not introduced by Phase 13. |
| plugins/shopbot_plugin_walmart.py | multiple | TODO: verify selectors against live walmart.com | Info | Pre-existing; out of scope. Not introduced by Phase 13. |
| plugins/shopbot_plugin_target.py | multiple | TODO: verify selectors | Info | Pre-existing; out of scope. Not introduced by Phase 13. |

No TBD, FIXME, or XXX markers found in any Phase 13 files.

### Human Verification Required

All 5 roadmap success criteria pass automated verification. Two live-environment checks remain that cannot be automated without a real browser, proxy server, and fingerprint probe service:

#### 1. Fingerprint Stealth Patch Effectiveness (ANTI-08)

**Test:** Run the bot against a CreepJS fingerprint probe URL (or https://bot.sanity.io) with `headless=true` in config. Inspect the fingerprint report in the browser.

**Expected:** window.chrome is defined, navigator.plugins shows 3 entries, navigator.languages is ['en-US','en'], screen dimensions are 1920x1080. The probe score shows measurably fewer "headless detected" signals compared to an unpatched baseline session.

**Why human:** Fingerprint probe results require a real Chromium process. The CDP injection path (apply_stealth -> cdp.page.add_script_to_evaluate_on_new_document) is fully verified by unit tests with mocks, but actual signal reduction can only be confirmed with a live browser against a real probe.

#### 2. Live Proxy Rotation and IP Hiding (ANTI-04/ANTI-05)

**Test:** Configure two proxies in config.yml (proxy.enabled=true). Run the bot against an Amazon or BestBuy item URL. Manually induce a ban on proxy 1 by hitting max_failures (either by a ban-returning page or directly calling pool.record_failure in a REPL). Restart the bot and confirm proxy 2 is assigned and the real IP is not exposed.

**Expected:** Startup log shows "Proxy rotation: enabled, pool_size=2" with no credentials. After proxy 1 is retired, the next restart assigns proxy 2. Checking the effective outbound IP (e.g. via https://httpbin.org/ip navigated by the bot) shows the proxy IP, not the host machine IP. WebRTC leak probe confirms no real-IP UDP leak.

**Why human:** Requires a real proxy server reachable from the test machine. IP hiding is a property of the network layer and cannot be asserted by inspecting Python code or mock objects.

### Gaps Summary

No gaps. All 5 roadmap success criteria are verified against the codebase. The `human_needed` status reflects two live-environment checks (fingerprint probe and live proxy IP verification) that are architecturally correct and fully unit-tested but require a real browser run to confirm end-to-end signal reduction.

Note on core/stealth.py line count: The file is 325 lines, 25 over the CLAUDE.md 300-line cap. The overage is the STEALTH_JS constant (82 lines of verbatim JS) plus the CR-04 task-retention fix. The logical Python code excluding the JS constant is approximately 240 lines. This is not a behavior gap but is worth noting for the next file-size audit.

---

_Verified: 2026-06-09T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
