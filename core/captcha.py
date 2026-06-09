"""2captcha v1 client for automated CAPTCHA solving (ANTI-06, ANTI-07).

Hand-rolled against the 2captcha in.php/res.php HTTP API using the already-pinned
requests==2.33.1. The blocking solve sequence (submit + poll) is designed to be
called via loop.run_in_executor() -- do NOT call solve_recaptcha from an async
context directly (Pitfall 2 in RESEARCH.md).

Security invariant: self._api_key is NEVER logged or embedded in str(exc).
"""
from __future__ import annotations

import json
import logging
import time

import requests

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 2captcha v1 endpoint constants
# ---------------------------------------------------------------------------
_SUBMIT_URL = "https://2captcha.com/in.php"
_RESULT_URL = "https://2captcha.com/res.php"

# Polling cadence per 2captcha documentation (Pattern 2 in RESEARCH.md)
_INITIAL_WAIT_SECS: int = 15
_POLL_INTERVAL_SECS: int = 5
_MAX_POLLS: int = 20  # 15 + 20*5 = 115s max; fits inside asyncio.timeout(120)


# ---------------------------------------------------------------------------
# Module-level private HTTP helpers (no logging of api_key; Pitfall 6)
# ---------------------------------------------------------------------------

def _submit_recaptcha(api_key: str, sitekey: str, pageurl: str) -> str:
    """POST reCAPTCHA v2 submit request. Returns captcha_id string."""
    resp = requests.post(
        _SUBMIT_URL,
        data={
            "key": api_key,
            "method": "userrecaptcha",
            "googlekey": sitekey,
            "pageurl": pageurl,
            "json": 1,
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != 1:
        raise RuntimeError(f"2captcha submit error: {body.get('request')}")
    return str(body["request"])


def _poll_result(api_key: str, captcha_id: str) -> str:
    """Block until solved token arrives. Returns token string."""
    time.sleep(_INITIAL_WAIT_SECS)
    for _ in range(_MAX_POLLS):
        resp = requests.get(
            _RESULT_URL,
            params={"key": api_key, "action": "get", "id": captcha_id, "json": 1},
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.json()
        status = body.get("status")
        result = str(body.get("request", ""))
        if status == 1:
            return result
        if result != "CAPTCHA_NOT_READY":   # two T's; matches 2captcha API response
            raise RuntimeError(f"2captcha poll error: {result}")
        time.sleep(_POLL_INTERVAL_SECS)
    raise TimeoutError("2captcha: exceeded max polls")


def _check_balance(api_key: str) -> float:
    """GET balance from 2captcha. Returns float or raises on ERROR_ response."""
    resp = requests.get(
        _RESULT_URL,
        params={"key": api_key, "action": "getbalance"},
        timeout=10,
    )
    resp.raise_for_status()
    text = resp.text.strip()
    if text == "ERROR_ZERO_BALANCE":
        return 0.0
    if text.startswith("ERROR_"):
        raise RuntimeError(f"2captcha balance check error: {text}")
    return float(text)


# ---------------------------------------------------------------------------
# CaptchaSolver
# ---------------------------------------------------------------------------


class CaptchaSolver:
    """Blocking 2captcha v1 client with per-run solve cap and balance gating.

    Construct via from_config(); call check_balance_at_startup() once; then
    guard each solve attempt with can_solve() before calling solve_recaptcha().

    MUST be called from a thread (run_in_executor); never on the async event loop.
    """

    def __init__(self, api_key: str, max_solves: int, low_threshold: float) -> None:
        self._api_key = api_key        # NEVER log this value
        self._max_solves = max_solves
        self._low_threshold = low_threshold
        self._solve_count: int = 0
        self.balance_ok: bool = True

    @classmethod
    def from_config(cls, cfg, store) -> "CaptchaSolver | None":
        """Return a CaptchaSolver if captcha is enabled and key is set, else None."""
        if not getattr(cfg, "enabled", False):
            return None
        api_key = store.get("TWOCAPTCHA_API_KEY")
        if not api_key:
            _log.warning(
                "TWOCAPTCHA_API_KEY not set in credential store -- captcha solving disabled"
            )
            return None
        return cls(api_key, cfg.max_solves_per_run, cfg.low_balance_threshold)

    def check_balance_at_startup(self) -> None:
        """Check 2captcha balance once at startup. Sets balance_ok; logs warnings."""
        try:
            balance = _check_balance(self._api_key)
        except Exception as exc:
            _log.warning(
                "2captcha balance check failed: %s -- captcha disabled",
                exc.__class__.__name__,
            )
            self.balance_ok = False
            return

        if balance <= 0.0:
            _log.warning("2captcha balance is zero -- captcha solving disabled for this run")
            self.balance_ok = False
            return

        if balance < self._low_threshold:
            _log.warning(
                "2captcha balance $%.2f is below threshold $%.2f",
                balance,
                self._low_threshold,
            )

    def can_solve(self) -> bool:
        """Return True when balance is OK and solve cap has not been reached."""
        return self.balance_ok and self._solve_count < self._max_solves

    def solve_recaptcha(self, sitekey: str, pageurl: str) -> str:
        """Submit + poll for a reCAPTCHA v2 token. Blocking -- use run_in_executor.

        Increments _solve_count before the network calls so the cap is respected
        even if the call raises.
        """
        self._solve_count += 1
        try:
            captcha_id = _submit_recaptcha(self._api_key, sitekey, pageurl)
            return _poll_result(self._api_key, captcha_id)
        except Exception as exc:
            _log.warning("solve_recaptcha failed: %s", exc.__class__.__name__)
            raise

    def solve_amazon_waf(
        self, key: str, iv: str, context: str, pageurl: str
    ) -> dict:
        """Submit AmazonTask + poll. Returns {captcha_voucher, existing_token}.

        NOTE: Amazon WAF auto-injection is deferred (CONTEXT.md); this method
        is the future API contract. Call only behind a manual-pause fallback.
        """
        if not self.can_solve():
            raise RuntimeError("solve_amazon_waf called when can_solve() is False")
        self._solve_count += 1
        resp = requests.post(
            _SUBMIT_URL,
            data={
                "key": self._api_key,
                "method": "AmazonTask",
                "websiteKey": key,
                "iv": iv,
                "context": context,
                "pageurl": pageurl,
                "json": 1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != 1:
            raise RuntimeError(f"2captcha AmazonTask submit error: {body.get('request')}")
        captcha_id = str(body["request"])
        token_str = _poll_result(self._api_key, captcha_id)
        # 2captcha returns JSON string for AmazonTask; decode defensively
        try:
            return json.loads(token_str)
        except Exception:
            return {"captcha_voucher": token_str, "existing_token": ""}
