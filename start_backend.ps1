# Start the Chocolate Factory backend (FastAPI) for local testing.
# Run from project root: .\start_backend.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Set-Location $ProjectRoot

if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Error "Virtual environment not found. Run: python -m venv venv; .\venv\Scripts\pip install -r requirements.txt"
}

& "$ProjectRoot\venv\Scripts\Activate.ps1"
Write-Host "Starting backend at http://127.0.0.1:8000" -ForegroundColor Green
& uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
