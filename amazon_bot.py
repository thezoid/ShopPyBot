from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from logger import writeLog
import time

def detect_captcha(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//h4[contains(text(), 'Enter the characters you see below')]"))
        )
        return True
    except:
        return False

def check_amazon_item(driver, item_url):
    writeLog(f"Entering check_amazon_item for URL: {item_url}", "DEBUG")
    try:
        driver.get(item_url)
        if detect_captcha(driver):
            writeLog("CAPTCHA detected. Please solve it manually.", "WARNING")
            input("Press Enter after solving the CAPTCHA...")
        writeLog("Waiting for add-to-cart or buy-now button", "DEBUG")
        try:
            add_to_cart_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "add-to-cart-button"))
            )
        except:
            writeLog("Could not find Add-to-cart button - assume unavailable", "WARNING")
            add_to_cart_button = None
        try:
            buy_now_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "buy-now-button"))
            )
        except:
            writeLog("Could not find Buy-now button - assume unavailable", "WARNING")
            buy_now_button = None
        
        if add_to_cart_button or buy_now_button:
            writeLog("Add-to-cart or Buy-now button found", "INFO")
            writeLog("Item is available on Amazon", "SUCCESS")
            return True
        else:
            writeLog("Add-to-cart or Buy-now button not found", "INFO")
            writeLog("Item is not available on Amazon", "INFO")
            return False
    except Exception as e:
        writeLog(f"Error checking Amazon item: {e}", "ERROR")
        return False

def amz_sign_in(driver, email, password):
    writeLog("Entering amz_sign_in", "DEBUG")
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

def auto_buy_amazon_item(driver, item_url, email, password, quantity, test_mode=False):
    writeLog(f"Entering auto_buy_amazon_item for URL: {item_url}", "DEBUG")
    try:
        driver.get(item_url)
        
        start_time = time.time()
        add_to_cart_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "add-to-cart-button"))
        )
        end_time = time.time()
        writeLog(f"Time to find add-to-cart button: {end_time - start_time:.2f} seconds", "DEBUG")
        
        add_to_cart_button.click()
        writeLog("Added to cart on Amazon", "INFO")

        driver.get("https://www.amazon.com/gp/cart/view.html")
        
        # Update quantity
        start_time = time.time()
        quantity_dropdown = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "a-dropdown-prompt"))
        )
        end_time = time.time()
        writeLog(f"Time to find quantity dropdown: {end_time - start_time:.2f} seconds", "DEBUG")
        
        quantity_dropdown.click()
        
        start_time = time.time()
        quantity_option = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//a[@id='quantity_{quantity}']"))
        )
        end_time = time.time()
        writeLog(f"Time to find quantity option: {end_time - start_time:.2f} seconds", "DEBUG")
        
        quantity_option.click()
        
        start_time = time.time()
        proceed_to_checkout_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "proceedToRetailCheckout"))
        )
        end_time = time.time()
        writeLog(f"Time to find proceed to checkout button: {end_time - start_time:.2f} seconds", "DEBUG")
        
        proceed_to_checkout_button.click()
        writeLog("Proceeded to checkout on Amazon", "INFO")

        amz_sign_in(driver, email, password)

        if test_mode:
            writeLog("Test mode active: Pausing before final purchase step", "DEBUG")
            input("Press Enter to continue...")

        start_time = time.time()
        buy_now_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "buy-now-button"))
        )
        end_time = time.time()
        writeLog(f"Time to find buy-now button: {end_time - start_time:.2f} seconds", "DEBUG")
        
        if not test_mode:
            buy_now_button.click()
        else:
            writeLog("Test mode active: Skipping final purchase step", "INFO")
        
        writeLog("Order placed on Amazon", "SUCCESS")
    except Exception as e:
        writeLog(f"Error during Amazon auto-buy: {e}", "ERROR")