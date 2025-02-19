from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from logger import writeLog

def check_amazon_item(driver, item_url):
    try:
        driver.get(item_url)
        # Add logic to check item availability
        add_to_cart_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "add-to-cart-button"))
        )
        if add_to_cart_button:
            writeLog("Item is available on Amazon", "SUCCESS")
            return True
        else:
            writeLog("Item is not available on Amazon", "INFO")
            return False
    except Exception as e:
        writeLog(f"Error checking Amazon item: {e}", "ERROR")
        return False