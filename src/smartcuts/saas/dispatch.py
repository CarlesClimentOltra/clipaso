"""Cómo llega un job recién creado a un worker.

- local: no hace nada; el worker (`smartcuts worker`) sondea la tabla `jobs`.
- modal: lanza una llamada a la GPU en Modal por cada job (ver deploy/modal_app.py).

Si un envío se pierde (Modal caído, red…), el job sigue en cola y el barrido
periódico (`redispatch_queued`) lo vuelve a enviar. Enviar dos veces el mismo job
es inofensivo: solo un worker consigue reclamarlo.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

import sentry_sdk
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from smartcuts.infra.config import Settings
from smartcuts.infra.logging import get_logger
from smartcuts.saas.db import session_scope, utcnow
from smartcuts.saas.models import Job, JobStatus

log = get_logger(__name__)

MODAL_CLASS = "Worker"  # clase de deploy/modal_app.py


class JobDispatcher(Protocol):
    remote: bool

    def dispatch(self, job_id: str) -> None: ...


class LocalDispatcher:
    remote = False

    def dispatch(self, job_id: str) -> None:
        log.info("job.dispatched", job_id=job_id, dispatcher="local")


class ModalDispatcher:
    remote = True

    def __init__(self, app_name: str) -> None:
        self.app_name = app_name
        self._worker = None

    def dispatch(self, job_id: str) -> None:
        if self._worker is None:
            import modal

            self._worker = modal.Cls.from_name(self.app_name, MODAL_CLASS)()
        self._worker.process.spawn(job_id)
        log.info("job.dispatched", job_id=job_id, dispatcher="modal")


def get_dispatcher(settings: Settings) -> JobDispatcher:
    if settings.worker.dispatcher == "modal":
        return ModalDispatcher(settings.worker.modal_app)
    return LocalDispatcher()


def dispatch_job(dispatcher: JobDispatcher, job: Job, now: datetime) -> bool:
    """Envía el job y anota cuándo (lo guarda quien confirme la sesión).

    Un fallo no se propaga: el job queda en cola y el barrido lo reintentará.
    """
    try:
        dispatcher.dispatch(job.id)
    except Exception as exc:
        log.error("job.dispatch_failed", job_id=job.id, error=str(exc))
        sentry_sdk.capture_exception(exc)
        return False
    if dispatcher.remote:
        job.dispatched_at = now
    return True


def redispatch_queued(settings: Settings, sessions: sessionmaker[Session], dispatcher: JobDispatcher) -> int:
    """Reenvía los jobs en cola que nunca se enviaron o cuyo envío no ha arrancado a tiempo."""
    now = utcnow()
    limit = now - timedelta(seconds=settings.worker.redispatch_after_seconds)
    with session_scope(sessions) as s:
        jobs = s.scalars(
            select(Job).where(
                Job.status == JobStatus.QUEUED,
                or_(Job.dispatched_at.is_(None), Job.dispatched_at < limit),
            ).order_by(Job.created_at)
        ).all()
        sent = sum(dispatch_job(dispatcher, job, now) for job in jobs)
    if jobs:
        log.warning("job.redispatched", pending=len(jobs), sent=sent)
    return sent
