#Requires -Version 5.1
<#
.SYNOPSIS
  Installation automatique ECTS GPU Worker (Windows + NVIDIA).
.DESCRIPTION
  - Installe Python 3.12 via winget si absent
  - Verifie nvidia-smi (GPU NVIDIA)
  - Cree venv, installe PyTorch CUDA + faster-whisper
  - Prepare .env si manquant
#>
param(
    [switch]$SkipPythonInstall,
    [switch]$SkipGpuCheck
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "OK: $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "WARN: $msg" -ForegroundColor Yellow }

function Get-PythonCmd {
    foreach ($cmd in @("python", "py")) {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) {
            $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver -and ([version]$ver -ge [version]"3.11")) {
                return $cmd
            }
        }
    }
    return $null
}

function Install-Python {
    if ($SkipPythonInstall) {
        throw "Python 3.11+ requis. Installe-le depuis https://python.org ou relance sans -SkipPythonInstall"
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Python introuvable et winget absent. Installe Python 3.12 manuellement (cocher Add to PATH)."
    }
    Write-Step "Installation Python 3.12 via winget..."
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    Start-Sleep -Seconds 3
    $py = Get-PythonCmd
    if (-not $py) { throw "Python installe mais introuvable. Redemarre PowerShell puis relance install.ps1" }
    return $py
}

function Test-NvidiaGpu {
    if ($SkipGpuCheck) {
        Write-Warn "Verification GPU ignoree (-SkipGpuCheck)"
        return
    }
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        throw "nvidia-smi introuvable. Installe les pilotes NVIDIA (GPU requis pour Whisper CUDA)."
    }
    $smi = & nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>&1
    if ($LASTEXITCODE -ne 0) { throw "nvidia-smi a echoue: $smi" }
    Write-Ok "GPU detecte: $($smi.Trim())"
}

Write-Step "ECTS GPU Worker — installation"
Write-Host "Dossier: $Root"

Test-NvidiaGpu

$python = Get-PythonCmd
if (-not $python) { $python = Install-Python }
Write-Ok "Python: $python"

Write-Step "Creation environnement virtuel"
if (Test-Path ".venv") {
    Write-Warn ".venv existe deja — reutilisation"
} else {
    & $python -m venv .venv
}

$pip = Join-Path $Root ".venv\Scripts\pip.exe"
$pyvenv = Join-Path $Root ".venv\Scripts\python.exe"

Write-Step "Installation dependances (peut prendre 10-15 min)..."
& $pip install --upgrade pip
& $pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
& $pip install -r requirements.txt

Write-Step "Verification imports"
& $pyvenv -c "import httpx; import faster_whisper; print('imports OK')"

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Warn "Fichier .env cree — verifie ECTS_GPU_WORKER_TOKEN"
} else {
    Write-Ok ".env present"
}

Write-Step "Installation terminee"
Write-Host @"

Prochaine etape:
  .\run.ps1

Le worker poll http://148.113.242.154:8080 et transcrit l'audio localement.
"@ -ForegroundColor Green
