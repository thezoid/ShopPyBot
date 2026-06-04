"""web/security.py: localhost detection and CSRF origin check for the web UI."""

import ipaddress
from urllib.parse import urlparse

from fastapi import HTTPException, Request

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def is_localhost(host: str) -> bool:
    """Return True if host resolves to a loopback address.

    Handles: bare hostname, IPv4:port, [::1], [::1]:port, bare IPv6.
    """
    h = host
    if h.startswith("["):
        # Bracketed IPv6: [::1] or [::1]:port
        h = h[1:].split("]")[0]
    elif ":" in h:
        # Could be IPv6 (no brackets) or IPv4:port
        try:
            ipaddress.ip_address(h)  # pure IPv6 -- don't strip the colon
        except ValueError:
            h = h.rsplit(":", 1)[0]  # strip port from IPv4:port
    if h in _LOCAL_HOSTS:
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


def check_origin(request: Request) -> None:
    """FastAPI Depends: rejects cross-origin state-changing requests (CSRF).

    Allows: no Origin header (same-origin form/fetch), or Origin hostname
    equals the server host. When the server is bound to a loopback address,
    all loopback literals are also accepted (127.0.0.1/localhost/::1 are
    interchangeable for localhost binds). For a non-local bind, only the
    exact server host is accepted -- the loopback escape hatch is NOT granted
    (CR-03).
    Rejects: any other Origin with 403.
    """
    origin = request.headers.get("origin")
    if origin is None:
        return
    hostname = urlparse(origin).hostname or ""
    server_host = request.url.hostname or "127.0.0.1"
    allowed = {server_host}
    if is_localhost(server_host):
        allowed |= _LOCAL_HOSTS
    if hostname not in allowed:
        raise HTTPException(status_code=403, detail="CSRF: origin rejected")
