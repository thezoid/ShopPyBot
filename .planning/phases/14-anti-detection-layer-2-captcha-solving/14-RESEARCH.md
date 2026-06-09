# Phase 14: Anti-Detection Layer 2 - CAPTCHA Solving - Research

**Researched:** 2026-06-09
**Domain:** 2captcha HTTP API, reCAPTCHA v2 token extraction/injection, Amazon WAF CAPTCHA, asyncio executor patterns, Python requests
**Confidence:** HIGH (API protocol verified via official docs; codebase patterns verified by reading source)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Hand-rolled 2captcha client using already-pinned `requests==2.33.1` (NO new dependency).
- Submit/poll protocol runs inside `run_in_executor` with `asyncio.timeout(120)`.
- Supports reCAPTCHA v2 and Amazon WAF CAPTCHA solving.
- 2captcha API key lives EXCLUSIVELY in CredentialStore under `TWOCAPTCHA_API_KEY` — never in config.yml, never logged.
- Single unified `captcha:` config section: `captcha.enabled: bool = False`, `captcha.max_solves_per_run: int`, `captcha.low_balance_threshold: float = 1.00`.
- At startup check balance: WARNING when < low_balance_threshold; zero balance -> skip solver, fall back to manual pause.
- `max_solves_per_run` hard cap per run.
- On any failure, timeout, zero balance, or cap-hit: fall back to EXISTING manual-pause behavior; never silent skip.
- Reuse existing `detect_captcha` pause path; do not duplicate it.

### Claude's Discretion
- Internal module structure (e.g. `core/captcha.py` or similar), exact class/function names.
- How the solver client is constructed and passed to plugins (mirror Phase 13 ProxyPool wiring).
- 2captcha endpoint/polling-interval details, exact config field validation.

### Deferred Ideas (OUT OF SCOPE)
- Plugin ecosystem registry (Phase 15).
- Price monitoring (Phase 16).
- Broad v3.0 test hardening (Phase 17).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ANTI-06 | User can enable CAPTCHA solving (reCAPTCHA v2 and Amazon WAF) via 2captcha through an opt-in `captcha_solver:` flag, with the API key stored in CredentialStore (`TWOCAPTCHA_API_KEY`), never in config.yml. | 2captcha v1 in.php API (method=userrecaptcha) + AmazonTask type verified; CredentialStore.get() confirmed pattern. |
| ANTI-07 | Bot checks the CAPTCHA-solver account balance at startup, warns when balance is low, and skips solver use when balance is zero. | res.php action=getbalance response format verified; ERROR_ZERO_BALANCE error code confirmed. |
</phase_requirements>

## Summary

Phase 14 adds an opt-in automated CAPTCHA solving layer using the 2captcha service. The integration is hand-rolled using the already-pinned `requests==2.33.1` against the 2captcha v1 (in.php/res.php) HTTP API — no new dependencies required. The entire synchronous HTTP sequence (submit, poll) runs inside `loop.run_in_executor(None, ...)` wrapped by `asyncio.timeout(120)` so the async event loop never blocks during a solve.

The phase introduces one new Pydantic model (`CaptchaConfig`) nested under `AppConfig.captcha`, a new `core/captcha.py` module containing the `CaptchaSolver` class, and wiring through the existing orchestrator/registry/plugin pipeline mirroring how `ProxyPool` was introduced in Phase 13. The API key is read exclusively from `CredentialStore` at construction time; it is never logged, never in config.yml, and `SECRET_KEYS` must be updated to include `TWOCAPTCHA_API_KEY` before any other CAPTCHA code is written.

Amazon WAF CAPTCHA (`AmazonTask` type) is fundamentally more complex than reCAPTCHA v2: it requires extracting three live per-request parameters (`websiteKey`, `iv`, `context`) from the challenged page's DOM, each with a ~30-second freshness window, and the returned token pair (`captcha_voucher`, `existing_token`) must be applied via a site-specific injection path that requires monitoring Network requests during manual testing. Given this complexity and the fact that Amazon.com currently shows a simple image-text CAPTCHA ("Enter the characters you see below") rather than the full WAF CAPTCHA on most shopping flows, the planner should scope Amazon WAF solving carefully: detect which type is present and fall back to manual pause for the WAF variant if DOM extraction is unreliable.

**Primary recommendation:** Implement `core/captcha.py` with `CaptchaSolver` mirroring `ProxyPool`'s `from_config` class-method pattern; wire through `BotService.__init__` and `async_main` analogously to `proxy_pool`; inject into plugins via `registry.assign_solver`; call from the existing `detect_captcha` path in each plugin with immediate manual-pause fallback on any failure.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CaptchaConfig parsing | Config / Pydantic | — | All config lives in `core/config_schema.py`; same pattern as `ProxyConfig` |
| API key storage | CredentialStore | — | CRED-01 canonical; `SECRET_KEYS` list gates key registration |
| Balance check at startup | BotService init path | core/captcha.py | Startup-time check mirrors proxy startup log in `BotService.__init__` |
| Submit/poll HTTP calls | core/captcha.py (sync) | run_in_executor bridge | Blocking I/O must not run on the async event loop (ASYNC-03) |
| Asyncio timeout guard | orchestrator / plugin callsite | asyncio.timeout(120) | 120s deadline wraps the executor call; timeout -> fall back to manual pause |
| Solve count cap | CaptchaSolver instance | — | Per-run counter incremented in solver; rejects once cap is hit |
| reCAPTCHA sitekey extraction | Plugin (Amazon/BestBuy) | CDP/DOM evaluate | Each plugin knows its page structure best |
| Token injection | Plugin (Amazon/BestBuy) | tab.evaluate() JS | Plugin executes JS to write `g-recaptcha-response` and fire callback |
| Amazon WAF param extraction | Plugin (Amazon) | tab.evaluate() JS | `window.gokuProps` extraction via JS; plugin-specific knowledge |
| Manual-pause fallback | Plugin (existing path) | asyncio.Event + stdin listener | Already implemented; must NOT be duplicated — just call it |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `requests` | 2.33.1 | HTTP calls to 2captcha API | Already pinned; no new dep; synchronous = safe in executor |

### No New Dependencies
This phase adds zero new packages. `requests==2.33.1` [VERIFIED: npm registry analogue — confirmed by `python -m pip show requests` returning 2.33.1 from the active venv] covers all HTTP needs.

**Version verification:**
```bash
python -m pip show requests
# Name: requests  Version: 2.33.1
```

## Package Legitimacy Audit

No new packages are installed in this phase. `requests==2.33.1` is the existing pinned dependency.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| requests | PyPI | ~14 yrs | 300M+/wk | github.com/psf/requests | N/A (pre-existing) | Approved — already pinned |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was not run (sandbox restriction); however no new packages are being added so no install-time risk exists.*

## Architecture Patterns

### System Architecture Diagram

```
BotService.__init__
  -> check captcha.enabled
  -> CaptchaSolver.from_config(cfg.captcha, store)
     -> store.get("TWOCAPTCHA_API_KEY")     [CredentialStore]
     -> GET res.php?action=getbalance       [sync, in executor]
     -> log WARNING if balance < threshold
     -> set solver.balance_ok = False if zero
  -> pass solver to async_main(cfg, cvv, solver)

async_main
  -> registry = PluginRegistry(cfg, plugins_dir, proxy_pool, captcha_solver)
  -> _staggered_setup -> registry.assign_solver(plugin) for each active plugin

Plugin.check_availability(url)
  -> tab.get(url)
  -> plugin.detect_captcha()  [True -> enter solve path]
     if solver and solver.can_solve():
       -> sitekey = await tab.evaluate("...extract sitekey JS...")
       -> token = await asyncio.timeout(120, loop.run_in_executor(solver.solve_recaptcha, sitekey, url))
          on success: await tab.evaluate("inject token JS")
          on failure/timeout/cap: fall through to manual-pause
     -> _wait_user_action(captcha_event, "CAPTCHA detected...")  [existing path]
```

### Recommended Project Structure
```
core/
  captcha.py       # CaptchaSolver class: submit/poll/balance; ~250 lines
  config_schema.py # add CaptchaConfig model + AppConfig.captcha field
  credentials.py   # add "TWOCAPTCHA_API_KEY" to SECRET_KEYS list
  orchestrator.py  # pass solver into async_main; pass to PluginRegistry
  registry.py      # assign_solver(plugin) mirroring assign_proxy
  service.py       # construct CaptchaSolver + startup log
plugins/
  shopbot_plugin_amazon.py   # use solver in check_availability CAPTCHA path
  shopbot_plugin_bestbuy.py  # idem (BestBuy also shows reCAPTCHA)
tests/
  test_captcha.py        # unit tests for CaptchaSolver (mocked requests)
  test_captcha_config.py # CaptchaConfig defaults + YAML parsing
  test_captcha_wiring.py # service startup log, registry.assign_solver, plugin path
```

### Pattern 1: 2captcha v1 HTTP API — reCAPTCHA v2 Submit

**What:** POST to `https://2captcha.com/in.php` with `method=userrecaptcha`.
**When to use:** A page presents a visible reCAPTCHA v2 widget (data-sitekey present in DOM).
**Example:**
```python
# Source: https://2captcha.com/2captcha-api (verified via WebFetch)
import requests

def _submit_recaptcha(api_key: str, sitekey: str, pageurl: str) -> str:
    """Submit reCAPTCHA v2 solve request. Returns captcha_id string."""
    resp = requests.post(
        "https://2captcha.com/in.php",
        data={
            "key": api_key,
            "method": "userrecaptcha",
            "googlekey": sitekey,
            "pageurl": pageurl,
            "json": 1,
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != 1:
        raise RuntimeError(f"2captcha submit error: {body.get('request')}")
    return str(body["request"])  # captcha_id
```

### Pattern 2: 2captcha v1 HTTP API — Poll for Result

**What:** GET `https://2captcha.com/res.php?action=get&id=...` every 5 seconds after an initial 15-second wait.
**When to use:** After receiving the captcha_id from Pattern 1.
**Example:**
```python
# Source: https://2captcha.com/2captcha-api (verified via WebFetch)
import time

_INITIAL_WAIT_SECS = 15
_POLL_INTERVAL_SECS = 5
_MAX_POLLS = 20  # 15 + 20*5 = 115s max, fits inside asyncio.timeout(120)

def _poll_result(api_key: str, captcha_id: str) -> str:
    """Block until solved token arrives or raise on error/timeout."""
    time.sleep(_INITIAL_WAIT_SECS)
    for _ in range(_MAX_POLLS):
        resp = requests.get(
            "https://2captcha.com/res.php",
            params={"key": api_key, "action": "get", "id": captcha_id, "json": 1},
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.json()
        status = body.get("status")
        result = str(body.get("request", ""))
        if status == 1:
            return result  # solved token
        if result != "CAPCHA_NOT_READY":
            raise RuntimeError(f"2captcha poll error: {result}")
        time.sleep(_POLL_INTERVAL_SECS)
    raise TimeoutError("2captcha: exceeded max polls")
```

### Pattern 3: Balance Check

**What:** GET `https://2captcha.com/res.php?action=getbalance` (v1 legacy) returns balance as plain text float.
**When to use:** Once at startup, before the bot loop starts.
**Example:**
```python
# Source: https://2captcha.com/api-docs/get-balance (JSON API) and legacy in.php docs
# Legacy v1 endpoint (consistent with rest of hand-rolled client):
def _check_balance(api_key: str) -> float:
    resp = requests.get(
        "https://2captcha.com/res.php",
        params={"key": api_key, "action": "getbalance"},
        timeout=10,
    )
    resp.raise_for_status()
    text = resp.text.strip()
    if text.startswith("ERROR_"):
        raise RuntimeError(f"2captcha balance check error: {text}")
    return float(text)
```

### Pattern 4: run_in_executor + asyncio.timeout Wrapper

**What:** Bridge blocking `_submit_recaptcha` + `_poll_result` to the async event loop.
**When to use:** Inside plugin `check_availability` after CAPTCHA detected.
**Example:**
```python
# Source: codebase pattern from core/orchestrator.py (run_in_executor usage) [VERIFIED: read source]
import asyncio

async def solve_with_timeout(solver, sitekey: str, pageurl: str) -> str | None:
    """Return solved token or None on any failure (timeout, error, cap)."""
    loop = asyncio.get_running_loop()
    try:
        async with asyncio.timeout(120):
            token = await loop.run_in_executor(
                None, solver.solve_recaptcha, sitekey, pageurl
            )
        return token
    except (asyncio.TimeoutError, Exception):
        return None
```

### Pattern 5: reCAPTCHA Sitekey Extraction + Token Injection (via CDP/JS)

**What:** Use `tab.evaluate()` to read `data-sitekey` and write the solved token back.
**When to use:** After `detect_captcha()` returns True and solver returns a token.
**Example:**
```python
# Source: https://2captcha.com/h/recaptcha-v2-callback (WebFetch verified)
# Extraction:
sitekey = await tab.evaluate(
    "document.querySelector('[data-sitekey]')?.getAttribute('data-sitekey') || ''"
)

# Injection (set hidden textarea + fire callback):
inject_js = f"""
(function() {{
  var el = document.getElementById('g-recaptcha-response');
  if (el) {{ el.value = '{token}'; }}
  var clients = window.___grecaptcha_cfg && window.___grecaptcha_cfg.clients;
  if (clients) {{
    Object.values(clients).forEach(function(c) {{
      var cb = c && c.callback;
      if (cb) {{ try {{ cb('{token}'); }} catch(e) {{}} }}
    }});
  }}
}})();
"""
await tab.evaluate(inject_js)
```

### Pattern 6: Amazon WAF CAPTCHA Parameter Extraction

**What:** Extract `websiteKey`, `iv`, `context` from `window.gokuProps` before submitting to 2captcha AmazonTask.
**When to use:** When Amazon page triggers the WAF CAPTCHA (distinct from the simple text CAPTCHA Amazon.com shows for product pages).
**Example:**
```python
# Source: https://2captcha.com/h/how-to-bypass-amazon-captcha (WebFetch verified)
# NOTE: gokuProps is the documented extraction point; use regex fallback on page source
waf_params_js = """
(function() {
  var p = window.gokuProps;
  if (p) return JSON.stringify({key: p.key, iv: p.iv, context: p.context});
  return null;
})();
"""
raw = await tab.evaluate(waf_params_js)
# raw is None if not a WAF CAPTCHA page
```

### Pattern 7: CaptchaSolver Class Skeleton

```python
# core/captcha.py — mirrors ProxyPool pattern from core/stealth.py [VERIFIED: read source]
class CaptchaSolver:
    def __init__(self, api_key: str, max_solves: int, low_threshold: float) -> None:
        self._api_key = api_key   # NEVER log this field
        self._max_solves = max_solves
        self._low_threshold = low_threshold
        self._solve_count = 0
        self.balance_ok: bool = True

    @classmethod
    def from_config(cls, cfg, store) -> "CaptchaSolver | None":
        """Return solver if captcha.enabled, else None."""
        if not getattr(cfg, "enabled", False):
            return None
        api_key = store.get("TWOCAPTCHA_API_KEY")
        if not api_key:
            writeLog("TWOCAPTCHA_API_KEY not set -- captcha solving disabled", "WARNING")
            return None
        return cls(api_key, cfg.max_solves_per_run, cfg.low_balance_threshold)

    def check_balance_at_startup(self) -> None:
        """Call once; sets self.balance_ok; logs WARNING if low / zero."""
        ...  # calls _check_balance(self._api_key)

    def can_solve(self) -> bool:
        """Return True when balance_ok and solve_count < max_solves."""
        return self.balance_ok and self._solve_count < self._max_solves

    def solve_recaptcha(self, sitekey: str, pageurl: str) -> str:
        """Blocking: submit + poll. Increments _solve_count. Raises on error."""
        ...

    def solve_amazon_waf(self, key: str, iv: str, context: str, pageurl: str) -> dict:
        """Blocking: submit AmazonTask + poll. Returns {captcha_voucher, existing_token}."""
        ...
```

### Anti-Patterns to Avoid
- **Logging the API key:** `writeLog(f"key={self._api_key}")` — key is a secret; log only `"TWOCAPTCHA_API_KEY"` (key name only).
- **Calling `solve_recaptcha` directly in async context:** blocks the event loop; must use `run_in_executor`.
- **Using `asyncio.timeout` outside the executor wrapper:** the timeout must wrap the entire `run_in_executor` call, not the internal sync function.
- **Reusing iv/context for Amazon WAF:** these expire in ~30 seconds; must be fetched fresh per solve attempt.
- **Adding `captcha.api_key` to Pydantic schema:** the key must never appear in config.yml (ANTI-06 requirement); only `CredentialStore` access is acceptable.
- **Silent skip on failure:** every failure path must call the existing `_wait_user_action` / manual-pause fallback.
- **Calling `input()` anywhere in orchestrator/captcha module:** violates ASYNC-03; manual pause stays in the plugin's `_wait_user_action` path.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client for 2captcha | Custom socket or urllib | `requests` (already pinned) | Error handling, timeout, keep-alive already implemented |
| Async HTTP to 2captcha | `aiohttp` or `httpx` | `requests` in `run_in_executor` | No new dep; blocking HTTP in executor is the established project pattern |
| Token expiry timer | Custom threading.Timer | `asyncio.timeout(120)` | Project already uses this pattern; simpler; integrates with TaskGroup cancellation |
| OS keyring / secret store | Any custom encryption | `get_store().get("TWOCAPTCHA_API_KEY")` | Phase 8 built this; re-use |
| Polling loop with backoff | Custom sleep/retry | See Pattern 2 above | 15s initial + 5s interval is the 2captcha-documented cadence |

**Key insight:** The 2captcha v1 HTTP API is simple enough (two GET/POST calls + a poll loop) that an SDK would add more surface area than it saves. The hand-rolled approach is 80 lines and has no hidden retry or thread state.

## Runtime State Inventory

Not applicable: this is a greenfield feature addition, not a rename/refactor phase.

## Common Pitfalls

### Pitfall 1: Adding `captcha.api_key` to CaptchaConfig / AppConfig
**What goes wrong:** The key ends up in config.yml (gitignored but plaintext) or in `pydantic-settings` env var parsing, surfacing it in logs or error messages.
**Why it happens:** Natural to put all CAPTCHA config in one place.
**How to avoid:** `CaptchaConfig` has NO `api_key` field. Read exclusively via `get_store().get("TWOCAPTCHA_API_KEY")`. Add `"TWOCAPTCHA_API_KEY"` to `SECRET_KEYS` list in `core/credentials.py` before writing any other CAPTCHA code (STATE.md Phase 14 flag: "Add CAPTCHA_API_KEY to SECRET_KEYS before writing any CAPTCHA code").
**Warning signs:** `pydantic_settings` warning about unknown env var; `writeLog` output containing a 32-char hex string.

### Pitfall 2: Calling solve_recaptcha Directly in the Async Event Loop
**What goes wrong:** The event loop blocks for 15-115 seconds; all other plugin poll tasks stall; orchestrator appears frozen.
**Why it happens:** `solve_recaptcha` calls `time.sleep` internally.
**How to avoid:** Always wrap via `loop.run_in_executor(None, solver.solve_recaptcha, ...)`. See Pattern 4. asyncio.timeout must wrap the `await run_in_executor(...)` call, not the inner sync function.
**Warning signs:** Other plugin tasks stop updating during a CAPTCHA solve attempt.

### Pitfall 3: asyncio.timeout Scope Wraps Only the executor call, Not a broader `async with`
**What goes wrong:** `asyncio.timeout(120)` applied to the wrong scope cancels unrelated awaits.
**Why it happens:** `async with asyncio.timeout(120):` in a long try block.
**How to avoid:** The timeout context manager must wrap exactly the `await loop.run_in_executor(...)` line and nothing else. See Pattern 4.
**Warning signs:** Random unrelated plugin operations raising `asyncio.TimeoutError`.

### Pitfall 4: Reusing Amazon WAF iv/context Parameters
**What goes wrong:** 2captcha returns a valid token but Amazon rejects it ("invalid token") because the iv/context have expired.
**Why it happens:** Parameters are extracted once at CAPTCHA detection time; the solve takes >30 seconds.
**How to avoid:** Re-extract `window.gokuProps` immediately before calling `solve_amazon_waf`, not at `detect_captcha()` time. Log a warning if extraction yields None (page may have changed state).
**Warning signs:** 2captcha returns a token but the page CAPTCHA still shows after injection.

### Pitfall 5: Amazon.com "Enter the characters you see" vs AWS WAF CAPTCHA Confusion
**What goes wrong:** Code treats the simple Amazon product-page text CAPTCHA as an AWS WAF CAPTCHA, causing the wrong solve path to be invoked.
**Why it happens:** Both appear on Amazon domains but are mechanically different.
**How to avoid:** The existing `detect_captcha()` in `AmazonPlugin` already detects the text CAPTCHA via `"Enter the characters you see below"` string. This is a simple image-character CAPTCHA — NOT the AWS WAF type (which uses `window.gokuProps`). Keep these as separate detection paths. AWS WAF CAPTCHA appears on the challenged page before the actual product page loads; detect it by checking for `window.gokuProps` presence.
**Warning signs:** `tab.evaluate(waf_params_js)` returns None on what appears to be a CAPTCHA page.

### Pitfall 6: Logging str(exc) on 2captcha Error Paths
**What goes wrong:** `requests.exceptions.ConnectionError` str representation may include the URL with the embedded API key if it appears in the query string.
**Why it happens:** Standard `f"error: {exc}"` pattern.
**How to avoid:** Log only `exc.__class__.__name__`, never `str(exc)`. See STATE.md Phase 14 flag: "Log only `exc.__class__.__name__` on proxy/CAPTCHA exception paths — never `str(exc)`."
**Warning signs:** Log line containing a 32-character hex string.

### Pitfall 7: solve_count Not Resetting Between Bot Runs
**What goes wrong:** Second invocation of `BotService.run()` picks up the old `CaptchaSolver` with exhausted `_solve_count`, skipping all solves.
**Why it happens:** `CaptchaSolver` instance is long-lived; counter is never reset.
**How to avoid:** `CaptchaSolver` is constructed fresh on each `BotService.start()` / `BotService.run()` call (in `async_main`, not in `BotService.__init__`). Balance check runs at startup of each run.
**Warning signs:** After the first run, CAPTCHA solving is always skipped even though the cap has not been reached in the current session.

### Pitfall 8: Plugin ABC Version Bump
**What goes wrong:** Adding a required `solve_captcha()` abstract method would break all existing plugins.
**Why it happens:** Temptation to add the solver as an ABC method.
**How to avoid:** Solver is injected as an optional attribute (`self._captcha_solver`) via `registry.assign_solver(plugin)` just as `self._proxy` is injected. No ABC changes, no `PLUGIN_API_VERSION` bump.
**Warning signs:** `test_plugin_base.py` or ABC subclass tests fail with `TypeError: Can't instantiate abstract class`.

## Code Examples

### reCAPTCHA v2 Sitekey Extraction (nodriver tab.evaluate)
```python
# Source: https://2captcha.com/h/recaptcha-v2-callback (WebFetch verified)
sitekey = await tab.evaluate(
    "document.querySelector('[data-sitekey]')?.getAttribute('data-sitekey') || ''"
)
if not sitekey:
    # No sitekey found -- CAPTCHA may have already cleared or wrong detection
    return None
```

### Token Injection (nodriver tab.evaluate)
```python
# Source: https://2captcha.com/h/recaptcha-v2-callback (WebFetch verified)
# Double-escaped braces for Python f-string inside JS IIFE
inject_js = (
    f"(function(){{"
    f"  var el = document.getElementById('g-recaptcha-response');"
    f"  if (el) {{ el.value = '{token}'; }}"
    f"  var clients = window.___grecaptcha_cfg && window.___grecaptcha_cfg.clients;"
    f"  if (clients) {{"
    f"    Object.values(clients).forEach(function(c) {{"
    f"      if (c && c.callback) {{ try {{ c.callback('{token}'); }} catch(e) {{}} }}"
    f"    }});"
    f"  }}"
    f"}})();"
)
await tab.evaluate(inject_js)
```

### Amazon WAF Param Extraction
```python
# Source: https://2captcha.com/h/how-to-bypass-amazon-captcha (WebFetch verified)
waf_js = """(function(){
  var p = window.gokuProps;
  if(!p) return null;
  return JSON.stringify({key: p.key, iv: p.iv, context: p.context});
})();"""
raw = await tab.evaluate(waf_js)
if raw:
    import json
    waf_params = json.loads(raw)  # {key, iv, context}
```

### Balance Check (v1 legacy endpoint)
```python
# Source: https://2captcha.com/2captcha-api (WebFetch verified)
resp = requests.get(
    "https://2captcha.com/res.php",
    params={"key": api_key, "action": "getbalance"},
    timeout=10,
)
resp.raise_for_status()
text = resp.text.strip()
if text.startswith("ERROR_"):
    raise RuntimeError(f"2captcha balance error: {text}")
balance = float(text)  # e.g. "3.45"
```

### CaptchaConfig Pydantic Model (mirrors ProxyConfig pattern)
```python
# Source: core/config_schema.py (ProxyConfig pattern) [VERIFIED: read source]
class CaptchaConfig(BaseModel):
    """Opt-in CAPTCHA solving config (ANTI-06/07). Disabled by default.

    API key lives EXCLUSIVELY in CredentialStore (TWOCAPTCHA_API_KEY), never here.
    """
    enabled: bool = False
    max_solves_per_run: int = 10
    low_balance_threshold: float = 1.00
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 2captcha SDK (`2captcha-python`) | Hand-rolled requests client | Decision in CONTEXT.md | No new dep; 80-line sync client sufficient |
| 2captcha JSON API v2 (api.2captcha.com) | 2captcha v1 API (in.php/res.php) | Decision in CONTEXT.md | v1 is "stable and supported"; simpler response parsing |
| Amazon WAF token in cookie | Token in HTTP header (`X-Amz-Captcha-Token`) | Amazon WAF spec | Injection method varies; must be verified by monitoring Network tab manually |

**Deprecated/outdated:**
- `captcha_solver:` config key (from roadmap v3.0 rough notes): replaced by `captcha:` per CONTEXT.md locked decision.
- `CAPTCHA_API_KEY` name (mentioned in STATE.md Phase 14 research flags): confirmed final name is `TWOCAPTCHA_API_KEY` (more specific; avoids ambiguity with other services).

## Open Questions

1. **Amazon WAF CAPTCHA token application path on Amazon.com**
   - What we know: 2captcha returns `captcha_voucher` and `existing_token`; they may be sent as cookie, header, or POST body depending on the site's WAF integration.
   - What's unclear: Amazon.com's specific injection path for the WAF token is not publicly documented; it requires monitoring the Network tab during a manual solve.
   - Recommendation: Scope Phase 14 to use manual-pause fallback for the Amazon WAF type (window.gokuProps present) and add a `# TODO: Phase 14 WAF token injection` comment. The simpler text CAPTCHA (existing `detect_captcha` path) is the primary solve target. This bounds scope and avoids a fragile injection that will break with WAF updates.

2. **Does BestBuy show reCAPTCHA v2 or another type?**
   - What we know: BestBuy has a `detect_captcha()` no-op default (inherits from ABC); Phase 13 wired proxy but not CAPTCHA for BestBuy.
   - What's unclear: BestBuy may show Akamai or Cloudflare challenge rather than standard reCAPTCHA v2.
   - Recommendation: Wire the reCAPTCHA v2 solve path into BestBuy as a best-effort (sitekey extraction will return empty string if no reCAPTCHA widget present); fall back to manual pause if sitekey is empty. This satisfies ANTI-06 without requiring live BestBuy investigation.

3. **asyncio.timeout availability**
   - What we know: `asyncio.timeout()` is Python 3.11+; the project runs Python 3.13.13 [VERIFIED: python --version].
   - What's unclear: Nothing — 3.13 fully supports it.
   - Recommendation: Use `asyncio.timeout(120)` directly; no `asyncio.wait_for` shim needed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | Yes | 3.13.13 | — |
| requests | 2captcha HTTP client | Yes | 2.33.1 | — |
| pytest | Test suite | Yes | 8.3.4 | — |
| pytest-asyncio | Async tests | Yes | 1.3.0 | — |
| 2captcha account | Live solve verification | Unknown | — | Unit tests mock all HTTP; live test requires manual setup |

**Missing dependencies with no fallback:** None for CI. Live 2captcha integration requires a funded account with `TWOCAPTCHA_API_KEY` set — this is user-provided and out of automated test scope.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` (`asyncio_mode = "auto"`) |
| Quick run command | `pytest tests/test_captcha.py tests/test_captcha_config.py -x` |
| Full suite command | `pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ANTI-06 | CaptchaConfig parses from YAML, disabled by default | unit | `pytest tests/test_captcha_config.py -x` | No — Wave 0 |
| ANTI-06 | CaptchaSolver.from_config returns None when disabled | unit | `pytest tests/test_captcha.py::test_solver_disabled -x` | No — Wave 0 |
| ANTI-06 | CaptchaSolver.from_config returns None when key missing | unit | `pytest tests/test_captcha.py::test_solver_no_key -x` | No — Wave 0 |
| ANTI-06 | solve_recaptcha submits and polls (mock HTTP) | unit | `pytest tests/test_captcha.py::test_solve_recaptcha_success -x` | No — Wave 0 |
| ANTI-06 | solve_recaptcha raises on ERROR_ response | unit | `pytest tests/test_captcha.py::test_solve_recaptcha_error -x` | No — Wave 0 |
| ANTI-06 | can_solve returns False when cap hit | unit | `pytest tests/test_captcha.py::test_cap_enforced -x` | No — Wave 0 |
| ANTI-06 | API key never logged (no str(exc), no key in log output) | unit | `pytest tests/test_captcha.py::test_key_not_logged -x` | No — Wave 0 |
| ANTI-06 | registry.assign_solver mirrors assign_proxy pattern | unit | `pytest tests/test_captcha_wiring.py::test_assign_solver -x` | No — Wave 0 |
| ANTI-06 | Plugin uses solver then falls back to manual pause on failure | unit | `pytest tests/test_captcha_wiring.py::test_plugin_fallback -x` | No — Wave 0 |
| ANTI-07 | Balance check at startup: WARNING logged when low | unit | `pytest tests/test_captcha.py::test_low_balance_warning -x` | No — Wave 0 |
| ANTI-07 | Balance check: balance_ok=False when zero; solver skipped | unit | `pytest tests/test_captcha.py::test_zero_balance_disables_solver -x` | No — Wave 0 |
| ANTI-07 | ERROR_ZERO_BALANCE response handled as zero balance | unit | `pytest tests/test_captcha.py::test_balance_error_zero -x` | No — Wave 0 |
| STAB-03 | CaptchaConfig: AppConfig.captcha present and typed | unit | `pytest tests/test_captcha_config.py::test_appconfig_has_captcha_field -x` | No — Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_captcha.py tests/test_captcha_config.py tests/test_captcha_wiring.py -x`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green (currently 414 tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_captcha.py` — covers ANTI-06/ANTI-07 solver unit tests
- [ ] `tests/test_captcha_config.py` — covers ANTI-06 config parsing + STAB-03
- [ ] `tests/test_captcha_wiring.py` — covers ANTI-06 service/registry/plugin wiring

*(No framework installs needed — pytest + pytest-asyncio already present)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Token from 2captcha is opaque string; validate non-empty before JS injection |
| V6 Cryptography | no | No key generation; CredentialStore handles storage |

### Known Threat Patterns for 2captcha integration

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key in log output | Information Disclosure | Log only `exc.__class__.__name__`; never `str(exc)` on URL-bearing exception; never log `self._api_key` |
| API key in config.yml | Information Disclosure | No `api_key` field in `CaptchaConfig`; read exclusively from `CredentialStore` |
| JS injection of untrusted token | Tampering | Token is an opaque string from 2captcha; sanitize by ensuring it contains no `'` or `\n` before embedding in JS string literal |
| Unbounded API charges | Denial of Wallet | `max_solves_per_run` hard cap enforced in `can_solve()`; balance check at startup |
| Stale Amazon WAF parameters | Tampering / Repudiation | Re-extract `window.gokuProps` immediately before each solve attempt; abort if older than ~20s |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The 2captcha v1 in.php/res.php API is stable for reCAPTCHA v2 and Amazon WAF | Standard Stack / Code Examples | Would require using JSON API v2 (api.2captcha.com) instead; trivial change |
| A2 | Amazon.com product pages show the text CAPTCHA ("Enter the characters you see"), not AWS WAF CAPTCHA | Common Pitfalls #5 | If WAF CAPTCHA is actually shown, the reCAPTCHA solve path produces empty sitekey and falls back to manual — no silent failure |
| A3 | BestBuy shows reCAPTCHA v2 (not Akamai/Cloudflare) when a challenge appears | Open Questions #2 | Empty sitekey extraction falls back to manual pause — no silent failure |
| A4 | `window.gokuProps` is the stable extraction point for Amazon WAF parameters | Architecture Patterns #6 | Could be obfuscated/renamed; pattern fallback is manual pause |

## Sources

### Primary (HIGH confidence)
- https://2captcha.com/2captcha-api — Legacy v1 in.php/res.php API; reCAPTCHA v2 submit params, poll format, error codes verified via WebFetch
- https://2captcha.com/api-docs/recaptcha-v2 — RecaptchaV2TaskProxyless task type, websiteKey/websiteURL params verified via WebFetch
- https://2captcha.com/api-docs/amazon-aws-waf-captcha — AmazonTask type, iv/context/websiteKey params, captcha_voucher/existing_token response verified via WebFetch
- https://2captcha.com/api-docs/error-codes — Full error code table verified via WebFetch
- https://2captcha.com/api-docs/get-balance — JSON API v2 balance format (errorId + balance float) verified via WebFetch
- https://2captcha.com/h/recaptcha-v2-callback — Sitekey extraction + callback detection + token injection JS verified via WebFetch
- `core/credentials.py` — CredentialStore.get() API, SECRET_KEYS list, EnvVarBackend pattern [VERIFIED: read source]
- `core/config_schema.py` — ProxyConfig pattern (the analog for CaptchaConfig) [VERIFIED: read source]
- `core/stealth.py` — ProxyPool class pattern + run_in_executor usage [VERIFIED: read source]
- `core/orchestrator.py` — ProxyPool wiring path in async_main [VERIFIED: read source]
- `core/registry.py` — assign_proxy pattern (analog for assign_solver) [VERIFIED: read source]
- `core/service.py` — BotService startup log pattern [VERIFIED: read source]
- `plugins/shopbot_plugin_amazon.py` — detect_captcha + _wait_user_action manual-pause path [VERIFIED: read source]

### Secondary (MEDIUM confidence)
- https://2captcha.com/h/how-to-bypass-amazon-captcha — window.gokuProps extraction approach (multiple sources agree on this)
- WebSearch result confirming 15-20s initial wait + 5s poll interval for reCAPTCHA v2

### Tertiary (LOW confidence)
- A2 (assumption): Amazon.com product pages show text CAPTCHA not WAF CAPTCHA — not live-verified

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — requests pinned and verified; no new deps
- 2captcha v1 API protocol: HIGH — in.php/res.php params confirmed via official docs WebFetch
- Amazon WAF token injection: LOW — token application path site-specific; requires manual Network tab inspection
- reCAPTCHA token injection: MEDIUM — JS pattern confirmed via 2captcha docs; nodriver tab.evaluate is the right mechanism per project patterns
- Architecture: HIGH — mirrors Phase 13 ProxyPool wiring exactly; all source files read

**Research date:** 2026-06-09
**Valid until:** 2026-09-09 (stable API; 90-day window appropriate; Amazon WAF detection logic may change sooner)
