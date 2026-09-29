"""Conexión a base de datos (SQLite en desarrollo, Postgres en producción)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from clipaso.infra.config import Settings


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


def make_engine(url: str, echo: bool = False) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, echo=echo, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(conn, _):  # WAL: la API y el worker escriben a la vez sin bloquearse
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return engine
    return create_engine(url, echo=echo, pool_pre_ping=True, pool_size=5, max_overflow=5)


@lru_cache
def _factory(url: str, echo: bool) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(url, echo), expire_on_commit=False)


def session_factory(settings: Settings) -> sessionmaker[Session]:
    if settings.database_url().startswith("sqlite"):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
    return _factory(settings.database_url(), settings.database.echo)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
