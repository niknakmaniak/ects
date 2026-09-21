import json
import logging
import time
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import get_settings
from app.db.models import get_session_factory, init_db
from app.services.jobs import create_job, parse_session_folder

logger = logging.getLogger(__name__)


class DriveClient:
    SCOPES = ["https://www.googleapis.com/auth/drive"]

    def __init__(self):
        settings = get_settings()
        creds = service_account.Credentials.from_service_account_file(
            settings.google_service_account_file, scopes=self.SCOPES
        )
        self.service = build("drive", "v3", credentials=creds)

    def list_folders(self, parent_id: str) -> list[dict]:
        q = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        res = self.service.files().list(q=q, fields="files(id,name)").execute()
        return res.get("files", [])

    def folder_has_ready(self, folder_id: str) -> bool:
        q = f"'{folder_id}' in parents and name='READY.txt' and trashed=false"
        res = self.service.files().list(q=q, fields="files(id)").execute()
        return bool(res.get("files"))

    def download_folder(self, folder_id: str, dest: Path):
        dest.mkdir(parents=True, exist_ok=True)
        q = f"'{folder_id}' in parents and trashed=false"
        res = self.service.files().list(q=q, fields="files(id,name,mimeType)").execute()
        for f in res.get("files", []):
            if f["mimeType"] == "application/vnd.google-apps.folder":
                self.download_folder(f["id"], dest / f["name"])
            else:
                content = self.service.files().get_media(fileId=f["id"]).execute()
                (dest / f["name"]).write_bytes(content)

    def upload_file(self, path: Path, parent_id: str, name: str | None = None):
        meta = {"name": name or path.name, "parents": [parent_id]}
        media = MediaFileUpload(str(path), resumable=True)
        self.service.files().create(body=meta, media_body=media, fields="id").execute()


class LocalInboxWatcher:
    """Fallback dev : surveille data/inbox/."""

    def __init__(self, inbox: Path, processed: set[str]):
        self.inbox = inbox
        self.processed = processed
        self.inbox.mkdir(parents=True, exist_ok=True)

    def scan(self) -> list[Path]:
        found = []
        for d in self.inbox.iterdir():
            if not d.is_dir():
                continue
            if (d / "READY.txt").exists() and d.name not in self.processed:
                found.append(d)
        return found


class IntakeService:
    def __init__(self, db_factory):
        self.db_factory = db_factory
        settings = get_settings()
        self.processed: set[str] = set()
        self.local_watcher = LocalInboxWatcher(settings.ects_data_dir / "inbox", self.processed)
        self.drive = None
        if settings.google_service_account_file and settings.drive_inbox_folder_id:
            try:
                self.drive = DriveClient()
            except Exception as e:
                logger.warning("Drive client init failed: %s", e)

    def ingest_local(self, folder: Path):
        parsed = parse_session_folder(folder.name)
        if not parsed:
            logger.warning("Nom de dossier invalide: %s", folder.name)
            return None
        subject, session_date = parsed
        slug = folder.name
        db = self.db_factory()()
        try:
            job = create_job(db, folder, slug, subject, session_date)
            self.processed.add(slug)
            return job
        finally:
            db.close()

    def ingest_drive_folder(self, folder_id: str, name: str):
        settings = get_settings()
        parsed = parse_session_folder(name)
        if not parsed:
            return None
        subject, session_date = parsed
        slug = name
        dest = settings.ects_data_dir / "inbox" / slug
        self.drive.download_folder(folder_id, dest)
        (dest / "READY.txt").touch()
        return self.ingest_local(dest)

    def scan_all(self) -> list:
        jobs = []
        for folder in self.local_watcher.scan():
            job = self.ingest_local(folder)
            if job:
                jobs.append(job)

        if self.drive and get_settings().drive_inbox_folder_id:
            for f in self.drive.list_folders(get_settings().drive_inbox_folder_id):
                if self.drive.folder_has_ready(f["id"]) and f["name"] not in self.processed:
                    job = self.ingest_drive_folder(f["id"], f["name"])
                    if job:
                        jobs.append(job)
        return jobs


async def intake_loop(db_factory, interval: int = 30):
    intake = IntakeService(db_factory)
    while True:
        try:
            intake.scan_all()
        except Exception:
            logger.exception("Intake scan failed")
        time.sleep(interval)
