"""handle_config_*: config subcommand (show/set) implementation.

Provides ALLOWLIST, _coerce, _atomic_yaml_write, handle_config_show, handle_config_set.
"""

import os
import sys
import tempfile
from pathlib import Path

import yaml

from core.config_schema import _DEFAULT_YAML_PATH

# Allowlist of scalar config keys that `config set` may update (RESEARCH Pattern 5).
# Maps key_name -> (yaml_section, python_type).
ALLOWLIST: dict[str, tuple[str, type]] = {
    "test_mode": ("debug", bool),
    "logging_level": ("debug", int),
}


def _coerce(raw: str, typ: type):
    """Coerce a CLI string value to the target Python type.

    Raises SystemExit(2) on invalid input (usage error convention).
    """
    if typ is bool:
        if raw.lower() in ("true", "1", "yes"):
            return True
        if raw.lower() in ("false", "0", "no"):
            return False
        print(f"Expected true/false, got: {raw!r}", file=sys.stderr)
        raise SystemExit(2)
    if typ is int:
        try:
            return int(raw)
        except ValueError:
            print(f"Expected integer, got: {raw!r}", file=sys.stderr)
            raise SystemExit(2)
    return raw


def _atomic_yaml_write(path: Path, data: dict) -> None:
    """Write data as YAML to path atomically via tempfile + os.replace.

    Mirrors EncryptedFileBackend._save() pattern (PATTERNS analog).
    """
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    dir_ = path.parent
    dir_.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dir_), suffix=".yml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def handle_config_show(args, svc=None) -> int:
    """Print the current effective config as YAML."""
    from core.service import BotService  # lazy import -- avoid construction at import time

    cfg = (svc or BotService()).get_config()
    print(yaml.dump(cfg.model_dump(), default_flow_style=False, allow_unicode=True))
    return 0


def handle_config_set(args, svc=None) -> int:
    """Update an allowlisted config key in config.yml atomically."""
    key = args.key
    if key not in ALLOWLIST:
        print(
            f"config set: '{key}' not in allowlist {list(ALLOWLIST)}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    section, typ = ALLOWLIST[key]
    value = _coerce(args.value, typ)
    if key == "logging_level" and not (0 <= value <= 5):
        print(
            f"config set: logging_level must be 0-5, got {value}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    try:
        raw = _DEFAULT_YAML_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        raw = ""
    data = yaml.safe_load(raw) or {}
    data.setdefault(section, {})[key] = value
    _atomic_yaml_write(_DEFAULT_YAML_PATH, data)
    print(f"Set {key} = {value}")
    return 0
