import warnings

import pytest
import yaml

from core.config_schema import AppConfig


@pytest.fixture
def legacy_config_yml(tmp_path):
    """Config YAML with the old credential keys (deprecated by Phase 1, CORE-07)."""
    config_content = {
        "app": {
            "amz_email": "your_amazon_email@example.com",
            "amz_pwd": "your_amazon_password",
            "bb_email": "your_bestbuy_email@example.com",
            "bb_password": "your_bestbuy_password",
            "bb_cvv": "your_bestbuy_cvv",
            "open_browser": False,
        },
        "debug": {"test_mode": True},
        "available": {
            "timeout": 10,
            "items": [
                {
                    "name": "Magic: The Gathering - Final Fantasy Play Booster Box (30 Packs)",
                    "link": "https://www.amazon.com/Magic-Gathering-Final-Fantasy-Booster/dp/B0DTMQBLSY",
                    "auto_buy": True,
                    "quantity": 2,
                }
            ],
        },
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(config_content))
    return config_file


def test_legacy_credentials_trigger_deprecation_warning(legacy_config_yml):
    """CORE-07: credential keys in config.yml emit DeprecationWarning via AppConfig.

    Phase 1 deprecated storing credentials in config.yml. AppConfig must warn
    loudly so operators know to migrate to environment variables.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        AppConfig(yaml_file=legacy_config_yml)
    warning_messages = [str(w.message) for w in caught]
    assert any("amz_email" in msg for msg in warning_messages), (
        "Expected DeprecationWarning mentioning 'amz_email'"
    )
    assert any(issubclass(w.category, DeprecationWarning) for w in caught), (
        "Expected at least one DeprecationWarning"
    )


def test_appconfig_has_no_credential_fields(legacy_config_yml):
    """CORE-07: AppConfig does not expose credential fields on the model.

    Credentials belong in environment variables, not in the config schema.
    This test asserts the new contract: loading a config with legacy credential
    keys does NOT populate credential attributes on AppConfig.
    """
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        cfg = AppConfig(yaml_file=legacy_config_yml)
    assert not hasattr(cfg, "amz_email"), "amz_email must not be a field on AppConfig"
    assert not hasattr(cfg, "amz_pwd"), "amz_pwd must not be a field on AppConfig"
    assert not hasattr(cfg, "bb_email"), "bb_email must not be a field on AppConfig"
    assert not hasattr(cfg, "bb_password"), "bb_password must not be a field on AppConfig"
    assert not hasattr(cfg, "bb_cvv"), "bb_cvv must not be a field on AppConfig"


def test_appconfig_items_still_load_correctly(legacy_config_yml):
    """Sanity: structured config sections load correctly even with legacy keys present."""
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        cfg = AppConfig(yaml_file=legacy_config_yml)
    assert len(cfg.available.items) == 1
    assert cfg.available.items[0].name == (
        "Magic: The Gathering - Final Fantasy Play Booster Box (30 Packs)"
    )
    assert cfg.available.items[0].auto_buy is True
