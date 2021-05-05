# ShopPyBot

A quick python project to try to grab targetted items in the competitive resellers market.

## Supported sites
- [x] Best Buy
- [ ] Amazon
- [ ] Newegg
## Requirements

- [Python](https://www.python.org/downloads/)
- Selenium
     - `pip install selenium`
- Playsound
     - `pip install playsound`
- [Google Chrome](https://chrome.google.com)
- [ChromeDriver](https://chromedriver.chromium.org/downloads)
     - Drop this in the same directory as `bot.py`

## How to Use

1. Make sure you have all the listed requirements above installed on your machine
2. Customize `settings.json` to include all of your appropriate information. Use the tables below if you are unsure of what settings you should use.
## Customizing `settings.json`

### Debug

|Key|Description| Default |
| --- | --- | --- |
|loggingLevel|Set the level of logging in the bot script such that 0 = SILENT, 1 = ERROR, 2 = WARNING, 3 = INFO| 3 |
|testMode|Set to false to allow purchases to trigger, otherwise leave to true| true |

### App

|Key|Description| Default |
| --- | --- | --- |
|delay|The delay used in the Selenium driver for actions| 0.5 |
|email| your email for your Best Buy account | *N/A* |
|password| your password for your Best Buy account | *N/A* |
|cvv| your security code for your Best Buy saved payment method | *N/A* |
|item | a link to the item of which you want to automate purchasing | *N/A* |

### Available

|Key|Description| Default |
| --- | --- | --- |
|delay|The delay used in the Selenium driver for actions| 0.5 |
|items|A list of items to check for availability. Must be presented as {"name":"item name","link":"link to the item"}| A hand gathered list of all the BestBuy RTX 3080/3070 offerings|

## Credits

[Alert sound](https://opengameart.org/content/picked-coin-echo-2) - NenandSimic