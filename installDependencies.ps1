start "https://chrome.google.com"
Read-Host "Press enter to continue once you download and install Google Chrome"
start "https://chromedriver.chromium.org/downloads"
Read-Host "Press enter to continue once you download and move chromedriver.exe"
start "https://www.python.org/downloads/"
Read-Host "Press enter to continue once you download and install Python 3.9 (add to PATH and include PIP install)"
pip install selenium
pip install playsound

Write-host -ForegroundColor Green "Dependencies should be installed if no errors were encountered above"