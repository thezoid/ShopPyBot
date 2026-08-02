"""web/__init__.py: create_app factory for the ShopPyBot optional web UI.

All fastapi imports live only inside this package. core/cli/web.py imports
create_app lazily (inside the function body) so the CLI works without fastapi
installed (CLI-04 invariant).
"""

from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from web.sse_hub import SseHub, _poll_loop

_HERE = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start _poll_loop on uvicorn's event loop at startup,
    cancel and await it cleanly on shutdown.

    SseHub() is created synchronously in create_app (factory body) so
    app.state.sse_hub always exists before lifespan runs (Pitfall 3).
    asyncio.create_task() runs here where the event loop is guaranteed live
    (Pitfall 2 — never call create_task in the factory body).
    """
    task = asyncio.create_task(
        _poll_loop(app.state.sse_hub, app.state.svc)
    )
    app.state.sse_poll_task = task
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app(svc, is_non_local: bool = False) -> FastAPI:
    """Build and return the ShopPyBot FastAPI application.

    Args:
        svc: A BotService instance (or compatible mock). Stored on app.state.svc.
        is_non_local: True when --host is not a loopback address. Sets
            app.state.is_non_local so the Jinja2 template renders the warning banner.

    Returns:
        Configured FastAPI application with StaticFiles mount and all routers.
    """
    app = FastAPI(title="ShopPyBot Dashboard", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.svc = svc
    app.state.is_non_local = is_non_local
    app.state.sse_hub = SseHub()

    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")

    from web.routes.api import router as api_router
    from web.routes.credentials import router as credentials_router
    from web.routes.config import router as config_router
    from web.routes.pages import router as pages_router
    from web.routes.sse import router as sse_router

    app.include_router(api_router, prefix="/api")
    app.include_router(credentials_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(pages_router)
    app.include_router(sse_router, prefix="/api")

    return app
