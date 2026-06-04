"""handle_web: Phase 10 stub with lazy fastapi import seam (CLI-04).

Only `sys` is imported at module level. fastapi is NEVER imported at the top
of this file -- the lazy import inside the function body is the CLI-04 invariant.
"""

import sys


def handle_web(args, svc=None) -> int:
    """Start the web UI. Requires fastapi (pip install .[web]).

    Lazy-imports fastapi so the CLI works without it installed (CLI-04).
    Phase 10 will implement the web server in the body after the import.
    """
    try:
        import fastapi  # noqa: F401 -- lazy; never at module level
    except ImportError:
        print(
            "FastAPI is not installed. Run: pip install .[web]",
            file=sys.stderr,
        )
        return 1
    # Phase 10 will implement the web server here
    print("web UI not yet implemented (Phase 10)")
    return 0
