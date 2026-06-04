"""web/routes/config.py: config read/write API routes.

GET  /config  -- returns allowlisted current config values.
POST /config  -- writes a single allowlisted key; unknown key -> 422.

Config scope: test_mode, logging_level, and the four notifier enable toggles
(notifications.sound, notifications.discord.enabled, notifications.email.enabled,
notifications.sms.enabled).  Platforms have no 'enabled' field in AppConfig so
no platform enable checkboxes are rendered (config-scope note from UI-SPEC).
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from web.config_web import WEB_ALLOWLIST, read_web_config, write_web_config
from web.security import check_origin

router = APIRouter()


@router.get("/config")
async def get_config(request: Request) -> JSONResponse:
    """Return the current values for all WEB_ALLOWLIST keys."""
    return JSONResponse(read_web_config(request.app.state.svc))


@router.post("/config", dependencies=[Depends(check_origin)])
async def set_config(request: Request) -> JSONResponse:
    """Write a single allowlisted config key atomically.

    Returns 422 if the key is not in WEB_ALLOWLIST (T-10-12).
    Never writes for unknown keys.
    """
    body = await request.json()
    key = body.get("key", "")
    if key not in WEB_ALLOWLIST:
        return JSONResponse(
            {"status": "error", "detail": "unknown key"},
            status_code=422,
        )
    write_web_config(key, str(body.get("value", "")))
    return JSONResponse({"status": "ok"})
