from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json

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

#------ start funcs
def writeLog(message, type):
     if loggingLevel == 0:
          return
     if type.upper() == "ERROR" and loggingLevel >= 1:
          print(bcolors.FAIL,"ERROR:",message,bcolors.ENDC)
          global errors
          errors+=1
     elif type.upper() == "WARNING" and loggingLevel >= 2:
          print(bcolors.WARNING,"WARNING:",message,bcolors.ENDC)
          global warnings
          warnings+=1
     elif type.upper() == "INFO" and loggingLevel >= 3:
          print("\033[1;37;40mINFO:",message,bcolors.ENDC)

#read ./settings.json
with open("dev.settings.json") as settingsFile: #!!!CHANGE THIS BACK TO DEFAULT TO settings.json!!!
     settings = json.load(settingsFile)

try:
     item = settings["item"]
     logLevel = settings["loggingLevel"]
     email = settings["email"]
     pwd = settings["password"]
     secCode = settings["cvv"]
except:
     writeLog("Failed to load settings","ERROR")
     exit()

driver = webdriver.Chrome("chromedriver.exe")
driver.get(item)
cardBought = False
while not cardBought:
     #find add to cart button
     try:
          atcBtn = WebDriverWait(driver,10).until(
               EC.element_to_be_clickable((By.CSS_SELECTOR,".add-to-cart-button"))
          )
     except:
          writeLog("Could not find clickable ATC button","WARNING")
          driver.refresh()
          continue

     writeLog("Add To Cart button found!","INFO")