---
phase: 02-plugin-migration
plan: 04
type: execute
wave: 2
depends_on: ["01", "02", "03"]
files_modified:
  - main.py
  - amazon_bot.py
  - bestbuy_bot.py
  - tests/test_main_smoke.py
autonomous: true
requirements:
  - CORE-03
  - CORE-04
  - PLG-01
  - PLG-02
tags:
  - integration
  - main
  - hard-cut
  - python

must_haves:
  truths:
    - "main.py imports from plugin_registry instead of amazon_bot / bestbuy_bot"
    - "main.py calls plugin_registry.discover(Path('plugins'), app_config=app_config, cvvs=cvvs) once at startup"
    - "main.py calls plugin_registry.verify_coverage(registry, app_config.available.items) between discovery and login (fail-fast on missing plugin)"
    - "main.py iterates the registry and calls plugin.login(app_config) for every plugin where plugin.login_at_startup is True (D-03)"
    - "main.py polling loop dispatches via plugin = route_url(link, registry); plugin.check_availability(link); skipping when plugin is None"
    - "main.py wraps plugin.check_availability and plugin.auto_buy in try/except that logs ERROR and continues the loop (runtime isolation, not D-04)"
    - "main.py contains no `if 'amazon.com' in link` chain and no `_handle_amazon`/`_handle_bestbuy` helpers"
    - "amazon_bot.py no longer exists in the repo (D-02 hard cut)"
    - "bestbuy_bot.py no longer exists in the repo (D-02 hard cut)"
    - "main.py no longer imports detect_captcha, check_amazon_item, auto_buy_amazon_item, check_bestbuy_item, or auto_buy_bestbuy_item"
    - "Test mode behavior preserved: auto_buy is only attempted when item.auto_buy is True; plugins read test_mode from config.debug.test_mode internally"
    - "open_browser behavior preserved: when item.auto_buy is False and item is available, main.py opens webbrowser if app_config.open_browser is True"
  artifacts:
    - path: "main.py"
      provides: "Plugin-registry-driven entrypoint replacing the amazon/bestbuy hardcoded dispatch"
      contains: "plugin_registry"
      min_lines: 80
    - path: "tests/test_main_smoke.py"
      provides: "Smoke tests asserting registry integration + legacy module removal"
      min_lines: 60
  key_links:
    - from: "main.py"
      to: "plugin_registry.discover"
      via: "single call at startup before login orchestration"
      pattern: "plugin_registry.*discover|from plugin_registry import.*discover"
    - from: "main.py"
      to: "plugin_registry.verify_coverage"
      via: "called after discover, before login"
      pattern: "verify_coverage"
    - from: "main.py"
      to: "plugin_registry.route_url"
      via: "called once per item per poll iteration"
      pattern: "route_url"
---

<objective>
Atomically swap `main.py` to drive the polling loop via the plugin registry AND delete the legacy `amazon_bot.py` and `bestbuy_bot.py` modules per D-02. This is the wave-2 integration plan: depends on Plans 01 (registry exists), 02 (AmazonPlugin exists), and 03 (BestBuyPlugin exists with PLG-02 fix). After this plan ships, the bot has no direct knowledge of Amazon or BestBuy — everything goes through `route_url`.

Purpose: D-02 mandates a hard cut. With both new plugins green from wave 1, this plan removes the legacy dispatch (`if "amazon.com" in link` chain), removes the `_handle_amazon`/`_handle_bestbuy` helpers, removes the `from amazon_bot import ...` / `from bestbuy_bot import ...` lines, deletes the two legacy modules, and replaces all of it with `discover` -> `verify_coverage` -> per-plugin startup login -> per-item `route_url` dispatch. The polling loop wraps each plugin call in try/except so a single-URL runtime failure does not crash the bot.

Output: rewritten `main.py`, deleted `amazon_bot.py`, deleted `bestbuy_bot.py`, smoke tests confirming the cut.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/02-plugin-migration/02-CONTEXT.md
@.planning/phases/02-plugin-migration/02-RESEARCH.md
@.planning/phases/02-plugin-migration/02-01-registry-and-abc-amendment-PLAN.md
@.planning/phases/02-plugin-migration/02-02-amazon-plugin-PLAN.md
@.planning/phases/02-plugin-migration/02-03-bestbuy-plugin-PLAN.md
@main.py
@plugin_registry.py
@plugin_base.py
@config_schema.py
@credentials.py
@driver.py
@logger.py
@models.py
@utils.py
</context>

<interfaces>
Target `main()` shape (RESEARCH Q6 lines 330-365 is the reference):

```python
def main():
    try:
        app_config = AppConfig()
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)

    configure_logger(app_config.debug.logging_level)
    writeLog("Starting ShopPyBot", "INFO")

    cvvs = collect_cvvs(app_config)

    # Chromedriver path resolution stays in main.py; passed to registry via app_config.
    app_config.selenium.driver_path = get_chromedriver_path(app_config.selenium.driver_path)

    registry = discover(Path("plugins"), app_config=app_config, cvvs=cvvs)
    verify_coverage(registry, app_config.available.items)

    for plugin in registry:
        if plugin.login_at_startup:
            plugin.login(app_config)

    initialize_db()
    items = [
        (it.name, it.link, it.auto_buy, it.quantity, False)
        for it in app_config.available.items
    ]
    add_items(items)

    open_browser = app_config.open_browser
    test_mode = app_config.debug.test_mode

    while True:
        writeLog("Starting new iteration of item checks", "INFO")
        for item in get_items():
            name, link, auto_buy, quantity, purchased = item
            if purchased:
                writeLog(f"{name} has already been purchased", "INFO")
                continue
            plugin = route_url(link, registry)
            if plugin is None:
                writeLog(f"Unsupported URL (no plugin): {link}", "WARNING")
                continue
            _poll_one(plugin, name, link, auto_buy, app_config, open_browser)


def _poll_one(plugin, name, link, auto_buy, app_config, open_browser):
    try:
        available = plugin.check_availability(link)
    except Exception as e:
        writeLog(
            f"Plugin {type(plugin).__name__} raised on check_availability for {link}: {e}",
            "ERROR",
        )
        return
    if not available:
        writeLog(f"{name} is not available", "INFO")
        return
    play_available_sound()
    writeLog(f"{name} is available: {make_tiny(link)}", "SUCCESS")
    if auto_buy:
        try:
            plugin.auto_buy(link, app_config)
            play_buy_sound()
        except Exception as e:
            writeLog(
                f"Plugin {type(plugin).__name__} raised on auto_buy for {link}: {e}",
                "ERROR",
            )
        return
    writeLog(f"{name} is available but auto-buy is disabled", "INFO")
    if open_browser:
        webbrowser.open(link)
```

Imports to remove from `main.py`:
- `from amazon_bot import auto_buy_amazon_item, check_amazon_item, detect_captcha` (line 19)
- `from bestbuy_bot import auto_buy_bestbuy_item, check_bestbuy_item` (line 20)

Imports to add to `main.py`:
- `from pathlib import Path`
- `from plugin_registry import discover, route_url, verify_coverage`

Functions to remove from `main.py`:
- `_handle_amazon` (lines 50-68)
- `_handle_bestbuy` (lines 71-89)

Files to delete (git rm):
- `amazon_bot.py`
- `bestbuy_bot.py`

`test_mode` is NOT passed to plugins explicitly. Per Plans 02 and 03, each plugin reads
`config.debug.test_mode` itself from the `config` arg to `auto_buy`. Main.py only checks
`item.auto_buy` (per-item flag), not `test_mode`, before calling `plugin.auto_buy(link, app_config)`.
The plugin's `auto_buy` short-circuits in test_mode internally (preserves the legacy
"skip final purchase click" semantics).

The `play_notification_sound` call in legacy `_handle_amazon` line 55 (CAPTCHA alert) is no
longer needed in main.py — AmazonPlugin.check_availability now calls `self.detect_captcha()`
inline and handles the pause itself (Plan 02 task 2 spec).
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write RED smoke tests for registry integration + legacy removal</name>
  <files>tests/test_main_smoke.py</files>
  <read_first>
    - main.py (current state, before refactor)
    - .planning/phases/02-plugin-migration/02-RESEARCH.md (Q6 main.py target shape; validation Wave 0 map)
    - .planning/phases/01-foundations-security/01-06-SUMMARY.md (if present — to see what tests/test_main_smoke.py looks like today; this plan EXTENDS that file)
  </read_first>
  <behavior>
    Add the following tests to `tests/test_main_smoke.py` (extend if file exists, create if not):
      - test_amazon_bot_module_removed: assert pathlib.Path("amazon_bot.py").exists() is False
      - test_bestbuy_bot_module_removed: assert pathlib.Path("bestbuy_bot.py").exists() is False
      - test_main_imports_plugin_registry: parse main.py with ast; assert at least one ImportFrom node with module == "plugin_registry"
      - test_main_does_not_import_legacy_bots: ast walk; assert NO ImportFrom node with module in {"amazon_bot", "bestbuy_bot"}
      - test_main_has_no_handle_amazon: ast walk; assert NO FunctionDef named "_handle_amazon" or "_handle_bestbuy"
      - test_main_calls_discover: ast walk; assert at least one Call to a Name "discover" inside the FunctionDef "main"
      - test_main_calls_verify_coverage: ast walk; assert at least one Call to a Name "verify_coverage" inside "main"
      - test_main_calls_route_url: ast walk; assert at least one Call to a Name "route_url" anywhere in main.py
      - test_main_no_amazon_string_dispatch: source-grep; assert the strings `"amazon.com" in link` and `"bestbuy.com" in link` do NOT appear in main.py (case-sensitive)
      - test_main_login_at_startup_loop: ast walk; assert at least one Attribute access `login_at_startup` AND a Call to `.login(` inside `main` (proves D-03 wiring)
  </behavior>
  <action>
    1. Read existing `tests/test_main_smoke.py` if it exists (Phase 1 may have created it).
       If it does not exist, create it. If it exists, append new tests; do not modify or
       remove existing Phase 1 tests.

    2. Add the 10 tests listed in <behavior>. Use a single AST parse helper at module scope:
       ```python
       import ast
       import pathlib

       MAIN_FILE = pathlib.Path("main.py")

       def _main_ast():
           return ast.parse(MAIN_FILE.read_text())

       def _walk_funcs(tree, name):
           return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
       ```

    3. Run `rtk pytest -x -q tests/test_main_smoke.py`. Expect failures on:
       - `test_amazon_bot_module_removed` (file still exists)
       - `test_bestbuy_bot_module_removed` (file still exists)
       - `test_main_imports_plugin_registry` (current main.py does not import it)
       - `test_main_does_not_import_legacy_bots` (current main.py imports both)
       - `test_main_has_no_handle_amazon` (helpers still present)
       - the four ast-Call tests (no calls yet)
       - `test_main_no_amazon_string_dispatch` (strings still present)
       - `test_main_login_at_startup_loop` (no login_at_startup access)

       All 10 should FAIL — this is the intended RED state.
  </action>
  <verify>
    <automated>rtk pytest tests/test_main_smoke.py 2>&1 | rtk grep -E "FAILED|amazon_bot.py.*exists|plugin_registry"</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_main_smoke.py` exists with the 10 new tests appended
    - Existing Phase 1 tests in the file (if any) are unchanged
    - `rtk pytest tests/test_main_smoke.py` shows 10 failures matching the RED expectations above
    - No test imports from `amazon_bot` or `bestbuy_bot` directly
  </acceptance_criteria>
  <done>Smoke tests committed in RED state</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Refactor main.py + delete legacy bots (GREEN, hard cut)</name>
  <files>main.py, amazon_bot.py, bestbuy_bot.py</files>
  <read_first>
    - tests/test_main_smoke.py (RED tests from Task 1)
    - main.py (current state — to be rewritten)
    - .planning/phases/02-plugin-migration/02-RESEARCH.md (Q6 target shape, pitfall 10 on runtime exceptions)
    - plugin_registry.py (Plan 01 output: discover/route_url/verify_coverage signatures)
    - plugins/shopbot_plugin_amazon.py (Plan 02 output)
    - plugins/shopbot_plugin_bestbuy.py (Plan 03 output)
  </read_first>
  <behavior>
    - All 10 new tests in tests/test_main_smoke.py pass
    - Full pytest suite passes (no Phase 1 or Phase 2 regressions)
    - `main.py` no longer imports anything from `amazon_bot` or `bestbuy_bot`
    - `amazon_bot.py` and `bestbuy_bot.py` no longer exist in the repo
    - `python -c "import ast; ast.parse(open('main.py').read())"` succeeds (file is valid Python)
  </behavior>
  <action>
    1. Rewrite `main.py`. Replace the existing file body with the structure shown in
       <interfaces>. Specifically:
       - Remove imports on current lines 19-20 (`from amazon_bot import ...` and `from bestbuy_bot import ...`)
       - Remove functions `_handle_amazon` (lines 50-68) and `_handle_bestbuy` (lines 71-89)
       - Modify the existing `from utils import play_available_sound, play_buy_sound, play_notification_sound`
         to drop `play_notification_sound` only (target line: `from utils import play_available_sound, play_buy_sound`).
         `play_available_sound` and `play_buy_sound` are still called by `_poll_one` per <interfaces>;
         `play_notification_sound`'s only legacy call site was inside `_handle_amazon` and AmazonPlugin now owns CAPTCHA alerts internally (Plan 02).
       - Add `from pathlib import Path`
       - Add `from plugin_registry import discover, route_url, verify_coverage`
       - Rewrite `main()` to match <interfaces> target. Keep `get_chromedriver_path` and
         `make_tiny` helpers in main.py (they are main-only concerns).
       - Add the `_poll_one` helper to keep `main()` under 30 lines while still enforcing
         CLAUDE.md function-size constraints.

    2. Delete `amazon_bot.py` and `bestbuy_bot.py`:
       ```
       rtk git rm amazon_bot.py bestbuy_bot.py
       ```
       Do NOT preserve them under `_deprecated/`. D-02 mandates a hard cut.

    3. Verify constraints:
       - `main()` and `_poll_one()` each under 30 lines
       - `main.py` under 300 lines
       - No `play_notification_sound` import in main.py if unused
       - No `webdriver.Chrome` direct instantiation in main.py (it has not been there since Phase 1; this is a sanity check)
       - The build_driver call removed from main.py — driver construction now lives inside each plugin (PLG-03)

    Important caveat: legacy `main.py` line 105 does `driver = build_driver(driver_path)` and
    line 125 passes `driver` to `_handle_amazon`. After this refactor, main.py NO LONGER
    constructs a top-level driver. Each plugin owns its own driver via __init__. Remove the
    `driver = build_driver(driver_path)` line. The driver_path resolution (lines 104) is
    still needed but the resolved path is stored back on app_config.selenium.driver_path
    so the registry can pass it to each plugin during discovery.

    4. Run `rtk pytest -x -q tests/test_main_smoke.py`. All 10 new tests pass; any pre-existing
       Phase 1 smoke tests also remain green.

    5. Run full suite `rtk pytest -x -q`. Expected outcome: every Phase 1 + Phase 2 test passes.

    6. Static sanity check: `python -c "import ast; ast.parse(open('main.py').read())"` exits 0.

    7. Do NOT run `python main.py` (would spawn Chrome and start polling). The smoke tests are
       the canonical verification for this plan; a live run is the verify-work checkpoint at
       phase close, not a per-plan gate.
  </action>
  <verify>
    <automated>rtk pytest -x -q tests/test_main_smoke.py</automated>
    <automated>python -c "import ast; ast.parse(open('main.py').read()); print('main.py syntactically valid')"</automated>
    <automated>rtk find amazon_bot.py 2>&1 | rtk grep -E "No such file|^$"</automated>
    <automated>rtk find bestbuy_bot.py 2>&1 | rtk grep -E "No such file|^$"</automated>
    <automated>rtk grep -n "from amazon_bot\|from bestbuy_bot\|amazon.com..in link\|bestbuy.com..in link" main.py</automated>
    <automated>rtk grep -n "plugin_registry\|route_url\|verify_coverage\|discover" main.py</automated>
    <automated>rtk pytest -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `main.py` imports `from plugin_registry import discover, route_url, verify_coverage`
    - `main.py` calls `discover`, `verify_coverage`, and `route_url` (asserted via AST in smoke tests)
    - `main.py` iterates `for plugin in registry: if plugin.login_at_startup: plugin.login(...)`
    - `_handle_amazon` and `_handle_bestbuy` no longer exist in `main.py`
    - `from amazon_bot import ...` and `from bestbuy_bot import ...` removed
    - `amazon_bot.py` and `bestbuy_bot.py` deleted (git rm; not in working tree)
    - All 10 new tests in `tests/test_main_smoke.py` pass
    - Full pytest suite green
    - `main.py` parses as valid Python
    - `main.py` under 300 lines; `main()` and `_poll_one()` each under 30 lines
  </acceptance_criteria>
  <done>main.py refactored, legacy modules deleted, full suite green, D-02 hard cut complete</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| registry runtime exception -> polling loop | A plugin's check_availability or auto_buy may raise (network error, DOM change, driver crash). Must not crash main loop |
| verify_coverage fail -> startup abort | An unsupported URL in config must hard-fail at startup, not silently never check |
| legacy module deletion -> downstream imports | Anything still importing `amazon_bot` or `bestbuy_bot` after this plan will break |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-2-CORE-03-LOOP | Denial of Service | polling loop | mitigate | `_poll_one` wraps each plugin call in try/except; logs ERROR and continues; matches legacy behavior. Runtime plugin failure cannot crash main loop (RESEARCH pitfall 10) |
| T-2-CORE-04-COVERAGE | Repudiation | verify_coverage at startup | mitigate | Called between `discover` and login. Acknowledged trade-off: `discover` instantiates plugins which constructs `self.driver` via `build_driver`, so two Chrome windows are open before `verify_coverage` runs. The mitigation prevents the more expensive side-effects: interactive OTP, sign-in flows, and any `auto_buy` purchase action. Provides loud feedback (`ValueError` naming offending URL) over silent unsupported-URL skipping. A stricter "validate class-level domain_pattern before instantiation" variant is deferred to v2 if Chrome-startup cost on misconfigured runs becomes an issue. |
| T-2-D02-CUT | Tampering | legacy module deletion | mitigate | `git rm` removes amazon_bot.py and bestbuy_bot.py in same commit as main.py edit. Smoke tests assert non-existence; CI fail-fast if any future PR re-introduces them |
| T-2-CORE-03-LEGACY-IMPORT | Tampering | residual imports | mitigate | AST test (`test_main_does_not_import_legacy_bots`) blocks regression; the import would also produce an ImportError at startup if a future contributor re-adds `from amazon_bot import ...` against deleted files |
| T-2-D03-LOGIN | Spoofing | startup login loop | mitigate | `for plugin in registry: if plugin.login_at_startup: plugin.login(app_config)` runs every opt-in plugin's login once. Order is registry order (sorted by filename); deterministic |
</threat_model>

<verification>
- `rtk pytest -x -q` full suite passes (all Phase 1 + Phase 2 tests)
- `rtk find amazon_bot.py bestbuy_bot.py` returns no results
- `rtk grep -n "from amazon_bot\|from bestbuy_bot" main.py` returns no matches
- `rtk grep -n "amazon.com..in link\|bestbuy.com..in link" main.py` returns no matches
- `rtk grep -n "discover\|verify_coverage\|route_url" main.py` returns matches for all three
- `python -c "import ast; ast.parse(open('main.py').read())"` exits 0
</verification>

<success_criteria>
- CORE-03 satisfied at the main.py side: discovery wired in, lenient-on-import behavior reaches the polling loop
- CORE-04 satisfied at the main.py side: route_url replaces the hardcoded `if "amazon.com" in link` chain
- PLG-01 finalized: amazon_bot.py deleted; main.py routes Amazon URLs through AmazonPlugin
- PLG-02 finalized: bestbuy_bot.py deleted; main.py routes BestBuy URLs through BestBuyPlugin (with PLG-02 fix from Plan 03 now live)
- D-02 hard cut complete: zero references to legacy module names anywhere in source
- D-03 wiring live: startup login loop iterates plugins with login_at_startup=True
</success_criteria>

<output>
After completion, create `.planning/phases/02-plugin-migration/02-04-SUMMARY.md`
</output>
