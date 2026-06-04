"""CLI-03 tests: config subcommand (show/set)."""

import pytest
import yaml
from unittest.mock import MagicMock, patch


def test_config_show(capsys, tmp_data_dir):
    """config show prints the effective config as YAML."""
    from core.service import main

    mock_svc = MagicMock()
    mock_svc.get_config.return_value.model_dump.return_value = {
        "debug": {"test_mode": True, "logging_level": 5}
    }
    with patch("core.service.BotService", return_value=mock_svc):
        with pytest.raises(SystemExit) as exc_info:
            main(["config", "show"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "test_mode" in out or "debug" in out


def test_config_set_test_mode(tmp_path):
    """config set test_mode false writes False to config.yml."""
    cfg = {"debug": {"logging_level": 5, "test_mode": True}}
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(cfg))

    with patch("core.cli.config_cmd._DEFAULT_YAML_PATH", config_file):
        from core.cli.config_cmd import handle_config_set

        args_mock = type("A", (), {"key": "test_mode", "value": "false"})()
        result = handle_config_set(args_mock)

    data = yaml.safe_load(config_file.read_text())
    assert data["debug"]["test_mode"] is False
    assert result == 0


def test_config_set_logging_level(tmp_path):
    """config set logging_level 3 writes integer 3 to config.yml."""
    cfg = {"debug": {"logging_level": 5, "test_mode": True}}
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(cfg))

    with patch("core.cli.config_cmd._DEFAULT_YAML_PATH", config_file):
        from core.cli.config_cmd import handle_config_set

        args_mock = type("A", (), {"key": "logging_level", "value": "3"})()
        result = handle_config_set(args_mock)

    data = yaml.safe_load(config_file.read_text())
    assert data["debug"]["logging_level"] == 3
    assert result == 0


def test_config_set_invalid_key(tmp_path):
    """config set unknown_key exits with code 2."""
    from core.cli.config_cmd import handle_config_set

    args_mock = type("A", (), {"key": "unknown_key", "value": "x"})()
    with pytest.raises(SystemExit) as exc_info:
        handle_config_set(args_mock)
    assert exc_info.value.code == 2
