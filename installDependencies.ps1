pip install selenium
pip install playsound
start "https://chrome.google.com"
Read-Host "Press enter to continue once you download and install Google Chrome"
start "https://chromedriver.chromium.org/downloads"
Read-Host "Press enter to continue once you download and move chromedriver.exe"
Write-host -ForegroundColor Green "Dependencies should be installed if no errors were encountered above"