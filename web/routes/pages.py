"""web/routes/pages.py: HTML page routes for the ShopPyBot dashboard."""

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from web.security import check_origin

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/")
async def dashboard(request: Request):
    """Render the dashboard page with initial data from BotService.

    list_plugins() constructs a PluginRegistry (filesystem scan + importlib
    per plugin file), so it is offloaded via asyncio.to_thread to avoid
    blocking the event loop -- consistent with the /logs|/history|/analytics
    to_thread convention (SSE-03).
    """
    svc = request.app.state.svc
    plugins = await asyncio.to_thread(svc.list_plugins)
    return templates.TemplateResponse(request, "dashboard.html", {
        "is_non_local": request.app.state.is_non_local,
        "status": svc.get_status(),
        "items": svc.list_items(),
        "plugins": plugins,
    })


@router.post("/items/remove", dependencies=[Depends(check_origin)])
async def remove_item_form(request: Request):
    """Zero-JS SSR remove action (AF-01): HTML forms cannot issue DELETE,
    so this POST mirrors DELETE /api/items/{link_b64}'s effect via the
    same BotService.remove_item() call, then redirects back to '/'.
    """
    form = await request.form()
    raw_link = form.get("link")
    link = raw_link.strip() if isinstance(raw_link, str) else ""
    if link:
        request.app.state.svc.remove_item(link)
    return RedirectResponse(url="/", status_code=303)
