@echo off
cd /d "%~dp0"
title ECTS GPU Worker (Docker)

where docker >nul 2>&1
if errorlevel 1 (
    echo.
    echo Docker Desktop est requis.
    echo Telecharge: https://www.docker.com/products/docker-desktop/
    echo Puis redemarre le PC et relance run-docker.bat
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    copy .env.example .env >nul
    echo.
    echo Fichier .env cree.
    echo Ouvre .env et colle ECTS_GPU_WORKER_TOKEN du VPS.
    echo Puis relance run-docker.bat
    echo.
    pause
    exit /b 1
)

echo.
echo ECTS GPU Worker - Docker
echo 1ere fois: build image + telechargement modele Whisper ^(10-20 min^)
echo Laisse cette fenetre ouverte.
echo.
docker compose up --build
pause
