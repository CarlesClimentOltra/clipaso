"""Casos de uso del producto. La API y el worker solo hablan con este módulo."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import PurePath

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from smartcuts.domain.errors import SmartCutsError
from smartcuts.domain.ports import PresignedUpload, Storage
from smartcuts.infra import ffmpeg
from smartcuts.infra.logging import get_logger
from smartcuts.saas.db import utcnow
from smartcuts.saas.errors import AppError, NotFound
from smartcuts.saas.models import Job, JobStatus, Plan, Upload, UploadStatus, UsageEvent, User
from smartcuts.saas.plans import DEFAULT_PLAN

log = get_logger(__name__)

ALLOWED_EXTENSIONS = {".mp4": "video/mp4", ".mov": "video/quicktime", ".mkv": "video/x-matroska",
                      ".webm": "video/webm", ".m4v": "video/mp4"}


def user_folder(user_id: str) -> str:
    """Carpeta de almacenamiento del usuario: estable, sin caracteres problemáticos ni datos personales."""
    return "u" + hashlib.sha256(user_id.encode()).hexdigest()[:20]


def clips_prefix(user_id: str, job_id: str) -> str:
    return f"clips/{user_folder(user_id)}/{job_id}/"


def period_of(moment: datetime) -> str:
    return moment.strftime("%Y-%m")


def billable_minutes(seconds: float) -> float:
    """Minutos facturables, redondeados hacia arriba a la décima."""
    return math.ceil(seconds / 6) / 10


# --------------------------------------------------------------------------- usuarios


def get_or_create_user(session: Session, subject: str, email: str) -> User:
    user = session.get(User, subject)
    if user is None:
        # El primer acceso suele lanzar varias peticiones en paralelo (/me, /jobs…): inserción
        # idempotente para que no choquen al crear el mismo usuario.
        insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
        result = session.execute(
            insert(User)
            .values(id=subject, email=email, plan_code=DEFAULT_PLAN, created_at=utcnow())
            .on_conflict_do_nothing(index_elements=["id"])
        )
        if result.rowcount:
            log.info("user.created", user_id=subject)
        user = session.get(User, subject, populate_existing=True)
    elif email and user.email != email:
        user.email = email
    return user


# --------------------------------------------------------------------------- cuotas


@dataclass
class Usage:
    period: str
    used_minutes: float
    limit_minutes: int

    @property
    def remaining_minutes(self) -> float:
        return max(0.0, self.limit_minutes - self.used_minutes)


def usage_for(session: Session, user: User, now: datetime) -> Usage:
    period = period_of(now)
    used = session.scalar(
        select(func.coalesce(func.sum(UsageEvent.minutes), 0.0)).where(
            UsageEvent.user_id == user.id, UsageEvent.period == period
        )
    )
    return Usage(period=period, used_minutes=round(float(used or 0.0), 1), limit_minutes=user.plan.monthly_minutes)


def running_jobs(session: Session, user: User) -> int:
    return session.scalar(
        select(func.count()).select_from(Job).where(
            Job.user_id == user.id, Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])
        )
    ) or 0


# --------------------------------------------------------------------------- subidas


def create_upload(
    session: Session, storage: Storage, user: User, *, filename: str, size_bytes: int, content_type: str
) -> tuple[Upload, PresignedUpload]:
    ext = PurePath(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError("unsupported_format")
    max_bytes = user.plan.max_upload_mb * 1024 * 1024
    if size_bytes <= 0 or size_bytes > max_bytes:
        raise AppError("upload_too_large", 413)

    upload = Upload(user_id=user.id, filename=filename[:255], size_bytes=size_bytes,
                    content_type=ALLOWED_EXTENSIONS[ext], storage_key="")
    session.add(upload)
    session.flush()
    upload.storage_key = f"uploads/{user_folder(user.id)}/{upload.id}{ext}"
    presigned = storage.presign_upload(upload.storage_key, upload.content_type, max_bytes=max_bytes)
    return upload, presigned


def complete_upload(session: Session, storage: Storage, user: User, upload_id: str, *, signed_ttl: int) -> Upload:
    upload = session.get(Upload, upload_id)
    if upload is None or upload.user_id != user.id:
        raise NotFound()
    if upload.status == UploadStatus.READY:
        return upload

    size = storage.size(upload.storage_key)
    if size is None:
        raise AppError("upload_incomplete")
    if size > user.plan.max_upload_mb * 1024 * 1024:
        _reject(storage, upload)
        raise AppError("upload_too_large", 413)

    target = storage.local_path(upload.storage_key) or storage.signed_url(upload.storage_key, expires=signed_ttl)
    try:
        width, height, _, duration = ffmpeg.video_info(target)
    except SmartCutsError as exc:
        _reject(storage, upload)
        raise AppError("invalid_video", detail=exc.detail) from exc
    if duration <= 0:
        _reject(storage, upload)
        raise AppError("invalid_video")
    if duration / 60 > user.plan.max_video_minutes:
        _reject(storage, upload)
        raise AppError(
            "video_too_long",
            message=f"El vídeo dura {duration / 60:.0f} min y tu plan permite hasta "
                    f"{user.plan.max_video_minutes} min por vídeo.",
        )

    upload.size_bytes = size
    upload.duration_seconds = duration
    upload.width, upload.height = width, height
    upload.status = UploadStatus.READY
    return upload


def _reject(storage: Storage, upload: Upload) -> None:
    upload.status = UploadStatus.REJECTED
    storage.delete_prefix(upload.storage_key)


# --------------------------------------------------------------------------- jobs


def create_job(
    session: Session, user: User, *, upload_id: str, max_clips: int, language: str, now: datetime
) -> Job:
    # Bloquea la fila del usuario (Postgres) para que dos peticiones simultáneas no se salten la cuota.
    session.execute(select(User.id).where(User.id == user.id).with_for_update())
    plan: Plan = user.plan

    upload = session.get(Upload, upload_id)
    if upload is None or upload.user_id != user.id:
        raise NotFound()
    if upload.status != UploadStatus.READY or upload.duration_seconds is None:
        raise AppError("upload_not_ready", 409)
    if max_clips < 1 or max_clips > plan.max_clips_per_job:
        raise AppError("too_many_clips", message=f"Tu plan permite hasta {plan.max_clips_per_job} clips por vídeo.")
    if running_jobs(session, user) >= plan.max_concurrent_jobs:
        raise AppError("too_many_jobs", 429)

    minutes = billable_minutes(upload.duration_seconds)
    usage = usage_for(session, user, now)
    if minutes > usage.remaining_minutes:
        raise AppError(
            "quota_exceeded", 402,
            message=f"Este vídeo necesita {minutes:g} min y te quedan {usage.remaining_minutes:g} min "
                    f"de tu plan este mes.",
        )

    job = Job(
        user_id=user.id,
        upload_id=upload.id,
        title=PurePath(upload.filename).stem[:255] or "Vídeo",
        status=JobStatus.QUEUED,
        stage="queued",
        video_minutes=minutes,
        max_clips=max_clips,
        options={"language": language},
        created_at=now,
        expires_at=now + timedelta(days=plan.retention_days),
    )
    session.add(job)
    session.flush()
    # Los minutos se reservan al encolar y se devuelven si el procesamiento falla.
    session.add(UsageEvent(user_id=user.id, job_id=job.id, kind="reserve", minutes=minutes,
                           period=usage.period, created_at=now))
    log.info("job.created", job_id=job.id, user_id=user.id, minutes=minutes)
    return job


def refund_job(session: Session, job: Job, now: datetime, note: str) -> None:
    """Devuelve los minutos reservados (idempotente)."""
    reserved = session.scalars(select(UsageEvent).where(UsageEvent.job_id == job.id)).all()
    balance = sum(e.minutes for e in reserved)
    if balance <= 0:
        return
    reserve_period = next((e.period for e in reserved if e.kind == "reserve"), period_of(now))
    session.add(UsageEvent(user_id=job.user_id, job_id=job.id, kind="refund", minutes=-balance,
                           period=reserve_period, note=note[:255], created_at=now))


def get_job(session: Session, user: User, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise NotFound()
    return job


def list_jobs(session: Session, user: User, limit: int = 50) -> list[Job]:
    return list(
        session.scalars(select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(limit))
    )


def delete_job(session: Session, storage: Storage, user: User, job_id: str, now: datetime) -> None:
    job = get_job(session, user, job_id)
    if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
        raise AppError("validation_error", 409, message="No se puede borrar un vídeo mientras se procesa.")
    storage.delete_prefix(clips_prefix(user.id, job.id))
    if job.upload_id:
        upload = session.get(Upload, job.upload_id)
        if upload is not None:
            storage.delete_prefix(upload.storage_key)
            session.delete(upload)
    session.delete(job)
