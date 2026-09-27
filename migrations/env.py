"""Entorno de Alembic: toma la URL de la configuración de SmartCuts."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool

from smartcuts.saas import models  # noqa: F401  (registra las tablas en Base.metadata)
from smartcuts.saas.db import Base

config = context.config
url = config.attributes["database_url"]
target_metadata = Base.metadata
is_sqlite = url.startswith("sqlite")


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, render_as_batch=is_sqlite)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url, poolclass=pool.NullPool)  # conexión corta solo para migrar
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=is_sqlite)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
