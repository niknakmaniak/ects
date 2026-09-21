$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Add-CudaToPath {
    $site = Join-Path $Root ".venv\Lib\site-packages"
    $paths = @(
        (Join-Path $site "torch\lib"),
        (Join-Path $site "nvidia\cublas\bin"),
        (Join-Path $site "nvidia\cudnn\bin"),
        (Join-Path $site "nvidia\cuda_runtime\bin"),
        (Join-Path $site "ctranslate2")
    )
    foreach ($p in $paths) {
        if (Test-Path $p) {
            $env:PATH = "$p;$env:PATH"
        }
    }
    $env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
}

if (-not (Test-Path ".venv")) {
    Write-Host "Premiere installation detectee - lancement install.ps1"
    powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\install.ps1"
}

if (Test-Path ".env") {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

Add-CudaToPath
& "$Root\.venv\Scripts\python.exe" "$Root\worker.py"
