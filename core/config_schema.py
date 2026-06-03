from __future__ import annotations

import os
import threading
import warnings
from pathlib import Path

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

# Absolute path to config.yml — avoids CWD-relative default (RESEARCH Pitfall 2)
_DEFAULT_YAML_PATH: Path = Path(__file__).parent.parent / "config.yml"

# Global default UA pool (ANTI-02): plugins fall back to this when platform
# user_agents list is empty.  Non-secret cosmetic config; update freely.
DEFAULT_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

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
    # NOTE: Amazon/BestBuy use delay_seconds/delay_jitter (legacy field names).
    # The five Phase-6 platforms use min_delay/max_delay instead.
    # This naming difference is intentional -- harmonization is deferred (out of Phase-6 scope).
    delay_seconds: float = 30.0
    delay_jitter: float = 10.0
    # SC3: declared field so extra="ignore" does not silently drop it from YAML.
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)


class BestBuyPlatformConfig(BaseModel):
    # NOTE: see AmazonPlatformConfig comment above on delay field naming.
    delay_seconds: float = 30.0
    delay_jitter: float = 10.0
    # SC3: declared field so extra="ignore" does not silently drop it from YAML.
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)


class WalmartPlatformConfig(BaseModel):
    """Per-platform anti-detection config for Walmart (ANTI-01/02/03)."""

    min_delay: float = Field(default=8.0, ge=0.0)   # ANTI-01: jitter lower bound
    max_delay: float = Field(default=15.0, ge=0.0)  # ANTI-01: jitter upper bound
    headless: bool = True                            # ANTI-03: per-platform headless toggle
    user_agents: list[str] = Field(default_factory=list)  # ANTI-02: empty = global default pool


class TargetPlatformConfig(BaseModel):
    """Per-platform anti-detection config for Target (ANTI-01/02/03)."""

    min_delay: float = Field(default=8.0, ge=0.0)
    max_delay: float = Field(default=15.0, ge=0.0)
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)


class GameStopPlatformConfig(BaseModel):
    """Per-platform anti-detection config for GameStop (ANTI-01/02/03)."""

    min_delay: float = Field(default=8.0, ge=0.0)
    max_delay: float = Field(default=15.0, ge=0.0)
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)


class SquareEnixPlatformConfig(BaseModel):
    """Per-platform anti-detection config for Square Enix (ANTI-01/02/03).

    Config key: platforms.squareenix (no underscore) -- matches plugin platform_key="squareenix".
    """

    min_delay: float = Field(default=8.0, ge=0.0)
    max_delay: float = Field(default=15.0, ge=0.0)
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)


class NeweggPlatformConfig(BaseModel):
    """Per-platform anti-detection config for NewEgg (ANTI-01/02/03)."""

    min_delay: float = Field(default=8.0, ge=0.0)
    max_delay: float = Field(default=15.0, ge=0.0)
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)


class PlatformsConfig(BaseModel):
    amazon: AmazonPlatformConfig = AmazonPlatformConfig()
    bestbuy: BestBuyPlatformConfig = BestBuyPlatformConfig()
    walmart: WalmartPlatformConfig = WalmartPlatformConfig()
    target: TargetPlatformConfig = TargetPlatformConfig()
    gamestop: GameStopPlatformConfig = GameStopPlatformConfig()
    # squareenix (no underscore): matches plugin platform_key and YAML key (RESEARCH Pitfall 4)
    squareenix: SquareEnixPlatformConfig = SquareEnixPlatformConfig()
    newegg: NeweggPlatformConfig = NeweggPlatformConfig()


class AppSettingsConfig(BaseModel):
    """Top-level app settings not tied to a specific platform.

    poll_interval: seconds between each full check cycle across all plugins.
    Per-platform jitter is Phase 6; do NOT add jitter fields here.
    """

    poll_interval: int = 30


class DiscordConfig(BaseModel):
    """Discord webhook notification config. Webhook URL is env-only (DISCORD_WEBHOOK_URL)."""

    enabled: bool = False


class EmailConfig(BaseModel):
    """Email/SMTP notification config. SMTP password is env-only (SMTP_PASSWORD)."""

    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_ssl: bool = False
    sender: str = ""
    smtp_username: str = ""  # defaults to sender when empty (per RESEARCH Open Question 1)
    recipients: list[str] = []


class SmsConfig(BaseModel):
    """SMS/Twilio notification config. Credentials are env-only (TWILIO_*)."""

    enabled: bool = False
    to_number: str = ""  # recipient; From number is TWILIO_FROM env var

    @model_validator(mode="after")
    def require_creds_if_enabled(self) -> "SmsConfig":
        """Gate: sms.enabled=true without TWILIO_* env vars raises at startup (NOTIF-06)."""
        if self.enabled:
            missing = [
                v for v in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM")
                if not os.environ.get(v)
            ]
            if missing:
                raise ValueError(
                    f"notifications.sms.enabled=true requires environment variables: "
                    f"{', '.join(missing)}"
                )
        return self


class NotificationsConfig(BaseModel):
    """Notification channel config. Sound is on by default; all network channels off."""

    sound: bool = True
    discord: DiscordConfig = DiscordConfig()
    email: EmailConfig = EmailConfig()
    sms: SmsConfig = SmsConfig()


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
    notifications: NotificationsConfig = NotificationsConfig()

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
