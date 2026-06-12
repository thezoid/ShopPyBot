import warnings

import pytest
import yaml
from pydantic import ValidationError

from core.config_schema import AppConfig, DEFAULT_USER_AGENTS


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


# ---------------------------------------------------------------------------
# Phase 6: per-platform anti-detection config (ANTI-01/02/03 + SC3)
# ---------------------------------------------------------------------------


def test_walmart_platform_fields_load_from_yaml(tmp_path):
    """ANTI-01/02/03: walmart min_delay, max_delay, headless, user_agents load from YAML."""
    cfg = {
        "debug": {"logging_level": 3, "test_mode": True},
        "available": {"timeout": 10, "items": []},
        "platforms": {
            "walmart": {
                "min_delay": 8,
                "max_delay": 15,
                "headless": False,
                "user_agents": ["Mozilla/5.0 FakeAgent/1.0"],
            }
        },
    }
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    config = AppConfig(yaml_file=f)
    assert config.platforms.walmart.min_delay == 8.0
    assert config.platforms.walmart.max_delay == 15.0
    assert config.platforms.walmart.headless is False
    assert config.platforms.walmart.user_agents == ["Mozilla/5.0 FakeAgent/1.0"]


def test_negative_min_delay_raises_validation_error(tmp_path):
    """ANTI-01 / T-06-01: min_delay=-1 raises Pydantic ValidationError at startup."""
    cfg = {
        "available": {"items": []},
        "platforms": {"walmart": {"min_delay": -1}},
    }
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    with pytest.raises(ValidationError):
        AppConfig(yaml_file=f)


def test_negative_max_delay_raises_validation_error(tmp_path):
    """ANTI-01 / T-06-01: max_delay=-1 raises Pydantic ValidationError at startup."""
    cfg = {
        "available": {"items": []},
        "platforms": {"walmart": {"max_delay": -1}},
    }
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    with pytest.raises(ValidationError):
        AppConfig(yaml_file=f)


def test_default_user_agents_is_non_empty_list_of_strings():
    """ANTI-02: DEFAULT_USER_AGENTS is a non-empty list[str] importable from config_schema."""
    assert isinstance(DEFAULT_USER_AGENTS, list)
    assert len(DEFAULT_USER_AGENTS) > 0
    for ua in DEFAULT_USER_AGENTS:
        assert isinstance(ua, str)


def test_squareenix_platform_config_reachable(tmp_path):
    """ANTI-01: platforms.squareenix (no underscore) is reachable on PlatformsConfig."""
    cfg = {
        "available": {"items": []},
        "platforms": {"squareenix": {"min_delay": 5, "max_delay": 10}},
    }
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    config = AppConfig(yaml_file=f)
    assert config.platforms.squareenix.min_delay == 5.0
    assert config.platforms.squareenix.max_delay == 10.0


def test_amazon_and_bestbuy_headless_default_true(valid_config_yml):
    """SC3: platforms.amazon.headless and platforms.bestbuy.headless default to True."""
    config = AppConfig(yaml_file=valid_config_yml)
    assert config.platforms.amazon.headless is True
    assert config.platforms.bestbuy.headless is True


def test_amazon_headless_false_loads_as_false(tmp_path):
    """SC3: platforms.amazon.headless: false in YAML yields False (not dropped by extra=ignore)."""
    cfg = {
        "available": {"items": []},
        "platforms": {"amazon": {"delay_seconds": 30.0, "headless": False}},
    }
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    config = AppConfig(yaml_file=f)
    assert config.platforms.amazon.headless is False


# ---------------------------------------------------------------------------
# Phase 18: DebugConfig.monitor_only + CheckoutConfig (BUY-01, BUY-02)
# ---------------------------------------------------------------------------


def test_monitor_only_default_false():
    """BUY-01: AppConfig().debug.monitor_only defaults to False (CONTEXT.md decision)."""
    from core.config_schema import AppConfig
    assert AppConfig().debug.monitor_only is False


def test_checkout_config_defaults():
    """BUY-01: CheckoutConfig() defaults match documented values."""
    from core.config_schema import CheckoutConfig
    ck = CheckoutConfig()
    assert ck.item_timeout_secs == 120
    assert ck.step_timeout_secs == 30
    assert ck.max_cart_retries == 3
    assert ck.backoff_base == 2.0
    assert ck.backoff_jitter == 0.5
    assert ck.alert_on_errors == 3


def test_appconfig_checkout_is_checkout_config_instance():
    """BUY-01: AppConfig().checkout is a CheckoutConfig instance with all defaults."""
    from core.config_schema import AppConfig, CheckoutConfig
    cfg = AppConfig()
    assert isinstance(cfg.checkout, CheckoutConfig)
    assert cfg.checkout.item_timeout_secs == 120
    assert cfg.checkout.step_timeout_secs == 30
    assert cfg.checkout.max_cart_retries == 3
    assert cfg.checkout.backoff_base == 2.0
    assert cfg.checkout.backoff_jitter == 0.5
    assert cfg.checkout.alert_on_errors == 3


def test_checkout_override_not_dropped(tmp_path):
    """T-18-03: checkout YAML key is not silently dropped (declared class attribute check)."""
    cfg = {
        "available": {"items": []},
        "checkout": {"item_timeout_secs": 60},
    }
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    from core.config_schema import AppConfig
    config = AppConfig(yaml_file=f)
    assert config.checkout.item_timeout_secs == 60


def test_checkout_item_timeout_zero_rejected():
    """T-18-01: item_timeout_secs=0 (below ge=1 bound) raises ValidationError."""
    from core.config_schema import CheckoutConfig
    with pytest.raises(ValidationError):
        CheckoutConfig(item_timeout_secs=0)


def test_checkout_step_timeout_zero_rejected():
    """T-18-01: step_timeout_secs=0 (below ge=1 bound) raises ValidationError."""
    from core.config_schema import CheckoutConfig
    with pytest.raises(ValidationError):
        CheckoutConfig(step_timeout_secs=0)


def test_checkout_max_cart_retries_negative_rejected():
    """T-18-01: max_cart_retries=-1 (below ge=0 bound) raises ValidationError."""
    from core.config_schema import CheckoutConfig
    with pytest.raises(ValidationError):
        CheckoutConfig(max_cart_retries=-1)


def test_checkout_backoff_base_negative_rejected():
    """T-18-01: backoff_base=-0.1 (below ge=0.0 bound) raises ValidationError."""
    from core.config_schema import CheckoutConfig
    with pytest.raises(ValidationError):
        CheckoutConfig(backoff_base=-0.1)


# ---------------------------------------------------------------------------
# Phase 23: session_persistence per-platform opt-in flag (REL-04)
# ---------------------------------------------------------------------------


def test_session_persistence_defaults_false_all_platforms():
    """T-23-06: session_persistence defaults to False on all 7 platform models (opt-in, off by default)."""
    from core.config_schema import PlatformsConfig
    p = PlatformsConfig()
    assert p.amazon.session_persistence is False
    assert p.bestbuy.session_persistence is False
    assert p.walmart.session_persistence is False
    assert p.target.session_persistence is False
    assert p.gamestop.session_persistence is False
    assert p.squareenix.session_persistence is False
    assert p.newegg.session_persistence is False


def test_session_persistence_override_true(tmp_path):
    """T-23-05: session_persistence: true in YAML survives extra='ignore' (declared field, not dropped)."""
    cfg = {
        "available": {"items": []},
        "platforms": {"amazon": {"session_persistence": True}},
    }
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    config = AppConfig(yaml_file=f)
    assert config.platforms.amazon.session_persistence is True


def test_session_persistence_legacy_config_loads(tmp_path):
    """REL-04: platform config dict without session_persistence key loads with default False (additive, non-breaking)."""
    cfg = {
        "available": {"items": []},
        "platforms": {
            "amazon": {"delay_seconds": 30.0, "headless": True},
            "bestbuy": {"delay_seconds": 30.0},
            "walmart": {"min_delay": 8.0, "max_delay": 15.0},
        },
    }
    f = tmp_path / "config.yml"
    f.write_text(yaml.dump(cfg))
    config = AppConfig(yaml_file=f)
    assert config.platforms.amazon.session_persistence is False
    assert config.platforms.bestbuy.session_persistence is False
    assert config.platforms.walmart.session_persistence is False
