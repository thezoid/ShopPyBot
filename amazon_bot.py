from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from logger import writeLog
import time
from utils import play_notification_sound
from models import update_item_purchased

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
        if driver.current_url != item_url:
            driver.get(item_url)
        if detect_captcha(driver):
            writeLog("CAPTCHA detected. Please solve it manually.", "WARNING")
            driver.focus()
            input("--------------------\nPress Enter after solving the CAPTCHA...--------------------\n")
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

def amz_sign_in(driver, config):
    try:
        email = config['app']['amz_email']
        password = config['app']['amz_pwd']
        
        # Check if the user is already signed in
        writeLog("Checking if user is already signed in", "INFO")
        try:
            account_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "nav-link-accountList"))
            )
            sign_in_button = account_element.find_element(By.CLASS_NAME, "nav-action-signin-button")
            if sign_in_button:
                writeLog("User is not signed in", "INFO")
            else:
                writeLog("User is already signed in", "INFO")
                return
        except Exception as e:
            writeLog(f"Error checking sign-in state: {e}", "ERROR")

        # User is not signed in, proceed with sign-in
        writeLog("User is not signed in, proceeding with sign-in", "INFO")
        driver.get("https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3Fref_%3Dnav_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=usflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0")
        try:
          WebDriverWait(driver, 10).until(
               EC.presence_of_element_located((By.ID, "ap_email"))
          ).send_keys(email)
          driver.find_element(By.ID, "continue").click()
        except Exception as e: 
          writeLog(f"Error during Amazon sign-in when entering email: {e}", "ERROR")
          raise Exception("Sign-in failed - failed to enter email")

        play_notification_sound()
        input("Press enter once you dismiss the passkey prompt...")
        
        try:
          writeLog("Attempting to enter password", "INFO")
          WebDriverWait(driver, 10).until(
               EC.presence_of_element_located((By.ID, "ap_password"))
          ).send_keys(password)
        except Exception as e:
          writeLog(f"Error during Amazon sign-in when entering password: {e}", "ERROR")
          raise Exception("Sign-in failed - failed to enter password")
        
        try:
            writeLog("Attempting to click sign-in button", "INFO")
            driver.find_element(By.ID, "signInSubmit").click()
        except Exception as e:
               writeLog(f"Error during Amazon sign-in when clicking sign-in button: {e}", "ERROR")
               raise Exception("Sign-in failed")
        # Check for MFA prompt
        try:
            writeLog("Checking for MFA prompt", "INFO")
            mfa_form = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "auth-mfa-form"))
            )
            if mfa_form:
                writeLog("MFA prompt detected. Please enter the OTP manually.", "WARNING")
                play_notification_sound()
                input("Press Enter after entering the OTP...")
        except:
            writeLog("No MFA prompt detected.", "warning")

        writeLog("Signed in to Amazon", "INFO")
    except Exception as e:
        writeLog(f"Error during Amazon sign-in: {e}", "ERROR")

def auto_buy_amazon_item(driver, item_url, config, quantity, test_mode=False):
    writeLog(f"Entering auto_buy_amazon_item for URL: {item_url}", "DEBUG")
    amz_sign_in(driver, config)
    try:
        if driver.current_url != item_url:
            driver.get(item_url)
        
        try:
            writeLog("Attempting to find quantity dropdown", "INFO")
            start_time = time.time()
            quantity_dropdown = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "a-button-dropdown"))
            )
            end_time = time.time()
            writeLog(f"Time to find quantity dropdown: {end_time - start_time:.2f} seconds", "DEBUG")
            quantity_dropdown.click()
        except Exception as e:
            writeLog(f"Error finding quantity dropdown: {e}", "ERROR")
            return
        
        try:
            writeLog(f"Attempting to find quantity option for {quantity}", "INFO")
            start_time = time.time()
            quantity_option = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, f"quantity_{quantity-1}"))
            )
            end_time = time.time()
            writeLog(f"Time to find quantity option: {end_time - start_time:.2f} seconds", "DEBUG")
            quantity_option.click()
        except Exception as e:
            writeLog(f"Error finding quantity option: {e}", "ERROR")
            return

        if test_mode:
            writeLog("Test mode active: Pausing before final purchase step", "DEBUG")
            input("Press Enter to continue...")

        try:
            writeLog("Attempting to find buy-now button", "INFO")
            start_time = time.time()
            buy_now_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "buy-now-button"))
            )
            end_time = time.time()
            writeLog(f"Time to find buy-now button: {end_time - start_time:.2f} seconds", "DEBUG")
            buy_now_button.click()
        except Exception as e:
            writeLog(f"Error finding buy-now button: {e}", "ERROR")
            return

        try:
            writeLog("Attempting to find place order button", "INFO")
            start_time = time.time()
            place_order_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "submitOrderButtonId"))
            )
            end_time = time.time()
            writeLog(f"Time to find place order button: {end_time - start_time:.2f} seconds", "DEBUG")
            if not test_mode:
                place_order_button.click()
                writeLog("Order placed on Amazon", "SUCCESS")
                update_item_purchased(item_url)
            else:
                writeLog("Test mode active: Skipping final purchase step, otherwise submitOrderButton would have been clicked!", "SUCCESS")
                input("Press Enter to continue...")
        except Exception as e:
            writeLog(f"Error finding place order button: {e}", "ERROR")
            return
    except Exception as e:
        writeLog(f"Error during Amazon auto-buy: {e}", "ERROR")