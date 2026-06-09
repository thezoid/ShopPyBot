"""test_web_dashboard.py: dashboard page rendering tests (Wave 0 scaffold)."""
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


def test_dashboard_no_credential_value_in_html():
    """SC3 runtime guard: GET / never leaks a credential value into the HTML.

    Seeds a mock store that returns a KNOWN secret for a credential key.
    The rendered HTML must NOT contain that secret -- the template renders
    only name + Set/Not-set status, never a value (T-10-15).
    """
    from web import create_app
    KNOWN_SECRET = "SUPER_SECRET_TOKEN_12345"

    mock_store = MagicMock()
    mock_store.get.return_value = KNOWN_SECRET  # every key "has" this value

    svc = MagicMock()
    svc.get_status.return_value = {"running": False}
    svc.list_items.return_value = []

    with patch("core.credentials.get_store", return_value=mock_store):
        app = create_app(svc)
        client = TestClient(app)
        resp = client.get("/")

    assert resp.status_code == 200
    assert KNOWN_SECRET not in resp.text


def test_banner_renders_when_non_local(mock_svc):
    """MC-4 regression: banner HTML renders when is_non_local=True.

    Proves that 'reachable beyond localhost' text and 'banner-warning' class appear in
    the dashboard response when the app is bound to a non-local interface.
    """
    from web import create_app
    non_local_client = TestClient(create_app(mock_svc, is_non_local=True))
    resp = non_local_client.get("/")
    assert resp.status_code == 200
    assert "reachable beyond localhost" in resp.text
    assert "banner-warning" in resp.text


def test_banner_absent_when_local(mock_svc):
    """MC-4 regression: banner HTML is absent when is_non_local=False (default).

    Proves the {% if is_non_local %} conditional actually gates the banner -- the
    warning must NOT appear for local-only binds (Pitfall 5).
    """
    from web import create_app
    local_client = TestClient(create_app(mock_svc, is_non_local=False))
    resp = local_client.get("/")
    assert resp.status_code == 200
    assert "reachable beyond localhost" not in resp.text


def test_dashboard_no_platform_config_toggles(client):
    """GET / must NOT render per-platform enable checkboxes in the Config section.

    Per the config-scope discrepancy: AppConfig has no platform 'enabled' field.
    Only notifier toggles (sound, discord, email, sms) render -- not platform names.
    """
    resp = client.get("/")
    html = resp.text
    # Config section must not contain platform-name config controls
    # (the JS loadConfig() renders only WEB_ALLOWLIST keys which have no platform keys)
    platform_names = ["amazon", "bestbuy", "walmart", "target", "gamestop",
                      "squareenix", "newegg"]
    # The config-form-wrapper div is populated by JS from /api/config -- the
    # SSR HTML contains the empty wrapper, not rendered platform toggles.
    # Assert the static HTML template itself contains no platform config input.
    assert 'id="cfg-amazon"' not in html
    assert 'id="cfg-bestbuy"' not in html
    for platform in platform_names:
        assert f'name="{platform}"' not in html and f'data-key="{platform}"' not in html, (
            f"Platform config toggle for {platform!r} leaked into SSR HTML"
        )
