"""Modo «Generar miniatura»: portada y miniatura de un vídeo sin subirlo.

El navegador extrae unos 20 fotogramas del vídeo del usuario (en su ordenador) y solo envía esas
imágenes. Aquí se puntúan, una IA rápida con visión elige la mejor y escribe el texto, y se guarda
como un proyecto más (modo `thumbnail`) con un único «clip» sin vídeo que lleva la portada. No gasta
minutos del plan: no hay vídeo que procesar.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta
from pathlib import PurePath

from sqlalchemy.orm import Session

from clipaso.domain.ports import Storage
from clipaso.infra.logging import get_logger
from clipaso.saas import cover_service, covers
from clipaso.saas.db import utcnow
from clipaso.saas.errors import AppError
from clipaso.saas.models import Clip, Job, JobStatus, User
from clipaso.saas.services import clips_prefix

log = get_logger(__name__)

MAX_FRAMES = 24
MAX_FRAME_BYTES = 800 * 1024
DAILY_LIMIT = 40  # miniaturas por usuario y día (cada una llama a la IA)


def decode_frame(data_b64: str):
    try:
        raw = base64.b64decode(data_b64.split(",", 1)[-1], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AppError("validation_error", key="thumbnail_frames") from exc
    if not raw or len(raw) > MAX_FRAME_BYTES:
        raise AppError("validation_error", key="thumbnail_frames")
    img = covers.from_jpeg(raw)
    if img is None or img.ndim != 3:
        raise AppError("validation_error", key="thumbnail_frames")
    return img


def check_limit(session: Session, user: User, now: datetime) -> None:
    from clipaso.saas import editing

    editing.check_daily(session, user, "daily_thumbnails", now, code="too_many_thumbnails")


def create(
    session: Session, storage: Storage, settings, user: User, *, filename: str, topic: str, language: str,
    branding: bool, frames: list[tuple[float, str]], now: datetime,
) -> Job:
    from clipaso.bootstrap import build_cost_tracker, build_fast_llm
    from clipaso.saas import editing

    if not frames or len(frames) > MAX_FRAMES:
        raise AppError("validation_error", key="thumbnail_frames")
    check_limit(session, user, now)
    detector = covers.face_detector(settings.data_dir / "models")
    scored: list[covers.Frame] = []
    for t, data in sorted(frames):
        img = decode_frame(data)
        score, face_x = covers.score_frame(img, detector)
        scored.append(covers.Frame(time=round(max(0.0, t), 2), image=img, face_x=face_x, score=round(score, 4)))
    best = covers.shortlist(scored)

    title = PurePath(filename).stem[:255] or "Vídeo"
    topic = " ".join(topic.split())[:300]
    cost = build_cost_tracker(settings)
    index, text, highlight = 0, covers.fallback_text(topic or title), None
    try:
        llm = build_fast_llm(settings)
        index, ai_text, highlight, usage = covers.ask_ai(llm, best, transcript=topic, title=title, language=language)
        text = ai_text or text
        if usage is not None:
            cost.record_llm(usage)
    except Exception as exc:  # sin IA: el mejor fotograma por puntuación y el tema o el nombre del archivo
        log.warning("thumbnail.ai_failed", error=str(exc)[:300])

    style, _ = editing.get_preferences(user)
    job = Job(
        user_id=user.id, upload_id=None, title=title, status=JobStatus.DONE, stage="done", progress=1.0,
        video_minutes=0, max_clips=1, created_at=now, started_at=now, finished_at=now,
        expires_at=now + timedelta(days=user.plan.retention_days), llm_cost_usd=round(cost.spent, 5),
        options={"mode": "thumbnail", "format": "horizontal", "topic": topic, "branding": branding,
                 "caption_style": style.model_dump(), "language": language, "keep_source": False},
    )
    session.add(job)
    session.flush()
    editing.record_daily(session, user, "daily_thumbnails", now)
    clip = Clip(job_id=job.id, rank=1, title=title, reason="", start=scored[0].time, end=scored[-1].time,
                score=1.0, video_key="", size_bytes=0, description="", hashtags=[])
    session.add(clip)
    session.flush()

    # Los fotogramas propuestos se guardan: cambiar de fotograma no necesita el vídeo.
    prefix = clips_prefix(user.id, job.id).rstrip("/")
    candidates = []
    for i, frame in enumerate(best):
        key = f"{prefix}/fotograma-{i + 1}.jpg"
        storage.put_bytes(key, covers.to_jpeg(frame.image), "image/jpeg")
        candidates.append({"time": frame.time, "face_x": frame.face_x, "key": key})
    chosen = best[index]
    choice = covers.CoverChoice(
        time=chosen.time, face_x=chosen.face_x, text=text, highlight=highlight, candidates=candidates,
        base_vertical=covers.to_jpeg(covers.fit(chosen.image, covers.SIZES["vertical"], chosen.face_x)),
        base_horizontal=covers.to_jpeg(covers.fit(chosen.image, covers.SIZES["horizontal"], chosen.face_x)),
    )
    logo, position = cover_service.branding_logo(storage, user, job.options)
    cover_service.save_choice(storage, user.id, job.id, clip, choice, style=style, logo=logo, logo_position=position)
    log.info("thumbnail.created", job_id=job.id, frames=len(scored), ai=bool(cost.spent))
    return job


def regenerate(session: Session, storage: Storage, settings, user: User, job: Job, clip: Clip) -> None:
    """Otra propuesta con IA para una miniatura (con los fotogramas guardados, sin vídeo)."""
    from clipaso.bootstrap import build_cost_tracker, build_fast_llm
    from clipaso.saas import editing

    now = utcnow()
    editing.check_daily(session, user, "daily_covers", now)  # cuenta como «portada nueva» del día
    current = clip.cover or {}
    frames = []
    for c in current.get("candidates", []):
        data = storage.read_bytes(c.get("key", "")) if c.get("key") else None
        if data is not None:
            frames.append(covers.Frame(time=c["time"], image=covers.from_jpeg(data), face_x=c.get("face_x"), score=0))
    others = [f for f in frames if abs(f.time - float(current.get("time", -1))) > 0.05] or frames
    if not others:
        raise AppError("not_found", 404)
    options = job.options or {}
    cost = build_cost_tracker(settings)
    index, text, highlight = 0, current.get("text", ""), current.get("highlight")
    try:
        llm = build_fast_llm(settings)
        index, ai_text, highlight, usage = covers.ask_ai(
            llm, others, transcript=options.get("topic", ""), title=job.title,
            language=options.get("language", "es"), avoid_text=current.get("text"))
        text = ai_text or text
        if usage is not None:
            cost.record_llm(usage)
    except Exception as exc:
        log.warning("thumbnail.ai_failed", error=str(exc)[:300])
        index = 0
    chosen = others[index]
    choice = covers.CoverChoice(
        time=chosen.time, face_x=chosen.face_x, text=text, highlight=highlight, candidates=current["candidates"],
        base_vertical=covers.to_jpeg(covers.fit(chosen.image, covers.SIZES["vertical"], chosen.face_x)),
        base_horizontal=covers.to_jpeg(covers.fit(chosen.image, covers.SIZES["horizontal"], chosen.face_x)),
    )
    style = editing.effective_style(job, clip)
    logo, position = cover_service.branding_logo(storage, user, options)
    cover_service.save_choice(storage, user.id, job.id, clip, choice, style=style, logo=logo, logo_position=position)
    editing.record_daily(session, user, "daily_covers", now)
    job.llm_cost_usd = round((job.llm_cost_usd or 0) + cost.spent, 5)
