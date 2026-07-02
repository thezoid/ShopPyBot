# ShopPyBot

![CI](https://github.com/thezoid/ShopPyBot/actions/workflows/ci.yml/badge.svg?branch=master)
![CodeQL](https://github.com/thezoid/ShopPyBot/actions/workflows/codeql-analysis.yml/badge.svg?branch=master)
![Gitleaks](https://github.com/thezoid/ShopPyBot/actions/workflows/gitleaks.yml/badge.svg?branch=master)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

## Overview
ShopPyBot is a drop-in plugin framework that monitors item availability and can automatically purchase across 7 retail platforms: Amazon, BestBuy, Walmart, Target, GameStop, NewEgg, and Square Enix. Community contributors can add support for a new platform by dropping a single plugin file into `plugins/` — no changes to the core framework required.

### Disclaimer

This software is provided for personal, non-commercial use only. It is offered "as is", without warranty of any kind, express or implied. You use it entirely at your own risk.

Automated availability checking and purchasing may violate the Terms of Service (TOS) of Amazon, BestBuy, or any other retailer. By using this software you acknowledge that you are solely responsible for ensuring your use complies with each retailer's Terms of Service and applicable law. The developer(s) accept no liability for any consequences arising from its use.

WARNING: The use of this software can result in a retailer restricting or suspending access to your account, banning your account, or otherwise making it difficult for you to purchase products, with or without the bot. By using this software, you acknowledge and accept these risks. These restrictions cannot and will not be resolved by the developer(s). If this is a major concern for you, you should avoid using this software.

Account restrictions may be triggered by any of the following: 1) running multiple instances on one device, 2) running multiple instances on different devices, using the same account, regardless of their IP, proxy, or location, 3) configuring an instance to check stock too frequently/aggressively (default settings not guaranteed to be safe).

## Features

- **Plugin framework** — add a new retail platform via a single file in `plugins/`, no core changes required
- Automated availability checks and automated purchasing across all 7 supported platforms (Amazon, BestBuy, Walmart, Target, GameStop, NewEgg, Square Enix)
- **Optional web dashboard** (`pip install -e .[web]`) with observability: a live status stream (Server-Sent Events), a health surface, and log filtering by plugin and level
- **Price monitoring** — alert or auto-buy on a target price or a percentage price drop
- **Anti-detection** — fingerprint and proxy rotation, plus 2captcha-backed CAPTCHA solving
- **Encrypted session persistence** (Fernet + scrypt) so logins survive restarts
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

2. Edit `config.yml` to add the items you want to monitor. `config.yml` holds only non-secret item and behavior settings — it never holds account credentials.

3. Account credentials go in environment variables, never in `config.yml`. Copy `.env.example` to `.env` and populate your platform credentials there; `.env` is gitignored and must never be committed. See [SECURITY.md](SECURITY.md#credentials-and-secrets) for the full credential-handling policy.

****If you update `config.yml`, please do not commit it to your local repository! I do not take responsibility for any PII or other sensitive data that may leak through your commits!***

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

[Final Fantasy 14 Sound Fan Kit](https://na.finalfantasyxiv.com/lodestone/special/fankit/smartphone_ringtone/) - Square Enix