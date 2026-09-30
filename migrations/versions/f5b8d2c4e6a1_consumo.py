"""consumo real de cada proyecto y tarea (tiempo, CPU, coste estimado)

Revision ID: f5b8d2c4e6a1
Revises: e3a9c7f1b2d4
Create Date: 2026-09-30 21:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'f5b8d2c4e6a1'
down_revision = 'e3a9c7f1b2d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('metrics', sa.JSON(), nullable=True))
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('metrics', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_column('metrics')
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_column('metrics')
