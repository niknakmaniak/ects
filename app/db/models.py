import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    WAITING_GPU = "WAITING_GPU"
    PROCESSING = "PROCESSING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    RENDERING = "RENDERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class JobStep(str, enum.Enum):
    INGEST = "INGEST"
    TRANSCRIBE = "TRANSCRIBE"
    EXTRACT = "EXTRACT"
    ALIGN = "ALIGN"
    AUDIT = "AUDIT"
    REVIEW = "REVIEW"
    GENERATE = "GENERATE"
    LATEX = "LATEX"
    SYNTHESIS = "SYNTHESIS"
    GIT = "GIT"
    PUBLISH = "PUBLISH"


class CorrectionStatus(str, enum.Enum):
    PENDING = "PENDING"
    AUTO_APPLIED = "AUTO_APPLIED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SessionJob(Base):
    __tablename__ = "session_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(64), index=True)
    session_date: Mapped[str] = mapped_column(String(10))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    current_step: Mapped[JobStep | None] = mapped_column(Enum(JobStep), nullable=True)
    deadline_at: Mapped[datetime] = mapped_column(DateTime)
    work_path: Mapped[str] = mapped_column(String(512))
    source_commit_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    drive_folder_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_cost_eur: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    corrections: Mapped[list["CorrectionItem"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class CorrectionItem(Base):
    __tablename__ = "correction_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("session_jobs.id"))
    audit_category: Mapped[str] = mapped_column(String(32))
    location: Mapped[str] = mapped_column(String(256))
    original: Mapped[str] = mapped_column(Text)
    proposed: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[str] = mapped_column(Text, default="")
    verdict: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[CorrectionStatus] = mapped_column(Enum(CorrectionStatus), default=CorrectionStatus.PENDING)
    priority: Mapped[str | None] = mapped_column(String(16), nullable=True)

    job: Mapped[SessionJob] = relationship(back_populates="corrections")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("session_jobs.id"))
    kind: Mapped[str] = mapped_column(String(32))
    path: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    job: Mapped[SessionJob] = relationship(back_populates="artifacts")


class GpuLease(Base):
    __tablename__ = "gpu_leases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("session_jobs.id"))
    worker_id: Mapped[str] = mapped_column(String(64))
    fencing_token: Mapped[int] = mapped_column(Integer, default=1)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime)
    task_type: Mapped[str] = mapped_column(String(32))


class SubjectProfile(Base):
    __tablename__ = "subject_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(64), unique=True)
    session_count: Mapped[int] = mapped_column(Integer, default=0)
    profile_json: Mapped[dict] = mapped_column(JSON, default=dict)
    lora_adapter_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_engine():
    settings = get_settings()
    settings.ects_data_dir.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args)


def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def init_db():
    Base.metadata.create_all(get_engine())
