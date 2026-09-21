#Requires -Version 5.1
param([switch]$Force)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$PythonDir = Join-Path $Root "python312"
$PythonExe = Join-Path $PythonDir "python.exe"
$Installer = Join-Path $Root "python-3.12.7-amd64.exe"
$PythonUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"

function Write-Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "OK: $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "WARN: $msg" -ForegroundColor Yellow }

function Invoke-Checked {
    param([string[]]$Command, [string]$Label)
    Write-Host "+ $($Command -join ' ')"
    & @Command
    if ($LASTEXITCODE -ne 0) { throw "$Label a echoue (code $LASTEXITCODE)" }
}

function Test-NvidiaGpu {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        throw "nvidia-smi introuvable. Installe les pilotes NVIDIA."
    }
    $smi = & nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>&1
    if ($LASTEXITCODE -ne 0) { throw "nvidia-smi a echoue: $smi" }
    Write-Ok "GPU: $($smi.Trim())"
}

function Ensure-LocalPython312 {
    if (Test-Path $PythonExe) {
        $ver = & $PythonExe -c "import sys; print(sys.version)" 2>$null
        Write-Ok "Python local deja present: $ver"
        return
    }

    Write-Step "Telechargement Python 3.12.7 (~25 Mo, une seule fois)..."
    if (-not (Test-Path $Installer)) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $PythonUrl -OutFile $Installer -UseBasicParsing
    }

    Write-Step "Installation Python 3.12 dans $PythonDir (sans toucher Windows)..."
    if (Test-Path $PythonDir) { Remove-Item $PythonDir -Recurse -Force -ErrorAction SilentlyContinue }

    $args = @(
        "/quiet",
        "InstallAllUsers=0",
        "PrependPath=0",
        "Include_test=0",
        "Shortcuts=0",
        "AssociateFiles=0",
        "TargetDir=$PythonDir"
    )
    $proc = Start-Process -FilePath $Installer -ArgumentList $args -Wait -PassThru
    if ($proc.ExitCode -ne 0 -or -not (Test-Path $PythonExe)) {
        throw "Installation Python locale echouee (code $($proc.ExitCode))"
    }
    Write-Ok "Python 3.12 installe localement"
}

function Install-Torch($pip) {
    foreach ($idx in @("https://download.pytorch.org/whl/cu124", "https://download.pytorch.org/whl/cu126")) {
        Write-Host "Essai PyTorch: $idx"
        & $pip install torch torchvision torchaudio --index-url $idx
        if ($LASTEXITCODE -eq 0) { Write-Ok "PyTorch OK"; return }
    }
    Invoke-Checked -Command @($pip, "install", "torch", "torchvision", "torchaudio") -Label "PyTorch"
}

Write-Step "ECTS GPU Worker"
Write-Host "Dossier: $Root"
Test-NvidiaGpu
Ensure-LocalPython312

if ($Force -and (Test-Path ".venv")) {
    Write-Warn "Suppression .venv"
    Remove-Item ".venv" -Recurse -Force
}

Write-Step "Environnement virtuel"
if (-not (Test-Path ".venv")) {
    Invoke-Checked -Command @($PythonExe, "-m", "venv", ".venv") -Label "venv"
} else {
    Write-Warn ".venv existant reutilise"
}

$pip = Join-Path $Root ".venv\Scripts\pip.exe"
$py = Join-Path $Root ".venv\Scripts\python.exe"

Write-Step "Dependances (10-20 min, PyTorch + Whisper)..."
Invoke-Checked -Command @($pip, "install", "--upgrade", "pip") -Label "pip"
Install-Torch $pip
Invoke-Checked -Command @($pip, "install", "-r", "requirements.txt") -Label "requirements"

Write-Step "Verification"
Invoke-Checked -Command @($py, "-c", "import httpx, faster_whisper, torch; print('OK'); print('torch', torch.__version__, 'cuda', torch.cuda.is_available())") -Label "imports"

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Warn "Edite .env avec ECTS_GPU_WORKER_TOKEN puis lance run.bat"
} else {
    Write-Ok ".env present"
}

Write-Step "Termine - lance run.bat"
