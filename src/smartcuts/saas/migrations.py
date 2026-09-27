"""Migraciones de esquema (Alembic) invocables desde código y desde la CLI."""

from __future__ import annotations

from alembic import command
from alembic.config import Config

from smartcuts.infra.config import PROJECT_ROOT, Settings


def alembic_config(settings: Settings) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    cfg.attributes["database_url"] = settings.database_url()
    if settings.database_url().startswith("sqlite"):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def upgrade_database(settings: Settings, revision: str = "head") -> None:
    command.upgrade(alembic_config(settings), revision)


def make_migration(settings: Settings, message: str) -> None:
    command.revision(alembic_config(settings), message=message, autogenerate=True)
