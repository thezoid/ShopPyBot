"""web/routes/api.py: JSON API routes for the ShopPyBot dashboard.

All state-changing routes (POST/DELETE) carry the check_origin CSRF dependency.
BotService is accessed only via request.app.state.svc (MOD-02).
Credential routes live in web/routes/credentials.py (SECRET_KEYS gate).
"""

import asyncio
import base64

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from web.security import check_origin
from web.log_reader import read_recent_logs
from models import get_confirmed_orders_sync, get_price_history_sync

router = APIRouter()


# ---------------------------------------------------------------------------
# Status + logs
# ---------------------------------------------------------------------------

@router.get("/status")
async def get_status(request: Request):
    """Return bot running state."""
    svc = request.app.state.svc
    return JSONResponse(svc.get_status())


@router.get("/logs")
async def get_logs(request: Request):
    """Return the last 50 lines of today's log file."""
    return JSONResponse({"logs": read_recent_logs(50)})


# ---------------------------------------------------------------------------
# Bot controls
# ---------------------------------------------------------------------------

@router.post("/bot/start", dependencies=[Depends(check_origin)])
async def bot_start(request: Request):
    """Start the bot. Offloads blocking start() off the event loop (WR-03)."""
    svc = request.app.state.svc
    if svc.get_status().get("running"):
        return JSONResponse({"status": "error", "detail": "Bot is already running."})
    await asyncio.to_thread(svc.start)
    return JSONResponse({"status": "ok"})


@router.post("/bot/stop", dependencies=[Depends(check_origin)])
async def bot_stop(request: Request):
    """Stop the bot. Offloads blocking stop() off the event loop (WR-01)."""
    svc = request.app.state.svc
    if not svc.get_status().get("running"):
        return JSONResponse({"status": "error", "detail": "Bot is not running."})
    await asyncio.to_thread(svc.stop)
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@router.get("/items")
async def list_items(request: Request):
    """Return all tracked items as a list of dicts."""
    rows = request.app.state.svc.list_items()
    items = [
        {
            "name": r[0],
            "link": r[1],
            "auto_buy": bool(r[2]),
            "quantity": r[3],
            "purchased": bool(r[4]),
        }
        for r in rows
    ]
    return JSONResponse({"items": items})


@router.post("/items", dependencies=[Depends(check_origin)])
async def add_item(request: Request):
    """Add a tracked item via BotService. Validates required fields (WR-02)."""
    body = await request.json()
    name = (body.get("name") or "").strip()
    link = (body.get("link") or "").strip()
    if not name or not link:
        return JSONResponse(
            {"status": "error", "detail": "name and link required"},
            status_code=422,
        )
    try:
        quantity = int(body.get("quantity", 1))
    except (TypeError, ValueError):
        return JSONResponse(
            {"status": "error", "detail": "quantity must be an integer"},
            status_code=422,
        )
    if quantity < 1:
        return JSONResponse(
            {"status": "error", "detail": "quantity must be >= 1"},
            status_code=422,
        )
    auto_buy = bool(body.get("auto_buy", False))
    request.app.state.svc.add_item(name, link, auto_buy, quantity)
    return JSONResponse({"status": "ok"})


@router.delete("/items/{link_b64}", dependencies=[Depends(check_origin)])
async def remove_item(link_b64: str, request: Request):
    """Remove a tracked item by base64-encoded URL."""
    try:
        link = base64.urlsafe_b64decode(link_b64.encode()).decode()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid link encoding")
    request.app.state.svc.remove_item(link)
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Observability (OBS-08 / SSE-03)
# ---------------------------------------------------------------------------

@router.get("/history")
async def get_history(request: Request):
    """Return confirmed orders. Read is async-safe via asyncio.to_thread (SSE-03)."""
    rows = await asyncio.to_thread(get_confirmed_orders_sync)
    orders = [
        {
            "name": r[0],
            "order_id": r[1],
            "confirmed_at": r[2],
            "checkout_attempts": r[3],
        }
        for r in rows
    ]
    return JSONResponse({"confirmed_orders": orders})


@router.get("/price-history/{link_b64}")
async def get_price_history(link_b64: str, request: Request):
    """Return price series (oldest-first) for a URL encoded as URL-safe base64.

    Returns {"series": []} on bad encoding or no data — never raises 400.
    Read is async-safe via asyncio.to_thread (SSE-03).
    """
    try:
        link = base64.urlsafe_b64decode(link_b64.encode()).decode()
    except Exception:
        return JSONResponse({"series": []})
    rows = await asyncio.to_thread(get_price_history_sync, link, 200)
    rows = list(reversed(rows))  # SQL returns newest-first; chart needs oldest-first
    series = [{"t": r[2], "price": r[0] / 100} for r in rows]
    return JSONResponse({"series": series})
