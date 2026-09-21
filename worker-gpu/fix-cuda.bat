@echo off
cd /d "%~dp0"
title Fix CUDA ECTS GPU Worker
echo Installation libs CUDA dans le venv...
.\.venv\Scripts\python.exe -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-runtime-cu12
echo.
echo Verification cublas64_12.dll...
.\.venv\Scripts\python.exe -c "from pathlib import Path; p=Path('.venv/Lib/site-packages/nvidia/cublas/bin/cublas64_12.dll'); print('OK' if p.exists() else 'MANQUANT', p)"
echo.
echo Relance run.bat
pause
