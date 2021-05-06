from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import os
import datetime
import time
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
def writeLog(message, type="",_loggingLevel=0):
     #print(f"in writeLog - loglvl: {_loggingLevel} - type: {type}")
     if type.upper() == "ALWAYS":
          print(bcolors.BASIC,message,bcolors.ENDC)
     elif type.upper() == "AVAILABLE":
          print(bcolors.OKGREEN,"AVAILABLE:",message,bcolors.ENDC)
     elif type.upper() == "UNAVAILABLE":
          print(bcolors.FAIL,"UNAVAILABLE:",message,bcolors.ENDC)
     elif _loggingLevel == 0:
          return
     elif type.upper() == "ERROR" and _loggingLevel >= 1:
          print(bcolors.FAIL,"ERROR:",message,bcolors.ENDC)
     elif type.upper() == "WARNING" and _loggingLevel >= 2:
          print(bcolors.WARNING,"WARNING:",message,bcolors.ENDC)
     elif type.upper() == "INFO" and _loggingLevel >= 3:
          print("\033[1;37;40mINFO:",message,bcolors.ENDC)

def bbIsAvail(_driver,_itemName, _itemLink,_alertSound,_loggingLevel=0):
     #find add to cart button (only available if not "sold out"?)
     _driver.get(_itemLink)
     try:
          atcBtn = WebDriverWait(driver,timeout).until(
               EC.element_to_be_clickable((By.CSS_SELECTOR,".add-to-cart-button"))
          )
     except:
          m= f"{itemName} is NOT available"
          writeLog(m,"UNAVAILABLE",_loggingLevel)
          return
     m=f"{_itemName} is available at {_itemLink}"
     writeLog(m,"AVAILABLE")
     if(_alertSound and _alertSound != ""):
          playsound(_alertSound,_loggingLevel)

 #------ end funcs

startTime = datetime.datetime.now()

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
     timeout = settings["available"]["timeout"]
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

options = webdriver.ChromeOptions()
#options.headless = True
options.add_argument("--log-level=3")
options.add_experimental_option('excludeSwitches', ['enable-logging'])
driver = webdriver.Chrome(scriptdir+"/chromedriver.exe",options=options)
driver.minimize_window()
writeLog("New Chrome opened - DONT CLOSE!","INFO",loggingLevel)

stopCheck = False
while not stopCheck:
     for item in items:
          itemName = item["name"]
          itemLink = item["link"]

          domain = itemLink.split("/")
          domain = domain[2][domain[2].index('.')+1:domain[2].rfind('.')]
          #writeLog(f"Item is from {domain}","INFO",loggingLevel)
          
          if domain.lower() == "bestbuy":
               bbIsAvail(driver,itemName,itemLink,alertSoundPath,loggingLevel)
               
     writeLog(f"Starting next round --- Total Duration:{datetime.timedelta(seconds=(datetime.datetime.now() - startTime).total_seconds())}",type="ALWAYS")