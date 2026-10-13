$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$envFile = Join-Path $projectRoot ".env"

if (-not (Test-Path $venvPython)) {
    throw "Project environment not found. Run .\setup.ps1 first."
}
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $projectRoot ".env.example") $envFile
    Write-Host "Created .env from .env.example. Set MODEL_PATH and ALERT_WEBHOOK_URL as needed."
}

Push-Location $projectRoot
try {
    & $venvPython -m uvicorn roadguard.api:app --env-file $envFile --host 127.0.0.1 --port 8000
    if ($LASTEXITCODE -ne 0) { throw "RoadGuard server exited with code $LASTEXITCODE." }
}
finally {
    Pop-Location
}
