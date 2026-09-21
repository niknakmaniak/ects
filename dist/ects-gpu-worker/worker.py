#!/usr/bin/env python3
"""Worker GPU ASUS — télécharge l'audio depuis le VPS, transcrit localement, renvoie le texte."""

import argparse
import logging
import os
import tempfile
import time
import uuid
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ects-gpu")


def transcribe_whisper(audio_path: Path, model_name: str) -> str:
    from faster_whisper import WhisperModel

    logger.info("Whisper %s sur %s", model_name, audio_path.name)
    model = WhisperModel(model_name, device="cuda", compute_type="float16")
    segments, _ = model.transcribe(str(audio_path), language="fr")
    return "\n".join(s.text.strip() for s in segments)


def download_audio(client: httpx.Client, job_id: int, filename: str, dest: Path):
    with client.stream("GET", f"/v1/gpu/{job_id}/audio/{filename}") as resp:
        resp.raise_for_status()
        with dest.open("wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)


def poll_and_transcribe(api_url: str, token: str, worker_id: str, model: str):
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=api_url.rstrip("/"), headers=headers, timeout=600) as client:
        logger.info("Worker %s → %s", worker_id, api_url)
        while True:
            resp = client.post("/v1/gpu/claim", params={"worker_id": worker_id})
            if resp.status_code == 401:
                raise SystemExit("Token GPU invalide — vérifie ECTS_GPU_WORKER_TOKEN dans .env")
            resp.raise_for_status()
            data = resp.json()
            if not data:
                time.sleep(10)
                continue

            job_id = data["job_id"]
            fencing = data["fencing_token"]
            slug = data["slug"]
            audio_files = data.get("audio_files", [])
            logger.info("Job %s (%s) — %d fichier(s) audio", job_id, slug, len(audio_files))

            text_parts = []
            with tempfile.TemporaryDirectory(prefix="ects-gpu-") as tmp:
                tmp_path = Path(tmp)
                for name in audio_files:
                    local = tmp_path / name
                    download_audio(client, job_id, name, local)
                    text_parts.append(f"=== {name} ===\n{transcribe_whisper(local, model)}")

            transcription = "\n\n".join(text_parts)
            complete = client.post(
                f"/v1/gpu/{job_id}/complete",
                json={"worker_id": worker_id, "fencing_token": fencing, "transcription": transcription},
            )
            if complete.status_code == 409:
                logger.warning("Fencing stale — un autre worker a repris le job")
            elif complete.status_code == 200:
                logger.info("Transcription envoyée pour job %s", job_id)
            else:
                logger.error("Complete failed (%s): %s", complete.status_code, complete.text)


def main():
    parser = argparse.ArgumentParser(description="ECTS GPU Worker (ASUS)")
    parser.add_argument("--api-url", default=os.getenv("GPU_WORKER_URL", "http://148.113.242.154:8080"))
    parser.add_argument("--token", default=os.getenv("ECTS_GPU_WORKER_TOKEN", ""))
    parser.add_argument("--worker-id", default=os.getenv("WORKER_ID", f"gpu-{uuid.uuid4().hex[:8]}"))
    parser.add_argument("--whisper-model", default=os.getenv("WHISPER_MODEL", "large-v3"))
    args = parser.parse_args()

    if not args.token:
        raise SystemExit("ECTS_GPU_WORKER_TOKEN manquant — copie .env.example vers .env")

    poll_and_transcribe(args.api_url, args.token, args.worker_id, args.whisper_model)


if __name__ == "__main__":
    main()
