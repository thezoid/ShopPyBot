"""CLI-02 tests: setup subcommand (credentials + backend selection)."""

from unittest.mock import MagicMock, patch

import pytest


def test_setup_writes_credentials(tmp_data_dir, reset_credential_store, monkeypatch):
    """handle_setup prompts for each SECRET_KEY and writes via store.set()."""
    mock_store = MagicMock()
    with (
        patch("core.cli.setup.get_store", return_value=mock_store),
        patch("core.cli.setup.getpass.getpass", side_effect=["secret_val", ""]),
    ):
        from core.cli.setup import handle_setup

        args = MagicMock()
        args.migrate = False
        result = handle_setup(args, None)
    assert result == 0
    mock_store.set.assert_called()


def test_setup_no_secret_echo(
    tmp_data_dir, reset_credential_store, capsys, monkeypatch
):
    """stdout must never contain any secret value entered during setup."""
    mock_store = MagicMock()
    with (
        patch("core.cli.setup.get_store", return_value=mock_store),
        patch("core.cli.setup.getpass.getpass", return_value="MY_SECRET"),
    ):
        from core.cli.setup import handle_setup

        args = MagicMock()
        args.migrate = False
        handle_setup(args, None)
    out = capsys.readouterr().out
    assert "MY_SECRET" not in out


def test_enter_skips_key(tmp_data_dir, reset_credential_store, monkeypatch):
    """Pressing Enter (empty string) skips a key -- store.set() not called for it."""
    mock_store = MagicMock()
    with (
        patch("core.cli.setup.get_store", return_value=mock_store),
        patch("core.cli.setup.getpass.getpass", return_value=""),
    ):
        from core.cli.setup import handle_setup

        args = MagicMock()
        args.migrate = False
        result = handle_setup(args, None)
    assert result == 0
    mock_store.set.assert_not_called()


def test_setup_writes_backend(tmp_data_dir, reset_credential_store, tmp_path, monkeypatch):
    """handle_setup writes credentials.backend to config.yml."""
    import yaml

    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump({"debug": {"test_mode": True}}))

    mock_store = MagicMock()
    with (
        patch("core.cli.setup.get_store", return_value=mock_store),
        patch("core.cli.setup.getpass.getpass", return_value=""),
        patch("core.cli.config_cmd._DEFAULT_YAML_PATH", config_file),
    ):
        from core.cli.setup import handle_setup

        args = MagicMock()
        args.migrate = False
        handle_setup(args, None)

    data = yaml.safe_load(config_file.read_text())
    assert "credentials" in data


def test_setup_migrate(tmp_data_dir, reset_credential_store, monkeypatch):
    """handle_setup with --migrate flag calls migrate_from_env and prints key names."""
    mock_store = MagicMock()
    with (
        patch("core.cli.setup.get_store", return_value=mock_store),
        patch("core.cli.setup.migrate_from_env", return_value=["KEY_A", "KEY_B"]) as mock_migrate,
    ):
        from core.cli.setup import handle_setup

        args = MagicMock()
        args.migrate = True
        result = handle_setup(args, None)
    assert result == 0
    mock_migrate.assert_called_once_with(mock_store)
