# ECTS — Architecture V3

## Décisions retenues

| Composant | Choix | Abandonné (COURS_AI_V2) |
|-----------|-------|---------------------------|
| Orchestration | Python FastAPI + job runner simple | n8n métier, queue SKIP LOCKED/fencing/outbox |
| État | PostgreSQL (prod) / SQLite (dev) | Schéma 20 tables + immutabilité complexe |
| Transcription | GPU local (Whisper), file `WAITING_GPU` | — |
| Rédaction | API cloud texte anonymisé | — |
| Rendu | LaTeX → PDF (Tectonic) | Word renderer |
| Fichiers | Google Drive (UX) | Blobs en Postgres |
| Apprentissage | Profils matière + LoRA GPU après 2–3 cours | 23 lots séquentiels |

## Séparation VPS / GPU

- **VPS** : ingest Drive, jobs, extraction, audit, LLM, LaTeX, Git, UI web
- **GPU (ASUS)** : Whisper + fine-tuning LoRA ; poll HTTP via Tailscale
- **Audio** : jamais vers API externe

## Livrables par séance

1. Rapport d'audit PDF (6 sections Syll./Sup./audio)
2. Syllabus PDF (LaTeX)
3. Mini-synthèse (préparer le cours suivant)

## Pipeline

Drive READY → snapshot → [GPU Whisper si besoin] → extract → align 3 sources → CourseIR + audit → validation corrections → syllabus LaTeX → synthèse → Git commit → Drive FINISHED

Deadline par défaut : lendemain 08:00.
