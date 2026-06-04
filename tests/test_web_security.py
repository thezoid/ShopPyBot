"""test_web_security.py: is_localhost matrix, non-local warning, CSRF tests (Wave 0)."""
import pytest
pytest.importorskip("fastapi")

from unittest.mock import MagicMock
import uvicorn


# ---------------------------------------------------------------------------
# is_localhost matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("host,expected", [
    ("127.0.0.1", True),
    ("localhost", True),
    ("::1", True),
    ("[::1]:8000", True),
    ("127.0.0.1:8000", True),
    ("0.0.0.0", False),
    ("192.168.1.5", False),
    ("10.0.0.1", False),
])
def test_is_localhost_matrix(host, expected):
    """is_localhost returns correct bool for each host form."""
    from web.security import is_localhost
    assert is_localhost(host) is expected


# ---------------------------------------------------------------------------
# Non-local warning via handle_web
# ---------------------------------------------------------------------------

def test_non_local_host_warning(capsys, monkeypatch):
    """handle_web with host=0.0.0.0 prints 'WARNING' to stderr before serving."""
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: None)
    from core.cli.web import handle_web
    handle_web(type("args", (), {"host": "0.0.0.0", "port": 8000})(), MagicMock())
    assert "WARNING" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# is_non_local flag on app.state
# ---------------------------------------------------------------------------

def test_non_local_banner_flag():
    """create_app(svc, is_non_local=True) sets app.state.is_non_local to True."""
    from web import create_app
    app = create_app(MagicMock(), is_non_local=True)
    assert app.state.is_non_local is True


def test_local_banner_flag():
    """create_app(svc) sets app.state.is_non_local to False by default."""
    from web import create_app
    app = create_app(MagicMock())
    assert app.state.is_non_local is False


# ---------------------------------------------------------------------------
# CSRF: cross-origin POST returns 403
# ---------------------------------------------------------------------------

def test_csrf_rejected():
    """POST /api/items with a non-local origin returns 403."""
    from fastapi.testclient import TestClient
    from web import create_app
    svc = MagicMock()
    svc.list_items.return_value = []
    client = TestClient(create_app(svc), raise_server_exceptions=False)
    resp = client.post(
        "/api/items",
        json={"name": "X", "link": "http://example.com", "auto_buy": False, "quantity": 1},
        headers={"origin": "http://evil.com"},
    )
    assert resp.status_code == 403
