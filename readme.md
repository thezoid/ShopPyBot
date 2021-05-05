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
  - Drop this in the same directory as `bot.py` and `bot-availCheck.py`
- A BestBuy account ([create one](https://www.bestbuy.com/identity/global/createAccount)) with a saved [payment method](https://www.bestbuy.com/profile/c/billinginfo/cc) (credit card)

## How to Use

1. Make sure you have all the listed requirements above installed on your machine.
     - Windows users can execute the supplied `installDependencies.ps1` script to walk through the requirements setup process
2. Customize `settings.json` to include all of your appropriate information. Use the tables below if you are unsure of what values you should use.
3. Run `bot.py` or `bot-availCheck.py` through your favorite method
     - *NOTE:* It is recommended to run this through the command line to more easily observe any output that may come up

### Link Processor

To make the population of links for the availability check easier to process, modify `data.csv` such that each line is a pair of `item name, link to BestBuy item`. Once you have all your new items accounted for, run `processor.ps1` to generate new content in `out.json`. Copy and paste the contents of the `data` array inside of `out.json` to the `items` array in the `available` `settings.json` section.

## Customizing `settings.json`

Before putting the bot to work, you need to configure `settings.json` so that the scripts will function correctly. Be sure not to commit or otherwise save your sensitive information in a public place (email, password, cvv, etc.). Non-GPU items from BestBuy should work but it is not guranteed.

OOtB the availability bot has a long list of RTX 30 series cards available on Best Buy; however, you will need to check the validity of this list to ensure your checks are up to date.

### Debug

|Key|Description| Default |
| --- | --- | --- |
|loggingLevel|Set the level of logging in the bot script such that `0 = SILENT`, `1 = ERROR`, `2 = WARNING`, `3 = INFO`| 3 |
|testMode|Set to false to allow purchases to trigger, otherwise leave to true| true |

### App

|Key|Description| Default |
| --- | --- | --- |
|timeout|The timeout used in the Selenium driver for actions| 10 |
|email*| your email for your Best Buy account | *N/A* |
|password*| your password for your Best Buy account | *N/A* |
|cvv*| your security code for your Best Buy saved payment method | *N/A* |
|item | a link to the item of which you want to automate purchasing | *N/A* |
|queueExists| represents whether the item being purchased is part of a queue system - !!!queue system requires manual input for checkout!!! | true |

****If you update these in your settings, please do not commit it to your local repository! I do not take responsibility for any PII that may leak through your commits!***
### Available

|Key|Description| Default |
| --- | --- | --- |
|timeout|The timeout used in the Selenium driver for actions| 10 |
|items|A list of items to check for availability. Must be presented as `{"name":"item name","link":"link to the item"}`| N/A |

## Support

No support is currently provided.

## Credits

[Alert sound](https://opengameart.org/content/picked-coin-echo-2) - NenandSimic
