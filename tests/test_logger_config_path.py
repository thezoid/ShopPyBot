"""TD-1 regression tests: logger reads logging_level from core.paths.config_path().

These tests verify that after Phase 12-01, logger._LOGGING_LEVEL honours the
config.yml found at the migrated data directory (SHOPBOT_DATA_DIR), not the
repo-root config.yml that no longer exists after path migration.

Pitfall 1 compliance: SHOPBOT_DATA_DIR is set via monkeypatch BEFORE the
importlib.reload() call so core.paths.config_path() resolves the correct file.
"""

import importlib
import yaml
import logger


def test_migrated_config_logging_level_honoured(monkeypatch, tmp_path):
    """Positive: logging_level in migrated config.yml is respected after reload."""
    # Write a config.yml with a non-default logging_level into the temp data dir.
    cfg = {"debug": {"logging_level": 2}}
    (tmp_path / "config.yml").write_text(yaml.dump(cfg))

    # Apply the env override BEFORE the reload (Pitfall 1).
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))

    try:
        importlib.reload(logger)
        assert logger._LOGGING_LEVEL == 2, (
            f"Expected _LOGGING_LEVEL=2 from migrated config; got {logger._LOGGING_LEVEL}"
        )
    finally:
        # Restore the module to its original import-time state so bleed is prevented.
        monkeypatch.delenv("SHOPBOT_DATA_DIR", raising=False)
        importlib.reload(logger)


def test_missing_config_falls_back_to_default(monkeypatch, tmp_path):
    """Negative: no config.yml at the migrated path falls back to level 5."""
    # tmp_path is empty — no config.yml present.
    monkeypatch.setenv("SHOPBOT_DATA_DIR", str(tmp_path))

    try:
        importlib.reload(logger)
        assert logger._LOGGING_LEVEL == 5, (
            f"Expected _LOGGING_LEVEL=5 (fallback); got {logger._LOGGING_LEVEL}"
        )
    finally:
        monkeypatch.delenv("SHOPBOT_DATA_DIR", raising=False)
        importlib.reload(logger)
