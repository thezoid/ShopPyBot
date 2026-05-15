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
    credentials: PlatformCredentials | None = None
    min_delay: float = 3.0
    max_delay: float = 8.0
    headless: bool = False

    @model_validator(mode="after")
    def validate_delay_range(self) -> "PlatformConfig":
        if self.min_delay <= 0 or self.max_delay <= 0:
            raise ValueError("min_delay and max_delay must be > 0")
        if self.min_delay > self.max_delay:
            raise ValueError(
                f"min_delay ({self.min_delay}) must be <= "
                f"max_delay ({self.max_delay})"
            )
        return self


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
    """Phase 4: orchestrator-level settings (polling cadence, etc.).

    Phase 6 ANTI-02: optional UA pool for build_driver rotation.
    """
    delay: float = Field(default=5.0, ge=0.1, le=3600.0)
    user_agents: list[str] | None = None


class SoundNotifierConfig(BaseModel):
    """Sound notifier defaults on (matches pre-Phase-5 behavior)."""
    enabled: bool = True


class DiscordNotifierConfig(BaseModel):
    """Discord webhook channel. webhook_url comes from SHOPBOT_DISCORD_WEBHOOK_URL env (SEC-01)."""
    enabled: bool = False


class EmailNotifierConfig(BaseModel):
    """SMTP channel. smtp_password comes from SHOPBOT_SMTP_PASSWORD env (SEC-01)."""
    enabled: bool = False
    from_addr: str | None = None
    to_addr: str | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str | None = None


class SmsNotifierConfig(BaseModel):
    """Twilio SMS. account_sid / auth_token / from_number come from env vars (SEC-01).

    Two-lock model: config.enabled AND SHOPBOT_ENABLE_SMS=true env are both required.
    """
    enabled: bool = False
    to: str | None = None


class NotificationsConfig(BaseModel):
    """Top-level notifications block; single source of truth for dedup window."""
    restock_window_seconds: int = Field(default=600, ge=0, le=86400)
    sound: SoundNotifierConfig = SoundNotifierConfig()
    discord: DiscordNotifierConfig = DiscordNotifierConfig()
    email: EmailNotifierConfig = EmailNotifierConfig()
    sms: SmsNotifierConfig = SmsNotifierConfig()


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
    notifications: NotificationsConfig = NotificationsConfig()

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
