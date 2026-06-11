"""Tests for handle_setup_checkout_profile (Phase 20 -- BUY-07).

Covers:
    - stores 9 keys (all non-empty inputs -> 9 store.set calls)
    - name-only output (stdout contains key names, never input values)
    - CHECKOUT_ADDRESS_LINE2 optional (empty -> not stored)
    - no card/CVV key stored
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.checkout_profile import CHECKOUT_PROFILE_KEYS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sentinel(key: str) -> str:
    """Distinct input value per key; unlikely to collide with any key name."""
    return f"input__{key}__val"


def _make_args():
    return SimpleNamespace(checkout_profile=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_setup_checkout_profile_stores_keys(reset_credential_store, monkeypatch):
    """Feeding 9 non-empty inputs results in 9 store.set calls and returns 0."""
    import core.credentials as creds_mod
    from core.credentials import EnvVarBackend

    store = EnvVarBackend()
    monkeypatch.setattr(creds_mod, "_store", store)

    # Remove any pre-existing env values so each key starts absent.
    for key in CHECKOUT_PROFILE_KEYS:
        monkeypatch.delenv(key, raising=False)

    inputs = iter(_sentinel(k) for k in CHECKOUT_PROFILE_KEYS)

    def _fake_readline():
        return next(inputs, "") + "\n"

    monkeypatch.setattr("core.cli.setup.sys.stdin", type("_FakeStdin", (), {"readline": staticmethod(_fake_readline)})())

    from core.cli.setup import handle_setup_checkout_profile

    result = handle_setup_checkout_profile(_make_args(), MagicMock())

    assert result == 0
    for key in CHECKOUT_PROFILE_KEYS:
        assert store.get(key) == _sentinel(key), f"key {key!r} not stored"


def test_setup_output_is_key_name_only(reset_credential_store, monkeypatch, capsys):
    """stdout contains each key NAME; no entered value appears in stdout."""
    import core.credentials as creds_mod
    from core.credentials import EnvVarBackend

    store = EnvVarBackend()
    monkeypatch.setattr(creds_mod, "_store", store)

    for key in CHECKOUT_PROFILE_KEYS:
        monkeypatch.delenv(key, raising=False)

    inputs = iter(_sentinel(k) for k in CHECKOUT_PROFILE_KEYS)

    def _fake_readline():
        return next(inputs, "") + "\n"

    monkeypatch.setattr("core.cli.setup.sys.stdin", type("_FakeStdin", (), {"readline": staticmethod(_fake_readline)})())

    from core.cli.setup import handle_setup_checkout_profile

    handle_setup_checkout_profile(_make_args(), MagicMock())

    out = capsys.readouterr().out
    for key in CHECKOUT_PROFILE_KEYS:
        assert key in out, f"key name {key!r} missing from output"
    # No input value may appear in stdout (T-20-03)
    for key in CHECKOUT_PROFILE_KEYS:
        assert _sentinel(key) not in out, f"input value for {key!r} leaked into stdout"


def test_setup_address_line2_optional(reset_credential_store, monkeypatch):
    """Empty input for CHECKOUT_ADDRESS_LINE2 skips store.set; the other 8 are stored."""
    import core.credentials as creds_mod
    from core.credentials import EnvVarBackend

    store = EnvVarBackend()
    monkeypatch.setattr(creds_mod, "_store", store)

    for key in CHECKOUT_PROFILE_KEYS:
        monkeypatch.delenv(key, raising=False)

    # Yield empty string for CHECKOUT_ADDRESS_LINE2, non-empty for the rest.
    def _values():
        for key in CHECKOUT_PROFILE_KEYS:
            if key == "CHECKOUT_ADDRESS_LINE2":
                yield ""
            else:
                yield _sentinel(key)

    inputs = iter(_values())

    def _fake_readline():
        return next(inputs, "") + "\n"

    monkeypatch.setattr("core.cli.setup.sys.stdin", type("_FakeStdin", (), {"readline": staticmethod(_fake_readline)})())

    from core.cli.setup import handle_setup_checkout_profile

    result = handle_setup_checkout_profile(_make_args(), MagicMock())

    assert result == 0
    assert store.get("CHECKOUT_ADDRESS_LINE2") is None, "optional key must not be stored when empty"
    for key in CHECKOUT_PROFILE_KEYS:
        if key != "CHECKOUT_ADDRESS_LINE2":
            assert store.get(key) == _sentinel(key), f"required key {key!r} not stored"


def test_setup_stores_no_card_or_cvv(reset_credential_store, monkeypatch):
    """After a full run no stored key contains CVV, CARD, or PAN substrings."""
    import core.credentials as creds_mod
    from core.credentials import EnvVarBackend

    store = EnvVarBackend()
    monkeypatch.setattr(creds_mod, "_store", store)

    for key in CHECKOUT_PROFILE_KEYS:
        monkeypatch.delenv(key, raising=False)

    inputs = iter(_sentinel(k) for k in CHECKOUT_PROFILE_KEYS)

    def _fake_readline():
        return next(inputs, "") + "\n"

    monkeypatch.setattr("core.cli.setup.sys.stdin", type("_FakeStdin", (), {"readline": staticmethod(_fake_readline)})())

    from core.cli.setup import handle_setup_checkout_profile

    handle_setup_checkout_profile(_make_args(), MagicMock())

    forbidden = ("CVV", "CARD", "PAN")
    # Assert no key in CHECKOUT_PROFILE_KEYS contains a forbidden fragment.
    # (The prior or-shortcircuit form was tautological -- IN-01.)
    for key in CHECKOUT_PROFILE_KEYS:
        for fragment in forbidden:
            assert fragment not in key.upper(), (
                f"CHECKOUT_PROFILE_KEYS contains key {key!r} with forbidden fragment {fragment!r}"
            )
