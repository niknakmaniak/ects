"""Tests panel web."""

from app.db.models import SessionJob


def test_panel_login_and_upload(logged_in_client, db):
    r = logged_in_client.get("/panel", follow_redirects=False)
    assert r.status_code == 200

    files = [("files", ("syllabus.txt", b"Contenu syllabus test", "text/plain"))]
    data = {"subject": "Psychologie", "session_date": "2026-09-21"}
    r = logged_in_client.post("/panel/upload", data=data, files=files, follow_redirects=False)
    assert r.status_code == 303

    job = db.query(SessionJob).filter(SessionJob.subject == "Psychologie").first()
    assert job is not None


def test_panel_requires_auth(client):
    r = client.get("/panel", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
