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
def writeLog(message, type=""):
     if type.upper() == "AVAILABLE":
          print(bcolors.OKGREEN,"AVAILABLE:",message,bcolors.ENDC)
     elif type.upper() == "UNAVAILABLE":
          print(bcolors.FAIL,"UNAVAILABLE:",message,bcolors.ENDC)
     else:
          print(bcolors.BASIC,message,bcolors.ENDC)
          
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
     items = settings["available"]["items"]
     delay = settings["available"]["delay"]
     alertSoundPath = scriptdir+"/sounds/Picked Coin Echo 2.wav"
except:
     writeLog("Failed to load settings","ERROR")
     exit()

driver = webdriver.Chrome("chromedriver.exe",service_log_path=os.devnull)

stopCheck = False
while not stopCheck:
     for item in items:
          itemName = item["name"]
          itemLink = item["link"]
          driver.get(itemLink)
          #find add to cart button (only available if not "sold out"?)
          try:
               atcBtn = WebDriverWait(driver,delay).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR,".add-to-cart-button"))
               )
          except:
               m= f"{itemName} is NOT available"
               writeLog(m,"UNAVAILABLE")
               #driver.refresh()
               continue
          m=f"{itemName} is available at {itemLink}"
          writeLog(m,"AVAILABLE")
          if(alertSoundPath and alertSoundPath != ""):
               playsound(alertSoundPath)
     m=f"\n\n\n\n\n\nStarting over from the top"
     writeLog(m)