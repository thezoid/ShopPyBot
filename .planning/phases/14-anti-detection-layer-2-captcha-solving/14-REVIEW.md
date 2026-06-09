---
phase: 14-anti-detection-layer-2-captcha-solving
reviewed: 2026-06-09T00:00:00Z
depth: deep
files_reviewed: 8
files_reviewed_list:
  - core/captcha.py
  - core/config_schema.py
  - core/credentials.py
  - core/orchestrator.py
  - core/registry.py
  - core/service.py
  - plugins/shopbot_plugin_amazon.py
  - plugins/shopbot_plugin_bestbuy.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: resolved
---

# Phase 14: Code Review Report

**Reviewed:** 2026-06-09
**Depth:** deep
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 14 adds automated reCAPTCHA v2 solving via the 2captcha API (ANTI-06/07). Overall
the security fundamentals are solid: the API key is never logged, config schema has no
`api_key` field, and every failure path falls back to manual pause rather than silent
skip. However two correctness bugs require fixes before ship: a misspelled polling
sentinel causes infinite paid polling on transient server errors, and the token injection
JS does not filter double-quote characters, breaking out of the JS string context when
2captcha returns a token containing `"`. Three further warnings address an orphaned
executor thread on timeout, an unchecked `can_solve()` guard in the stub method, and a
runtime error from a late import inside a hot path.

## Critical Issues

### CR-01: Misspelled "CAPCHA_NOT_READY" sentinel causes paid re-polling on any other error string

**File:** `core/captcha.py:70`

**Issue:** The 2captcha API returns `"CAPTCHA_NOT_READY"` (two T's). The code compares
against `"CAPCHA_NOT_READY"` (one T). Any legitimate "not ready yet" response therefore
does NOT match the guard and instead falls through to:

```python
raise RuntimeError(f"2captcha poll error: {result}")
```

This means `solve_recaptcha` raises on the very first poll even though the CAPTCHA is
still being worked on. Because `_solve_count` was already incremented before the call
(line 160), each failed solve charges one solve against the cap but the caller's
`except` block in `_solve_or_pause` catches it and falls back to manual pause -- the
CAPTCHA is never actually solved. Every CAPTCHA encounter wastes a paid submission at
a cost of ~$0.002-$0.003 and the bot never benefits from the solver.

**Fix:**

```python
# core/captcha.py line 70 -- correct the sentinel spelling
if result != "CAPTCHA_NOT_READY":   # two T's; matches 2captcha API response
    raise RuntimeError(f"2captcha poll error: {result}")
```

### CR-02: Token injection JS does not filter double-quote; 2captcha tokens break out of JS string context

**File:** `plugins/shopbot_plugin_amazon.py:79-82` and `plugins/shopbot_plugin_bestbuy.py:79-82`

**Issue:** The token validation at line 143 (Amazon) / 124 (BestBuy) only rejects
tokens containing `'` (single-quote) or `\n`. The f-string injection template uses
single-quoted JS string literals:

```python
f"if(el){{el.value='{token}';}}"
f"if(x&&x.callback){{try{{x.callback('{token}');}}"
```

2captcha tokens for reCAPTCHA v2 are base64url encoded and do not contain `"`, so the
double-quote gap is low practical risk for reCAPTCHA v2. However `solve_amazon_waf`
(AmazonTask) returns a JSON-decoded dict and the future WAF path that calls
`_inject_token` would pass an arbitrary string. More concretely, the token value is
externally controlled (comes from 2captcha's server response). A malicious or
misconfigured response containing `'` is filtered, but a response containing `\` is
not -- `\'` in the token closes the JS string and injects arbitrary JS into the live
page context via `tab.evaluate()`.

The validation must also reject backslash:

```python
# Both plugins, line 143 (Amazon) / line 124 (BestBuy)
if not token or "'" in token or "\\" in token or "\n" in token:
    _log.warning("CAPTCHA token failed validation -- falling back to manual pause")
    ...
    return
```

Alternatively, use `json.dumps(token)` to produce a JS-safe string literal rather than
raw f-string interpolation:

```python
import json as _json

async def _inject_token(self, tab, token: str) -> None:
    safe = _json.dumps(token)           # produces "..." with all special chars escaped
    inject_js = (
        f"(function(){{"
        f"var el=document.getElementById('g-recaptcha-response');"
        f"if(el){{el.value={safe};}}"
        f"var c=window.___grecaptcha_cfg&&window.___grecaptcha_cfg.clients;"
        f"if(c){{Object.values(c).forEach(function(x){{"
        f"if(x&&x.callback){{try{{x.callback({safe});}}catch(e){{}}}}"
        f"}});}}}})();"
    )
    await tab.evaluate(inject_js)
```

This eliminates the entire class of injection risk rather than playing whack-a-mole
with character lists. Apply identically to both plugin files.

## Warnings

### WR-01: asyncio.timeout cancels the awaitable but does NOT cancel the executor thread; orphan thread can continue charging the 2captcha account

**File:** `plugins/shopbot_plugin_amazon.py:130-133` and `plugins/shopbot_plugin_bestbuy.py:112-115`

**Issue:** `asyncio.timeout(120)` wraps `loop.run_in_executor(...)`. When the timeout
fires, asyncio cancels the coroutine's `await` on the Future, but the underlying thread
running `solver.solve_recaptcha` (which calls `time.sleep` + `requests.get` in a loop)
continues executing in the thread pool until it returns or raises naturally. The
`_poll_result` loop can take up to 115 seconds (15s initial + 20 * 5s polls). If the
timeout fires at t=120s, the thread has at most ~5s remaining before it would have
timed out itself -- but in the worst case (e.g. a slow network stall inside the
`requests.get(timeout=10)`) the thread can remain alive for up to 10 additional seconds
past the asyncio cancellation. During those extra seconds the thread may receive a
token from 2captcha and count it as a used solve (the `_solve_count` was incremented
pre-call so the cap is not double-counted), but the bot's event loop has already moved
to the manual pause path. This means a paid solve can be consumed with no benefit.

The practical impact is bounded because `_MAX_POLLS * _POLL_INTERVAL_SECS + _INITIAL_WAIT_SECS = 115s`
which is inside the 120s `asyncio.timeout`, so under normal network conditions the
thread always finishes before the timeout fires. The gap only opens under network
congestion causing a long `requests` stall. This is a "charge without benefit" risk,
not a crash risk.

**Fix:** Pass a threading `Event` into `_poll_result` and check it between polls to
allow cooperative cancellation from the async side, or document the residual risk and
accept it given the bounded window. At minimum add a comment:

```python
# WR-01: asyncio.timeout cancels the await but not the executor thread.
# The thread can run up to _POLL_INTERVAL_SECS + requests timeout (10s) past
# the 120s gate. _MAX_POLLS is sized so normal runs finish before timeout fires.
async with asyncio.timeout(120):
    token = await loop.run_in_executor(
        None, solver.solve_recaptcha, sitekey, pageurl
    )
```

### WR-02: solve_amazon_waf increments _solve_count and makes paid HTTP calls without checking can_solve() or balance_ok

**File:** `core/captcha.py:176`

**Issue:** `solve_amazon_waf` unconditionally increments `_solve_count` and calls
`requests.post` without any `can_solve()` or `balance_ok` guard. The method is
documented as deferred/stub, but it is public and callable. If a future caller invokes
it directly (bypassing the `can_solve()` check in `_solve_or_pause`) -- or once WAF
auto-solve is implemented in Phase N -- the cost-control invariant is silently bypassed:
`max_solves_per_run` is not enforced, and a zero-balance account still makes paid
requests.

**Fix:** Add a `can_solve()` guard at the top of `solve_amazon_waf`, matching the
pattern callers are expected to follow:

```python
def solve_amazon_waf(self, key: str, iv: str, context: str, pageurl: str) -> dict:
    if not self.can_solve():
        raise RuntimeError("solve_amazon_waf called when can_solve() is False")
    self._solve_count += 1
    ...
```

### WR-03: Late `import json as _json` inside solve_amazon_waf hot path; also masks module-level dependency

**File:** `core/captcha.py:197`

**Issue:** `import json as _json` is placed inside the body of `solve_amazon_waf`
(line 197), which is called in a polling thread. Python's import system serializes
on a per-module lock so this is safe from races, but the pattern:

1. Hides a dependency from the module's import section, making it invisible to static
   analysis tools and code readers.
2. Adds a dict lookup on every call to the method (minor but avoidable).
3. Contradicts `json` already being in the stdlib with zero cost to top-level import.

`json` is already used in `_submit_recaptcha` (via `resp.json()`) so the module
transitively depends on it. Move the import to the module top-level:

```python
# core/captcha.py top-level imports section
import json
import logging
import time

import requests
```

Then in `solve_amazon_waf`:

```python
try:
    return json.loads(token_str)
except Exception:
    return {"captcha_voucher": token_str, "existing_token": ""}
```

## Info

### IN-01: _poll_result raises TimeoutError (not RuntimeError) on max-polls exhaustion; callers catch generic Exception so it works, but the type choice is inconsistent

**File:** `core/captcha.py:73`

**Issue:** `_poll_result` raises `TimeoutError` when `_MAX_POLLS` is exceeded. All
callers catch `Exception` (which includes `TimeoutError`) so behavior is correct.
However `TimeoutError` is semantically ambiguous here: it is not an asyncio timeout
(the asyncio timeout fires via `asyncio.TimeoutError` / `CancelledError` in the outer
coroutine). Using `RuntimeError` with a clear message would match the error style used
throughout the rest of the file and avoid potential confusion if a future caller wants
to distinguish poll exhaustion from network timeout.

**Fix:** Rename to `RuntimeError` or subclass explicitly:

```python
raise RuntimeError("2captcha: exceeded max polls without a result")
```

### IN-02: solve_amazon_waf has no exception wrapper; RuntimeError from submit/poll leaks raw error string (contains no key, but is inconsistent with solve_recaptcha's logging pattern)

**File:** `core/captcha.py:190-195`

**Issue:** `solve_recaptcha` (line 164) wraps its body in a `try/except` that logs
`exc.__class__.__name__` before re-raising. `solve_amazon_waf` has no such wrapper: if
`resp.raise_for_status()` or `_poll_result` raises, the exception propagates silently
to the caller with no log entry. This makes diagnosing WAF solve failures harder.

**Fix:** Add the same wrapper pattern:

```python
def solve_amazon_waf(self, key, iv, context, pageurl):
    if not self.can_solve():
        raise RuntimeError("solve_amazon_waf: can_solve() is False")
    self._solve_count += 1
    try:
        resp = requests.post(...)
        ...
        return ...
    except Exception as exc:
        _log.warning("solve_amazon_waf failed: %s", exc.__class__.__name__)
        raise
```

_Reviewed: 2026-06-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
