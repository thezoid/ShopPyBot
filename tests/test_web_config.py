"""test_web_config.py: web config API route tests (Wave 0 scaffold)."""
import pytest
pytest.importorskip("fastapi")

from unittest.mock import MagicMock, patch
from pathlib import Path

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
    return TestClient(create_app(mock_svc), base_url="http://127.0.0.1:8000")


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
    client = TestClient(create_app(mock_svc), base_url="http://127.0.0.1:8000")
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


def test_sound_write_produces_scalar_bool_yaml(tmp_path):
    """write_web_config('notifications.sound', 'false') writes a scalar bool (CR-02).

    The resulting config.yml round-trips through AppConfig without ValidationError.
    """
    import yaml
    from core.config_schema import AppConfig
    from web.config_web import write_web_config

    cfg_path = tmp_path / "config.yml"
    cfg_path.write_text("notifications:\n  sound: true\n", encoding="utf-8")

    with patch("web.config_web._DEFAULT_YAML_PATH", cfg_path):
        write_web_config("notifications.sound", "false")

    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    # Must be a scalar bool, not a nested dict (CR-02)
    assert data["notifications"]["sound"] is False
    assert not isinstance(data["notifications"]["sound"], dict)

    # Round-trip: AppConfig must load without ValidationError
    app_cfg = AppConfig(yaml_file=cfg_path)
    assert app_cfg.notifications.sound is False
