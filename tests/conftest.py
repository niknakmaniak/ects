"""Fixtures partagées pour tests ECTS."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.models import init_db


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ECTS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ECTS_REPO_ROOT", str(tmp_path / "repo"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("ECTS_API_TOKEN", "test-api-token")
    monkeypatch.setenv("ECTS_GPU_WORKER_TOKEN", "test-gpu-token")
    monkeypatch.setenv("ECTS_PANEL_USER", "admin")
    monkeypatch.setenv("ECTS_PANEL_PASSWORD", "testpass")
    monkeypatch.setenv("ECTS_PANEL_SECRET", "test-secret-key-for-sessions")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    settings = get_settings()
    settings.ects_data_dir.mkdir(parents=True, exist_ok=True)
    settings.ects_repo_root.mkdir(parents=True, exist_ok=True)
    (settings.ects_repo_root / "templates" / "latex").mkdir(parents=True)
    for name in ("syllabus.tex", "audit.tex", "synthese.tex", "ects.cls"):
        src = ROOT / "templates" / "latex" / name
        if src.exists():
            (settings.latex_templates_dir / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    init_db()
    return settings


ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


@pytest.fixture
def db(app_env):
    from app.db.models import get_session_factory

    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(app_env):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def logged_in_client(client):
    r = client.post("/login", data={"username": "admin", "password": "testpass"}, follow_redirects=False)
    assert r.status_code == 303
    return client


@pytest.fixture
def git_repo(app_env, tmp_path):
    from git import Repo

    repo_path = app_env.ects_repo_root
    Repo.init(repo_path)
    (repo_path / "README.md").write_text("# test\n", encoding="utf-8")
    repo = Repo(repo_path)
    repo.index.add(["README.md"])
    repo.index.commit("init")
    return repo
