from __future__ import annotations

import os
import threading
import warnings
from pathlib import Path
from typing import Optional

from urllib.parse import urlparse as _urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from core.paths import config_path as _paths_config_path

# Absolute path to config.yml via core/paths.py (XPLAT-01)
_DEFAULT_YAML_PATH: Path = _paths_config_path()

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


def _shim_legacy_delay_fields(data: dict) -> dict:
    """Map legacy min_delay/max_delay -> canonical delay_seconds/delay_jitter (CFG-01).

    Only triggers when at least one legacy key is present AND neither canonical key
    is already present -- an explicit delay_seconds/delay_jitter value is NEVER
    clobbered by legacy keys, even if both are present in the same construction.

    Behavior-preserving: delay_seconds := min_delay, delay_jitter := max_delay - min_delay.
    Consumed as delay_seconds + random.uniform(0, delay_jitter), this is algebraically
    identical to the legacy random.uniform(min_delay, max_delay).

    NOTE (WR-01/IN-02): unlike the legacy random.uniform(min_delay, max_delay) call --
    which tolerated min_delay > max_delay and simply returned a value in the resulting
    range -- an inverted legacy range is now rejected with a ValueError naming
    min_delay/max_delay. This is a deliberate tightening, not a preserved behavior: the
    derived delay_jitter would otherwise be negative and fail the canonical field's own
    Field(ge=0.0) constraint with a confusing message about a field the user never set.
    """
    if not isinstance(data, dict):
        return data
    has_legacy = "min_delay" in data or "max_delay" in data
    has_canonical = "delay_seconds" in data or "delay_jitter" in data
    if has_legacy and not has_canonical:
        warnings.warn(
            "config.yml: 'min_delay'/'max_delay' are deprecated; use "
            "'delay_seconds'/'delay_jitter' instead. See sample.config.yml.",
            DeprecationWarning,
            stacklevel=2,
        )
        data = dict(data)
        # WR-03: these fallbacks are implicitly coupled to the 5 community models'
        # delay_seconds=8.0/delay_jitter=7.0 Field defaults (8.0 + 7.0 = 15.0). If a
        # future tuning pass changes those model defaults, update these two literals
        # to match -- see test_shim_legacy_fallback_defaults_match_community_model_defaults.
        min_d = float(data.pop("min_delay", 8.0))
        max_d = float(data.pop("max_delay", 15.0))
        if max_d < min_d:
            # WR-01: fail loudly and name the legacy fields the user actually set,
            # rather than letting this flow into delay_jitter's Field(ge=0.0) and
            # raise a ValidationError about a field the user never touched.
            raise ValueError(
                f"config.yml: legacy min_delay ({min_d}) must be <= max_delay "
                f"({max_d}): inverted delay range, fix your config so "
                "max_delay >= min_delay"
            )
        data["delay_seconds"] = min_d
        data["delay_jitter"] = max_d - min_d
    return data

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
    target_price: Optional[int] = None    # cents; NULL = monitoring off (PRICE-01)
    price_drop_pct: Optional[float] = None  # e.g. 10.0 = alert on 10%+ drop (PRICE-05)


class AvailableConfig(BaseModel):
    timeout: int = 10
    items: list[ItemConfig] = []


class DebugConfig(BaseModel):
    logging_level: int = 5
    test_mode: bool = True
    monitor_only: bool = False  # BUY-01: default False per CONTEXT.md


class AmazonPlatformConfig(BaseModel):
    # CFG-01: canonical delay field scheme for all 7 platforms (delay_seconds/delay_jitter).
    # Amazon/BestBuy already used these names; the five community platforms below were
    # renamed from min_delay/max_delay to match, with a back-compat shim (see
    # _shim_legacy_delay_fields) so legacy-named configs still load unchanged.
    delay_seconds: float = Field(default=30.0, ge=0.0)
    delay_jitter: float = Field(default=10.0, ge=0.0)
    # SC3: declared field so extra="ignore" does not silently drop it from YAML.
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)
    session_persistence: bool = False  # REL-04: opt-in encrypted cookie persistence (default off)


class BestBuyPlatformConfig(BaseModel):
    # NOTE: see AmazonPlatformConfig comment above on delay field naming.
    delay_seconds: float = Field(default=30.0, ge=0.0)
    delay_jitter: float = Field(default=10.0, ge=0.0)
    # SC3: declared field so extra="ignore" does not silently drop it from YAML.
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)
    session_persistence: bool = False  # REL-04: opt-in encrypted cookie persistence (default off)


class WalmartPlatformConfig(BaseModel):
    """Per-platform anti-detection config for Walmart (ANTI-01/02/03).

    CFG-01: canonical delay_seconds/delay_jitter. Legacy min_delay/max_delay configs
    still load via _shim_legacy_delay_fields (deprecated, back-compat).
    """

    delay_seconds: float = Field(default=8.0, ge=0.0)  # ANTI-01: base delay
    delay_jitter: float = Field(default=7.0, ge=0.0)   # ANTI-01: jitter width
    headless: bool = True                            # ANTI-03: per-platform headless toggle
    user_agents: list[str] = Field(default_factory=list)  # ANTI-02: empty = global default pool
    session_persistence: bool = False  # REL-04: opt-in encrypted cookie persistence (default off)

    @model_validator(mode="before")
    @classmethod
    def _legacy_delay_shim(cls, data):
        return _shim_legacy_delay_fields(data)


class TargetPlatformConfig(BaseModel):
    """Per-platform anti-detection config for Target (ANTI-01/02/03).

    CFG-01: canonical delay_seconds/delay_jitter. Legacy min_delay/max_delay configs
    still load via _shim_legacy_delay_fields (deprecated, back-compat).
    """

    delay_seconds: float = Field(default=8.0, ge=0.0)
    delay_jitter: float = Field(default=7.0, ge=0.0)
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)
    session_persistence: bool = False  # REL-04: opt-in encrypted cookie persistence (default off)

    @model_validator(mode="before")
    @classmethod
    def _legacy_delay_shim(cls, data):
        return _shim_legacy_delay_fields(data)


class GameStopPlatformConfig(BaseModel):
    """Per-platform anti-detection config for GameStop (ANTI-01/02/03).

    CFG-01: canonical delay_seconds/delay_jitter. Legacy min_delay/max_delay configs
    still load via _shim_legacy_delay_fields (deprecated, back-compat).
    """

    delay_seconds: float = Field(default=8.0, ge=0.0)
    delay_jitter: float = Field(default=7.0, ge=0.0)
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)
    session_persistence: bool = False  # REL-04: opt-in encrypted cookie persistence (default off)

    @model_validator(mode="before")
    @classmethod
    def _legacy_delay_shim(cls, data):
        return _shim_legacy_delay_fields(data)


class SquareEnixPlatformConfig(BaseModel):
    """Per-platform anti-detection config for Square Enix (ANTI-01/02/03).

    Config key: platforms.squareenix (no underscore) -- matches plugin platform_key="squareenix".
    CFG-01: canonical delay_seconds/delay_jitter. Legacy min_delay/max_delay configs
    still load via _shim_legacy_delay_fields (deprecated, back-compat).
    """

    delay_seconds: float = Field(default=8.0, ge=0.0)
    delay_jitter: float = Field(default=7.0, ge=0.0)
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)
    session_persistence: bool = False  # REL-04: opt-in encrypted cookie persistence (default off)

    @model_validator(mode="before")
    @classmethod
    def _legacy_delay_shim(cls, data):
        return _shim_legacy_delay_fields(data)


class NeweggPlatformConfig(BaseModel):
    """Per-platform anti-detection config for NewEgg (ANTI-01/02/03).

    CFG-01: canonical delay_seconds/delay_jitter. Legacy min_delay/max_delay configs
    still load via _shim_legacy_delay_fields (deprecated, back-compat).
    """

    delay_seconds: float = Field(default=8.0, ge=0.0)
    delay_jitter: float = Field(default=7.0, ge=0.0)
    headless: bool = True
    user_agents: list[str] = Field(default_factory=list)
    session_persistence: bool = False  # REL-04: opt-in encrypted cookie persistence (default off)

    @model_validator(mode="before")
    @classmethod
    def _legacy_delay_shim(cls, data):
        return _shim_legacy_delay_fields(data)


class PlatformsConfig(BaseModel):
    # CFG-02: unknown platform keys pass through as raw dicts instead of being
    # silently dropped (the default extra="ignore" behavior). A new plugin's
    # own model validates its section via RetailerPlugin.get_platform_config().
    # The 7 declared platform fields below keep full strict validation --
    # extra="allow" governs ONLY undeclared keys.
    model_config = ConfigDict(extra="allow")

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
        """Gate: sms.enabled=true without TWILIO_* env vars raises at startup (NOTIF-06).

        DELIBERATE os.environ exception: AppConfig() construction runs BEFORE init_store()
        can be called (init_store needs the constructed config). This validator is a
        startup presence check, not a runtime secret read. Do NOT migrate to get_store()
        here. See RESEARCH.md Pitfall 7.
        """
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


class CredentialsConfig(BaseModel):
    """Credential store config. Secrets are NEVER stored here (CRED-06).

    This section controls which backend the credential store uses and where the
    encrypted file lives. Actual secret values must come from the active backend
    (OS keyring, encrypted file, or env vars) -- never from config.yml.
    """

    backend: str = "auto"  # auto | keyring | file | env
    data_dir: str = ""     # empty = data/creds.bin (project-relative default)


class CaptchaConfig(BaseModel):
    """Opt-in CAPTCHA solving config (ANTI-06/07). Disabled by default.

    API key lives EXCLUSIVELY in CredentialStore (TWOCAPTCHA_API_KEY), never here.
    """

    enabled: bool = False
    max_solves_per_run: int = 10
    low_balance_threshold: float = 1.00


class ProxyConfig(BaseModel):
    """Opt-in proxy rotation config (ANTI-04). Disabled by default.

    Proxy URLs use scheme://[user:pass@]host:port format. Credential-bearing
    URLs are stored locally in config.yml (gitignored) and are never logged;
    only host:port appears in log output.
    """

    enabled: bool = False
    urls: list[str] = Field(default_factory=list)
    max_failures: int = 3
    cooldown_secs: float = 300.0

    @field_validator("urls", mode="before")
    @classmethod
    def validate_proxy_urls(cls, v):
        """WR-05 / CR-03: reject URLs missing scheme, hostname, or port at config load.

        A schemeless or portless URL would produce host_port='None:None', which Chrome
        ignores, silently causing a direct connection that leaks the real IP.
        """
        for url in v:
            parsed = _urlparse(url)
            if not parsed.scheme or not parsed.hostname or parsed.port is None:
                raise ValueError(
                    f"Invalid proxy URL {url!r}: must be scheme://[user:pass@]host:port"
                )
        return v


class CheckoutConfig(BaseModel):
    """Checkout timing and retry tuning. Consumed by Phases 21/22/24."""

    item_timeout_secs: int = Field(default=120, ge=1)
    step_timeout_secs: int = Field(default=30, ge=1)
    max_cart_retries: int = Field(default=3, ge=0)
    backoff_base: float = Field(default=2.0, ge=0.0)
    backoff_jitter: float = Field(default=0.5, ge=0.0)
    alert_on_errors: int = Field(default=3, ge=0)


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
    credentials: CredentialsConfig = CredentialsConfig()
    proxy: ProxyConfig = ProxyConfig()
    captcha: CaptchaConfig = CaptchaConfig()
    checkout: CheckoutConfig = CheckoutConfig()

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
