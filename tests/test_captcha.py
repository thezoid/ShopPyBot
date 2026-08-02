"""Unit tests for CaptchaSolver (ANTI-06, ANTI-07). HTTP calls are mocked."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call

from core.config_schema import CaptchaConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(key_value: str | None = "test-api-key-123"):
    """Return a mock CredentialStore that returns key_value for any .get()."""
    store = MagicMock()
    store.get.return_value = key_value
    return store


def _enabled_cfg(**kwargs) -> CaptchaConfig:
    return CaptchaConfig(enabled=True, **kwargs)


# ---------------------------------------------------------------------------
# from_config: disabled / missing key
# ---------------------------------------------------------------------------

def test_solver_disabled():
    """from_config returns None when cfg.enabled is False."""
    from core.captcha import CaptchaSolver
    cfg = CaptchaConfig(enabled=False)
    result = CaptchaSolver.from_config(cfg, _make_store())
    assert result is None


def test_solver_no_key(caplog):
    """from_config returns None and logs WARNING when API key is missing."""
    import logging
    from core.captcha import CaptchaSolver
    cfg = _enabled_cfg()
    store = _make_store(None)
    with caplog.at_level(logging.WARNING):
        result = CaptchaSolver.from_config(cfg, store)
    assert result is None
    assert any("TWOCAPTCHA_API_KEY" in r.message for r in caplog.records)


def test_solver_created_when_enabled():
    """from_config returns a CaptchaSolver when enabled and key present."""
    from core.captcha import CaptchaSolver
    cfg = _enabled_cfg()
    result = CaptchaSolver.from_config(cfg, _make_store("my-key"))
    assert isinstance(result, CaptchaSolver)


# ---------------------------------------------------------------------------
# solve_recaptcha: success path
# ---------------------------------------------------------------------------

def test_solve_recaptcha_success():
    """solve_recaptcha returns token and increments solve_count."""
    from core.captcha import CaptchaSolver

    submit_resp = MagicMock()
    submit_resp.json.return_value = {"status": 1, "request": "captcha-id-99"}

    not_ready_resp = MagicMock()
    not_ready_resp.json.return_value = {"status": 0, "request": "CAPTCHA_NOT_READY"}

    ready_resp = MagicMock()
    ready_resp.json.return_value = {"status": 1, "request": "solved-token-abc"}

    solver = CaptchaSolver("key", max_solves=10, low_threshold=1.0)

    with patch("core.captcha.requests") as mock_req:
        mock_req.post.return_value = submit_resp
        mock_req.get.side_effect = [not_ready_resp, ready_resp]
        with patch("core.captcha.time") as mock_time:
            mock_time.sleep = MagicMock()
            token = solver.solve_recaptcha("site-key", "https://example.com")

    assert token == "solved-token-abc"
    assert solver._solve_count == 1


def test_solve_recaptcha_submit_error():
    """solve_recaptcha raises RuntimeError when submit returns status != 1."""
    from core.captcha import CaptchaSolver

    error_resp = MagicMock()
    error_resp.json.return_value = {"status": 0, "request": "ERROR_WRONG_USER_KEY"}

    solver = CaptchaSolver("key", max_solves=10, low_threshold=1.0)

    with patch("core.captcha.requests") as mock_req:
        mock_req.post.return_value = error_resp
        with patch("core.captcha.time"):
            with pytest.raises(RuntimeError):
                solver.solve_recaptcha("site-key", "https://example.com")


# ---------------------------------------------------------------------------
# can_solve: cap and balance gate
# ---------------------------------------------------------------------------

def test_cap_enforced():
    """can_solve returns False once solve_count reaches max_solves_per_run."""
    from core.captcha import CaptchaSolver
    solver = CaptchaSolver("key", max_solves=3, low_threshold=1.0)
    solver._solve_count = 3
    assert solver.can_solve() is False


def test_can_solve_true_when_under_cap():
    """can_solve returns True when balance_ok and under cap."""
    from core.captcha import CaptchaSolver
    solver = CaptchaSolver("key", max_solves=3, low_threshold=1.0)
    solver._solve_count = 2
    assert solver.can_solve() is True


def test_can_solve_false_when_balance_not_ok():
    """can_solve returns False when balance_ok is False regardless of count."""
    from core.captcha import CaptchaSolver
    solver = CaptchaSolver("key", max_solves=10, low_threshold=1.0)
    solver.balance_ok = False
    assert solver.can_solve() is False


# ---------------------------------------------------------------------------
# check_balance_at_startup
# ---------------------------------------------------------------------------

def test_zero_balance_disables_solver():
    """check_balance_at_startup sets balance_ok=False when balance is 0.0."""
    from core.captcha import CaptchaSolver

    resp = MagicMock()
    resp.text = "0.0"

    solver = CaptchaSolver("key", max_solves=10, low_threshold=1.0)
    with patch("core.captcha.requests") as mock_req:
        mock_req.get.return_value = resp
        solver.check_balance_at_startup()

    assert solver.balance_ok is False


def test_low_balance_warning(caplog):
    """check_balance_at_startup logs WARNING when balance < low_threshold."""
    import logging
    from core.captcha import CaptchaSolver

    resp = MagicMock()
    resp.text = "0.50"

    solver = CaptchaSolver("key", max_solves=10, low_threshold=1.0)
    with patch("core.captcha.requests") as mock_req:
        mock_req.get.return_value = resp
        with caplog.at_level(logging.WARNING):
            solver.check_balance_at_startup()

    assert solver.balance_ok is True
    assert any("balance" in r.message.lower() for r in caplog.records)


def test_balance_error_zero(caplog):
    """ERROR_ZERO_BALANCE response is treated as zero balance."""
    import logging
    from core.captcha import CaptchaSolver

    resp = MagicMock()
    resp.text = "ERROR_ZERO_BALANCE"

    solver = CaptchaSolver("key", max_solves=10, low_threshold=1.0)
    with patch("core.captcha.requests") as mock_req:
        mock_req.get.return_value = resp
        with caplog.at_level(logging.WARNING):
            solver.check_balance_at_startup()

    assert solver.balance_ok is False


# ---------------------------------------------------------------------------
# Security: API key never logged
# ---------------------------------------------------------------------------

def test_key_not_logged(caplog):
    """API key value must never appear in any captured log record."""
    import logging
    from core.captcha import CaptchaSolver

    api_key = "super-secret-key-value-12345"

    # Trigger from_config log path with missing key, then check balance
    cfg = _enabled_cfg()
    store_none = _make_store(None)
    with caplog.at_level(logging.DEBUG):
        CaptchaSolver.from_config(cfg, store_none)

    # Trigger balance log paths
    solver = CaptchaSolver(api_key, max_solves=10, low_threshold=1.0)
    resp_low = MagicMock()
    resp_low.text = "0.50"
    with patch("core.captcha.requests") as mock_req:
        mock_req.get.return_value = resp_low
        with caplog.at_level(logging.DEBUG):
            solver.check_balance_at_startup()

    for record in caplog.records:
        assert api_key not in record.message, (
            f"API key leaked in log: {record.message!r}"
        )


def test_exception_logs_class_name_only(caplog):
    """On requests exception, only exc.__class__.__name__ is logged, never str(exc)."""
    import logging
    import requests as req_lib
    from core.captcha import CaptchaSolver

    api_key = "secret-key-abcdefgh"
    solver = CaptchaSolver(api_key, max_solves=10, low_threshold=1.0)

    # ConnectionError str() might contain the URL with the embedded key
    bad_exc = req_lib.exceptions.ConnectionError(
        f"Connection failed for key={api_key}"
    )

    resp_raise = MagicMock()
    resp_raise.text = "0.50"

    with patch("core.captcha.requests") as mock_req:
        mock_req.get.side_effect = bad_exc
        with caplog.at_level(logging.WARNING):
            solver.check_balance_at_startup()

    # Key must not appear in any log record
    for record in caplog.records:
        assert api_key not in record.message, (
            f"API key leaked via str(exc) in log: {record.message!r}"
        )
    # Class name must appear
    assert any("ConnectionError" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# CR-01 regression: CAPTCHA_NOT_READY (correct spelling) continues polling
# ---------------------------------------------------------------------------

def test_captcha_not_ready_continues_polling():
    """CAPTCHA_NOT_READY response is treated as keep-polling; eventual OK returns token."""
    from core.captcha import CaptchaSolver

    submit_resp = MagicMock()
    submit_resp.json.return_value = {"status": 1, "request": "captcha-id-cr01"}

    not_ready_resp = MagicMock()
    not_ready_resp.json.return_value = {"status": 0, "request": "CAPTCHA_NOT_READY"}

    ready_resp = MagicMock()
    ready_resp.json.return_value = {"status": 1, "request": "token-cr01-success"}

    solver = CaptchaSolver("key", max_solves=10, low_threshold=1.0)

    with patch("core.captcha.requests") as mock_req:
        mock_req.post.return_value = submit_resp
        # First two polls return not-ready; third returns token
        mock_req.get.side_effect = [not_ready_resp, not_ready_resp, ready_resp]
        with patch("core.captcha.time") as mock_time:
            mock_time.sleep = MagicMock()
            token = solver.solve_recaptcha("site-key", "https://example.com")

    assert token == "token-cr01-success"
    assert solver._solve_count == 1


def test_captcha_not_ready_no_runtime_error():
    """CAPTCHA_NOT_READY must never raise RuntimeError (regression for CR-01 typo)."""
    from core.captcha import CaptchaSolver

    submit_resp = MagicMock()
    submit_resp.json.return_value = {"status": 1, "request": "captcha-id-guard"}

    not_ready_resp = MagicMock()
    not_ready_resp.json.return_value = {"status": 0, "request": "CAPTCHA_NOT_READY"}

    ready_resp = MagicMock()
    ready_resp.json.return_value = {"status": 1, "request": "token-guard-ok"}

    solver = CaptchaSolver("key", max_solves=10, low_threshold=1.0)

    with patch("core.captcha.requests") as mock_req:
        mock_req.post.return_value = submit_resp
        mock_req.get.side_effect = [not_ready_resp, ready_resp]
        with patch("core.captcha.time") as mock_time:
            mock_time.sleep = MagicMock()
            # Must not raise -- if CR-01 typo were present this would RuntimeError
            token = solver.solve_recaptcha("site-key", "https://example.com")

    assert token == "token-guard-ok"


# ---------------------------------------------------------------------------
# CP-01: solve_recaptcha poll-error (non-CAPTCHA_NOT_READY) raises RuntimeError
# ---------------------------------------------------------------------------

def test_solve_recaptcha_poll_error_raises_runtimeerror():
    """CP-01: poll response with status!=1 and non-NOT_READY request raises RuntimeError.

    The _solve_count must still be 1 — the increment happens before network calls
    so the cap is honoured even when the call raises (captcha.py:72 + increment invariant).
    """
    from core.captcha import CaptchaSolver

    submit_resp = MagicMock()
    submit_resp.json.return_value = {"status": 1, "request": "cid-cp01"}

    error_poll_resp = MagicMock()
    error_poll_resp.json.return_value = {"status": 0, "request": "ERROR_CAPTCHA_UNSOLVABLE"}

    solver = CaptchaSolver("test-api-key-cp01", max_solves=10, low_threshold=1.0)

    with patch("core.captcha.requests") as mock_req:
        mock_req.post.return_value = submit_resp
        mock_req.get.return_value = error_poll_resp
        with patch("core.captcha.time") as mock_time:
            mock_time.sleep = MagicMock()
            with pytest.raises(RuntimeError):
                solver.solve_recaptcha("site-key", "https://example.com")

    assert solver._solve_count == 1


# ---------------------------------------------------------------------------
# CP-02: solve_recaptcha exceeds _MAX_POLLS raises TimeoutError
# ---------------------------------------------------------------------------

def test_solve_recaptcha_exceeds_max_polls_raises_timeout():
    """CP-02: every poll returning CAPTCHA_NOT_READY eventually raises TimeoutError.

    The GET mock must be called exactly _MAX_POLLS times (captcha.py:74).
    time.sleep is patched to a no-op so the test is instant.
    """
    import core.captcha
    from core.captcha import CaptchaSolver

    submit_resp = MagicMock()
    submit_resp.json.return_value = {"status": 1, "request": "cid-cp02"}

    not_ready_resp = MagicMock()
    not_ready_resp.json.return_value = {"status": 0, "request": "CAPTCHA_NOT_READY"}

    solver = CaptchaSolver("test-api-key-cp02", max_solves=10, low_threshold=1.0)

    with patch("core.captcha.requests") as mock_req:
        mock_req.post.return_value = submit_resp
        mock_req.get.return_value = not_ready_resp
        with patch("core.captcha.time") as mock_time:
            mock_time.sleep = MagicMock()
            with pytest.raises(TimeoutError):
                solver.solve_recaptcha("site-key", "https://example.com")

    assert mock_req.get.call_count == core.captcha._MAX_POLLS


# ---------------------------------------------------------------------------
# CP-03: generic ERROR_ balance response disables solver; api key never logged
# ---------------------------------------------------------------------------

def test_balance_check_error_response_disables_solver(caplog):
    """CP-03: a generic ERROR_ text from getbalance raises inside _check_balance (captcha.py:89).

    check_balance_at_startup catches it, sets balance_ok=False, and logs only
    exc.__class__.__name__ -- the sentinel api key must never appear in any log record.
    """
    import logging
    from core.captcha import CaptchaSolver

    sentinel_key = "sentinel-api-key-cp03-xyzzy"  #gitleaks:allow
    solver = CaptchaSolver(sentinel_key, max_solves=10, low_threshold=1.0)

    error_resp = MagicMock()
    error_resp.text = "ERROR_KEY_DOES_NOT_EXIST"

    with patch("core.captcha.requests") as mock_req:
        mock_req.get.return_value = error_resp
        with caplog.at_level(logging.WARNING):
            solver.check_balance_at_startup()

    assert solver.balance_ok is False
    for record in caplog.records:
        assert sentinel_key not in record.message, (
            f"API key leaked in log record: {record.message!r}"
        )


# ---------------------------------------------------------------------------
# WR-02 regression: solve_amazon_waf respects can_solve() guard
# ---------------------------------------------------------------------------

def test_solve_amazon_waf_blocked_when_cannot_solve():
    """solve_amazon_waf raises RuntimeError when can_solve() is False (WR-02)."""
    from core.captcha import CaptchaSolver
    solver = CaptchaSolver("key", max_solves=1, low_threshold=1.0)
    solver._solve_count = 1  # cap reached
    with pytest.raises(RuntimeError, match="can_solve"):
        solver.solve_amazon_waf("k", "iv", "ctx", "https://example.com")


def test_solve_amazon_waf_blocked_when_balance_not_ok():
    """solve_amazon_waf raises RuntimeError when balance_ok is False (WR-02)."""
    from core.captcha import CaptchaSolver
    solver = CaptchaSolver("key", max_solves=10, low_threshold=1.0)
    solver.balance_ok = False
    with pytest.raises(RuntimeError, match="can_solve"):
        solver.solve_amazon_waf("k", "iv", "ctx", "https://example.com")


# ---------------------------------------------------------------------------
# CP-04: solve_amazon_waf happy path returns decoded dict
# ---------------------------------------------------------------------------

def test_solve_amazon_waf_success_returns_decoded_dict():
    """CP-04: AmazonTask POST succeeds, poll returns JSON-string token, result decoded.

    Covers captcha.py:179 (_solve_count increment), 180-198 (submit + poll),
    201 (json.loads). _solve_count must increment by exactly 1.
    """
    import json as _json
    from core.captcha import CaptchaSolver

    submit_resp = MagicMock()
    submit_resp.json.return_value = {"status": 1, "request": "cid-cp04"}

    token_dict = {"captcha_voucher": "v", "existing_token": "e"}
    poll_resp = MagicMock()
    poll_resp.json.return_value = {"status": 1, "request": _json.dumps(token_dict)}

    solver = CaptchaSolver("test-api-key-cp04", max_solves=10, low_threshold=1.0)

    with patch("core.captcha.requests") as mock_req:
        mock_req.post.return_value = submit_resp
        mock_req.get.return_value = poll_resp
        with patch("core.captcha.time") as mock_time:
            mock_time.sleep = MagicMock()
            result = solver.solve_amazon_waf("k", "iv", "ctx", "https://example.com")

    assert result == {"captcha_voucher": "v", "existing_token": "e"}
    assert solver._solve_count == 1


# ---------------------------------------------------------------------------
# CP-05: solve_amazon_waf non-JSON fallback and submit-error raise
# ---------------------------------------------------------------------------

def test_solve_amazon_waf_non_json_token_falls_back_and_submit_error_raises():
    """CP-05a/b: non-JSON poll token falls back to dict; submit status!=1 raises RuntimeError.

    CP-05a covers captcha.py:202-203 (non-JSON fallback).
    CP-05b covers captcha.py:195-196 (AmazonTask submit error raise).
    """
    from core.captcha import CaptchaSolver

    # --- CP-05a: non-JSON token fallback ---
    submit_resp = MagicMock()
    submit_resp.json.return_value = {"status": 1, "request": "cid-cp05a"}

    plain_poll_resp = MagicMock()
    plain_poll_resp.json.return_value = {"status": 1, "request": "plain-voucher-string"}

    solver_a = CaptchaSolver("test-api-key-cp05a", max_solves=10, low_threshold=1.0)

    with patch("core.captcha.requests") as mock_req:
        mock_req.post.return_value = submit_resp
        mock_req.get.return_value = plain_poll_resp
        with patch("core.captcha.time") as mock_time:
            mock_time.sleep = MagicMock()
            result_a = solver_a.solve_amazon_waf("k", "iv", "ctx", "https://example.com")

    assert result_a == {"captcha_voucher": "plain-voucher-string", "existing_token": ""}

    # --- CP-05b: AmazonTask submit status!=1 raises RuntimeError ---
    error_submit_resp = MagicMock()
    error_submit_resp.json.return_value = {"status": 0, "request": "ERROR_WRONG_USER_KEY"}

    solver_b = CaptchaSolver("test-api-key-cp05b", max_solves=10, low_threshold=1.0)

    with patch("core.captcha.requests") as mock_req:
        mock_req.post.return_value = error_submit_resp
        with patch("core.captcha.time"):
            with pytest.raises(RuntimeError):
                solver_b.solve_amazon_waf("k", "iv", "ctx", "https://example.com")
