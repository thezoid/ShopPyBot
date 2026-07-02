# ShopPyBot

![CI](https://github.com/thezoid/ShopPyBot/actions/workflows/ci.yml/badge.svg?branch=master)
![CodeQL](https://github.com/thezoid/ShopPyBot/actions/workflows/codeql-analysis.yml/badge.svg?branch=master)
![Gitleaks](https://github.com/thezoid/ShopPyBot/actions/workflows/gitleaks.yml/badge.svg?branch=master)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

## Overview
ShopPyBot is a bot designed to automate the process of checking availability and purchasing items from online stores like Amazon and BestBuy.

### Disclaimer

This software is provided for personal, non-commercial use only. It is offered "as is", without warranty of any kind, express or implied. You use it entirely at your own risk.

Automated availability checking and purchasing may violate the Terms of Service (TOS) of Amazon, BestBuy, or any other retailer. By using this software you acknowledge that you are solely responsible for ensuring your use complies with each retailer's Terms of Service and applicable law. The developer(s) accept no liability for any consequences arising from its use.

WARNING: The use of this software can result in a retailer restricting or suspending access to your account, banning your account, or otherwise making it difficult for you to purchase products, with or without the bot. By using this software, you acknowledge and accept these risks. These restrictions cannot and will not be resolved by the developer(s). If this is a major concern for you, you should avoid using this software.

Account restrictions may be triggered by any of the following: 1) running multiple instances on one device, 2) running multiple instances on different devices, using the same account, regardless of their IP, proxy, or location, 3) configuring an instance to check stock too frequently/aggressively (default settings not guaranteed to be safe).

## Features

- Automated availability checks
- Automated purchasing
- CAPTCHA detection and notification
- Configurable via `config.yml`
- Logging and error handling

## Setup

### Prerequisites

- Python 3.11+
- pip (Python package installer)

#### Best Buy

- A BestBuy account ([create one](https://www.bestbuy.com/identity/global/createAccount)) with a saved [payment method](https://www.bestbuy.com/profile/c/billinginfo/cc) (credit card)

#### Amazon

- A valid Amazon account (presave your [address](https://smile.amazon.com/a/addresses) and [payment method](https://smile.amazon.com/cpe/yourpayments/wallet)!)
- Your OTP device on hand (manual login required)

### Installation

1. Clone the repository:

```sh
git clone https://github.com/thezoid/ShopPyBot.git
cd ShopPyBot
```

2. Create and activate a virtual environment:

```sh
python -m venv .venv
.venv\Scripts\activate  # On Windows
source .venv/bin/activate  # On macOS/Linux
```

3. Install the project in editable mode with the `web` extra (FastAPI/uvicorn/jinja2, needed for the optional web dashboard):

```sh
pip install -e .[web]
```

This also registers the `shoppybot` console command (see [Running the Bot](#running-the-bot)).

## Configuration

1. Copy the sample configuration file and update it with your details:

```sh
cp sample.config.yml config.yml
```

2. Edit `config.ym`l to include your Amazon and BestBuy account details and the items you want to monitor.

****If you update these in your settings, please do not commit it to your local repository! I do not take responsibility for any PII or other sensitive data that may leak through your commits!***

### Changing the Alert Sound

The bundled alert sounds (`sounds/notification.wav`, `sounds/available.wav`, `sounds/buy.wav`) are original, royalty-free tones generated from scratch by `sounds/generate_alert_sounds.py` (public domain / CC0, no third-party samples). Regenerate them any time with:

```sh
python sounds/generate_alert_sounds.py
```

To use your own sounds, drop a file of the same name (`notification`, `available`, or `buy`) into `sounds/`. Both `.mp3` and `.wav` are supported; `utils.py` loads `.mp3` first, then falls back to `.wav`.

## Running the Bot

```sh
shoppybot
```

`shoppybot` is the console entry point registered by `pip install -e .[web]`. `python main.py` still works as an alternative if you prefer running from a source checkout directly.

## Contributing

Contributions are welcome! Please read the contributing guidelines for more information.

## Credits

[Final Fantasy 14 Sound Fan Kit]https://na.finalfantasyxiv.com/lodestone/special/fankit/smartphone_ringtone/) - Square Enix