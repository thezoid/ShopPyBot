"""handle_web: FastAPI web UI launcher with lazy import seam (CLI-04).

Only `sys` is imported at module level. fastapi is NEVER imported at the top
of this file -- the lazy import inside the function body is the CLI-04 invariant.
"""

import sys


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
    port = getattr(args, "port", 8000)
    is_non_local = not is_localhost(host)

    if is_non_local:
        print(
            "WARNING: ShopPyBot dashboard is binding to a non-local interface. "
            "Credential management is exposed on a non-local interface. "
            "Use only on a trusted private network.",
            file=sys.stderr,
        )

    resolved_svc = svc if svc is not None else BotService()
    app = create_app(resolved_svc, is_non_local=is_non_local)
    uvicorn.run(app, host=host, port=port)
    return 0
