from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from logger import writeLog

def check_bestbuy_item(driver, item_url):
    writeLog(f"Entering check_bestbuy_item for URL: {item_url}", "DEBUG")
    try:
        driver.get(item_url)
        writeLog("Waiting for add-to-cart button", "DEBUG")
        add_to_cart_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "add-to-cart-button"))
        )
        if add_to_cart_button:
            writeLog("Add-to-cart button found", "INFO")
            writeLog("Item is available on BestBuy", "SUCCESS")
            return True
        else:
            writeLog("Add-to-cart button not found", "INFO")
            writeLog("Item is not available on BestBuy", "INFO")
            return False
    except Exception as e:
        writeLog(f"Error checking BestBuy item: {e}", "ERROR")
        return False

def bb_sign_in(driver, email, password):
    writeLog("Entering bb_sign_in", "DEBUG")
    try:
        driver.get("https://www.bestbuy.com/identity/signin")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "fld-e"))
        ).send_keys(email)
        driver.find_element(By.ID, "fld-p1").send_keys(password)
        driver.find_element(By.CLASS_NAME, "cia-form__controls__submit").click()
        writeLog("Signed in to BestBuy", "INFO")
    except Exception as e:
        writeLog(f"Error during BestBuy sign-in: {e}", "ERROR")

def auto_buy_bestbuy_item(driver, item_url, email, password, cvv, quantity):
    writeLog(f"Entering auto_buy_bestbuy_item for URL: {item_url}", "DEBUG")
    try:
        driver.get(item_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "add-to-cart-button"))
        ).click()
        writeLog("Added to cart on BestBuy", "INFO")

        driver.get("https://www.bestbuy.com/cart")
        
        # Update quantity
        quantity_dropdown = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "a-dropdown-prompt"))
        )
        quantity_dropdown.click()
        
        quantity_option = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//a[@id='quantity_{quantity}']"))
        )
        quantity_option.click()
        
        driver.find_element(By.CLASS_NAME, "checkout-buttons__checkout").click()
        writeLog("Proceeded to checkout on BestBuy", "INFO")

        bb_sign_in(driver, email, password)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "credit-card-cvv"))
        ).send_keys(cvv)
        driver.find_element(By.CLASS_NAME, "button--place-order").click()
        writeLog("Order placed on BestBuy", "SUCCESS")
    except Exception as e:
        writeLog(f"Error during BestBuy auto-buy: {e}", "ERROR")