param(
    [ValidateSet("api", "test", "gpu")]
    [string]$Mode = "api"
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$py = Join-Path $Root ".venv\Scripts\python.exe"
$pip = Join-Path $Root ".venv\Scripts\pip.exe"

& $pip install -r requirements.txt -q

switch ($Mode) {
    "api" {
        if (-not (Test-Path ".env")) { Copy-Item .env.example .env }
        & $py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
    }
    "test" {
        & $py -m pytest tests/ -v
    }
    "gpu" {
        & $py worker-gpu/worker.py @args
    }
}
