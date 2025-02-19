import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from config import config
from logger import setup_logger, writeLog
from amazon_bot import check_amazon_item, auto_buy_amazon_item
from bestbuy_bot import check_bestbuy_item, auto_buy_bestbuy_item
from utils import play_notification_sound
import time

logger = setup_logger()

def get_chromedriver_path():
    driver_path = config['selenium']['driver_path']
    if not os.path.exists(driver_path):
        writeLog(f"Chromedriver not found at {driver_path}. Trying to download the latest version.", "WARNING")
        driver_path = ChromeDriverManager().install()
        if not os.path.exists(driver_path):
            writeLog("Failed to download the latest Chromedriver. Exiting.", "ERROR")
            exit(1)
    return driver_path

def make_tiny(url):
    request_url = f'http://tinyurl.com/api-create.php?url={url}'
    response = requests.get(request_url)
    return response.text

def main():
    driver_path = get_chromedriver_path()
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service)
    test_mode = config['debug'].get('test_mode', False)
    
    while True:
        for item in config['available']['items']:
            item_url = item['link']
            auto_buy = item.get('auto_buy', False)
            quantity = item.get('quantity', 1)
            
            try:
                if "amazon.com" in item_url:
                    available = check_amazon_item(driver, item_url)
                    if available:
                        play_notification_sound()
                        short_url = make_tiny(item_url)
                        writeLog(f"{item['name']} is available: {short_url}", "SUCCESS")
                        if auto_buy:
                            writeLog(f"Attempting to auto-buy {item['name']} on Amazon", "INFO")
                            if not test_mode:
                                auto_buy_amazon_item(driver, item_url, config['app']['amz_email'], config['app']['amz_pwd'], quantity)
                            else:
                                writeLog(f"Test mode active: Skipping final purchase step for {item['name']} on Amazon", "INFO")
                        else:
                            writeLog(f"{item['name']} is available but auto-buy is disabled", "INFO")
                elif "bestbuy.com" in item_url:
                    available = check_bestbuy_item(driver, item_url)
                    if available:
                        play_notification_sound()
                        short_url = make_tiny(item_url)
                        writeLog(f"{item['name']} is available: {short_url}", "SUCCESS")
                        if auto_buy:
                            writeLog(f"Attempting to auto-buy {item['name']} on BestBuy", "INFO")
                            if not test_mode:
                                auto_buy_bestbuy_item(driver, item_url, config['app']['bb_email'], config['app']['bb_password'], config['app']['bb_cvv'], quantity)
                            else:
                                writeLog(f"Test mode active: Skipping final purchase step for {item['name']} on BestBuy", "INFO")
                        else:
                            writeLog(f"{item['name']} is available but auto-buy is disabled", "INFO")
                else:
                    writeLog(f"Unsupported URL: {item_url}", "ERROR")
            except Exception as e:
                writeLog(f"Error processing item {item['name']} with URL {item_url}: {e}", "ERROR")
                play_notification_sound()  # Play sound even if an error occurs
            # Wait for a specified interval before checking again
            time.sleep(config['available'].get('timeout', 10))
    driver.quit()
        
        

if __name__ == "__main__":
    main()