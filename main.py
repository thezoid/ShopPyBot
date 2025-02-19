from selenium import webdriver
from config import config
from logger import setup_logger, writeLog
from amazon_bot import check_amazon_item
from bestbuy_bot import check_bestbuy_item
from utils import play_notification_sound

logger = setup_logger()

def main():
    driver = webdriver.Chrome(executable_path=config['selenium']['driver_path'])
    
    amazon_url = config['amazon']['item_url']
    bestbuy_url = config['bestbuy']['item_url']
    
    if check_amazon_item(driver, amazon_url):
        play_notification_sound()
    
    if check_bestbuy_item(driver, bestbuy_url):
        play_notification_sound()
    
    driver.quit()

if __name__ == "__main__":
    main()