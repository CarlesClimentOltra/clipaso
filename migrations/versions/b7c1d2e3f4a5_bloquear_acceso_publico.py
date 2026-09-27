"""Bloquea el acceso público a las tablas (Supabase).

Supabase concede por defecto permisos sobre el esquema `public` a los roles
`anon` y `authenticated`, que son los que usa cualquiera con la clave pública
de la web. Nuestra web nunca consulta la base de datos directamente (todo pasa
por la API, que se conecta como propietaria), así que se retiran esos permisos
y se activa RLS sin políticas como segunda barrera.

Solo afecta a Postgres; en SQLite (desarrollo) no hace nada.

Revision ID: b7c1d2e3f4a5
Revises: a3e8946fb6a4
Create Date: 2026-09-27
"""

from __future__ import annotations

from alembic import op

revision = "b7c1d2e3f4a5"
down_revision = "a3e8946fb6a4"
branch_labels = None
depends_on = None

TABLES = ["plans", "users", "uploads", "jobs", "clips", "usage_events", "alembic_version"]

LOCKDOWN = """
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', r);
      EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', r);
      -- Tablas que creen futuras migraciones (las ejecuta el rol propietario de la conexión).
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', r);
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', r);
    END IF;
  END LOOP;
END $$;
"""


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(LOCKDOWN)


def downgrade() -> None:
    # No se restauran los permisos públicos: reabrir el acceso nunca debe ser automático.
    pass
