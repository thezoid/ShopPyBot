#built in
import json
import os
import datetime
import time
#third party
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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

def make_tiny(url):
    request_url = ('https://tinyurl.com/api-create.php?' + urlencode({'url':url}))    
    with contextlib.closing(urlopen(request_url)) as response:                      
        return response.read().decode('utf-8 ')

def bbIsAvail(_driver,_itemName, _itemLink,_alertSound,_timeout,_openBrowser=False,_shortURL=True,_loggingLevel=0):
     #find add to cart button (only available if not "sold out"?)
     _driver.get(_itemLink)
     time.sleep(0.5)
     try:
          atcBtn = WebDriverWait(driver,_timeout).until(
               EC.element_to_be_clickable((By.CSS_SELECTOR,".add-to-cart-button"))
          )
          try:
               priceText = WebDriverWait(_driver,_timeout).until(
                    EC.presence_of_element_located((By.XPATH,"/html/body/div[3]/main/div[2]/div[3]/div[2]/div/div/div[1]/div/div/div/div/div[2]/div[1]/div/div/span[1]"))
               )
               price = priceText.text
          except:
               writeLog("Failed to get price text","ERROR",_loggingLevel)
               price="N/A"
     except:
          m= f"[BestBuy] {itemName} is NOT available"
          writeLog(m,"UNAVAILABLE",_loggingLevel)
          return
     if shortURL:
          m=f"[Amazon][{price}] {_itemName} is available at {make_tiny(_itemLink)}"
     else:
          m=f"[Amazon][{price}] {_itemName} is available at {_itemLink}"
     writeLog(m,"AVAILABLE")
     if(_alertSound and _alertSound != ""):
          playsound(_alertSound,False)
     if _openBrowser:
          wb.open(_itemLink,new=1)

def amzIsAvail(_driver,_itemName, _itemLink,_alertSound,_timeout,_openBrowser=False,_shortURL=True,_loggingLevel=0):
     _driver.get(_itemLink)
     time.sleep(0.5)
     #try to see if there is a buy now button
     try:
          buyNowBTN = WebDriverWait(_driver,_timeout).until(
               EC.element_to_be_clickable((By.ID,"buy-now-button"))
          )
          try:
               priceText = WebDriverWait(_driver,_timeout).until(
                    EC.presence_of_element_located((By.ID,"priceblock_ourprice"))
               )
               price = priceText.text
          except:
               writeLog("Failed to get price text","ERROR",_loggingLevel)
               price="N/A"
     except:
          m= f"[Amazon] {itemName} is NOT available"
          writeLog(m,"UNAVAILABLE",_loggingLevel)
          return
     if shortURL:
          m=f"[Amazon][{price}] {_itemName} is available at {make_tiny(_itemLink)}"
     else:
          m=f"[Amazon][{price}] {_itemName} is available at {_itemLink}"
     writeLog(m,"AVAILABLE")
     if(_alertSound and _alertSound != ""):
          playsound(_alertSound,False)
     if _openBrowser:
          wb.open(_itemLink,new=1)

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
     items = sorted (settings["available"]["items"],key= lambda k: (k["type"],k["name"]))
     timeout = settings["available"]["timeout"]
     openBrowser = settings["available"]["openNewBrowser"]
     if(openBrowser):
          import webbrowser as wb
     shortURL = settings["available"]["shortURL"]
     if shortURL:                                                       
          import contextlib
          try:
               from urllib.parse import urlencode          
          except ImportError:
               from urllib import urlencode
          try:
               from urllib.request import urlopen
          except ImportError:
               from urllib2 import urlopen

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
               bbIsAvail(driver,itemName,itemLink,alertSoundPath,timeout,openBrowser,loggingLevel)
          
          if domain.lower() == "amazon":
               amzIsAvail(driver,itemName,itemLink,alertSoundPath,timeout,openBrowser,loggingLevel)
     
     writeLog(f"Starting next round --- Total Duration:{datetime.timedelta(seconds=(datetime.datetime.now() - startTime).total_seconds())}",type="ALWAYS")

driver.close()
driver.quit()