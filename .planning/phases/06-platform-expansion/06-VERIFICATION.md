---
phase: 06-platform-expansion
verified: 2026-05-15T00:00:00Z
status: human_needed
score: 4/4 roadmap success criteria + 8/8 requirements verified
re_verification: null
human_verification:
  - test: "Run bot end-to-end against live retailers with all five new plugins enabled"
    expected: "Each plugin's check_availability returns correctly against live PDPs; representative DOM selectors (marked TODO in source) match real markup"
    why_human: "Cannot CI-test against live retailers; selectors are representative per RESEARCH O-5 and marked TODO for runtime verification"
  - test: "Verify headless toggle visually: set platforms.walmart.headless: false while platforms.target.headless: true, run main.py"
    expected: "Walmart launches visible Chrome window; Target runs invisibly; both coexist in same process"
    why_human: "Visual/runtime behavior; nodriver browser lifecycle"
  - test: "Trigger Walmart auto_buy with SHOPBOT_ENABLE_RISKY_AUTOBUY=true to confirm one-time PerimeterX INFO log fires once"
    expected: "First call logs PerimeterX/HUMAN note; subsequent calls in same instance do NOT re-log"
    why_human: "Stateful behavior across multiple invocations; tests cover the flag flip but live runtime is the only proof"
  - test: "Trigger GameStop auto_buy and confirm CAPTCHA pause blocks only the GameStop worker thread, not the event loop"
    expected: "Other plugins continue polling while GameStop awaits stdin"
    why_human: "Concurrency behavior under real load"
---

# Phase 6: Platform Expansion Verification Report

**Phase Goal:** Five new platform plugins (Walmart, Target, GameStop, Square Enix, NewEgg) operational, each with documented anti-detection risk levels, and per-platform delay/jitter/headless configuration available across all plugins.

**Verified:** 2026-05-15
**Status:** human_needed (all automated checks pass; live-retailer DOM verification is the only outstanding item)
**Re-verification:** No (initial verification)

## Goal Achievement

### Roadmap Success Criteria

| #   | Truth                                                                                              | Status     | Evidence                                                                                                       |
| --- | -------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------- |
| 1   | All 5 new plugins load via registry without core changes; each plugin file self-contained          | VERIFIED   | plugins/shopbot_plugin_{walmart,target,gamestop,squareenix,newegg}.py present; plugin_registry.py unchanged in Phase 6 except for stagger discovery awaiting `open()`; tests/test_plugin_registry.py: 18 passed |
| 2   | platforms.walmart.min_delay/max_delay drive jitter via random.uniform without code changes         | VERIFIED   | plugin_base.py:80-82 `next_delay() -> random.uniform(self.min_delay, self.max_delay)`; main.py:216 `plugin.next_delay()`; all 5 nodriver plugins read min_delay/max_delay from platform_config in __init__ |
| 3   | platforms.amazon.headless: false launches visible Amazon while others run headless in same process | VERIFIED   | config_schema.py:27 `headless: bool = False` per-platform; driver.py:75-76 `--headless=new` (NOT bare); plugins/shopbot_plugin_amazon.py:38-43 raises ValueError when headless+login_at_startup (manual OTP guard) |
| 4   | Walmart documents PerimeterX risk; Target documents Akamai headless experimental status            | VERIFIED   | shopbot_plugin_walmart.py:73-78 one-time PerimeterX INFO; shopbot_plugin_target.py:48-52 Akamai headless WARNING; PLUGIN_DEV.md:191+ Selenium-vs-nodriver section |

**Score:** 4/4 roadmap success criteria verified

### Requirements Coverage

| Requirement | Source Plan | Description                                                                  | Status     | Evidence                                                                                          |
| ----------- | ----------- | ---------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------- |
| PLG-04      | 06-02       | Walmart plugin + PerimeterX risk doc                                         | VERIFIED   | plugins/shopbot_plugin_walmart.py; domain_pattern=["walmart.com"]; risky-autobuy gated            |
| PLG-05      | 06-03       | Target plugin; checkout experimental (Akamai)                                | VERIFIED   | plugins/shopbot_plugin_target.py; headless WARNING fires in __init__                              |
| PLG-06      | 06-04       | GameStop plugin + CAPTCHA pause                                              | VERIFIED   | plugins/shopbot_plugin_gamestop.py:107-122 `asyncio.to_thread(input, ...)` for hCaptcha            |
| PLG-07      | 06-05       | Square Enix plugin                                                           | VERIFIED   | plugins/shopbot_plugin_squareenix.py; domain_pattern=["square-enix.com","square-enix-games.com"]  |
| PLG-08      | 06-06       | NewEgg plugin                                                                | VERIFIED   | plugins/shopbot_plugin_newegg.py                                                                  |
| ANTI-01     | 06-01,06-07 | Per-platform configurable check interval with random jitter                  | VERIFIED   | config_schema.py:25-38 PlatformConfig.min_delay/max_delay + validator; main.py:216 next_delay()   |
| ANTI-02     | 06-01,06-07 | Rotating user agent strings from configurable list                           | VERIFIED   | driver.py:25-32 DEFAULT_USER_AGENTS; driver.py:66 `random.choice` on each build_driver call; AppSettings.user_agents (config_schema.py:67) |
| ANTI-03     | 06-01,06-07 | Headless mode toggle per platform                                            | VERIFIED   | config_schema.py:27 PlatformConfig.headless; driver.py:75-76 `--headless=new`; nodriver plugins pass `headless=` to uc.start |

### Locked Decisions (D-01..D-04)

| Decision | Status     | Evidence                                                                                                                  |
| -------- | ---------- | ------------------------------------------------------------------------------------------------------------------------- |
| D-01     | VERIFIED   | nodriver==0.50.3 pinned in requirements.txt:11; 5 new plugins use `import nodriver as uc`; Amazon/BestBuy still Selenium; ABC driver-agnostic (plugin_base.py has no driver type) |
| D-02     | VERIFIED   | All 5 new plugins read `os.environ.get("SHOPBOT_ENABLE_RISKY_AUTOBUY","").strip().lower() == "true"` in __init__ and short-circuit auto_buy with WARNING (grep: 5/5 hits) |
| D-03     | VERIFIED   | plugin_base.py:80-82 next_delay default; PlatformConfig.min_delay/max_delay with validator (config_schema.py:29-38)        |
| D-04     | VERIFIED   | driver.py:41-44 `build_driver(..., headless=False, user_agents=None)`; bare `--headless` NOT used (research pitfall #3)    |

### Required Artifacts (Level 1-3)

| Artifact                              | Status     | Notes                                                  |
| ------------------------------------- | ---------- | ------------------------------------------------------ |
| plugins/shopbot_plugin_walmart.py     | VERIFIED   | 118 lines, no selenium imports, ABC subclass            |
| plugins/shopbot_plugin_target.py      | VERIFIED   | 119 lines, headless Akamai WARNING in __init__         |
| plugins/shopbot_plugin_gamestop.py    | VERIFIED   | 146 lines, hCaptcha detect + to_thread(input) pause    |
| plugins/shopbot_plugin_squareenix.py  | VERIFIED   | 118 lines, dual-domain                                  |
| plugins/shopbot_plugin_newegg.py      | VERIFIED   | 114 lines                                              |
| plugin_base.py                        | VERIFIED   | open() async no-op default; next_delay() sync default; PLUGIN_API_VERSION=1 unchanged |
| plugin_registry.py                    | VERIFIED   | discover_async awaits `inst.open()` after instantiation, before next stagger (lines 188-194) |
| driver.py                             | VERIFIED   | headless kwarg + user_agents kwarg + random.choice per call |
| config_schema.py                      | VERIFIED   | PlatformConfig.min_delay/max_delay/headless + validator; AppSettings.user_agents |
| main.py                               | VERIFIED   | imports inspect; iscoroutinefunction branches in _poll_once and _attempt_purchase; poll_plugin uses plugin.next_delay() |
| plugins/PLUGIN_DEV.md                 | VERIFIED   | Selenium-vs-nodriver section at line 191; nodriver checklist; risky-autobuy gate; live-test scope |
| requirements.txt                      | VERIFIED   | nodriver==0.50.3 pinned (line 11)                       |

### Key Link Verification

| Check                                                                          | Status   | Evidence                                                                                  |
| ------------------------------------------------------------------------------ | -------- | ----------------------------------------------------------------------------------------- |
| ABC amendments additive (PLUGIN_API_VERSION still 1)                           | WIRED    | plugin_base.py:28 `PLUGIN_API_VERSION: int = 1`                                            |
| Existing Selenium plugins inherit defaults unchanged                           | WIRED    | shopbot_plugin_amazon.py / shopbot_plugin_bestbuy.py do NOT override open(); inherit no-op |
| Orchestrator coroutine handling                                                | WIRED    | main.py:138 (_attempt_purchase) + main.py:169 (_poll_once): `inspect.iscoroutinefunction` branch |
| discover_async awaits plugin.open() after each instantiation, before stagger   | WIRED    | plugin_registry.py:179-194: stagger sleep at top of loop; instantiate via to_thread; await inst.open() then continue |
| Amazon headless+OTP guard raises ValueError before build_driver                | WIRED    | shopbot_plugin_amazon.py:38-43 guard precedes line 46 `build_driver(...)` call             |
| SHOPBOT_ENABLE_RISKY_AUTOBUY gate at __init__ in all 5 new plugins             | WIRED    | grep: 31 occurrences across 6 files (5 plugins + PLUGIN_DEV.md)                            |
| Walmart one-time PerimeterX note via self._walmartRiskNoted flag               | WIRED    | shopbot_plugin_walmart.py:40,73-78                                                          |
| GameStop CAPTCHA pause via asyncio.to_thread(input)                            | WIRED    | shopbot_plugin_gamestop.py:107-111 + 117-121                                                |
| Target headless WARNING about Akamai when platform_config.headless True        | WIRED    | shopbot_plugin_target.py:48-52                                                              |
| No selenium imports in any of the 5 new nodriver plugins                       | WIRED    | grep "selenium" in plugins/: only example_plugin.py + Amazon + BestBuy + PLUGIN_DEV.md (mention) match |
| nodriver Browser.stop() inspect.isawaitable pattern in all 5 shutdown methods  | WIRED    | All 5 plugins use `result = driver.stop(); if inspect.isawaitable(result): await result` (O-3 fix) |
| PlatformConfig has min_delay/max_delay/headless + validator                    | WIRED    | config_schema.py:22-38                                                                      |
| PlatformConfig.credentials is Optional                                         | WIRED    | config_schema.py:24 `credentials: PlatformCredentials | None = None`                       |
| app.user_agents config field                                                   | WIRED    | config_schema.py:67 `user_agents: list[str] | None = None`                                  |
| build_driver uses random.choice per call                                       | WIRED    | driver.py:66 `chosen_ua = random.choice(user_agents or DEFAULT_USER_AGENTS)`               |
| PLUGIN_DEV.md nodriver vs Selenium guidance section                            | WIRED    | line 191 `## Selenium vs nodriver: choosing a driver`                                       |
| requirements.txt pins nodriver at specific version                             | WIRED    | line 11 `nodriver==0.50.3`                                                                  |

### Behavioral Spot-Checks

| Behavior                                              | Command                                                                          | Result                              | Status |
| ----------------------------------------------------- | -------------------------------------------------------------------------------- | ----------------------------------- | ------ |
| Full Phase 6 test suite (incl. all 5 new plugin tests) | `python -m pytest tests/ --ignore=tests/test_utils.py`                            | 423 passed, 1 skipped, 1 warning    | PASS   |
| All plugin import without errors                       | (covered by collection phase of pytest)                                          | 424 items collected                 | PASS   |
| Phase 1-5 regression suite still green                 | test_config_schema/credentials/driver_setup/main_smoke/models*/notifiers*/orchestrator/plugin_*/registry_stagger all green | 423 passed (no failures attributable to Phase 6) | PASS   |

### Anti-Patterns Found

| File                                | Line | Pattern                            | Severity | Impact                                                                          |
| ----------------------------------- | ---- | ---------------------------------- | -------- | ------------------------------------------------------------------------------- |
| shopbot_plugin_walmart.py           | 25   | TODO comment for live selector re-verification | Info     | Selectors representative; live verification deferred to runtime (RESEARCH O-5) |
| shopbot_plugin_target.py            | 28   | TODO comment                       | Info     | Same                                                                            |
| shopbot_plugin_gamestop.py          | 31   | TODO comment                       | Info     | Same                                                                            |
| shopbot_plugin_squareenix.py        | 33   | TODO comment                       | Info     | Same                                                                            |
| shopbot_plugin_newegg.py            | 29   | TODO comment                       | Info     | Same                                                                            |
| plugins/shopbot_plugin_newegg.py    | 15   | em dash in docstring               | Info     | CLAUDE.md says no em dashes "in any output, ever" but these live in code docstrings; not user-facing. Same pattern in target/squareenix/walmart docstrings (26 occurrences across 4 files). Not blocking. |
| tests/test_utils.py                 | 2    | Pre-existing ImportError (`from utils import make_tiny`) | Info | Pre-existing breakage unrelated to Phase 6; logged in deferred-items.md. `make_tiny` lives in main.py (line 68) |

No blockers, no warnings that affect Phase 6 goal achievement.

### Human Verification Required

1. **Live-retailer DOM smoke test for all 5 new plugins**
   - Test: Run main.py with each retailer's PDP and confirm check_availability returns correctly
   - Expected: Selectors match live markup; non-matching selectors logged as WARNING (not exception)
   - Why human: Cannot CI-test against live retailers; representative selectors are marked TODO

2. **Headless toggle visual verification**
   - Test: Set platforms.amazon.headless: false (Amazon already requires this), platforms.target.headless: true, run main.py
   - Expected: Amazon visible window; Target invisible; both poll concurrently
   - Why human: Visual behavior

3. **Walmart one-time PerimeterX note**
   - Test: SHOPBOT_ENABLE_RISKY_AUTOBUY=true, trigger Walmart auto_buy twice in same session
   - Expected: PerimeterX INFO logs once, not twice
   - Why human: Stateful runtime behavior

4. **GameStop CAPTCHA pause does not block event loop**
   - Test: Trigger GameStop auto_buy at checkout while other plugins are polling
   - Expected: Other plugins continue polling while GameStop awaits stdin
   - Why human: Real concurrency under load

### Gaps Summary

No blocking gaps. All automated checks pass:
- 8/8 requirements verified with file:line evidence
- 4/4 roadmap success criteria verified
- 4/4 locked decisions D-01..D-04 verified in source
- 423 of 424 tests pass (1 skipped is the Walmart-network skip; 1 pre-existing test_utils.py ImportError is unrelated to Phase 6, documented in deferred-items.md)
- No selenium imports in nodriver plugins, no nodriver imports in Selenium plugins (clean coexistence)
- inspect.isawaitable() pattern applied consistently across all 5 nodriver shutdown methods (O-3 fix)
- inspect.iscoroutinefunction() branch in main.py honors both async (nodriver) and sync (Selenium) plugin methods

Outstanding items are runtime/visual concerns that cannot be verified programmatically without spawning Chrome against live retailers.

### Notes / Follow-ups

- **Python 3.13 venv required for nodriver-based plugin tests.** Phase 6 tests were run with Python 3.13.13 (system interpreter). Python 3.14 has a known nodriver UTF-8 incompatibility; PLUGIN_DEV.md and CONTRIBUTING.md should document the supported Python version range for contributors who run tests locally.
- **Pre-existing test_utils.py ImportError**: `make_tiny` was moved from utils.py to main.py during Phase 4 or earlier; the test was never updated. Not a Phase 6 regression. Tracked in `.planning/phases/06-platform-expansion/deferred-items.md`. Recommended follow-up: either move `make_tiny` back to utils.py OR update the test import path in a follow-up doc commit.
- **Em dashes in plugin source docstrings**: CLAUDE.md prohibits em dashes "in any output, ever". The five new plugin files plus PLUGIN_DEV.md contain 31 em-dash occurrences inside Python docstrings/comments. These are not user-facing output, but a strict reading of the rule would flag them. Recommended action: either rewrite docstring sentences to use commas/colons, or accept as code-comment exception. Not blocking Phase 6 goal.

---

*Verified: 2026-05-15*
*Verifier: Claude (gsd-verifier)*
