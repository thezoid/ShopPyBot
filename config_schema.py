"""AppConfig: Pydantic schema validating config.yml at startup.

Replaces the legacy yaml.safe_load shim in config.py. Per Phase 1 D-06, deprecated
app.amz_*/app.bb_* credential keys hard-fail with a migration block; per D-07 the
schema is strict (extra=forbid) and env vars (SHOPBOT_ prefix, __ nested delimiter)
override YAML to satisfy SEC-01.
"""
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class PlatformCredentials(BaseModel):
    email: str
    password: str
    # cvv intentionally absent: prompted at runtime via getpass (SEC-02).


class PlatformConfig(BaseModel):
    enabled: bool = True
    credentials: PlatformCredentials


class SeleniumConfig(BaseModel):
    driver_path: str


class DebugConfig(BaseModel):
    logging_level: int = Field(5, ge=0, le=5)
    test_mode: bool = False


class ItemConfig(BaseModel):
    name: str
    link: str
    auto_buy: bool
    quantity: int = Field(ge=1)


class AvailableConfig(BaseModel):
    items: list[ItemConfig]


class AppSettings(BaseModel):
    """Phase 4: orchestrator-level settings (polling cadence, etc.)."""
    delay: float = Field(default=5.0, ge=0.1, le=3600.0)


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        extra="forbid",
        env_nested_delimiter="__",
        env_prefix="SHOPBOT_",
        yaml_file="config.yml",
    )

    selenium: SeleniumConfig
    debug: DebugConfig = DebugConfig()
    available: AvailableConfig
    platforms: dict[str, PlatformConfig]
    open_browser: bool = False
    app: AppSettings = AppSettings()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Priority: init > env > YAML. Env wins over YAML for SEC-01.
        return (init_settings, env_settings, YamlConfigSettingsSource(settings_cls))

    @model_validator(mode="before")
    @classmethod
    def reject_deprecated_keys(cls, data):
        # D-06: hard-fail on legacy app.* credential keys with no auto-remap.
        if not isinstance(data, dict):
            return data
        app = data.get("app", {}) if isinstance(data.get("app"), dict) else {}
        deprecated = {
            "amz_email":   "SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__EMAIL or platforms.amazon.credentials.email",
            "amz_pwd":     "SHOPBOT_PLATFORMS__AMAZON__CREDENTIALS__PASSWORD",
            "bb_email":    "SHOPBOT_PLATFORMS__BESTBUY__CREDENTIALS__EMAIL or platforms.bestbuy.credentials.email",
            "bb_password": "SHOPBOT_PLATFORMS__BESTBUY__CREDENTIALS__PASSWORD",
            "bb_cvv":      "(removed) prompted at runtime via getpass; opt-in env SHOPBOT_BESTBUY_CVV with SHOPBOT_ALLOW_CVV_ENV=true",
        }
        found = {k: v for k, v in deprecated.items() if k in app}
        if found:
            lines = [
                "=== DEPRECATED CONFIG KEYS DETECTED ===",
                "config.yml uses old credential keys. Migrate before continuing:",
                "",
            ]
            for old, new in found.items():
                lines.append(f"  app.{old}  ->  {new}")
            lines.append("")
            lines.append("After migration, remove the entire `app:` section if empty.")
            lines.append("Bot will not start until migration is complete.")
            raise ValueError("\n".join(lines))
        return data
