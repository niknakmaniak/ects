@echo off
cd /d "%~dp0"
echo ECTS GPU Worker - installation...
echo Si une install a deja echoue, supprime le dossier .venv puis relance.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Force
if errorlevel 1 (
    echo.
    echo Echec installation. Lis le message ci-dessus.
    pause
    exit /b 1
)
echo.
echo OK. Prochaine etape: double-clic sur run.bat (apres avoir configure .env)
pause
