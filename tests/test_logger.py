"""Contract tests for logger module (INFRA-02).

writeLog must NOT re-read config.yml on every call; level threshold is set
once via configure(level). Signature, type strings, and timestamp format are
preserved verbatim from the legacy logger.
"""
import builtins
import importlib
import pathlib


def test_no_yaml_import_in_source():
    src = pathlib.Path("logger.py").read_text()
    assert "import yaml" not in src, "INFRA-02: logger must not import yaml"
    assert "load_settings" not in src, "INFRA-02: per-call config load removed"


def test_writelog_does_not_open_config_yml(monkeypatch, capsys):
    import logger
    importlib.reload(logger)
    opened: list[str] = []
    realOpen = builtins.open

    def spyOpen(path, *a, **kw):
        opened.append(str(path))
        return realOpen(path, *a, **kw)

    monkeypatch.setattr("builtins.open", spyOpen)
    logger.configure(5)
    logger.writeLog("hello", "INFO", writeTofile=False)
    assert not any("config.yml" in p for p in opened), f"opened files: {opened}"


def test_configure_sets_threshold(capsys):
    import logger
    importlib.reload(logger)
    logger.configure(2)  # only ALWAYS, ERROR, WARNING, SUCCESS print
    logger.writeLog("debug-msg", "DEBUG", writeTofile=False)
    logger.writeLog("err-msg", "ERROR", writeTofile=False)
    out = capsys.readouterr().out
    assert "debug-msg" not in out
    assert "err-msg" in out


def test_writelog_preserves_format(capsys):
    import logger
    importlib.reload(logger)
    logger.configure(5)
    logger.writeLog("hello-world", "INFO", writeTofile=False)
    out = capsys.readouterr().out
    assert "[INFO]" in out
    assert "hello-world" in out
