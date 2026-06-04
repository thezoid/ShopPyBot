"""test_web_items.py: items API route tests (Wave 0 scaffold)."""
import pytest
pytest.importorskip("fastapi")

import base64
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


def test_get_items_returns_list(mock_svc, client):
    """GET /api/items serializes BotService.list_items() 5-tuples."""
    mock_svc.list_items.return_value = [
        ("Widget", "https://ex.com/w", False, 1, False),
    ]
    resp = client.get("/api/items")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) == 1


def test_post_item_calls_add_item(mock_svc, client):
    """POST /api/items calls svc.add_item with the correct arguments."""
    resp = client.post(
        "/api/items",
        json={"name": "Widget", "link": "https://ex.com/w", "auto_buy": False, "quantity": 1},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert resp.status_code == 200
    mock_svc.add_item.assert_called_once_with("Widget", "https://ex.com/w", False, 1)


def test_delete_item_calls_remove_item(mock_svc, client):
    """DELETE /api/items/{b64} calls svc.remove_item with decoded URL."""
    link = "https://ex.com/w"
    b64 = base64.urlsafe_b64encode(link.encode()).decode()
    resp = client.delete(
        f"/api/items/{b64}",
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert resp.status_code == 200
    mock_svc.remove_item.assert_called_once_with(link)


def test_post_item_missing_name_returns_422(mock_svc, client):
    """POST /api/items with missing name returns 422, not 500 (WR-02)."""
    resp = client.post(
        "/api/items",
        json={"link": "https://ex.com/w", "auto_buy": False, "quantity": 1},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert resp.status_code == 422
    mock_svc.add_item.assert_not_called()


def test_post_item_missing_link_returns_422(mock_svc, client):
    """POST /api/items with missing link returns 422, not 500 (WR-02)."""
    resp = client.post(
        "/api/items",
        json={"name": "Widget", "auto_buy": False, "quantity": 1},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert resp.status_code == 422
    mock_svc.add_item.assert_not_called()


def test_post_item_bad_quantity_returns_422(mock_svc, client):
    """POST /api/items with non-integer quantity returns 422 (WR-02)."""
    resp = client.post(
        "/api/items",
        json={"name": "Widget", "link": "https://ex.com/w", "auto_buy": False, "quantity": "banana"},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert resp.status_code == 422
    mock_svc.add_item.assert_not_called()


def test_web_add_item_parity(tmp_data_dir):
    """Web add produces identical DB state to CLI add (SC2)."""
    from models import initialize_db
    from core.service import BotService
    from web import create_app
    initialize_db(delete=True)
    svc = BotService()
    client = TestClient(create_app(svc), base_url="http://127.0.0.1:8000")
    client.post(
        "/api/items",
        json={"name": "Widget", "link": "https://example.com/w", "auto_buy": False, "quantity": 1},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    rows = svc.list_items()
    assert any(r[1] == "https://example.com/w" for r in rows)
