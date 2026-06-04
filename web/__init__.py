"""web/__init__.py: create_app factory for the ShopPyBot optional web UI.

All fastapi imports live only inside this package. core/cli/web.py imports
create_app lazily (inside the function body) so the CLI works without fastapi
installed (CLI-04 invariant).
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

_HERE = Path(__file__).parent


def create_app(svc, is_non_local: bool = False) -> FastAPI:
    """Build and return the ShopPyBot FastAPI application.

    Args:
        svc: A BotService instance (or compatible mock). Stored on app.state.svc.
        is_non_local: True when --host is not a loopback address. Sets
            app.state.is_non_local so the Jinja2 template renders the warning banner.

    Returns:
        Configured FastAPI application with StaticFiles mount and all routers.
    """
    app = FastAPI(title="ShopPyBot Dashboard", docs_url=None, redoc_url=None)
    app.state.svc = svc
    app.state.is_non_local = is_non_local

    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")

    from web.routes.api import router as api_router
    from web.routes.credentials import router as credentials_router
    from web.routes.config import router as config_router
    from web.routes.pages import router as pages_router

    app.include_router(api_router, prefix="/api")
    app.include_router(credentials_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(pages_router)

    return app
