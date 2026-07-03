import builtins
import contextvars
import re

import logger

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)


def _run_isolated(fn):
    """Run fn in a fresh copied context so a set_log_plugin() call inside fn
    never leaks into the caller's (module/test-session) context."""
    contextvars.copy_context().run(fn)


def test_no_config_reread(monkeypatch):
    """writeLog must not re-open config.yml; the level is cached at import."""
    real_open = builtins.open
    counter = {"config_opens": 0}

    def counting_open(file, *args, **kwargs):
        if "config.yml" in str(file):
            counter["config_opens"] += 1
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", counting_open)

    for _ in range(3):
        logger.writeLog("msg", "INFO", writeTofile=False)

    assert counter["config_opens"] == 0, (
        f"writeLog re-read config.yml {counter['config_opens']} times; expected 0"
    )


def test_writeLog_tags_line_with_active_plugin(capsys):
    """FC-01: set_log_plugin("amazon") injects [amazon] as the second bracket."""
    def _run():
        logger.set_log_plugin("amazon")
        logger.writeLog("hi", "INFO", writeTofile=False)

    _run_isolated(_run)
    line = _strip_ansi(capsys.readouterr().out)
    assert "[INFO][amazon]" in line
    assert line.startswith("[INFO]")


def test_writeLog_sentinel_when_no_plugin_active(capsys):
    """FC-01: no set_log_plugin() call in this context -> [core] sentinel."""
    def _run():
        logger.writeLog("boot", "INFO", writeTofile=False)

    _run_isolated(_run)
    line = _strip_ansi(capsys.readouterr().out)
    assert "[core]" in line
    assert line.startswith("[INFO]")


def test_writeLog_format_compat_level_first_bracket(capsys):
    """FC-01: level bracket stays first -- read_logs_filtered + dashboard regex depend on this."""
    def _run():
        logger.set_log_plugin("bestbuy")
        logger.writeLog("hi", "INFO", writeTofile=False)

    _run_isolated(_run)
    line = _strip_ansi(capsys.readouterr().out)
    assert line.startswith("[INFO]")
    match = re.match(r"^\[(\w+)\]", line)
    assert match is not None
    assert match.group(1) == "INFO"


def test_set_log_plugin_falsy_coerces_to_core(capsys):
    """FC-01: set_log_plugin(None) / set_log_plugin("") both coerce to the core sentinel."""
    def _run_none():
        logger.set_log_plugin(None)
        logger.writeLog("a", "INFO", writeTofile=False)

    def _run_empty():
        logger.set_log_plugin("")
        logger.writeLog("b", "INFO", writeTofile=False)

    _run_isolated(_run_none)
    line_none = _strip_ansi(capsys.readouterr().out)
    assert "[core]" in line_none

    _run_isolated(_run_empty)
    line_empty = _strip_ansi(capsys.readouterr().out)
    assert "[core]" in line_empty


def test_writeLog_level_gate_unchanged(monkeypatch, capsys):
    """FC-01: the level gate is untouched by the tag injection -- below-threshold emits nothing."""
    monkeypatch.setattr(logger, "_LOGGING_LEVEL", 0)
    logger.writeLog("should not appear", "TRACE", writeTofile=False)
    out = capsys.readouterr().out
    assert out == ""
