$ErrorActionPreference = "Stop"
$modelsDirectory = Join-Path $PSScriptRoot "..\models"
$modelPath = Join-Path $modelsDirectory "accident.pt"
$downloadPath = Join-Path $modelsDirectory "accident.pt.download"
$modelUrl = "https://huggingface.co/Enos-123/traffic-accident-detection-yolo11x/resolve/cdc556d278e00273fc3af373051b0df2fb7c7f1e/weights/epoch61.pt"
$expectedSha256 = "EA56E358905E79E1451170E699B21AD774CA95E12034AE1AB1F7D09FD3619CAE"

New-Item -ItemType Directory -Force -Path $modelsDirectory | Out-Null

if (Test-Path $modelPath) {
    $existingHash = (Get-FileHash -LiteralPath $modelPath -Algorithm SHA256).Hash
    if ($existingHash -ne $expectedSha256) {
        throw "models\accident.pt already exists and is not the pinned model. Move it aside before downloading."
    }
    Write-Host "Pinned accident model is already installed and checksum-verified."
    exit 0
}

if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    throw "curl.exe is required to download the model."
}

try {
    & curl.exe --location --fail --show-error --retry 3 --output $downloadPath $modelUrl
    if ($LASTEXITCODE -ne 0) {
        throw "Model download failed with curl exit code $LASTEXITCODE."
    }

    $downloadHash = (Get-FileHash -LiteralPath $downloadPath -Algorithm SHA256).Hash
    if ($downloadHash -ne $expectedSha256) {
        throw "Model checksum mismatch. The downloaded file will not be installed."
    }

    Move-Item -LiteralPath $downloadPath -Destination $modelPath
    Write-Host "Accident model downloaded and checksum-verified at models\accident.pt."
} finally {
    if (Test-Path $downloadPath) {
        Remove-Item -LiteralPath $downloadPath -Force
    }
}
