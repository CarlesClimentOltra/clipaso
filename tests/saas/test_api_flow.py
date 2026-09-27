from __future__ import annotations

import shutil
import subprocess
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from smartcuts.domain.errors import SelectionError
from smartcuts.domain.models import ExportedClip
from smartcuts.infra.config import Settings
from smartcuts.interfaces.api.app import create_app
from smartcuts.saas import worker as worker_mod
from smartcuts.saas.db import session_scope, utcnow
from smartcuts.saas.models import Job, JobStatus, UsageEvent
from smartcuts.saas.worker import JobRunner

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="necesita ffmpeg")

AUTH = {"Authorization": "Bearer dev:ana@example.com"}


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory) -> Path:
    """Vídeo real de 3 s (para que ffprobe lea su duración)."""
    path = tmp_path_factory.mktemp("media") / "charla.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=25:duration=3",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-shortest", "-c:v", "libx264", "-c:a", "aac",
         str(path)],
        check=True,
    )
    return path


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path / "data", output_dir=tmp_path / "out", _env_file=None)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


def put_parts(client: TestClient, upload_id: str, data: bytes, part_size: int, numbers: list[int]) -> dict[int, str]:
    """Sube las partes indicadas como lo haría el navegador; devuelve {número: ETag}."""
    urls = client.post(f"/uploads/{upload_id}/parts", json={"part_numbers": numbers}, headers=AUTH)
    assert urls.status_code == 200, urls.text
    etags = {}
    for item in urls.json()["urls"]:
        n = item["part_number"]
        chunk = data[(n - 1) * part_size : n * part_size]
        u = urlsplit(item["url"])
        r = client.put(f"{u.path}?{u.query}", content=chunk)
        assert r.status_code == 200, r.text
        etags[n] = r.headers["etag"]
    return etags


def upload_video(client: TestClient, video: Path) -> str:
    data = video.read_bytes()
    r = client.post("/uploads", json={"filename": video.name, "size_bytes": len(data)}, headers=AUTH)
    assert r.status_code == 201, r.text
    upload_id, part_size, count = r.json()["upload_id"], r.json()["part_size"], r.json()["part_count"]
    etags = put_parts(client, upload_id, data, part_size, list(range(1, count + 1)))
    parts = [{"part_number": n, "etag": e} for n, e in etags.items()]
    r = client.post(f"/uploads/{upload_id}/complete", json={"parts": parts}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready" and r.json()["billable_minutes"] == 0.1
    return r.json()["id"]


class FakePipeline:
    """Sustituye al pipeline real: genera un "clip" copiando el vídeo de entrada."""

    def __init__(self, fail: Exception | None = None):
        self.fail = fail

    def run(self, uri, opts, *, out_dir, on_progress):
        on_progress("transcribe", 0.3)
        if self.fail:
            raise self.fail
        out_dir.mkdir(parents=True, exist_ok=True)
        clip = out_dir / "01.mp4"
        shutil.copyfile(uri, clip)
        thumb = out_dir / "01.jpg"
        thumb.write_bytes(b"jpg")
        exp = ExportedClip(rank=1, path=clip, thumbnail=thumb, start=0, end=3, score=0.9, title="Gran momento",
                           reason="Tiene gancho", reframe_mode="face", profile=opts.profile.name)
        return type("R", (), {"exports": [exp], "cost_usd": 0.012})()


def run_worker(client: TestClient, monkeypatch, pipeline: FakePipeline) -> None:
    app = client.app
    monkeypatch.setattr(worker_mod, "build_pipeline", lambda *a, **k: pipeline)
    runner = JobRunner(app.state.settings, app.state.sessions, app.state.storage)
    job_id = runner.claim_next()
    assert job_id
    runner.run(job_id)


def test_requires_auth(client):
    r = client.get("/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "auth_required"


def test_me_starts_on_free_plan(client):
    r = client.get("/me", headers=AUTH)
    body = r.json()
    assert body["plan"]["code"] == "free" and body["usage"]["used_minutes"] == 0


def test_rejects_non_video(client):
    r = client.post("/uploads", json={"filename": "notas.pdf", "size_bytes": 10}, headers=AUTH)
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_format"


def test_full_flow_success(client, sample_video, monkeypatch):
    upload_id = upload_video(client, sample_video)
    r = client.post("/jobs", json={"upload_id": upload_id, "max_clips": 3}, headers=AUTH)
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    assert r.json()["status"] == "queued"
    assert client.get("/me", headers=AUTH).json()["usage"]["used_minutes"] == 0.1  # reservado

    run_worker(client, monkeypatch, FakePipeline())

    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert job["status"] == "done" and job["progress"] == 1.0
    clip = job["clips"][0]
    assert clip["title"] == "Gran momento" and clip["thumbnail_url"]
    video = client.get(urlsplit(clip["download_url"]).path + "?" + urlsplit(clip["download_url"]).query)
    assert video.status_code == 200 and video.content == sample_video.read_bytes()
    assert "attachment" in video.headers["content-disposition"]

    listing = client.get("/jobs", headers=AUTH).json()
    assert [j["id"] for j in listing] == [job_id] and listing[0]["clip_count"] == 1

    # Otro usuario no ve el job.
    other = {"Authorization": "Bearer dev:otro@example.com"}
    assert client.get(f"/jobs/{job_id}", headers=other).status_code == 404

    assert client.delete(f"/jobs/{job_id}", headers=AUTH).status_code == 204
    assert client.get("/jobs", headers=AUTH).json() == []


def test_failure_refunds_minutes(client, sample_video, monkeypatch):
    upload_id = upload_video(client, sample_video)
    job_id = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH).json()["id"]
    run_worker(client, monkeypatch, FakePipeline(fail=SelectionError("La transcripción está vacía")))

    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert job["status"] == "failed" and job["error_code"] == "no_speech"
    assert "voz" in job["error_message"]
    assert client.get("/me", headers=AUTH).json()["usage"]["used_minutes"] == 0


def test_limits_enforced(client, sample_video, monkeypatch):
    upload_id = upload_video(client, sample_video)
    r = client.post("/jobs", json={"upload_id": upload_id, "max_clips": 10}, headers=AUTH)
    assert r.json()["error"]["code"] == "too_many_clips"

    assert client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH).status_code == 201
    r = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH)  # plan gratis: 1 a la vez
    assert r.status_code == 429 and r.json()["error"]["code"] == "too_many_jobs"


def test_quota_exceeded(client, sample_video):
    upload_id = upload_video(client, sample_video)
    sessions = client.app.state.sessions
    with session_scope(sessions) as s:
        s.add(UsageEvent(user_id="dev|ana@example.com", kind="adjust", minutes=30,
                         period=utcnow().strftime("%Y-%m")))
    r = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH)
    assert r.status_code == 402 and r.json()["error"]["code"] == "quota_exceeded"


def test_stale_job_is_requeued_then_failed(client, sample_video):
    upload_id = upload_video(client, sample_video)
    job_id = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH).json()["id"]
    app = client.app
    runner = JobRunner(app.state.settings, app.state.sessions, app.state.storage)
    old = utcnow() - timedelta(hours=1)

    for expected in (JobStatus.QUEUED, JobStatus.FAILED):
        assert runner.claim(job_id) or expected == JobStatus.FAILED
        with session_scope(app.state.sessions) as s:
            job = s.get(Job, job_id)
            job.status, job.heartbeat_at = JobStatus.RUNNING, old
        runner.recover_stale()
        with session_scope(app.state.sessions) as s:
            assert s.get(Job, job_id).status == expected

    with session_scope(app.state.sessions) as s:
        assert s.get(Job, job_id).error_code == "worker_lost"
        total = sum(e.minutes for e in s.scalars(select(UsageEvent).where(UsageEvent.job_id == job_id)))
        assert total == 0


def test_tampered_storage_signature_rejected(client, sample_video):
    r = client.post("/uploads", json={"filename": "a.mp4", "size_bytes": 100}, headers=AUTH)
    urls = client.post(f"/uploads/{r.json()['upload_id']}/parts", json={"part_numbers": [1]}, headers=AUTH)
    url = urlsplit(urls.json()["urls"][0]["url"])
    put = client.put(f"{url.path}?{url.query.replace('max=', 'max=9')}", content=b"x")
    assert put.status_code == 403


@pytest.fixture
def small_parts(monkeypatch):
    """Partes de 16 KB para que el vídeo de prueba se suba en varias partes."""
    from smartcuts.saas import services

    monkeypatch.setattr(services, "MIN_PART_SIZE", 16 * 1024)


def test_multipart_upload_resumes_after_interruption(client, sample_video, small_parts):
    data = sample_video.read_bytes()
    r = client.post("/uploads", json={"filename": "charla.mp4", "size_bytes": len(data)}, headers=AUTH)
    upload_id, part_size, count = r.json()["upload_id"], r.json()["part_size"], r.json()["part_count"]
    assert count >= 2

    # Se sube solo la primera parte y "se corta la conexión".
    first = put_parts(client, upload_id, data, part_size, [1])
    listed = client.get(f"/uploads/{upload_id}/parts", headers=AUTH).json()["parts"]
    assert [p["part_number"] for p in listed] == [1] and listed[0]["etag"] == first[1]

    # Al reanudar solo se suben las que faltan.
    rest = put_parts(client, upload_id, data, part_size, list(range(2, count + 1)))
    parts = [{"part_number": n, "etag": e} for n, e in {**first, **rest}.items()]
    r = client.post(f"/uploads/{upload_id}/complete", json={"parts": parts}, headers=AUTH)
    assert r.status_code == 200 and r.json()["status"] == "ready"


def test_complete_rejects_missing_or_corrupt_parts(client, sample_video, small_parts):
    data = sample_video.read_bytes()
    r = client.post("/uploads", json={"filename": "charla.mp4", "size_bytes": len(data)}, headers=AUTH)
    upload_id, part_size, count = r.json()["upload_id"], r.json()["part_size"], r.json()["part_count"]
    etags = put_parts(client, upload_id, data, part_size, list(range(1, count + 1)))

    missing = [{"part_number": 1, "etag": etags[1]}]
    r = client.post(f"/uploads/{upload_id}/complete", json={"parts": missing}, headers=AUTH)
    assert r.json()["error"]["code"] == "upload_incomplete"

    corrupt = [{"part_number": n, "etag": '"deadbeef"'} for n in etags]
    r = client.post(f"/uploads/{upload_id}/complete", json={"parts": corrupt}, headers=AUTH)
    assert r.json()["error"]["code"] == "upload_incomplete"


def test_abort_upload_removes_parts(client, sample_video, small_parts):
    data = sample_video.read_bytes()
    r = client.post("/uploads", json={"filename": "charla.mp4", "size_bytes": len(data)}, headers=AUTH)
    upload_id, part_size = r.json()["upload_id"], r.json()["part_size"]
    put_parts(client, upload_id, data, part_size, [1])
    assert client.delete(f"/uploads/{upload_id}", headers=AUTH).status_code == 204
    r = client.get(f"/uploads/{upload_id}/parts", headers=AUTH)
    assert r.status_code == 409


def test_original_is_purged_after_success_and_clips_expire(client, sample_video, monkeypatch):
    from smartcuts.saas.maintenance import run_cleanup
    from smartcuts.saas.models import Upload, UploadStatus

    upload_id = upload_video(client, sample_video)
    job_id = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH).json()["id"]
    run_worker(client, monkeypatch, FakePipeline())
    app = client.app
    storage = app.state.storage

    with session_scope(app.state.sessions) as s:
        upload = s.get(Upload, upload_id)
        assert upload.status == UploadStatus.PURGED and storage.size(upload.storage_key) is None
        job = s.get(Job, job_id)
        video_key = job.clips[0].video_key
        assert storage.size(video_key)  # el clip sigue disponible
        job.expires_at = utcnow() - timedelta(minutes=1)

    report = run_cleanup(app.state.settings, app.state.sessions, storage)
    assert report.expired_jobs == 1
    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert job["status"] == "expired" and job["clips"] == []
    assert storage.size(video_key) is None


def test_cleanup_purges_abandoned_uploads(client, sample_video):
    from smartcuts.saas.maintenance import run_cleanup
    from smartcuts.saas.models import Upload, UploadStatus

    upload_id = upload_video(client, sample_video)  # lista pero nunca procesada
    app = client.app
    with session_scope(app.state.sessions) as s:
        s.get(Upload, upload_id).created_at = utcnow() - timedelta(days=2)
    assert run_cleanup(app.state.settings, app.state.sessions, app.state.storage).purged_uploads == 1
    with session_scope(app.state.sessions) as s:
        assert s.get(Upload, upload_id).status == UploadStatus.PURGED


def test_production_settings_are_validated():
    with pytest.raises(ValueError, match="insegura"):
        Settings(env="prod", _env_file=None)


def test_first_login_parallel_requests_create_user_once(client):
    """Regresión: /me y /jobs en paralelo en el primer acceso chocaban al crear el usuario."""
    from concurrent.futures import ThreadPoolExecutor

    headers = {"Authorization": "Bearer dev:nuevo@example.com"}
    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(lambda p: client.get(p, headers=headers).status_code, ["/me", "/jobs"] * 3))
    assert codes == [200] * 6


def test_unexpected_errors_keep_cors_headers(client, monkeypatch):
    from smartcuts.saas import services

    def boom(*a, **k):
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr(services, "list_jobs", boom)
    r = client.get("/jobs", headers={**AUTH, "Origin": "http://localhost:3000"})
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_part_size_stays_within_protocol_limits():
    from smartcuts.saas.services import MAX_PARTS, MIN_PART_SIZE, choose_part_size

    gib = 1024**3
    assert choose_part_size(50 * 1024 * 1024) == MIN_PART_SIZE
    for size in (2 * gib, 20 * gib, 200 * gib):
        part = choose_part_size(size)
        assert part >= MIN_PART_SIZE and -(-size // part) <= MAX_PARTS
