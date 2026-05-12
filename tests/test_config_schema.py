import pytest
from pydantic import ValidationError


VALID_YAML = """
selenium:
  driver_path: ./chromedriver.exe
debug:
  logging_level: 3
  test_mode: true
open_browser: false
platforms:
  amazon:
    enabled: true
    credentials:
      email: yaml@example.com
      password: yamlpw
available:
  items: []
"""


def _write_cfg(tmp_path, monkeypatch, body):
    (tmp_path / "config.yml").write_text(body)
    monkeypatch.chdir(tmp_path)


def test_valid_config_loads(tmp_path, monkeypatch, clean_env):
    _write_cfg(tmp_path, monkeypatch, VALID_YAML)
    from config_schema import AppConfig
    cfg = AppConfig()
    assert cfg.selenium.driver_path == "./chromedriver.exe"
    assert cfg.debug.logging_level == 3
    assert cfg.platforms["amazon"].enabled is True
    assert cfg.platforms["amazon"].credentials.email == "yaml@example.com"


def test_missing_field_message(tmp_path, monkeypatch, clean_env):
    bad = VALID_YAML.replace("selenium:\n  driver_path: ./chromedriver.exe\n", "")
    _write_cfg(tmp_path, monkeypatch, bad)
    from config_schema import AppConfig
    with pytest.raises(ValidationError) as exc:
        AppConfig()
    msg = str(exc.value)
    assert "selenium" in msg


def test_extra_keys_rejected(tmp_path, monkeypatch, clean_env):
    _write_cfg(tmp_path, monkeypatch, VALID_YAML + "\nbogus_key: 1\n")
    from config_schema import AppConfig
    with pytest.raises(ValidationError) as exc:
        AppConfig()
    assert "bogus_key" in str(exc.value) or "extra" in str(exc.value).lower()


def test_per_platform_credentials(tmp_path, monkeypatch, clean_env):
    _write_cfg(tmp_path, monkeypatch, VALID_YAML)
    from config_schema import AppConfig
    cfg = AppConfig()
    assert hasattr(cfg.platforms["amazon"].credentials, "email")
    assert hasattr(cfg.platforms["amazon"].credentials, "password")


def test_deprecated_amz_email_hard_fails(tmp_path, monkeypatch, clean_env):
    bad = VALID_YAML + "\napp:\n  amz_email: leftover@example.com\n"
    _write_cfg(tmp_path, monkeypatch, bad)
    from config_schema import AppConfig
    with pytest.raises(Exception) as exc:
        AppConfig()
    msg = str(exc.value)
    assert "DEPRECATED" in msg
    assert "SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL" in msg


def test_deprecated_bb_cvv_hard_fails(tmp_path, monkeypatch, clean_env):
    bad = VALID_YAML + "\napp:\n  bb_cvv: '123'\n"
    _write_cfg(tmp_path, monkeypatch, bad)
    from config_schema import AppConfig
    with pytest.raises(Exception) as exc:
        AppConfig()
    msg = str(exc.value)
    assert "SHOPBOT_BESTBUY_CVV" in msg
    assert "SHOPBOT_ALLOW_CVV_ENV" in msg


def test_env_var_overrides_yaml(tmp_path, monkeypatch, clean_env):
    _write_cfg(tmp_path, monkeypatch, VALID_YAML)
    monkeypatch.setenv("SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL", "env@example.com")
    from config_schema import AppConfig
    cfg = AppConfig()
    assert cfg.platforms["amazon"].credentials.email == "env@example.com"
