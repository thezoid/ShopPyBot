import pytest
import yaml


@pytest.fixture
def tmp_config_yml(tmp_path):
    """Write a minimal valid config.yml to tmp_path and return its Path."""
    cfg = {
        "debug": {"logging_level": 3, "test_mode": True},
        "available": {"timeout": 10, "items": []},
        "platforms": {
            "amazon": {"delay_seconds": 30.0},
            "bestbuy": {"delay_seconds": 30.0},
        },
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(cfg))
    return config_file


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect models.DB_PATH to a temp directory so tests don't need data/."""
    import models
    monkeypatch.setattr(models, "DB_PATH", str(tmp_path / "shop_py_bot.db"))
    return tmp_path
