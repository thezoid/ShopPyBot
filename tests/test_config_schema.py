import warnings

import pytest
import yaml
from pydantic import ValidationError

from core.config_schema import AppConfig


@pytest.fixture
def valid_config_yml(tmp_path):
    cfg = {
        "debug": {"logging_level": 3, "test_mode": True},
        "available": {"timeout": 10, "items": []},
        "platforms": {"amazon": {"delay_seconds": 30.0}, "bestbuy": {"delay_seconds": 30.0}},
    }
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    return f


def test_valid_yaml_loads(valid_config_yml):
    """CORE-05: valid config loads; typed attributes accessible."""
    config = AppConfig(yaml_file=valid_config_yml)
    assert config.debug.logging_level == 3


def test_missing_field_error(tmp_path):
    """CORE-05: items entry lacking 'name' raises ValidationError with field path."""
    cfg = {"available": {"items": [{"link": "https://example.com", "auto_buy": True}]}}
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    with pytest.raises(ValidationError) as exc_info:
        AppConfig(yaml_file=f)
    assert "name" in str(exc_info.value)


def test_platform_section_loads(valid_config_yml):
    """CORE-06: platforms.amazon.delay_seconds loads from nested YAML section."""
    config = AppConfig(yaml_file=valid_config_yml)
    assert config.platforms.amazon.delay_seconds == 30.0


def test_legacy_key_warning(tmp_path):
    """CORE-07: config with app.amz_email triggers DeprecationWarning."""
    cfg = {"app": {"amz_email": "old@example.com"}, "available": {"items": []}}
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        AppConfig(yaml_file=f)
    assert any("amz_email" in str(w.message) for w in caught)
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_env_var_override(valid_config_yml, monkeypatch):
    """SEC-01: env var DEBUG__LOGGING_LEVEL overrides YAML value."""
    monkeypatch.setenv("DEBUG__LOGGING_LEVEL", "1")
    config = AppConfig(yaml_file=valid_config_yml)
    assert config.debug.logging_level == 1


def test_poll_interval_default(valid_config_yml):
    """ASYNC-01: cfg.app.poll_interval defaults to 30 when app section absent."""
    config = AppConfig(yaml_file=valid_config_yml)
    assert config.app.poll_interval == 30


def test_poll_interval_yaml_override(tmp_path):
    """ASYNC-01: cfg.app.poll_interval reads integer from config.yml app section."""
    cfg = {
        "debug": {"logging_level": 3, "test_mode": True},
        "available": {"timeout": 10, "items": []},
        "app": {"poll_interval": 15},
    }
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    config = AppConfig(yaml_file=f)
    assert config.app.poll_interval == 15
