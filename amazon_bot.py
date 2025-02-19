from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from logger import writeLog

def check_amazon_item(driver, item_url):
    try:
        driver.get(item_url)
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

def amz_sign_in(driver, email, password):
    try:
        driver.get("https://www.amazon.com/ap/signin")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ap_email"))
        ).send_keys(email)
        driver.find_element(By.ID, "continue").click()

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ap_password"))
        ).send_keys(password)
        driver.find_element(By.ID, "signInSubmit").click()
        writeLog("Signed in to Amazon", "INFO")
    except Exception as e:
        writeLog(f"Error during Amazon sign-in: {e}", "ERROR")

def auto_buy_amazon_item(driver, item_url, email, password, quantity):
    try:
        driver.get(item_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "add-to-cart-button"))
        ).click()
        writeLog("Added to cart on Amazon", "INFO")

        driver.get("https://www.amazon.com/gp/cart/view.html")
        
        # Update quantity
        quantity_dropdown = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "a-dropdown-prompt"))
        )
        quantity_dropdown.click()
        
        quantity_option = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//a[@id='quantity_{quantity}']"))
        )
        quantity_option.click()
        
        driver.find_element(By.NAME, "proceedToRetailCheckout").click()
        writeLog("Proceeded to checkout on Amazon", "INFO")

        amz_sign_in(driver, email, password)

        # Click the "Buy Now" or "Pre-order now" button
        buy_now_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "buy-now-button"))
        )
        buy_now_button.click()
        writeLog("Order placed on Amazon", "SUCCESS")
    except Exception as e:
        writeLog(f"Error during Amazon auto-buy: {e}", "ERROR")