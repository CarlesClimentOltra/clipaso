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

from clipaso.domain.errors import ClipasoError
from clipaso.domain.ports import Storage, UploadedPart
from clipaso.infra import ffmpeg
from clipaso.infra.logging import get_logger
from clipaso.saas.db import utcnow
from clipaso.saas.errors import AppError, NotFound
from clipaso.saas.models import Job, JobStatus, Plan, Upload, UploadStatus, UsageEvent, User
from clipaso.saas.plans import DEFAULT_PLAN, DEV_PLAN

log = get_logger(__name__)

ALLOWED_EXTENSIONS = {".mp4": "video/mp4", ".mov": "video/quicktime", ".mkv": "video/x-matroska",
                      ".webm": "video/webm", ".m4v": "video/mp4",
                      # Audio (audiograma y «del vídeo al texto»).
                      ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".ogg": "audio/ogg",
                      ".opus": "audio/ogg", ".aac": "audio/aac", ".flac": "audio/flac"}
AUDIO_MODES = ("audiogram", "text")  # los únicos modos que aceptan un archivo de solo audio


def is_audio(upload: Upload) -> bool:
    return (upload.content_type or "").startswith("audio/")


def user_folder(user_id: str) -> str:
    """Carpeta de almacenamiento del usuario: estable, sin caracteres problemáticos ni datos personales."""
    return "u" + hashlib.sha256(user_id.encode()).hexdigest()[:20]


def clips_prefix(user_id: str, job_id: str) -> str:
    return f"clips/{user_folder(user_id)}/{job_id}/"


def job_prefix(user_id: str, job_id: str) -> str:
    """Archivos de trabajo del proyecto: transcripción, señales y vista previa (ver saas/artifacts.py)."""
    return f"jobs/{user_folder(user_id)}/{job_id}/"


def period_of(moment: datetime) -> str:
    return moment.strftime("%Y-%m")


MIN_TRIM_SECONDS = 5.0


HIGH_RES_FACTOR = 2  # medido: procesar 4K cuesta entre 1,7 y 3,4 veces más que 1080p (deploy/benchmark.py)


def minutes_factor(upload: Upload) -> int:
    """Los vídeos de más de 1080p (2.7K, 4K…) cuentan el doble: decodificarlos es lo que más cuesta."""
    if upload.width and upload.height and min(upload.width, upload.height) > 1080:
        return HIGH_RES_FACTOR
    return 1


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


def is_admin(user: User) -> bool:
    return bool(user.plan and user.plan.unlimited)


def apply_admin(session: Session, user: User, admin_emails: list[str]) -> None:
    """Las cuentas de desarrollo (por email, en la configuración) pasan al plan sin límites."""
    if user.email and user.email.lower() in {e.strip().lower() for e in admin_emails} and user.plan_code != DEV_PLAN:
        user.plan_code = DEV_PLAN
        session.flush()
        session.expire(user, ["plan"])
        log.info("user.admin", user_id=user.id)


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


MIN_PART_SIZE = 16 * 1024 * 1024  # R2/S3 exigen ≥5 MiB por parte (salvo la última)
MAX_PARTS = 9000  # el límite del protocolo es 10 000; dejamos margen
MAX_PARTS_PER_REQUEST = 100


def choose_part_size(size_bytes: int) -> int:
    """Partes de 16 MiB, o más grandes si el fichero necesitaría demasiadas."""
    needed = math.ceil(size_bytes / MAX_PARTS)
    if needed <= MIN_PART_SIZE:
        return MIN_PART_SIZE
    mib = 1024 * 1024
    return math.ceil(needed / mib) * mib


def part_count(upload: Upload) -> int:
    return max(1, math.ceil(upload.size_bytes / (upload.part_size or MIN_PART_SIZE)))


def _owned_upload(session: Session, user: User, upload_id: str) -> Upload:
    upload = session.get(Upload, upload_id)
    if upload is None or upload.user_id != user.id:
        raise NotFound()
    return upload


def _pending_upload(session: Session, user: User, upload_id: str) -> Upload:
    upload = _owned_upload(session, user, upload_id)
    if upload.status != UploadStatus.PENDING or not upload.multipart_id:
        raise AppError("upload_incomplete", 409, key="upload_inactive")
    return upload


def create_upload(
    session: Session, storage: Storage, user: User, *, filename: str, size_bytes: int, content_type: str
) -> Upload:
    ext = PurePath(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError("unsupported_format")
    max_bytes = user.plan.max_upload_mb * 1024 * 1024
    if size_bytes <= 0 or size_bytes > max_bytes:
        raise AppError("upload_too_large", 413)

    upload = Upload(user_id=user.id, filename=filename[:255], size_bytes=size_bytes,
                    content_type=ALLOWED_EXTENSIONS[ext], storage_key="", part_size=choose_part_size(size_bytes))
    session.add(upload)
    session.flush()
    upload.storage_key = f"uploads/{user_folder(user.id)}/{upload.id}{ext}"
    upload.multipart_id = storage.create_multipart(upload.storage_key, upload.content_type)
    return upload


def presign_parts(
    session: Session, storage: Storage, user: User, upload_id: str, part_numbers: list[int], *, ttl: int
) -> dict[int, str]:
    upload = _pending_upload(session, user, upload_id)
    total = part_count(upload)
    if not part_numbers or len(part_numbers) > MAX_PARTS_PER_REQUEST or any(n < 1 or n > total for n in part_numbers):
        raise AppError("validation_error")
    return {
        n: storage.presign_part(upload.storage_key, upload.multipart_id, n, max_bytes=upload.part_size, expires=ttl)
        for n in sorted(set(part_numbers))
    }


def uploaded_parts(session: Session, storage: Storage, user: User, upload_id: str) -> list[UploadedPart]:
    """Partes ya subidas: permite reanudar una subida interrumpida sin repetirlas."""
    upload = _pending_upload(session, user, upload_id)
    return storage.list_parts(upload.storage_key, upload.multipart_id)


def abort_upload(session: Session, storage: Storage, user: User, upload_id: str) -> None:
    upload = _owned_upload(session, user, upload_id)
    if upload.status == UploadStatus.PENDING:
        if upload.multipart_id:
            storage.abort_multipart(upload.storage_key, upload.multipart_id)
        _reject(storage, upload)


def complete_upload(
    session: Session, storage: Storage, user: User, upload_id: str, parts: list[UploadedPart], *, signed_ttl: int
) -> Upload:
    upload = _owned_upload(session, user, upload_id)
    if upload.status == UploadStatus.READY:
        return upload
    upload = _pending_upload(session, user, upload_id)

    expected = part_count(upload)
    numbers = sorted(p.part_number for p in parts)
    if numbers != list(range(1, expected + 1)):
        raise AppError("upload_incomplete", key="upload_missing_parts")
    try:
        storage.complete_multipart(upload.storage_key, upload.multipart_id, parts)
    except Exception as exc:  # partes corruptas, caducadas o inexistentes
        raise AppError("upload_incomplete", detail=str(exc)) from exc
    upload.multipart_id = None

    size = storage.size(upload.storage_key)
    if size is None:
        raise AppError("upload_incomplete")
    if size != upload.size_bytes or size > user.plan.max_upload_mb * 1024 * 1024:
        _reject(storage, upload)
        raise AppError("upload_too_large" if size > upload.size_bytes else "upload_incomplete", 413)

    target = storage.local_path(upload.storage_key) or storage.signed_url(upload.storage_key, expires=signed_ttl)
    try:
        if is_audio(upload):
            width, height, duration = None, None, ffmpeg.audio_duration(target)
        else:
            width, height, _, duration = ffmpeg.video_info(target)
    except ClipasoError as exc:
        _reject(storage, upload)
        raise AppError("invalid_video", detail=exc.detail) from exc
    if duration <= 0:
        _reject(storage, upload)
        raise AppError("invalid_video")
    if duration / 60 > user.plan.max_video_minutes:
        _reject(storage, upload)
        raise AppError(
            "video_too_long", key="video_too_long_detail",
            params={"minutes": f"{duration / 60:.0f}", "limit": user.plan.max_video_minutes},
        )

    upload.duration_seconds = duration
    upload.width, upload.height = width, height
    upload.status = UploadStatus.READY
    return upload


def purge_upload(storage: Storage, upload: Upload) -> None:
    """Borra el vídeo original (tras procesarlo o al caducar). El registro se conserva."""
    if upload.multipart_id:
        storage.abort_multipart(upload.storage_key, upload.multipart_id)
        upload.multipart_id = None
    storage.delete_prefix(upload.storage_key)
    upload.status = UploadStatus.PURGED


def _reject(storage: Storage, upload: Upload) -> None:
    upload.status = UploadStatus.REJECTED
    storage.delete_prefix(upload.storage_key)


# --------------------------------------------------------------------------- jobs


def create_job(
    session: Session, user: User, *, upload_id: str, max_clips: int, language: str, now: datetime,
    options: dict | None = None, trim: tuple[float, float] | None = None,
) -> Job:
    """`options`: formato, duración, tema, estilo de subtítulos, marca y si conservar el original.
    `trim`: tramo (inicio, fin) en segundos si solo se quiere una parte; el worker recorta el original
    antes de procesarlo y solo se cobran los minutos del tramo."""
    # Bloquea la fila del usuario (Postgres) para que dos peticiones simultáneas no se salten la cuota.
    session.execute(select(User.id).where(User.id == user.id).with_for_update())
    plan: Plan = user.plan

    upload = session.get(Upload, upload_id)
    if upload is None or upload.user_id != user.id:
        raise NotFound()
    if upload.status != UploadStatus.READY or upload.duration_seconds is None:
        raise AppError("upload_not_ready", 409)
    if max_clips < 1 or max_clips > plan.max_clips_per_job:
        raise AppError("too_many_clips", key="plan_clip_limit", params={"limit": plan.max_clips_per_job})
    if running_jobs(session, user) >= plan.max_concurrent_jobs:
        raise AppError("too_many_jobs", 429)

    options = dict(options or {})
    if is_audio(upload) and options.get("mode") not in AUDIO_MODES:
        raise AppError("validation_error", key="audio_needs_audio_mode")
    if options.get("format") == "original":
        if not (upload.width and upload.height):
            raise AppError("upload_not_ready", 409)
        options["source_size"] = [upload.width, upload.height]
    seconds = upload.duration_seconds
    if trim is not None:
        start, end = round(max(0.0, trim[0]), 3), round(min(trim[1], upload.duration_seconds), 3)
        if end - start < MIN_TRIM_SECONDS:
            raise AppError("validation_error", key="trim_too_short", params={"min": f"{MIN_TRIM_SECONDS:.0f}"})
        if start > 0.5 or end < upload.duration_seconds - 0.5:  # si es casi todo, no merece la pena recortar
            options["trim"] = [start, end]
            seconds = end - start
    minutes = billable_minutes(seconds) * minutes_factor(upload)
    if minutes != billable_minutes(seconds):
        options["minutes_factor"] = minutes_factor(upload)
    usage = usage_for(session, user, now)
    if minutes > usage.remaining_minutes and not user.plan.unlimited:
        raise AppError(
            "quota_exceeded", 402, key="quota_detail",
            params={"needed": f"{minutes:g}", "remaining": f"{usage.remaining_minutes:g}"},
        )

    job = Job(
        user_id=user.id,
        upload_id=upload.id,
        title=PurePath(upload.filename).stem[:255] or "Vídeo",
        status=JobStatus.QUEUED,
        stage="queued",
        video_minutes=minutes,
        max_clips=max_clips,
        options={**options, "language": language},
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
        raise AppError("validation_error", 409, key="delete_while_processing")
    storage.delete_prefix(clips_prefix(user.id, job.id))
    storage.delete_prefix(job_prefix(user.id, job.id))
    if job.upload_id:
        upload = session.get(Upload, job.upload_id)
        if upload is not None:
            storage.delete_prefix(upload.storage_key)
            session.delete(upload)
    session.delete(job)


# --------------------------------------------------------------------------- cuenta


def delete_account(session: Session, storage: Storage, user: User) -> None:
    """Borra todos los datos del usuario: archivos (subidas, clips, miniaturas) y filas de la BD.

    La identidad en el proveedor de autenticación (Supabase) la borra quien llama, después de
    confirmar esta transacción: así, si eso falla, reintentar sigue funcionando.
    """
    if running_jobs(session, user) > 0:
        raise AppError("account_busy", 409)
    for upload in session.scalars(select(Upload).where(Upload.user_id == user.id, Upload.multipart_id.is_not(None))):
        storage.abort_multipart(upload.storage_key, upload.multipart_id)
    folder = user_folder(user.id)
    removed = sum(storage.delete_prefix(f"{area}/{folder}/") for area in ("clips", "uploads", "jobs", "brand"))
    # Uploads, jobs, clips y consumo se borran en cascada (ON DELETE CASCADE).
    session.delete(user)
    session.flush()
    log.info("account.deleted", files=removed)
