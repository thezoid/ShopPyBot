"""test_api_observability.py: RED scaffold for Phase 26 read-only API endpoints.

Wave 1: every test here is expected to FAIL (RED) because the implementation
(get_confirmed_orders_sync, /api/history, /api/price-history, read_logs_filtered,
record_last_error, last_error) does not exist yet. Tests fail on 404 / assertion /
AttributeError -- NOT on collection / import errors.
"""
import base64
import json
import re

import pytest
pytest.importorskip("fastapi")

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


CRED_PATTERN = re.compile(r'(@|password|token|key=|cvv)', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Fixtures (verbatim from tests/test_web_dashboard.py lines 10-21, extended)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False, "uptime_secs": 0.0, "plugins": {}}
    svc.list_items.return_value = []
    return svc


@pytest.fixture
def client(mock_svc):
    from web import create_app
    return TestClient(create_app(mock_svc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_link_b64(url: str) -> str:
    """Return URL-safe base64 encoding of a URL string."""
    return base64.urlsafe_b64encode(url.encode()).decode()


_AMAZON_URL = "https://www.amazon.com/dp/B08N5WRWNW"
_AMAZON_B64 = _make_link_b64(_AMAZON_URL)


# ---------------------------------------------------------------------------
# Task 1: Three read-only endpoint tests
# ---------------------------------------------------------------------------


def test_get_history_empty(client, mock_svc):
    """GET /api/history with no confirmed orders returns {"confirmed_orders": []}."""
    mock_svc.get_confirmed_orders.return_value = []
    resp = client.get("/api/history")
    assert resp.status_code == 200
    assert resp.json() == {"confirmed_orders": []}


def test_get_history_with_orders(client, mock_svc):
    """GET /api/history returns one order dict with correct keys and values."""
    order = ("Widget A", "ORD-001", "2026-01-01T00:00:00+00:00", 1)
    mock_svc.get_confirmed_orders.return_value = [order]
    resp = client.get("/api/history")
    assert resp.status_code == 200
    data = resp.json()
    orders = data["confirmed_orders"]
    assert len(orders) == 1
    row = orders[0]
    assert row["name"] == "Widget A"
    assert row["order_id"] == "ORD-001"
    assert row["confirmed_at"] == "2026-01-01T00:00:00+00:00"
    assert row["checkout_attempts"] == 1


def test_get_price_history_with_data(client, mock_svc):
    """GET /api/price-history/<b64> returns series oldest-first; price is cents/100."""
    rows = [
        (2599, "USD", "2026-01-02T00:00:00+00:00"),
        (1999, "USD", "2026-01-01T00:00:00+00:00"),
    ]
    mock_svc.get_price_history_by_link.return_value = rows
    resp = client.get(f"/api/price-history/{_AMAZON_B64}")
    assert resp.status_code == 200
    series = resp.json()["series"]
    assert len(series) == 2
    assert series[0]["t"] <= series[-1]["t"]
    assert series[0]["price"] == pytest.approx(19.99)


def test_get_price_history_empty(client, mock_svc):
    """GET /api/price-history/<b64> with no rows returns {"series": []}."""
    mock_svc.get_price_history_by_link.return_value = []
    resp = client.get(f"/api/price-history/{_AMAZON_B64}")
    assert resp.status_code == 200
    assert resp.json() == {"series": []}


def test_get_price_history_bad_link(client):
    """GET /api/price-history with invalid base64 returns 200 with {"series": []}."""
    resp = client.get("/api/price-history/!!!notbase64!!!")
    assert resp.status_code == 200
    assert resp.json() == {"series": []}


def test_logs_filtered_level_and_search(client):
    """GET /api/logs?level=ERROR&search=captcha&n=50 calls read_logs_filtered correctly."""
    fake_logs = ["[ERROR][2026-01-01@00:00:00] captcha detected"]
    with patch("web.routes.api.read_logs_filtered", return_value=fake_logs) as mock_fn:
        resp = client.get("/api/logs?level=ERROR&search=captcha&n=50")
    assert resp.status_code == 200
    assert resp.json() == {"logs": fake_logs}
    mock_fn.assert_called_once_with(50, "ERROR", "captcha")


def test_logs_no_params_default_behavior(client):
    """GET /api/logs with no params calls read_logs_filtered(50, None, None)."""
    fake_logs = ["[INFO][2026-01-01@00:00:00] loop started"]
    with patch("web.routes.api.read_logs_filtered", return_value=fake_logs) as mock_fn:
        resp = client.get("/api/logs")
    assert resp.status_code == 200
    assert resp.json() == {"logs": fake_logs}
    mock_fn.assert_called_once_with(50, None, None)


# ---------------------------------------------------------------------------
# Task 3: Credential-leak + last_error scrub tests
# ---------------------------------------------------------------------------


def test_get_status_no_credential_leak():
    """get_status() payload serialises without any credential-pattern strings."""
    from core.health import HealthRegistry

    registry = HealthRegistry()
    registry._ensure("TestPlugin")
    registry._plugins["TestPlugin"]["last_error"] = "ConnectionError"

    svc_mock = MagicMock()
    svc_mock.get_status.return_value = {
        "running": False,
        "uptime_secs": 0.0,
        "plugins": registry.get_snapshot(),
    }
    payload = json.dumps(svc_mock.get_status())
    assert not CRED_PATTERN.search(payload), (
        f"Credential pattern found in get_status() output: {CRED_PATTERN.findall(payload)}"
    )


def test_api_status_no_credential_leak():
    """GET /api/status response body contains no credential-pattern strings."""
    from core.health import HealthRegistry
    from web import create_app

    registry = HealthRegistry()
    registry._ensure("TestPlugin")
    registry._plugins["TestPlugin"]["last_error"] = "ConnectionError"

    svc = MagicMock()
    svc.get_status.return_value = {
        "running": False,
        "uptime_secs": 0.0,
        "plugins": registry.get_snapshot(),
    }
    svc.list_items.return_value = []

    test_client = TestClient(create_app(svc))
    resp = test_client.get("/api/status")
    assert resp.status_code == 200
    assert not CRED_PATTERN.search(resp.text), (
        f"Credential pattern found in /api/status response: {CRED_PATTERN.findall(resp.text)}"
    )


def test_health_last_error_scrubbed():
    """HealthRegistry stores only the class name, never str(exc) with credentials."""
    from core.health import HealthRegistry

    registry = HealthRegistry()
    exc = RuntimeError("proxy http://user:pass@host token=abc")
    registry.record_last_error("P", exc)

    snapshot = registry.get_snapshot()
    assert snapshot["P"]["last_error"] == "RuntimeError"
    assert "@" not in snapshot["P"]["last_error"]
