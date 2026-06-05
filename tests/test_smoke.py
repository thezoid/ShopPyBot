"""Env-independent import + CLI smoke tests (XPLAT-02).

Proves the package imports cleanly and the safe CLI commands (--help, items list,
config show) run without error on any OS. No real browser, keyring, or audio device
is touched.

SHOPBOT_DATA_DIR is redirected to a temp dir so no writes land in the real user
data directory. PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring prevents any
D-Bus/SecretService probe (headless-safe). SDL_AUDIODRIVER=dummy prevents pygame
audio init failure on CI. SHOPBOT_STORE_PASSPHRASE=x causes the EncryptedFileBackend
to be selected (safe: no interactive prompt, no real secrets).
"""

import os
import sys
import subprocess


# ---------------------------------------------------------------------------
# Helper: build a headless subprocess env from a given temp dir path.
# ---------------------------------------------------------------------------

def _headless_env(data_dir: str) -> dict:
    return {
        **os.environ,
        "SHOPBOT_DATA_DIR": data_dir,
        "SHOPBOT_STORE_PASSPHRASE": "x",
        "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring",
        "SDL_AUDIODRIVER": "dummy",
    }


# ---------------------------------------------------------------------------
# test_import_smoke: all top-level modules import without exception
# ---------------------------------------------------------------------------


def test_import_smoke():
    """All top-level modules import without exception."""
    import core.service   # noqa: F401
    import core.paths     # noqa: F401
    import models         # noqa: F401
    import logger         # noqa: F401


# ---------------------------------------------------------------------------
# test_help_smoke: shoppybot --help exits 0
# ---------------------------------------------------------------------------


def test_help_smoke(tmp_path):
    """python -m core.service --help exits 0."""
    result = subprocess.run(
        [sys.executable, "-m", "core.service", "--help"],
        capture_output=True,
        text=True,
        env=_headless_env(str(tmp_path)),
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# test_items_list_smoke: shoppybot items list exits 0 on an initialised DB
# ---------------------------------------------------------------------------


def test_items_list_smoke(tmp_path):
    """items list exits 0 with a fresh (empty) initialised DB."""
    # Initialize the DB first so 'items list' has a table to query.
    # This mirrors real usage: main.py / BotService.__init__ calls
    # initialize_db() before any item queries. The smoke proves the
    # CLI dispatch + DB query path works end-to-end without error.
    script = (
        "import os; os.environ['SHOPBOT_DATA_DIR'] = r'" + str(tmp_path) + "';"
        "import models; models.initialize_db();"
        "from core.service import main; main(['items', 'list'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=_headless_env(str(tmp_path)),
    )
    assert result.returncode == 0, (
        f"items list exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# test_config_show_smoke: shoppybot config show exits 0
# ---------------------------------------------------------------------------


def test_config_show_smoke(tmp_path):
    """config show exits 0 against a minimal config.yml in a temp dir."""
    import yaml

    # Write a minimal valid config so AppConfig() loads cleanly.
    cfg_data = {
        "debug": {"logging_level": 3, "test_mode": True},
        "available": {"timeout": 10, "items": []},
        "platforms": {
            "amazon": {"delay_seconds": 30.0},
            "bestbuy": {"delay_seconds": 30.0},
        },
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(cfg_data))

    # Initialize the DB so BotService() -> init_store doesn't trip on a
    # missing data dir, and config show can complete cleanly.
    script = (
        "import os; os.environ['SHOPBOT_DATA_DIR'] = r'" + str(tmp_path) + "';"
        "import models; models.initialize_db();"
        "from core.service import main; main(['config', 'show'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=_headless_env(str(tmp_path)),
    )
    assert result.returncode == 0, (
        f"config show exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
