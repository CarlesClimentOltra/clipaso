"""Lo que el usuario hace con un proyecto ya procesado: editar clips, textos, valoraciones,
pedir más clips, descargar todo y configurar su estilo y su marca."""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clipaso.adapters.exporters.subtitles import build_captions
from clipaso.domain.ports import Storage
from clipaso.saas import styles
from clipaso.saas.artifacts import apply_edits, load_signals, load_transcript, logo_key, word_keys
from clipaso.saas.errors import AppError, NotFound
from clipaso.saas.models import (
    Clip,
    ClipStatus,
    Job,
    JobStatus,
    Task,
    TaskKind,
    TaskStatus,
    Upload,
    UploadStatus,
    User,
)
from clipaso.saas.presets import DEFAULT_STYLE, BrandingPrefs, CaptionStyle

WORD_KEY = re.compile(r"\d+(\.\d+)?")
BREAK_KEY = re.compile(r"br:\d+(\.\d+)?")
MIN_CLIP_SECONDS = 3.0
MAX_CLIP_SECONDS = 180.0
EDITOR_MARGIN_SECONDS = 30.0  # contexto que muestra el editor antes y después del clip
MAX_ACTIVE_TASKS = 3
MORE_CLIPS_FACTOR = 3  # un proyecto admite hasta 3 veces los clips por vídeo del plan
LOGO_MAX_BYTES = 1024 * 1024
LOGO_MAX_SIDE = 512


# --------------------------------------------------------------------------- acceso


def get_owned_clip(session: Session, user: User, clip_id: str) -> tuple[Clip, Job]:
    clip = session.get(Clip, clip_id)
    job = session.get(Job, clip.job_id) if clip else None
    if clip is None or job is None or job.user_id != user.id:
        raise NotFound()
    return clip, job


def source_available(session: Session, job: Job) -> bool:
    """El original sigue guardado: se puede re-renderizar y pedir más clips."""
    if job.status != JobStatus.DONE or not job.upload_id:
        return False
    upload = session.get(Upload, job.upload_id)
    return upload is not None and upload.status == UploadStatus.READY


def _active_tasks(session: Session, user: User) -> int:
    return session.scalar(
        select(func.count()).select_from(Task).where(
            Task.user_id == user.id, Task.status.in_([TaskStatus.QUEUED, TaskStatus.RUNNING])
        )
    ) or 0


def is_subtitle_job(job: Job) -> bool:
    return (job.options or {}).get("mode") == "subtitle"


def more_clips_available(job: Job, user: User) -> int:
    if is_subtitle_job(job):
        return 0  # un vídeo subtitulado no tiene «más clips»
    return max(0, user.plan.max_clips_per_job * MORE_CLIPS_FACTOR - len(job.clips))


def latest_task(session: Session, job: Job, kind: TaskKind) -> Task | None:
    return session.scalars(
        select(Task).where(Task.job_id == job.id, Task.kind == kind).order_by(Task.created_at.desc()).limit(1)
    ).first()


# --------------------------------------------------------------------------- textos y valoración


def update_texts(clip: Clip, *, title: str | None, description: str | None, hashtags: list[str] | None) -> None:
    from clipaso.adapters.selection.hybrid import clean_hashtags

    if title is not None:
        clip.title = title.strip()[:255] or clip.title
    if description is not None:
        clip.description = description.strip()[:2000]
    if hashtags is not None:
        clip.hashtags = clean_hashtags(hashtags)


def set_rating(clip: Clip, value: int) -> None:
    clip.rating = value or None


# --------------------------------------------------------------------------- subtítulos


def effective_style(job: Job, clip: Clip) -> CaptionStyle:
    raw = clip.caption_style or (job.options or {}).get("caption_style")
    return CaptionStyle.model_validate(raw) if raw else DEFAULT_STYLE


def clip_words(storage: Storage, job: Job, clip: Clip, start: float | None = None, end: float | None = None):
    """Palabras del tramo (con las correcciones del usuario), con tiempos absolutos."""
    transcript = load_transcript(storage, job.user_id, job.id)
    if transcript is None:
        raise AppError("not_found", 404, key="no_transcript")
    lo, hi = clip.start if start is None else start, clip.end if end is None else end
    return transcript, lo, hi


def captions(storage: Storage, job: Job, clip: Clip, fmt: str) -> str:
    transcript, lo, hi = clip_words(storage, job, clip)
    edited = apply_edits(transcript, clip.word_edits or {})
    words = [w.model_copy(update={"start": w.start - lo, "end": w.end - lo}) for w in edited.words_between(lo, hi)]
    return build_captions(words, fmt)


@dataclass
class EditorWord:
    key: str
    start: float
    end: float
    text: str
    original: str
    brk: str | None = None


def editor_words(storage: Storage, job: Job, clip: Clip, window: tuple[float, float]) -> list[EditorWord]:
    transcript, lo, hi = clip_words(storage, job, clip, *window)
    edits = clip.word_edits or {}
    keys = word_keys(transcript)
    out = []
    for w in transcript.words_between(lo, hi):
        key = keys[id(w)]
        original = w.text.strip()
        out.append(EditorWord(key=key, start=w.start, end=w.end, text=edits.get(key, original).strip(),
                              original=original, brk=edits.get(f"br:{key}")))
    return out


def editor_energy(storage: Storage, job: Job, window: tuple[float, float]) -> tuple[list[float], float]:
    """Volumen del audio en la ventana del editor (para dibujar la onda), a partir de las señales guardadas."""
    signals = load_signals(storage, job.user_id, job.id)
    signal = signals.signals.get("audio_energy") if signals else None
    if signal is None or not signal.values:
        return [], 0.5
    i0, i1 = int(window[0] / signal.step), int(window[1] / signal.step) + 1
    return [round(v, 3) for v in signal.values[i0:i1]], signal.step


def editor_window(clip: Clip, source_duration: float) -> tuple[float, float]:
    return max(0.0, clip.start - EDITOR_MARGIN_SECONDS), min(source_duration, clip.end + EDITOR_MARGIN_SECONDS)


# --------------------------------------------------------------------------- tareas


def request_render(
    session: Session, user: User, clip: Clip, job: Job, *, start: float, end: float,
    word_edits: dict[str, str], caption_style: CaptionStyle | None, now: datetime,
) -> Task:
    if not source_available(session, job):
        raise AppError("source_unavailable", 409)
    if clip.status == ClipStatus.RENDERING:
        raise AppError("clip_busy", 409)
    if _active_tasks(session, user) >= MAX_ACTIVE_TASKS:
        raise AppError("too_many_tasks", 429)
    upload = session.get(Upload, job.upload_id)
    duration = upload.duration_seconds or 0
    start, end = round(max(0.0, start), 3), round(min(end, duration), 3)
    # Un vídeo subtitulado entero puede durar lo que el vídeo; un clip, como mucho MAX_CLIP_SECONDS.
    longest = max(duration, MAX_CLIP_SECONDS) if is_subtitle_job(job) else MAX_CLIP_SECONDS
    if not MIN_CLIP_SECONDS <= end - start <= longest:
        raise AppError("validation_error", key="clip_duration",
                       params={"min": f"{MIN_CLIP_SECONDS:.0f}", "max": f"{longest:.0f}"})
    # Palabras corregidas y cortes de línea («br:<clave>»: split | join).
    clip.word_edits = {
        **{k: v.strip()[:60] for k, v in word_edits.items() if WORD_KEY.fullmatch(k)},
        **{k: v for k, v in word_edits.items() if BREAK_KEY.fullmatch(k) and v in ("split", "join")},
    }
    clip.caption_style = caption_style.model_dump() if caption_style else None
    clip.status, clip.render_error = ClipStatus.RENDERING, None
    task = Task(user_id=user.id, job_id=job.id, clip_id=clip.id, kind=TaskKind.RENDER_CLIP,
                payload={"start": start, "end": end}, created_at=now)
    session.add(task)
    session.flush()
    return task


def request_more_clips(session: Session, user: User, job: Job, *, count: int, topic: str, now: datetime) -> Task:
    if not source_available(session, job):
        raise AppError("source_unavailable", 409)
    running = latest_task(session, job, TaskKind.MORE_CLIPS)
    if running is not None and running.status in (TaskStatus.QUEUED, TaskStatus.RUNNING):
        raise AppError("more_clips_busy", 409)
    if _active_tasks(session, user) >= MAX_ACTIVE_TASKS:
        raise AppError("too_many_tasks", 429)
    available = more_clips_available(job, user)
    if available <= 0:
        raise AppError("too_many_clips", key="project_clip_limit")
    count = max(1, min(count, available, user.plan.max_clips_per_job))
    task = Task(user_id=user.id, job_id=job.id, kind=TaskKind.MORE_CLIPS,
                payload={"count": count, "topic": topic.strip()[:200]}, created_at=now)
    session.add(task)
    session.flush()
    return task


# --------------------------------------------------------------------------- preferencias y logo


def get_preferences(user: User) -> tuple[CaptionStyle, BrandingPrefs]:
    """Estilo por defecto (uno de los estilos del usuario) y marca personal."""
    return styles.default_style(user), BrandingPrefs.model_validate((user.preferences or {}).get("branding", {}))


def save_branding(user: User, branding: BrandingPrefs) -> None:
    _, current = get_preferences(user)
    branding = branding.model_copy(update={"has_logo": current.has_logo, "handle": branding.handle.strip()})
    user.preferences = {**(user.preferences or {}), "branding": branding.model_dump()}


def save_logo(storage: Storage, user: User, data: bytes) -> None:
    """Valida la imagen, la reduce a 512 px como máximo y la guarda como PNG (con transparencia)."""
    import cv2
    import numpy as np

    if not data or len(data) > LOGO_MAX_BYTES:
        raise AppError("validation_error", key="logo_invalid")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None or img.ndim < 2:
        raise AppError("validation_error", key="logo_unreadable")
    h, w = img.shape[:2]
    scale = min(1.0, LOGO_MAX_SIDE / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    ok, png = cv2.imencode(".png", img)
    if not ok:
        raise AppError("validation_error", key="logo_unprocessable")
    storage.put_bytes(logo_key(user.id), png.tobytes(), "image/png")
    _set_has_logo(user, True)


def delete_logo(storage: Storage, user: User) -> None:
    storage.delete_prefix(logo_key(user.id))
    _set_has_logo(user, False)


def _set_has_logo(user: User, value: bool) -> None:
    prefs = dict(user.preferences or {})
    prefs["branding"] = {**prefs.get("branding", {}), "has_logo": value}
    user.preferences = prefs


# --------------------------------------------------------------------------- descarga en ZIP


def archive_token(secret: str, job_id: str, user_id: str, ttl: int = 600) -> str:
    exp = int(time.time()) + ttl
    sig = hmac.new(secret.encode(), f"zip:{job_id}:{user_id}:{exp}".encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def verify_archive_token(secret: str, job_id: str, user_id: str, token: str) -> bool:
    exp, _, sig = token.partition(".")
    if not exp.isdigit() or int(exp) < time.time():
        return False
    expected = hmac.new(secret.encode(), f"zip:{job_id}:{user_id}:{exp}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
