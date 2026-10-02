"""Protección contra abusos: correos temporales, cuentas por conexión, límites diarios y de peticiones."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from clipaso.infra.config import AbuseSettings, Settings
from clipaso.interfaces.api.app import create_app
from clipaso.interfaces.api.routers.admin import duplicates
from clipaso.saas import abuse, editing
from clipaso.saas.db import session_scope, utcnow
from clipaso.saas.errors import AppError
from clipaso.saas.models import Job, JobStatus, Task, TaskKind, Upload, User


def bearer(email: str) -> dict:
    return {"Authorization": f"Bearer dev:{email}"}


def test_disposable_email_is_rejected(client):
    assert abuse.is_disposable("x@yopmail.com") and abuse.is_disposable("x@mx.mailinator.com")
    assert not abuse.is_disposable("ana@gmail.com")
    r = client.get("/me", headers=bearer("tira@yopmail.com"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "email_disposable"
    r = client.post("/signup-check", json={"email": "tira@yopmail.com"})
    assert r.json()["error"]["code"] == "email_disposable"
    assert client.post("/signup-check", json={"email": "ana@gmail.com"}).status_code == 204


def test_free_accounts_per_connection(client):
    for i in range(3):
        assert client.get("/me", headers=bearer(f"u{i}@example.com")).status_code == 200
    assert client.post("/signup-check", json={"email": "u9@example.com"}).json()["error"]["code"] == "too_many_accounts"
    r = client.get("/me", headers=bearer("u9@example.com"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "too_many_accounts"
    # Las cuentas que ya existen siguen entrando.
    assert client.get("/me", headers=bearer("u0@example.com")).status_code == 200


def test_developer_accounts_skip_signup_limits(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", output_dir=tmp_path / "out", _env_file=None,
                        admin_emails=["yo@example.com"], abuse=AbuseSettings(accounts_per_ip=0))
    with TestClient(create_app(settings)) as c:
        assert c.get("/me", headers=bearer("yo@example.com")).json()["is_admin"] is True


def test_rate_limit(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", output_dir=tmp_path / "out", _env_file=None,
                        abuse=AbuseSettings(requests_per_minute=5))
    with TestClient(create_app(settings)) as c:
        codes = [c.get("/me", headers=bearer("ana@example.com")).status_code for _ in range(6)]
        assert codes == [200] * 5 + [429]
        assert c.get("/me", headers=bearer("ana@example.com")).json()["error"]["code"] == "rate_limited"
        assert c.get("/health").status_code == 200


def test_rate_limiter_window():
    limiter = abuse.RateLimiter()
    assert all(limiter.allow("k", 2, now=t) for t in (0.0, 1.0))
    assert not limiter.allow("k", 2, now=2.0)
    assert limiter.allow("k", 2, now=61.0)


@pytest.mark.parametrize(("kind", "field", "limit"), [
    (TaskKind.RENDER_CLIP, "daily_renders", 10), (TaskKind.MORE_CLIPS, "daily_more_clips", 2),
    (TaskKind.EXPORT_CLIP, "daily_exports", 5), (TaskKind.COVER_CLIP, "daily_covers", 5),
])
def test_daily_limits(client, kind, field, limit):
    client.get("/me", headers=bearer("ana@example.com"))
    now = utcnow()
    with session_scope(client.app.state.sessions) as s:
        user = s.query(User).one()
        editing.record_daily(s, user, field, now - timedelta(days=2))  # de otro día: no cuenta
        for _ in range(limit - 1):
            editing.record_daily(s, user, field, now)
        s.flush()
        editing.check_daily_limit(s, user, kind, now)
        editing.record_daily(s, user, field, now)
        s.flush()
        with pytest.raises(AppError) as err:
            editing.check_daily_limit(s, user, kind, now)
        assert err.value.status == 429 and err.value.key == field
        user.plan_code = "dev"
        s.flush()
        s.expire(user, ["plan"])
        editing.check_daily_limit(s, user, kind, now)  # la cuenta de desarrollo no tiene tope


def test_daily_quota_survives_deleting_projects_and_ignores_failures(client):
    """Borrar el proyecto no devuelve el cupo; una tarea que falla, sí."""
    from clipaso.saas.tasks import TaskRunner

    client.get("/me", headers=bearer("ana@example.com"))
    now = utcnow()
    with session_scope(client.app.state.sessions) as s:
        user = s.query(User).one()
        upload = Upload(user_id=user.id, storage_key="k", filename="v.mp4", content_type="video/mp4", size_bytes=1)
        s.add(upload)
        s.flush()
        job = Job(user_id=user.id, upload_id=upload.id, title="t", status=JobStatus.DONE, stage="done",
                  video_minutes=1, max_clips=1, options={}, created_at=now, expires_at=now + timedelta(days=7))
        s.add(job)
        s.flush()
        ok = editing._queue(s, user, Task(user_id=user.id, job_id=job.id, kind=TaskKind.MORE_CLIPS, payload={},
                                          created_at=now), now)
        failed = editing._queue(s, user, Task(user_id=user.id, job_id=job.id, kind=TaskKind.MORE_CLIPS,
                                              payload={}, created_at=now), now)
        assert editing.daily_used(s, user, "daily_more_clips", now) == 2
        TaskRunner._finish_failed(None, s, failed, "processing_failed")
        s.flush()
        assert editing.daily_used(s, user, "daily_more_clips", now) == 1
        s.delete(job)  # borra también sus tareas
        s.flush()
        assert ok.id and editing.daily_used(s, user, "daily_more_clips", now) == 1
        editing.check_daily_limit(s, user, TaskKind.MORE_CLIPS, now)  # Gratis: 2 al día; queda 1
        editing.record_daily(s, user, "daily_more_clips", now)
        s.flush()
        with pytest.raises(AppError):
            editing.check_daily_limit(s, user, TaskKind.MORE_CLIPS, now)


def test_same_video_in_several_free_accounts_is_flagged():
    now = utcnow()
    owners = {"a": SimpleNamespace(email="a@x.com", plan_code="free"),
              "b": SimpleNamespace(email="b@x.com", plan_code="free"),
              "c": SimpleNamespace(email="c@x.com", plan_code="pro")}

    def job(user_id, fp):
        return SimpleNamespace(user_id=user_id, options={"source_fp": fp}, title="Charla", video_minutes=4.0,
                               created_at=now)

    flagged = duplicates([job("a", "1:2.0"), job("b", "1:2.0"), job("a", "9:9.0"), job("c", "9:9.0")], owners)
    assert [(d.users, d.jobs) for d in flagged] == [(["a@x.com", "b@x.com"], 2)]


def test_cover_shortlist_prefers_frames_with_faces():
    """Una diapositiva nítida no gana a un fotograma con cara (el texto de la portada chocaría con el suyo)."""
    from clipaso.saas import covers

    slide = covers.Frame(time=1.0, image=None, face_x=None, score=0.9)
    face = covers.Frame(time=5.0, image=None, face_x=0.5, score=0.6)
    assert [f.time for f in covers.shortlist([slide, face])] == [5.0]
    assert [f.time for f in covers.shortlist([slide])] == [1.0]  # sin caras, se usa lo que hay
