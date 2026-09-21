import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.models import init_db, get_session_factory
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ECTS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ECTS_REPO_ROOT", str(tmp_path / "repo"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("ECTS_PANEL_USER", "admin")
    monkeypatch.setenv("ECTS_PANEL_PASSWORD", "testpass")
    monkeypatch.setenv("ECTS_PANEL_SECRET", "test-secret")
    get_settings.cache_clear()
    settings = get_settings()
    settings.ects_data_dir.mkdir(parents=True)
    settings.ects_repo_root.mkdir(parents=True)
    init_db()
    return TestClient(app)


def test_panel_login_and_upload(client):
    r = client.get("/panel", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"

    r = client.post("/login", data={"username": "admin", "password": "testpass"}, follow_redirects=False)
    assert r.status_code == 303

    files = [("files", ("syllabus.txt", b"Contenu syllabus test", "text/plain"))]
    data = {"subject": "Psychologie", "session_date": "2026-09-21"}
    r = client.post("/panel/upload", data=data, files=files, follow_redirects=False)
    assert r.status_code == 303
    assert "/panel" in r.headers["location"]

    r = client.get("/panel")
    assert r.status_code == 200
    assert "Psychologie" in r.text
