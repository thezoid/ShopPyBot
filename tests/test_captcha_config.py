"""Tests for CaptchaConfig model and AppConfig.captcha field (ANTI-06, STAB-03)."""
from core.config_schema import AppConfig, CaptchaConfig


def test_captcha_config_defaults():
    """CaptchaConfig defaults: enabled=False, max_solves=10, threshold=1.00."""
    cfg = CaptchaConfig()
    assert cfg.enabled is False
    assert cfg.max_solves_per_run == 10
    assert cfg.low_balance_threshold == 1.00


def test_captcha_config_no_api_key_field():
    """CaptchaConfig must not expose an api_key field (ANTI-06 Pitfall 1)."""
    assert "api_key" not in CaptchaConfig.model_fields


def test_appconfig_has_captcha_field():
    """AppConfig.captcha is present and defaults to CaptchaConfig() (STAB-03)."""
    app = AppConfig()
    assert hasattr(app, "captcha")
    assert isinstance(app.captcha, CaptchaConfig)
    assert app.captcha.enabled is False
    assert app.captcha.max_solves_per_run == 10
    assert app.captcha.low_balance_threshold == 1.00


def test_captcha_config_yaml_override(tmp_path):
    """CaptchaConfig fields can be overridden via YAML."""
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text(
        "captcha:\n"
        "  enabled: true\n"
        "  max_solves_per_run: 5\n"
        "  low_balance_threshold: 2.50\n"
    )
    app = AppConfig(yaml_file=cfg_file)
    assert app.captcha.enabled is True
    assert app.captcha.max_solves_per_run == 5
    assert app.captcha.low_balance_threshold == 2.50
