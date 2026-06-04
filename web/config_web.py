"""web/config_web.py: config read/write helpers for the web UI.

Mirrors the CLI config_cmd ALLOWLIST pattern and reuses _atomic_yaml_write
from core/cli/config_cmd.py (no duplication).
"""

import yaml

from core.cli.config_cmd import ALLOWLIST, _atomic_yaml_write
from core.config_schema import _DEFAULT_YAML_PATH

# Extended allowlist: CLI scalar keys + per-notifier enable toggles.
# Platforms have no 'enabled' field in AppConfig -- notifiers only (config-scope note).
# Notifier toggle entries use a 3-tuple: (section, nested_key, type).
WEB_ALLOWLIST: dict = {
    **ALLOWLIST,  # "test_mode" and "logging_level"
    "notifications.sound": ("notifications", "sound", bool),
    "notifications.discord.enabled": ("notifications", "discord", bool),
    "notifications.email.enabled": ("notifications", "email", bool),
    "notifications.sms.enabled": ("notifications", "sms", bool),
}


def read_web_config(svc) -> dict:
    """Return the current values for all WEB_ALLOWLIST keys.

    Reads from the live AppConfig via svc.get_config() so test overrides work.
    """
    cfg = svc.get_config()
    return {
        "test_mode": cfg.debug.test_mode,
        "logging_level": cfg.debug.logging_level,
        "notifications.sound": cfg.notifications.sound,
        "notifications.discord.enabled": cfg.notifications.discord.enabled,
        "notifications.email.enabled": cfg.notifications.email.enabled,
        "notifications.sms.enabled": cfg.notifications.sms.enabled,
    }


def _coerce_web(value: str, typ: type):
    """Coerce a string value to the target Python type for web config writes."""
    if typ is bool:
        if str(value).lower() in ("true", "1", "yes"):
            return True
        if str(value).lower() in ("false", "0", "no"):
            return False
        raise ValueError(f"Expected true/false, got: {value!r}")
    if typ is int:
        return int(value)
    return value


def write_web_config(key: str, value: str) -> None:
    """Write a single WEB_ALLOWLIST key to config.yml atomically.

    Raises KeyError if the key is not in WEB_ALLOWLIST.
    Raises ValueError on type coercion failure.
    """
    entry = WEB_ALLOWLIST[key]  # KeyError if unknown
    _, *path_parts, typ = entry if len(entry) == 3 else (*entry, str)
    # Rebuild full entry: ALLOWLIST entries are 2-tuples (section, type),
    # WEB_ALLOWLIST notifier entries are 3-tuples (section, sub_key, type).
    section = entry[0]
    coerced = _coerce_web(value, entry[-1])

    try:
        raw = _DEFAULT_YAML_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        raw = ""
    data = yaml.safe_load(raw) or {}

    if len(entry) == 2:
        # CLI-style: section.key (e.g. debug.test_mode)
        data.setdefault(section, {})[key] = coerced
    else:
        # Notifier-style: section.sub_key.enabled (e.g. notifications.discord)
        sub_key = entry[1]
        data.setdefault(section, {}).setdefault(sub_key, {})[key.split(".")[-1]] = coerced

    _atomic_yaml_write(_DEFAULT_YAML_PATH, data)
