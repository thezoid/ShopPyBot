"""test_web_credentials.py: credentials API route tests — SC3 (Wave 0 scaffold)."""
import pytest
pytest.importorskip("fastapi")

from unittest.mock import MagicMock, patch

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
    return TestClient(create_app(mock_svc))


def test_get_credentials_returns_name_and_is_set_only(client):
    """GET /api/credentials returns name + is_set only; no 'value' field (SC3)."""
    resp = client.get("/api/credentials")
    assert resp.status_code == 200
    data = resp.json()
    assert "credentials" in data
    for item in data["credentials"]:
        assert "name" in item
        assert "is_set" in item
        assert "value" not in item


def test_post_credentials_returns_ok_status(client):
    """POST /api/credentials returns {"status": "ok"}."""
    with patch("core.credentials.get_store") as mock_get_store:
        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        resp = client.post(
            "/api/credentials",
            json={"key": "AMZ_EMAIL", "value": "test@example.com"},
            headers={"origin": "http://127.0.0.1:8000"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_post_credentials_secret_not_in_response(client):
    """POST /api/credentials response body never contains the secret value (SC3)."""
    secret_value = "super-secret-password-12345"
    with patch("core.credentials.get_store") as mock_get_store:
        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        resp = client.post(
            "/api/credentials",
            json={"key": "AMZ_EMAIL", "value": secret_value},
            headers={"origin": "http://127.0.0.1:8000"},
        )
    assert secret_value not in resp.text


def test_post_credentials_calls_store_set(client):
    """POST /api/credentials calls get_store().set(key, value)."""
    with patch("core.credentials.get_store") as mock_get_store:
        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        client.post(
            "/api/credentials",
            json={"key": "AMZ_EMAIL", "value": "test@example.com"},
            headers={"origin": "http://127.0.0.1:8000"},
        )
        mock_store.set.assert_called_once_with("AMZ_EMAIL", "test@example.com")
