---
phase: 13-anti-detection-layer-1-fingerprint-proxy
reviewed: 2026-06-09T00:00:00Z
depth: deep
files_reviewed: 12
files_reviewed_list:
  - core/stealth.py
  - core/config_schema.py
  - core/service.py
  - core/orchestrator.py
  - core/registry.py
  - plugins/shopbot_plugin_amazon.py
  - plugins/shopbot_plugin_bestbuy.py
  - plugins/shopbot_plugin_gamestop.py
  - plugins/shopbot_plugin_newegg.py
  - plugins/shopbot_plugin_squareenix.py
  - plugins/shopbot_plugin_target.py
  - plugins/shopbot_plugin_walmart.py
findings:
  critical: 4
  warning: 5
  info: 3
  total: 12
status: fixed
---

# Phase 13: Code Review Report

**Reviewed:** 2026-06-09
**Depth:** deep
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 13 adds a fingerprint stealth layer (STEALTH_JS + CDP injection), a round-robin proxy
pool with retire/cooldown, and wires both into all seven retailer plugins. The credential-
safety discipline is solid: credentials never appear in `--proxy-server` args, the startup
log, or exception strings. The fail-loud exhaustion guard is present in every plugin.

Four critical issues were found. Two are real-IP leak vectors. One is a silent proxy
bypass that defeats the entire point of proxy rotation. One is an unhandled `None` in URL
parsing that will crash when a proxy URL omits the port. Three warnings relate to
correctness of the round-robin advance logic, a ban-detection gap in BestBuy and five other
plugins, and an unchecked task reference in the CDP auth handler. Three info items cover
code quality.

## Critical Issues

### CR-01: `advance()` skips the current entry on first call, permanently skipping proxy[0]

**File:** `core/stealth.py:218-231`
**Issue:** `advance()` increments `_index` before reading the entry. On a freshly
constructed pool `_index=0`. The first call to `advance()` sets `_index=1` and returns
`entries[1]`, permanently skipping `entries[0]` for the lifetime of the pool. With a
single-proxy pool, `advance()` wraps back to index 0 and returns it correctly, but with
two or more proxies the first entry is never used at startup. The current-entry accessor
`current()` returns `entries[0]`, which is never the active proxy, making `current()` dead
relative to what is actually in use.

**Fix:** Either seed `_index = -1` so the first advance lands on index 0, or change
`assign_proxy` to call `current()` for the first plugin and `advance()` for subsequent
ones. The minimal fix is in `__init__`:

```python
self._index = -1          # was 0; advance() increments before read
```

Then `advance()` becomes:
```python
self._index = (self._index + 1) % len(self._entries)
entry = self._entries[self._index]
if not entry.is_retired():
    return entry
# ... rest of loop
```

With `_index=-1` the exhaustion loop still iterates `len(self._entries)` times and the
all-retired detection remains correct.

### CR-02: BestBuy `check_availability` has no ban-phrase scan; real IP leaks silently when banned

**File:** `plugins/shopbot_plugin_bestbuy.py:70-86`
**Issue:** Amazon's `check_availability` calls `_is_ban_response` and records a proxy
failure on ban. BestBuy's `check_availability` does not: it navigates, tries a selector,
and returns False on miss. When BestBuy returns a 403 / bot-challenge page the bot silently
treats it as "not available" and keeps using the same proxy indefinitely, never rotating
away and never surfacing the ban to the operator.

This is the same pattern as ANTI-05 which was explicitly applied only to Amazon in this
phase. All five non-Amazon, non-UA-rotating plugins (BestBuy, Target, Walmart, GameStop,
Newegg, SquareEnix) have the same gap, but BestBuy is the most established flow and the
most likely to be exercised in production.

**Fix:** Add the same ban-scan block that Amazon has, directly after `tab = await
self.driver.get(url)`:

```python
body_text = ""
try:
    body_text = await tab.evaluate("document.body.innerText") or ""
except Exception:
    pass
if _is_ban_response(0, body_text):
    proxy = getattr(self, "_proxy", None)
    pool = getattr(self, "_pool", None)
    if proxy and pool:
        pool.record_failure(proxy)
    return False
```

Import `_is_ban_response` (already imported in the file header). Apply identically to
Target, Walmart, GameStop, Newegg, and SquareEnix.

### CR-03: `_parse_proxy_url` raises `TypeError` on port-less URLs, causing an unhandled crash that silently falls back to no-proxy

**File:** `core/stealth.py:123-131`
**Issue:** `urlparse("http://user:pass@proxy.example.com").port` is `None` when no port is
given. The f-string `f"{parsed.hostname}:{parsed.port}"` then produces
`"proxy.example.com:None"`. Chrome ignores such an unparseable `--proxy-server` value and
silently connects directly, leaking the real IP. No exception is raised; the proxy just
does not work.

A slightly more broken URL (e.g. `http://:8080`) makes `parsed.hostname` also `None`,
producing `"None:8080"` for the same silent-bypass result.

**Fix:** Add validation in `_parse_proxy_url` and raise a clear `ValueError` so
`ProxyPool.from_urls` fails at startup rather than silently constructing a broken entry:

```python
def _parse_proxy_url(url: str) -> tuple:
    parsed = urlparse(url)
    if not parsed.hostname:
        raise ValueError(f"Proxy URL missing hostname: {url!r}")
    if parsed.port is None:
        raise ValueError(f"Proxy URL missing port: {url!r}")
    host_port = f"{parsed.hostname}:{parsed.port}"
    return host_port, parsed.username or "", parsed.password or ""
```

### CR-04: `asyncio.create_task()` in `setup_proxy_auth` handlers fires without saving the task reference; tasks can be silently garbage-collected before the auth handshake completes

**File:** `core/stealth.py:279-298`
**Issue:** CPython's asyncio garbage-collects tasks that have no references. Both
`_on_request_paused` and `_on_auth_required` call `asyncio.create_task(...)` without
storing the result. The Python docs explicitly warn: "Save a reference to the result of
this function, to avoid a task disappearing mid-execution." When the GC runs between the
`create_task` call and the first iteration of the event loop, the task is collected and the
407 challenge goes unanswered, causing all authenticated proxy requests to fail silently
(Chrome proceeds without credentials, sending real-IP traffic). This is a real-IP exposure
vector, not merely a reliability issue.

**Fix:** Capture the task and hold a strong reference until it completes. The cleanest
approach is a module-level weakref set:

```python
_live_tasks: set = set()

async def _on_auth_required(event: fetch.AuthRequired) -> None:
    t = asyncio.create_task(
        tab.send(fetch.continue_with_auth(
            request_id=event.request_id,
            auth_challenge_response=fetch.AuthChallengeResponse(
                response="ProvideCredentials",
                username=username,
                password=password,
            ),
        ))
    )
    _live_tasks.add(t)
    t.add_done_callback(_live_tasks.discard)
```

Apply the same pattern to `_on_request_paused`.

## Warnings

### WR-01: `record_failure` resets `failures` to 0 on retire; a proxy that gets retired and un-retires can reach max_failures again in one request instead of requiring a clean slate

**File:** `core/stealth.py:154-161`
**Issue:** `record_failure` resets `self.failures = 0` when retiring, so after cooldown
elapses the counter is clean. That part is correct. The issue is that `retired_until` is
only set once and never cleared. After the cooldown elapses, `is_retired()` returns False
and the entry re-enters rotation, but `retired_until` still holds the past timestamp. A
subsequent ban that does NOT trip `max_failures` (i.e. failures < 3) accumulates on the
0-based counter normally, which is correct. This path is fine.

The actual bug: `record_success` only resets `failures` but does not clear `retired_until`.
If a proxy is retired, its cooldown expires, it gets one successful request, then bans
again, `record_success` does not clear `retired_until`. That is acceptable. The more
concrete WR is that `current()` and `advance()` asymmetry (see CR-01) means the pool
state a caller can query via `current()` does not reflect the proxy actually in use.
`current()` should be documented or removed to avoid future misuse.

**Fix:** Add a `# NOTE: current() reflects the index cursor, not the last assigned proxy`
docstring clarification, or expose a separate `last_assigned` property that plugins set.

### WR-02: Amazon and BestBuy plugins pass `browser_args=None` to `nodriver.start()` when no proxy is configured, instead of omitting the parameter entirely

**File:** `plugins/shopbot_plugin_amazon.py:68`, `plugins/shopbot_plugin_bestbuy.py:53`
**Issue:** Both plugins do:
```python
browser_args = build_proxy_browser_args(proxy) or None
self.driver = await nodriver.start(headless=headless, browser_args=browser_args)
```

`build_proxy_browser_args(None)` returns `[]`. `[] or None` evaluates to `None`.
`nodriver.start(browser_args=None)` — depending on the nodriver version — may pass `None`
through to the underlying `Config` object and either crash or behave differently than
omitting the parameter. The five UA-rotating plugins (Walmart, Target, GameStop, Newegg,
SquareEnix) correctly pass a non-empty list that always has at least the UA arg, so this
issue is specific to Amazon and BestBuy, which have no UA rotation.

**Fix:** Pass `browser_args` as an empty list, not None:

```python
browser_args = build_proxy_browser_args(proxy)   # returns [] or [args...]
self.driver = await nodriver.start(headless=headless, browser_args=browser_args)
```

Remove the `or None` coercion on both lines.

### WR-03: `assign_proxy` is called in both `_staggered_setup` (orchestrator) and `setup_for_items` (registry), advancing the pool index twice per plugin

**File:** `core/orchestrator.py:186`, `core/registry.py:142`
**Issue:** Both code paths that initialize plugins call `registry.assign_proxy(plugin)`
before `plugin.setup()`. `_staggered_setup` is used by `async_main`. `setup_for_items` is
the registry's own method, used by legacy callers. If any caller ever routes through
`setup_for_items` instead of `_staggered_setup`, proxy assignment happens via the registry
method, not the orchestrator, but the double-assign pattern means any future code that
calls both would burn two pool slots per plugin. Currently only one path is active, so this
is latent. It also makes the data flow unclear: proxy assignment semantics are split across
two files.

**Fix:** Remove `self.assign_proxy(plugin)` from `setup_for_items` in registry.py and
document that proxy assignment is the caller's responsibility before invoking `setup()`.
Or consolidate by removing the call from `_staggered_setup` and relying solely on
`setup_for_items`. Pick one owner.

### WR-04: `_is_ban_response` scans the entire body text on every check; large DOM bodies cause visible latency spikes

**File:** `core/stealth.py:110-115`
**Issue:** `body_text.lower()` copies the entire DOM innerText string, then six `in`
substring searches walk up to the full length. For large product pages (50-200 KB of text)
this runs entirely in Python on the event loop thread, blocking other coroutines for
measurable durations. The function itself has no length cap.

This is a correctness-adjacent issue because it can starve the asyncio event loop
momentarily. It is also trivially exploitable by a site returning a huge page to slow down
the bot's polling cycle.

**Fix:** Cap the body scan to the first 8 KB, which is sufficient to catch ban phrases in
page headers:

```python
def _is_ban_response(status_code: int, body_text: str) -> bool:
    if status_code in _BAN_STATUSES:
        return True
    lower = body_text[:8192].lower()
    return any(phrase in lower for phrase in _BAN_PHRASES)
```

### WR-05: `ProxyConfig.urls` accepts any string with no format validation; a typo silently produces a broken `_ProxyEntry` that bypasses proxy

**File:** `core/config_schema.py:217-229`
**Issue:** `urls: list[str]` applies no format validation beyond "is a string". A user who
writes `proxy.example.com:8080` (no scheme) instead of `http://proxy.example.com:8080` in
config.yml gets `urlparse` returning an empty hostname (the whole thing is treated as a
path), which then produces a `_ProxyEntry` with `host_port="None:None"`. Chrome ignores
this `--proxy-server` value and connects directly. CR-03 partially addresses this by
raising in `_parse_proxy_url`, but the Pydantic model is the right place to reject bad
input at load time, before pool construction.

**Fix:** Add a `field_validator` to `ProxyConfig`:

```python
from pydantic import field_validator

@field_validator("urls", mode="before")
@classmethod
def validate_proxy_urls(cls, v):
    for url in v:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.hostname or parsed.port is None:
            raise ValueError(
                f"Invalid proxy URL {url!r}: must be scheme://[user:pass@]host:port"
            )
    return v
```

## Info

### IN-01: STEALTH_JS Patch 2 creates a fake `PluginArray` with `length=0` on each plugin object, contradicting the outer `arr.length=3`

**File:** `core/stealth.py:53-59`
**Issue:** Each fake plugin object has `Object.defineProperty(plugin, 'length', { value: 0 })`.
This sets the plugin's own `length` to 0. The outer array gets `length=3`. Modern browser
fingerprinting libraries check individual plugin `.length` (number of MIME types it
supports). Setting it to 0 is technically valid (Chrome PDF Plugin registers 1 MIME type)
but is itself a detectable signal. This is a minor fingerprint quality issue, not a
security bug.

**Fix:** Set realistic MIME type counts per plugin or omit the length property on
individual plugin objects, letting it fall through to `Plugin.prototype.length`.

### IN-02: `service.py` imports `ProxyPool` but never uses it

**File:** `core/service.py:20`
**Issue:** `from core.stealth import ProxyPool` is present but `ProxyPool` is not referenced
anywhere in `service.py`. Pool construction happens in `orchestrator.py`. This is a dead
import introduced during Phase 13 wiring.

**Fix:** Remove the import from `service.py`.

### IN-03: `_ProxyEntry.url` field stores the full credential-bearing URL in memory as a plain dataclass attribute; any future `repr()` or `str()` call will expose credentials

**File:** `core/stealth.py:141-143`
**Issue:** `_ProxyEntry` has `url: str` which holds the raw `scheme://user:pass@host:port`
string. The dataclass auto-generates a `__repr__` that includes all fields. Any accidental
`writeLog(f"entry={entry!r}", ...)` or `str(entry)` in future code will emit credentials
to the log file. The comment says "NEVER log this field" but there is no enforcement.

**Fix:** Override `__repr__` to redact the url field:

```python
def __repr__(self) -> str:
    return (
        f"_ProxyEntry(host_port={self.host_port!r}, "
        f"failures={self.failures}, retired_until={self.retired_until})"
    )
```

---

_Reviewed: 2026-06-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
