import os
import pytest


@pytest.fixture
def clean_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("SHOPBOT_"):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


@pytest.fixture
def tmp_config_yml(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        "selenium:\n  driver_path: ./chromedriver.exe\n"
        "debug:\n  logging_level: 3\n  test_mode: true\n"
        "open_browser: false\n"
        "platforms:\n  amazon:\n    enabled: true\n    credentials:\n      email: ''\n      password: ''\n"
        "available:\n  items: []\n"
    )
    monkeypatch.chdir(tmp_path)
    return cfg
