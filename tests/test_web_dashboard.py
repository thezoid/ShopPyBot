"""test_web_dashboard.py: dashboard page rendering tests (Wave 0 scaffold)."""
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
    return TestClient(create_app(mock_svc))


def test_dashboard_renders_controls_section(client):
    """GET / renders the Controls section heading."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Controls" in resp.text


def test_dashboard_renders_items_section(client):
    """GET / renders the Items section heading."""
    resp = client.get("/")
    assert "Items" in resp.text


def test_dashboard_renders_credentials_section(client):
    """GET / renders the Credentials section heading."""
    resp = client.get("/")
    assert "Credentials" in resp.text


def test_dashboard_renders_config_section(client):
    """GET / renders the Config section heading."""
    resp = client.get("/")
    assert "Config" in resp.text


def test_dashboard_renders_start_cta(client):
    """GET / includes the 'Start Bot' CTA copy from UI-SPEC."""
    resp = client.get("/")
    assert "Start Bot" in resp.text


def test_dashboard_renders_stop_cta(client):
    """GET / includes the 'Stop Bot' CTA copy from UI-SPEC."""
    resp = client.get("/")
    assert "Stop Bot" in resp.text
