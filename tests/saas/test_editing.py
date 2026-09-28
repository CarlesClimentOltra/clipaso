"""Opciones de proyecto, textos, editor, re-render, más clips, ZIP y preferencias."""

from __future__ import annotations

import io
import zipfile
from datetime import timedelta
from urllib.parse import urlsplit

import cv2
import numpy as np

from smartcuts.saas import tasks as tasks_mod
from smartcuts.saas.db import session_scope, utcnow
from smartcuts.saas.models import Clip, Task, TaskStatus
from smartcuts.saas.tasks import TaskRunner
from smartcuts.saas.worker import JobRunner
from tests.saas.test_api_flow import AUTH, FakePipeline, _stored_files, upload_video, worker_mod


class Dispatcher:
    remote = True

    def __init__(self):
        self.jobs: list[str] = []
        self.tasks: list[str] = []

    def dispatch(self, job_id):
        self.jobs.append(job_id)

    def dispatch_task(self, task_id):
        self.tasks.append(task_id)


def processed_job(client, sample_video, monkeypatch, pipeline=None, **options) -> tuple[str, FakePipeline]:
    pipeline = pipeline or FakePipeline()
    monkeypatch.setattr(worker_mod, "build_pipeline", lambda *a, **k: pipeline)
    monkeypatch.setattr(tasks_mod, "build_pipeline", lambda *a, **k: pipeline)
    upload_id = upload_video(client, sample_video)
    r = client.post("/jobs", json={"upload_id": upload_id, **options}, headers=AUTH)
    assert r.status_code == 201, r.text
    app = client.app
    runner = JobRunner(app.state.settings, app.state.sessions, app.state.storage)
    assert runner.process(r.json()["id"])
    return r.json()["id"], pipeline


def run_tasks(client) -> None:
    app = client.app
    runner = TaskRunner(app.state.settings, app.state.sessions, app.state.storage)
    while task_id := runner.claim_next():
        runner.run(task_id)


def test_options_reach_the_engine_and_publish_texts_are_saved(client, sample_video, monkeypatch):
    style = {"font": "Poppins", "text_color": "FFFFFF", "highlight_color": "FFE600", "size": "l",
             "position": "top", "uppercase": False, "box": True}
    job_id, pipeline = processed_job(client, sample_video, monkeypatch, format="square", duration="short",
                                     topic="dinero", caption_style=style)
    opts = pipeline.calls[0]["opts"]
    assert opts.profile.name == "square_1x1" and (opts.profile.min_duration, opts.profile.max_duration) == (15, 30)
    subs = opts.profile.subtitles
    assert subs.font == "Poppins ExtraBold" and subs.box and subs.position == "top" and not subs.uppercase
    assert subs.font_size_ratio == round(0.05 * 1.25, 4)  # «size: l» de los estilos antiguos = 125 %
    assert opts.topic == "dinero"

    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert job["options"]["format"] == "square" and job["options"]["topic"] == "dinero"
    clip = job["clips"][0]
    assert clip["description"] == "Mira esto hasta el final" and clip["hashtags"] == ["ia", "clips"]


def test_edit_texts_and_rate(client, sample_video, monkeypatch):
    job_id, _ = processed_job(client, sample_video, monkeypatch)
    clip_id = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]["id"]
    r = client.patch(f"/clips/{clip_id}", json={"title": "Nuevo título", "hashtags": ["#Viral", "viral", "ia ia"]},
                     headers=AUTH)
    assert r.status_code == 200 and r.json()["title"] == "Nuevo título" and r.json()["hashtags"] == ["Viral", "iaia"]
    assert client.put(f"/clips/{clip_id}/rating", json={"value": -1}, headers=AUTH).json()["rating"] == -1
    assert client.put(f"/clips/{clip_id}/rating", json={"value": 0}, headers=AUTH).json()["rating"] is None
    other = {"Authorization": "Bearer dev:otro@example.com"}
    assert client.patch(f"/clips/{clip_id}", json={"title": "x"}, headers=other).status_code == 404


def test_editor_render_applies_trim_word_fixes_and_style(client, sample_video, monkeypatch):
    dispatcher = Dispatcher()
    client.app.state.dispatcher = dispatcher
    job_id, pipeline = processed_job(client, sample_video, monkeypatch)
    clip = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]
    old_video_key = _clip_row(client, clip["id"]).video_key

    editor = client.get(f"/clips/{clip['id']}/editor", headers=AUTH).json()
    assert editor["can_render"] and editor["window_start"] == 0 and editor["format"] == "vertical"
    word = next(w for w in editor["words"] if w["text"] == "SmartCus.")

    body = {"start": 0.0, "end": 3.0, "word_edits": {word["key"]: "SmartCuts."},
            "caption_style": {"font": "Anton", "text_color": "FFFFFF", "highlight_color": "FF3B30"}}
    r = client.post(f"/clips/{clip['id']}/render", json=body, headers=AUTH)
    assert r.status_code == 202 and r.json()["status"] == "rendering"
    assert len(dispatcher.tasks) == 1
    # Mientras se genera no se puede lanzar otro render del mismo clip.
    assert client.post(f"/clips/{clip['id']}/render", json=body, headers=AUTH).json()["error"]["code"] == "clip_busy"

    run_tasks(client)
    call = pipeline.calls[-1]
    assert call["kind"] == "render" and (call["clip"].start, call["clip"].end) == (0.0, 3.0)
    assert "SmartCuts." in [w.text.strip() for w in call["transcript"].words_between(0, 3)]
    assert call["opts"].profile.subtitles.font == "Anton"

    clip = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]
    assert clip["status"] == "ready" and clip["version"] == 2 and (clip["start"], clip["end"]) == (0.0, 3.0)
    storage = client.app.state.storage
    assert storage.size(_clip_row(client, clip["id"]).video_key) and storage.size(old_video_key) is None

    srt = client.get(f"/clips/{clip['id']}/captions?format=srt", headers=AUTH)
    assert srt.status_code == 200 and "SmartCuts." in srt.text and "00:00:00,200 --> 00:00:01,000" in srt.text
    vtt = client.get(f"/clips/{clip['id']}/captions?format=vtt", headers=AUTH).text
    assert vtt.startswith("WEBVTT")


def test_render_validation(client, sample_video, monkeypatch):
    job_id, _ = processed_job(client, sample_video, monkeypatch, keep_source=False)
    clip_id = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]["id"]
    r = client.post(f"/clips/{clip_id}/render", json={"start": 0, "end": 3}, headers=AUTH)
    assert r.status_code == 409 and r.json()["error"]["code"] == "source_unavailable"
    assert client.get(f"/clips/{clip_id}/editor", headers=AUTH).json()["can_render"] is False

    job_id, _ = processed_job(client, sample_video, monkeypatch)
    clip_id = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]["id"]
    r = client.post(f"/clips/{clip_id}/render", json={"start": 1, "end": 2}, headers=AUTH)
    assert r.status_code == 400 and r.json()["error"]["code"] == "validation_error"


def test_failed_render_keeps_previous_video(client, sample_video, monkeypatch):
    job_id, pipeline = processed_job(client, sample_video, monkeypatch)
    clip_id = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]["id"]
    client.post(f"/clips/{clip_id}/render", json={"start": 0, "end": 3}, headers=AUTH)
    pipeline.fail = RuntimeError("ffmpeg roto")
    run_tasks(client)
    clip = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]
    assert clip["status"] == "failed" and clip["render_error"] and clip["version"] == 1
    assert client.app.state.storage.size(_clip_row(client, clip_id).video_key)


def test_more_clips_reuses_analysis_and_skips_existing(client, sample_video, monkeypatch):
    job_id, pipeline = processed_job(client, sample_video, monkeypatch)
    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert job["more_clips_available"] == 3 * 3 - 1

    pipeline.clips = 2
    r = client.post(f"/jobs/{job_id}/more", json={"count": 2}, headers=AUTH)
    assert r.status_code == 200 and r.json()["more_clips_task"]["status"] == "queued"
    assert client.post(f"/jobs/{job_id}/more", json={}, headers=AUTH).json()["error"]["code"] == "more_clips_busy"
    run_tasks(client)

    call = pipeline.calls[-1]
    assert call["reused_analysis"] and call["opts"].exclude == [(0.0, 3.0)] and call["opts"].first_rank == 2
    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert [c["rank"] for c in job["clips"]] == [1, 2, 3] and job["more_clips_task"]["status"] == "done"
    assert client.get("/me", headers=AUTH).json()["usage"]["used_minutes"] == 0.1  # no gasta minutos


def test_download_all_as_zip(client, sample_video, monkeypatch):
    job_id, _ = processed_job(client, sample_video, monkeypatch, pipeline=FakePipeline(clips=2))
    url = client.post(f"/jobs/{job_id}/archive", headers=AUTH).json()["url"]
    u = urlsplit(url)
    r = client.get(f"{u.path}?{u.query}")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert sum(n.endswith(".mp4") for n in names) == 2 and sum(n.endswith(".srt") for n in names) == 2
    assert "textos-para-publicar.txt" in names
    assert client.get(f"{u.path}?token=123.abc").status_code == 404


def test_preferences_logo_and_branding_in_new_projects(client, sample_video, monkeypatch):
    client.put("/me/default-style", json={"id": "titular"}, headers=AUTH)
    r = client.put("/me/preferences", json={"branding": {"handle": " @ana ", "position": "bottom-left"}}, headers=AUTH)
    assert r.status_code == 200 and r.json()["branding"]["handle"] == "@ana"
    assert r.json()["caption_style"]["font"] == "Bebas Neue"

    logo = cv2.imencode(".png", np.full((800, 1600, 4), 255, np.uint8))[1].tobytes()
    r = client.put("/me/logo", content=logo, headers={**AUTH, "Content-Type": "image/png"})
    assert r.status_code == 200 and r.json()["branding"]["has_logo"] and r.json()["logo_url"]
    assert client.put("/me/logo", content=b"no es imagen", headers={**AUTH, "Content-Type": "image/png"}
                      ).status_code == 400

    _, pipeline = processed_job(client, sample_video, monkeypatch)
    opts = pipeline.calls[0]["opts"]
    assert opts.profile.subtitles.font == "Bebas Neue"
    assert opts.branding.handle == "@ana" and opts.branding.position == "bottom-left"
    assert opts.branding.logo_path is not None

    assert client.delete("/me/logo", headers=AUTH).json()["branding"]["has_logo"] is False
    assert not any(f.startswith("brand/") for f in _stored_files(client))


def test_custom_styles(client, sample_video, monkeypatch):
    body = client.get("/me/styles", headers=AUTH).json()
    assert body["default_id"] == "clasico" and body["max_custom"] == 10
    assert all(s["builtin"] for s in body["styles"])

    # Modificar uno de serie guarda tu versión; borrarlo la restablece.
    neon = {**next(s for s in body["styles"] if s["id"] == "neon")["style"], "highlight_color": "00FF00"}
    body = client.put("/me/styles/neon", json={"style": neon}, headers=AUTH).json()
    mine = next(s for s in body["styles"] if s["id"] == "neon")
    assert mine["modified"] and mine["style"]["highlight_color"] == "00FF00"

    # Estilo propio, por defecto en los proyectos nuevos.
    own = {"font": "Oswald", "animation": "karaoke", "y": 40, "scale": 140, "outline": 0, "box": True,
           "box_opacity": 60}
    r = client.post("/me/styles", json={"name": "  Mi   podcast ", "style": own}, headers=AUTH)
    assert r.status_code == 201
    new = r.json()["styles"][-1]
    assert new["name"] == "Mi podcast" and not new["builtin"]
    assert client.put("/me/default-style", json={"id": new["id"]}, headers=AUTH).json()["default_id"] == new["id"]

    _, pipeline = processed_job(client, sample_video, monkeypatch)
    subs = pipeline.calls[0]["opts"].profile.subtitles
    assert subs.font == "Oswald" and subs.animation == "karaoke" and subs.pos_y == 0.4 and subs.box_opacity == 60
    assert subs.font_size_ratio == round(0.045 * 1.4, 4)

    # Límite de 10 estilos propios (los de serie modificados no cuentan).
    for i in range(9):
        assert client.post("/me/styles", json={"name": f"E{i}", "style": {}}, headers=AUTH).status_code == 201
    r = client.post("/me/styles", json={"name": "Once", "style": {}}, headers=AUTH)
    assert r.status_code == 409 and "10" in r.json()["error"]["message"]

    # Borrar el estilo por defecto vuelve al clásico; restablecer uno de serie quita los cambios.
    body = client.delete(f"/me/styles/{new['id']}", headers=AUTH).json()
    assert body["default_id"] == "clasico" and all(s["id"] != new["id"] for s in body["styles"])
    body = client.delete("/me/styles/neon", headers=AUTH).json()
    assert not next(s for s in body["styles"] if s["id"] == "neon")["modified"]
    assert client.delete("/me/styles/u_nada", headers=AUTH).status_code == 404
    assert client.post("/me/styles", json={"name": "   ", "style": {}}, headers=AUTH).status_code == 400


def test_legacy_default_style_becomes_a_custom_style(client):
    from smartcuts.saas.models import User

    client.get("/me", headers=AUTH)
    app = client.app
    with session_scope(app.state.sessions) as s:
        user = s.query(User).one()
        user.preferences = {"caption_style": {"font": "Anton", "size": "s", "highlight_color": "123456"}}
    body = client.get("/me/styles", headers=AUTH).json()
    legacy = next(s for s in body["styles"] if s["id"] == body["default_id"])
    assert legacy["name"] == "Mi estilo" and legacy["style"]["scale"] == 80 and legacy["style"]["font"] == "Anton"


def test_options_catalog(client):
    body = client.get("/options").json()
    assert {f["id"] for f in body["formats"]} == {"vertical", "square", "horizontal"}
    assert body["presets"][0]["id"] == "clasico" and "Anton" in body["fonts"]


def test_stale_task_is_requeued(client, sample_video, monkeypatch):
    job_id, _ = processed_job(client, sample_video, monkeypatch)
    clip_id = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]["id"]
    client.post(f"/clips/{clip_id}/render", json={"start": 0, "end": 3}, headers=AUTH)
    app = client.app
    runner = TaskRunner(app.state.settings, app.state.sessions, app.state.storage)
    task_id = runner.claim_next()
    with session_scope(app.state.sessions) as s:
        s.get(Task, task_id).heartbeat_at = utcnow() - timedelta(hours=1)
    runner.recover_stale()
    with session_scope(app.state.sessions) as s:
        assert s.get(Task, task_id).status == TaskStatus.QUEUED


def _clip_row(client, clip_id: str) -> Clip:
    with session_scope(client.app.state.sessions) as s:
        return s.get(Clip, clip_id)


def test_messages_follow_the_request_language(client):
    r = client.post("/uploads", json={"filename": "notas.pdf", "size_bytes": 10}, headers=AUTH)
    assert r.json()["error"]["message"].startswith("Formato no compatible")
    r = client.post("/uploads", json={"filename": "notas.pdf", "size_bytes": 10},
                    headers={**AUTH, "Accept-Language": "en-GB,en;q=0.9"})
    assert r.json()["error"]["message"].startswith("Unsupported format")
    r = client.get("/me", headers={"Accept-Language": "en"})
    assert r.json()["error"]["message"] == "Please sign in to continue."


def test_account_locale_drives_notification_language(client, sample_video, monkeypatch):
    from tests.saas.test_api_flow import RecordingNotifier

    assert client.get("/me", headers=AUTH).json()["locale"] is None
    assert client.put("/me/locale", json={"locale": "en"}, headers=AUTH).status_code == 204
    assert client.get("/me", headers=AUTH).json()["locale"] == "en"

    upload_id = upload_video(client, sample_video)
    job_id = client.post("/jobs", json={"upload_id": upload_id}, headers=AUTH).json()["id"]
    monkeypatch.setattr(worker_mod, "build_pipeline", lambda *a, **k: FakePipeline())
    notifier = RecordingNotifier()
    app = client.app
    JobRunner(app.state.settings, app.state.sessions, app.state.storage, notifier=notifier).process(job_id)
    [email] = notifier.sent
    assert email.subject.startswith("Your clips from") and "See my clips" in email.html


def test_words_starting_at_the_same_time_get_distinct_keys():
    from smartcuts.domain.models import Sentence, Transcript, Word
    from smartcuts.saas.artifacts import apply_edits, word_keys

    words = [Word(text=" a", start=1.0, end=1.0), Word(text=" b", start=1.0, end=1.2), Word(text=" c", start=2, end=2.5)]
    transcript = Transcript(language="es", duration=3, sentences=[
        Sentence(index=0, start=1, end=2.5, text="a b c", words=words)])
    assert sorted(word_keys(transcript).values()) == ["1000", "1000.1", "2000"]
    edited = apply_edits(transcript, {"1000.1": "B"})
    assert [w.text.strip() for w in edited.sentences[0].words] == ["a", "B", "c"]


def test_trim_on_the_server_bills_only_the_part_and_replaces_the_original(client, tmp_path, monkeypatch):
    import subprocess

    from smartcuts.infra import ffmpeg
    from smartcuts.saas.models import Upload
    from tests.saas.test_api_flow import put_parts

    video = tmp_path / "larga.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=25:duration=30",
                    "-f", "lavfi", "-i", "sine=duration=30", "-shortest", "-g", "25", "-c:v", "libx264", "-c:a", "aac",
                    str(video)], check=True)
    data = video.read_bytes()
    r = client.post("/uploads", json={"filename": video.name, "size_bytes": len(data)}, headers=AUTH).json()
    etags = put_parts(client, r["upload_id"], data, r["part_size"], list(range(1, r["part_count"] + 1)))
    parts = [{"part_number": n, "etag": e} for n, e in etags.items()]
    upload_id = client.post(f"/uploads/{r['upload_id']}/complete", json={"parts": parts}, headers=AUTH).json()["id"]

    r = client.post("/jobs", json={"upload_id": upload_id, "trim_start": 10, "trim_end": 12}, headers=AUTH)
    assert r.status_code == 400 and "5" in r.json()["error"]["message"]  # tramo demasiado corto

    pipeline = FakePipeline()
    monkeypatch.setattr(worker_mod, "build_pipeline", lambda *a, **k: pipeline)
    r = client.post("/jobs", json={"upload_id": upload_id, "trim_start": 10, "trim_end": 22}, headers=AUTH)
    assert r.status_code == 201, r.text
    assert client.get("/me", headers=AUTH).json()["usage"]["used_minutes"] == 0.2  # 12 s, no 30 s
    app = client.app
    assert JobRunner(app.state.settings, app.state.sessions, app.state.storage).process(r.json()["id"])

    with session_scope(app.state.sessions) as s:
        upload = s.get(Upload, upload_id)
        assert 11.5 < upload.duration_seconds < 12.5
        stored = app.state.storage.local_path(upload.storage_key)
    assert 11.5 < ffmpeg.video_info(stored)[3] < 12.5  # el original guardado es ya el tramo
    job = client.get(f"/jobs/{r.json()['id']}", headers=AUTH).json()
    assert job["status"] == "done"
