"""test_web_config.py: web config API route tests (Wave 0 scaffold)."""
import pytest
pytest.importorskip("fastapi")

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False}
    svc.list_items.return_value = []
    # Configure get_config() so read_web_config returns JSON-serializable values
    cfg = MagicMock()
    cfg.debug.test_mode = True
    cfg.debug.logging_level = 5
    cfg.notifications.sound = True
    cfg.notifications.discord.enabled = False
    cfg.notifications.email.enabled = False
    cfg.notifications.sms.enabled = False
    svc.get_config.return_value = cfg
    return svc


@pytest.fixture
def client(mock_svc):
    from web import create_app
    return TestClient(create_app(mock_svc))


def test_get_config_returns_allowlisted_keys(client):
    """GET /api/config returns test_mode, logging_level, and notifier toggles."""
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "test_mode" in data
    assert "logging_level" in data


def test_post_config_allowlisted_key(tmp_data_dir, mock_svc):
    """POST /api/config writes an allowlisted key and returns {"status": "ok"}."""
    from web import create_app
    client = TestClient(create_app(mock_svc))
    with patch("web.config_web.write_web_config") as mock_write:
        mock_write.return_value = None
        resp = client.post(
            "/api/config",
            json={"key": "test_mode", "value": "true"},
            headers={"origin": "http://127.0.0.1:8000"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_post_config_unknown_key_returns_422(client):
    """POST /api/config with an unknown key returns 422."""
    resp = client.post(
        "/api/config",
        json={"key": "not_a_real_key", "value": "anything"},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert resp.status_code == 422
