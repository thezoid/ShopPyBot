"""web/routes/api.py: JSON API routes for the ShopPyBot dashboard.

All state-changing routes (POST/DELETE) carry the check_origin CSRF dependency.
Route bodies are implemented in Plans 02-05; this file defines the router and
the complete route skeleton so include_router succeeds and CSRF tests pass.
"""

import base64

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from web.security import check_origin
from web.log_reader import read_recent_logs

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
    """Start the bot (no CVV -- web scope)."""
    request.app.state.svc.start()
    return JSONResponse({"status": "ok"})


@router.post("/bot/stop", dependencies=[Depends(check_origin)])
async def bot_stop(request: Request):
    """Stop the bot."""
    request.app.state.svc.stop()
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@router.get("/items")
async def list_items(request: Request):
    """Return all tracked items as a list of dicts."""
    rows = request.app.state.svc.list_items()
    items = [
        {"name": r[0], "link": r[1], "auto_buy": r[2], "quantity": r[3], "purchased": r[4]}
        for r in rows
    ]
    return JSONResponse({"items": items})


@router.post("/items", dependencies=[Depends(check_origin)])
async def add_item(request: Request):
    """Add a tracked item via BotService."""
    body = await request.json()
    request.app.state.svc.add_item(
        body["name"], body["link"], body["auto_buy"], body["quantity"]
    )
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
# Credentials (Plans 04/05 will fill these bodies)
# ---------------------------------------------------------------------------

@router.get("/credentials")
async def get_credentials(request: Request):
    """Return credential key names + set/unset status. Never returns values."""
    from core.credentials import get_store, SECRET_KEYS
    store = get_store()
    creds = [
        {"name": k, "is_set": store.get(k) is not None}
        for k in SECRET_KEYS
    ]
    return JSONResponse({"credentials": creds})


@router.post("/credentials", dependencies=[Depends(check_origin)])
async def set_credential(request: Request):
    """Store a credential value. Response never contains the value (SC3)."""
    from core.credentials import get_store
    body = await request.json()
    get_store().set(body["key"], body["value"])
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Config (Plan 05 will fill these bodies)
# ---------------------------------------------------------------------------

@router.get("/config")
async def get_config(request: Request):
    """Return allowlisted config values."""
    from web.config_web import read_web_config
    return JSONResponse(read_web_config(request.app.state.svc))


@router.post("/config", dependencies=[Depends(check_origin)])
async def set_config(request: Request):
    """Write an allowlisted config key atomically."""
    from web.config_web import WEB_ALLOWLIST, write_web_config
    body = await request.json()
    key = body.get("key", "")
    value = body.get("value", "")
    if key not in WEB_ALLOWLIST:
        raise HTTPException(status_code=422, detail=f"Key not in allowlist: {key!r}")
    write_web_config(key, str(value))
    return JSONResponse({"status": "ok"})
