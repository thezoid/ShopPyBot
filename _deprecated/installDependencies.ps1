$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Start-Process "https://chrome.google.com"
Read-Host "Press enter to continue once you download and install Google Chrome"
Start-Process "https://chromedriver.chromium.org/downloads"
Read-Host "Press enter to continue once you download and move chromedriver.exe"
Start-Process "https://www.python.org/downloads/"
Read-Host "Press enter to continue once you download and install Python 3.9 (add to PATH and include PIP install)"
# pip install selenium
# pip install playsound
pip install -r "$scriptDir/requirements.txt"

Write-host -ForegroundColor Green "Dependencies should be installed if no errors were encountered above"