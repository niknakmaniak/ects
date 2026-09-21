#!/usr/bin/env python3
"""Worker GPU ASUS — Whisper + LoRA."""

import argparse
import logging
import os
import time
import uuid
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ects-gpu")


def transcribe_stub(audio_path: Path) -> str:
    return f"[Transcription stub pour {audio_path.name} — installer faster-whisper pour prod]"


def transcribe_whisper(audio_path: Path, model_name: str) -> str:
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(model_name, device="cuda", compute_type="float16")
        segments, _ = model.transcribe(str(audio_path), language="fr")
        return "\n".join(s.text.strip() for s in segments)
    except ImportError:
        logger.warning("faster-whisper non installé — mode stub")
        return transcribe_stub(audio_path)


def poll_and_transcribe(api_url: str, token: str, worker_id: str, model: str):
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=api_url, headers=headers, timeout=120) as client:
        while True:
            resp = client.post("/v1/gpu/claim", params={"worker_id": worker_id})
            if resp.status_code == 401:
                raise SystemExit("Token GPU invalide")
            data = resp.json()
            if not data:
                time.sleep(10)
                continue

            job_id = data["job_id"]
            fencing = data["fencing_token"]
            work = Path(data["work_path"])
            audio_files = data.get("audio_files", [])
            text_parts = []
            for name in audio_files:
                audio = work / "input" / name
                if audio.exists():
                    text_parts.append(transcribe_whisper(audio, model))

            transcription = "\n\n".join(text_parts)
            complete = client.post(
                f"/v1/gpu/{job_id}/complete",
                json={"worker_id": worker_id, "fencing_token": fencing, "transcription": transcription},
            )
            if complete.status_code == 409:
                logger.warning("Fencing stale — job repris par un autre worker")
            elif complete.status_code == 200:
                logger.info("Transcription envoyée pour job %s", job_id)
            else:
                logger.error("Complete failed: %s", complete.text)


def train_lora(subject: str, sessions_dir: Path, output_dir: Path):
    """Entraîne un adapter LoRA quand assez de sessions validées."""
    output_dir.mkdir(parents=True, exist_ok=True)
    adapter_path = output_dir / f"{subject}_lora"
    readme = adapter_path / "README.md"
    adapter_path.mkdir(parents=True, exist_ok=True)
    readme.write_text(
        f"# LoRA adapter — {subject}\n\n"
        "Placeholder : brancher Unsloth/LLaMA-Factory ici avec les paires\n"
        "(course_ir.json → syllabus.tex) des sessions validées.\n",
        encoding="utf-8",
    )
    logger.info("Adapter LoRA placeholder créé: %s", adapter_path)
    return str(adapter_path)


def main():
    parser = argparse.ArgumentParser(description="ECTS GPU Worker")
    parser.add_argument("--api-url", default=os.getenv("GPU_WORKER_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--token", default=os.getenv("ECTS_GPU_WORKER_TOKEN", "gpu-dev-token"))
    parser.add_argument("--worker-id", default=f"gpu-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--whisper-model", default=os.getenv("WHISPER_MODEL", "large-v3"))
    parser.add_argument("--mode", choices=["transcribe", "lora"], default="transcribe")
    parser.add_argument("--subject", default="psychologie")
    args = parser.parse_args()

    if args.mode == "lora":
        train_lora(args.subject, Path("subjects"), Path(os.getenv("LORA_OUTPUT_DIR", "./adapters")))
    else:
        poll_and_transcribe(args.api_url, args.token, args.worker_id, args.whisper_model)


if __name__ == "__main__":
    main()
