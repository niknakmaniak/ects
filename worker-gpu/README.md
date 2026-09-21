# ECTS GPU Worker (ASUS)

## Methode simple : Docker (recommandee)

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) + redemarrage PC
2. Extraire le zip
3. Copier `.env.example` -> `.env` (token GPU du VPS)
4. **`run-docker.bat`**

Pas de Python a installer sur Windows. CUDA gere dans le container.

## Methode native (avancee)

Necessite **Python 3.12** (pas 3.13/3.15). Sinon utiliser Docker.

```cmd
install.bat
run.bat
```

## Configuration (.env)

| Variable | Description |
|----------|-------------|
| `GPU_WORKER_URL` | `http://148.113.242.154:8080` |
| `ECTS_GPU_WORKER_TOKEN` | Token du VPS |
| `WHISPER_MODEL` | `large-v3` |
