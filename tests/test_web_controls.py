"""test_web_controls.py: bot start/stop/status/logs API route tests (Wave 0)."""
import pytest
pytest.importorskip("fastapi")

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False}
    svc.list_items.return_value = []
    return svc


@pytest.fixture
def client(mock_svc):
    from web import create_app
    return TestClient(create_app(mock_svc), base_url="http://127.0.0.1:8000")


def test_bot_start_calls_svc_start(mock_svc, client):
    """POST /api/bot/start calls svc.start() (no CVV)."""
    resp = client.post(
        "/api/bot/start",
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert resp.status_code == 200
    mock_svc.start.assert_called_once()


def test_bot_stop_calls_svc_stop(mock_svc, client):
    """POST /api/bot/stop calls svc.stop() when bot is running."""
    mock_svc.get_status.return_value = {"running": True}
    resp = client.post(
        "/api/bot/stop",
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert resp.status_code == 200
    mock_svc.stop.assert_called_once()


def test_get_status_returns_running_bool(mock_svc, client):
    """GET /api/status returns a JSON body with a 'running' key."""
    mock_svc.get_status.return_value = {"running": True}
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert resp.json()["running"] is True


def test_get_logs_returns_list(client):
    """GET /api/logs returns a JSON body with a 'logs' list."""
    resp = client.get("/api/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert isinstance(data["logs"], list)


def test_status_endpoint_richer_shape(mock_svc, client):
    """GET /api/status with full health dict returns uptime_secs and plugins keys."""
    mock_svc.get_status.return_value = {
        "running": True,
        "uptime_secs": 10.5,
        "plugins": {
            "AmazonPlugin": {
                "status": "running",
                "heartbeat_age_secs": 5.3,
                "consecutive_errors": 0,
                "items_checked": 5,
                "orders_confirmed": 1,
            }
        },
    }
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "uptime_secs" in data
    assert "plugins" in data
    assert data["uptime_secs"] == 10.5
    assert "AmazonPlugin" in data["plugins"]
