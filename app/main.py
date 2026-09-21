import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import get_settings
from app.db.models import get_session_factory, init_db
from app.services.pipeline import JobRunner, Pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ects")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ects_data_dir.mkdir(parents=True, exist_ok=True)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    init_db()

    pipeline = Pipeline()
    runner = JobRunner(get_session_factory, pipeline)
    runner.start()
    app.state.runner = runner

    async def intake_task():
        from app.services.drive import IntakeService

        intake = IntakeService(get_session_factory)
        while True:
            try:
                intake.scan_all()
            except Exception:
                logger.exception("Intake failed")
            await asyncio.sleep(30)

    task = asyncio.create_task(intake_task())
    yield
    task.cancel()


app = FastAPI(title="ECTS", version="0.1.0", lifespan=lifespan)
app.include_router(router)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
