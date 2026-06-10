# Phase 13: Anti-Detection Layer 1 — Fingerprint + Proxy — Research

**Researched:** 2026-06-09
**Domain:** nodriver (CDP), browser fingerprint stealth, proxy rotation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Hand-rolled CDP injection: `core/stealth.py` builds the patch JS and injects it via CDP
  `addScriptToEvaluateOnNewDocument` (or the nodriver equivalent) at browser startup. NO new dependency.
- Patches required: `window.chrome`, `navigator.plugins`, `navigator.languages`,
  screen-dimension spoofing.
- WebRTC: set Chrome preferences at launch to prevent real-IP leak through the proxy tunnel.
- Opt-in `proxy:` config section, disabled by default. Lists `scheme://[user:pass@]host:port` URLs.
- Accept authenticated proxies (`user:pass@`) — credentials treated as secrets, never logged
  plaintext. The startup log line is `Proxy rotation: enabled, pool_size=N` (no credentials).
- Rotation order: round-robin (sequential cycling) — deterministic and testable.
- Each proxy scoped to its plugin instance via `self._proxy`; rotation happens only at browser
  restart, not mid-session.
- Ban signals: HTTP 403 / 429 / 503, challenge-redirect, block-phrase in response body.
- Retire a proxy after **3 consecutive failures** (configurable), with a **300s cooldown**
  (configurable) before it re-enters the pool.
- On ban signal: rotate to the next proxy (at restart boundary per scoping rule above).

### Claude's Discretion
- Exact block-phrase list, config schema field names/shape (follow existing `core/config_schema.py`
  conventions), internal class/module structure of `core/stealth.py` and the proxy pool/manager,
  and how rotation integrates with `core/plugin_base.py` browser launch.

### Deferred Ideas (OUT OF SCOPE)
- CAPTCHA solving — Phase 14.
- Broad test hardening for all v3.0 features — Phase 17.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ANTI-04 | Opt-in `proxy:` section, sticky sessions (one IP per check cycle), configurable pool | ProxyPool round-robin with per-instance `self._proxy`; proxy set at `setup()` time and held for lifecycle of that browser instance |
| ANTI-05 | Ban-signal detection (HTTP 403/429/503, challenge-redirect, body phrase), rotate + retire after N consecutive failures | `cdp.network` response interception in tab; ban signals → flag on plugin instance → rotate at next `teardown+setup` cycle |
| ANTI-08 | JS fingerprint stealth patch at every browser startup via shared `core/stealth.py`, no ABC version bump | `tab.send(cdp.page.add_script_to_evaluate_on_new_document(JS))` on `browser.main_tab` right after `nodriver.start()`; no ABC change because called inside existing `setup()` body |
</phase_requirements>

---

## Summary

The project uses **nodriver 0.50.3** (pinned in `requirements.txt`). The `nodriver.start()` function
accepts a `browser_args: List[str]` parameter that maps directly to Chrome command-line arguments.
This is the mechanism for both proxy injection (`--proxy-server=host:port`) and WebRTC leak
prevention (`--force-webrtc-ip-handling-policy=disable_non_proxied_udp`). All browser args are
passed when constructing the `nodriver.Config` internally; they are NOT blocked by the config
guard for `headless`, `data-dir`, `sandbox`, or `lang`.

CDP fingerprint injection (`Page.addScriptToEvaluateOnNewDocument`) is exposed in nodriver as
`cdp.page.add_script_to_evaluate_on_new_document(source)` and is already used internally by
nodriver's `_prepare_expert` path — confirming the API is stable at version 0.50.3. The call
pattern is `await tab.send(cdp.page.add_script_to_evaluate_on_new_document(JS_STRING))`.

Authenticated proxy (`user:pass@host:port`) is NOT supported via `--proxy-server` inline
credentials in Chrome. The standard solution is CDP `Fetch.enable(handle_auth_requests=True)` +
listening for `Fetch.AuthRequired` events and responding with `Fetch.continueWithAuth`.
nodriver exposes both as `cdp.fetch.enable(...)` and `cdp.fetch.continue_with_auth(...)`, and the
`Connection.add_handler(event_type, callback)` API registers event listeners on any `Tab` or
`Browser` connection object.

**Primary recommendation:** Implement `core/stealth.py` as two orthogonal pieces: (1) a
`apply_stealth(tab)` coroutine that injects the fingerprint JS via `cdp.page`, and (2) a
`ProxyPool` class that manages round-robin rotation and tracks failure counts. Both are called
from inside each plugin's existing `setup()` method — no ABC change, no new dependencies.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fingerprint JS injection | Plugin (browser startup) | core/stealth.py (utility) | Must happen once per browser launch; `setup()` owns that moment |
| Proxy arg injection | Plugin `setup()` | ProxyPool (state mgmt) | Browser launch args are set at `nodriver.start()` call time |
| Proxy auth (Fetch.enable) | Plugin `setup()` post-start | core/stealth.py helper | Tab event handler must be registered on the live tab after launch |
| Ban-signal detection | Plugin `check_availability()` | orchestrator restart | HTTP status + body check in the plugin's exception / return path |
| Proxy rotation state | core/stealth.py ProxyPool | plugin `self._proxy` | Per-instance state; global ProxyPool shared across plugins but each plugin holds its own current slot |
| Config parsing (proxy:) | core/config_schema.py ProxyConfig | AppConfig | Follows existing Pydantic nested model pattern |
| WebRTC prevention | Plugin `setup()` → browser_args | Chrome flag | Set at launch time via `--force-webrtc-ip-handling-policy` |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| nodriver | 0.50.3 (pinned) | CDP browser automation | Already in use; provides `tab.send()` + `add_handler()` |
| Python stdlib `urllib.parse` | 3.x | Parse `scheme://user:pass@host:port` URL | No new dep needed for URL decomposition |

### Supporting
None required. All functionality is achievable with nodriver's existing CDP bindings and
Python stdlib.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled CDP stealth JS | `puppeteer-extra-plugin-stealth` equivalent (Python) | No Python equivalent with sufficient quality; project rule forbids new deps without necessity |
| CDP Fetch.enable for proxy auth | in-memory Chrome extension | Extension approach unreliable in Chrome >= 120; CDP approach has no timing issues |
| `--force-webrtc-ip-handling-policy` flag | CDP `cdp.network` pref override | Flag is simpler, works at launch before any JS runs |

**Installation:** No new packages required.

---

## Package Legitimacy Audit

No new packages are introduced in this phase. All implementation uses nodriver 0.50.3 (already
installed and pinned) and Python stdlib.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| nodriver | PyPI | ~3 yrs | High | github.com/ultrafunkamsterdam/nodriver | N/A — already installed | Approved (existing dep) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Plugin.setup()
    |
    +-- build browser_args list
    |       +-- ["--proxy-server=host:port"]     (if proxy configured)
    |       +-- ["--force-webrtc-ip-handling-policy=disable_non_proxied_udp"]  (if proxy configured)
    |
    +-- nodriver.start(browser_args=[...])
    |
    +-- apply_stealth(browser.main_tab)
    |       +-- cdp.page.enable()
    |       +-- cdp.page.add_script_to_evaluate_on_new_document(STEALTH_JS)
    |
    +-- (if proxy has credentials)
    |       +-- tab.add_handler(cdp.fetch.AuthRequired, _auth_handler)
    |       +-- await tab.send(cdp.fetch.enable(handle_auth_requests=True))
    |
    +-- self._proxy = current_proxy_entry  (stored on instance)


Plugin.check_availability()
    |
    +-- navigate to URL
    +-- on HTTP 403/429/503 / challenge / block-phrase:
            +-- proxy_pool.record_failure(self._proxy)
            +-- (ban rotation happens at NEXT teardown+setup, not mid-session)


BotService restart cycle (orchestrator teardown + setup)
    +-- plugin.teardown()  -> driver.stop()
    +-- proxy_pool.next_proxy()  -> returns next live proxy (skips retired ones)
    +-- plugin.setup()  -> launches with new proxy
```

### Recommended Project Structure
```
core/
├── stealth.py          # apply_stealth(tab), STEALTH_JS constant, ProxyPool, ProxyConfig utils
config_schema.py        # ProxyConfig + ProxyEntryConfig Pydantic models; added to AppConfig
tests/
├── test_stealth.py     # unit tests: ProxyPool rotation, retire/cooldown, config parsing
sample.config.yml       # proxy: section (disabled by default, documented)
```

`core/stealth.py` stays under 300 lines. If it grows beyond that, split `ProxyPool` to
`core/proxy_pool.py`. Keep the split deferred until it is actually needed.

### Pattern 1: CDP Fingerprint Injection

**What:** Inject JS that patches navigator/window properties before any page script runs.
**When to use:** Every browser startup, immediately after `nodriver.start()`.

```python
# Source: nodriver 0.50.3 core/tab.py _prepare_expert (confirmed via source read)
# and cdp/page.py add_script_to_evaluate_on_new_document
import nodriver
from nodriver import cdp

STEALTH_JS = """
(function () {
  // Patch 1: window.chrome -- headless Chrome lacks this object entirely
  if (!window.chrome) {
    Object.defineProperty(window, 'chrome', {
      value: { runtime: {} },
      writable: false,
      enumerable: true,
      configurable: false,
    });
  }

  // Patch 2: navigator.plugins -- headless returns empty PluginArray
  // Spoof 3 common plugins present in real Chrome on Windows
  const fakePlugins = [
    { name: 'Chrome PDF Plugin',    filename: 'internal-pdf-viewer',    description: 'Portable Document Format' },
    { name: 'Chrome PDF Viewer',    filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
    { name: 'Native Client',        filename: 'internal-nacl-plugin',   description: '' },
  ];
  Object.defineProperty(navigator, 'plugins', {
    get: () => {
      const arr = Object.create(PluginArray.prototype);
      fakePlugins.forEach((p, i) => {
        const plugin = Object.create(Plugin.prototype);
        Object.defineProperty(plugin, 'name',        { value: p.name });
        Object.defineProperty(plugin, 'filename',    { value: p.filename });
        Object.defineProperty(plugin, 'description', { value: p.description });
        Object.defineProperty(plugin, 'length',      { value: 0 });
        arr[i] = plugin;
      });
      Object.defineProperty(arr, 'length', { value: fakePlugins.length });
      return arr;
    },
    enumerable: true, configurable: true,
  });

  // Patch 3: navigator.languages -- headless returns []
  Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
    enumerable: true, configurable: true,
  });

  // Patch 4: screen dimensions -- headless returns 0x0 or env-reported values
  // Use realistic 1920x1080 unless already set to something plausible
  if (screen.width === 0 || screen.height === 0) {
    Object.defineProperty(screen, 'width',       { value: 1920 });
    Object.defineProperty(screen, 'height',      { value: 1080 });
    Object.defineProperty(screen, 'availWidth',  { value: 1920 });
    Object.defineProperty(screen, 'availHeight', { value: 1040 });
    Object.defineProperty(screen, 'colorDepth',  { value: 24 });
    Object.defineProperty(screen, 'pixelDepth',  { value: 24 });
  }
})();
"""

async def apply_stealth(tab) -> None:
    """Inject fingerprint stealth patches into every new document on this tab.

    Must be called BEFORE first navigation so the script is registered for
    all subsequent navigations. Requires cdp.page to be enabled first.
    """
    await tab.send(cdp.page.enable())
    await tab.send(cdp.page.add_script_to_evaluate_on_new_document(STEALTH_JS))
```

### Pattern 2: Proxy Launch Args

**What:** Pass `--proxy-server` and WebRTC flag via `browser_args` to `nodriver.start()`.
**When to use:** When `cfg.proxy.enabled` is True.

```python
# Source: nodriver 0.50.3 core/util.py start() + core/config.py Config.__call__()
# [VERIFIED: nodriver source read] browser_args is List[str] forwarded to Config._browser_args

import nodriver

async def _start_with_proxy(proxy_url: str, headless: bool) -> nodriver.Browser:
    """Launch browser with proxy server and WebRTC leak prevention.

    proxy_url is host:port ONLY (no credentials -- those are handled via CDP).
    """
    args = [
        f"--proxy-server={proxy_url}",
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    ]
    return await nodriver.start(headless=headless, browser_args=args)
```

### Pattern 3: Authenticated Proxy via CDP Fetch

**What:** Intercept Chrome's `Fetch.authRequired` event and supply credentials.
**When to use:** When proxy URL contains `user:pass@`.
**Critical:** Add handlers BEFORE calling `fetch.enable`. Use `asyncio.create_task` in handlers
to avoid deadlocking the event loop.

```python
# Source: nodriver cdp/fetch.py (source read) + github.com/ultrafunkamsterdam/undetected-chromedriver/discussions/1798
# [VERIFIED: nodriver source read for API; CITED: GitHub discussion for handler ordering]

from nodriver import cdp
from nodriver.cdp import fetch

async def _setup_proxy_auth(tab, username: str, password: str) -> None:
    """Register CDP Fetch handlers to respond to proxy auth challenges.

    Ordering is mandatory: add_handler BEFORE fetch.enable or events are missed.
    """

    async def _on_request_paused(event: fetch.RequestPaused) -> None:
        asyncio.create_task(
            tab.send(fetch.continue_request(request_id=event.request_id))
        )

    async def _on_auth_required(event: fetch.AuthRequired) -> None:
        asyncio.create_task(
            tab.send(fetch.continue_with_auth(
                request_id=event.request_id,
                auth_challenge_response=fetch.AuthChallengeResponse(
                    response="ProvideCredentials",
                    username=username,
                    password=password,
                ),
            ))
        )

    tab.add_handler(fetch.RequestPaused, _on_request_paused)
    tab.add_handler(fetch.AuthRequired, _on_auth_required)
    await tab.send(fetch.enable(handle_auth_requests=True))
```

### Pattern 4: ProxyPool Round-Robin with Retire/Cooldown

**What:** Stateful pool managing proxies, failure counts, and cooldown timestamps.
**When to use:** At startup (pool construction) and at each browser restart boundary.

```python
# Source: codebase pattern (following existing dataclass/model patterns); [ASSUMED] for class design
import time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class _ProxyEntry:
    url: str              # full URL including creds; never logged
    host_port: str        # host:port only (logged, no creds)
    username: str
    password: str
    failures: int = 0
    retired_until: float = 0.0  # epoch seconds; 0 = not retired

    def is_retired(self) -> bool:
        return time.monotonic() < self.retired_until

    def record_failure(self, max_failures: int, cooldown_secs: float) -> bool:
        """Increment failure count. Return True if proxy was just retired."""
        self.failures += 1
        if self.failures >= max_failures:
            self.retired_until = time.monotonic() + cooldown_secs
            self.failures = 0
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0


class ProxyPool:
    def __init__(self, entries: list[_ProxyEntry], max_failures: int = 3,
                 cooldown_secs: float = 300.0) -> None:
        self._entries = entries
        self._index = 0
        self._max_failures = max_failures
        self._cooldown = cooldown_secs

    def current(self) -> Optional[_ProxyEntry]:
        if not self._entries:
            return None
        return self._entries[self._index % len(self._entries)]

    def advance(self) -> Optional[_ProxyEntry]:
        """Move to next non-retired proxy (round-robin). Returns None if all retired."""
        if not self._entries:
            return None
        for _ in range(len(self._entries)):
            self._index = (self._index + 1) % len(self._entries)
            entry = self._entries[self._index]
            if not entry.is_retired():
                return entry
        return None  # all retired

    def record_failure(self, entry: _ProxyEntry) -> None:
        entry.record_failure(self._max_failures, self._cooldown)

    def record_success(self, entry: _ProxyEntry) -> None:
        entry.record_success()
```

### Pattern 5: Config Schema for proxy:

**What:** Pydantic model nested under `AppConfig`, disabled by default.
**When to use:** Any user who sets `proxy.enabled: true` in config.yml.

```python
# Source: core/config_schema.py conventions (source read); [ASSUMED] for field names
from pydantic import BaseModel, Field

class ProxyConfig(BaseModel):
    """Opt-in proxy rotation config. Disabled by default (ANTI-04).

    Credentials in url strings are never logged; only host:port is emitted.
    Store proxy URLs in config.yml (they are not secrets in the same sense
    as auth tokens, but user:pass@ entries should be treated carefully --
    see CLAUDE.md: never log plaintext credentials).
    """
    enabled: bool = False
    urls: list[str] = Field(default_factory=list)
    max_failures: int = 3       # retire after N consecutive failures (ANTI-05)
    cooldown_secs: float = 300.0  # seconds before retired proxy re-enters pool
```

Then add `proxy: ProxyConfig = ProxyConfig()` to `AppConfig`.

### Pattern 6: Ban-Signal Detection in Plugin

**What:** Detect ban responses and flag for rotation at next restart.
**When to use:** In `check_availability` exception/result path, not as a mid-session rotate.

```python
# [ASSUMED] pattern design following orchestrator/plugin conventions

_BAN_PHRASES = [
    "access denied", "blocked", "bot detected",
    "unusual traffic", "automated access", "verify you are human",
]
_BAN_STATUSES = {403, 429, 503}

def _is_ban_response(status_code: int, body_text: str) -> bool:
    if status_code in _BAN_STATUSES:
        return True
    lower = body_text.lower()
    return any(phrase in lower for phrase in _BAN_PHRASES)
```

Detection requires intercepting the HTTP response. In nodriver, the tab navigates and returns
the resulting page. Status codes are available via `cdp.network` response events OR by checking
the final URL (challenge redirect) and page text (block phrase). The most practical approach
given this codebase's existing pattern is:

1. After `tab.get(url)`, evaluate `document.body.innerText` via `tab.send(cdp.runtime.evaluate(...))`
   and check for block phrases.
2. Use `tab.add_handler(cdp.network.ResponseReceived, ...)` to intercept status codes.

Both approaches have trade-offs documented in Pitfalls.

### Anti-Patterns to Avoid
- **Rotating proxy mid-session:** nodriver binds the proxy at Chrome launch. Mid-session rotate
  requires `teardown()` + `setup()` — this is the restart boundary and is already the correct
  integration point.
- **Logging proxy URLs with credentials:** Never pass `entry.url` to `writeLog`. Log only
  `entry.host_port`. Same rule as `str(exc)` on credential-containing exceptions (STATE.md
  Research Flags, Phase 13 entry).
- **`asyncio.create_task` omission in Fetch handlers:** Awaiting `tab.send()` directly inside
  a `Fetch.RequestPaused` or `Fetch.AuthRequired` handler deadlocks the connection because the
  handler is called from within the receive loop. Always wrap in `asyncio.create_task()`.
- **Calling `apply_stealth()` after first navigation:** The CDP call registers the script for
  future navigations. Calling it after the first `tab.get()` means the first page was loaded
  without patches. Call it immediately after `nodriver.start()`.
- **Adding `cdp.page.enable()` call inside stealth unnecessarily:** nodriver may already have
  enabled page events internally; a second enable is harmless but redundant. However,
  `add_script_to_evaluate_on_new_document` requires the Page domain to be enabled, so the
  `cdp.page.enable()` call inside `apply_stealth()` is a safe guard.
- **Using `add_script_to_evaluate_on_load` (deprecated):** nodriver's cdp/page.py line 1957
  explicitly labels this as deprecated. Use `add_script_to_evaluate_on_new_document` only.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL parsing for `scheme://user:pass@host:port` | custom string split | `urllib.parse.urlparse()` | Handles edge cases (no creds, IPv6 hosts, non-standard ports, trailing slashes) |
| CDP command dispatch | raw websocket send | `tab.send(cdp.X.method(...))` | nodriver wraps the generator protocol correctly; raw send bypasses transaction tracking |
| Fetch domain event registration | manual `handlers` dict | `tab.add_handler(EventType, callback)` | nodriver's `Connection.add_handler` ensures correct dispatch; direct dict mutation bypasses the dedup check |

**Key insight:** The CDP generator pattern in nodriver (`tab.send(cdp.page.X(...))`) handles
the request/response correlation automatically. Raw websocket calls break this.

---

## Runtime State Inventory

Not applicable. This is a new-feature phase with no renames or data migrations.

---

## Common Pitfalls

### Pitfall 1: Chrome Rejects Inline Credentials in --proxy-server
**What goes wrong:** `--proxy-server=http://user:pass@host:port` is silently ignored by Chrome.
The browser launches without proxy auth and falls back to direct connection.
**Why it happens:** Chrome's command-line proxy configuration does not accept credentials in
the URL. This is documented Chrome behavior, not a nodriver limitation.
**How to avoid:** Pass `--proxy-server=host:port` (no creds) and use CDP `Fetch.enable` with
`handle_auth_requests=True` to intercept the 407 Proxy Authentication Required challenge.
**Warning signs:** Requests succeed without ever triggering `Fetch.AuthRequired` handler;
IP check shows real IP, not proxy IP.

### Pitfall 2: Silent Direct-Connection Fallback Must Be Blocked
**What goes wrong:** If the `ProxyPool` has no available proxies (all retired), the plugin
silently falls back to direct Chrome launch — leaking the real IP.
**Why it happens:** `nodriver.start()` with no `--proxy-server` arg connects directly.
**How to avoid:** When `proxy.enabled=True` and `pool.current()` returns `None` (all retired),
raise a clear exception or log `ERROR` and refuse to launch, rather than launching without proxy.
STATE.md Research Flags: "fail loudly, never silently fall back to direct connection (PITFALLS 1.1)".
**Warning signs:** Bot continues checking items when all proxies are retired.

### Pitfall 3: WebRTC Leak Despite --proxy-server
**What goes wrong:** Even with `--proxy-server`, WebRTC STUN negotiation sends UDP packets
directly, bypassing the HTTP proxy tunnel and revealing the real IP.
**Why it happens:** WebRTC uses its own UDP transport, independent of the HTTP proxy.
**How to avoid:** Always include `--force-webrtc-ip-handling-policy=disable_non_proxied_udp`
in `browser_args` when proxy is enabled. This Chrome flag forces WebRTC to use only the proxy
interface.
**Warning signs:** WebRTC IP leak test (e.g., browserleaks.com/webrtc) shows real IP.

### Pitfall 4: Fetch Handler Ordering
**What goes wrong:** Registering `tab.add_handler(...)` AFTER `tab.send(fetch.enable(...))` causes
the first auth challenge to arrive before the handler is registered and the request hangs
indefinitely (no response to the 407).
**Why it happens:** `fetch.enable` immediately arms Chrome to intercept requests; if the
handler is not yet registered, the first intercepted request has no responder.
**How to avoid:** Always call `tab.add_handler(fetch.RequestPaused, ...)` and
`tab.add_handler(fetch.AuthRequired, ...)` BEFORE `await tab.send(fetch.enable(...))`.
**Warning signs:** Browser hangs on first page load after proxy is configured.

### Pitfall 5: Deadlock in Fetch Handlers Without asyncio.create_task
**What goes wrong:** Awaiting `tab.send(...)` directly inside a `Fetch.RequestPaused` handler
causes the nodriver receive loop to deadlock (it is waiting for the handler to return, which
is waiting for a send that the receive loop must process).
**Why it happens:** The handler is called from within the connection's async receive loop.
Awaiting another `tab.send()` from that call-stack re-enters the loop.
**How to avoid:** Wrap all `tab.send()` calls inside Fetch event handlers with
`asyncio.create_task(tab.send(...))` — fire-and-forget, no await.
**Warning signs:** Browser hangs indefinitely on first navigation after `fetch.enable`.

### Pitfall 6: Per-Instance vs. Module-Level Proxy Singleton
**What goes wrong:** A module-level `ProxyPool` singleton shared by all plugins means plugin A
advancing the pool affects plugin B's proxy assignment.
**Why it happens:** Global state in async contexts causes non-deterministic ordering.
**How to avoid:** `ProxyPool` is constructed once (at bot startup from config) and plugins
each hold their own `self._proxy` reference pointing to their assigned `_ProxyEntry`. The pool
advances per-plugin at setup time; the pool itself is read-only during the session except for
failure/success recording.
STATE.md Research Flags: "Proxy selection must be per plugin instance (`self._proxy`), never a
module-level singleton (PITFALLS 1.6)".

### Pitfall 7: Naive Fingerprint Patch Detection
**What goes wrong:** Retailers detect that `navigator.plugins` was overridden via `Object.defineProperty`
because the property descriptor reveals `configurable: true` (which a native PluginArray does not
expose), or `toString()` on the override function returns `"function get plugins() { [native code] }"`
inconsistency.
**Why it happens:** JS engines expose the override mechanism via `Object.getOwnPropertyDescriptor`.
Advanced bot-detection (Akamai, PerimeterX) specifically tests for this.
**How to avoid:** This is an inherent limitation of the JS-injection approach. REQUIREMENTS.md
explicitly out-of-scopes "HUMAN / PerimeterX / Akamai 'CAPTCHA' solving" and "Canvas / WebGL /
AudioContext fingerprint spoofing." The four patches in scope (window.chrome, plugins, languages,
screen) address Layer 2 signals (Amazon/BestBuy WAF triggers) for personal-use volume. The
STATE.md note says "test against CreepJS before merging" — this is the validation gate for
catching naive detector trips.
**Warning signs:** CreepJS reports `lies` on `navigator.plugins` after injection.

### Pitfall 8: apply_stealth Called After First Navigation
**What goes wrong:** The first page loaded after `nodriver.start()` gets unpatched navigator
values; fingerprint detection may fire on that first request.
**Why it happens:** `addScriptToEvaluateOnNewDocument` only affects documents loaded AFTER
the call. The browser opens `about:blank` initially; if `apply_stealth` is called right after
`start()` before any `tab.get()`, then all navigations including the first real one are patched.
**How to avoid:** Call `apply_stealth(browser.main_tab)` immediately after `nodriver.start()`
returns, before any call to `tab.get(url)` or `self.driver.get(url)`.

### Pitfall 9: Log Safety on Proxy Exception Paths
**What goes wrong:** Logging `str(exc)` where `exc` may be a URL-related exception containing
the proxy credential string `user:pass@host`.
**Why it happens:** Python exceptions for connection errors often include the full URL.
**How to avoid:** Log only `exc.__class__.__name__` on all proxy-related exception paths.
STATE.md Research Flags: "Log only `exc.__class__.__name__` on proxy/CAPTCHA exception paths --
never `str(exc)` which may contain credential strings in URLs (PITFALLS 6.4)".

---

## Code Examples

### nodriver.start() with browser_args — Verified
```python
# Source: nodriver 0.50.3 core/util.py start() (source-read confirmed)
# browser_args is passed directly to Config._browser_args; appears in Config.browser_args property
self.driver = await nodriver.start(
    headless=headless,
    browser_args=[
        "--proxy-server=192.168.1.1:8080",
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    ]
)
```

### CDP Page.addScriptToEvaluateOnNewDocument — Verified
```python
# Source: nodriver 0.50.3 cdp/page.py lines 1980-2008 (source-read confirmed)
# Already used by nodriver internally in core/tab.py _prepare_expert (lines 252-263)
await tab.send(cdp.page.enable())
await tab.send(cdp.page.add_script_to_evaluate_on_new_document(JS_STRING))
# Returns a ScriptIdentifier (can be stored for later removal; not needed here)
```

### tab.add_handler — Verified
```python
# Source: nodriver 0.50.3 core/connection.py lines 168-171 (source-read confirmed)
# Connection.add_handler(event_type: type, callback: Callable) -> None
tab.add_handler(cdp.fetch.AuthRequired, my_async_handler)
```

### AuthChallengeResponse fields — Verified
```python
# Source: nodriver 0.50.3 cdp/fetch.py lines 144-176 (source-read confirmed)
# response: str, username: Optional[str], password: Optional[str]
from nodriver.cdp import fetch as cdp_fetch
response = cdp_fetch.AuthChallengeResponse(
    response="ProvideCredentials",
    username="myuser",
    password="mypass",
)
```

### urllib.parse for proxy URL decomposition — Verified
```python
# Source: Python stdlib urllib.parse (standard library, no import needed beyond stdlib)
from urllib.parse import urlparse

def _parse_proxy_url(url: str):
    """Return (host_port, username, password) from scheme://[user:pass@]host:port."""
    parsed = urlparse(url)
    host_port = f"{parsed.hostname}:{parsed.port}"
    return host_port, parsed.username or "", parsed.password or ""
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `--proxy-server=user:pass@host` inline creds | CDP `Fetch.enable` + `continueWithAuth` | Chrome ~80+ | Inline creds never worked reliably; CDP is the correct mechanism |
| `addScriptToEvaluateOnLoad` (deprecated) | `addScriptToEvaluateOnNewDocument` | CDP ~2018 | Deprecated API still works but emits warnings; new API is preferred |
| Chrome extension for proxy auth | CDP `Fetch.enable` handler | Chrome ~120 | Extension MV3 constraints made the extension approach brittle |

**Deprecated/outdated:**
- `Page.addScriptToEvaluateOnLoad`: deprecated per nodriver cdp/page.py line 1957. Never use.
- In-memory Chrome extension for proxy auth: fragile with MV3, CDPapproach preferred.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ProxyConfig` field names (`enabled`, `urls`, `max_failures`, `cooldown_secs`) | Standard Stack, Pattern 5 | Planner may choose different names; low risk — schema shape is Claude's discretion |
| A2 | Block-phrase list (`access denied`, `blocked`, `bot detected`, `unusual traffic`, `automated access`, `verify you are human`) | Pattern 6 | Incomplete list misses some ban pages; can be extended post-phase without API change |
| A3 | `core/stealth.py` stays under 300 lines; no need to split `ProxyPool` to separate module | Architecture Patterns | If Phase 17 test coverage pushes the file over 300 lines, split at that point |
| A4 | `asyncio.create_task` approach in Fetch handlers is safe in nodriver 0.50.3's event loop context | Pattern 3 | If nodriver uses a non-standard loop, fire-and-forget tasks could be orphaned; confirmed by community discussion but not verified in nodriver source |

---

## Open Questions

1. **Ban detection via network status vs. body scan**
   - What we know: nodriver does not expose response status codes natively on `tab.get()` return;
     status is available via `cdp.network.ResponseReceived` event or by reading the final URL.
   - What's unclear: Registering a `cdp.network.ResponseReceived` handler for every request
     (including sub-resources) may be noisy. A lighter approach: after navigation, evaluate
     `document.body.innerText` for block phrases, and separately check if the final URL contains
     challenge-redirect indicators.
   - Recommendation: Implement body-scan approach (simpler, no additional handler registration)
     for Phase 13. Network-level handler is more precise but more complex; defer to Phase 14
     or Phase 17 if needed.

2. **ProxyPool construction location**
   - What we know: ProxyPool must be shared across plugins (they all draw from the same pool)
     but `self._proxy` is per-plugin-instance.
   - What's unclear: Where is the ProxyPool constructed? BotService.__init__? Orchestrator
     async_main? Registry?
   - Recommendation: Construct `ProxyPool` in `BotService.__init__` (same place `init_store`
     is called) and pass it down to `PluginRegistry`, which sets `plugin._pool` on each plugin
     instance before `setup()` is called. This mirrors how `config` is already passed.

3. **proxy.urls storing plaintext credentials in config.yml**
   - What we know: `proxy.urls` will contain `scheme://user:pass@host:port` entries in
     `config.yml` (which is gitignored). The credentials are not high-security (proxy creds,
     not account creds), but the project convention is to route secrets through the credential
     store.
   - What's unclear: Should proxy URLs go in `credentials` backend (complex) or stay in
     `config.yml` (simple, gitignored)?
   - Recommendation: Keep in `config.yml` (gitignored, lower-risk category than account
     credentials). Add a config comment warning. This matches the locked decision in CONTEXT.md
     and avoids new credential-store complexity.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| nodriver | CDP injection, proxy launch | Yes | 0.50.3 (pinned) | N/A — existing dep |
| Python stdlib urllib.parse | proxy URL parsing | Yes | 3.13 | N/A — stdlib |
| Chrome / Chromium | browser runtime | Yes (discovered by nodriver) | managed by nodriver | N/A |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio 1.3.0 (asyncio_mode=auto) |
| Config file | `pyproject.toml` (asyncio_mode=auto: no decorators needed) |
| Quick run command | `pytest tests/test_stealth.py -x` |
| Full suite command | `pytest` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ANTI-08 | `apply_stealth(tab)` sends `cdp.page.enable` then `add_script_to_evaluate_on_new_document` | unit (mock tab.send) | `pytest tests/test_stealth.py::test_apply_stealth_sends_correct_cdp_calls -x` | No — Wave 0 |
| ANTI-08 | Stealth script contains all 4 patches (window.chrome, plugins, languages, screen) | unit (string inspect) | `pytest tests/test_stealth.py::test_stealth_js_contains_required_patches -x` | No — Wave 0 |
| ANTI-04 | `ProxyPool.current()` returns first proxy on fresh pool | unit | `pytest tests/test_stealth.py::test_proxypool_current_returns_first -x` | No — Wave 0 |
| ANTI-04 | `ProxyPool.advance()` cycles round-robin across all entries | unit | `pytest tests/test_stealth.py::test_proxypool_roundrobin -x` | No — Wave 0 |
| ANTI-05 | `ProxyPool.record_failure()` retires proxy after `max_failures` | unit | `pytest tests/test_stealth.py::test_proxypool_retires_after_max_failures -x` | No — Wave 0 |
| ANTI-05 | Retired proxy re-enters pool after cooldown | unit (monkeypatch time.monotonic) | `pytest tests/test_stealth.py::test_proxypool_cooldown_reentry -x` | No — Wave 0 |
| ANTI-05 | `ProxyPool.advance()` returns None when all proxies retired | unit | `pytest tests/test_stealth.py::test_proxypool_all_retired_returns_none -x` | No — Wave 0 |
| ANTI-04 | `ProxyConfig` parses `enabled`, `urls`, `max_failures`, `cooldown_secs` from YAML | unit (tmp config) | `pytest tests/test_stealth.py::test_proxyconfig_parses_from_yaml -x` | No — Wave 0 |
| ANTI-04 | `ProxyConfig` defaults: `enabled=False`, `urls=[]` | unit | `pytest tests/test_stealth.py::test_proxyconfig_defaults -x` | No — Wave 0 |
| ANTI-04 | Startup log line is exactly `Proxy rotation: enabled, pool_size=N` (no credentials) | unit (caplog) | `pytest tests/test_stealth.py::test_proxy_startup_log_no_credentials -x` | No — Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_stealth.py -x`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_stealth.py` — new file covering all 10 test cases above
- [ ] No framework changes needed (pytest-asyncio already configured)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Yes (proxy URL parsing) | `urllib.parse.urlparse()` — stdlib, no raw string split |
| V6 Cryptography | No | N/A |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Proxy credential in log | Information Disclosure | Log only `entry.host_port`; log `exc.__class__.__name__` not `str(exc)` |
| Proxy credential in exception traceback | Information Disclosure | Catch broad exceptions on proxy paths; re-raise sanitized error only |
| Silent direct-connection fallback | Spoofing / Info Disclosure | Fail loudly when pool exhausted and `proxy.enabled=True` |
| Proxy URL injection via config.yml | Tampering | `config.yml` is gitignored + local; no additional sanitization needed beyond what `urlparse` provides |

---

## Sources

### Primary (HIGH confidence)
- nodriver 0.50.3 source: `core/util.py` — `start()` signature with `browser_args: List[str]`
- nodriver 0.50.3 source: `core/tab.py` — `_prepare_expert()` confirms `cdp.page.add_script_to_evaluate_on_new_document` pattern at lines 252-263
- nodriver 0.50.3 source: `cdp/page.py` — `add_script_to_evaluate_on_new_document()` at lines 1980-2008
- nodriver 0.50.3 source: `cdp/fetch.py` — `enable()`, `continue_with_auth()`, `AuthChallengeResponse`, `AuthRequired` event
- nodriver 0.50.3 source: `core/connection.py` — `add_handler(event_type, callback)` at lines 168-171
- nodriver 0.50.3 source: `core/config.py` — `Config.__call__()` confirms `browser_args` appended to launch args
- `core/plugin_base.py` + `plugins/shopbot_plugin_amazon.py` — `setup()` pattern: `nodriver.start(headless=headless)` is the integration point
- `core/config_schema.py` — Pydantic nested model conventions, `Field(default_factory=list)`, `model_validator`, `extra="ignore"`
- `core/credentials.py` — `SECRET_KEYS` list, logging pattern `exc.__class__.__name__` only

### Secondary (MEDIUM confidence)
- [GitHub discussion: nodriver authenticated proxy via CDP Fetch](https://github.com/ultrafunkamsterdam/undetected-chromedriver/discussions/1798) — handler ordering and `asyncio.create_task` pattern confirmed
- WebSearch result on `--proxy-server` not accepting inline credentials — corroborated by Chrome documentation and multiple framework guides

### Tertiary (LOW confidence)
- Fingerprint JS patch values (specific plugin names, screen dimensions) — drawn from community research on headless detection evasion; treat as starting point, validate against CreepJS per STATE.md flag

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — nodriver 0.50.3 source read directly; no new deps
- Architecture: HIGH — integration points confirmed by reading actual plugin + orchestrator source
- nodriver API (CDP injection, Fetch auth): HIGH — confirmed in installed package source
- Proxy auth handler ordering: MEDIUM — confirmed via community discussion, consistent with CDP spec
- Fingerprint JS patch content: LOW — community-derived values; validate with CreepJS before merge

**Research date:** 2026-06-09
**Valid until:** 2026-09-09 (nodriver 0.50.3 is pinned; stable until version bump)
