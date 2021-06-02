# ShopPyBot [![discord](https://img.shields.io/discord/136001983852052480.svg?label=&logo=discord&logoColor=ffffff&color=7389D8&labelColor=6A7EC2)](https://clan.bravebearstudios.com)  [![Tips](https://img.shields.io/badge/Donate-PayPal-green.svg)](paypal.me/BraveBearStudios)

*master*
![Linux](https://github.com/thezoid/ShopPyBot/actions/workflows/app_linuxBuild.yml/badge.svg?branch=master)
![Mac](https://github.com/thezoid/ShopPyBot/actions/workflows/app_macBuild.yml/badge.svg?branch=master)
![Windows](https://github.com/thezoid/ShopPyBot/actions/workflows/app_windowsBuild.yml/badge.svg?branch=master)

*dev*
![Linux](https://github.com/thezoid/ShopPyBot/actions/workflows/app_linuxBuild.yml/badge.svg?branch=dev)
![Mac](https://github.com/thezoid/ShopPyBot/actions/workflows/app_macBuild.yml/badge.svg?branch=dev)
![Windows](https://github.com/thezoid/ShopPyBot/actions/workflows/app_windowsBuild.yml/badge.svg?branch=dev)

A Python based system to 1) attempt to purchase an item from a link; and 2) check the availability of a list of items. This project takes advantage of the systems provided through Selenium in order to interact with shop web pages. This (as of writing) does not integrate with any shop APIs.

### Disclaimer

WARNING: The use of this software can result in a Amazon restricting access to your account and make it difficultfor you to purchase products, with or without the bot. By using this software, you acknowledge these risks. These restrictions cannot and will not be resolved by the developer(s). If this is a major issue you should consider avoiding use of this software.

Account restrictions may be triggered by any of the following: 1) running multiple instances on one device, 2) running multiple instances on different devices, using the same account, regardless of their IP, proxy, or location, 3) configuring an instance to check stock too frequently/aggressively (default settings not guaranteed to be safe).

## Supported sites

- [x] Best Buy
- [x] Amazon
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

### Best Buy

- A BestBuy account ([create one](https://www.bestbuy.com/identity/global/createAccount)) with a saved [payment method](https://www.bestbuy.com/profile/c/billinginfo/cc) (credit card)

### Amazon

- A valid Amazon account (presave your [address](https://smile.amazon.com/a/addresses) and [payment method](https://smile.amazon.com/cpe/yourpayments/wallet)!)
- Your OTP device on hand (manual login required)

## How to Use

1. Make sure you have all the listed requirements above installed on your machine.
     - Windows users can execute the supplied `installDependencies.ps1` script to walk through the requirements setup process
2. Customize `settings.json` to include all of your appropriate information. Use the tables below if you are unsure of what values you should use.
3. Run `bot.py` or `bot-availCheck.py` through your favorite method
     - *NOTE:* It is recommended to run this through the command line to more easily observe any output that may come up

### Link Processor

To make the population of links for the availability check easier to process, modify `data.csv` such that each line is a pair of `item name, link to BestBuy item`. Once you have all your new items accounted for, run `processor.ps1` to generate new content in `out.json`. Copy and paste the contents of the `data` array inside of `out.json` to the `items` array in the `available` `settings.json` section.

## Customization

Before putting the bot to work, you need to configure `settings.json` so that the scripts will function correctly. Be sure not to commit or otherwise save your sensitive information in a public place (email, password, cvv, etc.). Non-GPU items from BestBuy should work but it is not guranteed.

OOtB the availability bot has a long list of RTX 30 series cards available on Best Buy; however, you will need to check the validity of this list to ensure your checks are up to date.

### Debug

|Key|Description| Default |
| --- | --- | --- |
|loggingLevel|Set the level of logging in the bot script such that <br><ul><li>`0 = SILENT`</li><li>`1 = ERROR`</li><li>`2 = WARNING`</li><li>`3 = INFO`</li></ul>| 3 |
|testMode|Set to false to allow purchases to trigger, otherwise leave to true| true |


<br>

### App

|Key|Description| Default |
| --- | --- | --- |
|timeout|The timeout used in the Selenium driver for actions| 10 |
|alertType|The media type the alert file currently is (`alert_buy`). **Must be `mp3` or `wav`**|`wav`|
|amz_email*| your email for your Amazon account | *N/A* |
|amz_pwd*| your password for your Amazon account | *N/A* |
|bb_email*| your email for your Best Buy account | *N/A* |
|bb_password*| your password for your Best Buy account | *N/A* |
|bb_cvv*| your security code for your Best Buy saved payment method | *N/A* |
|item | a link to the item of which you want to automate purchasing | *N/A* |
|queueExists| represents whether the item being purchased is part of a queue system - **queue system requires manual input for final checkout** | true |

<br>

****If you update these in your settings, please do not commit it to your local repository! I do not take responsibility for any PII that may leak through your commits!***

### Available

|Key|Description| Default |
| --- | --- | --- |
|timeout|The timeout used in the Selenium driver for actions| 10 |
|alertType|The media type the alert file currently is (`alert_available`). **Must be `mp3` or `wav`**|`wav`|
|openNewBrowser|Wheter to open a new browser window when an available item is found (uses default browser)| false |
|shortURL|Whether the link presented in the console for will be a TinyURL link or the full shop link|true|
|items|A list of items to check for availability. Must be presented as `{"name":"item name","link":"link to the item","type":"category of product"}`| N/A |

<br>

### Changing the Alert Sound

The included alert sound can be changed to any other `.wav` file. Simply put the new `.wav.` file in the `sounds` folder and rename it to `alert.wav`. The process is similar if you would like to use a `.mp3` instead. Be sure to change the alertType value `alertType` to either `mp3` or `wav`. No other types are supported at this time.

## Support

Join my [Discord](https://clan.bravebearstudios.com) and join the Programmer's Parlor. #code-talk can be used to discuss this project, and code in general. Assistance may be provided on a case by case instance; however no offical or 24/7 support will be provided. **Do not** ping mods or admins for assitance for code.

## Credits

[wav Alert sound](https://opengameart.org/content/picked-coin-echo-2) - NenandSimic
