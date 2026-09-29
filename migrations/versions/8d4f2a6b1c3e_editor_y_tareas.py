"""editor de clips, textos para publicar, preferencias y tareas

Revision ID: 8d4f2a6b1c3e
Revises: 5c2d8e1f0a7b
Create Date: 2026-09-27 23:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import clipaso.saas.models

revision = '8d4f2a6b1c3e'
down_revision = '5c2d8e1f0a7b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('preferences', sa.JSON(), nullable=False, server_default='{}'))

    with op.batch_alter_table('clips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('hashtags', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('rating', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('word_edits', sa.JSON(), nullable=False, server_default='{}'))
        batch_op.add_column(sa.Column('caption_style', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('status', sa.String(length=16), nullable=False, server_default='ready'))
        batch_op.add_column(sa.Column('render_error', sa.String(length=255), nullable=True))

    op.create_table(
        'tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=128), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('clip_id', sa.String(length=36), nullable=True),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_detail', sa.Text(), nullable=True),
        sa.Column('created_at', clipaso.saas.models.UTCDateTime(timezone=True), nullable=False),
        sa.Column('started_at', clipaso.saas.models.UTCDateTime(timezone=True), nullable=True),
        sa.Column('finished_at', clipaso.saas.models.UTCDateTime(timezone=True), nullable=True),
        sa.Column('heartbeat_at', clipaso.saas.models.UTCDateTime(timezone=True), nullable=True),
        sa.Column('dispatched_at', clipaso.saas.models.UTCDateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['clip_id'], ['clips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.create_index('ix_tasks_status_created', ['status', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_job_id'), ['job_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tasks_user_id'), ['user_id'], unique=False)

    # Misma barrera que el resto de tablas en Supabase (ver b7c1d2e3f4a5): sin acceso público.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE tasks ENABLE ROW LEVEL SECURITY")
        op.execute("""
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.tasks FROM anon, authenticated';
  END IF;
END $$;
""")


def downgrade() -> None:
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tasks_user_id'))
        batch_op.drop_index(batch_op.f('ix_tasks_job_id'))
        batch_op.drop_index('ix_tasks_status_created')
    op.drop_table('tasks')
    with op.batch_alter_table('clips', schema=None) as batch_op:
        for col in ('render_error', 'status', 'version', 'caption_style', 'word_edits', 'rating', 'hashtags',
                    'description'):
            batch_op.drop_column(col)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('preferences')
