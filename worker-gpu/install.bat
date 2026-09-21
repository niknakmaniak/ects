@echo off
cd /d "%~dp0"
title ECTS GPU Worker - Install
echo.
echo Installe Python 3.12 LOCAL dans ce dossier (pas Docker, pas redemarrage).
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Force
if errorlevel 1 (
    echo.
    echo Echec - copie le message ci-dessus.
    pause
    exit /b 1
)
echo.
echo OK. Edite .env si besoin puis double-clic run.bat
pause
