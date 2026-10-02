"""registro de cupos diarios: borrar un proyecto no devuelve el cupo del día

Revision ID: d2e6f9a3b5c8
Revises: c1d5e8a2f4b7
Create Date: 2026-10-02 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'd2e6f9a3b5c8'
down_revision = 'c1d5e8a2f4b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'daily_actions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(128), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(24), nullable=False),
        sa.Column('task_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_daily_actions_user_kind_created', 'daily_actions', ['user_id', 'kind', 'created_at'])
    op.create_index('ix_daily_actions_task_id', 'daily_actions', ['task_id'])


def downgrade() -> None:
    op.drop_index('ix_daily_actions_task_id', 'daily_actions')
    op.drop_index('ix_daily_actions_user_kind_created', 'daily_actions')
    op.drop_table('daily_actions')
