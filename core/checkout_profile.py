"""Checkout profile model and loader (Phase 20 -- BUY-07).

Exposes:
    CHECKOUT_PROFILE_KEYS  -- 9 canonical address key names stored in CredentialStore
    CheckoutProfile        -- pydantic model for validated address data
    load_checkout_profile  -- reads store and returns model or None on incomplete profile

CHECKOUT_PROFILE_KEYS lives here only and must NEVER be merged into SECRET_KEYS in
core/credentials.py. migrate_from_env and KeyringBackend.list both iterate SECRET_KEYS
only; widening SECRET_KEYS would silently change those behaviours (Pitfall 5 / T-20-02).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


CHECKOUT_PROFILE_KEYS: list[str] = [
    "CHECKOUT_FIRST_NAME",
    "CHECKOUT_LAST_NAME",
    "CHECKOUT_ADDRESS_LINE1",
    "CHECKOUT_ADDRESS_LINE2",   # optional: the only key that may be absent without None-return
    "CHECKOUT_CITY",
    "CHECKOUT_STATE",
    "CHECKOUT_ZIP",
    "CHECKOUT_COUNTRY",
    "CHECKOUT_PHONE",
]

# All keys except CHECKOUT_ADDRESS_LINE2 are required; a missing required key causes
# load_checkout_profile() to return None and log key NAMES only (T-20-01).
_REQUIRED_CHECKOUT_KEYS: list[str] = [
    k for k in CHECKOUT_PROFILE_KEYS if k != "CHECKOUT_ADDRESS_LINE2"
]


class CheckoutProfile(BaseModel):
    """Shipping / billing address loaded from the CredentialStore.

    address_line2 is the only optional field; all others must be non-empty for a
    valid profile.
    """

    first_name: str
    last_name: str
    address_line1: str
    address_line2: Optional[str] = None   # only optional field
    city: str
    state: str
    zip_code: str
    country: str
    phone: str


def load_checkout_profile() -> CheckoutProfile | None:
    """Read address keys from the CredentialStore and return a CheckoutProfile.

    Returns None and emits a WARNING (key NAMES only, never values) if any of the
    8 required keys are absent or empty. CHECKOUT_ADDRESS_LINE2 is optional; its
    absence does not cause a None return.

    Deferred imports avoid circular-import issues with core.credentials (mirrors
    the lazy-import discipline used elsewhere in the codebase).
    """
    from core.credentials import get_store
    from logger import writeLog

    store = get_store()
    values: dict[str, str | None] = {k: store.get(k) for k in CHECKOUT_PROFILE_KEYS}

    missing = [k for k in _REQUIRED_CHECKOUT_KEYS if not values.get(k)]
    if missing:
        # Log key NAMES only -- never any value (T-20-01)
        writeLog(
            f"CheckoutProfile incomplete -- missing keys: {missing}",
            "WARNING",
        )
        return None

    return CheckoutProfile(
        first_name=values["CHECKOUT_FIRST_NAME"],       # type: ignore[arg-type]
        last_name=values["CHECKOUT_LAST_NAME"],          # type: ignore[arg-type]
        address_line1=values["CHECKOUT_ADDRESS_LINE1"],  # type: ignore[arg-type]
        address_line2=values.get("CHECKOUT_ADDRESS_LINE2"),
        city=values["CHECKOUT_CITY"],                    # type: ignore[arg-type]
        state=values["CHECKOUT_STATE"],                  # type: ignore[arg-type]
        zip_code=values["CHECKOUT_ZIP"],                 # type: ignore[arg-type]
        country=values["CHECKOUT_COUNTRY"],              # type: ignore[arg-type]
        phone=values["CHECKOUT_PHONE"],                  # type: ignore[arg-type]
    )
