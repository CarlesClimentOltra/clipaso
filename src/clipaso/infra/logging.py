"""Logging estructurado.

En desarrollo se imprime legible en consola; en producción (`log_json=True`)
cada línea es un JSON con `job_id`, `stage`, etc., listo para agregarse.
Usa `bind_job(job_id=...)` para que todo lo que se loguee después lleve el id.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json: bool = False) -> None:
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso" if json else "%H:%M:%S"),
    ]
    renderer = (
        structlog.processors.JSONRenderer()
        if json
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    structlog.configure(
        processors=[*shared, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    # Librerías ruidosas.
    for noisy in ("httpx", "httpcore", "faster_whisper", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_job(**values: object) -> None:
    structlog.contextvars.bind_contextvars(**values)


def clear_job() -> None:
    structlog.contextvars.clear_contextvars()
