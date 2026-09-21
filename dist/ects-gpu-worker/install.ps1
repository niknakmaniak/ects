$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

python -m venv .venv
& "$Root\.venv\Scripts\pip.exe" install --upgrade pip
& "$Root\.venv\Scripts\pip.exe" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
& "$Root\.venv\Scripts\pip.exe" install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Édite .env avec ton ECTS_GPU_WORKER_TOKEN puis lance .\run.ps1"
}
