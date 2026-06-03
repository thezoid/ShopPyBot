from __future__ import annotations

import threading
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

# Thread-local storage for yaml path injection: eliminates race on mutable class
# attribute when two AppConfig() constructions run concurrently (CR-03).
_yaml_path_local: threading.local = threading.local()


class SeleniumConfig(BaseModel):
    driver_path: str = "chromedriver"


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


class AppSettingsConfig(BaseModel):
    """Top-level app settings not tied to a specific platform.

    poll_interval: seconds between each full check cycle across all plugins.
    Per-platform jitter is Phase 6; do NOT add jitter fields here.
    """

    poll_interval: int = 30


class AppConfig(BaseSettings):
    # yaml_file is NOT in model_config; path is injected in settings_customise_sources.
    # Test injection: pass yaml_file=<Path> as a constructor kwarg.
    # Thread-safe: path stored in _yaml_path_local (threading.local) so concurrent
    # AppConfig() constructions cannot clobber each other (CR-03).
    model_config = SettingsConfigDict(
        extra="ignore",
        env_nested_delimiter="__",
    )

    selenium: SeleniumConfig = SeleniumConfig()
    debug: DebugConfig = DebugConfig()
    available: AvailableConfig = AvailableConfig()
    platforms: PlatformsConfig = PlatformsConfig()
    app: AppSettingsConfig = AppSettingsConfig()

    def __init__(self, yaml_file: Path | str | None = None, **values):
        # Store path in thread-local so settings_customise_sources (a classmethod)
        # picks up the correct path per-thread without a shared mutable class attr (CR-03).
        _yaml_path_local.active = Path(yaml_file) if yaml_file is not None else _DEFAULT_YAML_PATH
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
        # yaml_file is resolved from thread-local (CR-03: no shared mutable class attr)
        yaml_file = getattr(_yaml_path_local, "active", _DEFAULT_YAML_PATH)
        return (env_settings, YamlConfigSettingsSource(settings_cls, yaml_file=yaml_file))
