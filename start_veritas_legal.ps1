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

function Get-SearchRoots {
    $roots = @($root)
    if (-not [string]::IsNullOrWhiteSpace($env:CLAIRE_LLAMA_ROOT)) {
        $roots += $env:CLAIRE_LLAMA_ROOT
    }
    $roots += @(
        "I:\Claire_new",
        "I:\ClaireTech"
    )
    $resolved = @()
    foreach ($candidate in $roots) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        if (Test-Path $candidate) {
            $resolved += (Get-Item $candidate).FullName
        }
    }
    return $resolved | Select-Object -Unique
}

$searchRoots = Get-SearchRoots

if ([string]::IsNullOrWhiteSpace($env:CLAIRE_MODEL_ID)) {
    $modelHints = foreach ($base in $searchRoots) {
        @(
            (Join-Path $base "models"),
            (Join-Path $base "integrations\llama\models"),
            $base
        )
    }
    $model = Get-ChildItem -Path $modelHints `
        -Recurse -Filter *.gguf -File -ErrorAction SilentlyContinue |
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
        (Join-Path $root "llama\llama-server.exe"),
        "I:\Claire_new\integrations\llama\llama-server.exe",
        "I:\Claire_new\llama\llama-server.exe",
        "I:\ClaireTech\integrations\llama\llama-server.exe",
        "I:\ClaireTech\llama\llama-server.exe",
        "I:\ClaireTech\llama-server.exe"
    )
    foreach ($candidate in $preferred) {
        if (Test-Path $candidate) { return (Get-Item $candidate) }
    }
    return Get-ChildItem -Path $searchRoots -Recurse -Filter "llama-server.exe" -File -ErrorAction SilentlyContinue |
        Sort-Object FullName |
        Select-Object -First 1
}

function Get-ModelPath {
    $preferred = @(
        (Join-Path $root "models"),
        (Join-Path $root "integrations\llama\models"),
        "I:\Claire_new\models",
        "I:\Claire_new\integrations\llama\models",
        "I:\ClaireTech\models",
        "I:\ClaireTech\integrations\llama\models"
    )
    $preferredFiles = Get-ChildItem -Path $preferred `
        -Recurse -Filter *.gguf -File -ErrorAction SilentlyContinue |
        Sort-Object Length, LastWriteTime -Descending
    if ($preferredFiles) {
        return $preferredFiles | Select-Object -First 1
    }
    $modelHints = foreach ($base in $searchRoots) {
        @(
            (Join-Path $base "models"),
            (Join-Path $base "integrations\llama\models"),
            $base
        )
    }
    Get-ChildItem -Path $modelHints `
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
            '-m', ('"{0}"' -f $modelPath.FullName),
            '--alias', $env:CLAIRE_MODEL_ID,
            '--host', '127.0.0.1',
            '--port', '8080',
            '--ctx-size', '4096',
            '--parallel', '2',
            '--no-warmup'
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
