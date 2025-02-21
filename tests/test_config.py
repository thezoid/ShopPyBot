import yaml
import pytest
from config import load_config

@pytest.fixture
def sample_config(tmp_path):
    config_content = """
    app:
      amz_email: "your_amazon_email@example.com"
      amz_pwd: "your_amazon_password"
      bb_email: "your_bestbuy_email@example.com"
      bb_password: "your_bestbuy_password"
      bb_cvv: "your_bestbuy_cvv"
      open_browser: false

    debug:
      test_mode: false

    available:
      timeout: 10
      short_url: true
      alert_type: mp3
      items:
        - name: "Magic: The Gathering - Final Fantasy Play Booster Box (30 Packs)"
          link: "https://www.amazon.com/Magic-Gathering-Final-Fantasy-Booster/dp/B0DTMQBLSY?ref_=ast_sto_dp"
          type: card_mtg
          auto_buy: true
          quantity: 2
    """
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_content)
    return config_file

def test_load_config(sample_config):
    config = load_config(sample_config)
    assert config['app']['amz_email'] == "your_amazon_email@example.com"
    assert config['available']['items'][0]['name'] == "Magic: The Gathering - Final Fantasy Play Booster Box (30 Packs)"