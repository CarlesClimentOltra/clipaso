"""Copia de seguridad de la base de datos: se vuelca, se guarda y se restaura igual."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from clipaso.infra.config import Settings
from clipaso.interfaces.api.app import create_app
from clipaso.saas import backup
from clipaso.saas.db import session_scope, utcnow
from clipaso.saas.models import User


def test_backup_roundtrip(client, tmp_path):
    client.get("/me", headers={"Authorization": "Bearer dev:ana@example.com"})
    storage = client.app.state.storage
    now = utcnow()
    storage.put_bytes(backup.key_for((now - timedelta(days=backup.KEEP_DAYS)).date()), b"vieja", "application/gzip")
    key = backup.run_backup(client.app.state.sessions, storage, now)
    assert storage.size(key) and storage.size(backup.key_for((now - timedelta(days=30)).date())) is None

    other = Settings(data_dir=tmp_path / "otra", output_dir=tmp_path / "out2", _env_file=None)
    with TestClient(create_app(other)) as fresh, session_scope(fresh.app.state.sessions) as s:
        counts = backup.restore(s, storage.read_bytes(key))
        user = s.get(User, "dev|ana@example.com")
        assert counts["users"] == 1 and user.email == "ana@example.com" and user.created_at.tzinfo is not None


def test_ready_checks_database(client):
    assert client.get("/health/ready").json() == {"status": "ok"}
