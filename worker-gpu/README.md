# ECTS GPU Worker (ASUS)

Installation **automatique** sur Windows + NVIDIA.

## Quick start

```powershell
# Extraire le zip, puis :
.\install.ps1   # installe Python (winget) si besoin, GPU check, deps
.\run.ps1       # lance le worker (relance install.ps1 si .venv absent)
```

## Ce que install.ps1 fait

1. Verifie `nvidia-smi` (pilotes NVIDIA)
2. Installe **Python 3.12** via `winget` si absent
3. Cree `.venv`, installe PyTorch CUDA + faster-whisper
4. Cree `.env` depuis `.env.example` si manquant

Options :

```powershell
.\install.ps1 -SkipGpuCheck      # PC sans NVIDIA (debug seulement)
.\install.ps1 -SkipPythonInstall # Python deja installe manuellement
```

## Configuration (.env)

| Variable | Description |
|----------|-------------|
| `GPU_WORKER_URL` | `http://148.113.242.154:8080` |
| `ECTS_GPU_WORKER_TOKEN` | Token du VPS |
| `WHISPER_MODEL` | `large-v3` |
