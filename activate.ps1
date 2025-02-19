 function Test-Package {
     param (
         [string]$packageName
     )
     $package = pip show $packageName 2>&1
     return -not ($package -match "WARNING: Package(s) not found")
 }

if (-not (Test-Path "$PSScriptRoot\.venv")) {
     Write-Host "No virtual environment found in $PSScriptRoot\.venv"
     python -m venv "$PSScriptRoot\.venv"
 }
 
 .\.venv\Scripts\activate

 $requirements = Get-Content "$PSScriptRoot\requirements.txt"
 foreach ($requirement in $requirements) {
     if (-not (Test-Package -packageName $requirement)) {
         Write-Host "Installing $requirement..."
         pip install $requirement
     } else {
         Write-Host "$requirement is already installed."
     }
 }