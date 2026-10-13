$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pythonCommand = $null
$pythonArgs = @()

$launcher = Get-Command py.exe -ErrorAction SilentlyContinue
if ($launcher) {
    $pythonCommand = $launcher.Source
    $pythonArgs = @("-3")
} else {
    $pythonRoots = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python"),
        (Join-Path $env:ProgramFiles "Python")
    )
    foreach ($root in $pythonRoots) {
        if (Test-Path $root) {
            $candidate = Get-ChildItem $root -Directory -Filter "Python3*" -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending |
                ForEach-Object { Join-Path $_.FullName "python.exe" } |
                Where-Object { Test-Path $_ } |
                Select-Object -First 1
            if ($candidate) {
                $pythonCommand = $candidate
                break
            }
        }
    }
}

if (-not $pythonCommand) {
    throw "Python 3.10 or newer was not found. Install Python, then reopen PowerShell."
}

$versionText = & $pythonCommand @pythonArgs --version 2>&1
if ($LASTEXITCODE -ne 0 -or $versionText -notmatch "Python 3\.(1[0-9]|[2-9][0-9])") {
    throw "Python 3.10 or newer is required. Found: $versionText"
}

if (-not (Test-Path $venvPython)) {
    & $pythonCommand @pythonArgs -m venv (Join-Path $projectRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create the project virtual environment." }
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip." }

& $venvPython -m pip install -r (Join-Path $projectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

$envFile = Join-Path $projectRoot ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $projectRoot ".env.example") $envFile
}

Write-Host "Setup complete. Download the starter model with .\scripts\download_model.ps1, or add your reviewed weights, then run .\start.ps1."
