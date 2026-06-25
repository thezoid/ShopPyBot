---
phase: 20-checkout-profile-form-fill
reviewed: 2026-06-11T00:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - core/checkout_profile.py
  - core/cli/__init__.py
  - core/cli/run.py
  - core/cli/setup.py
  - core/credentials.py
  - core/orchestrator.py
  - core/plugin_base.py
  - plugins/shopbot_plugin_amazon.py
  - plugins/shopbot_plugin_bestbuy.py
  - tests/conftest.py
  - tests/test_checkout_form_fill.py
  - tests/test_checkout_profile.py
  - tests/test_cvv_threading.py
  - tests/test_no_cvv_in_logs.py
  - tests/test_plugin_bestbuy.py
  - tests/test_setup_checkout_profile.py
findings:
  critical: 3
  warning: 4
  info: 2
  total: 9
status: issues_found
---

# Phase 20: Code Review Report

**Reviewed:** 2026-06-11
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Phase 20 delivers the checkout profile model, CLI setup wizard, form-fill integration in both plugins, and a CVV-in-logs AST guard. The security fundamentals are sound: no card number is ever stored, CVV lives only in memory, and CHECKOUT_PROFILE_KEYS is provably disjoint from SECRET_KEYS. However, three critical defects exist: the CLI form deviation is a real user-facing breakage against the spec (not merely cosmetic), the CVV AST guard covers the wrong file set and misses `shopbot_plugin_bestbuy.py`, and the BestBuy `auto_buy` monitor_only default is `True` which silently suppresses every live buy regardless of config.

## Critical Issues

### CR-01: BUY-07 Criterion 1 Violated -- `setup checkout-profile` Sub-Action Not Accepted

**File:** `core/cli/__init__.py:57-63`
**Issue:** BUY-07 criterion 1 specifies the command form `shoppybot setup checkout-profile` (sub-action). The implementation shipped `shoppybot setup --checkout-profile` (a boolean flag). These are not the same invocation. A user or operator following the spec documentation, the ROADMAP, or the planning artifacts (which consistently use the sub-action form in every acceptance criterion, every UAT step, and the research recommendation) will type `shoppybot setup checkout-profile` and receive an argparse error: `unrecognized arguments: checkout-profile`. The flag form is only discoverable via `--help`. This is a user-visible breakage against a written, reviewed acceptance criterion.

The 20-02-SUMMARY.md justification ("Option A was skipped because MagicMock fixtures would need restructuring") is weak: the `items` and `config` groups already use `add_subparsers` on the same parser object. A sub-subparser under `setup_p` does not require restructuring any test fixture because `handle_setup_checkout_profile` takes `(args, svc)` -- the same signature as all other handlers. The test fixtures for existing setup tests do not need to change because they call `handle_setup` directly, not via `build_parser`.

The lowest-risk fix is to accept BOTH forms: keep the `--checkout-profile` flag (existing callers unbroken) AND add a `checkout-profile` sub-subparser under `setup_p` that calls `handle_setup_checkout_profile` directly. This is the same aliasing pattern already used for the top-level `--migrate` flag. Approximately 10 lines:

```python
# in build_parser(), after setup_p.add_argument("--checkout-profile", ...)
setup_sub = setup_p.add_subparsers(dest="setup_command")
cp_p = setup_sub.add_parser(
    "checkout-profile",
    help="Configure shipping/billing address profile (9 address keys; no card/CVV).",
)
cp_p.set_defaults(func=handle_setup_checkout_profile)
```

No existing test changes are needed. The `handle_setup` dispatch via `getattr(args, "checkout_profile", False) is True` continues to work for the flag form.

### CR-02: CVV AST Guard (`test_no_cvv_in_logs.py`) Misses `shopbot_plugin_bestbuy.py`

**File:** `tests/test_no_cvv_in_logs.py:23-27`
**Issue:** The `test_cvv_not_in_writelog_args` function scans three files:
- `plugins/shopbot_plugin_bestbuy.py`
- `plugins/shopbot_plugin_amazon.py`
- `core/checkout_profile.py`

`shopbot_plugin_bestbuy.py` is in the list, so this guard correctly covers BestBuy. However, the companion guard in `test_cvv_threading.py` (lines 231-235) scans a DIFFERENT three-file set:
- `core/orchestrator.py`
- `core/cli/run.py`
- `plugins/shopbot_plugin_amazon.py`

Neither guard scans `shopbot_plugin_bestbuy.py` in the threading-files context, and critically, `test_no_cvv_in_logs.py` does not scan `core/orchestrator.py` or `core/cli/run.py`. The two guards together are not union-complete: `core/orchestrator.py` is only covered by the threading guard (which checks `writeLog` and `print` but not f-string interpolation into log calls via keyword args), and `core/cli/run.py` is only checked by the threading guard.

More concretely: both guards check only positional `node.args`, not `node.keywords`. Any `writeLog(msg=..., type=cvv)` or `print(file=..., end=cvv)` keyword argument containing `_cvv` would pass both guards silently. This is a low-probability risk but the guard is documented as a CI security assertion (T-20-07) and should be airtight.

**Fix:** Extend `test_no_cvv_in_logs.py` to also scan `core/orchestrator.py` and `core/cli/run.py` (matching `test_cvv_threading.py`'s scope), and update both guards to check `node.keywords` as well as `node.args`:

```python
for kw in node.keywords:
    kw_src = ast.unparse(kw.value)
    if "_cvv" in kw_src and not isinstance(kw.value, ast.Constant):
        violations.append(...)
```

### CR-03: `BestBuyPlugin.auto_buy` monitor_only Default `True` Suppresses All Live Buys

**File:** `plugins/shopbot_plugin_bestbuy.py:285`
**Issue:** The monitor_only guard at the top of `BestBuyPlugin.auto_buy` reads:

```python
if getattr(debug, "monitor_only", True):
```

The `getattr` default is `True`. This means: if `self.config` is `None` OR if `debug` has no `monitor_only` attribute, the guard fires and `auto_buy` returns `False` immediately. For a correctly configured normal run where `config.debug.monitor_only = False`, this is fine. But any plugin instantiation with `config=None` (tests, edge cases) or a config missing a `debug` attribute (legacy config, registry bug) will silently suppress the buy without any log message beyond "auto_buy suppressed (monitor_only)".

The parallel in `AmazonPlugin.auto_buy` at line 378 uses the same `getattr(debug, "monitor_only", True)` default. The `plugin_base.py` comment at line 112 justifies this for `place_order_guarded` as a "fail-safe" because `DebugConfig.monitor_only` defaults to `False` in the schema -- meaning real configs always have the attribute. But in `auto_buy` the guard fires BEFORE `place_order_guarded`, and unlike `place_order_guarded` there is no log that distinguishes "suppressed because monitor_only=True" from "suppressed because config absent". The `test_plugin_bestbuy.py` test at line 157 uses `_make_config(test_mode=False, monitor_only=False)` which passes correctly, but `test_autobuy_calls_update_purchased` -- the Phase 8 regression test -- may use a different config path.

More critically: the `test_autobuy_returns_false_no_profile` test in `test_checkout_form_fill.py` (line 131) uses `_no_op_config()` which correctly sets `debug.monitor_only = False`. But `test_missing_required_selector_aborts` (line 164) also uses `_no_op_config()` -- fine. The production risk is that any code path that constructs a BestBuyPlugin or AmazonPlugin without a fully-populated config (e.g., during a plugin hot-reload or a misconfigured registry) will silently never attempt an auto-buy, which could cause real financial harm (missed purchase of a drop item) with no actionable error.

**Fix:** Replace the `True` default with `False` and let `place_order_guarded` (which correctly defaults `monitor_only` to `True`) be the fail-safe. Add a log warning when config is None:

```python
debug = getattr(self.config, "debug", None) if self.config else None
if self.config is None:
    writeLog("[BestBuyPlugin] auto_buy called with no config -- suppressing", "WARNING")
    return False
if getattr(debug, "monitor_only", False):
    writeLog("[BestBuyPlugin] auto_buy suppressed (monitor_only)", "INFO")
    return False
```

## Warnings

### WR-01: `handle_setup_checkout_profile` Uses Visible Input for Address Fields (Correct Design, Missing Operator Warning)

**File:** `core/cli/setup.py:83`
**Issue:** The function uses `_prompt_visible` (echoed `sys.stdin.readline()`) for all 9 address fields. This is correct per spec (address fields are non-secret, echo aids verification). However, for keys like `CHECKOUT_PHONE` and `CHECKOUT_ZIP`, the values will appear on-screen in environments where terminal output is logged (CI, tmux scrollback, SSH session recording). The function prints no warning that input will be echoed. The parallel `handle_setup` uses `getpass` for secret keys; users accustomed to that workflow may be surprised to see their address echoed, or conversely may not notice that phone/address are going to a visible terminal in a recorded session.

This is not a hard block but is a quality and UX gap given the security posture of the rest of the codebase. A one-line note at the start of `handle_setup_checkout_profile` would suffice:

```python
print("\nCheckout profile setup (address keys only -- no card/CVV). Input is visible.")
```

### WR-02: `load_checkout_profile` Silently Reads From Uninitialized Singleton

**File:** `core/checkout_profile.py:70`
**Issue:** `load_checkout_profile` calls `get_store()` which, when `init_store()` has not been called, silently returns a fresh `EnvVarBackend`. During plugin `setup()`, `init_store(cfg)` should already have been called by `BotService.__init__`. But if `load_checkout_profile()` is called in a test or tool context without `init_store()`, it reads from `os.environ` silently -- a different backend than the user configured. The function has no assertion or log that it obtained the configured store vs. the lazy fallback.

This is the same latent issue documented in `credentials.py` (RESEARCH Pitfall 1) and is consistent with the existing design. The risk here is that a developer running `load_checkout_profile()` in isolation will silently get empty values if the checkout keys are stored in keyring/file and not in environment, with no error surfaced. The `load_checkout_profile()` docstring says nothing about this dependency.

**Fix:** Add a note to the docstring: "Requires `init_store(cfg)` to have been called; otherwise falls back to `EnvVarBackend` (env vars)." No code change required beyond documentation.

### WR-03: `test_no_cvv_in_logs.py` Does Not Check `kwargs` in f-string `writeLog` Calls

**File:** `tests/test_no_cvv_in_logs.py:57-62`
**Issue:** The guard walks `node.args` only. Any f-string like `writeLog(f"info: {self._cvv}")` where the f-string is an `ast.JoinedStr` (not `ast.Constant`) would be caught because `ast.unparse` on a `JoinedStr` produces the string with `_cvv` in it. However, the guard also does not check `node.keywords` at all. A future developer adding `writeLog(message=f"val={self._cvv}", type="INFO")` would bypass the guard. Given this is a security CI assertion, it should be keyword-complete.

This partially overlaps CR-02 but the keyword-args gap is a distinct concern warranting a warning even if the union-coverage issue is fixed.

**Fix:** Add keyword arg scanning after the `for arg in node.args` loop:

```python
for kw in node.keywords:
    kw_src = ast.unparse(kw.value)
    if "_cvv" in kw_src:
        violations.append(
            f"{path.name}:{node.lineno}: writeLog kwarg contains '_cvv': {kw_src!r}"
        )
```

### WR-04: `orchestrator.py` CVV Injection Block Is Duplicated -- Second `if cvv:` Check Is Redundant

**File:** `core/orchestrator.py:411-418`
**Issue:** The CVV injection for BestBuy (lines 411-414) and Amazon (lines 415-418) are two separate `if cvv:` blocks. The second block re-checks `if cvv:` which is always True when the first block executed. While not a correctness bug (both blocks inject independently, and both guards are necessary for the `if amz_plugin:` inner check), the duplicate top-level `if cvv:` check is dead logic: if `cvv` is falsy, neither block runs; if `cvv` is truthy, both run. A future reader may believe they're independent conditions.

**Fix:** Merge into a single `if cvv:` block:

```python
if cvv:
    bb_plugin = registry.route("https://www.bestbuy.com/")
    if bb_plugin:
        bb_plugin._cvv = cvv
    amz_plugin = registry.route("https://www.amazon.com/")
    if amz_plugin:
        amz_plugin._cvv = cvv
```

## Info

### IN-01: `test_setup_stores_no_card_or_cvv` Contains a Tautological Assertion

**File:** `tests/test_setup_checkout_profile.py:157-158`
**Issue:** The assertion:

```python
assert fragment not in key.upper() or key in CHECKOUT_PROFILE_KEYS
```

is always True because `key` is being iterated from `CHECKOUT_PROFILE_KEYS`, making `key in CHECKOUT_PROFILE_KEYS` unconditionally True. The `or` short-circuits and the left side is never actually enforced. The test will pass even if a key with "CVV" in its name were added to `CHECKOUT_PROFILE_KEYS`. The real check is in the second assertion block (lines 162-168), which does correctly assert `fragment not in upper`. The first assertion block provides zero coverage.

**Fix:** Remove lines 155-158 (the first assertion block) entirely, or replace with an assertion that would actually fail:

```python
for key in CHECKOUT_PROFILE_KEYS:
    for fragment in forbidden:
        assert fragment not in key.upper(), (
            f"CHECKOUT_PROFILE_KEYS contains key {key!r} with forbidden fragment {fragment!r}"
        )
```

### IN-02: `test_cvv_threading.py` AST Scan Scope Comment Is Misleading

**File:** `tests/test_cvv_threading.py:230`
**Issue:** The docstring says the test scans "threading files" (orchestrator, cli/run, amazon plugin), but the BestBuy plugin -- which also threads `_cvv` via the same `auto_buy` method and `place_order_guarded` pattern -- is not included. The docstring's scope description is accurate for what it tests but a reader relying on these tests for CVV safety assurance would not realize BestBuy's threading path is only covered by `test_no_cvv_in_logs.py`, not this test. The two guards have overlapping but non-identical scopes with no comment explaining the division.

**Fix:** Add a comment to both test files noting the intended scope split: `test_cvv_threading.py` covers the orchestration + CLI path; `test_no_cvv_in_logs.py` covers the plugin checkout path. No code change required.

---

_Reviewed: 2026-06-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
