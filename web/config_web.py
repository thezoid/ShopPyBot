"""web/config_web.py: config read/write helpers for the web UI.

Mirrors the CLI config_cmd ALLOWLIST pattern and reuses _atomic_yaml_write
from core/cli/config_cmd.py (no duplication).
"""

import yaml

from core.cli.config_cmd import ALLOWLIST, _atomic_yaml_write
from core.config_schema import _DEFAULT_YAML_PATH

# Extended allowlist: CLI scalar keys + per-notifier enable toggles.
# Platforms have no 'enabled' field in AppConfig -- notifiers only (config-scope note).
#
# notifications.sound is a scalar bool on NotificationsConfig, NOT a nested section.
# It uses a 2-tuple (section, type) so the write path emits {"sound": true/false}.
# The nested notifier toggles (discord/email/sms) use 3-tuples (section, sub_key, type).
WEB_ALLOWLIST: dict = {
    **ALLOWLIST,  # "test_mode" and "logging_level"
    "notifications.sound": ("notifications", bool),
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

    2-tuple entries (section, type): write data[section][leaf] = coerced.
    3-tuple entries (section, sub_key, type): write data[section][sub_key][leaf] = coerced.
    Leaf is always key.split('.')[-1] for both branches (WR-05).

    Raises KeyError if the key is not in WEB_ALLOWLIST.
    Raises ValueError on type coercion failure.

    MOD-02 accepted design gap (TD-4, v2.0 audit):
    This function writes config directly to _DEFAULT_YAML_PATH rather than routing through
    a BotService write API. This is an accepted gap within the letter of MOD-02 (BotService
    is scoped to DB/registry/orchestrator operations, not arbitrary config file writes).
    The WEB_ALLOWLIST key gate provides the safety boundary. A regression test in
    tests/test_web_config.py documents and enforces this direct write seam (TD-4 config).
    """
    entry = WEB_ALLOWLIST[key]  # KeyError if unknown
    section = entry[0]
    coerced = _coerce_web(value, entry[-1])
    leaf = key.split(".")[-1]

    try:
        raw = _DEFAULT_YAML_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        raw = ""
    data = yaml.safe_load(raw) or {}

    if len(entry) == 2:
        # CLI-style scalar: section.leaf (e.g. debug.test_mode, notifications.sound)
        data.setdefault(section, {})[leaf] = coerced
    else:
        # Nested notifier toggle: section.sub_key.leaf (e.g. notifications.discord.enabled)
        sub_key = entry[1]
        data.setdefault(section, {}).setdefault(sub_key, {})[leaf] = coerced

    _atomic_yaml_write(_DEFAULT_YAML_PATH, data)
