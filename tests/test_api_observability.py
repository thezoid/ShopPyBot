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


def test_get_analytics_aggregate_only_no_link_leak(client, mock_svc):
    """GET /api/analytics returns overall + per_plugin JSON with no link/credential leak (FC-02)."""
    mock_svc.get_analytics.return_value = {
        "overall": {
            "attempted": 4,
            "confirmed": 3,
            "success_rate": 0.75,
            "avg_time_to_checkout_secs": 46.666666666666664,
            "sample_size": 3,
        },
        "per_plugin": [
            {
                "plugin": "amazon",
                "attempted": 2,
                "confirmed": 2,
                "success_rate": 1.0,
                "avg_time_to_checkout_secs": 40.0,
                "sample_size": 2,
            },
            {
                "plugin": "bestbuy",
                "attempted": 2,
                "confirmed": 1,
                "success_rate": 0.5,
                "avg_time_to_checkout_secs": 60.0,
                "sample_size": 1,
            },
        ],
    }
    resp = client.get("/api/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert "overall" in data and "per_plugin" in data
    assert data["overall"]["success_rate"] == 0.75
    assert data["per_plugin"][0]["plugin"] == "amazon"

    # Aggregate-only: no link/URL field anywhere in the response, and no
    # credential-pattern string (mirrors the get_status boundary convention).
    def _no_link_key(obj):
        if isinstance(obj, dict):
            assert "link" not in obj, f"link key leaked in analytics response: {obj}"
            for v in obj.values():
                _no_link_key(v)
        elif isinstance(obj, list):
            for item in obj:
                _no_link_key(item)

    _no_link_key(data)
    assert not CRED_PATTERN.search(resp.text), (
        f"Credential pattern found in /api/analytics response: {CRED_PATTERN.findall(resp.text)}"
    )


def test_get_analytics_empty_dataset(client, mock_svc):
    """GET /api/analytics with no order data returns valid JSON, no ZeroDivisionError."""
    mock_svc.get_analytics.return_value = {
        "overall": {
            "attempted": 0,
            "confirmed": 0,
            "success_rate": None,
            "avg_time_to_checkout_secs": None,
            "sample_size": 0,
        },
        "per_plugin": [],
    }
    resp = client.get("/api/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall"]["success_rate"] is None
    assert data["overall"]["avg_time_to_checkout_secs"] is None
    assert data["per_plugin"] == []


def test_logs_filtered_level_and_search(client):
    """GET /api/logs?level=ERROR&search=captcha&n=50 calls read_logs_filtered correctly."""
    fake_logs = ["[ERROR][2026-01-01@00:00:00] captcha detected"]
    with patch("web.routes.api.read_logs_filtered", return_value=fake_logs) as mock_fn:
        resp = client.get("/api/logs?level=ERROR&search=captcha&n=50")
    assert resp.status_code == 200
    assert resp.json() == {"logs": fake_logs}
    mock_fn.assert_called_once_with(50, "ERROR", "captcha", None)


def test_logs_no_params_default_behavior(client):
    """GET /api/logs with no params calls read_logs_filtered(50, None, None, None)."""
    fake_logs = ["[INFO][2026-01-01@00:00:00] loop started"]
    with patch("web.routes.api.read_logs_filtered", return_value=fake_logs) as mock_fn:
        resp = client.get("/api/logs")
    assert resp.status_code == 200
    assert resp.json() == {"logs": fake_logs}
    mock_fn.assert_called_once_with(50, None, None, None)


def test_logs_plugin_filter_param(client):
    """GET /api/logs?plugin=amazon calls read_logs_filtered(50, None, None, "amazon") (FC-01)."""
    fake_logs = ["[INFO][amazon][2026-01-01@00:00:00] checking stock"]
    with patch("web.routes.api.read_logs_filtered", return_value=fake_logs) as mock_fn:
        resp = client.get("/api/logs?plugin=amazon")
    assert resp.status_code == 200
    assert resp.json() == {"logs": fake_logs}
    mock_fn.assert_called_once_with(50, None, None, "amazon")


def test_logs_invalid_plugin_param_dropped_to_none(client):
    """GET /api/logs?plugin=<invalid> is dropped to None before calling read_logs_filtered.

    Defense-in-depth whitelist (V5): the internal [plugin] tag is always
    lowercase-alphanumeric; anything else is not a real platform_key and is
    dropped rather than passed through to the filter (T-34-03/T-34-04).
    """
    fake_logs = []
    with patch("web.routes.api.read_logs_filtered", return_value=fake_logs) as mock_fn:
        resp = client.get("/api/logs?plugin=Bad%21Value")
    assert resp.status_code == 200
    mock_fn.assert_called_once_with(50, None, None, None)


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
