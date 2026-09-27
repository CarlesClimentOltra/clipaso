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
    style = {"font": "Bebas Neue", "text_color": "FFFFFF", "highlight_color": "FF3B30"}
    r = client.put("/me/preferences", json={"caption_style": style,
                                             "branding": {"handle": " @ana ", "position": "bottom-left"}}, headers=AUTH)
    assert r.status_code == 200 and r.json()["branding"]["handle"] == "@ana"

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
