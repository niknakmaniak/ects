#Requires -Version 5.1
param(
    [switch]$SkipPythonInstall,
    [switch]$SkipGpuCheck,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-Step($msg) { Write-Host "" ; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "OK: $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "WARN: $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "ERREUR: $msg" -ForegroundColor Red }

function Invoke-Checked {
    param([string[]]$Command, [string]$Label)
    Write-Host "+ $($Command -join ' ')"
    & @Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label a echoue (code $LASTEXITCODE)"
    }
}

function Get-PythonVersion($cmd, [string[]]$args = @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")) {
    try {
        $ver = & $cmd @args 2>$null
        if ($LASTEXITCODE -ne 0 -and -not $ver) { return $null }
        return $ver.ToString().Trim()
    } catch {
        return $null
    }
}

function Find-Python312Path {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $lines = & py -0p 2>$null
        foreach ($line in $lines) {
            if ($line -notmatch '3\.12') { continue }
            $exe = ($line -split '\s+')[-1]
            if ($exe -like '*.exe' -and (Test-Path $exe)) { return $exe }
        }
    }
    foreach ($p in @(
        "$env:LocalAppData\Programs\Python\Python312\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "${env:ProgramFiles(x86)}\Python312\python.exe"
    )) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Resolve-Python312 {
    $direct = Find-Python312Path
    if ($direct) {
        return @{ Cmd = $direct; Args = @() }
    }
    return $null
}

function Install-Python312 {
    if ($SkipPythonInstall) {
        throw "Python 3.12 requis. Installe-le depuis https://python.org/downloads/release/python-3120/"
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Python 3.12 introuvable et winget absent. Installe Python 3.12 manuellement (cocher Add to PATH)."
    }
    Write-Step "Installation Python 3.12 via winget..."
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    Start-Sleep -Seconds 8
    $resolved = Resolve-Python312
    if (-not $resolved) {
        $resolved = @{ Cmd = (Find-Python312Path); Args = @() }
    }
    if (-not $resolved.Cmd) {
        throw "Python 3.12 introuvable. Utilise run-docker.bat (Docker Desktop) - plus simple."
    }
    return $resolved
}

function Test-NvidiaGpu {
    if ($SkipGpuCheck) {
        Write-Warn "Verification GPU ignoree (-SkipGpuCheck)"
        return
    }
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        throw "nvidia-smi introuvable. Installe les pilotes NVIDIA."
    }
    $smi = & nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>&1
    if ($LASTEXITCODE -ne 0) { throw "nvidia-smi a echoue: $smi" }
    Write-Ok "GPU detecte: $($smi.Trim())"
}

function Install-Torch($pip) {
    $indexes = @(
        "https://download.pytorch.org/whl/cu124",
        "https://download.pytorch.org/whl/cu126"
    )
    foreach ($idx in $indexes) {
        Write-Host "Essai PyTorch depuis $idx ..."
        & $pip install torch torchvision torchaudio --index-url $idx
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "PyTorch installe ($idx)"
            return
        }
    }
    Write-Warn "Index CUDA indisponible, essai PyPI standard..."
    Invoke-Checked -Command @($pip, "install", "torch", "torchvision", "torchaudio") -Label "PyTorch"
}

Write-Step "ECTS GPU Worker - installation"
Write-Host "Dossier: $Root"

Test-NvidiaGpu

$py = Resolve-Python312
if (-not $py) { $py = Install-Python312 }
$pythonCmd = $py.Cmd
$pythonArgs = $py.Args
$ver = if ($pythonArgs.Count -gt 0) { Get-PythonVersion $pythonCmd $pythonArgs[0..($pythonArgs.Count-1)] } else { Get-PythonVersion $pythonCmd }
Write-Ok "Python 3.12 via: $pythonCmd $($pythonArgs -join ' ') (detecte $ver)"

if ($Force -and (Test-Path ".venv")) {
    Write-Warn "Suppression .venv existant (-Force)"
    Remove-Item ".venv" -Recurse -Force
}

if (Test-Path ".venv") {
    $venvVer = & ".\.venv\Scripts\python.exe" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($venvVer -ne "3.12") {
        Write-Warn ".venv en Python $venvVer - recreation en 3.12"
        Remove-Item ".venv" -Recurse -Force
    }
}

Write-Step "Creation environnement virtuel (Python 3.12 obligatoire)"
if (Test-Path ".venv") {
    Write-Warn ".venv existe deja - reutilisation"
} else {
    if ($pythonArgs.Count -gt 0) {
        Invoke-Checked -Command @($pythonCmd) + $pythonArgs + @("-m", "venv", ".venv") -Label "venv"
    } else {
        Invoke-Checked -Command @($pythonCmd, "-m", "venv", ".venv") -Label "venv"
    }
}

$pip = Join-Path $Root ".venv\Scripts\pip.exe"
$pyvenv = Join-Path $Root ".venv\Scripts\python.exe"

Write-Step "Installation dependances (10-20 min)..."
Invoke-Checked -Command @($pip, "install", "--upgrade", "pip") -Label "pip upgrade"
Install-Torch $pip
Invoke-Checked -Command @($pip, "install", "-r", "requirements.txt") -Label "requirements"

Write-Step "Verification imports"
Invoke-Checked -Command @($pyvenv, "-c", "import httpx; import faster_whisper; import torch; print('imports OK'); print('torch', torch.__version__, 'cuda', torch.cuda.is_available())") -Label "imports"

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Warn "Fichier .env cree - verifie ECTS_GPU_WORKER_TOKEN"
} else {
    Write-Ok ".env present"
}

Write-Step "Installation terminee"
Write-Host "Prochaine etape: run.bat" -ForegroundColor Green
