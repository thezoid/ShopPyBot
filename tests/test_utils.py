import pytest
from unittest.mock import MagicMock


def test_make_tiny(tmp_config_yml, monkeypatch):
    monkeypatch.chdir(tmp_config_yml.parent)

    import importlib
    import config as config_module
    importlib.reload(config_module)

    import main as main_module
    importlib.reload(main_module)

    mock_response = MagicMock()
    mock_response.text = "http://tinyurl.com/abc123"
    monkeypatch.setattr(main_module.requests, "get", lambda url: mock_response)

    short_url = main_module.make_tiny("https://www.example.com")
    assert short_url.startswith("http://tinyurl.com/")
