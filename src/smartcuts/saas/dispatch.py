"""Cómo llega un job recién creado a un worker.

- local: no hace nada; el worker (`smartcuts worker`) sondea la tabla `jobs`.
- modal: lanza una función con GPU en Modal por cada job (fase 2).
"""

from __future__ import annotations

from typing import Protocol

from smartcuts.infra.config import Settings
from smartcuts.infra.logging import get_logger

log = get_logger(__name__)


class JobDispatcher(Protocol):
    def dispatch(self, job_id: str) -> None: ...


class LocalDispatcher:
    def dispatch(self, job_id: str) -> None:
        log.info("job.dispatched", job_id=job_id, dispatcher="local")


def get_dispatcher(settings: Settings) -> JobDispatcher:
    if settings.worker.dispatcher == "local":
        return LocalDispatcher()
    raise NotImplementedError("El dispatcher 'modal' se añade en la fase 2")
