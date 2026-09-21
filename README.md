# ECTS — Education Course Transformation System

Transformation automatique de séances universitaires en :
1. **Rapport d'audit PDF** (6 sections Syll./Sup./audio)
2. **Syllabus PDF** (LaTeX)
3. **Mini-synthèse** (préparer le prochain cours)

## Démarrage rapide (dev)

```bash
cd ects
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"

copy .env.example .env
uvicorn app.main:app --reload --app-dir .
```

Déposer une séance :
```
data/inbox/Psychologie__2026-09-15/
  READY.txt
  syllabus_annuel.txt
  support_prof.txt
  transcription.txt
```

UI : http://127.0.0.1:8080

## Worker GPU (ASUS)

```bash
pip install -e ".[gpu]"
python worker-gpu/worker.py --api-url http://VPS:8080 --token YOUR_GPU_TOKEN
```

LoRA (après 3 sessions validées) :
```bash
python worker-gpu/worker.py --mode lora --subject psychologie
```

## Docker (VPS)

```bash
cd infra
docker compose up -d
```

## Architecture

Voir [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repo Git

https://github.com/niknakmaniak/ects.git

Commits automatiques par matière sous `subjects/{matiere}/sessions/{date}/`.
