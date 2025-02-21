import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from config import config
from logger import setup_logger, writeLog
from amazon_bot import check_amazon_item, auto_buy_amazon_item
from bestbuy_bot import check_bestbuy_item, auto_buy_bestbuy_item
from utils import play_notification_sound, play_buy_sound, play_available_sound
import time
import webbrowser

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

def detect_captcha(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//h4[contains(text(), 'Enter the characters you see below')]"))
        )
        return True
    except:
        return False

def main():
    writeLog("Starting main function", "INFO")
    driver_path = get_chromedriver_path()
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service)
    test_mode = config['debug'].get('test_mode', False)
    open_browser = config['app'].get('open_browser', False)
    
    while True:
        writeLog("Starting new iteration of item checks", "INFO")
        for item in config['available']['items']:
            item_url = item['link']
            auto_buy = item.get('auto_buy', False)
            quantity = item.get('quantity', 1)
            
            try:
                if "amazon.com" in item_url:
                    writeLog(f"Checking availability for Amazon item: {item['name']}", "INFO")
                    driver.get(item_url)
                    if detect_captcha(driver):
                        writeLog("CAPTCHA detected. Please solve it manually.", "WARNING")
                        play_notification_sound()
                        input("Press Enter after solving the CAPTCHA...")
                    available = check_amazon_item(driver, item_url)
                    if available:
                        play_available_sound()
                        short_url = make_tiny(item_url)
                        writeLog(f"{item['name']} is available: {short_url}", "SUCCESS")
                        if auto_buy:
                            writeLog(f"Attempting to auto-buy {item['name']} on Amazon", "INFO")
                            auto_buy_amazon_item(driver, item_url, config['app']['amz_email'], config['app']['amz_pwd'], quantity, test_mode)
                        else:
                            writeLog(f"{item['name']} is available but auto-buy is disabled", "INFO")
                            if open_browser:
                                writeLog(f"Opening browser for {item['name']}", "INFO")
                                webbrowser.open(item_url)
                    else:
                         writeLog(f"{item['name']} is not available", "INFO")
                elif "bestbuy.com" in item_url:
                    writeLog(f"Checking availability for BestBuy item: {item['name']}", "INFO")
                    available = check_bestbuy_item(driver, item_url)
                    if available:
                        play_available_sound()
                        short_url = make_tiny(item_url)
                        writeLog(f"{item['name']} is available: {short_url}", "SUCCESS")
                        if auto_buy:
                            writeLog(f"Attempting to auto-buy {item['name']} on BestBuy", "INFO")
                            if not test_mode:
                                auto_buy_bestbuy_item(driver, item_url, config['app']['bb_email'], config['app']['bb_password'], config['app']['bb_cvv'], quantity)
                                play_buy_sound()
                            else:
                                writeLog(f"Test mode active: Skipping final purchase step", "INFO")
                        else:
                            writeLog(f"{item['name']} is available but auto-buy is disabled", "INFO")
                            if open_browser:
                                writeLog(f"Opening browser for {item['name']}", "INFO")
                                webbrowser.open(item_url)
                    else:
                         writeLog(f"{item['name']} is not available", "INFO")
                else:
                    writeLog(f"Unsupported URL: {item_url}", "ERROR")
            except Exception as e:
                writeLog(f"Error processing item {item['name']} with URL {item_url}: {e}", "ERROR")
        
        # Wait for a specified interval before checking again
        time.sleep(config['available'].get('timeout', 10))

if __name__ == "__main__":
    logger = setup_logger()
    main()