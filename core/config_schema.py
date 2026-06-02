from __future__ import annotations

import warnings
from pathlib import Path

from pydantic import BaseModel, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

# Absolute path to config.yml — avoids CWD-relative default (RESEARCH Pitfall 2)
_DEFAULT_YAML_PATH: Path = Path(__file__).parent.parent / "config.yml"

_LEGACY_KEYS = {
    "app": ["amz_email", "amz_pwd", "bb_email", "bb_password", "bb_cvv"]
}


class ItemConfig(BaseModel):
    name: str
    link: str
    auto_buy: bool = False
    quantity: int = 1


class AvailableConfig(BaseModel):
    timeout: int = 10
    items: list[ItemConfig] = []


class DebugConfig(BaseModel):
    logging_level: int = 5
    test_mode: bool = True


class AmazonPlatformConfig(BaseModel):
    delay_seconds: float = 30.0
    delay_jitter: float = 10.0


class BestBuyPlatformConfig(BaseModel):
    delay_seconds: float = 30.0
    delay_jitter: float = 10.0


class PlatformsConfig(BaseModel):
    amazon: AmazonPlatformConfig = AmazonPlatformConfig()
    bestbuy: BestBuyPlatformConfig = BestBuyPlatformConfig()


class AppConfig(BaseSettings):
    # yaml_file is NOT in model_config; path is injected in settings_customise_sources.
    # Test injection: pass yaml_file=<Path> as a constructor kwarg.
    # pydantic-settings routes unrecognised init kwargs through init_settings,
    # so we intercept in __init__ and store on a class-level sentinel before
    # super().__init__ triggers settings_customise_sources (a classmethod).
    # We use a plain class attribute (no underscore) so pydantic treats it as
    # a class-level value, not a PrivateAttr.
    model_config = SettingsConfigDict(
        extra="ignore",
        env_nested_delimiter="__",
    )

    debug: DebugConfig = DebugConfig()
    available: AvailableConfig = AvailableConfig()
    platforms: PlatformsConfig = PlatformsConfig()

    # Class-level sentinel read by settings_customise_sources.
    # Each AppConfig() call may temporarily override this via __init__.
    _active_yaml_file: Path = _DEFAULT_YAML_PATH

    def __init__(self, yaml_file: Path | str | None = None, **values):
        # Temporarily set the class-level path so settings_customise_sources picks it up.
        # This is safe for single-threaded use (the typical test/CLI scenario).
        if yaml_file is not None:
            AppConfig._active_yaml_file = Path(yaml_file)
        else:
            AppConfig._active_yaml_file = _DEFAULT_YAML_PATH
        super().__init__(**values)

    @model_validator(mode="before")
    @classmethod
    def warn_legacy_keys(cls, data: dict) -> dict:
        """Emit DeprecationWarning for legacy credential keys (CORE-07)."""
        for section, keys in _LEGACY_KEYS.items():
            if not isinstance(data.get(section), dict):
                continue
            for key in keys:
                if key in data[section]:
                    warnings.warn(
                        f"config.yml: '{section}.{key}' is no longer used. "
                        f"Set credentials via environment variables. "
                        f"See .env.example for the new variable names.",
                        DeprecationWarning,
                        stacklevel=2,
                    )
        return data

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # env_settings first: env vars override YAML (SEC-01)
        # yaml_file is resolved from class-level sentinel (supports test injection)
        yaml_file = getattr(cls, "_active_yaml_file", _DEFAULT_YAML_PATH)
        return (env_settings, YamlConfigSettingsSource(settings_cls, yaml_file=yaml_file))
