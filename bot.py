from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import os
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
def writeLog(message, type,_loggingLevel):
     if _loggingLevel == 0:
          return
     if type.upper() == "ERROR" and _loggingLevel >= 1:
          print(bcolors.FAIL,"ERROR:",message,bcolors.ENDC)
     elif type.upper() == "WARNING" and _loggingLevel >= 2:
          print(bcolors.WARNING,"WARNING:",message,bcolors.ENDC)
     elif type.upper() == "INFO" and _loggingLevel >= 3:
          print("\033[1;37;40mINFO:",message,bcolors.ENDC)
     elif type.upper() == "ALWAYS":
          print(bcolors.OKGREEN,message,bcolors.ENDC)

def bbBuy(_link,_alertSound,_loggingLevel=0):
     #find add to cart button (only available if not "sold out"?)
     try:
          atcBtn = WebDriverWait(driver,timeout).until(
               EC.element_to_be_clickable((By.CSS_SELECTOR,".add-to-cart-button"))
          )
     except:
          writeLog("Could not find clickable ATC button","WARNING",_loggingLevel)
          driver.refresh()
          return False

     writeLog("Add To Cart button found!","INFO",_loggingLevel)

     if not queueExists:
          try:
               #click add to cart button
               atcBtn.click()
               #go to cart and begin checkout as guest
               driver.get("https://bestbuy.com/cart")
               checkoutBtn = WebDriverWait(driver,timeout).until(
                    EC.presence_of_element_located((By.XPATH,"/html/body/div[1]/main/div/div[2]/div[1]/div/div[1]/div[1]/section[2]/div/div/div[3]/div/div[1]/button"))
               )
               checkoutBtn.click()
               writeLog("Successfully added to cart - begin checkout","INFO",_loggingLevel)

               #fill in account details
               emailField = WebDriverWait(driver,timeout).until(
                    EC.presence_of_element_located((By.ID,"fld-e"))
               )
               emailField.send_keys(email)
               pwField = WebDriverWait(driver,timeout).until(
                    EC.presence_of_element_located((By.ID,"fld-p1"))
               )
               pwField.send_keys(pwd)

               #click sign in
               signInBtn = WebDriverWait(driver,timeout).until(
                    EC.presence_of_element_located((By.XPATH,"/html/body/div[1]/div/section/main/div[2]/div[1]/div/div/div/div/form/div[3]/button"))
               )
               signInBtn.click()
               writeLog("Signing in","INFO",_loggingLevel)

               #fill in card cvv (assumes account already has exactly 1 payment method setup)
               cvvField = WebDriverWait(driver,timeout).until(
                    EC.presence_of_element_located((By.ID,"credit-card-cvv"))
               )
               cvvField.send_keys(secCode)
               writeLog("Attempting to place order","INFO",_loggingLevel)

               #order
               placeOrderBtn = WebDriverWait(driver,timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR,".button__fast-track"))
               )
               if not testMode:
                    placeOrderBtn.click()

               writeLog("Item should have been purchased","INFO",_loggingLevel)
               return True
               
          except:
               #ensure the driver is looking at the right page
               driver.get(_link)
               writeLog("Trying again...","ERROR",_loggingLevel)
     else:
          atcBtn.click()
          if(_alertSound and _alertSound != ""):
               playsound(_alertSound)
          writeLog("YOU'RE IN QUEUE - GOOD LUCK","ALWAYS",_loggingLevel)
          return True
     

#------ end funcs


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
     email = settings["app"]["email"]
     pwd = settings["app"]["password"]
     secCode = settings["app"]["cvv"]
     timeout = settings["app"]["timeout"]
     queueExists = settings["app"]["queueExists"]
     if settings["debug"]["alertType"] == "wav":
          alertSoundPath = scriptdir+"/sounds/alert.wav"
     elif settings["debug"]["alertType"] == "mp3":
          alertSoundPath = scriptdir+"/sounds/alert.mp3"
     else:
          writeLog("Alert file type is invalid","ERROR",loggingLevel)
          exit()
except:
     writeLog("Failed to load settings","ERROR")
     exit()

driver = webdriver.Chrome(scriptdir+"/chromedriver.exe",service_log_path=os.devnull)

cardBought = False
while not cardBought:

     driver.get(item)
     #get domain from item link
     domain = item.split("/")
     domain = domain[2][domain[2].index('.')+1:domain[2].rfind('.')]
     writeLog(f"Item is from {domain}","INFO",loggingLevel)

     if(domain == "bestbuy"):
          cardBought = bbBuy(item,alertSoundPath)

     