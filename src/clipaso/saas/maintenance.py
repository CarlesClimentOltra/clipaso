"""Limpieza periódica: cumple la retención prometida en los planes y no acumula datos.

- Proyectos caducados (según `retention_days` del plan): se borran sus clips del
  almacenamiento y el proyecto queda como `expired` en el histórico.
- Subidas abandonadas (a medias o sin llegar a procesarse) y originales de
  proyectos fallidos: se borran pasado un margen.
- Carpetas de trabajo del worker (audio, transcripción…): se borran pasado un margen.

La ejecuta el worker cada hora y también `clipaso cleanup`. Es idempotente.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from clipaso.domain.ports import Storage
from clipaso.infra.config import Settings
from clipaso.infra.logging import get_logger
from clipaso.saas.db import session_scope, utcnow
from clipaso.saas.models import Job, JobStatus, Upload, UploadStatus
from clipaso.saas.services import clips_prefix, job_prefix, purge_upload

log = get_logger(__name__)


@dataclass
class CleanupReport:
    expired_jobs: int = 0
    purged_uploads: int = 0
    workspaces: int = 0


def expire_jobs(session: Session, storage: Storage, now) -> int:
    jobs = session.scalars(
        select(Job).where(Job.status.in_([JobStatus.DONE, JobStatus.FAILED]), Job.expires_at < now)
    ).all()
    for job in jobs:
        storage.delete_prefix(clips_prefix(job.user_id, job.id))
        storage.delete_prefix(job_prefix(job.user_id, job.id))
        job.clips = []
        job.status = JobStatus.EXPIRED
        if job.upload_id and (upload := session.get(Upload, job.upload_id)) and upload.status != UploadStatus.PURGED:
            purge_upload(storage, upload)
    return len(jobs)


def purge_stale_uploads(session: Session, storage: Storage, now, max_age: timedelta) -> int:
    """Subidas sin terminar, sin usar o de proyectos fallidos, más antiguas que `max_age`."""
    limit = now - max_age
    active = select(Job.upload_id).where(
        Job.upload_id.is_not(None), Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])
    )
    uploads = session.scalars(
        select(Upload).where(
            Upload.status.in_([UploadStatus.PENDING, UploadStatus.READY]),
            Upload.created_at < limit,
            Upload.id.not_in(active),
        )
    ).all()
    for upload in uploads:
        purge_upload(storage, upload)
    return len(uploads)


def purge_workspaces(jobs_dir: Path, max_age: timedelta) -> int:
    if not jobs_dir.is_dir():
        return 0
    cutoff = time.time() - max_age.total_seconds()
    removed = 0
    for folder in jobs_dir.iterdir():
        if folder.is_dir() and folder.stat().st_mtime < cutoff:
            shutil.rmtree(folder, ignore_errors=True)
            removed += 1
    return removed


def run_cleanup(settings: Settings, sessions: sessionmaker[Session], storage: Storage) -> CleanupReport:
    now = utcnow()
    report = CleanupReport()
    retention = timedelta(hours=settings.worker.temp_retention_hours)
    with session_scope(sessions) as s:
        report.expired_jobs = expire_jobs(s, storage, now)
    with session_scope(sessions) as s:
        report.purged_uploads = purge_stale_uploads(s, storage, now, retention)
    report.workspaces = purge_workspaces(settings.jobs_dir(), retention)
    if report.expired_jobs or report.purged_uploads or report.workspaces:
        log.info("cleanup.done", **report.__dict__)
    return report
