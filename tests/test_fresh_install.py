"""Fresh-install regression tests (MOD-01, MOD-03, CLI-01, CLI-03).

Milestone v2.0 audit found that the `shoppybot` console entry point
(core.service:main) never called initialize_db() -- only the legacy main.py
shim did. On a fresh install (no prior `python main.py` run), the items table
did not exist, so `shoppybot run`, `shoppybot items add`, and
`shoppybot items list` crashed with `sqlite3.OperationalError: no such table:
items`.

These tests reproduce the fresh-install case: they invoke the CLI through
core.service:main in a brand-new temp data dir WITHOUT pre-calling
initialize_db(). They MUST pass because main() now creates the items table
itself. Unlike test_smoke.py, they deliberately do NOT pre-seed the DB -- that
omission is the whole point of the regression.
"""

import os
import sys
import subprocess


def _headless_env(data_dir: str) -> dict:
    return {
        **os.environ,
        "SHOPBOT_DATA_DIR": data_dir,
        "SHOPBOT_STORE_PASSPHRASE": "x",
        "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring",
        "SDL_AUDIODRIVER": "dummy",
    }


def _run_cli(tmp_path, argv: list) -> subprocess.CompletedProcess:
    """Invoke core.service:main(argv) in a fresh subprocess with NO DB pre-init."""
    argv_literal = repr(list(argv))
    script = (
        "import os; os.environ['SHOPBOT_DATA_DIR'] = r'" + str(tmp_path) + "';"
        "from core.service import main; main(" + argv_literal + ")"
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=_headless_env(str(tmp_path)),
    )


def test_items_list_on_fresh_install(tmp_path):
    """`shoppybot items list` exits 0 on a fresh dir with no pre-created DB."""
    result = _run_cli(tmp_path, ["items", "list"])
    assert result.returncode == 0, (
        f"items list exited {result.returncode} on fresh install\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "no such table" not in result.stderr.lower()
    # main() must have created the DB file itself.
    assert (tmp_path / "shop_py_bot.db").exists(), "items table DB was not created by main()"


def test_items_add_then_list_on_fresh_install(tmp_path):
    """`shoppybot items add` then `items list` works on a fresh dir, no pre-init."""
    add = _run_cli(
        tmp_path,
        ["items", "add", "--name", "Test", "--url", "https://example.com/p", "--quantity", "2"],
    )
    assert add.returncode == 0, (
        f"items add exited {add.returncode} on fresh install\n"
        f"stdout: {add.stdout}\nstderr: {add.stderr}"
    )
    assert "no such table" not in add.stderr.lower()

    listed = _run_cli(tmp_path, ["items", "list"])
    assert listed.returncode == 0
    assert "Test" in listed.stdout, f"added item not listed\nstdout: {listed.stdout}"
