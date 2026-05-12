"""Contract tests for credentials.collect_cvvs (SEC-02, D-04, D-05)."""
import pytest
from types import SimpleNamespace


def _makeConfig(platformsWithAutoBuy):
    """Build a fake AppConfig with the given platform names enabled and auto_buy items."""
    items = [SimpleNamespace(auto_buy=True)] if platformsWithAutoBuy else []
    platforms = {
        name: SimpleNamespace(enabled=True)
        for name in platformsWithAutoBuy
    }
    return SimpleNamespace(
        platforms=platforms,
        available=SimpleNamespace(items=items),
    )


def test_no_platforms_returns_empty(clean_env):
    from credentials import collect_cvvs
    cfg = _makeConfig([])
    assert collect_cvvs(cfg) == {}


def test_cvv_prompt_once_per_platform(clean_env, monkeypatch):
    calls = []
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        "getpass.getpass",
        lambda prompt="": (calls.append(prompt) or "111"),
    )
    from credentials import collect_cvvs
    cfg = _makeConfig(["amazon", "bestbuy"])
    result = collect_cvvs(cfg)
    assert result == {"amazon": "111", "bestbuy": "111"}
    assert len(calls) == 2


def test_non_tty_without_optin_hard_fails(clean_env, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    from credentials import collect_cvvs
    cfg = _makeConfig(["amazon"])
    with pytest.raises(SystemExit) as exc:
        collect_cvvs(cfg)
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "TTY" in err
    assert "SHOPBOT_ALLOW_CVV_ENV" in err


def test_non_tty_with_optin_reads_env(clean_env, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setenv("SHOPBOT_ALLOW_CVV_ENV", "true")
    monkeypatch.setenv("SHOPBOT_AMAZON_CVV", "999")
    from credentials import collect_cvvs
    cfg = _makeConfig(["amazon"])
    assert collect_cvvs(cfg) == {"amazon": "999"}


def test_non_tty_with_optin_missing_env_exits(clean_env, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setenv("SHOPBOT_ALLOW_CVV_ENV", "true")
    from credentials import collect_cvvs
    cfg = _makeConfig(["amazon"])
    with pytest.raises(SystemExit) as exc:
        collect_cvvs(cfg)
    assert exc.value.code == 1
    assert "SHOPBOT_AMAZON_CVV" in capsys.readouterr().err


def test_empty_getpass_response_exits(clean_env, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "")
    from credentials import collect_cvvs
    cfg = _makeConfig(["amazon"])
    with pytest.raises(SystemExit) as exc:
        collect_cvvs(cfg)
    assert exc.value.code == 1
    assert "empty CVV" in capsys.readouterr().err
