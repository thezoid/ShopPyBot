import sys
import os
import yaml
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from logger import setup_logger, writeLog
from amazon_bot import check_amazon_item, auto_buy_amazon_item,detect_captcha
from bestbuy_bot import check_bestbuy_item, auto_buy_bestbuy_item
from utils import play_notification_sound, play_buy_sound, play_available_sound
import webbrowser
from selenium.webdriver.chrome.options import Options
from models import initialize_db, add_items, get_items
from config import config

def get_chromedriver_path():
    writeLog("Entering get_chromedriver_path", "DEBUG")
    driver_path = config['selenium']['driver_path']
    if not os.path.exists(driver_path):
        writeLog(f"Chromedriver not found at {driver_path}. Trying to download the latest version.", "WARNING")
        driver_path = ChromeDriverManager().install()
        if not os.path.exists(driver_path):
            writeLog("Failed to download the latest Chromedriver. Exiting.", "ERROR")
            exit(1)
    writeLog(f"Chromedriver path: {driver_path}", "DEBUG")
    return driver_path

def make_tiny(url):
    writeLog(f"Creating tiny URL for {url}", "DEBUG")
    request_url = f'http://tinyurl.com/api-create.php?url={url}'
    response = requests.get(request_url)
    short_url = response.text
    writeLog(f"Tiny URL created: {short_url}", "DEBUG")
    return short_url

def load_config():
    with open('config.yml', 'r') as file:
        return yaml.safe_load(file)

def main():
     writeLog("Starting main function", "INFO")
     config = load_config()
     driver_path = get_chromedriver_path()
     service = Service(driver_path)

     # Set up Chrome options
     chromeOptions = Options()
     prefs = {
          "credentials_enable_service": False,
          "profile.password_manager_enabled": False,
          "autofill.profile_enabled": False,
          "autofill.credit_card_enabled": False
     }
     chromeOptions.add_experimental_option("prefs", prefs)
     chromeOptions.add_argument("--disable-blink-features=AutomationControlled")
     chromeOptions.add_argument("--disable-notifications")
     chromeOptions.add_argument("--disable-extensions")
     chromeOptions.add_argument("--disable-web-security")
     chromeOptions.add_argument("--disable-site-isolation-trials")
     chromeOptions.add_argument("--disable-infobars")
     chromeOptions.add_argument("--disable-save-password-bubble")
     chromeOptions.add_argument("--disable-translate")
     chromeOptions.add_argument("--disable-features=AutofillServerCommunication,PasswordManagerOnboarding,PasswordManagerSettings,PasswordManagerUI,PasswordManagerInBrowserSettings,PasswordManagerReauthentication,PasswordManagerAccountStorage,PasswordManager,PasswordAutofillPublicSuffixDomainMatching,PasswordAutofill,PasswordGeneration,PasswordImportExport,PasswordLeakDetection,PasswordReuseDetection,PasswordSave")

     # Suppress unwanted console output
     sys.stdout = open(os.devnull, 'w')
     sys.stderr = open(os.devnull, 'w')

     driver = webdriver.Chrome(service=service, options=chromeOptions)

     # Restore standard output and error streams
     sys.stdout = sys.__stdout__
     sys.stderr = sys.__stderr__

     # Initialize the database and add items from config
     initialize_db()
     items = [(item['name'], item['link'], item['auto_buy'], item['quantity'], False) for item in config['available']['items']]
     add_items(items)

     test_mode = config['debug'].get('test_mode', False)
     open_browser = config['app'].get('open_browser', False)

     while True:
          writeLog("Starting new iteration of item checks", "INFO")
          for item in get_items():
               name, link, auto_buy, quantity, purchased = item
               if purchased:
                    writeLog(f"{name} has already been purchased", "INFO")
                    continue
               if "amazon.com" in link:
                    writeLog(f"Checking availability for Amazon item: {name}", "INFO")
                    driver.get(link)
                    if detect_captcha(driver):
                         writeLog("CAPTCHA detected. Please solve it manually.", "WARNING")
                         play_notification_sound()
                         input("Press Enter after solving the CAPTCHA...")
                    available = check_amazon_item(driver, link)
                    if available:
                         play_available_sound()
                         short_url = make_tiny(link)
                         writeLog(f"{name} is available: {short_url}", "SUCCESS")
                         if auto_buy:
                              writeLog(f"Attempting to auto-buy {name} on Amazon", "INFO")
                              auto_buy_amazon_item(driver, link, config, quantity, test_mode)
                         else:
                              writeLog(f"{name} is available but auto-buy is disabled", "INFO")
                              if open_browser:
                                   writeLog(f"Opening browser for {name}", "INFO")
                                   webbrowser.open(link)
                    else:
                         writeLog(f"{name} is not available", "INFO")
               elif "bestbuy.com" in link:
                    writeLog(f"Checking availability for BestBuy item: {name}", "INFO")
                    available = check_bestbuy_item(driver, link)
                    if available:
                         play_available_sound()
                         short_url = make_tiny(link)
                         writeLog(f"{name} is available: {short_url}", "SUCCESS")
                         if auto_buy:
                              writeLog(f"Attempting to auto-buy {name} on BestBuy", "INFO")
                              if not test_mode:
                                   auto_buy_bestbuy_item(driver, link, config['app']['bb_email'], config['app']['bb_password'], config['app']['bb_cvv'], quantity)
                                   play_buy_sound()
                              else:
                                   writeLog(f"Test mode active: Skipping final purchase step", "INFO")
                         else:
                              writeLog(f"{name} is available but auto-buy is disabled", "INFO")
                              if open_browser:
                                   writeLog(f"Opening browser for {name}", "INFO")
                                   webbrowser.open(link)
                    else:
                         writeLog(f"{name} is not available", "INFO")
               else:
                    writeLog(f"Unsupported URL: {link}", "WARNING")

if __name__ == "__main__":
    logger = setup_logger()
    main()