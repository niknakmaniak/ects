@echo off
cd /d "%~dp0"
if not exist ".venv" (
    echo Premiere installation...
    call "%~dp0install.bat"
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
pause
