"""Browser fingerprint stealth and proxy rotation utilities (ANTI-08, ANTI-04, ANTI-05).

Provides:
  - STEALTH_JS: IIFE that patches 4 headless-detection signals per browser launch
  - apply_stealth(tab): injects STEALTH_JS via CDP before first navigation
  - _parse_proxy_url: splits scheme://user:pass@host:port into (host_port, user, pass)
  - _is_ban_response: detects HTTP ban signals by status code or response body phrase
  - _ProxyEntry / ProxyPool: round-robin rotation with retire/cooldown state machine
  - build_proxy_browser_args: Chrome launch args (proxy + WebRTC leak prevention)
  - setup_proxy_auth: CDP Fetch handler registration for authenticated proxies

Security: credentials are never logged. Log only entry.host_port, never entry.url.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from nodriver import cdp
from nodriver.cdp import fetch


# ---------------------------------------------------------------------------
# STEALTH_JS — 4-patch IIFE (ANTI-08, Pitfall 8: call before first navigation)
# ---------------------------------------------------------------------------

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

    MUST be called before first navigation so the script is registered for all
    subsequent navigations. Requires cdp.page to be enabled first (Pitfall 8).
    """
    await tab.send(cdp.page.enable())
    await tab.send(cdp.page.add_script_to_evaluate_on_new_document(STEALTH_JS))


# ---------------------------------------------------------------------------
# Ban-signal detection (ANTI-05)
# ---------------------------------------------------------------------------

_BAN_STATUSES = {403, 429, 503}
_BAN_PHRASES = [
    "access denied",
    "blocked",
    "bot detected",
    "unusual traffic",
    "automated access",
    "verify you are human",
]


def _is_ban_response(status_code: int, body_text: str) -> bool:
    """Return True if the HTTP response indicates a ban or challenge page."""
    if status_code in _BAN_STATUSES:
        return True
    lower = body_text.lower()
    return any(phrase in lower for phrase in _BAN_PHRASES)


# ---------------------------------------------------------------------------
# Proxy URL parsing (T-13-03: stdlib only, no custom split)
# ---------------------------------------------------------------------------


def _parse_proxy_url(url: str) -> tuple:
    """Split scheme://[user:pass@]host:port into (host_port, username, password).

    host_port never includes credentials (T-13-01 mitigation).
    Returns empty strings for missing username/password, not None.
    """
    parsed = urlparse(url)
    host_port = f"{parsed.hostname}:{parsed.port}"
    return host_port, parsed.username or "", parsed.password or ""


# ---------------------------------------------------------------------------
# ProxyPool + _ProxyEntry (ANTI-04, ANTI-05)
# ---------------------------------------------------------------------------


@dataclass
class _ProxyEntry:
    """Single proxy slot with failure tracking and cooldown state."""

    url: str               # full URL including creds; NEVER log this field
    host_port: str         # host:port only; safe to log
    username: str
    password: str
    failures: int = field(default=0)
    retired_until: float = field(default=0.0)  # monotonic timestamp; 0 = active

    def is_retired(self) -> bool:
        """Return True if the cooldown period has not yet elapsed."""
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
        """Reset failure count on a successful request."""
        self.failures = 0


class ProxyPool:
    """Round-robin proxy pool with per-proxy retire/cooldown (ANTI-04, ANTI-05).

    Each plugin instance holds a reference to its current _ProxyEntry via
    self._proxy. The pool is shared; entries advance at browser restart.
    """

    def __init__(
        self,
        entries: list,
        max_failures: int = 3,
        cooldown_secs: float = 300.0,
    ) -> None:
        self._entries = entries
        self._index = 0
        self._max_failures = max_failures
        self._cooldown = cooldown_secs

    @classmethod
    def from_urls(
        cls,
        urls: list,
        max_failures: int = 3,
        cooldown_secs: float = 300.0,
    ) -> "ProxyPool":
        """Build a ProxyPool from a list of proxy URL strings."""
        entries = []
        for url in urls:
            host_port, username, password = _parse_proxy_url(url)
            entries.append(_ProxyEntry(
                url=url,
                host_port=host_port,
                username=username,
                password=password,
            ))
        return cls(entries, max_failures=max_failures, cooldown_secs=cooldown_secs)

    def size(self) -> int:
        """Return total number of entries (including retired ones)."""
        return len(self._entries)

    def __len__(self) -> int:
        return self.size()

    def current(self) -> Optional[_ProxyEntry]:
        """Return the proxy at the current index without advancing."""
        if not self._entries:
            return None
        return self._entries[self._index % len(self._entries)]

    def advance(self) -> Optional[_ProxyEntry]:
        """Move to the next non-retired proxy (round-robin).

        Returns None if every proxy is retired — caller must fail loudly
        (Pitfall 2: never silently fall back to direct connection).
        """
        if not self._entries:
            return None
        for _ in range(len(self._entries)):
            self._index = (self._index + 1) % len(self._entries)
            entry = self._entries[self._index]
            if not entry.is_retired():
                return entry
        return None  # all retired

    def record_failure(self, entry: _ProxyEntry) -> bool:
        """Record a failure on the given entry. Returns True if just retired."""
        return entry.record_failure(self._max_failures, self._cooldown)

    def record_success(self, entry: _ProxyEntry) -> None:
        """Record a successful request for the given entry."""
        entry.record_success()


# ---------------------------------------------------------------------------
# Browser launch helpers (ANTI-04 SC4: WebRTC leak prevention)
# ---------------------------------------------------------------------------


def build_proxy_browser_args(entry: Optional[_ProxyEntry]) -> list:
    """Return Chrome launch args for proxy + WebRTC leak prevention.

    Passes host:port only -- credentials are NEVER included in launch args
    (T-13-01 mitigation; Chrome ignores inline creds anyway per Pitfall 1).
    Returns [] when entry is None (proxy disabled).
    """
    if entry is None:
        return []
    return [
        f"--proxy-server={entry.host_port}",
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    ]


# ---------------------------------------------------------------------------
# Authenticated proxy via CDP Fetch (Pitfalls 4+5: ordering + create_task)
# ---------------------------------------------------------------------------


async def setup_proxy_auth(tab, username: str, password: str) -> None:
    """Register CDP Fetch handlers to respond to proxy 407 auth challenges.

    No-op when username is empty (unauthenticated proxy or proxy disabled).
    Handlers are registered BEFORE fetch.enable to avoid missing the first
    auth challenge (Pitfall 4). All tab.send calls are wrapped in
    asyncio.create_task to prevent receive-loop deadlock (Pitfall 5).
    Credentials are passed to AuthChallengeResponse only, never logged.
    """
    if not username:
        return

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
