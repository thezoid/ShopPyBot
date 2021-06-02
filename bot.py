from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import os
import datetime
from playsound import playsound

#text colors
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    BASIC = '\033[1;37;40m'

#------ start funcs
def writeLog(message, type,_loggingLevel=0):
     if type.upper() == "ALWAYS":
          print(bcolors.OKGREEN,message,bcolors.ENDC)
     elif _loggingLevel == 0:
          return
     if type.upper() == "ERROR" and _loggingLevel >= 1:
          print(bcolors.FAIL,"ERROR:",message,bcolors.ENDC)
     elif type.upper() == "WARNING" and _loggingLevel >= 2:
          print(bcolors.WARNING,"WARNING:",message,bcolors.ENDC)
     elif type.upper() == "INFO" and _loggingLevel >= 3:
          print("\033[1;37;40mINFO:",message,bcolors.ENDC)
def bbBuy(_driver,_link,_alertSound,_timeout,_queueExists,_email,_pwd,_sec,_testMode,_loggingLevel=0):
     _driver.get(_link)
     
     #find add to cart button (only available if not "sold out"?)
     try:
          atcBtn = WebDriverWait(_driver,_timeout).until(
               EC.element_to_be_clickable((By.CSS_SELECTOR,".add-to-cart-button"))
          )
     except:
          writeLog("Could not find clickable ATC button","WARNING",_loggingLevel)
          return False

     writeLog("Add To Cart button found!","INFO",_loggingLevel)

     if not _queueExists:
          try:
               #click add to cart button
               atcBtn.click()
               #go to cart and begin checkout as guest
               _driver.get("https://bestbuy.com/cart")
               checkoutBtn = WebDriverWait(_driver,_timeout).until(
                    EC.presence_of_element_located((By.XPATH,"/html/body/div[1]/main/div/div[2]/div[1]/div/div[1]/div[1]/section[2]/div/div/div[3]/div/div[1]/button"))
               )
               checkoutBtn.click()
               writeLog("Successfully added to cart - begin checkout","INFO",_loggingLevel)

               #fill in account details
               emailField = WebDriverWait(_driver,_timeout).until(
                    EC.presence_of_element_located((By.ID,"fld-e"))
               )
               emailField.send_keys(_email)
               pwField = WebDriverWait(_driver,_timeout).until(
                    EC.presence_of_element_located((By.ID,"fld-p1"))
               )
               pwField.send_keys(_pwd)

               #click sign in
               signInBtn = WebDriverWait(_driver,_timeout).until(
                    EC.presence_of_element_located((By.XPATH,"/html/body/div[1]/div/section/main/div[2]/div[1]/div/div/div/div/form/div[3]/button"))
               )
               signInBtn.click()
               writeLog("Signing in","INFO",_loggingLevel)

               #fill in card cvv (assumes account already has exactly 1 payment method setup)
               cvvField = WebDriverWait(_driver,_timeout).until(
                    EC.presence_of_element_located((By.ID,"credit-card-cvv"))
               )
               cvvField.send_keys(_sec)
               writeLog("Attempting to place order","INFO",_loggingLevel)

               #order
               placeOrderBtn = WebDriverWait(_driver,_timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR,".button__fast-track"))
               )
               if not _testMode:
                    placeOrderBtn.click()
               
               if(_alertSound and _alertSound != ""):
                    playsound(_alertSound,False)
               writeLog("Item should have been purchased","INFO",_loggingLevel)
               return True
               
          except:
               #ensure the driver is looking at the right page
               _driver.get(_link)
               writeLog("Trying again...","ERROR",_loggingLevel)
     else:
          atcBtn.click()
          if(_alertSound and _alertSound != ""):
               playsound(_alertSound,False)
          writeLog("YOU'RE IN QUEUE - GOOD LUCK","ALWAYS",_loggingLevel)
          return True
     
def amzSignIn(_driver,_timeout,_email,_pwd,_loggingLevel=0):
     try:
          _driver.get("https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3Fref_%3Dnav_ya_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=usflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&")
          emailField = WebDriverWait(_driver,_timeout).until(
               EC.presence_of_element_located((By.ID,"ap_email"))
          )
          emailField.send_keys(_email)

          contBtn = WebDriverWait(_driver,_timeout).until(
               EC.presence_of_element_located((By.ID,"continue"))
          )
          contBtn.click()
          pwdField = WebDriverWait(_driver,_timeout).until(
               EC.presence_of_element_located((By.ID,"ap_password"))
          )
          pwdField.send_keys(_pwd)
          signInBTN = WebDriverWait(_driver,_timeout).until(
               EC.presence_of_element_located((By.ID,"signInSubmit"))
          )
          signInBTN.click()
          input("Press enter once you sign in with your OTP code...")
          return True
     except:
          writeLog("Failed to login to Amazon!!!","ERROR",_loggingLevel)
          return False

def AMZBuy(_driver,_link,_alertSound,_timeout,_testMode,_loggingLevel=0):
     _driver.get(_link)
     #try to see if there is a buy now button
     try:
          buyNowBTN = WebDriverWait(_driver,_timeout).until(
               EC.element_to_be_clickable((By.ID,"buy-now-button"))
          )
     except:
          writeLog("Could not find Buy Now button","WARNING",_loggingLevel)
          return False

     writeLog("'Buy Now button found!","INFO",_loggingLevel)
     try:
          buyNowBTN.click()          
          placeOrderBtn = WebDriverWait(_driver,_timeout).until(
               EC.presence_of_element_located((By.NAME,"placeYourOrder1"))
          )
          if not _testMode:
               placeOrderBtn.click()

          if(_alertSound and _alertSound != ""):
               playsound(_alertSound,False)
          writeLog("Item should have been purchased","INFO",_loggingLevel)
          return True
     except:
          writeLog(f"Failed to buy {_link}","ERROR",_loggingLevel)
          return False
     

#------ end funcs
startTime = datetime.datetime.now()

os.system('color')

scriptdir = os.path.dirname(os.path.realpath(__file__))

#read ./settings.json
with open(scriptdir+"/dev.settings.json") as settingsFile: #!!!CHANGE THIS BACK TO DEFAULT TO settings.json!!!
     settings = json.load(settingsFile)

try:
     loggingLevel = settings["debug"]["loggingLevel"]
     if loggingLevel > 3:
          loggingLevel = 3
     if loggingLevel < 0:
          loggingLevel = 0
     testMode = settings["debug"]["testMode"]
     item = settings["app"]["item"]
     bb_email = settings["app"]["bb_email"]
     bb_pwd = settings["app"]["bb_password"]
     bb_secCode = settings["app"]["bb_cvv"]
     amz_email = settings["app"]["amz_email"]
     amz_pwd = settings["app"]["amz_pwd"]
     timeout = settings["app"]["timeout"]
     queueExists = settings["app"]["queueExists"]
     if settings["app"]["alertType"] == "wav":
          alertSoundPath = scriptdir+"/sounds/alert_buy.wav"
     elif settings["app"]["alertType"] == "mp3":
          alertSoundPath = scriptdir+"/sounds/alert_buy.mp3"
     else:
          writeLog("Alert file type is invalid","ERROR",loggingLevel)
          exit()
except:
     writeLog("Failed to load settings","ERROR")
     exit()

options = webdriver.ChromeOptions()
options.add_argument("--log-level=3")
options.add_experimental_option('excludeSwitches', ['enable-logging'])
driver = webdriver.Chrome(scriptdir+"/chromedriver.exe",options=options)
writeLog("New Chrome opened - DONT CLOSE!","INFO",loggingLevel)

itemBought = False
signedIn = False
attempts = 0
while not itemBought:
     attempts+=1
     #get domain from item link
     domain = item.split("/")
     domain = domain[2][domain[2].index('.')+1:domain[2].rfind('.')]
     writeLog(f"[{attempts}]Attempting to buy item from {domain}","INFO",loggingLevel)
     if(domain == "bestbuy"):
          itemBought = bbBuy(driver,item,alertSoundPath,timeout,queueExists,bb_email,bb_pwd,bb_secCode,testMode,loggingLevel)

     if(domain == "amazon"):
          if signedIn:
               itemBought = AMZBuy(driver,item, alertSoundPath,timeout,testMode,loggingLevel)
          else:
               writeLog("Amazon sign in required!!","WARNING",loggingLevel)
               signedIn = amzSignIn(driver,timeout,amz_email,amz_pwd,loggingLevel)

     if itemBought:
          writeLog(f"Item purchased after {attempts} attempts --- Total duration:{datetime.timedelta(seconds=(datetime.datetime.now() - startTime).total_seconds())}","ALWAYS")
          driver.save_screenshot(scriptdir+f"/purchases/{datetime.date.today()}.png")



#cleanup
driver.close()
driver.quit()