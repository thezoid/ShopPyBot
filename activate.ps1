if (-not (Test-Path "$PSScriptRoot\.venv")) {
     Write-Host "No virtual environment found in $PSScriptRoot\.venv"
     python -m venv "$PSScriptRoot\.venv"
}
.\.venv\Scripts\activate  