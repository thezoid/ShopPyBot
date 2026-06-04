"""web/routes/pages.py: HTML page routes for the ShopPyBot dashboard."""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/")
async def dashboard(request: Request):
    """Render the dashboard page with initial data from BotService."""
    svc = request.app.state.svc
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "is_non_local": request.app.state.is_non_local,
        "status": svc.get_status(),
        "items": svc.list_items(),
    })
