"""Descargas de un clip en otros formatos: MP4 en 480p, 720p o 4K y el audio en MP3.

El clip "normal" es la versión en 1080p. Las demás se generan cuando se piden y se guardan junto
al clip (`clips.exports`) hasta que el clip se vuelve a renderizar o el proyecto caduca:
- MP3: en la propia API, a partir del MP4 ya renderizado (segundos, sin GPU).
- 480p/720p/4K: tarea del worker que vuelve a renderizar desde el original (subtítulos nítidos en
  cualquier tamaño). Si el original ya no se guarda, 480p y 720p se sacan reduciendo el MP4.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from clipaso.domain.models import OutputProfile
from clipaso.domain.ports import Storage
from clipaso.infra import ffmpeg
from clipaso.saas.editing import MAX_ACTIVE_TASKS, _active_tasks, _queue, check_daily_limit, source_available
from clipaso.saas.errors import AppError
from clipaso.saas.models import Clip, Job, Task, TaskKind, TaskStatus, Upload, User
from clipaso.saas.services import clips_prefix

# Calidad → lado corto del vídeo en píxeles (en vertical, el ancho).
QUALITIES: dict[str, int] = {"480p": 480, "720p": 720, "1080p": 1080, "2160p": 2160}
BASE_QUALITY = "1080p"  # la del clip tal como sale del procesamiento
MP3_BITRATE = "192k"


@dataclass
class ExportState:
    format: str  # mp4 | mp3
    quality: str | None
    status: str  # ready | pending | failed | available (se puede pedir)
    key: str | None = None
    size: int | None = None
    error_code: str | None = None


def scaled_profile(profile: OutputProfile, quality: str) -> OutputProfile:
    """El mismo perfil con el lado corto en la calidad pedida (dimensiones pares, para el códec)."""
    short = QUALITIES[quality]
    factor = short / min(profile.width, profile.height)
    width, height = (round(profile.width * factor / 2) * 2, round(profile.height * factor / 2) * 2)
    return profile.model_copy(update={"width": width, "height": height})


def export_key(job: Job, clip: Clip, name: str, ext: str) -> str:
    prefix = clips_prefix(job.user_id, job.id).rstrip("/")
    return f"{prefix}/{clip.rank:02d}-v{clip.version}-{name}.{ext}"


def qualities_for(session: Session, job: Job) -> list[str]:
    """Calidades que tiene sentido ofrecer: 4K solo si el original lo es y sigue guardado."""
    upload = session.get(Upload, job.upload_id) if job.upload_id else None
    out = ["480p", "720p", "1080p"]
    if upload and source_available(session, job) and min(upload.width or 0, upload.height or 0) >= 2160:
        out.append("2160p")
    return out


def locked_qualities(session: Session, job: Job, user: User) -> list[str]:
    """Calidades posibles para este vídeo que el plan del usuario no incluye (se ofrecen para mejorar de plan)."""
    top = QUALITIES.get(user.plan.max_export_quality, QUALITIES["1080p"]) if user.plan else QUALITIES["1080p"]
    return [q for q in qualities_for(session, job) if QUALITIES[q] > top]


def _current(clip: Clip, name: str) -> dict | None:
    item = (clip.exports or {}).get(name)
    return item if item and item.get("version") == clip.version else None


def _latest_export_task(session: Session, clip: Clip, quality: str) -> Task | None:
    tasks = session.scalars(
        select(Task).where(Task.clip_id == clip.id, Task.kind == TaskKind.EXPORT_CLIP)
        .order_by(Task.created_at.desc()).limit(10)
    ).all()
    return next((t for t in tasks if (t.payload or {}).get("quality") == quality
                 and (t.payload or {}).get("version") == clip.version), None)


def states(session: Session, job: Job, clip: Clip) -> list[ExportState]:
    out: list[ExportState] = []
    for quality in qualities_for(session, job):
        if quality == BASE_QUALITY:
            out.append(ExportState("mp4", quality, "ready", clip.video_key, clip.size_bytes))
            continue
        if item := _current(clip, quality):
            out.append(ExportState("mp4", quality, "ready", item["key"], item.get("size")))
            continue
        task = _latest_export_task(session, clip, quality)
        if task is not None and task.status in (TaskStatus.QUEUED, TaskStatus.RUNNING):
            out.append(ExportState("mp4", quality, "pending"))
        elif task is not None and task.status == TaskStatus.FAILED:
            out.append(ExportState("mp4", quality, "failed", error_code=task.error_code))
        else:
            out.append(ExportState("mp4", quality, "available"))
    mp3 = _current(clip, "mp3")
    out.append(ExportState("mp3", None, "ready" if mp3 else "available", mp3 and mp3["key"], mp3 and mp3.get("size")))
    return out


def request_quality(session: Session, user: User, job: Job, clip: Clip, quality: str, now: datetime) -> Task | None:
    """Pide el clip en otra calidad. Devuelve la tarea creada (None si ya está lista o en marcha)."""
    if quality not in qualities_for(session, job):
        raise AppError("validation_error", key="export_quality_unavailable")
    if quality in locked_qualities(session, job, user):
        raise AppError("plan_required", 402, key="plan_quality", params={"quality": quality})
    if quality == BASE_QUALITY or _current(clip, quality):
        return None
    running = _latest_export_task(session, clip, quality)
    if running is not None and running.status in (TaskStatus.QUEUED, TaskStatus.RUNNING):
        return None
    if QUALITIES[quality] > QUALITIES[BASE_QUALITY] and not source_available(session, job):
        raise AppError("source_unavailable", 409)
    if _active_tasks(session, user) >= MAX_ACTIVE_TASKS:
        raise AppError("too_many_tasks", 429)
    check_daily_limit(session, user, TaskKind.EXPORT_CLIP, now)
    task = Task(user_id=user.id, job_id=job.id, clip_id=clip.id, kind=TaskKind.EXPORT_CLIP,
                payload={"quality": quality, "version": clip.version}, created_at=now)
    return _queue(session, user, task, now)


def make_mp3(storage: Storage, job: Job, clip: Clip) -> dict:
    """Audio del clip en MP3 (se genera una vez por versión del clip)."""
    if item := _current(clip, "mp3"):
        return item
    with tempfile.TemporaryDirectory(prefix="clipaso-mp3-") as tmp:
        work = Path(tmp)
        video = storage.local_path(clip.video_key) or storage.download_to(clip.video_key, work / "clip.mp4")
        audio = work / "clip.mp3"
        ffmpeg.run(["-i", str(video), "-vn", "-c:a", "libmp3lame", "-b:a", MP3_BITRATE, str(audio)],
                   what="audio del clip en MP3")
        key = export_key(job, clip, "audio", "mp3")
        storage.put_file(key, audio, "audio/mpeg")
        item = {"version": clip.version, "key": key, "size": audio.stat().st_size}
    clip.exports = {**(clip.exports or {}), "mp3": item}
    return item


def drop_exports(storage: Storage, clip: Clip) -> None:
    """Borra las versiones exportadas (al volver a renderizar el clip dejan de corresponder)."""
    for item in (clip.exports or {}).values():
        if key := item.get("key"):
            storage.delete_prefix(key)
    clip.exports = {}
