import importlib
import yaml
import pytest


@pytest.fixture
def sample_config(tmp_path, monkeypatch):
    config_content = {
        "app": {
            "amz_email": "your_amazon_email@example.com",
            "amz_pwd": "your_amazon_password",
            "bb_email": "your_bestbuy_email@example.com",
            "bb_password": "your_bestbuy_password",
            "bb_cvv": "your_bestbuy_cvv",
            "open_browser": False,
        },
        "debug": {"test_mode": False},
        "available": {
            "timeout": 10,
            "short_url": True,
            "alert_type": "mp3",
            "items": [
                {
                    "name": "Magic: The Gathering - Final Fantasy Play Booster Box (30 Packs)",
                    "link": "https://www.amazon.com/Magic-Gathering-Final-Fantasy-Booster/dp/B0DTMQBLSY",
                    "type": "card_mtg",
                    "auto_buy": True,
                    "quantity": 2,
                }
            ],
        },
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(config_content))
    monkeypatch.chdir(tmp_path)
    return config_file


def test_load_config(sample_config):
    import config as config_module
    importlib.reload(config_module)
    cfg = config_module.load_config()
    assert cfg["app"]["amz_email"] == "your_amazon_email@example.com"
    assert (
        cfg["available"]["items"][0]["name"]
        == "Magic: The Gathering - Final Fantasy Play Booster Box (30 Packs)"
    )
