$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root "venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "[ERROR] Missing venv Python at $python" -ForegroundColor Red
    exit 1
}

$env:CLAIRE_API_URL = $env:CLAIRE_API_URL
if ([string]::IsNullOrWhiteSpace($env:CLAIRE_API_URL)) {
    $env:CLAIRE_API_URL = "http://127.0.0.1:8080"
}

if ([string]::IsNullOrWhiteSpace($env:CLAIRE_MODEL_ID)) {
    $model = Get-ChildItem -Path $root -Recurse -Filter *.gguf -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($model) { $env:CLAIRE_MODEL_ID = [System.IO.Path]::GetFileNameWithoutExtension($model.Name) } else { $env:CLAIRE_MODEL_ID = "local" }
}

$serverExe = Get-ChildItem -Path $root -Recurse -Filter "llama-server.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
$modelPath = Get-ChildItem -Path $root -Recurse -Filter *.gguf -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($serverExe -and $modelPath) {
    try {
        $resp = Invoke-WebRequest "$($env:CLAIRE_API_URL)/v1/models" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -ne 200) { throw "model unavailable" }
    } catch {
        Start-Process -FilePath $serverExe.FullName -ArgumentList @(
            "-m", $modelPath.FullName,
            "--alias", $env:CLAIRE_MODEL_ID,
            "--host", "127.0.0.1",
            "--port", "8080",
            "--ctx-size", "4096",
            "--parallel", "2",
            "--no-warmup"
        ) -WindowStyle Hidden | Out-Null
        Start-Sleep -Seconds 4
    }
}

Push-Location $root
try {
    & $python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
} finally {
    Pop-Location
}

