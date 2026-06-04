"""test_web_app.py: basic app factory + route smoke tests (Wave 0 scaffold)."""
import pytest
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from unittest.mock import MagicMock


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


def test_create_app_returns_app():
    """create_app(svc) returns a FastAPI application instance."""
    from fastapi import FastAPI
    from web import create_app
    app = create_app(MagicMock())
    assert isinstance(app, FastAPI)


def test_root_returns_200(client):
    """GET / returns HTTP 200."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_static_mount_exists(mock_svc):
    """StaticFiles is mounted at /static."""
    from web import create_app
    app = create_app(mock_svc)
    route_paths = [getattr(r, "path", None) for r in app.routes]
    assert "/static" in route_paths


def test_api_status_returns_200(client):
    """GET /api/status returns 200 with a 'running' key."""
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert "running" in resp.json()
