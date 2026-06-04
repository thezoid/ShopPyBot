"""web/routes/credentials.py: credential management routes (GUI-03 / SC3).

GET  /credentials -- returns each SECRET_KEY as {name, is_set} only; never a value.
POST /credentials -- stores via CredentialStore.set; returns status only.

The secret value MUST NEVER appear in any response body, HTML, or log (SC3 / T-10-08).
POST is origin-checked to mitigate local-malware CSRF (T-10-10).
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

import core.credentials as _creds
from web.security import check_origin

router = APIRouter()


@router.get("/credentials")
async def get_credentials(request: Request) -> JSONResponse:
    """Return each known secret key with its name and set status only."""
    store = _creds.get_store()
    credentials = [
        {"name": k, "is_set": store.get(k) is not None}
        for k in _creds.SECRET_KEYS
    ]
    return JSONResponse({"credentials": credentials})


@router.post("/credentials", dependencies=[Depends(check_origin)])
async def set_credential(request: Request) -> JSONResponse:
    """Store a credential value via CredentialStore.set; return status only.

    The submitted value NEVER appears in any response branch (SC3).
    Unknown keys return 422 with no echo of the value (T-10-11).
    """
    body = await request.json()
    key = body.get("key")
    if key not in _creds.SECRET_KEYS:
        return JSONResponse(
            {"status": "error", "detail": "unknown key"},
            status_code=422,
        )
    _creds.get_store().set(key, body["value"])
    return JSONResponse({"status": "ok"})
