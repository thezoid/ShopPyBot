"""test_observability_ui.py: Static-scaffold assertions for Phase 28 observability surfaces.

Wave 0 RED scaffold — all tests assert HTML ids and content that do NOT yet exist
in dashboard.html. They turn GREEN when 28-03/28-04 land the new sections.

Does NOT duplicate:
- test_no_innerHTML_with_api_data  (lives in test_web_dashboard.py, covers whole file)
- test_uplot_served                (lives in test_web_dashboard.py)
"""
import pytest
pytest.importorskip("fastapi")

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    svc.get_status.return_value = {"running": False, "uptime_secs": 0, "plugins": {}}
    svc.list_items.return_value = []
    return svc


@pytest.fixture
def client(mock_svc):
    from web import create_app
    return TestClient(create_app(mock_svc))


# ---------------------------------------------------------------------------
# OBS-01 / OBS-02 / OBS-03 — Plugin Health section
# ---------------------------------------------------------------------------

def test_dashboard_renders_health_section(client):
    """GET / renders #section-health with 'Plugin Health' heading (OBS-01/02/03).

    RED until 28-03/28-04 land the section HTML.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="section-health"' in resp.text
    assert "Plugin Health" in resp.text


# ---------------------------------------------------------------------------
# OBS-09 — Uptime slot in header
# ---------------------------------------------------------------------------

def test_header_uptime_slot_present(client):
    """GET / includes the #header-uptime span in the page header (OBS-09).

    The slot already exists from Phase 25; this guard ensures it is NOT removed.
    GREEN at Wave 0 since Phase 25 already placed it.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="header-uptime"' in resp.text


# ---------------------------------------------------------------------------
# OBS-04 — Confirmed Orders section
# ---------------------------------------------------------------------------

def test_dashboard_renders_buys_section(client):
    """GET / renders #section-buys with 'Confirmed Orders' heading and table headers (OBS-04).

    RED until 28-03/28-04 land the section HTML.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="section-buys"' in resp.text
    assert "Confirmed Orders" in resp.text
    assert "Order ID" in resp.text
    assert "Checkout Attempts" in resp.text


# ---------------------------------------------------------------------------
# OBS-06 / OBS-08 UI — Log Viewer section
# ---------------------------------------------------------------------------

def test_dashboard_renders_log_viewer_section(client):
    """GET / renders #section-log-viewer with log-buffer, level filter, and search controls (OBS-06/08).

    RED until 28-03/28-04 land the section HTML.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="section-log-viewer"' in resp.text
    assert 'id="log-buffer"' in resp.text
    assert 'id="log-level-filter"' in resp.text
    assert 'id="log-search"' in resp.text


# ---------------------------------------------------------------------------
# OBS-07 — DOM cap constant (500 lines)
# ---------------------------------------------------------------------------

def test_log_dom_cap_constant(client):
    """GET / includes the MAX_LOG_LINES = 500 constant in the rendered page (OBS-07).

    The constant is declared inline in the JS block inside dashboard.html.
    RED until 28-03/28-04 land the JS.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert "MAX_LOG_LINES = 500" in resp.text


# ---------------------------------------------------------------------------
# OBS-05 — uPlot script and CSS assets linked
# ---------------------------------------------------------------------------

def test_uplot_script_and_css_present(client):
    """GET / links both uplot.iife.min.js and uplot.min.css (OBS-05).

    uplot.min.css is already present from Phase 25.
    uplot.iife.min.js script tag must also appear for charts to render.
    GREEN for css link (Phase 25 placed it); RED for iife script src until 28-03/28-04.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    assert "/static/vendor/uplot.iife.min.js" in resp.text
    assert "/static/vendor/uplot.min.css" in resp.text
