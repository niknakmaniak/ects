# ECTS GPU Worker (ASUS)

Transcrit l'audio **localement** (Whisper + CUDA). L'audio est téléchargé depuis le VPS puis **jamais** renvoyé ailleurs.

## Prérequis

- Windows 11 + NVIDIA RTX (CUDA)
- Python 3.11+
- [CUDA Toolkit](https://developer.nvidia.com/cuda-downloads) compatible avec PyTorch

## Installation

```powershell
cd ects-gpu-worker
python -m venv .venv
.\.venv\Scripts\activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
copy .env.example .env
# Éditer .env : ECTS_GPU_WORKER_TOKEN=...
```

## Lancer

```powershell
.\run.ps1
```

Ou :

```powershell
.\.venv\Scripts\python.exe worker.py
```

Le worker poll le VPS toutes les 10 s. Quand une séance a de l'audio sans transcription, il la traite automatiquement.

## Variables

| Variable | Description |
|----------|-------------|
| `GPU_WORKER_URL` | `http://148.113.242.154:8080` |
| `ECTS_GPU_WORKER_TOKEN` | Token GPU du VPS (`/opt/ects/.env`) |
| `WHISPER_MODEL` | `large-v3` recommandé |
| `WORKER_ID` | Nom libre pour identifier ce PC |
