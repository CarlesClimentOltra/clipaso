"""Copia de seguridad diaria de la base de datos en el almacenamiento (R2, en la UE).

Se vuelca cada tabla a JSON comprimido (independiente de la versión de Postgres, y se puede
restaurar también en SQLite para inspeccionarla). Se guardan `KEEP_DAYS` días. Los vídeos no se
copian: caducan solos y el original lo tiene el usuario.

    clipaso backup                    (copia ahora)
    clipaso restore copia.json.gz     (en una base vacía, con las migraciones aplicadas)
"""

from __future__ import annotations

import gzip
import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session, sessionmaker

import clipaso.saas.models  # noqa: F401  (registra las tablas en Base.metadata)
from clipaso.domain.ports import Storage
from clipaso.infra.logging import get_logger
from clipaso.saas.db import Base

log = get_logger(__name__)

PREFIX = "backups/db/"
KEEP_DAYS = 30


def _encode(value):
    if isinstance(value, datetime):
        return {"$dt": value.isoformat()}
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"tipo no serializable: {type(value).__name__}")


def _decode(obj: dict):
    if "$dt" in obj and len(obj) == 1:
        return datetime.fromisoformat(obj["$dt"])
    if "$date" in obj and len(obj) == 1:
        return date.fromisoformat(obj["$date"])
    return obj


def dump(session: Session) -> bytes:
    tables = {
        table.name: [dict(row) for row in session.execute(select(table)).mappings()]
        for table in Base.metadata.sorted_tables
    }
    data = {"version": 1, "created_at": datetime.now().isoformat(), "tables": tables}
    return gzip.compress(json.dumps(data, default=_encode, ensure_ascii=False).encode(), compresslevel=6)


def restore(session: Session, blob: bytes) -> dict[str, int]:
    """Carga una copia en una base vacía (se niega si ya hay usuarios, para no mezclar datos)."""
    data = json.loads(gzip.decompress(blob), object_hook=_decode)
    users = Base.metadata.tables["users"]
    if session.scalar(select(func.count()).select_from(users)):
        raise RuntimeError("La base de datos no está vacía: restaura en una base nueva.")
    counts = {}
    for table in Base.metadata.sorted_tables:  # padres antes que hijos (claves ajenas)
        rows = data["tables"].get(table.name, [])
        known = set(table.columns.keys())
        rows = [{k: v for k, v in row.items() if k in known} for row in rows]
        if rows:
            if table.name == "plans":
                session.execute(table.delete())  # los crea la API al arrancar: se sustituyen por los de la copia
            session.execute(insert(table), rows)
        counts[table.name] = len(rows)
    return counts


def key_for(day: date) -> str:
    return f"{PREFIX}{day.isoformat()}.json.gz"


def run_backup(sessions: sessionmaker[Session], storage: Storage, now: datetime) -> str:
    with sessions() as session:
        blob = dump(session)
    key = key_for(now.date())
    storage.put_bytes(key, blob, "application/gzip")
    storage.delete_prefix(key_for(now.date() - timedelta(days=KEEP_DAYS)))
    log.info("backup.done", key=key, size_kb=round(len(blob) / 1024, 1))
    return key
