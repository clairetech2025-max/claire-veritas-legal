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
    $model = Get-ChildItem -Path (Join-Path $root "models"), (Join-Path $root "integrations\llama\models"), $root `
        -Recurse -Filter *.gguf -ErrorAction SilentlyContinue |
        Sort-Object Length, LastWriteTime -Descending |
        Select-Object -First 1
    if ($model) {
        $env:CLAIRE_MODEL_ID = [System.IO.Path]::GetFileNameWithoutExtension($model.Name)
    } else {
        $env:CLAIRE_MODEL_ID = "local"
    }
}

function Get-LlamaServerPath {
    $preferred = @(
        (Join-Path $root "integrations\llama\llama-server.exe"),
        (Join-Path $root "llama\llama-server.exe")
    )
    foreach ($candidate in $preferred) {
        if (Test-Path $candidate) { return (Get-Item $candidate) }
    }
    return Get-ChildItem -Path $root -Recurse -Filter "llama-server.exe" -File -ErrorAction SilentlyContinue |
        Sort-Object FullName |
        Select-Object -First 1
}

function Get-ModelPath {
    Get-ChildItem -Path (Join-Path $root "models"), (Join-Path $root "integrations\llama\models"), $root `
        -Recurse -Filter *.gguf -File -ErrorAction SilentlyContinue |
        Sort-Object Length, LastWriteTime -Descending |
        Select-Object -First 1
}

function Test-ServerReady {
    param([string]$Url)
    try {
        $resp = Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 2
        return $resp.StatusCode -eq 200
    } catch {
        return $false
    }
}

$serverExe = Get-LlamaServerPath
$modelPath = Get-ModelPath

if (-not $serverExe) {
    Write-Host "[WARN] llama-server.exe not found; CLAIRE will start without a local model server." -ForegroundColor Yellow
} elseif (-not $modelPath) {
    Write-Host "[WARN] No .gguf model found; CLAIRE will start without a local model server." -ForegroundColor Yellow
} else {
    $logDir = Join-Path $root "logs"
    New-Item -ItemType Directory -Force $logDir | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $stdout = Join-Path $logDir "llama-$stamp.out.log"
    $stderr = Join-Path $logDir "llama-$stamp.err.log"

    if (-not (Test-ServerReady "$($env:CLAIRE_API_URL)/v1/models")) {
        Write-Host "[INFO] Starting llama-server from $($serverExe.FullName)" -ForegroundColor Cyan
        $args = @(
            "-m", $modelPath.FullName,
            "--alias", $env:CLAIRE_MODEL_ID,
            "--host", "127.0.0.1",
            "--port", "8080",
            "--ctx-size", "4096",
            "--parallel", "2",
            "--no-warmup"
        )
        Start-Process -FilePath $serverExe.FullName `
            -ArgumentList $args `
            -WorkingDirectory $serverExe.DirectoryName `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr | Out-Null

        $deadline = (Get-Date).AddSeconds(30)
        while (-not (Test-ServerReady "$($env:CLAIRE_API_URL)/v1/models")) {
            if ((Get-Date) -gt $deadline) {
                throw "llama-server failed to start. Check $stderr"
            }
            Start-Sleep -Milliseconds 500
        }
    }
}

Push-Location $root
try {
    & $python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
} finally {
    Pop-Location
}
