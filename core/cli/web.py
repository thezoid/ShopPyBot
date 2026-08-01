"""handle_web: FastAPI web UI launcher with lazy import seam (CLI-04).

Only `sys` and `socket` are imported at module level. fastapi is NEVER imported
at the top of this file -- the lazy import inside the function body is the
CLI-04 invariant.
"""

import socket
import sys

PORT_SCAN_ATTEMPTS = 20
_WILDCARD_HOSTS = ("0.0.0.0", "::", "")


def _is_port_free(host: str, port: int) -> bool:
    """True if (host, port) can be bound right now.

    Deliberately does NOT set SO_REUSEADDR: the probe must fail for a port that
    is genuinely in use, and on Windows SO_REUSEADDR would let it succeed anyway.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def find_open_port(host: str, start_port: int, attempts: int = PORT_SCAN_ATTEMPTS) -> int | None:
    """First free port at or above start_port, or None if the scan is exhausted."""
    for port in range(start_port, start_port + attempts):
        if port > 65535:
            return None
        if _is_port_free(host, port):
            return port
    return None


def browse_host(host: str) -> str:
    """Host to put in a browsable URL. Wildcard binds are not addressable."""
    return "127.0.0.1" if host in _WILDCARD_HOSTS else host


def handle_web(args, svc=None) -> int:
    """Start the web UI dashboard. Requires fastapi (pip install .[web]).

    Lazy-imports web.create_app so the CLI works without fastapi installed (CLI-04).
    Non-localhost --host prints a security warning to stderr before serving.
    """
    try:
        from web import create_app          # lazy -- only inside function body
    except ImportError:
        print(
            "Web UI is not installed. Run: pip install .[web]",
            file=sys.stderr,
        )
        return 1

    import uvicorn
    from core.service import BotService
    from web.security import is_localhost

    host = getattr(args, "host", "127.0.0.1")
    requested_port = getattr(args, "port", 8000)
    is_non_local = not is_localhost(host)

    if is_non_local:
        print(
            "WARNING: ShopPyBot dashboard is binding to a non-local interface. "
            "Credential management is exposed on a non-local interface. "
            "Use only on a trusted private network.",
            file=sys.stderr,
        )

    port = find_open_port(host, requested_port)
    if port is None:
        last = requested_port + PORT_SCAN_ATTEMPTS - 1
        print(
            f"No free port found on {host} in range {requested_port}-{last}. "
            "Free a port or pass a different --port.",
            file=sys.stderr,
        )
        return 1

    if port != requested_port:
        print(
            f"Port {requested_port} is already in use on {host}; "
            f"serving on {port} instead.",
            file=sys.stderr,
        )

    url = f"http://{browse_host(host)}:{port}/"
    # flush: uvicorn.run blocks immediately after this, and a piped/redirected
    # stdout would otherwise hold the URL in the buffer until process exit.
    print(f"ShopPyBot dashboard: {url}", flush=True)

    if getattr(args, "open_browser", False):
        _open_when_up(url)

    resolved_svc = svc if svc is not None else BotService()
    app = create_app(resolved_svc, is_non_local=is_non_local)
    uvicorn.run(app, host=host, port=port)
    return 0


def _open_when_up(url: str, delay: float = 1.0) -> None:
    """Open the dashboard in the default browser once uvicorn has had time to bind.

    uvicorn.run blocks, so the open is deferred onto a daemon timer rather than
    fired inline against a socket that is not listening yet.
    """
    import threading
    import webbrowser

    timer = threading.Timer(delay, webbrowser.open, args=(url,))
    timer.daemon = True
    timer.start()
