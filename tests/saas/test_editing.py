"""Opciones de proyecto, textos, editor, re-render, más clips, ZIP y preferencias."""

from __future__ import annotations

import io
import zipfile
from datetime import timedelta
from urllib.parse import urlsplit

import cv2
import numpy as np

from clipaso.saas import tasks as tasks_mod
from clipaso.saas.db import session_scope, utcnow
from clipaso.saas.models import Clip, Job, Task, TaskStatus, Upload
from clipaso.saas.tasks import TaskRunner
from clipaso.saas.worker import JobRunner
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


def purge_original(client, job_id: str) -> None:
    """El original ya no está (proyectos antiguos o borrado): el editor no puede volver a generar."""
    from clipaso.saas.services import purge_upload

    with session_scope(client.app.state.sessions) as s:
        purge_upload(client.app.state.storage, s.get(Upload, s.get(Job, job_id).upload_id))


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

    body = {"start": 0.0, "end": 3.0, "word_edits": {word["key"]: "Clipaso."},
            "caption_style": {"font": "Anton", "text_color": "FFFFFF", "highlight_color": "FF3B30"}}
    r = client.post(f"/clips/{clip['id']}/render", json=body, headers=AUTH)
    assert r.status_code == 202 and r.json()["status"] == "rendering"
    assert len(dispatcher.tasks) == 1
    # Mientras se genera no se puede lanzar otro render del mismo clip.
    assert client.post(f"/clips/{clip['id']}/render", json=body, headers=AUTH).json()["error"]["code"] == "clip_busy"

    run_tasks(client)
    call = pipeline.calls[-1]
    assert call["kind"] == "render" and (call["clip"].start, call["clip"].end) == (0.0, 3.0)
    assert "Clipaso." in [w.text.strip() for w in call["transcript"].words_between(0, 3)]
    assert call["opts"].profile.subtitles.font == "Anton"

    clip = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]
    assert clip["status"] == "ready" and clip["version"] == 2 and (clip["start"], clip["end"]) == (0.0, 3.0)
    storage = client.app.state.storage
    assert storage.size(_clip_row(client, clip["id"]).video_key) and storage.size(old_video_key) is None

    srt = client.get(f"/clips/{clip['id']}/captions?format=srt", headers=AUTH)
    assert srt.status_code == 200 and "Clipaso." in srt.text and "00:00:00,200 --> 00:00:01,000" in srt.text
    vtt = client.get(f"/clips/{clip['id']}/captions?format=vtt", headers=AUTH).text
    assert vtt.startswith("WEBVTT")


def test_render_validation(client, sample_video, monkeypatch):
    job_id, _ = processed_job(client, sample_video, monkeypatch)
    purge_original(client, job_id)
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
    from clipaso.saas.models import User

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
    assert {f["id"] for f in body["formats"]} == {"vertical", "square", "horizontal", "original"}
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
    from clipaso.domain.models import Sentence, Transcript, Word
    from clipaso.saas.artifacts import apply_edits, word_keys

    words = [Word(text=" a", start=1.0, end=1.0), Word(text=" b", start=1.0, end=1.2),
             Word(text=" c", start=2, end=2.5)]
    transcript = Transcript(language="es", duration=3, sentences=[
        Sentence(index=0, start=1, end=2.5, text="a b c", words=words)])
    assert sorted(word_keys(transcript).values()) == ["1000", "1000.1", "2000"]
    edited = apply_edits(transcript, {"1000.1": "B"})
    assert [w.text.strip() for w in edited.sentences[0].words] == ["a", "B", "c"]


def test_trim_on_the_server_bills_only_the_part_and_replaces_the_original(client, tmp_path, monkeypatch):
    import subprocess

    from clipaso.infra import ffmpeg
    from clipaso.saas.models import Upload
    from tests.saas.test_api_flow import put_parts

    video = tmp_path / "larga.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "testsrc=size=320x180:rate=25:duration=30",
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


def _exports(client, clip_id) -> dict:
    items = client.get(f"/clips/{clip_id}/exports", headers=AUTH).json()["items"]
    return {(i["format"], i["quality"]): i for i in items}


def test_exports_other_qualities_and_mp3(client, sample_video, monkeypatch):
    dispatcher = Dispatcher()
    client.app.state.dispatcher = dispatcher
    job_id, pipeline = processed_job(client, sample_video, monkeypatch)
    clip_id = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]["id"]

    items = _exports(client, clip_id)
    assert items[("mp4", "1080p")]["status"] == "ready" and items[("mp4", "1080p")]["url"]
    assert items[("mp4", "720p")]["status"] == "available" and ("mp4", "2160p") not in items  # el original no es 4K
    assert client.post(f"/clips/{clip_id}/exports", json={"format": "mp4", "quality": "2160p"},
                       headers=AUTH).status_code == 400

    # MP3: al momento, en la API
    r = client.post(f"/clips/{clip_id}/exports", json={"format": "mp3"}, headers=AUTH).json()
    mp3 = next(i for i in r["items"] if i["format"] == "mp3")
    assert mp3["status"] == "ready" and mp3["size_bytes"] > 0 and mp3["url"]

    # 720p: tarea del worker, que renderiza desde el original a esa resolución
    r = client.post(f"/clips/{clip_id}/exports", json={"format": "mp4", "quality": "720p"}, headers=AUTH).json()
    assert next(i for i in r["items"] if i["quality"] == "720p")["status"] == "pending"
    assert len(dispatcher.tasks) == 1
    client.post(f"/clips/{clip_id}/exports", json={"format": "mp4", "quality": "720p"}, headers=AUTH)
    assert len(dispatcher.tasks) == 1  # no se duplica mientras está en marcha
    run_tasks(client)
    assert (pipeline.calls[-1]["opts"].profile.width, pipeline.calls[-1]["opts"].profile.height) == (720, 1280)
    items = _exports(client, clip_id)
    assert items[("mp4", "720p")]["status"] == "ready" and items[("mp4", "720p")]["url"]
    clip = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]
    assert clip["status"] == "ready" and clip["version"] == 1  # exportar no toca el clip

    # Al volver a renderizar el clip, las otras versiones se descartan
    exported = [v["key"] for v in _clip_row(client, clip_id).exports.values()]
    client.post(f"/clips/{clip_id}/render", json={"start": 0, "end": 3}, headers=AUTH)
    run_tasks(client)
    items = _exports(client, clip_id)
    assert items[("mp4", "720p")]["status"] == "available" and items[("mp3", None)]["status"] == "available"
    assert all(client.app.state.storage.size(k) is None for k in exported)


def test_exports_without_source_downscale_the_clip(client, sample_video, monkeypatch):
    job_id, pipeline = processed_job(client, sample_video, monkeypatch)
    purge_original(client, job_id)
    clip_id = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]["id"]
    client.post(f"/clips/{clip_id}/exports", json={"format": "mp4", "quality": "480p"}, headers=AUTH)
    renders = len([c for c in pipeline.calls if c["kind"] == "render"])
    run_tasks(client)
    assert len([c for c in pipeline.calls if c["kind"] == "render"]) == renders  # sin original: se reduce el MP4
    items = _exports(client, clip_id)
    assert items[("mp4", "480p")]["status"] == "ready"


def test_line_breaks_chosen_by_the_user(client, sample_video, monkeypatch):
    job_id, pipeline = processed_job(client, sample_video, monkeypatch)
    clip_id = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]["id"]
    words = client.get(f"/clips/{clip_id}/editor", headers=AUTH).json()["words"]
    hola, todos = words[0], words[2]  # «Hola a todos, esto…»: «todos,» corta por la coma
    edits = {f"br:{hola['key']}": "split", f"br:{todos['key']}": "join", "br:1": "nada"}
    client.post(f"/clips/{clip_id}/render", json={"start": 0, "end": 3, "word_edits": edits}, headers=AUTH)
    run_tasks(client)
    words = client.get(f"/clips/{clip_id}/editor", headers=AUTH).json()["words"]
    assert words[0]["brk"] == "split" and words[2]["brk"] == "join" and words[1]["brk"] is None
    srt = client.get(f"/clips/{clip_id}/captions?format=srt", headers=AUTH).text
    assert "\nHola\n" in srt and "a todos, esto es" in srt


def test_subtitle_only_mode(client, sample_video, monkeypatch):
    job_id, pipeline = processed_job(client, sample_video, monkeypatch, mode="subtitle", format="original",
                                     subtitle_language="en")
    call = pipeline.calls[0]
    assert call["kind"] == "subtitle" and call["translate_to"] == "en"
    profile = call["opts"].profile
    assert (profile.name, profile.width, profile.height) == ("original", 320, 180)  # tal cual, sin recorte
    assert profile.reframe.value == "center" and profile.subtitles.enabled

    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert job["status"] == "done" and len(job["clips"]) == 1 and job["more_clips_available"] == 0
    assert job["options"]["mode"] == "subtitle" and job["options"]["subtitle_language"] == "en"
    clip_id = job["clips"][0]["id"]
    r = client.post(f"/jobs/{job_id}/more", json={"count": 1}, headers=AUTH)
    assert r.status_code == 400 and r.json()["error"]["code"] == "too_many_clips"
    # El vídeo entero se puede volver a generar aunque dure más que un clip normal.
    assert client.post(f"/clips/{clip_id}/render", json={"start": 0, "end": 3}, headers=AUTH).status_code == 202


def test_original_profile_keeps_the_frame():
    from clipaso.infra.config import Settings
    from clipaso.saas.rendering import original_profile

    settings = Settings(_env_file=None)
    vertical = original_profile(settings, (2160, 3840))
    assert (vertical.width, vertical.height) == (1080, 1920) and vertical.subtitles.font_size_ratio == 0.045
    wide = original_profile(settings, (3840, 2160))
    assert (wide.width, wide.height) == (1920, 1080) and wide.subtitles.font_size_ratio == 0.06
    odd = original_profile(settings, (853, 481))
    assert odd.width % 2 == 0 and odd.height % 2 == 0


def test_only_the_cover_the_format_needs(client, sample_video, monkeypatch):
    storage = client.app.state.storage
    job_id, _ = processed_job(client, sample_video, monkeypatch, format="vertical")
    clip = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]
    assert clip["cover"]["vertical_url"] and clip["cover"]["horizontal_url"] is None
    row = _clip_row(client, clip["id"])
    assert row.cover["sizes"] == ["vertical"] and "horizontal" not in row.cover and "base_horizontal" not in row.cover
    # Editar (texto u otro fotograma) mantiene solo esa.
    r = client.put(f"/clips/{clip['id']}/cover", json={"text": "Otro texto", "highlight": -1}, headers=AUTH)
    edited = r.json()["cover"]
    assert r.status_code == 200 and edited["horizontal_url"] is None and edited["highlight"] is None
    r = client.put(f"/clips/{clip['id']}/cover", json={"time": 2.0}, headers=AUTH)
    assert r.status_code == 200 and r.json()["cover"]["horizontal_url"] is None
    assert storage.read_bytes(_clip_row(client, clip["id"]).cover["vertical"])

    job_id, _ = processed_job(client, sample_video, monkeypatch, mode="subtitle", format="horizontal")
    cover = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]["cover"]
    assert cover["horizontal_url"] and cover["vertical_url"] is None


def test_covers_are_generated_edited_and_regenerated(client, sample_video, monkeypatch, cover_llm):
    from clipaso.saas import covers

    dispatcher = Dispatcher()
    client.app.state.dispatcher = dispatcher
    job_id, _ = processed_job(client, sample_video, monkeypatch, format="square")  # cuadrado: las dos portadas
    clip = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]
    cover = clip["cover"]
    assert cover["text"] == "Esto lo cambia todo" and cover["highlight"] == 3 and cover["template"] == "impacto"
    assert cover["vertical_url"] and cover["horizontal_download_url"] and not cover["pending"]
    assert cover_llm.calls[0]["images"] >= 1  # la IA vio los fotogramas candidatos
    storage = client.app.state.storage
    row = _clip_row(client, clip["id"])
    vertical = covers.from_jpeg(storage.read_bytes(row.cover["vertical"]))
    horizontal = covers.from_jpeg(storage.read_bytes(row.cover["horizontal"]))
    assert vertical.shape[:2] == (1920, 1080) and horizontal.shape[:2] == (720, 1280)

    # Editar texto y plantilla: se recompone sin volver a leer el vídeo, y las imágenes viejas se borran.
    old_keys = [row.cover["vertical"], row.cover["horizontal"]]
    r = client.put(f"/clips/{clip['id']}/cover", json={"text": "  Nadie   te lo cuenta ", "highlight": 0,
                                                        "template": "caja"}, headers=AUTH)
    assert r.status_code == 200
    cover = r.json()["cover"]
    assert (cover["text"], cover["highlight"], cover["template"]) == ("Nadie te lo cuenta", 0, "caja")
    assert all(storage.size(k) is None for k in old_keys)
    # Otro fotograma del vídeo
    r = client.put(f"/clips/{clip['id']}/cover", json={"time": 2.0}, headers=AUTH)
    assert r.status_code == 200 and r.json()["cover"]["time"] == 2.0
    assert client.put(f"/clips/{clip['id']}/cover", json={"template": "otra"}, headers=AUTH).status_code == 422

    # Regenerar con IA: tarea del worker, con otra propuesta distinta
    r = client.post(f"/clips/{clip['id']}/cover/regenerate", headers=AUTH)
    assert r.status_code == 202 and r.json()["cover"]["pending"] and len(dispatcher.tasks) == 1
    assert client.post(f"/clips/{clip['id']}/cover/regenerate", headers=AUTH).status_code == 409
    run_tasks(client)
    cover = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]["cover"]
    assert not cover["pending"] and cover["template"] == "caja"  # conserva la plantilla elegida
    assert "Nadie te lo cuenta" in cover_llm.calls[-1]["system"]  # pide un texto distinto del actual


def test_subtitle_mode_video_gets_a_cover(client, sample_video, monkeypatch):
    job_id, _ = processed_job(client, sample_video, monkeypatch, mode="subtitle", format="original")
    assert client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]["cover"] is not None


def test_audio_uploads_only_for_audio_modes(client, sample_audio, sample_video, monkeypatch):
    import base64
    import io

    from PIL import Image

    upload_id = upload_video(client, sample_audio)  # un MP3 se sube y se mide como cualquier vídeo
    r = client.post("/jobs", json={"upload_id": upload_id, "mode": "clips"}, headers=AUTH)
    assert r.status_code == 400 and "audiograma" in r.json()["error"]["message"]

    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (10, 120, 200)).save(buf, "PNG")
    image = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    pipeline = FakePipeline(video=sample_video)
    job_id, _ = processed_job(client, sample_audio, monkeypatch, pipeline=pipeline, mode="audiogram",
                              format="vertical", audiogram_title="Episodio 1", audiogram_accent="FF0055",
                              audiogram_image=image)
    call = pipeline.calls[0]
    assert call["kind"] == "audiogram" and call["style"].title == "Episodio 1" and call["style"].accent == "FF0055"
    assert (call["style"].width, call["style"].height) == (1080, 1920)
    assert call["style"].image.name == "audiograma-fondo.jpg"
    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert job["status"] == "done" and len(job["clips"]) == 1 and job["clips"][0]["video_url"]
    assert "audiogram_image" not in job["options"]
    with session_scope(client.app.state.sessions) as s:
        row = s.get(Job, job_id)
        upload = s.get(Upload, row.upload_id)
        assert upload.content_type == "video/mp4"  # el editor parte del vídeo del audiograma
        stored = client.app.state.storage.read_bytes(row.options["audiogram_image_key"])
        assert stored and stored[:2] == b"\xff\xd8"  # guardada como JPEG
    bad = client.post("/jobs", json={"upload_id": upload_video(client, sample_audio), "mode": "audiogram",
                                     "audiogram_image": "no-es-una-imagen"}, headers=AUTH)
    assert bad.status_code == 400


def test_text_mode_writes_texts_and_offers_the_transcript(client, sample_audio, monkeypatch):
    from clipaso.application import writer

    written = {}

    def fake_write(self, transcript, *, duration, language, title=""):
        written.update(duration=duration, language=language, title=title)
        return {"language": language, "summary": "Resumen", "key_points": ["Idea"], "chapters": [],
                "chapters_text": "", "blog_title": "Blog", "blog_markdown": "Texto", "linkedin": "Post",
                "thread": ["1/"], "seo_title": "SEO", "seo_description": "Desc", "seo_tags": ["ia"]}

    monkeypatch.setattr(writer.TextWriter, "write", fake_write)
    job_id, pipeline = processed_job(client, sample_audio, monkeypatch, mode="text", subtitle_language="en")
    assert pipeline.calls[0]["kind"] == "transcribe_only"
    assert written == {"duration": 6.0, "language": "en", "title": "podcast"}
    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert job["status"] == "done" and job["clips"] == [] and job["text_results"]["summary"] == "Resumen"
    assert job["can_edit"] is False  # el original se borra al terminar
    txt = client.get(f"/jobs/{job_id}/transcript", headers=AUTH)
    assert txt.status_code == 200 and txt.text.startswith("Hola a todos, esto es SmartCus.")
    assert "attachment" in txt.headers["content-disposition"]
    srt = client.get(f"/jobs/{job_id}/transcript?format=srt", headers=AUTH).text
    assert srt.startswith("1\n00:00:00,200 --> ")


def test_trailer_mode_replaces_the_source_and_reports_the_moments(client, sample_video, monkeypatch):
    job_id, pipeline = processed_job(client, sample_video, monkeypatch, mode="trailer", format="vertical",
                                     trailer_seconds=30, topic="dinero")
    call = pipeline.calls[0]
    assert call["kind"] == "trailer" and call["seconds"] == 30 and call["opts"].topic == "dinero"
    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert job["status"] == "done" and job["more_clips_available"] == 0
    assert job["trailer_stats"] == {"original_seconds": 120.0, "trailer_seconds": 3.0, "moments": 2}
    assert job["clips"][0]["title"] == "Lo que nadie cuenta"
    with session_scope(client.app.state.sessions) as s:
        assert s.get(Upload, s.get(Job, job_id).upload_id).duration_seconds == 3.0
    r = client.post("/jobs", json={"upload_id": upload_video(client, sample_video), "mode": "trailer",
                                   "trailer_seconds": 45}, headers=AUTH)
    assert r.status_code == 422


def test_reframe_mode_uses_the_chosen_format_and_fit(client, sample_video, monkeypatch):
    job_id, pipeline = processed_job(client, sample_video, monkeypatch, mode="reframe", format="vertical",
                                     reframe_fit="blur_pad")
    call = pipeline.calls[0]
    assert call["kind"] == "subtitle" and call["allow_silent"]
    profile = call["opts"].profile
    assert (profile.width, profile.height, profile.reframe.value) == (1080, 1920, "blur_pad")
    assert not profile.subtitles.enabled
    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert job["options"]["reframe_fit"] == "blur_pad" and job["more_clips_available"] == 0
    upload_id = upload_video(client, sample_video)
    r = client.post("/jobs", json={"upload_id": upload_id, "mode": "reframe", "format": "original"}, headers=AUTH)
    assert r.status_code == 400


def test_delete_a_clip_with_all_its_files(client, sample_video, monkeypatch):
    storage = client.app.state.storage
    job_id, _ = processed_job(client, sample_video, monkeypatch, pipeline=FakePipeline(clips=2))
    clips = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"]
    row = _clip_row(client, clips[0]["id"])
    keys = [row.video_key, row.thumb_key, row.cover["vertical"], row.cover["base_vertical"]]
    assert all(storage.size(k) for k in keys)

    other = {"Authorization": "Bearer dev:otro@example.com"}
    assert client.delete(f"/clips/{clips[0]['id']}", headers=other).status_code == 404  # solo el dueño
    assert client.delete(f"/clips/{clips[0]['id']}", headers=AUTH).status_code == 204
    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert [c["id"] for c in job["clips"]] == [clips[1]["id"]]
    assert all(storage.size(k) is None for k in keys)
    assert client.delete(f"/clips/{clips[0]['id']}", headers=AUTH).status_code == 404

    # Mientras se genera una nueva versión no se puede borrar.
    client.post(f"/clips/{clips[1]['id']}/render", json={"start": 0, "end": 3}, headers=AUTH)
    r = client.delete(f"/clips/{clips[1]['id']}", headers=AUTH)
    assert r.status_code == 409 and r.json()["error"]["code"] == "clip_busy"


def test_watermark_follows_the_current_plan(client, sample_video, monkeypatch):
    from clipaso.saas.models import Plan

    _, pipeline = processed_job(client, sample_video, monkeypatch)
    assert pipeline.calls[0]["opts"].branding is None  # sin marca personal ni marca de agua
    with session_scope(client.app.state.sessions) as s:
        s.get(Plan, "free").watermark = True
    _, pipeline = processed_job(client, sample_video, monkeypatch, branding=False)
    branding = pipeline.calls[0]["opts"].branding
    assert branding is not None and branding.watermark and not branding.active


def test_subtitles_are_off_by_default_except_in_subtitle_mode(client, sample_video, monkeypatch):
    _, pipeline = processed_job(client, sample_video, monkeypatch)
    assert not pipeline.calls[0]["opts"].profile.subtitles.enabled
    style = {"font": "Anton", "enabled": False}
    _, pipeline = processed_job(client, sample_video, monkeypatch, mode="subtitle", caption_style=style)
    assert pipeline.calls[0]["opts"].profile.subtitles.enabled


def test_clean_mode_replaces_the_source_and_reports_what_was_removed(client, sample_video, monkeypatch):
    job_id, pipeline = processed_job(client, sample_video, monkeypatch, mode="clean", format="original",
                                     clean_pace="fast", clean_fillers=False, subtitle_language="en")
    call = pipeline.calls[0]
    assert call["kind"] == "clean" and call["pace"] == "fast" and not call["fillers"] and call["translate_to"] == "en"
    job = client.get(f"/jobs/{job_id}", headers=AUTH).json()
    assert job["status"] == "done" and len(job["clips"]) == 1 and job["more_clips_available"] == 0
    assert job["options"]["mode"] == "clean" and job["clips"][0]["cover"] is not None
    assert job["clean_stats"] == {"original_seconds": 3.0, "removed_seconds": 0.5, "pauses": 1, "fillers": 2}
    with session_scope(client.app.state.sessions) as s:
        upload = s.get(Upload, s.get(Job, job_id).upload_id)
        assert upload.duration_seconds == 2.5 and upload.content_type == "video/mp4"
    # El editor trabaja sobre el vídeo ya limpio.
    assert client.get(f"/clips/{job['clips'][0]['id']}/editor", headers=AUTH).status_code == 200


def test_cover_without_ai_uses_the_title(client, sample_video, monkeypatch):
    import clipaso.bootstrap

    def no_llm(settings):
        raise RuntimeError("sin IA")

    monkeypatch.setattr(clipaso.bootstrap, "build_fast_llm", no_llm)
    job_id, _ = processed_job(client, sample_video, monkeypatch)
    clip = client.get(f"/jobs/{job_id}", headers=AUTH).json()["clips"][0]
    assert clip["cover"]["text"] == "Gran momento"


def _frames_b64(video, times):
    import base64

    from clipaso.saas import covers

    out = []
    for t in times:
        img = covers.grab_frame(video, t, max_width=640)
        out.append({"time": t, "image": base64.b64encode(covers.to_jpeg(img)).decode()})
    return out


def test_thumbnail_without_uploading_the_video(client, sample_video, cover_llm, monkeypatch):
    frames = _frames_b64(sample_video, [0.2, 0.8, 1.4, 2.0, 2.6])
    r = client.post("/jobs/thumbnail", json={"filename": "mi-viaje.mp4", "topic": "Viaje a la India",
                                             "language": "es", "frames": frames}, headers=AUTH)
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "done" and job["video_minutes"] == 0 and job["options"]["mode"] == "thumbnail"
    assert job["title"] == "mi-viaje" and client.get("/me", headers=AUTH).json()["usage"]["used_minutes"] == 0
    cover = job["clips"][0]["cover"]
    assert cover["text"] == "Esto lo cambia todo" and all(cover["candidate_images"])
    assert "Viaje a la India" in cover_llm.calls[-1]["user"] and cover_llm.calls[-1]["images"] >= 2
    summary = next(j for j in client.get("/jobs", headers=AUTH).json() if j["id"] == job["id"])
    assert summary["mode"] == "thumbnail" and summary["thumbnail_url"]

    clip_id = job["clips"][0]["id"]
    other = next(t for t in cover["candidates"] if abs(t - cover["time"]) > 0.05)
    r = client.put(f"/clips/{clip_id}/cover", json={"time": other, "template": "limpia"}, headers=AUTH)
    assert r.status_code == 200 and r.json()["cover"]["time"] == other  # sin vídeo: con los fotogramas guardados
    r = client.post(f"/clips/{clip_id}/cover/regenerate", headers=AUTH)
    assert r.status_code == 202 and not r.json()["cover"]["pending"]  # al momento, sin worker
    assert r.json()["cover"]["template"] == "limpia"

    # No se puede crear por la vía normal, y hay límite diario
    assert client.post("/jobs", json={"upload_id": "x", "mode": "thumbnail"}, headers=AUTH).status_code == 400
    from clipaso.saas import thumbnails

    monkeypatch.setattr(thumbnails, "DAILY_LIMIT", 1)
    r = client.post("/jobs/thumbnail", json={"filename": "b.mp4", "frames": frames[:1]}, headers=AUTH)
    assert r.status_code == 429
    bad = client.post("/jobs/thumbnail", json={"filename": "c.mp4", "frames": [{"time": 0, "image": "no"}]},
                      headers=AUTH)
    assert bad.status_code in (400, 429)
