from __future__ import annotations

import shutil
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from clipaso.application.cleanup import CutPlan
from clipaso.domain.errors import SelectionError
from clipaso.domain.models import ExportedClip, Sentence, SignalSet, Transcript, Word
from clipaso.infra.config import Settings
from clipaso.saas import worker as worker_mod
from clipaso.saas.db import session_scope, utcnow
from clipaso.saas.dispatch import redispatch_queued
from clipaso.saas.models import Job, JobStatus, Upload, UsageEvent
from clipaso.saas.worker import JobRunner

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="necesita ffmpeg")

AUTH = {"Authorization": "Bearer dev:ana@example.com"}


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


WORDS = [(" Hola", 0.2, 0.5), (" a", 0.5, 0.6), (" todos,", 0.6, 1.0), (" esto", 1.2, 1.5),
         (" es", 1.5, 1.6), (" SmartCus.", 1.6, 2.4), (" Seguimos", 3.0, 3.6), (" luego.", 3.6, 4.2)]
TRANSCRIPT = Transcript(language="es", duration=6.0, sentences=[
    Sentence(index=0, start=0.2, end=2.4, text="Hola a todos, esto es SmartCus.",
             words=[Word(text=w, start=a, end=b) for w, a, b in WORDS[:6]]),
    Sentence(index=1, start=3.0, end=4.2, text="Seguimos luego.",
             words=[Word(text=w, start=a, end=b) for w, a, b in WORDS[6:]]),
])


class FakeResult:
    def __init__(self, exports, cost_usd=0.012):
        self.exports, self.cost_usd = exports, cost_usd
        self.transcript, self.signals = TRANSCRIPT, SignalSet()


class FakePipeline:
    """Sustituye al pipeline real: genera "clips" copiando el vídeo de entrada."""

    def __init__(self, fail: Exception | None = None, clips: int = 1):
        self.fail = fail
        self.clips = clips
        self.calls: list[dict] = []

    def _clip(self, uri, out_dir, rank, start, end, title, profile) -> ExportedClip:
        out_dir.mkdir(parents=True, exist_ok=True)
        clip = out_dir / f"{rank:02d}.mp4"
        shutil.copyfile(uri, clip)
        thumb = out_dir / f"{rank:02d}.jpg"
        thumb.write_bytes(b"jpg")
        return ExportedClip(rank=rank, path=clip, thumbnail=thumb, start=start, end=end, score=0.9, title=title,
                            reason="Tiene gancho", description="Mira esto hasta el final", hashtags=["ia", "clips"],
                            reframe_mode="face", profile=profile.name)

    def run(self, uri, opts, *, out_dir, on_progress=None, transcript=None, signals=None):
        self.calls.append({"kind": "run", "opts": opts, "reused_analysis": transcript is not None})
        if on_progress:
            on_progress("transcribe", 0.3)
        if self.fail:
            raise self.fail
        exports = [self._clip(uri, out_dir, opts.first_rank + i, 3.0 * i, 3.0 * i + 3, "Gran momento", opts.profile)
                   for i in range(self.clips)]
        return FakeResult(exports)

    def subtitle(self, uri, opts, *, out_dir, translate_to=None, on_progress=None):
        self.calls.append({"kind": "subtitle", "opts": opts, "translate_to": translate_to})
        if self.fail:
            raise self.fail
        return FakeResult([self._clip(uri, out_dir, 1, 0.0, 3.0, opts.title or "Vídeo", opts.profile)])

    def clean(self, uri, opts, *, out_dir, pace="normal", remove_fillers=True, translate_to=None, on_progress=None):
        self.calls.append({"kind": "clean", "opts": opts, "pace": pace, "fillers": remove_fillers,
                           "translate_to": translate_to})
        if self.fail:
            raise self.fail
        out_dir.mkdir(parents=True, exist_ok=True)
        cleaned = out_dir / "limpio.mp4"
        shutil.copyfile(uri, cleaned)
        result = FakeResult([self._clip(uri, out_dir, 1, 0.0, 2.5, opts.title or "Vídeo", opts.profile)])
        result.source = SimpleNamespace(path=cleaned)
        return result, CutPlan(cuts=[(1.0, 1.5)], pauses=1, fillers=2, original=3.0)

    def render(self, uri, opts, clip, rank, transcript, out_dir):
        self.calls.append({"kind": "render", "opts": opts, "clip": clip, "transcript": transcript})
        if self.fail:
            raise self.fail
        return self._clip(uri, out_dir, rank, clip.start, clip.end, clip.title, opts.profile)


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
    from clipaso.saas import services

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


def test_original_is_purged_after_success_if_not_kept(client, sample_video, monkeypatch):
    from clipaso.saas.maintenance import run_cleanup
    from clipaso.saas.models import Upload, UploadStatus

    upload_id = upload_video(client, sample_video)
    job_id = client.post("/jobs", json={"upload_id": upload_id, "keep_source": False}, headers=AUTH).json()["id"]
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


def test_kept_original_and_analysis_are_deleted_when_project_expires(client, sample_video, monkeypatch):
    from clipaso.saas.artifacts import transcript_key
    from clipaso.saas.maintenance import run_cleanup
    from clipaso.saas.models import Upload, UploadStatus

    upload_id = upload_video(client, sample_video)
    job_id = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH).json()["id"]
    run_worker(client, monkeypatch, FakePipeline())
    app, storage = client.app, client.app.state.storage
    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert job["can_edit"] is True and job["options"]["keep_source"] is True

    with session_scope(app.state.sessions) as s:
        upload = s.get(Upload, upload_id)
        assert upload.status == UploadStatus.READY and storage.size(upload.storage_key)  # se conserva
        assert storage.size(transcript_key(upload.user_id, job_id))
        s.get(Job, job_id).expires_at = utcnow() - timedelta(minutes=1)

    run_cleanup(app.state.settings, app.state.sessions, storage)
    assert _stored_files(client) == []
    assert client.get(f"/jobs/{job_id}", headers=AUTH).json()["can_edit"] is False


def test_cleanup_purges_abandoned_uploads(client, sample_video):
    from clipaso.saas.maintenance import run_cleanup
    from clipaso.saas.models import Upload, UploadStatus

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
    from clipaso.saas import services

    def boom(*a, **k):
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr(services, "list_jobs", boom)
    r = client.get("/jobs", headers={**AUTH, "Origin": "http://localhost:3000"})
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_part_size_stays_within_protocol_limits():
    from clipaso.saas.services import MAX_PARTS, MIN_PART_SIZE, choose_part_size

    gib = 1024**3
    assert choose_part_size(50 * 1024 * 1024) == MIN_PART_SIZE
    for size in (2 * gib, 20 * gib, 200 * gib):
        part = choose_part_size(size)
        assert part >= MIN_PART_SIZE and -(-size // part) <= MAX_PARTS


class FakeRemoteDispatcher:
    """Como Modal: registra los envíos; `down` simula que Modal no responde."""

    remote = True

    def __init__(self):
        self.sent: list[str] = []
        self.down = False

    def dispatch(self, job_id: str) -> None:
        if self.down:
            raise ConnectionError("modal caído")
        self.sent.append(job_id)


def test_remote_dispatch_survives_outage_and_duplicates(client, sample_video, monkeypatch):
    app = client.app
    remote = FakeRemoteDispatcher()
    remote.down = True
    app.state.dispatcher = remote
    upload_id = upload_video(client, sample_video)

    # Modal caído: el usuario no ve un error, el job queda en cola sin marca de envío.
    r = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH)
    assert r.status_code == 201 and r.json()["status"] == "queued"
    job_id = r.json()["id"]

    # Vuelve Modal: el barrido lo reenvía una vez, y no lo repite mientras el envío sea reciente.
    remote.down = False
    settings, sessions = app.state.settings, app.state.sessions
    assert redispatch_queued(settings, sessions, remote) == 1
    assert redispatch_queued(settings, sessions, remote) == 0
    assert remote.sent == [job_id]

    # Si el envío no arranca a tiempo, se reenvía.
    with session_scope(sessions) as s:
        s.get(Job, job_id).dispatched_at = utcnow() - timedelta(hours=1)
    assert redispatch_queued(settings, sessions, remote) == 1

    # Dos envíos del mismo job: solo uno lo procesa.
    monkeypatch.setattr(worker_mod, "build_pipeline", lambda *a, **k: FakePipeline())
    runner = JobRunner(settings, sessions, app.state.storage)
    assert runner.process(job_id) is True
    assert runner.process(job_id) is False
    assert client.get(f"/jobs/{job_id}", headers=AUTH).json()["status"] == "done"


def test_requeued_stale_job_is_redispatched_immediately(client, sample_video):
    app = client.app
    remote = FakeRemoteDispatcher()
    app.state.dispatcher = remote
    upload_id = upload_video(client, sample_video)
    job_id = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH).json()["id"]
    assert remote.sent == [job_id]

    settings, sessions = app.state.settings, app.state.sessions
    runner = JobRunner(settings, sessions, app.state.storage)
    assert runner.claim(job_id)
    with session_scope(sessions) as s:
        s.get(Job, job_id).heartbeat_at = utcnow() - timedelta(hours=1)  # el worker murió
    runner.recover_stale()
    assert redispatch_queued(settings, sessions, remote) == 1
    assert remote.sent == [job_id, job_id]


class RecordingNotifier:
    def __init__(self, fail: bool = False):
        self.sent = []
        self.fail = fail

    def send(self, email):
        if self.fail:
            raise ConnectionError("brevo caído")
        self.sent.append(email)


def _runner_with(client, monkeypatch, pipeline, notifier) -> JobRunner:
    monkeypatch.setattr(worker_mod, "build_pipeline", lambda *a, **k: pipeline)
    app = client.app
    return JobRunner(app.state.settings, app.state.sessions, app.state.storage, notifier=notifier)


def test_email_when_clips_are_ready(client, sample_video, monkeypatch):
    upload_id = upload_video(client, sample_video)
    job_id = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH).json()["id"]
    notifier = RecordingNotifier()
    assert _runner_with(client, monkeypatch, FakePipeline(), notifier).process(job_id)

    [email] = notifier.sent
    assert email.to == "ana@example.com" and "listos" in email.subject
    assert f"/projects/{job_id}" in email.html and "1 clip" in email.text and "7 días" in email.text


def test_email_when_processing_fails(client, sample_video, monkeypatch):
    upload_id = upload_video(client, sample_video)
    job_id = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH).json()["id"]
    notifier = RecordingNotifier()
    runner = _runner_with(client, monkeypatch, FakePipeline(fail=SelectionError("La transcripción está vacía")),
                          notifier)
    runner.process(job_id)

    [email] = notifier.sent
    assert "No hemos podido" in email.subject and "voz" in email.text and "devuelto" in email.text


def test_email_outage_does_not_break_the_job(client, sample_video, monkeypatch):
    upload_id = upload_video(client, sample_video)
    job_id = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH).json()["id"]
    _runner_with(client, monkeypatch, FakePipeline(), RecordingNotifier(fail=True)).process(job_id)
    assert client.get(f"/jobs/{job_id}", headers=AUTH).json()["status"] == "done"


def _stored_files(client) -> list[str]:
    root = client.app.state.settings.storage_root()
    return [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".multipart" not in p.parts]


def test_delete_account_removes_everything(client, sample_video, monkeypatch):
    upload_id = upload_video(client, sample_video)
    job_id = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH).json()["id"]
    run_worker(client, monkeypatch, FakePipeline())
    pending = client.post("/uploads", json={"filename": "b.mp4", "size_bytes": 1000}, headers=AUTH).json()
    other = {"Authorization": "Bearer dev:otro@example.com"}
    client.get("/me", headers=other)
    assert any(f.startswith("clips/") for f in _stored_files(client))

    assert client.delete("/me", headers=AUTH).status_code == 204

    assert _stored_files(client) == []
    with session_scope(client.app.state.sessions) as s:
        assert s.get(Job, job_id) is None
        assert s.scalars(select(UsageEvent).where(UsageEvent.user_id == "dev|ana@example.com")).all() == []
        assert s.get(Upload, pending["upload_id"]) is None
    # El otro usuario no se ve afectado; si Ana vuelve a entrar, empieza de cero.
    assert client.get("/me", headers=other).status_code == 200
    assert client.get("/jobs", headers=AUTH).json() == []


def test_delete_account_waits_for_running_jobs(client, sample_video):
    upload_id = upload_video(client, sample_video)
    client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH)
    r = client.delete("/me", headers=AUTH)
    assert r.status_code == 409 and r.json()["error"]["code"] == "account_busy"


def test_delete_identity_calls_supabase_admin(monkeypatch):
    from clipaso.infra.config import AuthSettings
    from clipaso.interfaces.api import auth as auth_mod

    calls = []

    class Resp:
        status_code, is_error, text = 200, False, ""

    monkeypatch.setattr(auth_mod.httpx, "delete", lambda url, headers, timeout: calls.append((url, headers)) or Resp())
    cfg = AuthSettings(mode="supabase", supabase_url="https://abc.supabase.co/", supabase_service_key="sb_secret_x")
    auth_mod.delete_identity("user-123", cfg)
    assert calls == [("https://abc.supabase.co/auth/v1/admin/users/user-123", {"apikey": "sb_secret_x"})]

    with pytest.raises(auth_mod.AppError):
        auth_mod.delete_identity("user-123", AuthSettings(mode="supabase", supabase_url="https://abc.supabase.co"))


def test_ready_email_talks_about_the_video_in_whole_video_modes():
    from clipaso.saas.notifications import clips_ready

    email = clips_ready("a@b.c", "Charla", 1, 7, "https://x/projects/1", mode="clean")
    assert email.subject == "Tu vídeo «Charla» está listo" and "sin silencios" in email.html
    assert "Ver mi vídeo" in email.html and "clip" not in email.text
    english = clips_ready("a@b.c", "Talk", 1, 7, "https://x", lang="en", mode="subtitle")
    assert "captioned video" in english.text
    assert "clips" in clips_ready("a@b.c", "Charla", 3, 7, "https://x").subject
