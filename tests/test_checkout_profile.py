"""Tests for core/checkout_profile.py -- Phase 20 BUY-07 model layer.

Covers:
    test_profile_keys_roundtrip         -- all 9 keys set; first_name mapped correctly
    test_incomplete_profile_returns_none -- missing required key -> None return
    test_address_line2_optional         -- 8 required keys set; address_line2 is None
    test_checkout_keys_not_in_secret_keys -- disjointness + len(SECRET_KEYS)==20
"""

import pytest
from core.checkout_profile import (
    CHECKOUT_PROFILE_KEYS,
    load_checkout_profile,
)
from core.credentials import SECRET_KEYS


# ---------------------------------------------------------------------------
# Helpers: clear checkout keys from os.environ before each test so prior
# EnvVarBackend.set() calls cannot bleed across tests.
# ---------------------------------------------------------------------------

def _clear_checkout_keys(monkeypatch):
    for key in CHECKOUT_PROFILE_KEYS:
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_profile_keys_roundtrip(monkeypatch):
    """Round-trip: all 9 keys set -> non-None profile with correct field mapping."""
    from core.credentials import EnvVarBackend
    import core.credentials as creds_mod

    _clear_checkout_keys(monkeypatch)

    store = EnvVarBackend()
    monkeypatch.setattr(creds_mod, "_store", store)

    for key in CHECKOUT_PROFILE_KEYS:
        store.set(key, f"val_{key}")

    profile = load_checkout_profile()

    assert profile is not None
    assert profile.first_name == "val_CHECKOUT_FIRST_NAME"
    assert profile.last_name == "val_CHECKOUT_LAST_NAME"
    assert profile.address_line1 == "val_CHECKOUT_ADDRESS_LINE1"
    assert profile.address_line2 == "val_CHECKOUT_ADDRESS_LINE2"
    assert profile.city == "val_CHECKOUT_CITY"
    assert profile.state == "val_CHECKOUT_STATE"
    assert profile.zip_code == "val_CHECKOUT_ZIP"
    assert profile.country == "val_CHECKOUT_COUNTRY"
    assert profile.phone == "val_CHECKOUT_PHONE"


def test_incomplete_profile_returns_none(monkeypatch):
    """Missing a required key (CHECKOUT_CITY) causes load to return None."""
    from core.credentials import EnvVarBackend
    import core.credentials as creds_mod

    _clear_checkout_keys(monkeypatch)

    store = EnvVarBackend()
    monkeypatch.setattr(creds_mod, "_store", store)

    for key in CHECKOUT_PROFILE_KEYS:
        if key != "CHECKOUT_CITY":
            store.set(key, f"val_{key}")

    # Ensure CHECKOUT_CITY is absent from environment (not just store)
    monkeypatch.delenv("CHECKOUT_CITY", raising=False)

    profile = load_checkout_profile()

    assert profile is None


def test_address_line2_optional(monkeypatch):
    """CHECKOUT_ADDRESS_LINE2 absent -> non-None profile with address_line2=None."""
    from core.credentials import EnvVarBackend
    import core.credentials as creds_mod

    _clear_checkout_keys(monkeypatch)

    store = EnvVarBackend()
    monkeypatch.setattr(creds_mod, "_store", store)

    for key in CHECKOUT_PROFILE_KEYS:
        if key != "CHECKOUT_ADDRESS_LINE2":
            store.set(key, f"val_{key}")

    monkeypatch.delenv("CHECKOUT_ADDRESS_LINE2", raising=False)

    profile = load_checkout_profile()

    assert profile is not None
    assert profile.address_line2 is None


def test_checkout_keys_not_in_secret_keys():
    """CHECKOUT_PROFILE_KEYS is disjoint from SECRET_KEYS; SECRET_KEYS has 20 entries."""
    assert len(SECRET_KEYS) == 20, (
        f"SECRET_KEYS length changed from expected 20: {len(SECRET_KEYS)}"
    )
    overlap = set(CHECKOUT_PROFILE_KEYS) & set(SECRET_KEYS)
    assert not overlap, (
        f"CHECKOUT_PROFILE_KEYS entries found in SECRET_KEYS (isolation violated): {overlap}"
    )
