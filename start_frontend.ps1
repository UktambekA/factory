# Open the Chocolate Factory web UI in the default browser (for local testing).
# Ensure the backend is running first: .\start_backend.ps1

$Url = "http://127.0.0.1:8000"

# Optional: wait briefly for backend if just started
$maxTries = 5
for ($i = 0; $i -lt $maxTries; $i++) {
    try {
        $null = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        break
    } catch {
        if ($i -eq $maxTries - 1) {
            Write-Host "Backend not responding at $Url. Start it first: .\start_backend.ps1" -ForegroundColor Yellow
        }
        Start-Sleep -Seconds 1
    }
}

Write-Host "Opening $Url" -ForegroundColor Green
Start-Process $Url
