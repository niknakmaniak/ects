import logging
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


async def publish_to_drive(job, work: Path):
    settings = get_settings()
    if not settings.google_service_account_file or not settings.drive_finished_folder_id:
        logger.info("Drive non configuré — publication locale uniquement pour %s", job.slug)
        return

    try:
        from app.services.drive import DriveClient

        client = DriveClient()
        out_dir = work / "output"
        for pdf in out_dir.glob("*.pdf"):
            client.upload_file(pdf, settings.drive_finished_folder_id, f"{job.slug}_{pdf.name}")
        logger.info("Publié sur Drive: %s", job.slug)
    except Exception as e:
        logger.warning("Publication Drive échouée: %s", e)
