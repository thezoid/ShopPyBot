"""Source-grep smoke tests for main.py integration invariants (Plan 01-06)."""
import pathlib


def _src():
    return pathlib.Path("main.py").read_text(encoding="utf-8")


def test_no_stdout_monkey_patch():
    assert "sys.stdout = open(os.devnull" not in _src(), "INFRA-03"


def test_no_stderr_monkey_patch():
    assert "sys.stderr = open(os.devnull" not in _src(), "INFRA-03"


def test_imports_appconfig():
    assert "from config_schema import AppConfig" in _src()


def test_imports_build_driver():
    assert "from driver import build_driver" in _src()


def test_imports_collect_cvvs():
    assert "from credentials import collect_cvvs" in _src()


def test_imports_configure_logger():
    assert "from logger import configure" in _src(), "logger.configure must be imported"


def test_python_version_guard():
    src = _src()
    assert "sys.version_info < (3, 11)" in src
    assert "3.11+" in src or "3.11" in src


def test_no_old_app_credential_reads():
    forbidden = [
        "config['app']['bb_email']",
        "config['app']['bb_password']",
        "config['app']['bb_cvv']",
        "config['app']['amz_email']",
        "config['app']['amz_pwd']",
    ]
    for fname in ("main.py", "amazon_bot.py", "bestbuy_bot.py"):
        src = pathlib.Path(fname).read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in src, f"{fname} still contains {needle!r}"
